"""Collapsible sections (like Apple): headings fold their content up to the next heading
of the same or a higher rank; the state is saved as "z" on the heading block."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import gi  # noqa: E402

gi.require_version("Gtk", "4.0")

from linotes.editor import NoteEditor  # noqa: E402

NOTE = [
    {"t": "title", "x": "Plan"},
    {"t": "heading", "x": "Woche 1"},
    {"t": "body", "x": "Montag"},
    {"t": "subheading", "x": "Details"},
    {"t": "check", "x": "Einkaufen"},
    {"t": "heading", "x": "Woche 2"},
    {"t": "body", "x": "Dienstag"},
]


def hidden(editor):
    """Text lines that are hidden right now."""
    buffer = editor.buffer
    tag = buffer.get_tag_table().lookup("folded")
    result = []
    for line in range(buffer.get_line_count()):
        start, end, _w = editor.line_bounds(line)
        if start.has_tag(tag):
            result.append(buffer.get_text(start, end, True))
    return result


def main():
    editor = NoteEditor()
    editor.load_blocks(NOTE)
    assert editor.section_end(1) == 4 and editor.section_end(3) == 4 and editor.section_end(5) == 6
    # Collapse "Woche 1": everything up to "Woche 2" disappears, nothing is lost when saving.
    editor.toggle_fold(1)
    assert hidden(editor) == ["Montag", "Details", "Einkaufen"]
    blocks = editor.to_blocks()
    assert blocks[1] == {"t": "heading", "x": "Woche 1", "z": True}
    assert [b["x"] for b in blocks] == [b["x"] for b in NOTE]
    # Loading keeps it collapsed (also on the other device).
    other = NoteEditor()
    other.load_blocks(blocks)
    assert hidden(other) == ["Montag", "Details", "Einkaufen"]
    # A subheading only folds its own part.
    other.toggle_fold(1)
    other.toggle_fold(3)
    assert hidden(other) == ["Einkaufen"]
    assert "z" not in other.to_blocks()[1] and other.to_blocks()[3]["z"] is True
    # Enter on a collapsed heading opens it, like typing into it in Notes.
    editor.buffer.place_cursor(editor.line_bounds(1)[1])
    editor.handle_return()
    assert hidden(editor) == [] and "z" not in editor.to_blocks()[1]
    print("ok – Einklappbare Abschnitte")


if __name__ == "__main__":
    main()
