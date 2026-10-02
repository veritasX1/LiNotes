"""Text color, font and alignment (like Apple's Notes): spans "c:…"/"f:…", block field "a"."""

import sys
import tempfile
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
    editor.load_blocks([{"t": "title", "x": "T"}, {"t": "body", "x": "rot und blau", "s": [[0, 3, "c:pink"]], "a": "center"}])
    assert editor.to_blocks()[1] == {"t": "body", "x": "rot und blau", "s": [[0, 3, "c:pink"]], "a": "center"}
    # A color replaces the other one; highlight and color can be combined.
    select(editor, 0, 3)
    editor.set_text_color("c:blue")
    editor.set_highlight("h:mint")
    select(editor, 8, 12)
    editor.set_font("f:serif")
    assert editor.to_blocks()[1]["s"] == [[0, 3, "c:blue"], [0, 3, "h:mint"], [8, 12, "f:serif"]]
    select(editor, 0, 3)
    editor.set_text_color(None)
    assert editor.to_blocks()[1]["s"] == [[0, 3, "h:mint"], [8, 12, "f:serif"]]
    # Alignment: per paragraph, carried on by Enter, removed with left.
    editor.buffer.place_cursor(editor.buffer.get_end_iter())
    editor.set_alignment("right")
    editor.handle_return()
    editor.buffer.insert_at_cursor("weiter")
    blocks = editor.to_blocks()
    assert blocks[1].get("a") == "right" and blocks[2] == {"t": "body", "x": "weiter", "a": "right"}, blocks
    editor.set_alignment(None)
    assert "a" not in editor.to_blocks()[2]
    # PDF.
    assert "#1C8CE0" in report.block_markup({"x": "abc", "s": [[0, 3, "c:blue"]]})
    with tempfile.TemporaryDirectory() as folder:
        report.write_note_pdf(editor.to_blocks(), Path(folder) / "t.pdf", "T")
    print("ok – Textfarbe, Schrift, Ausrichtung")


if __name__ == "__main__":
    main()
