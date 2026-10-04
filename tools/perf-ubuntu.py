#!/usr/bin/env python3
"""Speed check of the Ubuntu app with fixed test data – run it before and after changes:

    python3 tools/perf-ubuntu.py                 # this checkout
    python3 tools/perf-ubuntu.py <linux-folder>  # another checkout (e.g. an older version in a worktree)

Works in a fresh temporary data folder in local mode; keys stay in memory (never the keyring, never
the real ~/.local/share/linotes). Prints milliseconds per step (median of several runs)."""

import os
import statistics
import sys
import tempfile
import time
from pathlib import Path

LINUX = Path(sys.argv[1] if len(sys.argv) > 1 else Path(__file__).resolve().parent.parent / "linux").resolve()
SCRATCH = tempfile.mkdtemp(prefix="linotes-perf-")
os.environ["XDG_DATA_HOME"] = os.environ["XDG_CACHE_HOME"] = os.environ["XDG_CONFIG_HOME"] = SCRATCH
sys.path.insert(0, str(LINUX))

import gi  # noqa: E402

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gio, GLib, Gtk  # noqa: E402

from linotes import sync as sync_module  # noqa: E402

assert SCRATCH in str(sync_module.DATA_DIR), sync_module.DATA_DIR
SECRETS = {}
sync_module.store_credentials = lambda server, username, token, secret: SECRETS.update(k=(token, secret))
sync_module.load_credentials = lambda *args: SECRETS.get("k")
sync_module.clear_credentials = lambda *args: SECRETS.clear()

from linotes import window as window_module  # noqa: E402

WORDS = ("Fundament Garten Holz Lasur Dach Fenster Tür Schraube Werkzeug Plan Termin Angebot Rechnung Liste "
         "Besprechung Aufgabe Projekt Notiz Kalender Ordner").split()


def text(n, seed):
    return " ".join(WORDS[(seed * 7 + i * 3) % len(WORDS)] for i in range(n))


def make_data(sync):
    now = time.time()
    folders = [sync.put("folder", {"name": f"Projekt {i}", "order": i}) for i in range(8)]
    for i in range(300):
        body = [{"t": "title", "x": f"Notiz {i} {text(3, i)}"}]
        body += [{"t": "body", "x": text(30, i + k)} for k in range(6)]
        body += [{"t": "check", "x": text(5, i + k), "c": k % 2 == 0} for k in range(4)]
        sync.put("note", {"folder": folders[i % 8]["id"], "body": body, "created": now - i * 600, "modified": now - i * 600})
    long_body = [{"t": "title", "x": "Lange Notiz"}]
    for k in range(1500):
        kind = ("heading", "body", "body", "check", "bullet", "body")[k % 6]
        long_body.append({"t": kind, "x": text(14, k)})
    long_note = sync.put("note", {"folder": folders[0]["id"], "body": long_body, "created": now, "modified": now + 10})
    board = sync.put("board", {"name": "Großes Board", "order": 1})
    columns = [sync.put("column", {"board": board["id"], "name": name, "order": i}) for i, name in enumerate(("Offen", "In Arbeit", "Erledigt"))]
    for i in range(120):
        sync.put("card", {"board": board["id"], "column": columns[i % 3]["id"], "title": f"Karte {i} {text(6, i)}",
                          "notes": text(40, i), "order": i, "priority": ("hoch", "mittel", "niedrig", "")[i % 4]})
    for i in range(6):
        sync.put("list", {"name": f"Liste {i}", "grocery": True, "order": i})
    sync.save()
    return long_note, board


def settle():
    context = GLib.MainContext.default()
    for _ in range(200):
        if not context.iteration(False):
            break


def timed(function, runs=7, name=None):
    if name and os.environ.get("LINOTES_PROFILE_STEP") == name:
        # Profile just this step: LINOTES_PROFILE_STEP="board" python3 tools/perf-ubuntu.py
        import cProfile
        import pstats
        profile = cProfile.Profile()
        profile.enable()
        function()
        settle()
        profile.disable()
        pstats.Stats(profile).sort_stats("cumulative").print_stats(25)
    values = []
    for _ in range(runs):
        start = time.perf_counter()
        function()
        settle()
        values.append((time.perf_counter() - start) * 1000)
    return statistics.median(values)


class App(Adw.Application):
    def __init__(self):
        super().__init__(application_id="io.github.veritasx1.LiNotesPerf", flags=Gio.ApplicationFlags.NON_UNIQUE)

    def do_activate(self):
        try:
            self.measure()
        except Exception:
            import traceback
            traceback.print_exc()
        sys.stdout.flush()
        os._exit(0)

    def measure(self):
        sync = sync_module.SyncEngine()
        sync.start_local("Messlauf")
        long_note, board = make_data(sync)
        results = {}
        start = time.perf_counter()
        window = window_module.LiNotesWindow(self, sync)
        window.set_default_size(1300, 850)
        window.present()
        settle()
        results["Fenster öffnen"] = (time.perf_counter() - start) * 1000
        results["Seitenleiste neu aufbauen"] = timed(window.sidebar.refresh)
        results["Alle Notizen anzeigen"] = timed(lambda: window.show_notes(), name="notes")
        results["Lange Notiz öffnen (1500 Absätze)"] = timed(lambda: (setattr(window, "current_note", None), window.open_note(long_note["id"])), runs=5, name="open")
        editor = window.note_pane.editor
        buffer = editor.get_buffer()

        def keystroke():
            buffer.place_cursor(buffer.get_end_iter())
            buffer.insert_interactive_at_cursor("x", -1, True)  # like typing (all insert handlers run)
        results["Tastendruck in langer Notiz"] = timed(keystroke, runs=40, name="key")
        results["Board öffnen (120 Karten)"] = timed(lambda: window.sidebar.select("board:" + board["id"]), runs=5)
        results["Board neu aufbauen"] = timed(window.board_view.refresh, runs=5, name="board")
        print(f"Stand: {LINUX}")
        for name, value in results.items():
            print(f"  {name:38} {value:8.1f} ms")


App().run([])
