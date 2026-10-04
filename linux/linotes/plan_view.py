"""Plans in the main window: a grid (timetable, shifts, cleaning rota, rooms) or a timeline
(project plan). The data model is plans.py; every change is saved after a short pause."""

import datetime
import time

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("PangoCairo", "1.0")
from gi.repository import Gdk, GLib, Gtk, Pango, PangoCairo

from . import plans
from . import smoothscroll
from .dialogs import ask_text

COLUMN_TYPES = [("free", "Freie Spalten"), ("weekdays", "Wochentage"), ("dates", "Datum (Tage)"), ("weeks", "Wochen")]


def css_color(name, alpha=1.0):
    r, g, b = plans.COLORS.get(name, plans.COLORS["grey"])
    return f"rgba({int(r * 255)}, {int(g * 255)}, {int(b * 255)}, {alpha})"


_provider = None


def install_css():
    """One CSS class per cell color (plan-k-blue …)."""
    global _provider
    if _provider is not None:
        return
    _provider = Gtk.CssProvider()
    _provider.load_from_string("\n".join(
        f".plan-k-{name} {{ background-color: {css_color(name, 0.35)}; }}" for name in plans.COLORS))
    Gtk.StyleContext.add_provider_for_display(Gdk.Display.get_default(), _provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)


class PlanView(Gtk.Box):

    def __init__(self, window):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        install_css()
        self.window = window
        self.sync = window.sync
        self.plan_id = None
        self.data = {}
        self.saved = None
        self.save_source = None

        bar = Gtk.Box(spacing=6, margin_start=16, margin_end=16, margin_top=12, margin_bottom=8)
        self.title = Gtk.Label(xalign=0, hexpand=True, ellipsize=Pango.EllipsizeMode.END, css_classes=["title-2"])
        bar.append(self.title)
        self.tools = Gtk.Box(spacing=6)
        bar.append(self.tools)
        self.append(bar)
        self.scroller = Gtk.ScrolledWindow(vexpand=True, hexpand=True)
        smoothscroll.enable(self.scroller)
        self.append(self.scroller)

    # --- loading and saving ---

    def show(self, plan_id):
        self.flush()
        self.plan_id = plan_id
        obj = self.sync.get(plan_id)
        self.data = dict(obj["data"]) if obj else {}
        self.saved = dict(self.data)
        self.build()

    def refresh(self):
        """Changed elsewhere: take it unless I am editing right now."""
        obj = self.sync.get(self.plan_id) if self.plan_id else None
        if obj is None or self.save_source is not None:
            return
        if obj["data"] != self.saved:
            focus = self.get_root().get_focus() if self.get_root() else None
            if focus is not None and focus.is_ancestor(self):
                return  # do not pull the cell away under the cursor; the next change brings it
            self.data = dict(obj["data"])
            self.saved = dict(self.data)
            self.build()

    def change(self, data, rebuild=False):
        self.data = data
        if self.save_source is not None:
            GLib.source_remove(self.save_source)
        self.save_source = GLib.timeout_add(600, self.flush)
        if rebuild:
            self.build()

    def flush(self):
        if self.save_source is not None:
            GLib.source_remove(self.save_source)
            self.save_source = None
        obj = self.sync.get(self.plan_id) if self.plan_id else None
        if obj is not None and self.data != self.saved:
            self.sync.put("plan", self.data, obj.get("share"), self.plan_id, notify=False)
            self.saved = dict(self.data)
        return False

    # --- building ---

    def clear_tools(self):
        while (child := self.tools.get_first_child()) is not None:
            self.tools.remove(child)

    def tool(self, label, callback, tooltip=None):
        button = Gtk.Button(label=label, css_classes=["flat"], tooltip_text=tooltip)
        button.connect("clicked", lambda _button: callback())
        self.tools.append(button)
        return button

    def build(self):
        self.title.set_label(self.data.get("name") or "Plan")
        self.clear_tools()
        if self.data.get("mode") == "timeline":
            self.build_timeline()
        else:
            self.build_grid()
        self.tool("PDF …", self.export, "Als PDF speichern oder drucken (zum Aushängen)")

    # --- grid ---

    def build_grid(self):
        data = self.data
        kind = (data.get("cols") or {}).get("type", "free")
        columns = Gtk.DropDown.new_from_strings([label for _key, label in COLUMN_TYPES])
        columns.set_selected([key for key, _label in COLUMN_TYPES].index(kind))
        columns.set_tooltip_text("Was die Spalten sind")
        columns.connect("notify::selected", lambda dropdown, _p: self.set_column_type(COLUMN_TYPES[dropdown.get_selected()][0]))
        self.tools.append(columns)
        self.tool("+ Zeile", lambda: self.change(plans.insert_row(self.data, len(self.data.get("rows") or [])), True))
        self.tool("+ Spalte", lambda: self.change(plans.insert_column(self.data, plans.column_count(self.data)), True))
        if kind == "weeks":
            self.tool("Rotation …", self.edit_rotation, "Namen, die Woche für Woche weiterrücken (Putzplan, Dienste)")

        grid = Gtk.Grid(css_classes=["plan-grid"], margin_start=16, margin_end=16, margin_bottom=16,
                        halign=Gtk.Align.START, valign=Gtk.Align.START)
        labels = plans.column_labels(data)
        today = plans.today_column(data)
        corner = Gtk.Label(label="", css_classes=["plan-head"])
        grid.attach(corner, 0, 0, 1, 1)
        for c, label in enumerate(labels):
            if kind == "free":
                head = Gtk.Entry(text=label, has_frame=False, width_chars=12, css_classes=["plan-head"], placeholder_text="Spalte")
                head.connect("changed", lambda entry, c=c: self.set_column_label(c, entry.get_text()))
            else:
                head = Gtk.Label(label=label, css_classes=["plan-head"], xalign=0)
            if c == today:
                head.add_css_class("plan-today")
            self.cell_menu(head, None, c)
            grid.attach(head, c + 1, 0, 1, 1)
        rows = data.get("rows") or [""]
        grid_cells = plans.cells(data)
        for r, label in enumerate(rows):
            name = Gtk.Entry(text=label, has_frame=False, width_chars=12, css_classes=["plan-row"], placeholder_text="Zeile")
            name.connect("changed", lambda entry, r=r: self.set_row_label(r, entry.get_text()))
            self.cell_menu(name, r, None)
            grid.attach(name, 0, r + 1, 1, 1)
            for c in range(len(labels)):
                cell = grid_cells[r][c] or {}
                entry = Gtk.Entry(text=cell.get("x", ""), has_frame=False, width_chars=12, css_classes=["plan-cell"])
                rotated = plans.rotation_name(data, r, c)
                if rotated:
                    entry.set_placeholder_text(rotated)  # by rotation; typing overrides it for this week
                if cell.get("k"):
                    entry.add_css_class("plan-k-" + cell["k"])
                if c == today:
                    entry.add_css_class("plan-today")
                entry.connect("changed", lambda e, r=r, c=c: self.change(plans.set_cell(self.data, r, c, e.get_text())))
                self.cell_menu(entry, r, c)
                grid.attach(entry, c + 1, r + 1, 1, 1)
        self.scroller.set_child(grid)

    def set_column_type(self, kind):
        cols = dict(self.data.get("cols") or {})
        if cols.get("type", "free") == kind:
            return
        count = plans.column_count(self.data)
        cols = {"type": kind}
        if kind == "free":
            cols["labels"] = plans.column_labels(self.data)
        elif kind == "weekdays":
            cols["count"] = 7 if count > 5 else 5
        elif kind == "dates":
            cols.update(count=max(count, 7), start=datetime.date.today().isoformat())
        else:
            cols["count"] = max(count, 4)
        data = {**self.data, "cols": cols}
        data["cells"] = plans.cells(data)
        self.change(data, True)

    def set_column_label(self, column, text):
        labels = plans.column_labels(self.data)
        labels[column] = text
        self.change({**self.data, "cols": {**(self.data.get("cols") or {}), "labels": labels}})

    def set_row_label(self, row, text):
        rows = list(self.data.get("rows") or [""])
        rows[row] = text
        self.change({**self.data, "rows": rows})

    def cell_menu(self, widget, row, column):
        """Right-click: color (cells), insert or remove rows and columns."""
        click = Gtk.GestureClick(button=Gdk.BUTTON_SECONDARY)

        def pressed(gesture, _n, x, y):
            gesture.set_state(Gtk.EventSequenceState.CLAIMED)
            popover = Gtk.Popover()
            box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)

            def item(label, action, enabled=True):
                button = Gtk.Button(label=label, css_classes=["flat"], sensitive=enabled)
                button.get_child().set_xalign(0)
                button.connect("clicked", lambda _b: (popover.popdown(), GLib.idle_add(lambda: action() and False)))
                box.append(button)

            if row is not None and column is not None:
                colors = Gtk.Box(spacing=4, margin_start=6, margin_end=6, margin_top=4, margin_bottom=4)
                for name, title in [("", "Keine")] + list(plans.COLOR_NAMES.items()):
                    swatch = Gtk.Button(tooltip_text=title, css_classes=["circular", "plan-swatch"] + ([f"plan-k-{name}"] if name else []))
                    swatch.set_size_request(24, 24)
                    swatch.connect("clicked", lambda _b, name=name: (popover.popdown(),
                                                                       self.change(plans.set_cell(self.data, row, column, color=name), True)))
                    colors.append(swatch)
                box.append(colors)
                box.append(Gtk.Separator())
            rows = len(self.data.get("rows") or [""])
            if row is not None:
                item("Zeile darüber einfügen", lambda: self.change(plans.insert_row(self.data, row), True))
                item("Zeile darunter einfügen", lambda: self.change(plans.insert_row(self.data, row + 1), True))
                item("Zeile löschen", lambda: self.change(plans.remove_row(self.data, row), True), rows > 1)
                item("Zeile nach oben", lambda: self.change(plans.move_row(self.data, row, row - 1), True), row > 0)
                item("Zeile nach unten", lambda: self.change(plans.move_row(self.data, row, row + 1), True), row < rows - 1)
            if column is not None:
                free = (self.data.get("cols") or {}).get("type", "free") == "free"
                item("Spalte links einfügen" if free else "Spalte anhängen",
                     lambda: self.change(plans.insert_column(self.data, column), True))
                if free:
                    item("Spalte rechts einfügen", lambda: self.change(plans.insert_column(self.data, column + 1), True))
                item("Spalte löschen" if free else "Letzte Spalte entfernen",
                     lambda: self.change(plans.remove_column(self.data, column), True), plans.column_count(self.data) > 1)
            popover.set_child(box)
            popover.set_parent(widget)
            rect = Gdk.Rectangle()
            rect.x, rect.y, rect.width, rect.height = int(x), int(y), 1, 1
            popover.set_pointing_to(rect)
            popover.connect("closed", lambda p: GLib.idle_add(lambda: p.unparent() and False))
            popover.popup()
        click.connect("pressed", pressed)
        widget.add_controller(click)

    def edit_rotation(self):
        rot = self.data.get("rot") or {}
        people = ", ".join(rot.get("people") or [])

        def done(text, _choice):
            names = [name.strip() for name in text.replace("\n", ",").split(",") if name.strip()]
            start = rot.get("start") or plans.monday(datetime.date.today()).isoformat()
            data = {**self.data, "rot": {"people": names, "start": start}} if names else \
                {key: value for key, value in self.data.items() if key != "rot"}
            self.change(data, True)
        ask_text(self.window, "Rotation", done, text=people, placeholder="z. B. Olaf, Anna, Ben", action="Übernehmen",
                 body="Die Namen rücken jede Woche eine Zeile weiter. Ein eigener Eintrag in einer Zelle gilt nur dort.")

    # --- timeline ---

    def build_timeline(self):
        self.tool("+ Aufgabe", lambda: self.add_task(False))
        self.tool("+ Meilenstein", lambda: self.add_task(True))
        self.tool("Nach Datum sortieren", lambda: self.change(plans.sort_tasks(self.data), True),
                  "Alle Aufgaben und Meilensteine nach ihrem Beginn ordnen")
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12, margin_start=16, margin_end=16, margin_bottom=16)
        chart = Gtk.DrawingArea(content_height=max(120, 34 * len(self.data.get("tasks") or []) + 50), hexpand=True)
        chart.set_draw_func(self.draw_timeline)
        self.chart = chart
        box.append(chart)
        tasks = Gtk.Grid(column_spacing=8, row_spacing=4)
        for col, title in enumerate(["", "Aufgabe", "Von", "Bis", "Farbe", ""]):
            tasks.attach(Gtk.Label(label=title, xalign=0, css_classes=["dim-label", "caption"]), col, 0, 1, 1)
        all_tasks = self.data.get("tasks") or []
        line = 1
        for index, task in enumerate(all_tasks):
            # Order one by one (the whole plan: "Nach Datum sortieren").
            arrows = Gtk.Box(css_classes=["linked"], valign=Gtk.Align.CENTER)
            for icon, tooltip, to in (("go-up-symbolic", "Nach oben", index - 1), ("go-down-symbolic", "Nach unten", index + 1)):
                arrow = Gtk.Button(icon_name=icon, tooltip_text=tooltip, css_classes=["flat"], sensitive=0 <= to < len(all_tasks))
                arrow.connect("clicked", lambda _b, i=index, to=to: self.change(plans.move_task(self.data, i, to), True))
                arrows.append(arrow)
            tasks.attach(arrows, 0, line, 1, 1)
            name = Gtk.Entry(text=task.get("x", ""), width_chars=24, placeholder_text="Meilenstein" if task.get("m") else "Aufgabe")
            name.connect("changed", lambda e, i=index: self.set_task(i, x=e.get_text()))
            tasks.attach(name, 1, line, 1, 1)
            for col, key in ((2, "from"), (3, "to")):
                if key == "to" and task.get("m"):
                    tasks.attach(Gtk.Label(label="◆ Meilenstein", xalign=0, css_classes=["dim-label"]), col, line, 1, 1)
                    continue
                value = plans.day(task.get(key))
                date = Gtk.Entry(text=value.strftime("%d.%m.%Y") if value else "", width_chars=10, placeholder_text="TT.MM.JJJJ",
                                 tooltip_text="Mit Enter übernehmen")
                date.shown = date.get_text()  # only a changed field counts (also after reordering)
                # Taken on Enter or when leaving the field – not while typing, or every half-typed
                # date would count as a milestone shift.
                date.connect("activate", lambda e, i=index, key=key: self.set_task_date(i, key, e))
                focus = Gtk.EventControllerFocus()
                focus.connect("leave", lambda _c, e=date, i=index, key=key: self.set_task_date(i, key, e))
                date.add_controller(focus)
                tasks.attach(date, col, line, 1, 1)
            color = Gtk.DropDown.new_from_strings(list(plans.COLOR_NAMES.values()))
            names = list(plans.COLOR_NAMES)
            color.set_selected(names.index(task.get("k")) if task.get("k") in names else names.index("blue"))
            color.connect("notify::selected", lambda d, _p, i=index: self.set_task(i, k=names[d.get_selected()]))
            tasks.attach(color, 4, line, 1, 1)
            remove = Gtk.Button(icon_name="user-trash-symbolic", css_classes=["flat"], tooltip_text="Entfernen")
            remove.connect("clicked", lambda _b, i=index: self.remove_task(i))
            tasks.attach(remove, 5, line, 1, 1)
            line += 1
            if task.get("moved"):
                days = [entry.get("was") for entry in task["moved"]] + [task.get("from")]
                trail = " → ".join(d.strftime("%d.%m.%Y") for d in map(plans.day, days) if d)
                history = Gtk.Label(label=f"verschoben: {trail}", xalign=0, css_classes=["dim-label", "caption"])
                tasks.attach(history, 1, line, 4, 1)
                line += 1
        box.append(tasks)
        self.scroller.set_child(box)

    def tasks(self):
        return [dict(task) for task in self.data.get("tasks") or []]

    def set_task(self, index, **fields):
        tasks = self.tasks()
        tasks[index].update(fields)
        self.change({**self.data, "tasks": tasks})
        self.chart.queue_draw()

    def set_task_date(self, index, key, entry):
        if index >= len(self.tasks()) or entry.get_text().strip() == entry.shown:
            return
        try:
            value = datetime.datetime.strptime(entry.get_text().strip(), "%d.%m.%Y").date()
            if value.year < 1000:
                raise ValueError("Jahr vierstellig")
        except ValueError:
            entry.add_css_class("error")
            return
        entry.remove_css_class("error")
        entry.shown = entry.get_text().strip()
        if self.tasks()[index].get(key) == value.isoformat():
            return
        moved = self.tasks()[index].get("m")
        self.change(plans.set_task_day(self.data, index, key, value.isoformat(), by=self.sync.user_id, at=time.time()))
        if moved:
            GLib.idle_add(lambda: self.build() and False)  # show the "verschoben" line
        else:
            self.chart.queue_draw()

    def add_task(self, milestone):
        today = datetime.date.today()
        task = {"x": "", "from": today.isoformat(), "to": (today if milestone else today + datetime.timedelta(days=4)).isoformat(),
                "k": "pink" if milestone else "blue"}
        if milestone:
            task["m"] = True
        self.change({**self.data, "tasks": self.tasks() + [task]}, True)

    def remove_task(self, index):
        tasks = self.tasks()
        del tasks[index]
        self.change({**self.data, "tasks": tasks}, True)

    def draw_timeline(self, area, cr, width, height):
        first, last = plans.timeline_range(self.data)
        days = (last - first).days + 1
        label_width = 150
        scale = max(4.0, (width - label_width - 8) / days)
        fg = area.get_color()
        top = 28
        # weeks: a line and "KW n" every Monday
        layout = area.create_pango_layout("")
        for i in range(0, days, 7):
            x = label_width + i * scale
            cr.set_source_rgba(fg.red, fg.green, fg.blue, 0.15)
            cr.rectangle(x, top - 6, 1, height - top)
            cr.fill()
            d = first + datetime.timedelta(days=i)
            layout.set_text(f"KW {d.isocalendar()[1]} · {d.strftime('%d.%m.')}", -1)
            cr.set_source_rgba(fg.red, fg.green, fg.blue, 0.6)
            cr.move_to(x + 4, 4)
            PangoCairo.show_layout(cr, layout)
        today = datetime.date.today()
        if first <= today <= last:
            x = label_width + ((today - first).days + 0.5) * scale
            cr.set_source_rgba(0.88, 0.11, 0.14, 0.8)
            cr.rectangle(x - 1, top - 6, 2, height - top)
            cr.fill()
        for index, task in enumerate(self.data.get("tasks") or []):
            y = top + index * 34
            layout.set_text(task.get("x") or ("Meilenstein" if task.get("m") else "Aufgabe"), -1)
            layout.set_width(int((label_width - 10) * Pango.SCALE))
            layout.set_ellipsize(Pango.EllipsizeMode.END)
            cr.set_source_rgba(fg.red, fg.green, fg.blue, 0.9)
            cr.move_to(0, y + 6)
            PangoCairo.show_layout(cr, layout)
            layout.set_width(-1)
            span = plans.task_span(task)
            if span is None:
                continue
            r, g, b = plans.COLORS.get(task.get("k"), plans.COLORS["blue"])
            cr.set_source_rgb(r, g, b)
            start = label_width + (span[0] - first).days * scale
            if task.get("m"):
                cx, cy, s = start + scale / 2, y + 14, 9
                # Earlier days stay visible, faded, joined to the current one by a dashed line.
                for entry in task.get("moved") or []:
                    was = plans.day(entry.get("was"))
                    if was is None or not first <= was <= last:
                        continue
                    ox = label_width + (was - first).days * scale + scale / 2
                    cr.set_source_rgba(r, g, b, 0.3)
                    cr.move_to(ox, cy - s)
                    cr.line_to(ox + s, cy)
                    cr.line_to(ox, cy + s)
                    cr.line_to(ox - s, cy)
                    cr.close_path()
                    cr.fill()
                    cr.set_dash([3, 3])
                    cr.set_line_width(1.2)
                    cr.move_to(ox + (s if cx > ox else -s), cy)
                    cr.line_to(cx + (-s if cx > ox else s), cy)
                    cr.stroke()
                    cr.set_dash([])
                cr.set_source_rgb(r, g, b)
                cr.move_to(cx, cy - s)
                cr.line_to(cx + s, cy)
                cr.line_to(cx, cy + s)
                cr.line_to(cx - s, cy)
                cr.close_path()
                cr.fill()
            else:
                w = ((span[1] - span[0]).days + 1) * scale
                self.round_rect(cr, start + 1, y + 4, max(4, w - 2), 20, 5)
                cr.fill()

    @staticmethod
    def round_rect(cr, x, y, w, h, r):
        import math
        cr.new_sub_path()
        cr.arc(x + w - r, y + r, r, -math.pi / 2, 0)
        cr.arc(x + w - r, y + h - r, r, 0, math.pi / 2)
        cr.arc(x + r, y + h - r, r, math.pi / 2, math.pi)
        cr.arc(x + r, y + r, r, math.pi, 3 * math.pi / 2)
        cr.close_path()

    # --- PDF ---

    def export(self):
        self.flush()
        self.window.export_plan(self.plan_id)
