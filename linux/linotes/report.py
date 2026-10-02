"""Board report as PDF or CSV – a simple list for ordinary boards, a
traceability matrix plus card details for development projects."""

import csv
import datetime

import cairo
import gi

gi.require_version("Pango", "1.0")
gi.require_version("PangoCairo", "1.0")

from gi.repository import GLib, Pango, PangoCairo

from . import model

A4 = (595.0, 842.0)  # points
MARGIN = 48.0
ACCENT = (0.72, 0.49, 0.0)
GREY = (0.42, 0.42, 0.45)
LINE = (0.85, 0.85, 0.87)
LIST_MARKS = {"bullet": "•", "dash": "–", "number": "", "check": "○"}


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


# --- single note ------------------------------------------------------

NOTE_STYLES = {  # size, bold, italic, space after
    "title": (20, True, False, 8), "heading": (15, True, False, 5), "subheading": (12.5, True, False, 4),
    "body": (10.5, False, False, 3), "mono": (9.5, False, False, 3), "quote": (10.5, False, True, 3),
}
NOTE_MARKUP = {"b": ("<b>", "</b>"), "i": ("<i>", "</i>"), "u": ("<u>", "</u>"), "s": ("<s>", "</s>"),
               "h": ("<span background='#FFE680'>", "</span>"),
               "h:orange": ("<span background='#FFCF85'>", "</span>"), "h:pink": ("<span background='#FFB7D3'>", "</span>"),
               "h:purple": ("<span background='#DFBCF7'>", "</span>"), "h:mint": ("<span background='#A5ECE0'>", "</span>"),
               "h:blue": ("<span background='#ACE3FC'>", "</span>"),
               "c:purple": ("<span foreground='#9B51E0'>", "</span>"), "c:pink": ("<span foreground='#E0457F'>", "</span>"),
               "c:orange": ("<span foreground='#E07A00'>", "</span>"), "c:mint": ("<span foreground='#12A594'>", "</span>"),
               "c:blue": ("<span foreground='#1C8CE0'>", "</span>"),
               "f:serif": ("<span font_family='Serif'>", "</span>"), "f:mono": ("<span font_family='Monospace'>", "</span>")}


NOTE_LINK_MARKUP = ("<span foreground='#B87D00' underline='single'>", "</span>")


def block_markup(block):
    """Pango markup of one line with its bold/italic/… spans."""
    text = block.get("x", "")
    opening, closing = {}, {}
    for span in block.get("s", []):
        try:
            start, end, name = span
        except ValueError:
            continue
        # Links to other notes look like links (accent color, underlined).
        markup = NOTE_MARKUP.get(name) or (NOTE_LINK_MARKUP if isinstance(name, str) and name.startswith("n:") else None)
        if markup and int(start) < int(end):
            opening.setdefault(int(start), []).append(markup[0])
            closing.setdefault(min(int(end), len(text)), []).insert(0, markup[1])
    out = []
    for index in range(len(text) + 1):
        out += closing.get(index, [])
        out += opening.get(index, [])
        if index < len(text):
            out.append(GLib.markup_escape_text(text[index]))
    # Pango needs properly nested tags; spans that overlap only partially lose their style.
    markup = "".join(out)
    try:
        Pango.parse_markup(markup, -1, "\0")
        return markup
    except GLib.Error:
        return GLib.markup_escape_text(text)


def write_note_pdf(blocks, path, header, image_path=None):
    """A note as PDF in the look of the editor: title, headings, lists, checklists, photos."""
    gi.require_version("Gdk", "4.0")
    from gi.repository import Gdk, GdkPixbuf
    pdf = Pdf(path, header)
    numbers = {}
    for block in blocks:
        kind = block.get("t", "body")
        level = int(block.get("l", 0))
        if kind == "image":
            if not image_path or not block.get("f"):
                continue
            try:
                pixbuf = GdkPixbuf.Pixbuf.new_from_file(str(image_path(block["f"])))
                pixbuf = pixbuf.apply_embedded_orientation() or pixbuf
            except Exception as error:  # missing download, unknown format
                print("LiNotes: Bild nicht im PDF:", error)
                continue
            width = pdf.width - 2 * MARGIN
            scale = min(width / pixbuf.get_width(), 360 / pixbuf.get_height(), 1.0)
            height = pixbuf.get_height() * scale
            pdf.need(height)
            pdf.cr.save()
            pdf.cr.translate(MARGIN, pdf.y)
            pdf.cr.scale(scale, scale)
            Gdk.cairo_set_source_pixbuf(pdf.cr, pixbuf, 0, 0)
            pdf.cr.paint()
            pdf.cr.restore()
            pdf.y += height + 8
            numbers = {}
            continue
        if kind == "file":
            # Attachments are listed with name and size (their content is not part of the PDF).
            from .editor import file_details
            layout = pdf.layout(f"📎 {block.get('n') or 'Datei'}  ({file_details(block)})", 10.5, color=GREY)
            pdf.need(layout[0].get_pixel_extents()[1].height)
            pdf.draw(layout, MARGIN, pdf.y)
            pdf.y += layout[0].get_pixel_extents()[1].height + 6
            numbers = {}
            continue
        if kind == "table":
            # Rows with thin lines, each row kept on one page.
            rows = model.table_rows(block)
            width = (pdf.width - 2 * MARGIN) / len(rows[0])
            for row in rows:
                cells = [pdf.layout(text, 10.5, width=width - 10) for text in row]
                height = max(pdf.height(cell) for cell in cells) + 10
                pdf.need(height)
                pdf.cr.set_source_rgb(*LINE)
                pdf.cr.set_line_width(0.8)
                for index, cell in enumerate(cells):
                    pdf.cr.rectangle(MARGIN + index * width, pdf.y, width, height)
                    pdf.cr.stroke()
                    pdf.draw(cell, MARGIN + index * width + 5, pdf.y + 5)
                    pdf.cr.set_source_rgb(*LINE)
                pdf.y += height
            pdf.y += 8
            numbers = {}
            continue
        if kind == "divider":
            pdf.need(16)
            pdf.cr.set_source_rgb(*LINE)
            pdf.cr.rectangle(MARGIN, pdf.y + 7, pdf.width - 2 * MARGIN, 0.8)
            pdf.cr.fill()
            pdf.y += 16
            numbers = {}
            continue
        if kind == "number":
            numbers[level] = numbers.get(level, 0) + 1
            numbers = {key: value for key, value in numbers.items() if key <= level}
        elif kind not in LIST_MARKS:
            numbers = {}
        size, bold, italic, space = NOTE_STYLES.get(kind if kind in NOTE_STYLES else "body")
        indent = 18 * level + (18 if kind in LIST_MARKS else 0) + (14 if kind == "quote" else 0)
        layout, color = pdf.layout("", size, bold, pdf.width - 2 * MARGIN - indent,
                                   GREY if kind == "quote" or (kind == "check" and block.get("c")) else (0, 0, 0),
                                   mono=kind == "mono")
        if italic:
            font = layout.get_font_description().copy()
            font.set_style(Pango.Style.ITALIC)
            layout.set_font_description(font)
        markup = block_markup(block) or " "
        if kind == "check" and block.get("c"):
            markup = f"<s>{markup}</s>"
        layout.set_markup(markup, -1)
        if block.get("a") in ("center", "right"):
            layout.set_alignment(Pango.Alignment.CENTER if block["a"] == "center" else Pango.Alignment.RIGHT)
        height = layout.get_pixel_extents()[1].height
        pdf.need(height)
        x = MARGIN + indent
        if kind in LIST_MARKS:
            mark = f"{numbers.get(level, 1)}." if kind == "number" else LIST_MARKS[kind]
            if kind == "check" and block.get("c"):
                mark = "☑"
            mark_layout = pdf.layout(mark, size, color=ACCENT if kind == "check" else (0, 0, 0))
            pdf.draw(mark_layout, x - 16, pdf.y)
        if kind == "quote":
            pdf.cr.set_source_rgb(*LINE)
            pdf.cr.rectangle(x - 10, pdf.y, 2.5, height)
            pdf.cr.fill()
        pdf.draw((layout, color), x, pdf.y)
        pdf.y += height + space
    pdf.close()


def write_plan_pdf(plan, path):
    """A plan on A4 landscape to hang up: the grid with colors, or the timeline with bars."""
    import datetime
    from . import plans
    name = plan.get("name") or "Plan"
    pdf = Pdf(path, f"{name} · Stand {datetime.date.today().strftime('%d.%m.%Y')}", landscape=True)
    title = pdf.layout(name, 18, bold=True)
    pdf.draw(title, MARGIN, pdf.y)
    pdf.y += pdf.height(title) + 12
    if plan.get("mode") == "timeline":
        first, last = plans.timeline_range(plan)
        days = (last - first).days + 1
        label_width = 150
        scale = (pdf.width - 2 * MARGIN - label_width) / days
        top = pdf.y
        for i in range(0, days, 7):
            x = MARGIN + label_width + i * scale
            d = first + datetime.timedelta(days=i)
            pdf.draw(pdf.layout(f"KW {d.isocalendar()[1]} · {d.strftime('%d.%m.')}", 8, color=GREY), x + 2, top)
        pdf.y += 16
        for task in plan.get("tasks") or []:
            pdf.need(24)
            pdf.draw(pdf.layout(task.get("x") or "", 10, width=label_width - 8), MARGIN, pdf.y + 3)
            for i in range(0, days, 7):
                pdf.cr.set_source_rgb(*LINE)
                pdf.cr.rectangle(MARGIN + label_width + i * scale, pdf.y, 0.6, 22)
                pdf.cr.fill()
            span = plans.task_span(task)
            if span:
                pdf.cr.set_source_rgb(*plans.COLORS.get(task.get("k"), plans.COLORS["blue"]))
                x = MARGIN + label_width + (span[0] - first).days * scale
                if task.get("m"):
                    cx, cy = x + scale / 2, pdf.y + 11
                    pdf.cr.move_to(cx, cy - 8)
                    pdf.cr.line_to(cx + 8, cy)
                    pdf.cr.line_to(cx, cy + 8)
                    pdf.cr.line_to(cx - 8, cy)
                    pdf.cr.close_path()
                else:
                    pdf.cr.rectangle(x, pdf.y + 4, ((span[1] - span[0]).days + 1) * scale, 14)
                pdf.cr.fill()
            pdf.y += 24
        pdf.close()
        return
    rows = plans.text_rows(plan)
    columns = len(rows[0])
    first_width = 110
    width = (pdf.width - 2 * MARGIN - first_width) / max(1, columns - 1)
    grid = plans.cells(plan)
    today = plans.today_column(plan)
    for r, row in enumerate(rows):
        layouts = [pdf.layout(text, 10, bold=(r == 0 or c == 0), width=(first_width if c == 0 else width) - 10)
                   for c, text in enumerate(row)]
        height = max(pdf.height(cell) for cell in layouts) + 12
        pdf.need(height)
        x = MARGIN
        for c, cell in enumerate(layouts):
            w = first_width if c == 0 else width
            color = (grid[r - 1][c - 1] or {}).get("k") if r > 0 and c > 0 else None
            if color:
                red, green, blue = plans.COLORS.get(color, plans.COLORS["grey"])
                pdf.cr.set_source_rgba(red, green, blue, 0.35)
                pdf.cr.rectangle(x, pdf.y, w, height)
                pdf.cr.fill()
            elif c > 0 and c - 1 == today and r == 0:
                pdf.cr.set_source_rgba(1.0, 0.85, 0.24, 0.25)
                pdf.cr.rectangle(x, pdf.y, w, height)
                pdf.cr.fill()
            pdf.cr.set_source_rgb(*LINE)
            pdf.cr.set_line_width(0.8)
            pdf.cr.rectangle(x, pdf.y, w, height)
            pdf.cr.stroke()
            pdf.draw(cell, x + 5, pdf.y + 6)
            x += w
        pdf.y += height
    pdf.close()
