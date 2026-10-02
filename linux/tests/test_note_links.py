"""Links between notes (">>", like Apple's Notes): saved as span "n:<id>",
showing the current title of the linked note."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import gi  # noqa: E402

gi.require_version("Gtk", "4.0")

from linotes import model, report  # noqa: E402
from linotes.editor import NoteEditor  # noqa: E402


def test_model():
    titles = {"a": "Einkauf Samstag", "b": None}
    block = {"t": "body", "x": "siehe Einkauf und mehr", "s": [[6, 13, "n:a"], [18, 22, "b"], [0, 5, "i"]]}
    updated = model.refresh_note_links(block, titles.get)
    # The link shows the new title, later spans move along, earlier ones stay.
    assert updated["x"] == "siehe Einkauf Samstag und mehr"
    assert [6, 21, "n:a"] in updated["s"] and [26, 30, "b"] in updated["s"] and [0, 5, "i"] in updated["s"]
    # Gone notes keep the old text; unchanged blocks come back as they are.
    gone = {"t": "body", "x": "alt", "s": [[0, 3, "n:b"]]}
    assert model.refresh_note_links(gone, titles.get) is gone
    notes = [{"id": "a", "data": {"body": [{"t": "title", "x": "Apfel"}], "modified": 1}},
             {"id": "b", "data": {"body": [{"t": "title", "x": "Birne"}], "modified": 2}},
             {"id": "c", "data": {"body": [{"t": "title", "x": "Apfelkuchen"}], "modified": 3, "trashed": True}}]
    assert [n["id"] for n in model.link_choices(notes)] == ["b", "a"]
    assert [n["id"] for n in model.link_choices(notes, exclude="b", query="apf")] == ["a"]
    # PDF: the link is drawn like a link.
    assert "underline='single'" in report.block_markup({"x": "Apfel", "s": [[0, 5, "n:a"]]})


def test_editor():
    titles = {"a": "Einkauf Samstag"}
    editor = NoteEditor()
    editor.note_title = titles.get
    editor.load_blocks([{"t": "title", "x": "Plan"}, {"t": "body", "x": "siehe Einkauf", "s": [[6, 13, "n:a"]]}])
    assert editor.to_blocks()[1] == {"t": "body", "x": "siehe Einkauf Samstag", "s": [[6, 21, "n:a"]]}

    # Typing right after the link does not make the link longer.
    buffer = editor.buffer
    buffer.place_cursor(buffer.get_end_iter())
    buffer.insert_at_cursor("!")
    assert editor.to_blocks()[1]["s"] == [[6, 21, "n:a"]]

    # ">>" asks for a note; the choice replaces ">>" and the typed filter.
    buffer.insert_at_cursor(" >")
    buffer.insert_at_cursor(">")
    assert editor.link_start is not None
    buffer.insert_at_cursor("ein")
    assert editor.pending_link_query() == "ein"
    editor.finish_link("a", "Einkauf Samstag")
    line = editor.to_blocks()[1]
    assert line["x"] == "siehe Einkauf Samstag! Einkauf Samstag ", line
    assert line["s"] == [[6, 21, "n:a"], [23, 38, "n:a"]], line

    # Esc keeps ">>" as plain text.
    buffer.insert_at_cursor(">>")
    editor.finish_link(None)
    assert editor.to_blocks()[1]["x"].endswith(" >>")


def test_web_address_after_image():
    """Olafs Finding 02.10.: with a photo above, the last letter was not part of the link."""
    editor = NoteEditor()
    editor.load_blocks([{"t": "title", "x": "Kameratest"}, {"t": "image", "f": None},
                        {"t": "divider"}, {"t": "body", "x": "http://linotes.goip.de"}])
    buffer = editor.buffer
    tag = buffer.get_tag_table().lookup("link")
    start = buffer.get_iter_at_line(3)[1]
    assert start.starts_tag(tag)
    end = start.copy()
    end.forward_to_tag_toggle(tag)
    assert buffer.get_text(start, end, False) == "http://linotes.goip.de"


if __name__ == "__main__":
    test_model()
    test_editor()
    test_web_address_after_image()
    print("ok – Notizen verlinken")
