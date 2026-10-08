"""Plans (timetable, shift plan, cleaning rota, room plan, project plan …): the data model.

A plan is one object of kind "plan" holding all of its content (encrypted like everything else).

Grid plan  {"name", "mode": "grid", "cols": {"type", "labels" | "count", "start"}, "rows": [label],
            "cells": [[cell]], "rot": {"people": [name], "start": "YYYY-MM-DD"}}
    cols.type  "free"      labels given
               "weekdays"  Mo … Fr (count 5) or Mo … So (count 7), repeats every week
               "dates"     count days from start
               "weeks"     this week and the next count-1 weeks (moves along by itself)
    cell       {"x": text, "k": color} or None
    rot        Rotation (cleaning rota): with "weeks" columns, row r in week w gets
               people[(r + weeks since rot.start) % len(people)] unless the cell has its own text.

Timeline plan  {"name", "mode": "timeline", "tasks": [{"x", "from", "to", "k", "m", "moved"}]}
    from/to    "YYYY-MM-DD" (to inclusive); "m": milestone (one day, drawn as a diamond)
    moved      milestones only: earlier days, oldest first, [{"was": "YYYY-MM-DD", "at": time, "by": user}] –
               drawn faded and listed in the plan report (Terminverschiebungen)

The same rules are in Android's Plans.kt (PlanTest has the same cases as tests/test_plans.py).
"""

import datetime
from .i18n import _

WEEKDAYS = [_("Mo"), _("Di"), _("Mi"), _("Do"), _("Fr"), _("Sa"), _("So")]
COLORS = {  # name -> RGB (0..1), the same as the highlight colors in notes
    "yellow": (1.0, 0.85, 0.24), "orange": (1.0, 0.62, 0.04), "pink": (1.0, 0.44, 0.66),
    "purple": (0.75, 0.52, 0.95), "mint": (0.3, 0.85, 0.75), "blue": (0.35, 0.7, 1.0), "grey": (0.6, 0.6, 0.63),
}
COLOR_NAMES = {"yellow": _("Gelb"), "orange": _("Orange"), "pink": _("Rosa"), "purple": _("Lila"), "mint": _("Mint"), "blue": _("Blau"),
               "grey": _("Grau")}


def day(text):
    try:
        return datetime.date.fromisoformat(text)
    except (TypeError, ValueError):
        return None


def monday(date):
    return date - datetime.timedelta(days=date.weekday())


def short_date(date):
    """05.10. · 10/5 · 05/10 – as each language writes a short date."""
    from .i18n import language
    if language() == "en":
        return f"{date.month}/{date.day}"
    if language() == "fr":
        return date.strftime("%d/%m")
    return date.strftime("%d.%m.")


def week_label(date):
    """„KW 41 · 05.10.“ · „Wk 41 · 10/5“ · „Sem. 41 · 05/10“"""
    return _("KW {week} · {date}", week=date.isocalendar()[1], date=short_date(date))


# --- grid ---------------------------------------------------------------

def column_count(plan):
    cols = plan.get("cols") or {}
    if cols.get("type", "free") == "free":
        return max(1, len(cols.get("labels") or []))
    return max(1, int(cols.get("count") or 1))


def column_labels(plan, today=None):
    today = today or datetime.date.today()
    cols = plan.get("cols") or {}
    kind = cols.get("type", "free")
    count = column_count(plan)
    if kind == "weekdays":
        return WEEKDAYS[:count]
    if kind == "dates":
        start = day(cols.get("start")) or today
        return [f"{WEEKDAYS[d.weekday()]} {short_date(d)}" for d in (start + datetime.timedelta(days=i) for i in range(count))]
    if kind == "weeks":
        first = monday(today)
        return [week_label(d) for d in (first + datetime.timedelta(weeks=i) for i in range(count))]
    labels = list(cols.get("labels") or [])
    return labels + [""] * (count - len(labels))


def today_column(plan, today=None):
    """The column for today (highlighted), or None."""
    today = today or datetime.date.today()
    cols = plan.get("cols") or {}
    kind = cols.get("type", "free")
    count = column_count(plan)
    if kind == "weekdays":
        return today.weekday() if today.weekday() < count else None
    if kind == "dates":
        start = day(cols.get("start"))
        if start is None:
            return None
        index = (today - start).days
        return index if 0 <= index < count else None
    if kind == "weeks":
        return 0
    return None


def cells(plan):
    """The cells as a rectangle rows × columns (missing ones None)."""
    rows = len(plan.get("rows") or []) or 1
    count = column_count(plan)
    grid = [list(row) for row in (plan.get("cells") or [])]
    grid = [row[:count] + [None] * (count - len(row)) for row in grid[:rows]]
    return grid + [[None] * count for _ in range(rows - len(grid))]


def rotation_name(plan, row, column, today=None):
    """Who is on duty in this cell by rotation (weeks columns only), or None."""
    rot = plan.get("rot") or {}
    people = [p for p in (rot.get("people") or []) if p.strip()]
    if not people or (plan.get("cols") or {}).get("type") != "weeks":
        return None
    today = today or datetime.date.today()
    start = monday(day(rot.get("start")) or today)
    week = (monday(today) - start).days // 7 + column
    return people[(row + week) % len(people)]


def cell_text(plan, row, column, today=None):
    cell = cells(plan)[row][column]
    if cell and cell.get("x"):
        return cell["x"]
    return rotation_name(plan, row, column, today) or ""


def set_cell(plan, row, column, text=None, color=None):
    """New plan data with one cell changed (text and/or color; "" clears)."""
    grid = cells(plan)
    cell = dict(grid[row][column] or {})
    if text is not None:
        cell["x"] = text
    if color is not None:
        cell["k"] = color
    cell = {key: value for key, value in cell.items() if value}
    grid[row][column] = cell or None
    return {**plan, "cells": grid}


def insert_row(plan, at, label=""):
    rows = list(plan.get("rows") or [])
    grid = cells(plan)
    rows.insert(at, label)
    grid.insert(at, [None] * column_count(plan))
    return {**plan, "rows": rows, "cells": grid}


def remove_row(plan, at):
    rows = list(plan.get("rows") or [])
    if len(rows) <= 1:
        return plan
    grid = cells(plan)
    del rows[at]
    del grid[at]
    return {**plan, "rows": rows, "cells": grid}


def insert_column(plan, at, label=""):
    """Free columns only (the others follow their type and count)."""
    cols = dict(plan.get("cols") or {})
    grid = cells(plan)
    if cols.get("type", "free") == "free":
        labels = column_labels(plan)
        labels.insert(at, label)
        cols["labels"] = labels
    else:
        cols["count"] = column_count(plan) + 1
        at = column_count(plan)
    for row in grid:
        row.insert(at, None)
    return {**plan, "cols": cols, "cells": grid}


def remove_column(plan, at):
    count = column_count(plan)
    if count <= 1:
        return plan
    cols = dict(plan.get("cols") or {})
    grid = cells(plan)
    if cols.get("type", "free") == "free":
        labels = column_labels(plan)
        del labels[at]
        cols["labels"] = labels
    else:
        # Weekdays, dates and weeks follow their count: the last one goes.
        cols["count"] = count - 1
        at = count - 1
    for row in grid:
        del row[at]
    return {**plan, "cols": cols, "cells": grid}


# --- timeline -----------------------------------------------------------

def timeline_range(plan, today=None):
    """First and last day to draw: all tasks, at least two weeks, starting on a Monday."""
    today = today or datetime.date.today()
    days = []
    for task in plan.get("tasks") or []:
        start, end = day(task.get("from")), day(task.get("to")) or day(task.get("from"))
        days += [d for d in (start, end) if d]
        days += [d for d in (day(entry.get("was")) for entry in task.get("moved") or []) if d]  # faded earlier days
    first = monday(min(days) if days else today)
    last = max(days) if days else today
    last = max(last, first + datetime.timedelta(days=13))
    last = monday(last) + datetime.timedelta(days=6)
    return first, last


def task_span(task):
    start = day(task.get("from"))
    end = day(task.get("to")) or start
    if start is None:
        return None
    if task.get("m"):
        end = start
    return (start, max(start, end))


# --- order and shifts ---------------------------------------------------

def moved_list(items, at, to):
    """`items` with the element at `at` moved to position `to` (clamped)."""
    items = list(items)
    if not 0 <= at < len(items):
        return items
    item = items.pop(at)
    items.insert(max(0, min(to, len(items))), item)
    return items


def move_row(plan, at, to):
    """A grid row with its cells to another place."""
    rows = list(plan.get("rows") or [])
    if not 0 <= at < len(rows):
        return plan
    return {**plan, "rows": moved_list(rows, at, to), "cells": moved_list(cells(plan), at, to)}


def move_task(plan, at, to):
    return {**plan, "tasks": moved_list(plan.get("tasks") or [], at, to)}


def sort_tasks(plan):
    """All tasks by start day (tasks without a day at the end); equal days keep their order."""
    far = datetime.date.max
    return {**plan, "tasks": sorted(plan.get("tasks") or [], key=lambda task: day(task.get("from")) or far)}


def set_task_day(plan, index, key, value, by=None, at=None):
    """Set "from" or "to" of a task (ISO day). A milestone keeps the day it had in "moved",
    so the old date stays visible (faded) and the report lists the shift."""
    tasks = [dict(task) for task in plan.get("tasks") or []]
    if not 0 <= index < len(tasks):
        return plan
    task = tasks[index]
    if task.get(key) == value:
        return plan
    if task.get("m"):
        if task.get("from"):
            task["moved"] = list(task.get("moved") or []) + [{"was": task["from"], "at": at, "by": by}]
        task["from"] = task["to"] = value
    else:
        task[key] = value
    return {**plan, "tasks": tasks}


def shifts(plan):
    """Every milestone shift, oldest first per milestone: (name, was, now, at, by)."""
    result = []
    for task in plan.get("tasks") or []:
        moved = task.get("moved") or []
        days = [entry.get("was") for entry in moved] + [task.get("from")]
        for entry, new in zip(moved, days[1:]):
            result.append((task.get("x") or _("Meilenstein"), entry.get("was"), new, entry.get("at"), entry.get("by")))
    return result


# --- templates ----------------------------------------------------------

def template(key, today=None):
    today = today or datetime.date.today()
    if key == "stundenplan":
        return {"mode": "grid", "cols": {"type": "weekdays", "count": 5},
                "rows": ["1. 8:00", "2. 8:50", "3. 9:55", "4. 10:45", "5. 11:50", "6. 12:40"]}
    if key == "schichtplan":
        return {"mode": "grid", "cols": {"type": "weekdays", "count": 7}, "rows": [_("Person 1"), _("Person 2"), _("Person 3")],
                "cells": [[{"x": _("Früh"), "k": "yellow"}, {"x": _("Früh"), "k": "yellow"}, {"x": _("Spät"), "k": "blue"},
                           {"x": _("Spät"), "k": "blue"}, {"x": _("Nacht"), "k": "purple"}, None, None]]}
    if key == "putzplan":
        return {"mode": "grid", "cols": {"type": "weeks", "count": 4}, "rows": [_("Bad"), _("Küche"), _("Staubsaugen"), _("Müll")],
                "rot": {"people": [_("Person 1"), _("Person 2")], "start": monday(today).isoformat()}}
    if key == "raumplan":
        return {"mode": "grid", "cols": {"type": "free", "labels": [_("Saal 1"), _("Saal 2"), _("Saal 3")]},
                "rows": [f"{hour:02d}:00" for hour in range(7, 17)]}
    if key == "projektplan":
        start = monday(today)
        def at(days):
            return (start + datetime.timedelta(days=days)).isoformat()
        return {"mode": "timeline", "tasks": [
            {"x": _("Konzept"), "from": at(0), "to": at(4), "k": "blue"},
            {"x": _("Umsetzung"), "from": at(7), "to": at(18), "k": "orange"},
            {"x": _("Test"), "from": at(14), "to": at(20), "k": "mint"},
            {"x": _("Abnahme"), "from": at(21), "to": at(21), "k": "pink", "m": True}]}
    return {"mode": "grid", "cols": {"type": "free", "labels": ["", "", ""]}, "rows": ["", "", ""]}


TEMPLATES = [("leer", _("Leerer Plan"), _("Raster mit freien Zeilen und Spalten")),
             ("stundenplan", _("Stundenplan"), _("Mo–Fr × Schulstunden")),
             ("schichtplan", _("Schichtplan"), _("Mo–So × Personen, Schichten farbig")),
             ("putzplan", _("Putzplan"), _("Aufgaben × Wochen, Namen rotieren wöchentlich")),
             ("raumplan", _("OP- / Raumplan"), _("Uhrzeit × Säle oder Räume")),
             ("projektplan", _("Projektplan"), _("Zeitstrahl mit Aufgaben und Meilensteinen"))]


def text_rows(plan, today=None):
    """The plan as rows of text (PDF, search, plain text)."""
    if plan.get("mode") == "timeline":
        lines = [[_("Aufgabe"), _("Von"), _("Bis")]]
        for task in plan.get("tasks") or []:
            span = task_span(task)
            if span:
                lines.append([task.get("x", "") + (" ◆" if task.get("m") else ""), span[0].strftime("%d.%m.%Y"),
                              span[1].strftime("%d.%m.%Y")])
        return lines
    rows = plan.get("rows") or [""]
    lines = [[""] + column_labels(plan, today)]
    for r, label in enumerate(rows):
        lines.append([label] + [cell_text(plan, r, c, today) for c in range(column_count(plan))])
    return lines
