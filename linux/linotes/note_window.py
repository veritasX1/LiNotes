"""A note in its own window, like a double-click in Apple's Notes on the Mac.

The window has its own editor; saving goes through the main window
(store_note), which also shows the change wherever else the note is open.
"""

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gdk, Gtk

from . import model
from .editor import NoteEditor
from .icons import icon_menu_button


class NoteWindow(Adw.ApplicationWindow):

    def __init__(self, main, note_id):
        super().__init__(application=main.get_application())
        self.main = main
        self.note_id = note_id
        self.share = None
        self.blocks = None
        self.locked = False
        self.set_default_size(620, 680)

        self.editor = NoteEditor(image_loader=lambda reference: main.sync.fetch_file(reference, self.share))
        self.editor.note_title = main.link_title
        self.editor.connect("edited", lambda _editor: self.save())
        self.editor.connect("open-note", lambda _editor, target: (main.open_linked_note(target), main.present()))
        self.editor.connect("link-requested", lambda editor: main.show_link_choice(editor, exclude=self.note_id))

        header = Adw.HeaderBar()
        self.title = Adw.WindowTitle()
        header.set_title_widget(self.title)
        header.pack_end(icon_menu_button("format", "Format", main.build_format_popover(self.editor)))

        self.date = Gtk.Label()
        self.date.add_css_class("note-date")
        self.date.set_margin_top(14)
        self.date.set_margin_bottom(6)
        column = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        column.append(self.date)
        column.append(self.editor)
        scroller = Gtk.ScrolledWindow(vexpand=True, child=Adw.Clamp(maximum_size=820, child=column))
        scroller.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroller.add_css_class("note-pane")

        view = Adw.ToolbarView()
        view.add_top_bar(header)
        view.set_content(scroller)
        self.set_content(view)

        # Ctrl+Plus/Minus/0 change the text size here too.
        keys = Gtk.EventControllerKey()
        keys.connect("key-pressed", self.on_key)
        self.add_controller(keys)

        main.note_windows.add(self)
        self.connect("close-request", self.on_close)
        if self.load():
            self.editor.grab_focus()

    def load(self, keep_cursor=False):
        """Show the note as it is stored; closes the window if it is gone, trashed or locked."""
        note = self.main.sync.get(self.note_id)
        blocks = self.main.note_body(note) if note and not note["data"].get("trashed") else None
        if blocks is None:
            self.close()
            return False
        self.share = note.get("share")
        self.locked = bool(note["data"].get("enc"))
        if blocks != self.blocks:
            self.blocks = blocks
            self.editor.load_blocks(blocks, keep_cursor=keep_cursor)
        self.update_title(note)
        return True

    def update_title(self, note):
        title = model.note_title(note)
        self.title.set_title(title)
        self.set_title(title)
        self.date.set_label(model.long_date(model.modified(note)))

    def save(self):
        blocks = self.editor.to_blocks()
        if blocks == self.blocks:
            return
        self.blocks = blocks
        self.main.store_note(self.note_id, blocks, self.editor)
        note = self.main.sync.get(self.note_id)
        if note:
            self.update_title(note)

    def on_sync_changed(self, ids):
        # Changed on another device: reload unless there are unsaved edits here.
        if self.note_id in ids and self.editor.edit_source is None:
            self.load(keep_cursor=True)

    def on_key(self, _controller, keyval, _keycode, state):
        from .window import text_size_step
        control = bool(state & Gdk.ModifierType.CONTROL_MASK)
        if control and Gdk.keyval_to_lower(keyval) == Gdk.KEY_w:
            self.close()
            return True
        if keyval == Gdk.KEY_F1 or (control and keyval == Gdk.KEY_question):
            self.main.show_shortcuts()
            return True
        step = text_size_step(keyval) if control else None
        if step is None:
            return False
        self.main.change_text_size(step)
        return True

    def on_close(self, _window):
        if self.editor.edit_source is not None:
            self.editor.flush()
        self.main.note_windows.discard(self)
        return False
