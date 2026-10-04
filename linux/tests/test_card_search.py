"""Searching cards in a board. The same cases are in Android's CardSearchTest."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from linotes import model  # noqa: E402

CARD = {"id": "65a4dd44c0ffee0123456789abcdef01", "data": {
    "title": "Suche in Aufgaben (Lupe)", "notes": "Olaf: Karte xyz123abc987 finden",
    "impact": "Board-Ansicht", "verification": "Screenshots", "version": "2.3.0",
    "commits": [{"h": "e4afa02", "m": "Pläne (Android)"}], "files": [{"n": "Skizze.png"}],
    "evidence": [{"n": "Prüfprotokoll.pdf"}], "assignee": 3}}
NAMES = {3: "Claude"}.get


def main():
    found = lambda query: model.card_matches(CARD, query, NAMES)  # noqa: E731
    assert found("") and found("   ")
    assert found("65a4dd44") and found("65A4DD") and found("c0ffee")           # id, short or any part
    assert found("lupe") and found("XYZ123ABC987") and found("board-ansicht")  # title, notes, fields
    assert found("2.3.0") and found("e4afa02") and found("pläne")              # version, commits
    assert found("skizze") and found("prüfprotokoll") and found("claude")      # files, evidence, person
    assert found("suche lupe") and not found("suche anna")                     # all words
    assert not found("65a4dd45")
    assert model.card_matches({"id": "x", "data": {}}, "x") and not model.card_matches({"id": "x", "data": {}}, "y")
    print("ok – Karten suchen")


if __name__ == "__main__":
    main()
