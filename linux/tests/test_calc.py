"""Math in notes (like Apple's Math Notes). The same cases are in Android's CalcTest."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from linotes import calc  # noqa: E402

CASES = [
    ("2+2=", [], "4"),
    ("12,5 * 4 =", [], "50"),
    ("√12 =", [], "3,464101615"),
    ("x*y=", ["x = 64", "y=2"], "128"),
    ("Summe 450 + 120 =", [], "570"),
    ("Miete * 12 =", ["Miete = 450 + 120"], "6840"),
    ("10 / 3 =", [], "3,333333333"),
    ("2^10 =", [], "1024"),
    ("19% * 200 =", [], "38"),
    ("(1+2)*3 =", [], "9"),
    ("2 × 3 · 4 ÷ 6 =", [], "4"),
    ("-5 + 2 =", [], "-3"),
    ("sin(0) =", [], "0"),
    ("π * 2 =", [], "6,283185307"),
    ("0,1 + 0,2 =", [], "0,3"),
    ("1000000 * 3 =", [], "3000000"),
    # Not a calculation: plain numbers, assignments, division by zero, words.
    ("5 =", [], None),
    ("x = 3 =", [], None),
    ("1/0 =", [], None),
    ("Hallo =", [], None),
    ("Termin am 3.10. =", [], None),
]


def main():
    for line, earlier, expected in CASES:
        got = calc.result_for(line, earlier)
        assert got == expected, (line, got, expected)
    print("ok – Rechnen")


if __name__ == "__main__":
    main()


def test_editor():
    import gi
    gi.require_version("Gtk", "4.0")
    from gi.repository import GLib
    from linotes.editor import NoteEditor
    editor = NoteEditor()
    editor.load_blocks([{"t": "title", "x": "Kosten"}, {"t": "body", "x": "Miete = 450"}, {"t": "body", "x": "Miete * 12 "}])
    buffer = editor.buffer
    buffer.place_cursor(buffer.get_end_iter())
    buffer.insert_at_cursor("=")
    context = GLib.MainContext.default()
    while context.pending():
        context.iteration(False)
    assert editor.to_blocks()[2]["x"] == "Miete * 12 = 5400", editor.to_blocks()
    print("ok – Rechnen im Editor")


if __name__ == "__main__":
    test_editor()
