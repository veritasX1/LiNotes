"""Plans: columns, today, rotation, editing, timeline. The same cases are in Android's PlanTest."""

import datetime
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from linotes import plans  # noqa: E402

TODAY = datetime.date(2026, 10, 7)  # a Wednesday, KW 41


def main():
    week = {"cols": {"type": "weekdays", "count": 5}, "rows": ["1", "2"]}
    assert plans.column_labels(week, TODAY) == ["Mo", "Di", "Mi", "Do", "Fr"]
    assert plans.today_column(week, TODAY) == 2
    assert plans.today_column(week, datetime.date(2026, 10, 11)) is None  # Sunday, Mo–Fr plan

    dates = {"cols": {"type": "dates", "count": 3, "start": "2026-10-06"}, "rows": ["a"]}
    assert plans.column_labels(dates, TODAY) == ["Di 06.10.", "Mi 07.10.", "Do 08.10."]
    assert plans.today_column(dates, TODAY) == 1

    weeks = {"cols": {"type": "weeks", "count": 3}, "rows": ["Bad", "Küche", "Müll"],
             "rot": {"people": ["Olaf", "Anna"], "start": "2026-09-28"}}
    assert plans.column_labels(weeks, TODAY) == ["KW 41 · 05.10.", "KW 42 · 12.10.", "KW 43 · 19.10."]
    # rotation started the week before: week index 1 now
    assert [plans.cell_text(weeks, r, 0, TODAY) for r in range(3)] == ["Anna", "Olaf", "Anna"]
    assert [plans.cell_text(weeks, 0, c, TODAY) for c in range(3)] == ["Anna", "Olaf", "Anna"]
    changed = plans.set_cell(weeks, 0, 0, "Gast")
    assert plans.cell_text(changed, 0, 0, TODAY) == "Gast" and plans.cell_text(changed, 1, 0, TODAY) == "Olaf"

    free = {"cols": {"type": "free", "labels": ["A", "B"]}, "rows": ["x", "y"]}
    free = plans.set_cell(free, 1, 1, "z", "blue")
    assert plans.cells(free) == [[None, None], [None, {"x": "z", "k": "blue"}]]
    free = plans.insert_column(free, 1, "neu")
    assert plans.column_labels(free) == ["A", "neu", "B"] and plans.cells(free)[1] == [None, None, {"x": "z", "k": "blue"}]
    free = plans.insert_row(free, 0, "oben")
    assert free["rows"] == ["oben", "x", "y"] and plans.cells(free)[2][2] == {"x": "z", "k": "blue"}
    free = plans.remove_column(plans.remove_row(free, 0), 1)
    assert plans.cells(free) == [[None, None], [None, {"x": "z", "k": "blue"}]]
    assert plans.set_cell(free, 1, 1, "", "")["cells"][1][1] is None

    timeline = plans.template("projektplan", TODAY)
    first, last = plans.timeline_range(timeline, TODAY)
    assert first == datetime.date(2026, 10, 5) and last == datetime.date(2026, 11, 1)
    assert plans.task_span(timeline["tasks"][3]) == (datetime.date(2026, 10, 26), datetime.date(2026, 10, 26))
    assert plans.timeline_range({"tasks": []}, TODAY) == (datetime.date(2026, 10, 5), datetime.date(2026, 10, 18))
    assert plans.text_rows(week, TODAY)[0] == ["", "Mo", "Di", "Mi", "Do", "Fr"]
    for key, _name, _hint in plans.TEMPLATES:
        assert plans.template(key, TODAY)["mode"] in ("grid", "timeline")
    print("ok – Pläne")


if __name__ == "__main__":
    main()
