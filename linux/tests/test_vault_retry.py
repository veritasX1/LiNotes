"""Locking with a wrong notes password (05.10.2026): the dialog closed with only a short message and
the note stayed open; the hint stood in every prompt. Like Apple now: the first prompt shows no hint,
a wrong password asks again with "Falsches Passwort" and the hint, the right one locks the note.

Needs a display (real or headless). Data: scratch folder, local test account only."""

import os
import sys
import tempfile

TMP = tempfile.mkdtemp()
os.environ["XDG_DATA_HOME"] = os.path.join(TMP, "data")
os.environ["XDG_CONFIG_HOME"] = os.path.join(TMP, "config")
os.environ["XDG_CACHE_HOME"] = os.path.join(TMP, "cache")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import gi  # noqa: E402

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import GLib  # noqa: E402

from linotes import sync, vault, window as window_module  # noqa: E402

assert str(sync.DATA_DIR).startswith(TMP), sync.DATA_DIR
sync.store_credentials = lambda *args: None
sync.load_credentials = lambda *args: (None, None)

from linotes.application import LiNotesApplication  # noqa: E402
from linotes.window import LiNotesWindow  # noqa: E402

prompts = []
answers = ["falsch", "richtig123"]


def fake_ask_password(parent, heading, body, callback, hint=None, confirm=False, action="OK", wrong=False):
    prompts.append({"hint": hint, "wrong": wrong})
    callback(answers.pop(0), None)


window_module.ask_password = fake_ask_password
window_module.run_async = lambda work, done: done(*_call(work))


def _call(work):
    try:
        return work(), None
    except Exception as error:  # noqa: BLE001 – the window shows it as "wrong password"
        return None, error


class TestApp(LiNotesApplication):
    def do_activate(self):
        engine = self.sync = sync.SyncEngine()
        engine.start_local("Test")
        window = LiNotesWindow(self, engine)
        data, _key = vault.create_vault("richtig123", "Unipasswort")
        engine.put("vault", data, None, f"vault-{engine.user_id}")
        note = engine.put("note", {"body": [{"t": "title", "x": "Geheim"}, {"t": "body", "x": "PIN 1234"}]})
        window.refresh_all()

        def lock():
            window.open_note(note["id"])
            window.toggle_lock()
            assert [p["wrong"] for p in prompts] == [False, True], prompts
            assert prompts[0]["hint"] == "Unipasswort"  # passed along, but shown only when wrong
            locked = engine.get(note["id"])["data"]
            assert locked.get("enc") and "body" not in locked, "Notiz ist nicht gesperrt"
            print("ok – falsches Passwort fragt erneut (mit Merkhilfe), richtiges sperrt die Notiz")
            self.quit()
            return False
        GLib.timeout_add(500, lock)


if __name__ == "__main__":
    app = TestApp()
    app.set_application_id("io.github.veritasx1.LiNotesTest")
    raise SystemExit(app.run([]))
