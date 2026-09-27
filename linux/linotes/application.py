import sys
from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gdk, Gio, GLib, Gtk

from .sync import SyncEngine
from .window import LiNotesWindow

APP_ID = "io.github.veritasx1.LiNotes"


class LiNotesApplication(Adw.Application):

    def __init__(self):
        super().__init__(application_id=APP_ID, flags=Gio.ApplicationFlags.DEFAULT_FLAGS)
        self.sync = None

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

        for name, callback in (("quit", self.quit_app), ("about", self.about)):
            action = Gio.SimpleAction.new(name, None)
            action.connect("activate", lambda _a, _p, function=callback: function())
            self.add_action(action)
        self.set_accels_for_action("app.quit", ["<Control>q"])
        self.set_accels_for_action("win.lock-all", ["<Control><Alt>l"])

    def do_activate(self):
        if self.sync is None:
            self.sync = SyncEngine()
        window = self.get_active_window() or LiNotesWindow(self, self.sync)
        window.present()

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
            application_name="LiNotes", application_icon=APP_ID, version="2.0",
            developer_name="Olaf Winkler",
            comments="Notizen, Einkaufslisten und Aufgaben – auf deinem eigenen Server.",
        )
        dialog.present(self.get_active_window())


def main():
    return LiNotesApplication().run(sys.argv)
