import sys
from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gdk, Gio, GLib, Gtk

from .sync import SyncEngine
from .window import LiNotesWindow
from .i18n import _

APP_ID = "io.github.veritasx1.LiNotes"


class LiNotesApplication(Adw.Application):

    def __init__(self):
        super().__init__(application_id=APP_ID, flags=Gio.ApplicationFlags.DEFAULT_FLAGS)
        self.sync = None
        self.start_with_new_note = False
        # Quick note from anywhere: "linotes --neue-notiz" (dock menu, own keyboard shortcut).
        self.add_main_option("neue-notiz", ord("n"), GLib.OptionFlags.NONE, GLib.OptionArg.NONE, _("Neue Notiz anlegen"), None)

    def do_handle_local_options(self, options):
        if options.contains("neue-notiz"):
            self.register(None)
            if self.get_is_remote():
                # LiNotes is already running: open the new note there.
                self.activate_action("new-note", None)
                return 0
            self.start_with_new_note = True
        return -1

    def do_startup(self):
        Adw.Application.do_startup(self)
        GLib.set_application_name("LiNotes")
        display = Gdk.Display.get_default()
        data = Path(__file__).resolve().parent.parent / "data"
        Gtk.IconTheme.get_for_display(display).add_search_path(str(data))
        Gtk.Window.set_default_icon_name(APP_ID)
        css = Gtk.CssProvider()
        css.load_from_path(str(Path(__file__).with_name("style.css")))
        Gtk.StyleContext.add_provider_for_display(display, css, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

        for name, callback in (("quit", self.quit_app), ("about", self.about), ("new-note", self.new_note)):
            action = Gio.SimpleAction.new(name, None)
            action.connect("activate", lambda _a, _p, function=callback: function())
            self.add_action(action)
        # Clicking a notification (e.g. an @-mention) opens the note.
        open_note = Gio.SimpleAction.new("open-note", GLib.VariantType.new("s"))
        open_note.connect("activate", lambda _a, note_id: self.open_note(note_id.get_string()))
        self.add_action(open_note)
        self.set_accels_for_action("app.quit", ["<Control>q"])
        self.set_accels_for_action("win.lock-all", ["<Control><Alt>l"])
        self.set_accels_for_action("win.print-note", ["<Control>p"])
        self.set_accels_for_action("win.export-note", ["<Control><Shift>e"])
        self.set_accels_for_action("win.shortcuts", ["F1"])

    def do_activate(self):
        if self.sync is None:
            self.sync = SyncEngine()
        window = self.get_active_window() or LiNotesWindow(self, self.sync)
        window.present()
        if self.start_with_new_note:
            self.start_with_new_note = False
            GLib.idle_add(lambda: (self.new_note(), False)[1])

    def open_note(self, note_id):
        if self.sync is None:
            self.activate()
        window = self.get_active_window() or LiNotesWindow(self, self.sync)
        if isinstance(window, LiNotesWindow) is False:
            window = next((w for w in self.get_windows() if isinstance(w, LiNotesWindow)), window)
        window.present()
        if window.pages.get_visible_child_name() == "main":
            window.open_linked_note(note_id)

    def new_note(self):
        if self.sync is None:
            self.activate()
            return
        window = self.get_active_window() or LiNotesWindow(self, self.sync)
        window.present()
        if window.pages.get_visible_child_name() == "main":
            window.new_note()

    def quit_app(self):
        for window in self.get_windows():
            window.close()

    def do_shutdown(self):
        if self.sync is not None:
            for window in self.get_windows():
                if hasattr(window, "note_pane"):
                    window.note_pane.editor.flush()
            try:
                if self.sync.signed_in:
                    self.sync.push_once()
            except Exception:
                pass
            self.sync.save()
        Adw.Application.do_shutdown(self)

    def about(self):
        dialog = Adw.AboutDialog(
            application_name="LiNotes", application_icon=APP_ID, version="2.2.0",
            developer_name="Olaf Winkler",
            comments=_("Notizen, Listen, Aufgaben und Pläne – auf deinem eigenen Server.\nEntwickelt in Schleswig-Holstein."),
            copyright="© 2026 Olaf Winkler", license_type=Gtk.License.GPL_3_0,
            website="https://lisoft.goip.de/linotes/", issue_url="https://github.com/veritasX1/LiNotes/issues",
        )
        dialog.present(self.get_active_window())


def main():
    return LiNotesApplication().run(sys.argv)
