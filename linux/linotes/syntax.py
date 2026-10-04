"""Code with syntax colors (a Profi-Funktion): a small line-by-line tokenizer instead of a large
library – keywords, strings, comments and numbers for a few languages. Only for display, never
stored. The same rules are in Android's Syntax.kt (SyntaxTest has the same cases)."""

import re

LANGUAGES = {
    "python": "Python", "kotlin": "Kotlin", "shell": "Shell", "json": "JSON",
}
KEYWORDS = {
    "python": {"False", "None", "True", "and", "as", "assert", "async", "await", "break", "class", "continue", "def", "del",
               "elif", "else", "except", "finally", "for", "from", "global", "if", "import", "in", "is", "lambda",
               "nonlocal", "not", "or", "pass", "raise", "return", "try", "while", "with", "yield", "self"},
    "kotlin": {"as", "break", "class", "continue", "do", "else", "false", "for", "fun", "if", "in", "interface", "is",
               "null", "object", "package", "return", "super", "this", "throw", "true", "try", "typealias", "val", "var",
               "when", "while", "import", "private", "override", "data", "enum", "sealed", "companion", "const",
               "lateinit", "by", "catch", "finally", "internal", "open", "suspend"},
    "shell": {"if", "then", "else", "elif", "fi", "for", "while", "until", "do", "done", "case", "esac", "in",
              "function", "return", "export", "local", "echo", "cd", "exit", "set", "unset", "read", "source", "sudo"},
    "json": {"true", "false", "null"},
}
COMMENT = {"python": "#", "shell": "#", "kotlin": "//", "json": None}
TOKEN = re.compile(r'''(?P<string>"(?:\\.|[^"\\])*"?|'(?:\\.|[^'\\])*'?)|(?P<number>\b\d+(?:\.\d+)?\b)|(?P<word>[A-Za-z_$][\w$]*)''')


def tokens(line, lang):
    """(start, end, kind) with kind "keyword", "string", "comment" or "number"."""
    if lang not in LANGUAGES:
        return []
    marker = COMMENT[lang]
    result = []
    position = 0
    while position < len(line):
        if lang == "shell" and line[position] == "$":
            position += 2  # "$#", "$1", "$?" are variables, not a comment or a number
            continue
        # In shell scripts "#" starts a comment only at the start of a word.
        word_start = lang != "shell" or position == 0 or line[position - 1].isspace()
        if marker and word_start and line.startswith(marker, position):
            result.append((position, len(line), "comment"))
            break
        match = TOKEN.match(line, position)
        if match is None:
            position += 1
            continue
        kind = match.lastgroup
        if kind == "word":
            if match.group() in KEYWORDS[lang]:
                result.append((match.start(), match.end(), "keyword"))
        else:
            result.append((match.start(), match.end(), kind))
        position = match.end()
    return result
