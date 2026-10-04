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

    # order: grid rows with their cells, tasks one by one and by date
    moved = plans.move_row({"rows": ["a", "b", "c"], "cols": {"type": "free", "labels": ["x"]},
                            "cells": [[{"x": "1"}], [None], [{"x": "3"}]]}, 2, 0)
    assert moved["rows"] == ["c", "a", "b"] and plans.cells(moved) == [[{"x": "3"}], [{"x": "1"}], [None]]
    assert plans.move_row(moved, 5, 0) == moved
    assert [t["x"] for t in plans.move_task(timeline, 0, 9)["tasks"]] == ["Umsetzung", "Test", "Abnahme", "Konzept"]
    mixed = {"tasks": [{"x": "c", "from": "2026-10-20"}, {"x": "ohne"}, {"x": "a", "from": "2026-10-01"},
                       {"x": "b", "from": "2026-10-20"}]}
    assert [t["x"] for t in plans.sort_tasks(mixed)["tasks"]] == ["a", "c", "b", "ohne"]

    # a milestone remembers where it was; ordinary tasks just change
    shifted = plans.set_task_day(timeline, 3, "from", "2026-11-02", by=1, at=100.0)
    shifted = plans.set_task_day(shifted, 3, "from", "2026-11-09", by=3, at=200.0)
    stone = shifted["tasks"][3]
    assert stone["from"] == stone["to"] == "2026-11-09"
    assert stone["moved"] == [{"was": "2026-10-26", "at": 100.0, "by": 1}, {"was": "2026-11-02", "at": 200.0, "by": 3}]
    assert plans.set_task_day(shifted, 3, "from", "2026-11-09", by=1, at=300.0) == shifted  # same day: no shift
    assert plans.shifts(shifted) == [("Abnahme", "2026-10-26", "2026-11-02", 100.0, 1),
                                     ("Abnahme", "2026-11-02", "2026-11-09", 200.0, 3)]
    task = plans.set_task_day(timeline, 0, "to", "2026-10-12", by=1, at=1.0)["tasks"][0]
    assert task["to"] == "2026-10-12" and "moved" not in task
    assert plans.timeline_range(shifted, TODAY)[1] >= datetime.date(2026, 11, 9)
    early = plans.set_task_day(timeline, 0, "from", "2026-10-06", by=1, at=1.0)  # task: no history
    back = plans.set_task_day({"tasks": [{"x": "M", "from": "2026-09-14", "to": "2026-09-14", "m": True}]}, 0, "from",
                              "2026-10-12", by=1, at=1.0)
    assert plans.timeline_range(back, TODAY)[0] == datetime.date(2026, 9, 14)  # the faded old day is drawn too
    assert "moved" not in early["tasks"][0]
    print("ok – Pläne")


if __name__ == "__main__":
    main()
