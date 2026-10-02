"""Empty new notes are dropped when left (like Apple). The same cases are in Android's EmptyNoteTest."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from linotes import model  # noqa: E402

CASES = [
    ([{"t": "title", "x": ""}], True),
    ([{"t": "title", "x": "  "}, {"t": "body", "x": "\t"}], True),
    ([{"t": "check", "x": ""}, {"t": "bullet", "x": ""}], True),
    ([{"t": "title", "x": "Einkauf"}], False),
    ([{"t": "title", "x": ""}, {"t": "body", "x": "x"}], False),
    ([{"t": "title", "x": ""}, {"t": "image", "f": "a:b"}], False),
    ([{"t": "title", "x": ""}, {"t": "file", "f": "a:b", "n": "x.pdf"}], False),
    ([{"t": "title", "x": ""}, {"t": "divider"}], False),
]


def main():
    for blocks, expected in CASES:
        assert model.is_empty_body(blocks) == expected, blocks
    print("ok – leere Notizen")


if __name__ == "__main__":
    main()
