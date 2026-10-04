"""Shortcuts that keep the app fast (card b9046682) must give the same result as the long way:
list numbers of the visible lines only, the fold arrow without walking the whole section, only the
changed row of the note list rebuilt, and the state file written piece by piece."""

import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ["XDG_DATA_HOME"] = os.environ["XDG_CONFIG_HOME"] = os.environ["XDG_CACHE_HOME"] = tempfile.mkdtemp()
import gi  # noqa: E402

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from linotes import model, sync  # noqa: E402
from linotes.editor import NoteEditor  # noqa: E402
from linotes.notes import NoteList  # noqa: E402

NOTE = [{"t": "title", "x": "Plan"}, {"t": "heading", "x": "Woche"}, {"t": "number", "x": "eins"}, {"t": "number", "x": "zwei"},
        {"t": "number", "x": "drei", "l": 1}, {"t": "check", "x": "Haken"}, {"t": "number", "x": "vier"}, {"t": "body", "x": "Text"},
        {"t": "number", "x": "neu eins"}, {"t": "heading", "x": "Leer"}, {"t": "body", "x": ""}, {"t": "subheading", "x": "Unter"},
        {"t": "body", "x": "x"}, {"t": "heading", "x": "Ende"}]


def numbers(editor):
    return editor.list_numbers(0, editor.buffer.get_line_count() - 1)


def check_editor():
    editor = NoteEditor()
    editor.load_blocks(NOTE)
    every = numbers(editor)
    assert every == {2: 1, 3: 2, 4: 1, 6: 3, 8: 1}, every
    count = editor.buffer.get_line_count()
    for first in range(count):
        for last in range(first, count):
            part = editor.list_numbers(first, last)
            assert all(part[line] == every[line] for line in every if first <= line <= last), (first, last)
    for line in range(count):
        assert editor.has_section_body(line) == (editor.section_end(line) > line), line


class FakeSync:
    user_id = 1

    def settings(self):
        return {}

    def user_name(self, _user):
        return ""


def check_rows():
    notes = [{"id": f"n{i}", "data": {"body": [{"t": "title", "x": f"Notiz {i}"}], "modified": 1000 - i}} for i in range(5)]
    view = NoteList(FakeSync())
    view.show("Alle", notes, selected_id="n2")

    def rows():
        result = []
        while (row := view.list.get_row_at_index(len(result))) is not None:
            result.append(row)
        return result
    before = rows()
    changed = dict(notes[3], data={**notes[3]["data"], "body": [{"t": "title", "x": "Neu"}]})
    view.show("Alle", notes[:3] + [changed] + notes[4:], selected_id="n2")
    after = rows()
    assert [row.note_id for row in after] == [row.note_id for row in before]
    assert [a is b for a, b in zip(before, after)] == [True, True, True, False, True]
    assert view.list.get_selected_row() is after[2] and view.selected_id == "n2"
    view.show("Alle", notes[1:], selected_id="n9")  # other notes: built anew
    assert len(rows()) == 4 and view.selected_id is None and view.list.get_selected_row() is None


def check_state_file():
    engine = sync.SyncEngine()
    engine.state = {"server": "", "user": {"name": "Ö"}, "cursor": 3, "remote": {"a": {"x": [1, "ä"]}, "b": {}},
                    "pending": [{"id": "a"}], "identity": None}
    engine.save()
    assert json.loads(engine.path.read_text()) == engine.state
    engine.state.update(remote={}, pending=[])
    engine.save()
    assert json.loads(engine.path.read_text()) == engine.state


def main():
    check_editor()
    check_rows()
    check_state_file()
    print("ok – schnelle Wege")


if __name__ == "__main__":
    main()
