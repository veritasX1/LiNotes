"""Board report as PDF or CSV – a simple list for ordinary boards, a
traceability matrix plus card details for development projects."""

import csv
import datetime

import cairo
import gi

gi.require_version("Pango", "1.0")
gi.require_version("PangoCairo", "1.0")

from gi.repository import Pango, PangoCairo

from . import model

A4 = (595.0, 842.0)  # points
MARGIN = 48.0
ACCENT = (0.72, 0.49, 0.0)
GREY = (0.42, 0.42, 0.45)
LINE = (0.85, 0.85, 0.87)


def stamp(timestamp):
    return datetime.datetime.fromtimestamp(timestamp).strftime("%d.%m.%Y %H:%M") if timestamp else ""


def german_date(iso):
    try:
        return datetime.date.fromisoformat(iso).strftime("%d.%m.%Y")
    except (TypeError, ValueError):
        return ""


# --- data -------------------------------------------------------------

def build(sync, board_id):
    """Everything the report shows, independent of the output format."""
    board = sync.get(board_id)
    columns = model.board_columns(sync, board_id)
    last = columns[-1]["id"] if columns else None
    cards = [c for c in sync.objects("card") if c["data"].get("board") == board_id and not c["data"].get("archived")]
    order = {column["id"]: index for index, column in enumerate(columns)}
    cards.sort(key=lambda c: (order.get(c["data"].get("column"), 99), c["data"].get("order", 0)))
    names = {column["id"]: column["data"].get("name", "") for column in columns}
    rows = []
    for card in cards:
        data = card["data"]
        history = data.get("history") or []
        accepted = next((step for step in reversed(history) if step.get("c") == last), None) \
            if data.get("column") == last else None
        rows.append({
            "id": model.short_id(card["id"]),
            "title": data.get("title", ""),
            "notes": data.get("notes", "") or "",
            "status": names.get(data.get("column"), ""),
            "priority": dict(model.PRIORITIES).get(data.get("priority"), "") if data.get("priority") else "",
            "assignee": sync.user_name(data["assignee"]) if data.get("assignee") else "",
            "due": german_date(data.get("due")),
            "created": stamp(data.get("created")),
            "done": stamp(data.get("done_at")),
            "commits": ", ".join(c.get("h", "") for c in data.get("commits") or []),
            "commit_list": data.get("commits") or [],
            "impact": data.get("impact") or "",
            "verification": data.get("verification") or "",
            "version": data.get("version") or "",
            "accepted": f"{sync.user_name(accepted.get('by'))}, {stamp(accepted.get('at'))}" if accepted else "",
            "history": [(step.get("n", ""), stamp(step.get("at")), sync.user_name(step.get("by"))) for step in history],
        })
    return {
        "title": board["data"].get("name", "Board") if board else "Board",
        "dev": bool(board and board["data"].get("dev")),
        "generated": datetime.datetime.now().strftime("%d.%m.%Y %H:%M"),
        "columns": [(column["data"].get("name", ""), [r for r, c in zip(rows, cards) if c["data"].get("column") == column["id"]])
                    for column in columns],
        "rows": rows,
    }


# --- CSV --------------------------------------------------------------

CSV_FIELDS = [("id", "ID"), ("title", "Titel"), ("status", "Status"), ("priority", "Priorität"),
              ("assignee", "Zuständig"), ("due", "Fällig"), ("created", "Erstellt"), ("done", "Erledigt")]
CSV_DEV_FIELDS = [("commits", "Commits"), ("verification", "Verifikation"), ("impact", "Auswirkungsanalyse"),
                  ("version", "Version"), ("accepted", "Abnahme")]


def write_csv(report, path):
    fields = CSV_FIELDS + (CSV_DEV_FIELDS if report["dev"] else [])
    # Semicolons and a BOM: opens directly in a German Excel.
    with open(path, "w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.writer(handle, delimiter=";")
        writer.writerow([label for _key, label in fields])
        for row in report["rows"]:
            writer.writerow([row[key] for key, _label in fields])


# --- PDF --------------------------------------------------------------

class Pdf:
    """A tiny flowing layout on Cairo/Pango: paragraphs and tables with page breaks."""

    def __init__(self, path, header, landscape=False):
        self.width, self.height_ = (A4[1], A4[0]) if landscape else A4
        self.surface = cairo.PDFSurface(path, self.width, self.height_)
        self.cr = cairo.Context(self.surface)
        self.header = header
        self.page = 1
        self.y = MARGIN

    def layout(self, text, size=10, bold=False, width=None, color=(0, 0, 0), mono=False):
        layout = PangoCairo.create_layout(self.cr)
        font = Pango.FontDescription.from_string(("Monospace " if mono else "Ubuntu, Sans ") + str(size))
        if bold:
            font.set_weight(Pango.Weight.BOLD)
        layout.set_font_description(font)
        layout.set_width(int((width or self.width - 2 * MARGIN) * Pango.SCALE))
        layout.set_wrap(Pango.WrapMode.WORD_CHAR)
        layout.set_text(text, -1)
        return layout, color

    def height(self, layout):
        return layout[0].get_pixel_extents()[1].height

    def draw(self, layout, x, y):
        self.cr.set_source_rgb(*layout[1])
        self.cr.move_to(x, y)
        PangoCairo.show_layout(self.cr, layout[0])

    def footer(self):
        layout = self.layout(f"{self.header} · Seite {self.page}", size=7.5, color=GREY)
        self.draw(layout, MARGIN, self.height_ - MARGIN + 14)

    def need(self, height):
        if self.y + height > self.height_ - MARGIN:
            self.new_page()

    def new_page(self):
        self.footer()
        self.cr.show_page()
        self.page += 1
        self.y = MARGIN

    def text(self, text, size=10, bold=False, color=(0, 0, 0), space=4, mono=False):
        layout = self.layout(text, size, bold, color=color, mono=mono)
        self.need(self.height(layout))
        self.draw(layout, MARGIN, self.y)
        self.y += self.height(layout) + space

    def rule(self, space=8):
        self.cr.set_source_rgb(*LINE)
        self.cr.set_line_width(0.6)
        self.cr.move_to(MARGIN, self.y)
        self.cr.line_to(self.width - MARGIN, self.y)
        self.cr.stroke()
        self.y += space

    def table(self, headers, widths, rows, size=8, mono=()):
        total = self.width - 2 * MARGIN
        widths = [w * total / sum(widths) for w in widths]
        pad = 3

        def row_layouts(cells, bold=False, color=(0, 0, 0)):
            return [self.layout(str(cell), size, bold, width - 2 * pad, color, mono=index in mono and not bold)
                    for index, (cell, width) in enumerate(zip(cells, widths))]

        def draw_row(layouts, shade=False):
            height = max(self.height(layout) for layout in layouts) + 2 * pad
            if self.y + height > self.height_ - MARGIN:
                self.new_page()
                draw_row(row_layouts(headers, True, GREY), shade=True)
            if shade:
                self.cr.set_source_rgb(0.95, 0.95, 0.96)
                self.cr.rectangle(MARGIN, self.y, total, height)
                self.cr.fill()
            x = MARGIN
            for layout, width in zip(layouts, widths):
                self.draw(layout, x + pad, self.y + pad)
                x += width
            self.y += height
            self.cr.set_source_rgb(*LINE)
            self.cr.set_line_width(0.4)
            self.cr.move_to(MARGIN, self.y)
            self.cr.line_to(MARGIN + total, self.y)
            self.cr.stroke()

        draw_row(row_layouts(headers, True, GREY), shade=True)
        for cells in rows:
            draw_row(row_layouts(cells))
        self.y += 10

    def close(self):
        self.footer()
        self.surface.finish()


def write_pdf(report, path):
    title = report["title"]
    pdf = Pdf(path, f"{title} · Stand {report['generated']}", landscape=report["dev"])
    kind = "Entwicklungsprojekt – Nachverfolgung" if report["dev"] else "Aufgaben-Board"
    pdf.text(kind.upper(), size=8, bold=True, color=ACCENT, space=2)
    pdf.text(title, size=20, bold=True, space=2)
    rows = report["rows"]
    counts = " · ".join(f"{name}: {len(items)}" for name, items in report["columns"])
    pdf.text(f"Stand {report['generated']} · {len(rows)} Karten · {counts}", size=9, color=GREY, space=12)
    pdf.rule()

    if report["dev"]:
        pdf.text("Traceability-Matrix", size=13, bold=True, space=6)
        pdf.table(["ID", "Titel", "Prio", "Status", "Commits", "Verifikation", "Version", "Abnahme"],
                  [8, 29, 6, 11, 11, 19, 8, 13],
                  [[r["id"], r["title"], r["priority"], r["status"], r["commits"], r["verification"],
                    r["version"], r["accepted"]] for r in rows], mono=(0, 4))
        pdf.text("Karten im Einzelnen", size=13, bold=True, space=6)
        for r in rows:
            pdf.need(60)
            pdf.rule(6)
            pdf.text(f"[{r['id']}]  {r['title']}", size=11, bold=True, space=2)
            facts = [f"Status: {r['status']}"] + [f"{label}: {r[key]}" for key, label in (
                ("priority", "Priorität"), ("assignee", "Zuständig"), ("created", "Erstellt"),
                ("done", "Erledigt"), ("version", "Version"), ("accepted", "Abnahme")) if r[key]]
            pdf.text(" · ".join(facts), size=8.5, color=GREY, space=6)
            for key, label in (("notes", "Beschreibung"), ("impact", "Auswirkungsanalyse"), ("verification", "Verifikation")):
                if r[key].strip():
                    pdf.text(label, size=9, bold=True, space=1)
                    pdf.text(r[key].strip(), size=9, space=5)
            if r["commit_list"]:
                pdf.text("Commits", size=9, bold=True, space=1)
                for commit in r["commit_list"]:
                    pdf.text(f"{commit.get('h', '')}  {commit.get('s', '')}", size=8.5, space=1)
                pdf.y += 4
            if r["history"]:
                pdf.text("Verlauf", size=9, bold=True, space=1)
                for name, when, who in r["history"]:
                    pdf.text(f"{when}  {name}  ({who})", size=8.5, color=GREY, space=1)
                pdf.y += 4
    else:
        for name, items in report["columns"]:
            pdf.text(f"{name} ({len(items)})", size=13, bold=True, space=6)
            if items:
                pdf.table(["Titel", "Priorität", "Zuständig", "Fällig", "Erledigt"], [42, 11, 15, 14, 18],
                          [[r["title"], r["priority"], r["assignee"], r["due"], r["done"]] for r in items])
            else:
                pdf.text("Keine Karten", size=9, color=GREY, space=10)
    pdf.close()
