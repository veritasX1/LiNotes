"""Footnotes (Profi-Funktion): span names and reading order. Android's FootnoteTest has the same cases."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from linotes import model  # noqa: E402


def main():
    assert model.footnote_text("fn:Müller 2020, S. 4") == "Müller 2020, S. 4"
    assert model.footnote_text("fn:") == "" and model.footnote_text("n:abc") is None and model.footnote_text(None) is None
    blocks = [{"t": "title", "x": "Quellen"},
              {"t": "body", "x": "Erst1 dann2", "s": [[10, 11, "fn:Zweite"], [0, 4, "b"], [4, 5, "fn:Erste"]]},
              {"t": "body", "x": "kein Verweis"},
              {"t": "body", "x": "Ende3", "s": [[4, 5, "fn:Dritte, mit Komma"]]}]
    assert model.footnotes(blocks) == ["Erste", "Zweite", "Dritte, mit Komma"]
    assert model.footnotes([{"t": "body", "x": "x", "s": [[0, 1]]}]) == []  # broken span: ignored
    print("ok – Fußnoten")


if __name__ == "__main__":
    main()
