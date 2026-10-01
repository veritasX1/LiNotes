"""Sorting notes like Apple: pinned first, then edit date, creation date or title."""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from linotes import model  # noqa: E402


def note(note_id, title, modified, created, pinned=False):
    return {"id": note_id, "data": {"body": [{"t": "title", "x": title}], "modified": modified,
                                    "created": created, "pinned": pinned}}


def main():
    now = time.time()
    notes = [note("a", "banane", now, now - 10 * 86400), note("b", "Apfel", now - 86400, now),
             note("c", "zitrone", now - 3 * 86400, now - 2 * 86400, pinned=True)]
    order = lambda key: [(n["id"], group) for n, group, _stamp in model.sort_notes(notes, key)]  # noqa: E731
    assert order("modified") == [("c", "Angeheftet"), ("a", "Heute"), ("b", "Gestern")]
    assert order("created") == [("c", "Angeheftet"), ("b", "Heute"), ("a", "Vorherige 30 Tage")]
    # Title: A–Z ignoring case, no date groups.
    assert order("title") == [("c", "Angeheftet"), ("b", "Notizen"), ("a", "Notizen")]
    assert [group for _n, group, _s in model.sort_notes(notes[:2], "title")] == ["", ""]
    # The row shows the date the list is sorted by.
    assert model.sort_notes(notes, "created")[1][2] == now
    print("ok – Notizen sortieren")


if __name__ == "__main__":
    main()
