"""Changes by others are highlighted (like Apple's Highlights): line diff since the last view.
The same cases are in Android's ActivityTest."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from linotes import model  # noqa: E402

CASES = [
    (["a", "b", "c"], ["a", "b", "c"], []),
    (["a", "b", "c"], ["a", "x", "b", "c"], [1]),
    (["a", "b", "c"], ["a", "B", "c"], [1]),
    (["a", "b", "c"], ["a", "c"], []),
    ([], ["a", "b"], [0, 1]),
    (["a", "b"], ["b", "a", "neu"], [1, 2]),
    (["Titel", "eins", "zwei"], ["Titel", "eins", "zwei", "drei", "vier"], [3, 4]),
]


def main():
    for old, new, expected in CASES:
        assert model.changed_lines(old, new) == expected, (old, new, model.changed_lines(old, new))
    blocks = [{"t": "title", "x": "T"}, {"t": "image", "f": "a:b"}]
    assert model.block_lines(blocks) == ["title:T", "image:a:b"]
    print("ok – Änderungen anderer")


if __name__ == "__main__":
    main()
