"""Keyboard shortcuts: overview builds, Ctrl+K starts a note link, Ctrl+Alt+Up/Down moves lines."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import gi  # noqa: E402

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gtk  # noqa: E402

from linotes.editor import NoteEditor  # noqa: E402
from linotes.shortcuts import SECTIONS, shortcuts_dialog  # noqa: E402


def main():
    Adw.init()
    # Every accelerator in the overview is valid.
    for _title, items in SECTIONS:
        for label, accelerators in items:
            for accelerator in accelerators.split():
                ok, key, _mods = Gtk.accelerator_parse(accelerator)
                assert ok and key, (label, accelerator)
    assert shortcuts_dialog() is not None

    editor = NoteEditor()
    editor.load_blocks([{"t": "title", "x": "T"}, {"t": "check", "x": "eins"}, {"t": "check", "x": "zwei"}, {"t": "body", "x": "drei"}])
    buffer = editor.buffer
    buffer.place_cursor(buffer.get_iter_at_line(2)[1])
    editor.move_line(-1)
    assert [b.get("x") for b in editor.to_blocks()] == ["T", "zwei", "eins", "drei"]
    assert buffer.get_iter_at_mark(buffer.get_insert()).get_line() == 1
    editor.move_line(-1)  # the title stays on top
    assert [b.get("x") for b in editor.to_blocks()] == ["T", "zwei", "eins", "drei"]
    buffer.place_cursor(buffer.get_iter_at_line(1)[1])
    editor.move_line(1)
    editor.move_line(1)
    assert [b.get("x") for b in editor.to_blocks()] == ["T", "eins", "drei", "zwei"]
    assert editor.to_blocks()[3]["t"] == "check"

    # Ctrl+K: same as typing ">>".
    buffer.place_cursor(buffer.get_end_iter())
    editor.start_link()
    assert editor.link_start is not None and editor.pending_link_query() == ""
    assert editor.to_blocks()[3]["x"] == "zwei >>"
    print("ok – Tastenkürzel")


if __name__ == "__main__":
    main()
