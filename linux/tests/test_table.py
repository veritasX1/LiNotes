"""Tables in notes. The same cases are in Android's TableTest."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from linotes import model  # noqa: E402


def main():
    assert model.new_table(3, 2) == {"t": "table", "r": [["", "", ""], ["", "", ""]], "x": " |  | \n |  | "}
    assert model.table_rows({"r": [["a"], ["b", "c"]]}) == [["a", ""], ["b", "c"]]
    assert model.table_rows({}) == [[""]]
    block = model.table_block([["Tag", "Wer"], ["Mo", "Olaf"]])
    assert block["x"] == "Tag | Wer\nMo | Olaf"
    assert not model.is_empty_body([{"t": "title", "x": ""}, model.new_table()])
    print("ok – Tabellen")


if __name__ == "__main__":
    main()
