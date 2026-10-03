"""Marketing and help screenshots of the Ubuntu app with demo data (isolated data folder, local mode).

    LINOTES_DEMO_DIR=/tmp/demo python3 tools/demo-screenshots-ubuntu.py      (light)
    DEMO_DARK=1 LINOTES_DEMO_DIR=/tmp/demo python3 tools/demo-screenshots-ubuntu.py

The folder needs probe.ogg (a short Opus recording) and tab.pdf (any small PDF); pictures go to
<folder>/shots, data to <folder>/demodata (delete it before each run). Never touches real data."""
import os, sys, time, datetime
SCRATCH = os.environ.get("LINOTES_DEMO_DIR") or os.path.dirname(os.path.abspath(__file__))
os.environ["XDG_DATA_HOME"] = os.path.join(SCRATCH, "demodata")
os.environ["XDG_CACHE_HOME"] = os.path.join(SCRATCH, "democache")
DARK = os.environ.get("DEMO_DARK") == "1"
sys.path.insert(0, os.path.expanduser("~/LiNotes/linux"))
import gi
gi.require_version("Gtk", "4.0"); gi.require_version("Adw", "1"); gi.require_version("Graphene", "1.0")
from gi.repository import Adw, Gio, GLib, Gtk, Graphene
from linotes import application, model, plans, sync as _sync, uiprefs
from linotes.application import LiNotesApplication
assert "/scratchpad/demodata/" in str(_sync.DATA_DIR), _sync.DATA_DIR
application.APP_ID = "io.github.veritasx1.LiNotesDemo"
OUT = os.path.join(SCRATCH, "shots")


class App(LiNotesApplication):
    def __init__(self):
        Adw.Application.__init__(self, application_id="io.github.veritasx1.LiNotesDemo", flags=Gio.ApplicationFlags.NON_UNIQUE)
        self.sync = None
        self.start_with_new_note = False


def shot(widget, name, scale=2):
    w, h = widget.get_width(), widget.get_height()
    paintable = Gtk.WidgetPaintable.new(widget)
    snap = Gtk.Snapshot()
    snap.scale(scale, scale)
    paintable.snapshot(snap, w, h)
    node = snap.to_node()
    rect = Graphene.Rect().init(0, 0, w * scale, h * scale)
    tex = widget.get_native().get_renderer().render_texture(node, rect)
    tex.save_to_png(os.path.join(OUT, ("dark-" if DARK else "") + name + ".png"))
    print("Bild", name, flush=True)


def span(text, part, name):
    start = text.index(part)
    return [start, start + len(part), name]


def seed(sync):
    uid = sync.user_id
    model.ensure_defaults(sync)
    now = time.time()
    folder = model.default_private_folder(uid)
    def make_folder(name, order):
        return sync.put("folder", {"name": name, "order": order}, None, notify=False)["id"]
    reisen = make_folder("Reisen", 1)
    rezepte = make_folder("Rezepte", 2)
    haushalt = make_folder("Haushalt", 3)

    def note(folder_id, body, minutes_ago, pinned=False):
        data = {"folder": folder_id, "body": body, "created": now - minutes_ago * 60 - 3600, "modified": now - minutes_ago * 60}
        if pinned:
            data["pinned"] = True
        return sync.put("note", data, None, notify=False)

    tour = note(reisen, [
        {"t": "title", "x": "Radtour Kühlungsborn"},
        {"t": "body", "x": "Rund 42 km, flach und fast immer am Wasser."},
        {"t": "number", "x": "Start am Bahnhof Kühlungsborn West"},
        {"t": "number", "x": "Steilküste bis Heiligendamm"},
        {"t": "number", "x": "Mittag im Café am Kamp"},
        {"t": "number", "x": "Zurück durch den Gespensterwald"},
    ], 95)
    intro = "Freitag nach der Arbeit los, Rückfahrt Sonntagabend. Zimmer mit Meerblick ist reserviert."
    link_line = "Route: Radtour Kühlungsborn"
    calc_line = "240 + 78 + 120 = 438"
    hero = note(reisen, [
        {"t": "title", "x": "Wochenende an der Ostsee"},
        {"t": "body", "x": intro, "s": [span(intro, "Zimmer mit Meerblick", "h:mint")]},
        {"t": "heading", "x": "Packliste"},
        {"t": "check", "x": "Badesachen und Handtücher", "c": True},
        {"t": "check", "x": "Sonnencreme", "c": True},
        {"t": "check", "x": "Fahrradschloss und Helm"},
        {"t": "check", "x": "Ladekabel und Powerbank"},
        {"t": "heading", "x": "Budget"},
        model.table_block([["Posten", "Betrag", "Wer"], ["Unterkunft", "240 €", "Anna"], ["Bahn", "78 €", "Olaf"], ["Essen", "120 €", "beide"]]),
        {"t": "body", "x": calc_line, "s": [span(calc_line, "438", "b")]},
        {"t": "body", "x": link_line, "s": [span(link_line, "Radtour Kühlungsborn", "n:" + tour["id"])]},
    ], 3, pinned=True)
    cake = note(rezepte, [
        {"t": "title", "x": "Omas Apfelkuchen"},
        {"t": "subheading", "x": "Zutaten"},
        {"t": "bullet", "x": "6 säuerliche Äpfel"},
        {"t": "bullet", "x": "200 g Butter, 180 g Zucker"},
        {"t": "bullet", "x": "3 Eier, 300 g Mehl, 1 Päckchen Backpulver"},
        {"t": "subheading", "x": "Zubereitung"},
        {"t": "number", "x": "Butter und Zucker schaumig schlagen, Eier einzeln unterrühren."},
        {"t": "number", "x": "Mehl und Backpulver unterheben, Teig in die Form."},
        {"t": "number", "x": "Äpfel vierteln, einritzen, dicht auf den Teig setzen."},
        {"t": "number", "x": "45 Minuten bei 180 °C backen."},
        {"t": "quote", "x": "Mit Sahne servieren – Oma bestand darauf."},
    ], 60 * 26)
    book = note(haushalt, [
        {"t": "title", "x": "Haushaltsbuch Oktober"},
        {"t": "body", "x": "Fixkosten: 850 + 74 + 35 = 959"},
        {"t": "body", "x": "Lebensmittel: 412 / 2 = 206"},
        {"t": "body", "x": "Sparrate: 959 * 0,1 = 95,9"},
        {"t": "mono", "x": "Rechnen geht einfach mit = am Zeilenende"},
    ], 60 * 5)
    pdf_id = sync.upload_file(open(os.path.join(SCRATCH, "tab.pdf"), "rb").read(), None)
    ogg = open(os.path.join(SCRATCH, "probe.ogg"), "rb").read()
    ogg_id = sync.upload_file(ogg, None)
    meeting_text = "Kurz besprochen: Lieferung kommt Dienstag, Anna übernimmt die Abholung."
    meeting = note(folder, [
        {"t": "title", "x": "Elternabend 2b"},
        {"t": "body", "x": meeting_text, "s": [span(meeting_text, "Dienstag", "b")]},
        {"t": "file", "f": ogg_id, "n": "Aufnahme 2026-10-01 19-30.ogg", "m": "audio/ogg", "b": 214000, "d": 512.4},
        {"t": "file", "f": pdf_id, "n": "Ausflug Zoo – Elternbrief.pdf", "m": "application/pdf", "b": len(open(os.path.join(SCRATCH, "tab.pdf"), "rb").read())},
        {"t": "divider"},
        {"t": "check", "x": "Unterschrift bis Freitag abgeben"},
        {"t": "check", "x": "10 € Busgeld mitgeben"},
    ], 40)
    ideas = note(folder, [
        {"t": "title", "x": "Geschenkideen"},
        {"t": "heading", "x": "Anna", "z": True},
        {"t": "bullet", "x": "Kochkurs Thai"},
        {"t": "bullet", "x": "Konzertkarten"},
        {"t": "heading", "x": "Ben"},
        {"t": "bullet", "x": "Kletterhalle – Zehnerkarte"},
        {"t": "bullet", "x": "Bluetooth-Lautsprecher"},
    ], 60 * 30)
    note(folder, [{"t": "title", "x": "Zählerstände"}, {"t": "body", "x": "Strom 24 518 kWh · Gas 8 214 m³ · Wasser 312 m³"}], 60 * 50)

    # list
    lst = model.default_list(uid)
    base = now
    for i, (text, done) in enumerate([("Hafermilch", False), ("Äpfel (Boskop)", False), ("Vollkornbrot", False), ("Kaffeebohnen", False),
                                       ("Basilikum", False), ("Butter", True), ("Spülmaschinentabs", True)]):
        sync.put("item", {"list": lst, "text": text, "done": done, "order": base + i * 0.001, "by": uid}, None, notify=False)

    # board
    board = model.default_board(uid)
    columns = {c["data"]["name"]: c["id"] for c in model.board_columns(sync, board)}
    cards = [("Offen", "Steuererklärung abgeben", "rot", "hoch", "Belege liegen im Ordner „Haushalt“."),
             ("Offen", "Fahrrad zur Inspektion", "blau", "mittel", ""),
             ("Offen", "Fenster putzen", None, None, ""),
             ("In Arbeit", "Gartenhaus planen", "grün", "mittel", "Projektplan steht, Material bestellen."),
             ("In Arbeit", "Fotobuch Sommerurlaub", "lila", None, ""),
             ("Erledigt", "Geburtstagsgeschenk für Anna", "orange", None, "")]
    for order, (column, title, color, priority, notes) in enumerate(cards):
        data = {"board": board, "column": columns[column], "title": title, "order": order, **model.new_card_fields(sync, columns[column])}
        if color: data["color"] = color
        if priority: data["priority"] = priority
        if notes: data["notes"] = notes
        sync.put("card", data, None, notify=False)

    # plans
    today = datetime.date.today()
    putz = {**plans.template("putzplan"), "name": "Putzplan WG", "order": 1}
    putz["rot"] = {"people": ["Olaf", "Anna", "Ben"], "start": plans.monday(today).isoformat()}
    putz["cols"]["count"] = 5
    putz = plans.set_cell(putz, 2, 1, "Ben (Urlaub)", "yellow")
    ids = {"putz": sync.put("plan", putz, None, notify=False)["id"]}
    stunden = {**plans.template("stundenplan"), "name": "Stundenplan Emma", "order": 2}
    lessons = [["Deutsch", "Mathe", "Englisch", "Sport", "Kunst"], ["Deutsch", "Mathe", "Sachkunde", "Sport", "Musik"],
               ["Mathe", "Englisch", "Deutsch", "Religion", "Deutsch"], ["Sachkunde", "Deutsch", "Mathe", "Englisch", "Mathe"],
               ["Musik", "", "Kunst", "Förder", ""], ["", "", "Kunst", "", ""]]
    colors = {"Deutsch": "yellow", "Mathe": "blue", "Englisch": "pink", "Sport": "mint", "Kunst": "purple", "Musik": "orange",
              "Sachkunde": "grey", "Religion": "grey", "Förder": "grey"}
    for r, row in enumerate(lessons):
        for c, subject in enumerate(row):
            if subject:
                stunden = plans.set_cell(stunden, r, c, subject, colors[subject])
    ids["stunden"] = sync.put("plan", stunden, None, notify=False)["id"]
    start = plans.monday(today) - datetime.timedelta(days=7)
    def at(days):
        return (start + datetime.timedelta(days=days)).isoformat()
    projekt = {"name": "Gartenhaus bauen", "order": 3, "mode": "timeline", "tasks": [
        {"x": "Planung und Genehmigung", "from": at(0), "to": at(9), "k": "blue"},
        {"x": "Fundament gießen", "from": at(10), "to": at(13), "k": "grey"},
        {"x": "Material liefern", "from": at(14), "to": at(14), "k": "pink", "m": True},
        {"x": "Aufbau Wände und Dach", "from": at(15), "to": at(26), "k": "orange"},
        {"x": "Streichen", "from": at(24), "to": at(30), "k": "mint"},
        {"x": "Einweihung", "from": at(33), "to": at(33), "k": "purple", "m": True}]}
    ids["projekt"] = sync.put("plan", projekt, None, notify=False)["id"]
    schicht = {**plans.template("schichtplan"), "name": "Dienstplan Station 3", "order": 4, "rows": ["Lena", "Murat", "Sabine", "Tom"]}
    pattern = [["Früh", "Früh", "Spät", "Spät", "Frei", "Nacht", "Nacht"], ["Spät", "Spät", "Frei", "Früh", "Früh", "Frei", "Frei"],
               ["Nacht", "Nacht", "Frei", "Frei", "Spät", "Spät", "Früh"], ["Frei", "Früh", "Früh", "Nacht", "Nacht", "Frei", "Spät"]]
    shift_colors = {"Früh": "yellow", "Spät": "blue", "Nacht": "purple", "Frei": "grey"}
    schicht["cells"] = []
    for r, row in enumerate(pattern):
        for c, value in enumerate(row):
            schicht = plans.set_cell(schicht, r, c, value, shift_colors[value])
    ids["schicht"] = sync.put("plan", schicht, None, notify=False)["id"]
    # automotive development project (theoretical): ASPICE-like flow, ISO 26262 impact analysis
    dev = sync.put("board", {"name": "Spurhalteassistent LKA – Steuergerät", "order": 2, "dev": True}, None, notify=False)["id"]
    dev_cols = {}
    for order, name in enumerate(["CR", "Analyse", "Umsetzung", "Verifikation", "Freigegeben"]):
        dev_cols[name] = sync.put("column", {"board": dev, "name": name, "order": order}, None, notify=False)["id"]
    day = 86400
    def hist(*steps):
        return [{"c": dev_cols[n], "n": n, "at": now - ago * day, "by": uid} for n, ago in steps]
    dev_cards = [
        ("CR", "Warnschwelle bei Nässe anpassen", "mittel", "orange", None, None, None, [], hist(("CR", 2))),
        ("CR", "Diagnose-Trouble-Code für Kamerablindheit", "niedrig", "blau", None, None, None, [], hist(("CR", 1))),
        ("Analyse", "Lenkmoment-Eingriff auf 3 Nm begrenzen", "hoch", "rot",
         "ASIL B betroffen (Sicherheitsziel SG-02: kein ungewollter Lenkeingriff > 3 Nm). Änderung an SW-Komponente LKA_Ctrl, "
         "Schnittstelle zum EPS unverändert. Regressionsumfang: HIL-Szenarien 12–18. Kein Einfluss auf ESC/ABS.", None, None, [],
         hist(("CR", 6), ("Analyse", 3))),
        ("Umsetzung", "Spurerkennung bei Baustellenmarkierung (gelb)", "hoch", "orange",
         "QM, kein Sicherheitsziel betroffen. Kalibrierdaten der Kamera, neue Parameter-Tabelle. Bestehende Freigabe-Tests ausreichend.",
         None, None, [{"h": "a41c9e2", "s": "LKA: gelbe Fahrbahnmarkierung bevorzugen (Baustellenmodus)"}], hist(("CR", 12), ("Analyse", 9), ("Umsetzung", 4))),
        ("Verifikation", "Abschaltung unter 60 km/h", "mittel", "grün",
         "ASIL A. Funktionsgrenze in Zustandsautomat LKA_Mode. Wirkt nur auf Aktivierung.",
         "SIL-Test TC-LKA-031..036 bestanden, HIL-Lauf 2026-09-30 i. O., Fahrversuch ausstehend.", "SW 4.2.0",
         [{"h": "7d03b1f", "s": "LKA: Aktivierungsschwelle 60 km/h, Hysterese 5 km/h"}, {"h": "c19e844", "s": "Tests: SIL-Szenarien Abschaltgrenze"}],
         hist(("CR", 20), ("Analyse", 17), ("Umsetzung", 11), ("Verifikation", 2))),
        ("Freigegeben", "Hands-off-Erkennung 15 s", "hoch", "lila",
         "ASIL B (SG-04). Erkennung über Lenkmomentsensor, Warnkaskade optisch → akustisch → Abschaltung.",
         "Fahrversuch 2 × 500 km i. O., HIL 100 % bestanden, Review RV-118 abgeschlossen.", "SW 4.1.3",
         [{"h": "e5520ad", "s": "LKA: Hands-off-Warnkaskade"}], hist(("CR", 40), ("Analyse", 35), ("Umsetzung", 28), ("Verifikation", 14), ("Freigegeben", 6))),
    ]
    dev_ids = []
    for order, (col, title, prio, color, impact, verification, version, commits, history) in enumerate(dev_cards):
        data = {"board": dev, "column": dev_cols[col], "title": title, "order": order, "priority": prio, "color": color,
                "created_by": uid, "created": history[0]["at"], "history": history}
        for key, value in (("impact", impact), ("verification", verification), ("version", version)):
            if value:
                data[key] = value
        if commits:
            data["commits"] = commits
        if col == "Freigegeben":
            data["done_at"] = history[-1]["at"]
        dev_ids.append(sync.put("card", data, None, notify=False)["id"])

    return {"dev": dev, "dev_card": dev_ids[4], "hero": hero["id"], "cake": cake["id"], "book": book["id"], "meeting": meeting["id"], "ideas": ideas["id"],
            "tour": tour["id"], "reisen": reisen, "board": board, "list": lst, **ids}


def add_evidence(sync, card_id):
    """Two verification records on the demo card: a test protocol (PDF) and a result picture."""
    import cairo
    picture = os.path.join(SCRATCH, "sil-ergebnis.png")
    surface = cairo.ImageSurface(cairo.FORMAT_RGB24, 640, 300)
    cr = cairo.Context(surface)
    cr.set_source_rgb(1, 1, 1); cr.paint()
    cr.set_source_rgb(0.13, 0.13, 0.15); cr.select_font_face("Sans", 0, 1); cr.set_font_size(26)
    cr.move_to(28, 52); cr.show_text("SIL-Testlauf LKA – Abschaltgrenze")
    cr.select_font_face("Sans", 0, 0); cr.set_font_size(19)
    for i, case in enumerate(["TC-LKA-031", "TC-LKA-032", "TC-LKA-033", "TC-LKA-034", "TC-LKA-035", "TC-LKA-036"]):
        cr.set_source_rgb(0.13, 0.13, 0.15); cr.move_to(28, 100 + i * 31); cr.show_text(case)
        cr.set_source_rgb(0.18, 0.66, 0.31); cr.move_to(240, 100 + i * 31); cr.show_text("bestanden")
    surface.write_to_png(picture)
    card = sync.get(card_id)
    items = []
    for path, name, mime in ((os.path.join(SCRATCH, "tab.pdf"), "HIL-Protokoll 2026-09-30.pdf", "application/pdf"),
                             (picture, "SIL-Ergebnis TC-LKA-031–036.png", "image/png")):
        content = open(path, "rb").read()
        reference = sync.upload_file(content, card.get("share"))
        items.append({"f": reference, "n": name, "m": mime, "b": len(content), **model.evidence_fields(sync, content)})
    sync.update(card_id, notify=False, evidence=items)


def show_evidence(win):
    """Scroll the open card dialog to its evidence."""
    dialog = win._demo_dialog
    dialog.evidence_rows[-1].grab_focus()


def open_card(win, ids):
    from linotes.kanban import CardDialog
    dialog = CardDialog(win.board_view, win.sync.get(ids["dev_card"]))
    dialog.present(win)
    win._demo_dialog = dialog


def report_image(sync, ids):
    """The traceability report (PDF) of the development project as a picture."""
    import subprocess
    from linotes import report
    path = os.path.join(OUT, "bericht.pdf")
    report.write_pdf(report.build(sync, ids["dev"]), path)
    subprocess.run(["pdftoppm", "-r", "110", "-png", "-f", "1", "-l", "2", path, os.path.join(OUT, ("dark-" if DARK else "") + "15-bericht-seite")], check=True)


def run(app):
    win = app.get_active_window()
    sync = win.sync
    if not sync.is_local:
        win.on_local(None, "Olaf")
    if DARK:
        Adw.StyleManager.get_default().set_color_scheme(Adw.ColorScheme.FORCE_DARK)
    win.set_default_size(1280, 800)
    win.unmaximize()
    ids = seed(sync)
    add_evidence(sync, ids["dev_card"])
    win.sidebar.refresh()
    steps = [
        ("01-notiz", lambda: (win.sidebar.select("folder:" + ids["reisen"]), win.select("folder:" + ids["reisen"]), win.open_note(ids["hero"]))),
        ("02-rezept", lambda: win.open_note(ids["cake"])),
        ("03-rechnen", lambda: (win.select("all"), win.open_note(ids["book"]))),
        ("04-audio-pdf", lambda: win.open_note(ids["meeting"])),
        ("05-abschnitte", lambda: win.open_note(ids["ideas"])),
        ("06-galerie", lambda: (win.set_note_mode("gallery") if hasattr(win, "set_note_mode") else None)),
        ("07-liste", lambda: (win.set_note_mode("list"), win.sidebar.select("list:" + ids["list"]), win.select("list:" + ids["list"]))),
        ("08-board", lambda: (win.sidebar.select("board:" + ids["board"]), win.select("board:" + ids["board"]))),
        ("09-putzplan", lambda: (win.sidebar.select("plan:" + ids["putz"]), win.select("plan:" + ids["putz"]))),
        ("10-stundenplan", lambda: (win.sidebar.select("plan:" + ids["stunden"]), win.select("plan:" + ids["stunden"]))),
        ("11-projektplan", lambda: (win.sidebar.select("plan:" + ids["projekt"]), win.select("plan:" + ids["projekt"]))),
        ("12-dienstplan", lambda: (win.sidebar.select("plan:" + ids["schicht"]), win.select("plan:" + ids["schicht"]))),
        ("13-entwicklung", lambda: (win.sidebar.select("board:" + ids["dev"]), win.select("board:" + ids["dev"]), win.split.set_show_sidebar(False), win.set_default_size(1480, 820))),
        ("14-karte", lambda: (win.set_default_size(1280, 800), win.split.set_show_sidebar(True), open_card(win, ids))),
        ("14b-nachweise", lambda: (open_card(win, ids), GLib.timeout_add(500, lambda: show_evidence(win) and False))),
        ("15-bericht", lambda: report_image(sync, ids)),
    ]
    only = os.environ.get("DEMO_ONLY")

    def next_step(index=0):
        if index >= len(steps):
            app.quit()
            return False
        name, action = steps[index]
        if only and name not in only.split(","):
            GLib.idle_add(lambda: next_step(index + 1))
            return False
        action()
        def after():
            if name == "15-bericht":
                print("Bild", name, flush=True)
            else:
                shot(win, name)
            dialog = getattr(win, "_demo_dialog", None)
            if dialog is not None:
                dialog.close()
                win._demo_dialog = None
            GLib.timeout_add(150, lambda: next_step(index + 1))
            return False
        GLib.timeout_add(900, after)
        return False
    GLib.timeout_add(1200, lambda: next_step(0))


app = App()
app.connect("activate", lambda a: GLib.idle_add(lambda: run(a) and False))
app.run([])
