"""Regression 05.10.2026: deleting a note or turning a board into a development project from the
right-click menu froze LiNotes (fan up, "antwortet nicht"). The menu hung as an extra child on the
list; rebuilding the list (remove_all) then tried to remove that menu forever ("Tried to remove
non-child"). The menu must never sit on a list that gets rebuilt.

Needs a display (real or headless). Data: scratch folder, local test account only."""

import os
import sys
import tempfile
import threading
import time

TMP = tempfile.mkdtemp()
os.environ["XDG_DATA_HOME"] = os.path.join(TMP, "data")
os.environ["XDG_CONFIG_HOME"] = os.path.join(TMP, "config")
os.environ["XDG_CACHE_HOME"] = os.path.join(TMP, "cache")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import gi  # noqa: E402

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import GLib, Gtk  # noqa: E402

from linotes import sync  # noqa: E402

assert str(sync.DATA_DIR).startswith(TMP), sync.DATA_DIR
sync.store_credentials = lambda *args: None
sync.load_credentials = lambda *args: (None, None)

from linotes.application import LiNotesApplication  # noqa: E402
from linotes.window import LiNotesWindow  # noqa: E402

# A frozen main loop would never end the test: a watchdog fails it instead.
beat = [time.time()]


def watchdog():
    while True:
        time.sleep(0.5)
        if time.time() - beat[0] > 8:
            print("FEHLER: LiNotes hängt nach dem Kontextmenü (Endlosschleife beim Neuaufbau der Liste)", flush=True)
            os._exit(1)


class TestApp(LiNotesApplication):
    def do_activate(self):
        GLib.timeout_add(100, lambda: (beat.__setitem__(0, time.time()), True)[1])
        engine = self.sync = sync.SyncEngine()
        engine.start_local("Test")
        window = LiNotesWindow(self, engine)
        window.present()
        folder = engine.put("folder", {"name": "Ordner"})
        notes = [engine.put("note", {"folder": folder["id"], "body": [{"t": "title", "x": f"Notiz {i}"}]}) for i in range(3)]
        board = engine.put("board", {"name": "Board", "folder": folder["id"]})
        window.refresh_all()

        def menus_not_on_lists():
            for widget in (window.note_list.list, window.sidebar.list):
                child = widget.get_first_child()
                while child is not None:
                    assert not isinstance(child, Gtk.Popover), f"Menü hängt an {type(widget).__name__}"
                    child = child.get_next_sibling()

        def note_menu():
            window.select("folder:" + folder["id"])
            window.on_note_context(None, notes[1]["id"], window.note_list.list, 20, 20)
            menus_not_on_lists()
            window.activate_action("win.delete-note", None)  # froze before the fix
            return False

        def board_menu():
            window.object_menu("board", board["id"], window.sidebar.list, 20, 20)
            menus_not_on_lists()
            window.toggle_dev()  # what "Als Entwicklungsprojekt führen" runs; froze before the fix
            assert engine.get(board["id"])["data"].get("dev")
            return False

        def done():
            assert engine.get(notes[1]["id"])["data"].get("trashed")
            print("ok – Löschen und Entwicklungsprojekt über das Kontextmenü, ohne Hänger")
            self.quit()
            return False

        GLib.timeout_add(500, note_menu)
        GLib.timeout_add(1500, board_menu)
        GLib.timeout_add(2500, done)


if __name__ == "__main__":
    threading.Thread(target=watchdog, daemon=True).start()
    app = TestApp()
    app.set_application_id("io.github.veritasx1.LiNotesTest")
    raise SystemExit(app.run([]))
