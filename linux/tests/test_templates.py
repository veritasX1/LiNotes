"""Templates: placeholders and shipped templates. Android's TemplateTest has the same cases."""

import datetime
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from linotes import model  # noqa: E402

NOW = datetime.datetime(2026, 10, 4, 9, 5)  # a Sunday


def main():
    filled = model.fill_template([{"t": "title", "x": "Besprechung {{Datum}}"},
                                  {"t": "body", "x": "{{Wochentag}} um {{Uhrzeit}} – wichtig", "s": [[31, 38, "b"]]},
                                  {"t": "body", "x": "{{Unbekannt}} bleibt"}], NOW)
    assert filled[0]["x"] == "Besprechung 04.10.2026"
    assert filled[1]["x"] == "Sonntag um 09:05 – wichtig"
    assert filled[1]["s"] == [[19, 26, "b"]] and filled[1]["x"][19:26] == "wichtig"   # the bold word moved along
    assert filled[2]["x"] == "{{Unbekannt}} bleibt"
    assert [key for key, _name, _blocks in model.BUILTIN_TEMPLATES] == ["besprechung", "protokoll", "reise", "tagebuch"]
    diary = model.fill_template(dict((k, b) for k, _n, b in model.BUILTIN_TEMPLATES)["tagebuch"], NOW)
    assert diary[0] == {"t": "title", "x": "Sonntag, 04.10.2026"}
    original = model.BUILTIN_TEMPLATES[0][2][0]["x"]
    assert original == "Besprechung {{Datum}}"  # the template itself stays unchanged
    print("ok – Vorlagen")


if __name__ == "__main__":
    main()
