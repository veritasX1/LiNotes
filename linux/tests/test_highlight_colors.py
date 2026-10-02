"""Highlight in several colors (like Apple's Notes): one color per character, "h" stays yellow."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import gi  # noqa: E402

gi.require_version("Gtk", "4.0")

from linotes import report  # noqa: E402
from linotes.editor import NoteEditor  # noqa: E402


def select(editor, start, end, line=1):
    base = editor.buffer.get_iter_at_line(line)[1].get_offset()
    editor.buffer.select_range(editor.buffer.get_iter_at_offset(base + start), editor.buffer.get_iter_at_offset(base + end))


def main():
    editor = NoteEditor()
    # Old notes with the yellow marking load unchanged.
    editor.load_blocks([{"t": "title", "x": "T"}, {"t": "body", "x": "eins zwei drei", "s": [[0, 4, "h"]]}])
    assert editor.to_blocks()[1]["s"] == [[0, 4, "h"]]
    # A new color replaces the old one on the same text.
    select(editor, 0, 4)
    editor.set_highlight("h:pink")
    select(editor, 5, 9)
    editor.set_highlight("h:blue")
    assert editor.to_blocks()[1]["s"] == [[0, 4, "h:pink"], [5, 9, "h:blue"]]
    # Same color again or "remove" takes it off.
    select(editor, 0, 4)
    editor.set_highlight("h:pink")
    select(editor, 5, 9)
    editor.set_highlight(None)
    assert "s" not in editor.to_blocks()[1]
    # Without a selection the color applies to the text typed next.
    editor.buffer.place_cursor(editor.buffer.get_end_iter())
    editor.set_highlight("h:mint")
    editor.buffer.insert_at_cursor(" vier")
    assert editor.to_blocks()[1]["s"] == [[14, 19, "h:mint"]]
    # PDF: each color has its own background.
    assert "#A5ECE0" in report.block_markup({"x": "abc", "s": [[0, 3, "h:mint"]]})
    print("ok – Markieren in Farben")


if __name__ == "__main__":
    main()
