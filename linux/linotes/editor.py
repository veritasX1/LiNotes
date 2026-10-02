"""Rich text editor for notes, modelled on Apple's Notes.

The buffer holds plain text. Paragraph styles are tags covering whole lines
(including the line break), inline styles are tags on character ranges.
List markers (bullets, numbers, check circles) are drawn in the left margin,
so the text itself stays clean. Images are child anchors.
"""

import math
import re
import threading

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
gi.require_version("Graphene", "1.0")
gi.require_version("Pango", "1.0")

from gi.repository import Gdk, GdkPixbuf, GLib, GObject, Graphene, Gtk, Pango

from . import model


PARAGRAPHS = ("title", "heading", "subheading", "body", "mono", "quote",
              "bullet", "dash", "number", "check")
LISTS = ("bullet", "dash", "number", "check")
# Highlight colors like in Apple's Notes; "h" (yellow) is the original one and stays as it is.
HIGHLIGHTS = {
    "h": (1.0, 0.85, 0.24), "h:orange": (1.0, 0.62, 0.04), "h:pink": (1.0, 0.44, 0.66),
    "h:purple": (0.75, 0.48, 0.94), "h:mint": (0.30, 0.85, 0.75), "h:blue": (0.35, 0.78, 0.98),
}
INLINE = ("b", "i", "u", "s") + tuple(HIGHLIGHTS)
# Web addresses that become clickable links (trailing punctuation is not part of the address).
LINK = re.compile(r"(?:https?://|www\.)[^\s<>\"']+[^\s<>\"'.,;:!?)\]]")
MAX_INDENT = 4
INDENT = 26
LIST_MARGIN = 30
OBJECT = "￼"

ACCENT = (0.90, 0.64, 0.0)


class NoteEditor(Gtk.TextView):
    """Emits "changed" (debounced) when the content was edited."""

    __gsignals__ = {
        "edited": (GObject.SignalFlags.RUN_FIRST, None, ()),
        "style-changed": (GObject.SignalFlags.RUN_FIRST, None, ()),
        # ">>" was typed: the window offers notes to link to.
        "link-requested": (GObject.SignalFlags.RUN_FIRST, None, ()),
        "open-note": (GObject.SignalFlags.RUN_FIRST, None, (str,)),
    }

    def __init__(self, image_loader=None):
        super().__init__()
        self.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        self.set_left_margin(36)
        self.set_right_margin(36)
        self.set_top_margin(8)
        self.set_bottom_margin(80)
        self.set_pixels_below_lines(3)
        self.add_css_class("note-editor")
        self.image_loader = image_loader
        self.anchors = {}
        self.loading = False
        self.auto_sort_checked = False
        self.typing_inline = None
        # Title of a note by id (None if it is gone) – note links show the current title.
        self.note_title = lambda _note_id: None
        self.link_start = None
        # While the note choice after ">>" is open, it gets ↑/↓/Enter/Esc first.
        self.link_keys = None

        buffer = self.get_buffer()
        self.buffer = buffer
        self.make_tags()
        buffer.connect("insert-text", self.on_insert_before)
        buffer.connect_after("insert-text", self.on_insert_after)
        buffer.connect("changed", self.on_changed)
        buffer.connect("mark-set", self.on_mark_set)

        keys = Gtk.EventControllerKey()
        keys.connect("key-pressed", self.on_key)
        self.add_controller(keys)

        click = Gtk.GestureClick()
        click.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
        click.connect("pressed", self.on_click)
        self.add_controller(click)
        motion = Gtk.EventControllerMotion()
        motion.connect("motion", self.on_motion)
        self.add_controller(motion)

        self.pending_line_style = None
        self.edit_source = None

    # ========================================================
    # TAGS
    # ========================================================

    def make_tags(self):
        table = self.buffer.get_tag_table()

        def tag(name, **properties):
            new = Gtk.TextTag(name=name)
            for key, value in properties.items():
                new.set_property(key.replace("_", "-"), value)
            table.add(new)
            return new

        tag("title", scale=1.9, weight=Pango.Weight.BOLD, pixels_below_lines=8)
        tag("heading", scale=1.45, weight=Pango.Weight.BOLD, pixels_above_lines=6, pixels_below_lines=4)
        tag("subheading", scale=1.18, weight=Pango.Weight.SEMIBOLD, pixels_above_lines=4)
        tag("body")
        tag("mono", family="Monospace", scale=0.92)
        tag("quote", left_margin=20, foreground_rgba=rgba(0.45, 0.45, 0.48), style=Pango.Style.ITALIC)
        for name in LISTS:
            tag(name)
        for level in range(1, MAX_INDENT + 1):
            tag(f"l{level}")
        tag("checked", foreground_rgba=rgba(0.55, 0.55, 0.58))

        tag("b", weight=Pango.Weight.BOLD)
        tag("i", style=Pango.Style.ITALIC)
        tag("u", underline=Pango.Underline.SINGLE)
        tag("s", strikethrough=True)
        for name, color in HIGHLIGHTS.items():
            tag(name, background_rgba=rgba(*color, 0.45))
        # Web addresses: shown as links, a click opens them (not saved – found again on every change).
        tag("link", foreground_rgba=rgba(0.72, 0.49, 0.0, 1.0), underline=Pango.Underline.SINGLE)
        tag("image", pixels_above_lines=6, pixels_below_lines=6)
        self.update_margins()

    def update_margins(self):
        """List and indentation margins depend on the level."""
        table = self.buffer.get_tag_table()
        for name in LISTS:
            table.lookup(name).set_property("left-margin", self.get_left_margin() + LIST_MARGIN)
        for level in range(1, MAX_INDENT + 1):
            table.lookup(f"l{level}").set_property(
                "left-margin", self.get_left_margin() + LIST_MARGIN + INDENT * level,
            )
        # Indent tags must win over list tags.
        for level in range(1, MAX_INDENT + 1):
            table.lookup(f"l{level}").set_priority(table.get_size() - 1)

    # ========================================================
    # LINES
    # ========================================================

    def line_bounds(self, line):
        start = self.buffer.get_iter_at_line(line)[1]
        end = start.copy()
        if not end.ends_line():
            end.forward_to_line_end()
        # Include the line break so the paragraph style survives edits.
        with_break = end.copy()
        with_break.forward_char()
        return start, end, with_break

    def line_style(self, line):
        start, _end, with_break = self.line_bounds(line)
        probe = start if not start.equal(with_break) else start
        for name in PARAGRAPHS:
            tag = self.buffer.get_tag_table().lookup(name)
            if probe.has_tag(tag):
                return name
        if line == self.buffer.get_line_count() - 1 and self.pending_line_style:
            return self.pending_line_style
        return "body"

    def line_level(self, line):
        start, _end, _with_break = self.line_bounds(line)
        for level in range(MAX_INDENT, 0, -1):
            if start.has_tag(self.buffer.get_tag_table().lookup(f"l{level}")):
                return level
        return 0

    def line_checked(self, line):
        start, _end, _with_break = self.line_bounds(line)
        return start.has_tag(self.buffer.get_tag_table().lookup("checked"))

    def set_line_style(self, line, style, level=None, checked=None):
        start, _end, with_break = self.line_bounds(line)
        buffer = self.buffer
        if level is None:
            level = self.line_level(line)
        if checked is None:
            checked = self.line_checked(line)
        for name in PARAGRAPHS + ("checked",) + tuple(f"l{n}" for n in range(1, MAX_INDENT + 1)):
            buffer.remove_tag_by_name(name, start, with_break)
        buffer.apply_tag_by_name(style, start, with_break)
        if style in LISTS and level:
            buffer.apply_tag_by_name(f"l{level}", start, with_break)
        if style == "check" and checked:
            buffer.apply_tag_by_name("checked", start, with_break)
        if start.equal(with_break):
            # Empty last line: remember the style for the next typed text.
            self.pending_line_style = style
        self.queue_draw()

    def current_line(self):
        return self.buffer.get_iter_at_mark(self.buffer.get_insert()).get_line()

    def selected_lines(self):
        bounds = self.buffer.get_selection_bounds()
        if bounds:
            return range(bounds[0].get_line(), bounds[1].get_line() + 1)
        return range(self.current_line(), self.current_line() + 1)

    # ========================================================
    # EDITING
    # ========================================================

    def on_insert_before(self, buffer, location, text, length):
        if self.loading:
            return
        line = location.get_line()
        self.insert_context = (line, self.line_style(line), self.line_level(line))
        # Inline styles continue from the character before the cursor.
        before = location.copy()
        if self.typing_inline is not None:
            self.insert_inline = set(self.typing_inline)
        elif before.backward_char() and not before.ends_line():
            self.insert_inline = {name for name in INLINE if before.has_tag(buffer.get_tag_table().lookup(name))}
        else:
            self.insert_inline = set()

    def on_insert_after(self, buffer, location, text, length):
        if self.loading:
            return
        line, style, level = self.insert_context
        end_line = location.get_line()
        start = location.copy()
        start.backward_chars(len(text))
        for name in INLINE:
            buffer.remove_tag_by_name(name, start, location)
        for name in self.insert_inline:
            buffer.apply_tag_by_name(name, start, location)
        self.trim_note_links(start, location)
        for number in range(line, end_line + 1):
            if number == line:
                self.set_line_style(number, style, level)
            else:
                self.set_line_style(number, style if style not in ("title",) else "body", level, checked=False)
        self.pending_line_style = None
        if text == ">" and not self.link_start:
            # ">>" links to another note, like in Apple's Notes.
            before = location.copy()
            if before.backward_chars(2) and buffer.get_text(before, location, False) == ">>":
                self.link_start = buffer.create_mark(None, before, True)
                GLib.idle_add(lambda: self.emit("link-requested") and False)

    def on_changed(self, buffer):
        self.queue_draw()
        if self.loading:
            return
        self.mark_links()
        if self.edit_source is not None:
            GLib.source_remove(self.edit_source)
        self.edit_source = GLib.timeout_add(700, self.emit_edited)

    def emit_edited(self):
        self.edit_source = None
        self.emit("edited")
        return False

    def flush(self):
        """Emit a pending edit right away (before switching notes)."""
        if self.edit_source is not None:
            GLib.source_remove(self.edit_source)
            self.edit_source = None
            self.emit("edited")

    def on_mark_set(self, buffer, location, mark):
        if mark.get_name() == "insert":
            self.typing_inline = None
            self.emit("style-changed")

    def on_key(self, controller, keyval, keycode, state):
        control = bool(state & Gdk.ModifierType.CONTROL_MASK)
        shift = bool(state & Gdk.ModifierType.SHIFT_MASK)
        key = Gdk.keyval_to_lower(keyval)

        if self.link_keys and self.link_keys(keyval):
            return True

        if keyval in (Gdk.KEY_Return, Gdk.KEY_KP_Enter) and not control:
            return self.handle_return()

        if keyval == Gdk.KEY_BackSpace and not control:
            return self.handle_backspace()

        if keyval in (Gdk.KEY_Tab, Gdk.KEY_ISO_Left_Tab):
            line = self.current_line()
            if self.line_style(line) in LISTS or self.buffer.get_selection_bounds():
                self.indent(-1 if (shift or keyval == Gdk.KEY_ISO_Left_Tab) else 1)
                return True
            return False

        if control and shift:
            shortcuts = {
                Gdk.KEY_t: "title", Gdk.KEY_h: "heading", Gdk.KEY_j: "subheading",
                Gdk.KEY_b: "body", Gdk.KEY_l: "check", Gdk.KEY_m: "mono",
                Gdk.KEY_7: "bullet", Gdk.KEY_ampersand: "bullet",
                Gdk.KEY_8: "dash", Gdk.KEY_parenleft: "dash",
                Gdk.KEY_9: "number", Gdk.KEY_parenright: "number",
            }
            if key in shortcuts:
                self.apply_paragraph(shortcuts[key])
                return True
            if key == Gdk.KEY_u:
                self.toggle_checked_current()
                return True
        elif control:
            inline = {Gdk.KEY_b: "b", Gdk.KEY_i: "i", Gdk.KEY_u: "u"}
            if key in inline:
                self.toggle_inline(inline[key])
                return True
            if keyval in (Gdk.KEY_apostrophe, Gdk.KEY_numbersign):
                self.apply_paragraph("quote")
                return True
            if keyval == Gdk.KEY_bracketright:
                self.indent(1)
                return True
            if keyval == Gdk.KEY_bracketleft:
                self.indent(-1)
                return True
        return False

    def handle_return(self):
        buffer = self.buffer
        if buffer.get_selection_bounds():
            buffer.delete_selection(True, True)
        line = self.current_line()
        style = self.line_style(line)
        level = self.line_level(line)
        start, end, _with_break = self.line_bounds(line)
        text = buffer.get_text(start, end, False).replace(OBJECT, "")

        if style in LISTS and not text.strip():
            # An empty list item ends the list (or outdents first).
            if level:
                self.set_line_style(line, style, level - 1)
            else:
                self.set_line_style(line, "body", 0, checked=False)
            self.emit_style()
            return True

        cursor = buffer.get_iter_at_mark(buffer.get_insert())
        buffer.begin_user_action()
        self.loading = True
        buffer.insert(cursor, "\n")
        self.loading = False
        new_line = line + 1
        # The old line keeps its style; the new one continues lists, but
        # titles and headings are followed by normal text.
        self.set_line_style(line, style, level)
        next_style = style if style in LISTS + ("mono", "quote", "body") else "body"
        # Inline styles of the split text stay where they were; new text is plain.
        self.set_line_style(new_line, next_style, level if next_style in LISTS else 0, checked=False)
        buffer.end_user_action()
        self.scroll_mark_onscreen(buffer.get_insert())
        self.emit_style()
        return True

    def handle_backspace(self):
        buffer = self.buffer
        if buffer.get_selection_bounds():
            return False
        cursor = buffer.get_iter_at_mark(buffer.get_insert())
        if not cursor.starts_line():
            return False
        line = cursor.get_line()
        style = self.line_style(line)
        if style in LISTS or style == "quote":
            # Backspace at the start of a list item removes the marker first.
            level = self.line_level(line)
            if level:
                self.set_line_style(line, style, level - 1)
            else:
                self.set_line_style(line, "body", 0, checked=False)
            self.emit_style()
            self.on_changed(buffer)
            return True
        return False

    def emit_style(self):
        self.emit("style-changed")
        self.on_changed(self.buffer)

    # ========================================================
    # FORMATTING (used by the toolbar and menus)
    # ========================================================

    def apply_paragraph(self, style):
        lines = list(self.selected_lines())
        # Toggling a list style off returns to body text, like in Notes.
        if style in LISTS and all(self.line_style(line) == style for line in lines):
            style = "body"
        for line in lines:
            level = self.line_level(line) if style in LISTS else 0
            self.set_line_style(line, style, level, checked=False if style != "check" else None)
        self.emit_style()

    def set_highlight(self, name):
        """Mark the selection (or the next typed text) in one color; name None removes
        the marking. One color per character – a new one replaces the old."""
        buffer = self.buffer
        bounds = buffer.get_selection_bounds()
        if not bounds:
            current = set(self.active_inline())
            same = name in current
            current -= set(HIGHLIGHTS)
            if name and not same:
                current.add(name)
            self.typing_inline = current
            self.emit("style-changed")
            return
        start, end = bounds
        everything = name is not None
        if name:
            tag = buffer.get_tag_table().lookup(name)
            probe = start.copy()
            while probe.compare(end) < 0:
                if not probe.has_tag(tag) and probe.get_char() not in ("\n", OBJECT):
                    everything = False
                    break
                probe.forward_char()
        for other in HIGHLIGHTS:
            buffer.remove_tag_by_name(other, start, end)
        if name and not everything:
            buffer.apply_tag_by_name(name, start, end)
        self.emit_style()

    def toggle_inline(self, name):
        if name in HIGHLIGHTS:
            self.set_highlight(name)
            return
        buffer = self.buffer
        bounds = buffer.get_selection_bounds()
        tag = buffer.get_tag_table().lookup(name)
        if not bounds:
            # No selection: switch the style for the next typed characters.
            current = self.typing_inline
            if current is None:
                cursor = buffer.get_iter_at_mark(buffer.get_insert())
                before = cursor.copy()
                current = set()
                if before.backward_char():
                    current = {n for n in INLINE if before.has_tag(buffer.get_tag_table().lookup(n))}
            current = set(current)
            current.symmetric_difference_update({name})
            self.typing_inline = current
            self.emit("style-changed")
            return
        start, end = bounds
        everything = True
        probe = start.copy()
        while probe.compare(end) < 0:
            if not probe.has_tag(tag) and probe.get_char() not in ("\n", OBJECT):
                everything = False
                break
            probe.forward_char()
        if everything:
            buffer.remove_tag(tag, start, end)
        else:
            buffer.apply_tag(tag, start, end)
        self.emit_style()

    def active_inline(self):
        if self.typing_inline is not None:
            return set(self.typing_inline)
        buffer = self.buffer
        bounds = buffer.get_selection_bounds()
        probe = bounds[0] if bounds else buffer.get_iter_at_mark(buffer.get_insert())
        if not bounds:
            probe = probe.copy()
            if not probe.backward_char():
                return set()
        return {n for n in INLINE if probe.has_tag(buffer.get_tag_table().lookup(n))}

    def current_style(self):
        return self.line_style(self.current_line())

    def indent(self, direction):
        for line in self.selected_lines():
            style = self.line_style(line)
            if style not in LISTS:
                if direction > 0:
                    style = "bullet"
                else:
                    continue
            level = max(0, min(MAX_INDENT, self.line_level(line) + direction))
            self.set_line_style(line, style, level)
        self.emit_style()

    def toggle_checked(self, line):
        if self.line_style(line) != "check":
            return
        checked = not self.line_checked(line)
        self.set_line_style(line, "check", self.line_level(line), checked=checked)
        if checked and self.auto_sort_checked:
            self.sort_checked_block(line)
        self.on_changed(self.buffer)

    def toggle_checked_current(self):
        for line in self.selected_lines():
            self.toggle_checked(line)

    def sort_checked_block(self, line):
        """Move checked items to the end of their checklist."""
        blocks = self.to_blocks()
        # Find the checklist run containing the line.
        start = line
        while start > 0 and blocks[start - 1].get("t") == "check":
            start -= 1
        end = line
        while end + 1 < len(blocks) and blocks[end + 1].get("t") == "check":
            end += 1
        run = blocks[start:end + 1]
        run.sort(key=lambda block: bool(block.get("c")))
        blocks[start:end + 1] = run
        self.load_blocks(blocks, keep_cursor=True)

    def mark_links(self):
        buffer = self.get_buffer()
        start, end = buffer.get_bounds()
        buffer.remove_tag_by_name("link", start, end)
        for match in LINK.finditer(buffer.get_text(start, end, True)):
            buffer.apply_tag_by_name("link", buffer.get_iter_at_offset(match.start()), buffer.get_iter_at_offset(match.end()))

    def link_at(self, x, y):
        """The web address under the pointer (widget coordinates), "n:<id>" for a
        link to a note, or None."""
        buffer_x, buffer_y = self.window_to_buffer_coords(Gtk.TextWindowType.WIDGET, int(x), int(y))
        found, iterator = self.get_iter_at_location(buffer_x, buffer_y)
        if found:
            for tag in iterator.get_tags():
                if model.link_target(tag.get_property("name")):
                    return tag.get_property("name")
        tag = self.get_buffer().get_tag_table().lookup("link")
        if not found or not iterator.has_tag(tag):
            return None
        start, end = iterator.copy(), iterator.copy()
        if not start.starts_tag(tag):
            start.backward_to_tag_toggle(tag)
        end.forward_to_tag_toggle(tag)
        url = self.get_buffer().get_text(start, end, True)
        return url if url.startswith(("http://", "https://")) else "https://" + url

    # ========================================================
    # LINKS TO OTHER NOTES (">>")
    # ========================================================

    def note_link_tag(self, note_id):
        """One tag per linked note, named like the saved span ("n:<id>")."""
        table = self.buffer.get_tag_table()
        tag = table.lookup(model.NOTE_LINK + note_id)
        if tag is None:
            tag = Gtk.TextTag(name=model.NOTE_LINK + note_id)
            tag.set_property("foreground-rgba", rgba(0.72, 0.49, 0.0, 1.0))
            tag.set_property("underline", Pango.Underline.SINGLE)
            table.add(tag)
        return tag

    def trim_note_links(self, start, end):
        """Typed text belongs to a note link only inside it, not at its edges."""
        names = set()
        probe = start.copy()
        while probe.compare(end) < 0:
            names.update(tag.get_property("name") for tag in probe.get_tags())
            probe.forward_char()
        for name in names:
            if not model.link_target(name):
                continue
            tag = self.buffer.get_tag_table().lookup(name)
            before = start.copy()
            inside = before.backward_char() and before.has_tag(tag) and end.has_tag(tag)
            if not inside:
                self.buffer.remove_tag(tag, start, end)

    def pending_link_query(self):
        """The text typed after ">>" while the note choice is open (None: cursor left it)."""
        if not self.link_start:
            return None
        start = self.buffer.get_iter_at_mark(self.link_start)
        start.forward_chars(2)
        cursor = self.buffer.get_iter_at_mark(self.buffer.get_insert())
        if cursor.compare(start) < 0 or cursor.get_line() != start.get_line():
            return None
        return self.buffer.get_text(start, cursor, False)

    def finish_link(self, note_id=None, title=None):
        """Replace ">>" (and what was typed after it) with a link to the note,
        or just forget the pending ">>" when note_id is None."""
        mark = self.link_start
        self.link_start = None
        if mark is None:
            return
        buffer = self.buffer
        start = buffer.get_iter_at_mark(mark)
        buffer.delete_mark(mark)
        if note_id is None:
            return
        end = buffer.get_iter_at_mark(buffer.get_insert())
        if end.compare(start) < 0 or end.get_line() != start.get_line():
            end = start.copy()
            end.forward_chars(2)
        offset = start.get_offset()
        buffer.begin_user_action()
        buffer.delete(start, end)
        buffer.insert(buffer.get_iter_at_offset(offset), title)
        buffer.apply_tag(self.note_link_tag(note_id), buffer.get_iter_at_offset(offset),
                         buffer.get_iter_at_offset(offset + len(title)))
        after = buffer.get_iter_at_offset(offset + len(title))
        if after.get_char() == " ":
            after.forward_char()
            buffer.place_cursor(after)
        else:
            buffer.place_cursor(after)
            buffer.insert_at_cursor(" ")
        buffer.end_user_action()
        self.grab_focus()

    def cursor_rect(self):
        """Where the cursor is, in widget coordinates (for the note choice popover)."""
        location = self.get_iter_location(self.buffer.get_iter_at_mark(self.buffer.get_insert()))
        x, y = self.buffer_to_window_coords(Gtk.TextWindowType.WIDGET, location.x, location.y)
        rect = Gdk.Rectangle()
        rect.x, rect.y, rect.width, rect.height = x, y, max(1, location.width), location.height
        return rect

    def on_motion(self, _controller, x, y):
        self.set_cursor_from_name("pointer" if self.link_at(x, y) else "text")

    def on_click(self, gesture, n_press, x, y):
        """Clicks on a check circle toggle the item; a click on a web address opens it."""
        url = self.link_at(x, y) if n_press == 1 else None
        if url:
            gesture.set_state(Gtk.EventSequenceState.CLAIMED)
            if model.link_target(url):
                self.emit("open-note", model.link_target(url))
            else:
                Gtk.UriLauncher.new(url).launch(self.get_root(), None, None)
            return
        buffer_x, buffer_y = self.window_to_buffer_coords(Gtk.TextWindowType.WIDGET, int(x), int(y))
        found, iterator = self.get_iter_at_location(buffer_x, buffer_y)
        if not found:
            over, iterator, _trailing = self.get_iter_at_position(buffer_x, buffer_y)
        line = iterator.get_line()
        if self.line_style(line) != "check":
            return
        marker_x = self.marker_x(line)
        if marker_x - 14 <= buffer_x <= marker_x + 12:
            gesture.set_state(Gtk.EventSequenceState.CLAIMED)
            self.toggle_checked(line)

    # ========================================================
    # DRAWING THE LIST MARKERS
    # ========================================================

    def marker_x(self, line):
        return self.get_left_margin() + LIST_MARGIN - 16 + INDENT * self.line_level(line)

    def do_snapshot_layer(self, layer, snapshot):
        if layer != Gtk.TextViewLayer.ABOVE_TEXT:
            return
        visible = self.get_visible_rect()
        first = self.get_line_at_y(visible.y)[0].get_line()
        last = self.get_line_at_y(visible.y + visible.height)[0].get_line()

        color = self.get_color()
        numbers = {}
        counter = {}
        # Numbering has to start at the top of each numbered run.
        for line in range(0, last + 1):
            style = self.line_style(line)
            level = self.line_level(line)
            if style == "number":
                counter[level] = counter.get(level, 0) + 1
                for deeper in [key for key in counter if key > level]:
                    del counter[deeper]
                numbers[line] = counter[level]
            elif style not in LISTS:
                counter = {}

        cr = snapshot.append_cairo(Graphene.Rect().init(visible.x, visible.y, visible.width, visible.height))
        for line in range(first, last + 1):
            style = self.line_style(line)
            if style not in LISTS:
                continue
            start = self.buffer.get_iter_at_line(line)[1]
            location = self.get_iter_location(start)
            y_top, height = self.get_line_yrange(start)
            # Center on the first display line of the paragraph.
            center_y = location.y + location.height / 2
            x = self.marker_x(line)
            cr.set_source_rgba(color.red, color.green, color.blue, 0.85)
            if style == "check":
                checked = self.line_checked(line)
                radius = 8
                cr.arc(x, center_y, radius, 0, 2 * math.pi)
                if checked:
                    cr.set_source_rgb(*ACCENT)
                    cr.fill()
                    cr.set_source_rgb(1, 1, 1)
                    cr.set_line_width(1.8)
                    cr.move_to(x - 3.8, center_y + 0.2)
                    cr.line_to(x - 1, center_y + 3)
                    cr.line_to(x + 4, center_y - 3)
                    cr.stroke()
                else:
                    cr.set_source_rgba(color.red, color.green, color.blue, 0.45)
                    cr.set_line_width(1.3)
                    cr.stroke()
            elif style == "bullet":
                cr.arc(x, center_y, 2.8, 0, 2 * math.pi)
                cr.fill()
            elif style == "dash":
                cr.set_line_width(1.5)
                cr.move_to(x - 5, center_y)
                cr.line_to(x + 3, center_y)
                cr.stroke()
            elif style == "number":
                layout = self.create_pango_layout(f"{numbers.get(line, 1)}.")
                _ink, logical = layout.get_pixel_extents()
                cr.move_to(x + 4 - logical.width, center_y - logical.height / 2)
                from gi.repository import PangoCairo
                PangoCairo.show_layout(cr, layout)

    # ========================================================
    # LOADING AND SAVING
    # ========================================================

    def load_blocks(self, blocks, keep_cursor=False):
        buffer = self.buffer
        offset = buffer.get_iter_at_mark(buffer.get_insert()).get_offset() if keep_cursor else 0
        self.loading = True
        buffer.begin_irreversible_action()
        for anchor in list(self.anchors):
            pass
        self.anchors = {}
        buffer.set_text("", 0)
        if not blocks:
            blocks = [{"t": "title", "x": ""}]
        for index, block in enumerate(blocks):
            kind = block.get("t", "body")
            end = buffer.get_end_iter()
            line_start_offset = end.get_offset()
            if kind == "image":
                anchor = buffer.create_child_anchor(end)
                self.add_image(anchor, block.get("f"), block.get("w"))
            else:
                block = model.refresh_note_links(block, self.note_title)
                text = block.get("x", "")
                buffer.insert(end, text)
                base = line_start_offset
                for span in block.get("s", []):
                    try:
                        start_offset, end_offset, name = span
                    except ValueError:
                        continue
                    if name in INLINE or model.link_target(name):
                        if model.link_target(name):
                            self.note_link_tag(model.link_target(name))
                        buffer.apply_tag_by_name(
                            name,
                            buffer.get_iter_at_offset(base + int(start_offset)),
                            buffer.get_iter_at_offset(base + min(int(end_offset), len(text))),
                        )
            if index < len(blocks) - 1:
                buffer.insert(buffer.get_end_iter(), "\n")
            line = buffer.get_line_count() - 1 if index == len(blocks) - 1 else buffer.get_line_count() - 2
            style = kind if kind in PARAGRAPHS else ("body" if kind != "image" else "body")
            self.set_line_style(line, style, int(block.get("l", 0)), checked=bool(block.get("c")))
            if kind == "image":
                start, _end, with_break = self.line_bounds(line)
                buffer.apply_tag_by_name("image", start, with_break)
        buffer.end_irreversible_action()
        self.loading = False
        self.mark_links()
        cursor = buffer.get_iter_at_offset(min(offset, buffer.get_char_count()))
        buffer.place_cursor(cursor)
        self.queue_draw()

    def to_blocks(self):
        buffer = self.buffer
        blocks = []
        for line in range(buffer.get_line_count()):
            start, end, _with_break = self.line_bounds(line)
            anchor = start.get_child_anchor()
            if anchor is not None and anchor in self.anchors:
                image = self.anchors[anchor]
                blocks.append({"t": "image", "f": image["file"], "w": image.get("width")})
                continue
            text = buffer.get_text(start, end, True).replace(OBJECT, "")
            block = {"t": self.line_style(line), "x": text}
            level = self.line_level(line)
            if level:
                block["l"] = level
            if block["t"] == "check":
                block["c"] = self.line_checked(line)
            spans = self.spans(start, end)
            if spans:
                block["s"] = spans
            blocks.append(block)
        # Drop trailing empty body lines.
        while len(blocks) > 1 and blocks[-1]["t"] == "body" and not blocks[-1].get("x"):
            blocks.pop()
        return blocks

    def spans(self, start, end):
        result = []
        base = start.get_offset()
        table = self.buffer.get_tag_table()
        links = []
        table.foreach(lambda tag: links.append(tag.get_property("name")) if model.link_target(tag.get_property("name")) else None)
        for name in INLINE + tuple(links):
            tag = table.lookup(name)
            probe = start.copy()
            while probe.compare(end) < 0:
                if probe.has_tag(tag) or probe.starts_tag(tag):
                    span_start = probe.get_offset()
                    if not probe.forward_to_tag_toggle(tag) or probe.compare(end) > 0:
                        probe = end.copy()
                    result.append([span_start - base, probe.get_offset() - base, name])
                elif not probe.forward_to_tag_toggle(tag):
                    break
        return sorted(result)

    # ========================================================
    # IMAGES
    # ========================================================

    def add_image(self, anchor, file_id, width=None):
        picture = Gtk.Picture()
        picture.set_can_shrink(True)
        picture.set_content_fit(Gtk.ContentFit.CONTAIN)
        picture.add_css_class("note-image")
        picture.set_size_request(360, 220)
        self.anchors[anchor] = {"file": file_id, "width": width, "picture": picture}
        self.add_child_at_anchor(picture, anchor)
        if self.image_loader and file_id:
            def load():
                try:
                    path = self.image_loader(file_id)
                except Exception as error:
                    print("LiNotes: Bild nicht geladen:", error)
                    return
                GLib.idle_add(self.show_image, picture, str(path))
            threading.Thread(target=load, daemon=True).start()

    def show_image(self, picture, path):
        try:
            pixbuf = GdkPixbuf.Pixbuf.new_from_file(path)
        except GLib.Error:
            return False
        # Handyfotos sind oft quer gespeichert, die Drehung steht im EXIF.
        pixbuf = pixbuf.apply_embedded_orientation() or pixbuf
        width = min(520, pixbuf.get_width())
        height = int(pixbuf.get_height() * width / max(1, pixbuf.get_width()))
        picture.set_size_request(width, height)
        picture.set_paintable(Gdk.Texture.new_for_pixbuf(pixbuf))
        return False

    def insert_image(self, file_id):
        buffer = self.buffer
        cursor = buffer.get_iter_at_mark(buffer.get_insert())
        if not cursor.starts_line():
            cursor.forward_to_line_end()
            buffer.insert(cursor, "\n")
        elif buffer.get_text(*self.line_bounds(cursor.get_line())[:2], False):
            buffer.insert(cursor, "\n")
            cursor.backward_char()
        self.loading = True
        anchor = buffer.create_child_anchor(cursor)
        self.loading = False
        self.add_image(anchor, file_id)
        line = cursor.get_line()
        after = buffer.get_iter_at_line(line)[1]
        after.forward_to_line_end()
        buffer.insert(after, "\n")
        self.set_line_style(line, "body", 0, checked=False)
        start, _end, with_break = self.line_bounds(line)
        buffer.apply_tag_by_name("image", start, with_break)
        self.on_changed(buffer)


def rgba(red, green, blue, alpha=1.0):
    color = Gdk.RGBA()
    color.red, color.green, color.blue, color.alpha = red, green, blue, alpha
    return color
