from .i18n import _
"""Formulas in LaTeX notation, set the way TeX does it – a small, offline part of TeX: fractions, roots,
indices, Greek letters, sums and integrals with limits, growing brackets, matrices, cases, aligned
equations, accents and the usual symbols. No library: the layout here gives drawing steps (text,
rules, lines) that Cairo draws in the editor and the PDF. Twin: MathTex.kt (MathTexTest has the same
cases, test_math.py here) – keep both in step.

A formula block in a note: {"t": "math", "x": "<LaTeX>"}. Older LiNotes versions show the source."""

AXIS = 0.26          # height of the math axis (middle of "+", fraction bar) in font sizes
ASCENT = 0.72        # nominal glyph height above the baseline
DESCENT = 0.22       # … and below
SCALES = (1.0, 1.0, 0.7, 0.5)   # display, text, script, scriptscript
MAX_DEPTH = 40

GREEK = {
    "alpha": "α", "beta": "β", "gamma": "γ", "delta": "δ", "epsilon": "ϵ", "varepsilon": "ε", "zeta": "ζ",
    "eta": "η", "theta": "θ", "vartheta": "ϑ", "iota": "ι", "kappa": "κ", "lambda": "λ", "mu": "μ", "nu": "ν",
    "xi": "ξ", "pi": "π", "varpi": "ϖ", "rho": "ρ", "varrho": "ϱ", "sigma": "σ", "varsigma": "ς", "tau": "τ",
    "upsilon": "υ", "phi": "ϕ", "varphi": "φ", "chi": "χ", "psi": "ψ", "omega": "ω",
}
GREEK_UPPER = {
    "Gamma": "Γ", "Delta": "Δ", "Theta": "Θ", "Lambda": "Λ", "Xi": "Ξ", "Pi": "Π", "Sigma": "Σ",
    "Upsilon": "Υ", "Phi": "Φ", "Psi": "Ψ", "Omega": "Ω",
}
# name: (character, class) – classes as in TeX: ord, bin, rel, open, close, punct
SYMBOLS = {
    "pm": ("±", "bin"), "mp": ("∓", "bin"), "times": ("×", "bin"), "div": ("÷", "bin"), "cdot": ("⋅", "bin"),
    "ast": ("∗", "bin"), "star": ("⋆", "bin"), "circ": ("∘", "bin"), "bullet": ("∙", "bin"), "oplus": ("⊕", "bin"),
    "ominus": ("⊖", "bin"), "otimes": ("⊗", "bin"), "cup": ("∪", "bin"), "cap": ("∩", "bin"), "setminus": ("∖", "bin"),
    "wedge": ("∧", "bin"), "land": ("∧", "bin"), "vee": ("∨", "bin"), "lor": ("∨", "bin"),
    "leq": ("≤", "rel"), "le": ("≤", "rel"), "geq": ("≥", "rel"), "ge": ("≥", "rel"), "neq": ("≠", "rel"), "ne": ("≠", "rel"),
    "approx": ("≈", "rel"), "equiv": ("≡", "rel"), "sim": ("∼", "rel"), "simeq": ("≃", "rel"), "cong": ("≅", "rel"),
    "propto": ("∝", "rel"), "ll": ("≪", "rel"), "gg": ("≫", "rel"), "in": ("∈", "rel"), "notin": ("∉", "rel"),
    "ni": ("∋", "rel"), "subset": ("⊂", "rel"), "supset": ("⊃", "rel"), "subseteq": ("⊆", "rel"), "supseteq": ("⊇", "rel"),
    "to": ("→", "rel"), "rightarrow": ("→", "rel"), "leftarrow": ("←", "rel"), "gets": ("←", "rel"),
    "leftrightarrow": ("↔", "rel"), "Rightarrow": ("⇒", "rel"), "Leftarrow": ("⇐", "rel"), "Leftrightarrow": ("⇔", "rel"),
    "implies": ("⟹", "rel"), "iff": ("⟺", "rel"), "mapsto": ("↦", "rel"), "perp": ("⊥", "rel"), "parallel": ("∥", "rel"),
    "mid": ("∣", "rel"), "colon": (":", "punct"),
    "infty": ("∞", "ord"), "partial": ("∂", "ord"), "nabla": ("∇", "ord"), "forall": ("∀", "ord"), "exists": ("∃", "ord"),
    "nexists": ("∄", "ord"), "emptyset": ("∅", "ord"), "varnothing": ("∅", "ord"), "neg": ("¬", "ord"), "lnot": ("¬", "ord"),
    "angle": ("∠", "ord"), "triangle": ("△", "ord"), "hbar": ("ℏ", "ord"), "ell": ("ℓ", "ord"), "Re": ("ℜ", "ord"),
    "Im": ("ℑ", "ord"), "aleph": ("ℵ", "ord"), "prime": ("′", "ord"), "degree": ("°", "ord"), "dagger": ("†", "ord"),
    "ldots": ("…", "inner"), "dots": ("…", "inner"), "cdots": ("⋯", "inner"), "vdots": ("⋮", "ord"), "ddots": ("⋱", "ord"),
    "langle": ("⟨", "open"), "rangle": ("⟩", "close"), "lfloor": ("⌊", "open"), "rfloor": ("⌋", "close"),
    "lceil": ("⌈", "open"), "rceil": ("⌉", "close"), "vert": ("|", "ord"), "Vert": ("‖", "ord"),
    "{": ("{", "open"), "}": ("}", "close"), "|": ("‖", "ord"), "_": ("_", "ord"), "%": ("%", "ord"),
    "&": ("&", "ord"), "#": ("#", "ord"), "$": ("$", "ord"),
}
CHARACTERS = {"+": ("+", "bin"), "-": ("−", "bin"), "*": ("∗", "bin"), "=": ("=", "rel"), "<": ("<", "rel"),
              ">": (">", "rel"), ":": (":", "rel"), ",": (",", "punct"), ";": (";", "punct"), "(": ("(", "open"),
              "[": ("[", "open"), ")": (")", "close"), "]": ("]", "close"), "!": ("!", "close"), "?": ("?", "close"),
              "/": ("/", "ord"), "|": ("|", "ord"), ".": (".", "ord")}
BIG_OPERATORS = {"sum": "∑", "prod": "∏", "coprod": "∐", "int": "∫", "iint": "∬", "iiint": "∭", "oint": "∮",
                 "bigcup": "⋃", "bigcap": "⋂", "bigoplus": "⨁", "bigotimes": "⨂", "bigvee": "⋁", "bigwedge": "⋀"}
INTEGRALS = {"int", "iint", "iiint", "oint"}
FUNCTIONS = {"sin", "cos", "tan", "cot", "sec", "csc", "arcsin", "arccos", "arctan", "sinh", "cosh", "tanh", "coth",
             "log", "ln", "lg", "exp", "det", "dim", "ker", "deg", "gcd", "min", "max", "sup", "inf", "lim", "liminf",
             "limsup", "Pr", "arg", "hom", "mod"}
LIMIT_FUNCTIONS = {"det", "gcd", "min", "max", "sup", "inf", "lim", "liminf", "limsup", "Pr"}
SPACES = {",": 3 / 18, ":": 4 / 18, ">": 4 / 18, ";": 5 / 18, "!": -3 / 18, " ": 6 / 18, "quad": 1.0, "qquad": 2.0,
          "enspace": 0.5, "thinspace": 3 / 18}
FONTS = {"mathrm": "rm", "mathbf": "bf", "mathit": "it", "mathsf": "rm", "mathtt": "rm", "mathbb": "bb",
         "mathcal": "it", "boldsymbol": "bf", "bm": "bf"}
TEXTS = {"text": "rm", "textrm": "rm", "mbox": "rm", "textbf": "bf", "textit": "it", "textsf": "rm", "texttt": "rm"}
ACCENTS = {"hat", "widehat", "bar", "overline", "underline", "vec", "overrightarrow", "dot", "ddot", "tilde", "widetilde"}
DELIMITERS = {"(": "(", ")": ")", "[": "[", "]": "]", "\\{": "{", "\\}": "}", "|": "|", "\\|": "‖", "\\vert": "|",
              "\\Vert": "‖", "\\langle": "⟨", "\\rangle": "⟩", ".": "", "<": "⟨", ">": "⟩", "\\lfloor": "⌊",
              "\\rfloor": "⌋", "\\lceil": "⌈", "\\rceil": "⌉", "\\lbrace": "{", "\\rbrace": "}"}
BIG_SIZES = {"big": 1.2, "Big": 1.8, "bigg": 2.4, "Bigg": 3.0}
ENVIRONMENTS = {"matrix": ("", ""), "pmatrix": ("(", ")"), "bmatrix": ("[", "]"), "Bmatrix": ("{", "}"),
                "vmatrix": ("|", "|"), "Vmatrix": ("‖", "‖"), "cases": ("{", ""), "aligned": ("", ""),
                "align": ("", ""), "align*": ("", ""), "gathered": ("", ""), "gather": ("", ""), "array": ("", ""),
                "split": ("", "")}
DOUBLE_STRUCK = {"C": "ℂ", "H": "ℍ", "N": "ℕ", "P": "ℙ", "Q": "ℚ", "R": "ℝ", "Z": "ℤ"}


def double_struck(char):
    if char in DOUBLE_STRUCK:
        return DOUBLE_STRUCK[char]
    if "A" <= char <= "Z":
        return chr(0x1D538 + ord(char) - ord("A"))
    if "a" <= char <= "z":
        return chr(0x1D552 + ord(char) - ord("a"))
    if "0" <= char <= "9":
        return chr(0x1D7D8 + ord(char) - ord("0"))
    return char


def is_letter(char):
    return ("a" <= char <= "z") or ("A" <= char <= "Z")


# ============================================================
# READING (source → tree)
# ============================================================

def tokens(source):
    """Commands (\\frac, \\, …), single characters, and " " for any run of white space."""
    result = []
    index = 0
    while index < len(source):
        char = source[index]
        if char == "\\":
            end = index + 1
            if end < len(source) and is_letter(source[end]):
                while end < len(source) and is_letter(source[end]):
                    end += 1
                result.append(source[index:end])
                index = end
            else:
                result.append(source[index:end + 1])
                index = end + 1
        elif char.isspace():
            while index < len(source) and source[index].isspace():
                index += 1
            result.append(" ")
        elif char == "%":
            while index < len(source) and source[index] != "\n":
                index += 1  # a comment up to the end of the line
        else:
            result.append(char)
            index += 1
    return result


class Parser:
    """Turns tokens into nodes – lists like ["sym", char, class, italic]. Never fails: whatever it
    cannot read becomes an ["error", text] node, shown in red."""

    def __init__(self, source):
        self.tokens = tokens(source)
        self.index = 0
        self.depth = 0

    def peek(self, skip=True):
        if skip:
            while self.index < len(self.tokens) and self.tokens[self.index] == " ":
                self.index += 1
        return self.tokens[self.index] if self.index < len(self.tokens) else None

    def take(self, skip=True):
        token = self.peek(skip)
        if token is not None:
            self.index += 1
        return token

    def rows(self, inside=False):
        """Rows (split by \\\\) of cells (split by &) – of the whole formula or, inside=True, of an
        environment up to its \\end (not taken)."""
        rows = [[]]
        while True:
            rows[-1].append(self.list({"&", "\\\\", "}", "\\right", "\\end"}))
            token = self.peek()
            if token is None or (inside and token == "\\end"):
                return rows
            self.index += 1
            if token == "\\\\":
                rows.append([])
            elif token != "&":
                rows[-1][-1].append(["error", token])  # a stray }, \right or \end

    def list(self, stops):
        nodes = []
        self.depth += 1
        if self.depth > MAX_DEPTH:
            self.depth -= 1
            self.index = len(self.tokens)
            return [["error", "…"]]
        while True:
            token = self.peek()
            if token is None or token in stops:
                break
            self.index += 1
            if token in ("^", "_"):
                self.attach(nodes, "sup" if token == "^" else "sub", self.argument())
            elif token == "'":
                primes = "′"
                while self.peek(False) == "'":
                    self.index += 1
                    primes += "′"
                self.attach(nodes, "sup", ["sym", primes, "ord", False])
            elif token in ("\\limits", "\\nolimits"):
                target = nodes[-1] if nodes else None
                if target and target[0] == "scripts":
                    target = target[1]
                if target and target[0] in ("bigop", "op"):
                    target[2] = token == "\\limits"
            else:
                nodes.append(self.atom(token))
        self.depth -= 1
        return nodes

    @staticmethod
    def attach(nodes, where, argument):
        if nodes and nodes[-1][0] == "scripts" and nodes[-1][2 if where == "sup" else 3] is None:
            nodes[-1][2 if where == "sup" else 3] = argument
            return
        base = nodes.pop() if nodes and nodes[-1][0] != "scripts" else ["group", []]
        nodes.append(["scripts", base, argument if where == "sup" else None, argument if where == "sub" else None])

    def argument(self):
        token = self.take()
        if token is None:
            return ["group", []]
        if token in ("}", "&", "\\\\", "^", "_"):
            self.index -= 1
            return ["error", "{}"]
        return self.atom(token)

    def group(self):
        """{ … } as a list (or the one atom when there are no braces)."""
        if self.peek() == "{":
            self.index += 1
            nodes = self.list({"}"})
            if self.take() != "}":
                nodes.append(["error", "}"])
            return ["group", nodes]
        return self.argument()

    def raw_group(self):
        """{text} as written (for \\text, \\begin, \\operatorname)."""
        if self.peek() != "{":
            token = self.take()
            return token or ""
        self.index += 1
        text, depth = "", 0
        while self.index < len(self.tokens):
            token = self.tokens[self.index]
            self.index += 1
            if token == "{":
                depth += 1
            elif token == "}":
                if depth == 0:
                    return text
                depth -= 1
            text += token[1:] if len(token) == 2 and token[0] == "\\" and not is_letter(token[1]) else token
        return text

    def delimiter(self):
        token = self.take()
        if token is None:
            return ""
        return DELIMITERS.get(token)

    def atom(self, token):
        if token == "{":
            nodes = self.list({"}"})
            if self.take() != "}":
                nodes.append(["error", "}"])
            return ["group", nodes]
        if token == "}":
            return ["error", "}"]
        if not token.startswith("\\"):
            if token in CHARACTERS:
                char, kind = CHARACTERS[token]
                return ["sym", char, kind, False]
            if token == "~":
                return ["space", 6 / 18]
            if token == "&":
                return ["error", "&"]
            return ["sym", token, "ord", token.isalpha()]
        name = token[1:]
        if name in GREEK:
            return ["sym", GREEK[name], "ord", True]
        if name in GREEK_UPPER:
            return ["sym", GREEK_UPPER[name], "ord", False]
        if name in SYMBOLS:
            char, kind = SYMBOLS[name]
            return ["sym", char, kind, False]
        if name in SPACES:
            return ["space", SPACES[name]]
        if name in ("frac", "dfrac", "tfrac", "cfrac"):
            return ["frac", self.group(), self.group(), True]
        if name in ("binom", "dbinom", "tbinom"):
            return ["leftright", "(", [["frac", self.group(), self.group(), False]], ")"]
        if name == "sqrt":
            index = None
            if self.peek() == "[":
                self.index += 1
                index = ["group", self.list({"]"})]
                self.take()
            return ["sqrt", self.group(), index]
        if name in BIG_OPERATORS:
            return ["bigop", BIG_OPERATORS[name], name not in INTEGRALS]
        if name in FUNCTIONS:
            return ["op", name, name in LIMIT_FUNCTIONS]
        if name == "operatorname":
            return ["op", self.raw_group(), False]
        if name in TEXTS:
            return ["text", self.raw_group(), TEXTS[name]]
        if name in FONTS:
            return ["font", FONTS[name], self.group()]
        if name in ACCENTS:
            return ["accent", name, self.group()]
        if name == "left":
            left = self.delimiter()
            body = self.list({"\\right"})
            right = ""
            if self.peek() == "\\right":
                self.index += 1
                right = self.delimiter()
            if left is None or right is None:
                return ["error", "\\left"]
            return ["leftright", left, body, right]
        if name == "right":
            return ["error", token]
        if name.rstrip("lrm") in BIG_SIZES and name not in ("bigcup", "bigcap"):
            size = BIG_SIZES[name.rstrip("lrm")]
            char = self.delimiter()
            return ["bigdelim", char, size] if char is not None else ["error", token]
        if name == "begin":
            environment = self.raw_group()
            if environment == "array" and self.peek() == "{":
                self.raw_group()  # column spec: the cells are centered
            rows = self.rows(inside=True)
            if self.take() != "\\end" or self.raw_group() != environment or environment not in ENVIRONMENTS:
                return ["error", f"\\begin{{{environment}}}"]
            return ["matrix", environment, rows]
        return ["error", token]


def parse(source):
    return Parser(source).rows()


# ============================================================
# SETTING (tree → boxes → drawing steps)
# ============================================================

class Box:
    """Width, height above and depth below the baseline; items placed relative to the baseline,
    y upwards: ("text", x, y, text, size, style), ("rule", x, y, w, h) with y the lower edge,
    ("path", [(x, y), …], thickness), ("box", x, y, Box)."""
    __slots__ = ("width", "ascent", "descent", "items", "kind")

    def __init__(self, width=0.0, ascent=0.0, descent=0.0, items=None, kind="ord"):
        self.width, self.ascent, self.descent = width, ascent, descent
        self.items = items if items is not None else []
        self.kind = kind


class Setter:
    def __init__(self, size, measure):
        self.size = size
        self.measure = measure

    def text(self, text, size, style, kind="ord"):
        return Box(self.measure(text, size, style), ASCENT * size, DESCENT * size, [("text", 0.0, 0.0, text, size, style)], kind)

    # ---- lists and spacing ----

    def space(self, left, right, level, size):
        if left is None or right is None:
            return 0.0
        mu = size / 18
        if "op" in (left, right) and left not in ("open", "punct") and right not in ("close", "punct", "rel", "bin"):
            return 3 * mu
        if level >= 2:
            return 0.0
        if left == "rel" or right == "rel":
            return 0.0 if (left == right) or left == "open" or right in ("close", "punct") else 5 * mu
        if left == "bin" or right == "bin":
            return 4 * mu
        if left == "punct" or (left == "inner" and right not in ("close", "punct")) or (right == "inner" and left != "open"):
            return 3 * mu
        return 0.0

    def row(self, nodes, level, font):
        size = self.size * SCALES[level]
        boxes = [self.node(node, level, font) for node in nodes]
        # A + or − at the start, after an operator or an opening bracket is a sign, not an operation.
        previous = None
        for index, box in enumerate(boxes):
            if box.kind is None:
                continue
            if box.kind == "bin":
                following = next((b.kind for b in boxes[index + 1:] if b.kind is not None), None)
                if previous in (None, "bin", "rel", "open", "punct", "op") or following in (None, "rel", "close", "punct"):
                    box.kind = "ord"
            previous = box.kind
        result = Box()
        previous = None
        x = 0.0
        for box in boxes:
            if box.kind is not None:
                x += self.space(previous, box.kind, level, size)
                previous = box.kind
            result.items.append(("box", x, 0.0, box))
            x += box.width
            result.ascent = max(result.ascent, box.ascent)
            result.descent = max(result.descent, box.descent)
        result.width = x
        if len(boxes) == 1:
            result.kind = boxes[0].kind
        return result

    def node(self, node, level, font):
        size = self.size * SCALES[level]
        kind = node[0]
        if kind == "sym":
            _, char, cls, italic = node
            style = "it" if italic else "rm"
            if font == "bb":
                char, style = "".join(double_struck(c) for c in char), "rm"
            elif font in ("rm", "bf") and (is_letter(char[0]) or char[0].isdigit() or italic):
                style = font
            elif font == "it" and is_letter(char[0]):
                style = "it"
            elif font == "bf":
                style = "bf"
            return self.text(char, size, style, cls)
        if kind == "group":
            return self.row(node[1], level, font)
        if kind == "font":
            return self.node(node[2], level, node[1])
        if kind == "text":
            return self.text(node[1] or " ", size, node[2])
        if kind == "space":
            return Box(node[1] * size, kind=None)
        if kind == "error":
            return self.text(node[1], size, "err")
        if kind == "frac":
            return self.fraction(node[1], node[2], node[3], level, font)
        if kind == "sqrt":
            return self.root(node[1], node[2], level, font)
        if kind == "scripts":
            return self.scripts(node[1], node[2], node[3], level, font)
        if kind == "bigop":
            return self.big_operator(node[1], level)
        if kind == "op":
            box = self.text(node[1], size, "rm", "op")
            return box
        if kind == "leftright":
            body = self.row(node[2], level, font)
            return self.fence(node[1], body, node[3], level)
        if kind == "bigdelim":
            height = node[2] * size
            box = self.delimiter(node[1], height, size)
            box.kind = "open" if node[1] in "([{⟨⌊⌈" else "close" if node[1] in ")]}⟩⌋⌉" else "ord"
            return box
        if kind == "accent":
            return self.accent(node[1], node[2], level, font)
        if kind == "matrix":
            return self.matrix(node[1], node[2], level, font)
        return Box()

    # ---- the pieces ----

    def fraction(self, top, bottom, rule, level, font):
        size = self.size * SCALES[level]
        inner = min(level + 1, 3)
        num = self.node(top, inner, font)
        den = self.node(bottom, inner, font)
        thick = 0.06 * size if rule else 0.0
        gap = (0.14 if level == 0 else 0.08) * size
        pad = 0.12 * size
        width = max(num.width, den.width) + 2 * pad
        axis = AXIS * size
        up = axis + thick / 2 + gap + num.descent
        down = axis - thick / 2 - gap - den.ascent
        items = [("box", (width - num.width) / 2, up, num), ("box", (width - den.width) / 2, down, den)]
        if rule:
            items.append(("rule", pad / 2, axis - thick / 2, width - pad, thick))
        return Box(width, up + num.ascent, den.descent - down, items, "inner")

    def root(self, body_node, index_node, level, font):
        size = self.size * SCALES[level]
        body = self.node(body_node, level, font)
        thick = 0.06 * size
        gap = (0.12 if level == 0 else 0.08) * size
        top = max(body.ascent, ASCENT * size * 0.9) + gap
        bottom = max(body.descent, DESCENT * size * 0.5)
        height = top + bottom
        sign = 0.55 * size
        shift = 0.0
        index = None
        if index_node is not None:
            index = self.node(index_node, 3, font)
            shift = max(0.0, index.width - 0.28 * size)
        x = shift
        points = [(x, -bottom + 0.42 * height), (x + 0.14 * size, -bottom + 0.5 * height), (x + 0.32 * size, -bottom),
                  (x + sign, top + thick / 2), (x + sign + body.width + 0.1 * size, top + thick / 2)]
        items = [("path", points, thick), ("box", x + sign, 0.0, body)]
        ascent = top + thick
        if index is not None:
            index_up = -bottom + 0.62 * height + index.descent
            items.append(("box", x + 0.3 * size - index.width, index_up, index))
            ascent = max(ascent, index_up + index.ascent)
        return Box(x + sign + body.width + 0.12 * size, ascent, bottom + thick, items)

    def big_operator(self, char, level):
        size = self.size * SCALES[level]
        glyph = (1.55 if level == 0 else 1.15) * size
        if char in "∫∬∭∮":
            glyph = (1.8 if level == 0 else 1.25) * size
        base = AXIS * size - 0.27 * glyph
        width = self.measure(char, glyph, "rm")
        return Box(width, base + 0.78 * glyph, 0.26 * glyph - base, [("text", 0.0, base, char, glyph, "rm")], "op")

    def scripts(self, base_node, sup_node, sub_node, level, font):
        size = self.size * SCALES[level]
        base = self.node(base_node, level, font)
        inner = 2 if level < 2 else 3
        sup = self.node(sup_node, inner, font) if sup_node is not None else None
        sub = self.node(sub_node, inner, font) if sub_node is not None else None
        limits = base_node[0] in ("bigop", "op") and level == 0 and base_node[2]
        if limits:
            gap = 0.12 * size
            width = max(base.width, sup.width if sup else 0, sub.width if sub else 0)
            items = [("box", (width - base.width) / 2, 0.0, base)]
            ascent, descent = base.ascent, base.descent
            if sup:
                up = base.ascent + gap + sup.descent
                items.append(("box", (width - sup.width) / 2, up, sup))
                ascent = up + sup.ascent
            if sub:
                down = base.descent + gap + sub.ascent
                items.append(("box", (width - sub.width) / 2, -down, sub))
                descent = down + sub.descent
            return Box(width, ascent, descent, items, "op")
        up = max(base.ascent - 0.38 * size, 0.38 * size) if sup else 0.0
        down = max(base.descent - 0.1 * size, 0.18 * size) if sub else 0.0
        if sup and sub:
            down = max(down, 0.26 * size)
            gap = (up - sup.descent) - (sub.ascent - down)
            if gap < 0.12 * size:
                down += 0.12 * size - gap
        items = [("box", 0.0, 0.0, base)]
        width = 0.0
        ascent, descent = base.ascent, base.descent
        x = base.width + (0.03 * size if base_node[0] == "sym" and base_node[3] else 0.0)
        if base_node[0] == "bigop" and base_node[1] in "∫∬∭∮":
            x -= 0.1 * size  # integral limits tuck in under the slant
        if sup:
            items.append(("box", x, up, sup))
            width = max(width, sup.width)
            ascent = max(ascent, up + sup.ascent)
        if sub:
            sub_x = base.width if not (base_node[0] == "bigop" and base_node[1] in "∫∬∭∮") else base.width - 0.25 * size
            items.append(("box", sub_x, -down, sub))
            width = max(width, sub_x - x + sub.width)
            descent = max(descent, down + sub.descent)
        return Box(x + width + 0.04 * size, ascent, descent, items, base.kind)

    def fence(self, left, body, right, level):
        size = self.size * SCALES[level]
        axis = AXIS * size
        half = max(body.ascent - axis, body.descent + axis)
        height = max(2 * half + 0.16 * size, 1.1 * size)
        left_box = self.delimiter(left, height, size)
        right_box = self.delimiter(right, height, size)
        items = [("box", 0.0, 0.0, left_box), ("box", left_box.width, 0.0, body),
                 ("box", left_box.width + body.width, 0.0, right_box)]
        return Box(left_box.width + body.width + right_box.width, max(body.ascent, left_box.ascent),
                   max(body.descent, left_box.descent), items, "inner")

    def delimiter(self, char, height, size):
        """A bracket of any height, drawn as lines (fonts only have a few sizes)."""
        if not char:
            return Box(0.1 * size, kind="ord")
        axis = AXIS * size
        top, bottom = axis + height / 2, axis - height / 2
        middle = axis
        thick = 0.06 * size
        pad = 0.08 * size
        if char in "()":
            width = min(0.28 * size + 0.06 * height, 0.7 * size)
        elif char in "{}":
            width = 0.5 * size
        elif char in "|‖":
            width = (0.3 if char == "|" else 0.45) * size
        else:
            width = 0.36 * size
        inner, outer = pad, width - pad   # bulge side, open side (for an opening bracket)
        paths = []
        if char in "(⟨[{⌊⌈":
            near, far = inner, outer
        else:
            near, far = outer, inner
        if char in "()":
            control = 2 * near - far
            points = []
            for step in range(13):
                t = step / 12
                y = (1 - t) ** 2 * top + 2 * (1 - t) * t * middle + t * t * bottom
                x = (1 - t) ** 2 * far + 2 * (1 - t) * t * control + t * t * far
                points.append((x, y))
            paths.append(points)
        elif char in "[]":
            paths.append([(far, top), (near, top), (near, bottom), (far, bottom)])
        elif char in "⌊⌋":
            paths.append([(near, top), (near, bottom), (far, bottom)])
        elif char in "⌈⌉":
            paths.append([(far, top), (near, top), (near, bottom)])
        elif char in "⟨⟩":
            paths.append([(far, top), (near, middle), (far, bottom)])
        elif char in "{}":
            centre = width / 2
            paths.append([(far, top), (centre, top - 0.06 * height), (centre, middle + 0.06 * height), (near, middle),
                          (centre, middle - 0.06 * height), (centre, bottom + 0.06 * height), (far, bottom)])
        elif char == "|":
            paths.append([(width / 2, top), (width / 2, bottom)])
        elif char == "‖":
            paths.append([(width / 2 - 0.08 * size, top), (width / 2 - 0.08 * size, bottom)])
            paths.append([(width / 2 + 0.08 * size, top), (width / 2 + 0.08 * size, bottom)])
        items = [("path", points, thick) for points in paths]
        return Box(width, top + thick, thick - bottom, items, "ord")

    def accent(self, name, body_node, level, font):
        size = self.size * SCALES[level]
        body = self.node(body_node, level, font)
        thick = 0.05 * size
        top = max(body.ascent, ASCENT * size * 0.85) + 0.06 * size
        slant = 0.08 * size if body_node[0] == "sym" and body_node[3] else 0.0
        items = [("box", 0.0, 0.0, body)]
        ascent, descent = body.ascent, body.descent
        middle = body.width / 2 + slant
        if name in ("bar", "overline"):
            inset = 0.04 * size if name == "bar" else 0.0
            items.append(("rule", inset + slant, top, body.width - 2 * inset, thick))
            ascent = top + thick
        elif name == "underline":
            down = body.descent + 0.08 * size
            items.append(("rule", 0.0, -down - thick, body.width, thick))
            descent = down + thick
        elif name in ("hat", "widehat"):
            half = body.width / 2 if name == "widehat" else min(body.width / 2, 0.22 * size)
            items.append(("path", [(middle - half, top), (middle, top + 0.2 * size), (middle + half, top)], thick))
            ascent = top + 0.2 * size + thick
        elif name in ("vec", "overrightarrow"):
            half = max(body.width / 2, 0.22 * size) if name == "overrightarrow" else max(min(body.width / 2, 0.3 * size), 0.22 * size)
            y = top + 0.1 * size
            items.append(("path", [(middle - half, y), (middle + half, y)], thick))
            items.append(("path", [(middle + half - 0.13 * size, y + 0.1 * size), (middle + half, y),
                                   (middle + half - 0.13 * size, y - 0.1 * size)], thick))
            ascent = y + 0.1 * size + thick
        elif name in ("tilde", "widetilde"):
            half = body.width / 2 if name == "widetilde" else min(body.width / 2, 0.24 * size)
            y = top + 0.08 * size
            wave = 0.06 * size
            items.append(("path", [(middle - half, y - wave), (middle - half / 2, y + wave), (middle + half / 2, y - wave),
                                   (middle + half, y + wave)], thick))
            ascent = y + wave + thick
        elif name in ("dot", "ddot"):
            dot = 0.1 * size
            spots = [middle] if name == "dot" else [middle - 0.12 * size, middle + 0.12 * size]
            for spot in spots:
                items.append(("rule", spot - dot / 2, top + 0.02 * size, dot, dot))
            ascent = top + 0.02 * size + dot
        return Box(body.width, ascent, descent, items, body.kind)

    def matrix(self, environment, rows, level, font, centred=True):
        size = self.size * SCALES[level]
        inner = max(level, 1) if environment not in ("aligned", "align", "align*", "gathered", "gather", "split") else level
        aligned = environment in ("aligned", "align", "align*", "split")
        cells = []
        for row in rows:
            line = []
            for column, nodes in enumerate(row):
                if aligned and column % 2 == 1:
                    nodes = [["group", []]] + nodes  # "&=" still spaces the "=" like a relation
                line.append(self.row(nodes, inner, font))
            cells.append(line)
        columns = max(len(line) for line in cells)
        widths = [max((line[c].width for line in cells if c < len(line)), default=0.0) for c in range(columns)]
        if aligned:
            gaps = [0.0 if c % 2 == 0 else 1.0 * size for c in range(columns)]
            sides = ["right" if c % 2 == 0 else "left" for c in range(columns)]
        elif environment == "cases":
            gaps = [1.0 * size] * columns
            sides = ["left"] * columns
        else:
            gaps = [0.9 * size] * columns
            sides = ["centre"] * columns
        row_gap = (0.3 if aligned or environment in ("gathered", "gather") else 0.22) * size
        heights = [(max([ASCENT * size] + [c.ascent for c in line]), max([DESCENT * size] + [c.descent for c in line])) for line in cells]
        total = sum(a + d for a, d in heights) + row_gap * (len(cells) - 1)
        axis = AXIS * size if centred else 0.0
        top = axis + total / 2 if centred else heights[0][0]
        width = sum(widths) + sum(gaps[:-1]) if columns else 0.0
        items = []
        y = top
        for line, (ascent, descent) in zip(cells, heights):
            baseline = y - ascent
            x = 0.0
            for column, cell in enumerate(line):
                offset = {"left": 0.0, "right": widths[column] - cell.width}.get(sides[column], (widths[column] - cell.width) / 2)
                items.append(("box", x + offset, baseline, cell))
                x += widths[column] + gaps[column]
            y = baseline - descent - row_gap
        body = Box(width, top, total - top, items, "inner")
        left, right = ENVIRONMENTS.get(environment, ("", ""))
        if not left and not right:
            pad = 0.1 * size if environment not in ("aligned", "align", "align*", "gathered", "gather", "split") else 0.0
            return Box(width + 2 * pad, top, total - top, [("box", pad, 0.0, body)], "inner")
        height = total + 0.2 * size
        left_box = self.delimiter(left, height, size)
        right_box = self.delimiter(right, height, size)
        items = [("box", 0.0, 0.0, left_box), ("box", left_box.width + 0.08 * size, 0.0, body),
                 ("box", left_box.width + 0.16 * size + width, 0.0, right_box)]
        return Box(left_box.width + right_box.width + width + 0.16 * size, max(top, left_box.ascent),
                   max(total - top, left_box.descent), items, "inner")


class Formula:
    """The set formula: size and drawing steps with the top left corner at (0, 0), y downwards –
    ("text", x, baseline, text, size, style) with style rm/it/bf/err, ("rule", x, y, w, h),
    ("path", [(x, y), …], thickness)."""

    def __init__(self, width, ascent, descent, ops, error):
        self.width, self.ascent, self.descent, self.ops, self.error = width, ascent, descent, ops, error

    @property
    def height(self):
        return self.ascent + self.descent


def flatten(box, x, baseline, ops):
    for item in box.items:
        kind = item[0]
        if kind == "box":
            flatten(item[3], x + item[1], baseline - item[2], ops)
        elif kind == "text":
            ops.append(("text", x + item[1], baseline - item[2], item[3], item[4], item[5]))
        elif kind == "rule":
            ops.append(("rule", x + item[1], baseline - item[2] - item[4], item[3], item[4]))
        elif kind == "path":
            ops.append(("path", [(x + px, baseline - py) for px, py in item[1]], item[2]))


def layout(source, size, measure):
    """Set `source` at font size `size` (display style). `measure(text, size, style)` gives a text's
    width – the only thing that differs between Ubuntu (Pango) and Android (Paint)."""
    setter = Setter(size, measure)
    rows = parse(source)
    if len(rows) == 1 and len(rows[0]) == 1:
        box = setter.row(rows[0][0], 0, None)
    else:
        box = setter.matrix("gathered" if all(len(row) == 1 for row in rows) else "aligned", rows, 0, None, centred=False)
    ops = []
    flatten(box, 0.0, box.ascent, ops)
    error = any(op[0] == "text" and op[5] == "err" for op in ops)
    return Formula(box.width, box.ascent, box.descent, ops, error)


def rounded(formula):
    """Steps with numbers rounded to 0.01 – for the twin tests (Python and Kotlin give the same)."""
    def number(value):
        return round(value + 0.0, 2) + 0.0
    result = []
    for op in formula.ops:
        if op[0] == "text":
            result.append(["text", number(op[1]), number(op[2]), op[3], number(op[4]), op[5]])
        elif op[0] == "rule":
            result.append(["rule"] + [number(v) for v in op[1:]])
        else:
            result.append(["path", [[number(x), number(y)] for x, y in op[1]], number(op[2])])
    return [number(formula.width), number(formula.ascent), number(formula.descent), result]


# ============================================================
# DRAWING (Cairo – editor, PDF)
# ============================================================

FAMILY = "Noto Serif, DejaVu Serif, serif"
ERROR_COLOR = (0.85, 0.2, 0.2)
_layouts = {}
_layouts_context = {}


def _pango():
    """Pango and PangoCairo, loaded once (gi.require_version on every measurement cost more than
    setting the formula)."""
    if "modules" not in _layouts_context:
        import gi
        gi.require_version("Pango", "1.0")
        gi.require_version("PangoCairo", "1.0")
        from gi.repository import Pango, PangoCairo
        _layouts_context["modules"] = (Pango, PangoCairo)
    return _layouts_context["modules"]


def _pango_layout(text, size, style):
    Pango, PangoCairo = _pango()
    key = (text, round(size, 2), style)
    entry = _layouts.get(key)
    if entry is None:
        if len(_layouts) > 4000:
            _layouts.clear()
        if "context" not in _layouts_context:
            _layouts_context["context"] = PangoCairo.FontMap.get_default().create_context()
        layout = Pango.Layout.new(_layouts_context["context"])
        font = Pango.FontDescription.from_string(FAMILY)
        font.set_absolute_size(size * Pango.SCALE)
        if style == "it":
            font.set_style(Pango.Style.ITALIC)
        if style == "bf":
            font.set_weight(Pango.Weight.BOLD)
        layout.set_font_description(font)
        layout.set_text(text, -1)
        entry = (layout.get_pixel_extents()[1].width, layout.get_baseline() / Pango.SCALE, font)
        _layouts[key] = entry
    return entry


def measure(text, size, style):
    """Width as the sum of the characters: far fewer different measurements (each costs Pango
    shaping, ~1 ms on an old CPU), and TeX does not kern math either."""
    if len(text) == 1:
        return float(_pango_layout(text, size, style)[0])
    return float(sum(_pango_layout(char, size, style)[0] for char in text))


def draw(cr, formula, x, y, color):
    """Draw at (x, y) = top left corner."""
    _Pango, PangoCairo = _pango()
    cr.save()
    cr.set_line_cap(1)   # round
    cr.set_line_join(1)
    for op in formula.ops:
        cr.set_source_rgb(*(ERROR_COLOR if op[0] == "text" and op[5] == "err" else color))
        if op[0] == "text":
            _width, baseline, font = _pango_layout(op[3], op[4], op[5])
            layout = PangoCairo.create_layout(cr)
            layout.set_font_description(font)
            layout.set_text(op[3], -1)
            cr.move_to(x + op[1], y + op[2] - baseline)
            PangoCairo.show_layout(cr, layout)
        elif op[0] == "rule":
            cr.rectangle(x + op[1], y + op[2], op[3], op[4])
            cr.fill()
        else:
            points = op[1]
            cr.set_line_width(op[2])
            cr.move_to(x + points[0][0], y + points[0][1])
            for px, py in points[1:]:
                cr.line_to(x + px, y + py)
            cr.stroke()
    cr.restore()
