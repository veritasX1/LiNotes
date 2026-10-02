"""@-mentions (like Apple, only in shared notes): span "m:<user id>" over "@Name"."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import gi  # noqa: E402

gi.require_version("Gtk", "4.0")

from linotes import model  # noqa: E402
from linotes.editor import NoteEditor  # noqa: E402


def main():
    names = {1: "Olaf", 3: "Claude"}
    editor = NoteEditor()
    editor.user_name = names.get
    editor.mention_people = lambda: [(1, "Olaf")]
    # The name shown is always the current one.
    editor.load_blocks([{"t": "title", "x": "T"}, {"t": "body", "x": "Frage an @Ol", "s": [[9, 12, "m:1"]]}])
    assert editor.to_blocks()[1] == {"t": "body", "x": "Frage an @Olaf", "s": [[9, 14, "m:1"]]}
    buffer = editor.buffer
    # "@" in an e-mail address does nothing.
    buffer.place_cursor(buffer.get_end_iter())
    buffer.insert_at_cursor(" a@")
    assert editor.link_start is None
    # "@" at a word start offers the people; picking one inserts the mention.
    buffer.insert_at_cursor("b.de ")
    buffer.insert_at_cursor("@")
    assert editor.link_start is not None and editor.link_kind == "mention"
    buffer.insert_at_cursor("Ol")
    assert editor.pending_link_query() == "Ol"
    editor.finish_link(1, "Olaf")
    line = editor.to_blocks()[1]
    assert line["x"] == "Frage an @Olaf a@b.de @Olaf ", line
    assert line["s"] == [[9, 14, "m:1"], [22, 27, "m:1"]], line
    assert model.mentions_of(editor.to_blocks(), 1) == 2 and model.mentions_of(editor.to_blocks(), 3) == 0
    # Not shared: no people, "@" stays plain text.
    editor.mention_people = lambda: []
    buffer.insert_at_cursor("@")
    assert editor.link_start is None
    print("ok – @-Erwähnungen")


if __name__ == "__main__":
    main()
