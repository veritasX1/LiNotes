"""Code colors: the same cases are in Android's SyntaxTest."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from linotes import syntax  # noqa: E402


def words(line, lang):
    return [(line[a:b], kind) for a, b, kind in syntax.tokens(line, lang)]


def main():
    assert words('def add(a, b=2):  # sum', "python") == [("def", "keyword"), ("2", "number"), ("# sum", "comment")]
    assert words("x = 'it\\'s' + \"#no comment\"", "python") == [("'it\\'s'", "string"), ('"#no comment"', "string")]
    assert words("val total = items.size * 3.5 // count", "kotlin") == [("val", "keyword"), ("3.5", "number"), ("// count", "comment")]
    assert words('if [ "$1" = "-v" ]; then echo $# fi', "shell") == [("if", "keyword"), ('"$1"', "string"), ('"-v"', "string"),
                                                                      ("then", "keyword"), ("echo", "keyword"), ("fi", "keyword")]
    assert words('{"name": "LiNotes", "pro": true, "n": 2}', "json") == [('"name"', "string"), ('"LiNotes"', "string"), ('"pro"', "string"),
                                                                       ("true", "keyword"), ('"n"', "string"), ("2", "number")]
    assert words('print("offen', "python") == [('"offen', "string")]   # unclosed string runs to the end
    assert words("ls a#b  # Liste", "shell") == [("# Liste", "comment")]  # "#" inside a word is no comment
    assert syntax.tokens("anything", "cobol") == [] and syntax.tokens("", "python") == []
    assert words("variable2 = 10", "python") == [("10", "number")]      # digits inside a name are no number
    print("ok – Code-Farben")


if __name__ == "__main__":
    main()
