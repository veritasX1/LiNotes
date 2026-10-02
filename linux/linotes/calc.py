"""Math in notes, like Apple's Math Notes: "12,5 * 4 =" gets its result, lines such as
"x = 64" define variables for the lines below. Mirrors android …/data/Calc.kt."""

import math
import re

FUNCTIONS = {"sqrt": math.sqrt, "√": math.sqrt, "sin": math.sin, "cos": math.cos, "tan": math.tan,
             "ln": math.log, "log": math.log10, "abs": abs}
CONSTANTS = {"pi": math.pi, "π": math.pi, "e": math.e}
NAME = r"[A-Za-zÄÖÜäöüßπ_][A-Za-zÄÖÜäöüß_0-9]*"
TOKEN = re.compile(r"\s*(?:(\d+(?:[.,]\d+)?)|(" + NAME + r")|(√)|([-+*/×·÷^%()−]))")
ASSIGNMENT = re.compile(r"^\s*(" + NAME + r")\s*=\s*(.+?)\s*$")


class CalcError(ValueError):
    pass


def tokenize(text):
    tokens, position = [], 0
    text = text.rstrip()
    while position < len(text):
        match = TOKEN.match(text, position)
        if not match or match.end() == position:
            raise CalcError(text[position:])
        number, name, root, operator = match.groups()
        if number:
            tokens.append(("num", float(number.replace(",", "."))))
        elif name:
            tokens.append(("name", name))
        elif root:
            tokens.append(("name", "√"))
        else:
            tokens.append(("op", {"×": "*", "·": "*", "÷": "/", "−": "-"}.get(operator, operator)))
        position = match.end()
    return tokens


class Parser:
    """expression := term (("+"|"-") term)* ; term := power (("*"|"/") power)* ;
    power := unary ("^" power)? ; unary := "-" unary | postfix ; postfix := atom "%"?"""

    def __init__(self, tokens, variables):
        self.tokens, self.index, self.variables = tokens, 0, variables
        self.used = False  # an operator, function or variable was used (not just a number)

    def peek(self):
        return self.tokens[self.index] if self.index < len(self.tokens) else (None, None)

    def take(self, value=None):
        token = self.peek()
        if token[0] is None or (value is not None and token[1] != value):
            raise CalcError("unexpected end")
        self.index += 1
        return token

    def parse(self):
        value = self.expression()
        if self.index != len(self.tokens):
            raise CalcError("trailing")
        return value

    def expression(self):
        value = self.term()
        while self.peek() in (("op", "+"), ("op", "-")):
            operator = self.take()[1]
            self.used = True
            value = value + self.term() if operator == "+" else value - self.term()
        return value

    def term(self):
        value = self.power()
        while self.peek() in (("op", "*"), ("op", "/")):
            operator = self.take()[1]
            self.used = True
            right = self.power()
            if operator == "/" and right == 0:
                raise CalcError("division by zero")
            value = value * right if operator == "*" else value / right
        return value

    def power(self):
        value = self.unary()
        if self.peek() == ("op", "^"):
            self.take()
            self.used = True
            value = value ** self.power()
        return value

    def unary(self):
        if self.peek() == ("op", "-"):
            self.take()
            return -self.unary()
        if self.peek() == ("op", "+"):
            self.take()
            return self.unary()
        value = self.atom()
        if self.peek() == ("op", "%"):
            self.take()
            self.used = True
            value = value / 100
        return value

    def atom(self):
        kind, value = self.take()
        if kind == "num":
            return value
        if kind == "op" and value == "(":
            inner = self.expression()
            self.take(")")
            return inner
        if kind == "name":
            if value in FUNCTIONS:
                self.used = True
                argument = self.atom() if self.peek() != ("op", "(") else self.atom()
                try:
                    return FUNCTIONS[value](argument)
                except (ValueError, OverflowError) as error:
                    raise CalcError(str(error)) from error
            if value in self.variables:
                self.used = True
                return self.variables[value]
            if value in CONSTANTS:
                self.used = True
                return CONSTANTS[value]
        raise CalcError(f"unknown {value}")


def evaluate(text, variables=None):
    """The value of an expression, or None. Plain numbers count only with variables=…
    (for definitions); results need at least one operator, function or variable."""
    parser = Parser(tokenize(text), variables or {})
    value = parser.parse()
    if isinstance(value, complex) or math.isnan(value) or math.isinf(value):
        raise CalcError("no real number")
    return value, parser.used


def variables_of(lines):
    """Variables defined by lines like "x = 64" or "Miete = 450 + 120" (in order)."""
    variables = {}
    for line in lines:
        match = ASSIGNMENT.match(line)
        if not match or match.group(2).endswith("="):
            continue
        try:
            variables[match.group(1)] = evaluate(match.group(2), variables)[0]
        except (CalcError, ZeroDivisionError, OverflowError):
            continue
    return variables


def result_for(line, earlier_lines=()):
    """For a line ending in "=": the formatted result of the longest calculation before it
    ("Summe 450 + 120 =" → "570"), or None. Assignments ("x = 3 =") are left alone."""
    if not line.rstrip().endswith("="):
        return None
    before = line.rstrip()[:-1]
    if "=" in before or not before.strip():
        return None
    variables = variables_of(earlier_lines)
    # Try from the left: the longest tail that is a complete calculation wins.
    starts = [0] + [index + 1 for index, char in enumerate(before) if char == " "]
    for start in starts:
        candidate = before[start:].strip()
        if not candidate:
            continue
        try:
            value, used = evaluate(candidate, variables)
        except (CalcError, ZeroDivisionError, OverflowError):
            continue
        if used:
            return format_number(value)
    return None


def format_number(value):
    """German style: decimal comma, at most 10 significant digits, no trailing zeros."""
    if abs(value) >= 1e15 or (value != 0 and abs(value) < 1e-9):
        return f"{value:.6g}".replace(".", ",")
    text = f"{value:.10g}" if abs(value) >= 1 else f"{round(value, 12):.10f}".rstrip("0")
    if "e" in text:
        text = f"{value:.10f}"
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return "0" if text in ("-0", "") else text.replace(".", ",")
