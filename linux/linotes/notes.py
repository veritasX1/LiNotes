"""Note list (middle column) and note pane (editor column)."""

import collections
import threading

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gdk, GdkPixbuf, GLib, GObject, Gtk

from . import model
from . import smoothscroll
from .editor import NoteEditor
from .icons import Icon, drag_source


class NoteRow(Gtk.ListBoxRow):

    def __init__(self, note, group, sync, stamp=None, unread=False):
        super().__init__()
        self.note_id = note["id"]
        self.group = group
        self.signature = self.signature_of(note, group, stamp, unread)
        data = note["data"]
        drag_source(self, "note:" + note["id"])

        box = Gtk.Box(spacing=8)
        text = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2, hexpand=True)
        title_row = Gtk.Box(spacing=5)
        if unread:
            # Changed by someone else since I looked (like Apple's blue dot).
            dot = Gtk.Box(css_classes=["unread-dot"], valign=Gtk.Align.CENTER)
            dot.set_tooltip_text("Neu geändert")
            title_row.append(dot)
        if data.get("enc"):
            title_row.append(Icon("lock", 13))
        title = Gtk.Label(label=model.note_title(note), xalign=0, ellipsize=3, hexpand=True)
        title.add_css_class("note-row-title")
        title_row.append(title)
        if note.get("share"):
            shared = Icon("person", 13)
            shared.set_tooltip_text("Geteilt")
            title_row.append(shared)
        text.append(title_row)

        meta = Gtk.Box()
        meta.add_css_class("note-row-meta")
        # Found by a search although archived: say so.
        date = Gtk.Label(label=("Vorlage · " if data.get("template") else "") + ("im Archiv · " if model.archived(note) else "")
                         + model.short_date(stamp or model.modified(note)), xalign=0)
        date.add_css_class("note-row-date")
        meta.append(date)
        preview_text = model.note_preview(note) or ("Gesperrt" if data.get("enc") else "Kein weiterer Text")
        preview = Gtk.Label(label=preview_text, xalign=0, ellipsize=3, hexpand=True)
        preview.add_css_class("note-row-preview")
        meta.append(preview)
        text.append(meta)

        if note.get("share") and note.get("updated_by") and note.get("updated_by") != sync.user_id:
            who = Gtk.Label(label=f"Zuletzt bearbeitet von {sync.user_name(note['updated_by'])}", xalign=0, ellipsize=3)
            who.add_css_class("note-row-preview")
            who.add_css_class("caption")
            text.append(who)
        box.append(text)

        image = model.note_image(note)
        if image:
            thumb = Gtk.Picture(can_shrink=True, content_fit=Gtk.ContentFit.COVER)
            thumb.set_size_request(44, 44)
            thumb.add_css_class("thumb")
            box.append(thumb)
            load_thumbnail(sync, image, thumb, share=note.get("share"))
        self.set_child(box)

    @staticmethod
    def signature_of(note, group, stamp, unread):
        """Everything the row shows comes from these; equal signature, equal row."""
        return (note["id"], group, stamp, unread, note.get("share"), note.get("updated_by"), note["data"])


# Finished thumbnails by (file id, size). The list is rebuilt on every edit; loading them again
# each time left the boxes empty for a moment, so they flickered. File ids never change content.
THUMBNAILS = collections.OrderedDict()
THUMBNAIL_LIMIT = 400


def load_thumbnail(sync, file_id, picture, size=88, share=None):
    key = (file_id, size)
    texture = THUMBNAILS.get(key)
    if texture is not None:
        THUMBNAILS.move_to_end(key)
        picture.set_paintable(texture)
        return

    def work():
        try:
            path = sync.fetch_file(file_id, share)
            pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_scale(str(path), size, size, True)
            pixbuf = pixbuf.apply_embedded_orientation() or pixbuf
        except Exception:
            return

        def show():
            texture = Gdk.Texture.new_for_pixbuf(pixbuf)
            THUMBNAILS[key] = texture
            while len(THUMBNAILS) > THUMBNAIL_LIMIT:
                THUMBNAILS.popitem(last=False)
            picture.set_paintable(texture)
            return False
        GLib.idle_add(show)
    threading.Thread(target=work, daemon=True).start()


class NoteList(Gtk.Box):

    __gsignals__ = {
        "note-selected": (GObject.SignalFlags.RUN_FIRST, None, (str,)),
        "context": (GObject.SignalFlags.RUN_FIRST, None, (str, object, float, float)),
        "open-window": (GObject.SignalFlags.RUN_FIRST, None, (str,)),
        "open-key": (GObject.SignalFlags.RUN_FIRST, None, (str,)),
    }

    def __init__(self, sync):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self.sync = sync
        self.selected_id = None
        self.updating = False
        self.is_unread = lambda _note: False
        self.add_css_class("note-list-pane")

        self.search = Gtk.SearchEntry(placeholder_text="Suchen")
        self.search.set_margin_start(10)
        self.search.set_margin_end(10)
        self.search.set_margin_top(8)
        self.search.set_margin_bottom(4)
        self.append(self.search)

        self.heading = Gtk.Label(xalign=0)
        self.heading.add_css_class("title-2")
        self.heading.set_margin_start(16)
        self.heading.set_margin_top(6)
        self.append(self.heading)
        self.count = Gtk.Label(xalign=0)
        self.count.add_css_class("dim-label")
        self.count.add_css_class("caption")
        self.count.set_margin_start(16)
        self.append(self.count)

        # What else lives in the selected folder: subfolders, lists, boards.
        self.extras = Gtk.ListBox(selection_mode=Gtk.SelectionMode.NONE)
        self.extras.add_css_class("navigation-sidebar")
        self.extras.add_css_class("folder-extras")
        self.extras.set_header_func(self.header_func)
        self.extras.connect("row-activated", lambda _box, row: self.emit("open-key", row.key))
        self.extras.set_visible(False)
        self.append(self.extras)

        self.list = Gtk.ListBox()
        self.list.add_css_class("note-list")
        self.list.add_css_class("navigation-sidebar")
        self.list.set_header_func(self.header_func)
        self.list.connect("row-selected", self.on_selected)
        click = Gtk.GestureClick(button=Gdk.BUTTON_SECONDARY)
        click.connect("pressed", self.on_context)
        self.list.add_controller(click)
        # Double-click opens the note in its own window (like Apple's Notes).
        double = Gtk.GestureClick(button=Gdk.BUTTON_PRIMARY)
        double.connect("pressed", self.on_double_click)
        self.list.add_controller(double)

        self.gallery = Gtk.FlowBox(selection_mode=Gtk.SelectionMode.SINGLE, homogeneous=True)
        self.gallery.set_valign(Gtk.Align.START)
        self.gallery.set_max_children_per_line(4)
        self.gallery.set_min_children_per_line(2)
        self.gallery.set_row_spacing(10)
        self.gallery.set_column_spacing(10)
        self.gallery.set_margin_start(10)
        self.gallery.set_margin_end(10)
        self.gallery.connect("child-activated", lambda _box, child: self.emit("note-selected", child.note_id))

        self.stack = Gtk.Stack()
        list_scroller = Gtk.ScrolledWindow(vexpand=True, child=self.list)
        smoothscroll.enable(list_scroller)
        list_scroller.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        gallery_scroller = Gtk.ScrolledWindow(vexpand=True, child=self.gallery)
        smoothscroll.enable(gallery_scroller)
        gallery_scroller.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.empty = Adw.StatusPage(title="Keine Notizen", vexpand=True)
        self.empty.add_css_class("compact")
        self.stack.add_named(list_scroller, "list")
        self.stack.add_named(gallery_scroller, "gallery")
        self.stack.add_named(self.empty, "empty")
        self.append(self.stack)
        self.mode = "list"

    def show_extras(self, entries):
        """entries: [(key, icon, label, count, group)]"""
        self.extras.remove_all()
        for key, icon, label, count, group in entries:
            row = Gtk.ListBoxRow()
            row.key, row.group = key, group
            box = Gtk.Box(spacing=10)
            box.set_margin_top(4)
            box.set_margin_bottom(4)
            box.set_margin_start(6)
            box.set_margin_end(6)
            symbol = Icon(icon, 16)
            symbol.add_css_class("accent-icon")
            box.append(symbol)
            box.append(Gtk.Label(label=label, xalign=0, hexpand=True, ellipsize=3))
            number = Gtk.Label(label=str(count))
            number.add_css_class("sidebar-count")
            box.append(number)
            row.set_child(box)
            self.extras.append(row)
        self.extras.set_visible(bool(entries))

    def header_func(self, row, before):
        if row.group and (before is None or before.group != row.group):
            label = Gtk.Label(label=row.group, xalign=0)
            label.add_css_class("list-section-header")
            row.set_header(label)
        else:
            row.set_header(None)

    def set_mode(self, mode):
        self.mode = mode
        if mode == "gallery":
            self.fill_gallery()

    def show(self, title, notes, selected_id=None, empty_text="Keine Notizen"):
        self.updating = True
        self.heading.set_label(title)
        count = len(notes)
        self.count.set_label("1 Notiz" if count == 1 else f"{count} Notizen")
        ordered = list(model.sort_notes(notes, self.sync.settings().get("note_sort", "modified")))
        if self.update_rows(ordered, selected_id):
            self.stack.set_visible_child_name(self.mode)
            self.shown_notes = notes
            self.gallery_dirty = True
            if self.mode == "gallery":
                self.fill_gallery()
            self.updating = False
            return
        self.list.remove_all()
        child = self.gallery.get_first_child()
        while child is not None:
            following = child.get_next_sibling()
            self.gallery.remove(child)
            child = following

        select_row = None
        for note, group, stamp in ordered:
            row = NoteRow(note, group, self.sync, stamp, unread=self.is_unread(note))
            self.list.append(row)
            if note["id"] == selected_id:
                select_row = row
        # Gallery cards only when the gallery is shown (building 300 of them on every save was slow).
        self.shown_notes = notes
        self.gallery_dirty = True
        if self.mode == "gallery":
            self.fill_gallery()

        if not notes:
            self.empty.set_title(empty_text)
            self.stack.set_visible_child_name("empty")
        else:
            self.stack.set_visible_child_name(self.mode)
        if select_row is not None:
            self.list.select_row(select_row)
        self.selected_id = selected_id if select_row is not None else None
        self.updating = False

    def update_rows(self, ordered, selected_id):
        """Same notes in the same order as shown: rebuild only the rows whose note changed. Saving
        an edit rebuilt all rows (0.45 s with 300 notes) although only one had changed (b9046682)."""
        rows = []
        while (row := self.list.get_row_at_index(len(rows))) is not None:
            rows.append(row)
        if not rows or len(rows) != len(ordered) or any(row.note_id != note["id"] or row.group != group
                                                        for row, (note, group, _stamp) in zip(rows, ordered)):
            return False
        for position, (row, (note, group, stamp)) in enumerate(zip(rows, ordered)):
            unread = self.is_unread(note)
            if row.signature == NoteRow.signature_of(note, group, stamp, unread):
                continue
            fresh = NoteRow(note, group, self.sync, stamp, unread=unread)
            self.list.remove(row)
            self.list.insert(fresh, position)
        wanted = next((self.list.get_row_at_index(index) for index, (note, _g, _s) in enumerate(ordered) if note["id"] == selected_id), None)
        if wanted is None:
            self.list.unselect_all()
        elif self.list.get_selected_row() is not wanted:
            self.list.select_row(wanted)
        self.selected_id = selected_id if wanted is not None else None
        self.list.invalidate_headers()
        return True

    def fill_gallery(self):
        if not getattr(self, "gallery_dirty", False):
            return
        self.gallery_dirty = False
        for note, _group, _stamp in model.sort_notes(self.shown_notes, self.sync.settings().get("note_sort", "modified")):
            self.gallery.append(self.gallery_card(note))

    def gallery_card(self, note):
        child = Gtk.FlowBoxChild()
        child.note_id = note["id"]
        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        frame = Gtk.Frame()
        frame.set_size_request(150, 150)
        image = model.note_image(note)
        if image:
            picture = Gtk.Picture(can_shrink=True, content_fit=Gtk.ContentFit.COVER)
            frame.set_child(picture)
            load_thumbnail(self.sync, image, picture, 300, share=note.get("share"))
        else:
            text = Gtk.Label(label=model.note_preview(note)[:120], wrap=True, xalign=0, yalign=0)
            text.set_margin_start(10)
            text.set_margin_end(10)
            text.set_margin_top(10)
            text.add_css_class("caption")
            frame.set_child(text)
        card.append(frame)
        title = Gtk.Label(label=model.note_title(note), ellipsize=3)
        title.add_css_class("note-row-title")
        card.append(title)
        date = Gtk.Label(label=model.short_date(model.modified(note)))
        date.add_css_class("dim-label")
        date.add_css_class("caption")
        card.append(date)
        child.set_child(card)
        return child

    def on_selected(self, listbox, row):
        if row is None or self.updating:
            return
        self.selected_id = row.note_id
        self.emit("note-selected", row.note_id)

    def on_double_click(self, gesture, n_press, x, y):
        row = self.list.get_row_at_y(int(y))
        if n_press == 2 and isinstance(row, NoteRow):
            self.emit("open-window", row.note_id)

    def on_context(self, gesture, n_press, x, y):
        row = self.list.get_row_at_y(int(y))
        if isinstance(row, NoteRow):
            self.emit("context", row.note_id, self.list, x, y)


class NotePane(Gtk.Stack):
    """Shows the editor, a locked notice or an empty state."""

    __gsignals__ = {
        "unlock-requested": (GObject.SignalFlags.RUN_FIRST, None, ()),
        "restore-requested": (GObject.SignalFlags.RUN_FIRST, None, ()),
    }

    def __init__(self, sync):
        super().__init__()
        self.sync = sync
        self.add_css_class("note-pane")
        self.set_transition_type(Gtk.StackTransitionType.CROSSFADE)

        empty = Adw.StatusPage(title="Keine Notiz ausgewählt")
        empty.add_css_class("note-pane")
        self.add_named(empty, "empty")

        locked = Adw.StatusPage(
            title="Diese Notiz ist gesperrt",
            description="Gib dein Notizen-Passwort ein, um sie anzusehen.",
        )
        lock_icon = Icon("lock", 64)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=18, halign=Gtk.Align.CENTER)
        button = Gtk.Button(label="Notiz anzeigen")
        button.add_css_class("pill")
        button.add_css_class("suggested-action")
        button.connect("clicked", lambda _button: self.emit("unlock-requested"))
        box.append(button)
        locked.set_child(box)
        locked.set_paintable(None)
        locked_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, valign=Gtk.Align.CENTER, vexpand=True)
        lock_icon.set_margin_bottom(0)
        locked_box.append(lock_icon)
        locked_box.append(locked)
        locked_box.add_css_class("locked-page")
        self.add_named(locked_box, "locked")

        editing = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.banner = Adw.Banner(title="Diese Notiz liegt in „Zuletzt gelöscht“.", button_label="Wiederherstellen")
        self.banner.connect("button-clicked", lambda _banner: self.emit("restore-requested"))
        editing.append(self.banner)
        self.image_share = None
        self.editor = NoteEditor(image_loader=lambda reference: sync.fetch_file(reference, self.image_share))
        column = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.date = Gtk.Label()
        self.date.add_css_class("note-date")
        self.date.set_margin_top(14)
        self.date.set_margin_bottom(6)
        column.append(self.date)
        # "Claude hat geändert · heute 05:45 – Änderungen sind markiert" (changes by others).
        self.activity = Gtk.Label(xalign=0, wrap=True, css_classes=["activity-note"], visible=False)
        self.activity.set_margin_start(36)
        self.activity.set_margin_end(36)
        self.activity.set_margin_bottom(6)
        column.append(self.activity)
        column.append(self.editor)
        from .editor import FootnoteList
        column.append(FootnoteList(self.editor))
        clamp = Adw.Clamp(maximum_size=820, tightening_threshold=600, child=column)
        scroller = Gtk.ScrolledWindow(vexpand=True, child=clamp)
        smoothscroll.enable(scroller)
        scroller.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        editing.append(scroller)
        self.add_named(editing, "editor")
        self.note_id = None

    def show_empty(self):
        self.note_id = None
        self.set_visible_child_name("empty")

    def show_locked(self, note_id):
        self.note_id = note_id
        self.set_visible_child_name("locked")

    def show_note(self, note, blocks, editable=True):
        self.note_id = note["id"]
        self.image_share = note.get("share")
        self.editor.load_blocks(blocks)
        self.editor.set_editable(editable)
        self.editor.set_cursor_visible(editable)
        self.banner.set_revealed(bool(note["data"].get("trashed")))
        self.activity.set_visible(False)
        self.update_date(note)
        self.set_visible_child_name("editor")

    def show_changes(self, lines, who, when):
        """Mark lines someone else changed and say who and when."""
        self.editor.mark_changed(lines)
        self.activity.set_label(f"{who} hat geändert · {model.short_date(when)} – die Änderungen sind markiert.")
        self.activity.set_visible(True)

    def update_date(self, note):
        self.date.set_label(model.long_date(model.modified(note)))
