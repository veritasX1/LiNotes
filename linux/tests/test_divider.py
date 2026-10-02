"""Divider in notes: "---" + Enter or the format menu, saved as block {"t": "divider"}."""

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import gi  # noqa: E402

gi.require_version("Gtk", "4.0")

from linotes import report  # noqa: E402
from linotes.editor import NoteEditor  # noqa: E402


def main():
    editor = NoteEditor()
    editor.load_blocks([{"t": "title", "x": "T"}, {"t": "body", "x": "oben"}, {"t": "divider"}, {"t": "body", "x": "unten"}])
    assert [b["t"] for b in editor.to_blocks()] == ["title", "body", "divider", "body"]
    assert editor.is_divider(2) and not editor.is_divider(1)

    # "---" and Enter on a line of its own becomes a divider; typing goes on below.
    buffer = editor.buffer
    buffer.place_cursor(buffer.get_end_iter())
    editor.handle_return()
    buffer.insert_at_cursor("---")
    editor.handle_return()
    buffer.insert_at_cursor("weiter")
    assert [(b["t"], b.get("x")) for b in editor.to_blocks()][-3:] == [("body", "unten"), ("divider", None), ("body", "weiter")]

    # Inserted from the menu in the middle of a line: own line, text stays around it.
    editor.load_blocks([{"t": "title", "x": "T"}, {"t": "body", "x": "eins"}])
    buffer.place_cursor(buffer.get_end_iter())
    editor.insert_divider()
    buffer.insert_at_cursor("zwei")
    assert [(b["t"], b.get("x")) for b in editor.to_blocks()] == [("title", "T"), ("body", "eins"), ("divider", None), ("body", "zwei")]

    # Backspace at the start of the line below removes the divider, the text stays.
    buffer.place_cursor(buffer.get_iter_at_line(3)[1])
    assert editor.handle_backspace()
    assert [(b["t"], b.get("x")) for b in editor.to_blocks()] == [("title", "T"), ("body", "eins"), ("body", "zwei")]
    # Text that got onto an object line is not lost.
    editor.load_blocks([{"t": "title", "x": "T"}, {"t": "divider"}])
    buffer.place_cursor(buffer.get_end_iter())
    buffer.insert_at_cursor("da")
    assert [(b["t"], b.get("x")) for b in editor.to_blocks()][1:] == [("divider", None), ("body", "da")]

    # PDF with a divider.
    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder) / "t.pdf"
        report.write_note_pdf(editor.to_blocks(), path, "T")
        assert path.stat().st_size > 500
    print("ok – Trennlinie")


if __name__ == "__main__":
    main()
