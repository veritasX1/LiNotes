"""Formulas (LaTeX, card 25ae467f): the setting is the same on Ubuntu and Android. The cases are set
with a made-up measure (every character half the font size wide) and stored in data/math-cases.json;
Android's MathTexTest reads the same file. After a deliberate change of mathtex.py:

    python3 tests/test_math.py --update     (then mirror the change in MathTex.kt)"""

import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ["XDG_DATA_HOME"] = os.environ["XDG_CONFIG_HOME"] = os.environ["XDG_CACHE_HOME"] = tempfile.mkdtemp()
import gi  # noqa: E402

gi.require_version("Gtk", "4.0")

from linotes import mathtex  # noqa: E402

CASES_FILE = Path(__file__).resolve().parent / "data" / "math-cases.json"
CASES = [
    r"x = \frac{-b \pm \sqrt{b^2 - 4ac}}{2a}",
    r"e^{i\pi} + 1 = 0",
    r"\sum_{k=1}^{n} k = \frac{n(n+1)}{2}",
    r"\int_0^\infty e^{-x^2}\,dx = \frac{\sqrt{\pi}}{2}",
    r"\lim_{x \to 0} \frac{\sin x}{x} = 1",
    r"\left( \frac{a}{b} \right)^2 \leq \alpha_i^2 + \beta'",
    r"A = \begin{pmatrix} 1 & 2 \\ 3 & 4 \end{pmatrix}",
    r"|x| = \begin{cases} x & \text{wenn } x \geq 0 \\ -x & \text{sonst} \end{cases}",
    r"\sqrt[3]{8} = 2, \quad \vec{v} \cdot \hat{n}, \bar{x}, \tilde{a}, \dot{x}, \ddot{y}, \overline{AB}, \underline{u}",
    r"\mathbb{R}^n \to \mathbb{C}, \ \Gamma(z) \approx \mathrm{d}x \mathbf{v}",
    r"\begin{aligned} f(x) &= (x+1)^2 \\ &= x^2 + 2x + 1 \end{aligned}",
    r"a^2 + b^2 = c^2 \\ E = mc^2",
    r"\left\{ x \in \mathbb{N} \mid x > 2 \right\}, \binom{n}{k}, \left[ \sum_i x_i \right], \left. \frac{1}{2} \right|",
    r"\bigl( x \bigr) \Big[ y \Big] \operatorname{rank} A, \max_{i} a_i, \sum\nolimits_i, \int\limits_0^1",
    r"\begin{vmatrix} a & b \\ c & d \end{vmatrix} \begin{bmatrix} 1 \end{bmatrix} \begin{Bmatrix} x \end{Bmatrix} \begin{Vmatrix} y \end{Vmatrix}",
    r"\langle u, v \rangle \lfloor x \rfloor \lceil y \rceil -1 + -x, a - -b % Kommentar",
    r"\frac{1}{1+\frac{1}{x}} \foo { x^",
    r"\end{x} } \right) _2 ^",
    r"",
    r"x_{i_{j_{k}}}^{2^{2^{2}}} \text{Größe} \mathbb{A} 𝔸 ü",
]


def measure(text, size, _style):
    return 0.5 * size * len(text)


def current():
    return [{"source": source, "result": mathtex.rounded(mathtex.layout(source, 20.0, measure))} for source in CASES]


def check_twin_cases():
    cases = current()
    if "--update" in sys.argv:
        CASES_FILE.write_text(json.dumps(cases, ensure_ascii=False, indent=1) + "\n")
    stored = json.loads(CASES_FILE.read_text())
    assert [c["source"] for c in stored] == CASES, "data/math-cases.json passt nicht zu CASES (--update)"
    for old, new in zip(stored, cases):
        assert old == json.loads(json.dumps(new)), f"Satz geändert: {old['source']} (--update, Kotlin nachziehen)"


def check_rules():
    def ops(source):
        return mathtex.layout(source, 20.0, measure)
    # Spacing like TeX: = gets thick spaces, a sign after = none.
    texts = [(op[1], op[3]) for op in ops("a=-b").ops]
    assert texts[0] == (0.0, "a") and texts[1][1] == "=" and texts[1][0] > 10.0 and texts[2][0] - texts[1][0] > 10.0
    assert texts[3][0] - texts[2][0] == 10.0  # "−" then "b" without space: a sign
    # Unknown commands, missing braces: red, no exception.
    for broken in (r"\foo", "{", "}", r"\frac{", r"\left(", r"\begin{pmatrix}", "^", "x^", r"\sqrt[", "{" * 200, r"\right)"):
        formula = ops(broken)
        assert formula.width >= 0
    assert ops(r"\foo").error and not ops(r"\frac{a}{b}").error
    assert ops("{" * 200).error  # too deep → marked, no crash
    # Fractions: numerator above, denominator below the baseline.
    fraction = ops(r"\frac{a}{b}")
    a, b = [op for op in fraction.ops if op[0] == "text"]
    assert a[2] < fraction.ascent < b[2]
    # Limits under \sum in display style, beside it with \nolimits.
    under = [op for op in ops(r"\sum_{i}").ops if op[0] == "text"]
    beside = [op for op in ops(r"\sum\nolimits_{i}").ops if op[0] == "text"]
    assert under[1][1] < under[0][1] + 20 and beside[1][1] >= beside[0][1] + 0.5 * 31
    # \mathbb gives double-struck letters.
    assert [op[3] for op in ops(r"\mathbb{R}").ops] == ["ℝ"]


def check_editor():
    from linotes.editor import NoteEditor
    editor = NoteEditor()
    blocks = [{"t": "title", "x": "Formeln"}, {"t": "math", "x": r"\frac{a}{b}"}, {"t": "body", "x": "Text"}]
    editor.load_blocks(blocks)
    assert editor.to_blocks() == blocks, editor.to_blocks()
    anchor = next(a for a, e in editor.anchors.items() if "math" in e)
    editor.set_math(anchor, r"\sqrt{2}")
    assert editor.to_blocks()[1] == {"t": "math", "x": r"\sqrt{2}"}
    assert editor.line_alignment(1) == "center"
    editor.buffer.place_cursor(editor.buffer.get_end_iter())
    editor.insert_math("x^2")
    assert [b for b in editor.to_blocks() if b["t"] == "math"][-1] == {"t": "math", "x": "x^2"}
    # Typing goes on below the formula, left aligned (the centering belongs to the formula line only).
    editor.buffer.insert_interactive_at_cursor("weiter", -1, True)
    line = editor.buffer.get_iter_at_mark(editor.buffer.get_insert()).get_line()
    assert editor.line_alignment(line) is None and "a" not in editor.to_blocks()[-1], editor.to_blocks()[-1]
    assert editor.to_blocks()[-1]["x"] == "weiter"


def check_pdf():
    from linotes import report
    path = Path(tempfile.mkdtemp()) / "formel.pdf"
    blocks = [{"t": "title", "x": "Formel"}, {"t": "math", "x": r"\int_0^1 x^2\,dx = \frac{1}{3}"}]
    report.write_note_pdf(blocks, path, "Test")
    data = path.read_bytes()
    assert data.startswith(b"%PDF") and len(data) > 1000


def main():
    check_twin_cases()
    check_rules()
    check_editor()
    check_pdf()
    print("ok – Formeln")


if __name__ == "__main__":
    main()
