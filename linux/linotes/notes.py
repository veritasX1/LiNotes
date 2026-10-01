"""Note list (middle column) and note pane (editor column)."""

import threading

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gdk, GdkPixbuf, GLib, GObject, Gtk

from . import model
from .editor import NoteEditor
from .icons import Icon


class NoteRow(Gtk.ListBoxRow):

    def __init__(self, note, group, sync):
        super().__init__()
        self.note_id = note["id"]
        self.group = group
        data = note["data"]

        box = Gtk.Box(spacing=8)
        text = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2, hexpand=True)
        title_row = Gtk.Box(spacing=5)
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
        date = Gtk.Label(label=model.short_date(model.modified(note)), xalign=0)
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


def load_thumbnail(sync, file_id, picture, size=88, share=None):
    def work():
        try:
            path = sync.fetch_file(file_id, share)
            pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_scale(str(path), size, size, True)
            pixbuf = pixbuf.apply_embedded_orientation() or pixbuf
        except Exception:
            return
        GLib.idle_add(lambda: (picture.set_paintable(Gdk.Texture.new_for_pixbuf(pixbuf)), False)[1])
    threading.Thread(target=work, daemon=True).start()


class NoteList(Gtk.Box):

    __gsignals__ = {
        "note-selected": (GObject.SignalFlags.RUN_FIRST, None, (str,)),
        "context": (GObject.SignalFlags.RUN_FIRST, None, (str, object, float, float)),
    }

    def __init__(self, sync):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self.sync = sync
        self.selected_id = None
        self.updating = False
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

        self.list = Gtk.ListBox()
        self.list.add_css_class("note-list")
        self.list.add_css_class("navigation-sidebar")
        self.list.set_header_func(self.header_func)
        self.list.connect("row-selected", self.on_selected)
        click = Gtk.GestureClick(button=Gdk.BUTTON_SECONDARY)
        click.connect("pressed", self.on_context)
        self.list.add_controller(click)

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
        list_scroller.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        gallery_scroller = Gtk.ScrolledWindow(vexpand=True, child=self.gallery)
        gallery_scroller.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.empty = Adw.StatusPage(title="Keine Notizen", vexpand=True)
        self.empty.add_css_class("compact")
        self.stack.add_named(list_scroller, "list")
        self.stack.add_named(gallery_scroller, "gallery")
        self.stack.add_named(self.empty, "empty")
        self.append(self.stack)
        self.mode = "list"

    def header_func(self, row, before):
        if before is None or before.group != row.group:
            label = Gtk.Label(label=row.group, xalign=0)
            label.add_css_class("list-section-header")
            row.set_header(label)
        else:
            row.set_header(None)

    def set_mode(self, mode):
        self.mode = mode

    def show(self, title, notes, selected_id=None, empty_text="Keine Notizen"):
        self.updating = True
        self.heading.set_label(title)
        count = len(notes)
        self.count.set_label("1 Notiz" if count == 1 else f"{count} Notizen")
        self.list.remove_all()
        child = self.gallery.get_first_child()
        while child is not None:
            following = child.get_next_sibling()
            self.gallery.remove(child)
            child = following

        pinned = [note for note in notes if note["data"].get("pinned") and not note["data"].get("trashed")]
        others = [note for note in notes if note not in pinned]
        pinned.sort(key=model.modified, reverse=True)
        others.sort(key=model.modified, reverse=True)

        select_row = None
        for note in pinned + others:
            group = "Angeheftet" if note in pinned else model.date_group(model.modified(note))
            row = NoteRow(note, group, self.sync)
            self.list.append(row)
            if note["id"] == selected_id:
                select_row = row
            self.gallery.append(self.gallery_card(note))

        if not notes:
            self.empty.set_title(empty_text)
            self.stack.set_visible_child_name("empty")
        else:
            self.stack.set_visible_child_name(self.mode)
        if select_row is not None:
            self.list.select_row(select_row)
        self.selected_id = selected_id if select_row is not None else None
        self.updating = False

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
        column.append(self.editor)
        clamp = Adw.Clamp(maximum_size=820, tightening_threshold=600, child=column)
        scroller = Gtk.ScrolledWindow(vexpand=True, child=clamp)
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
        self.update_date(note)
        self.set_visible_child_name("editor")

    def update_date(self, note):
        self.date.set_label(model.long_date(model.modified(note)))
