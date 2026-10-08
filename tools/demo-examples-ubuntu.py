"""Example projects for the website (isolated data folder, local mode, invented content):

  1. Automotive: electromechanical brake, rear axle – ASIL D item with an ASIL C(D) main computer and an
     ASIL A(D) safety monitor (ISO 26262 decomposition), run with folders, notes, development boards,
     plans, evidence and reports.
  2. Software with AI support: a small app built with an AI account on the Kanban board.

    LINOTES_DEMO_DIR=<scratchpad> python3 tools/demo-examples-ubuntu.py
    DEMO_DARK=1 …                                                   (dark)

Data goes to <folder>/demodata (delete before each run), pictures to <folder>/examples.
Never touches real data. All names, numbers and results are made up."""
import os, sys, time, datetime, json
SCRATCH = os.environ.get("LINOTES_DEMO_DIR") or os.path.dirname(os.path.abspath(__file__))
os.environ["XDG_DATA_HOME"] = os.path.join(SCRATCH, "demodata")
os.environ["XDG_CACHE_HOME"] = os.path.join(SCRATCH, "democache")
DARK = os.environ.get("DEMO_DARK") == "1"
sys.path.insert(0, os.path.expanduser("~/LiNotes/linux"))
import cairo
import gi
gi.require_version("Gtk", "4.0"); gi.require_version("Adw", "1"); gi.require_version("Graphene", "1.0")
from gi.repository import Adw, Gio, GLib, Gtk, Graphene
from linotes import application, model, sync as _sync
from linotes.application import LiNotesApplication
assert "/scratchpad/demodata/" in str(_sync.DATA_DIR), _sync.DATA_DIR
application.APP_ID = "io.github.veritasx1.LiNotesDemo"
OUT = os.path.join(SCRATCH, "examples")
os.makedirs(OUT, exist_ok=True)
DAY = 86400
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from demo_texts import EN, FR, translator  # noqa: E402  – LINOTES_LANGUAGE=en|fr: contents in that language
EN.update({"Dr. K. Brandt (Safety)": "Dr K. Brandt (Safety)", "Bremse Nord (Test)": "Brakes North (Test)",
           "Lena (Entwicklung)": "Lena (development)", "Claude (KI-Konto)": "Claude (AI account)"})
FR.update({"Bremse Nord (Test)": "Freins Nord (Test)", "Lena (Entwicklung)": "Lena (développement)",
           "Claude (KI-Konto)": "Claude (compte IA)"})
EN.update({"dienstlich": "business", "privat": "private", "gesamt": "total", "i. O.": "OK", "n. i. O.": "not OK", "offen": "open"})
FR.update({"dienstlich": "professionnel", "privat": "privé", "gesamt": "total", "i. O.": "OK", "n. i. O.": "non OK", "offen": "ouvert"})
L, TRANSLATE = translator(os.environ.get("LINOTES_LANGUAGE", "de"))


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
    tex = widget.get_native().get_renderer().render_texture(node, Graphene.Rect().init(0, 0, w * scale, h * scale))
    tex.save_to_png(os.path.join(OUT, ("dark-" if DARK else "") + name + ".png"))
    print("Bild", name, flush=True)


# ---------------------------------------------------------------- evidence pictures

def report_png(path, title, subtitle, rows, footer=None, chart=None):
    """A test report page as picture: title, table of results (green/red), optional bar chart."""
    width, height = 900, 120 + 34 * len(rows) + (230 if chart else 0) + 50
    surface = cairo.ImageSurface(cairo.FORMAT_RGB24, width, height)
    cr = cairo.Context(surface)
    cr.set_source_rgb(1, 1, 1); cr.paint()
    cr.set_source_rgb(0.12, 0.12, 0.14); cr.select_font_face("Sans", 0, 1); cr.set_font_size(26)
    cr.move_to(32, 50); cr.show_text(L(title))
    cr.select_font_face("Sans", 0, 0); cr.set_font_size(15); cr.set_source_rgb(0.42, 0.42, 0.45)
    cr.move_to(32, 78); cr.show_text(L(subtitle))
    y = 118
    for i, row in enumerate(rows):
        if i % 2 == 0:
            cr.set_source_rgb(0.96, 0.96, 0.97); cr.rectangle(24, y - 22, width - 48, 32); cr.fill()
        x = 34
        for j, cell in enumerate(row):
            ok = cell in ("bestanden", "i. O.", "erfüllt")
            bad = cell in ("nicht bestanden", "n. i. O.", "offen")
            cr.set_source_rgb(*((0.18, 0.62, 0.3) if ok else (0.85, 0.25, 0.2) if bad else (0.12, 0.12, 0.14)))
            cr.select_font_face("Sans", 0, 1 if j == 0 else 0); cr.set_font_size(16)
            cr.move_to(x, y); cr.show_text(L(str(cell)))
            x += [220, 300, 180, 160][j] if j < 4 else 120
        y += 34
    if chart:
        label, values, limit = chart
        top, base = y + 10, y + 190
        cr.set_source_rgb(0.42, 0.42, 0.45); cr.set_font_size(14); cr.move_to(34, top); cr.show_text(L(label))
        bw = (width - 120) / len(values)
        peak = max(max(values), limit) * 1.15
        for i, v in enumerate(values):
            h = (base - top - 20) * v / peak
            cr.set_source_rgb(0.17, 0.44, 0.88) if v <= limit else cr.set_source_rgb(0.85, 0.25, 0.2)
            cr.rectangle(60 + i * bw + 4, base - h, bw - 8, h); cr.fill()
        ly = base - (base - top - 20) * limit / peak
        cr.set_source_rgb(0.85, 0.25, 0.2); cr.set_line_width(2); cr.set_dash([6, 4])
        cr.move_to(52, ly); cr.line_to(width - 40, ly); cr.stroke(); cr.set_dash([])
        cr.move_to(width - 190, ly - 6); cr.set_font_size(13); cr.show_text(L("Grenze ") + str(limit))
        y = base + 20
    if footer:
        cr.set_source_rgb(0.42, 0.42, 0.45); cr.set_font_size(13); cr.move_to(32, height - 22); cr.show_text(L(footer))
    surface.write_to_png(path)
    return path


def attach(sync, card_id, files, by, ago_days):
    items = []
    for path in files:
        content = open(path, "rb").read()
        reference = sync.upload_file(content, None)
        fields = model.evidence_fields(sync, content)
        fields.update({"by": by, "at": time.time() - ago_days * DAY})
        items.append({"f": reference, "n": os.path.basename(path), "m": "image/png" if path.endswith(".png") else "text/plain",
                      "b": len(content), **fields})
    sync.update(card_id, notify=False, evidence=items)


# ---------------------------------------------------------------- seed: automotive

def seed_automotive(sync, people):
    now = time.time()
    P = people
    def folder(name, order, parent=None):
        data = {"name": name, "order": order}
        if parent: data["parent"] = parent
        return sync.put("folder", data, None, notify=False)["id"]
    root = folder("EMB Hinterachse – ASIL D", 1)
    f_plan = folder("01 Sicherheitsplan und Konzept", 1, root)
    f_sys = folder("02 System", 2, root)
    f_main = folder("03 Hauptrechner – ASIL C(D)", 3, root)
    f_mon = folder("04 Safety-Monitor – ASIL A(D)", 4, root)
    f_prob = folder("05 Problemlösung", 5, root)
    f_rel = folder("06 Freigabe und Safety Case", 6, root)

    def note(folder_id, blocks, ago_hours, pinned=False):
        data = {"folder": folder_id, "body": blocks, "created": now - ago_hours * 3600 - 7 * DAY, "modified": now - ago_hours * 3600}
        if pinned: data["pinned"] = True
        return sync.put("note", data, None, notify=False)["id"]

    ids = {"root": root, "f_plan": f_plan, "f_sys": f_sys, "f_main": f_main}
    ids["plan_note"] = note(f_plan, [
        {"t": "title", "x": "Sicherheitsplan EMB Hinterachse"},
        {"t": "body", "x": "Item: elektromechanische Bremse Hinterachse mit integrierter Parkbremse. Höchstes ASIL: D (SG-01, SG-02)."},
        {"t": "heading", "x": "Rollen"},
        model.table_block([["Rolle", "Person"], ["Projektleitung", "Olaf W."], ["Safety Manager", "Dr. K. Brandt"],
                           ["SW", "M. Yilmaz"], ["HW", "S. Hansen"], ["Test", "Bremse Nord"]]),
        {"t": "body", "x": "Safety Manager: Sicherheitsplan, Safety Case, Bestätigungsmaßnahmen. SW: Hauptrechner ASIL C(D) und Safety-Monitor ASIL A(D). HW: Schaltplan, FMEDA, Metriken. Test (Zulieferer): HIL und Fahrversuch."},
        {"t": "heading", "x": "Arbeitsweise in LiNotes"},
        {"t": "bullet", "x": "Jede Anforderung und jede Änderung ist eine Karte; Kurz-ID in jedem Commit."},
        {"t": "bullet", "x": "Spalten = Status nach SUP.10: CR → Analyse → Umsetzung → Verifikation → Freigegeben."},
        {"t": "bullet", "x": "Auswirkungsanalyse vor jeder Umsetzung (ISO 26262-8 §8.4.3), Nachweise direkt an der Karte."},
        {"t": "bullet", "x": "Monatlicher Bericht (PDF) als Traceability-Nachweis an Kunde und Assessor."},
    ], 300, pinned=True)
    ids["hara"] = note(f_plan, [
        {"t": "title", "x": "HARA – Gefährdungs- und Risikoanalyse"},
        {"t": "body", "x": "Nach ISO 26262-3 §6. Bewertung je Fahrsituation: Schwere (S), Häufigkeit (E), Beherrschbarkeit (C)."},
        model.table_block([["ID", "S", "E", "C", "ASIL"], ["H-01", "S3", "E4", "C3", "D"], ["H-02", "S3", "E4", "C3", "D"],
                           ["H-03", "S2", "E3", "C3", "B"], ["H-04", "S2", "E4", "C2", "B"]]),
        {"t": "bullet", "x": "H-01 Ungewollte Bremsung Hinterachse – Autobahn, 130 km/h"},
        {"t": "bullet", "x": "H-02 Ausfall der Bremswirkung – Notbremsung in der Stadt"},
        {"t": "bullet", "x": "H-03 Parkbremse löst ungewollt – Fahrzeug steht im Gefälle"},
        {"t": "bullet", "x": "H-04 Verzögerte Bremswirkung – Kolonnenverkehr"},
        {"t": "heading", "x": "Sicherheitsziele"},
        {"t": "bullet", "x": "SG-01 (ASIL D): Keine ungewollte Bremswirkung > 0,2 g an der Hinterachse."},
        {"t": "bullet", "x": "SG-02 (ASIL D): Kein Verlust der angeforderten Bremswirkung."},
        {"t": "bullet", "x": "SG-03 (ASIL B): Kein ungewolltes Lösen der Parkbremse im Stand."},
    ], 280)
    note(f_plan, [
        {"t": "title", "x": "Funktionales Sicherheitskonzept"},
        {"t": "body", "x": "ISO 26262-3 §7. Sichere Zustände: Bremsmoment halten bzw. kontrolliert auf 0 rampen; Fehlerreaktionszeit ≤ 50 ms."},
        {"t": "bullet", "x": "FSR-01: Plausibilisierung der Bremsanforderung über zwei unabhängige Pfade."},
        {"t": "bullet", "x": "FSR-02: Überwachung von Strom, Drehzahl und Klemmkraft des Aktors."},
        {"t": "bullet", "x": "FSR-03: Abschaltpfad unabhängig vom Hauptrechner."},
    ], 260)
    ids["tsc"] = note(f_sys, [
        {"t": "title", "x": "Technisches Sicherheitskonzept"},
        {"t": "body", "x": "ISO 26262-4 §6. ASIL-Dekomposition nach ISO 26262-9 §5: Das ASIL-D-Ziel SG-01 wird auf zwei unabhängige Elemente aufgeteilt."},
        model.table_block([["Element", "ASIL"], ["MCU A", "C(D)"], ["MCU B", "A(D)"], ["Endstufe", "D"]]),
        {"t": "bullet", "x": "MCU A – Hauptrechner: Bremsmomentregelung und Plausibilisierung; eigene Versorgung, eigener Takt."},
        {"t": "bullet", "x": "MCU B – Safety-Monitor: Überwachung und unabhängiger Abschaltpfad; getrennte, diversitäre Software."},
        {"t": "bullet", "x": "Leistungsendstufe: Motoransteuerung mit zwei Abschaltpfaden."},
        {"t": "quote", "x": "Abhängige Fehler (ISO 26262-9 §7): gemeinsame Versorgung, Stecker, Software-Bibliothek – Analyse DFA-07 abgeschlossen."},
        {"t": "heading", "x": "Hardware-Metriken (aus FMEDA, Ziel ASIL D)"},
        model.table_block([["Metrik", "Ziel", "Ist"], ["SPFM", "≥ 99 %", "99,3 %"], ["LFM", "≥ 90 %", "93,1 %"], ["PMHF", "< 10 FIT", "6,4 FIT"]]),
    ], 200, pinned=True)
    note(f_rel, [
        {"t": "title", "x": "Safety Case – Stand C-Muster"},
        {"t": "body", "x": "Argumentation, dass SG-01…SG-03 erfüllt sind (ISO 26262-2 §6.4.8). Nachweise: Berichte der Boards, FMEDA, DFA, Testberichte."},
        {"t": "check", "x": "Sicherheitsplan bestätigt (Confirmation Review CR-02)", "c": True},
        {"t": "check", "x": "HARA und Sicherheitsziele bestätigt (CR-01)", "c": True},
        {"t": "check", "x": "Technisches Sicherheitskonzept bestätigt (CR-03)", "c": True},
        {"t": "check", "x": "Hardware-Metriken ASIL D erfüllt", "c": True},
        {"t": "check", "x": "Software-Verifikation MC/DC 100 % (Hauptrechner)", "c": True},
        {"t": "check", "x": "Functional Safety Assessment (unabhängig)"},
        {"t": "check", "x": "Freigabe für Serienproduktion (ISO 26262-4 §10)"},
    ], 20)
    note(f_rel, [
        {"t": "title", "x": "Protokoll Confirmation Review CR-03"},
        {"t": "body", "x": "Prüfer: Dr. K. Brandt (I3, unabhängig). Gegenstand: Technisches Sicherheitskonzept v1.4. Ergebnis: bestätigt mit 2 Auflagen."},
        {"t": "number", "x": "Auflage: DFA-07 um Steckerausfall ergänzen – erledigt (Karte im System-Board)."},
        {"t": "number", "x": "Auflage: Fehlerreaktionszeit im HIL nachweisen – erledigt, Nachweis an Karte."},
    ], 70)

    # --- development boards
    cols = ["CR", "Analyse", "Umsetzung", "Verifikation", "Freigegeben"]

    def board(name, folder_id, order):
        b = sync.put("board", {"name": name, "order": order, "dev": True, "folder": folder_id}, None, notify=False)["id"]
        c = {n: sync.put("column", {"board": b, "name": n, "order": i}, None, notify=False)["id"] for i, n in enumerate(cols)}
        return b, c

    def hist(c, steps):
        return [{"c": c[n], "n": n, "at": now - ago * DAY, "by": by} for n, ago, by in steps]

    def card(b, c, column, title, prio, color, assignee, notes, impact, verification, version, commits, steps, order):
        data = {"board": b, "column": c[column], "title": title, "order": order, "priority": prio, "color": color,
                "assignee": assignee, "notes": notes, "created": now - steps[0][1] * DAY, "created_by": steps[0][2],
                "history": hist(c, steps)}
        for k, v in (("impact", impact), ("verification", verification), ("version", version)):
            if v: data[k] = v
        if commits: data["commits"] = [{"h": h, "s": s} for h, s in commits]
        if column == cols[-1]: data["done_at"] = now - steps[-1][1] * DAY
        return sync.put("card", data, None, notify=False)["id"]

    ev = os.path.join(SCRATCH, "evidence-demo"); os.makedirs(ev, exist_ok=True)
    sysb, sysc = board("EMB System – Anforderungen und Änderungen", f_sys, 1)
    ids["sys_board"] = sysb
    S = []
    S.append(card(sysb, sysc, "Freigegeben", "SysRS-012 Fehlerreaktionszeit ≤ 50 ms", "hoch", "rot", P["safety"],
        "Aus FSR-02. Gilt für beide Abschaltpfade.",
        "ASIL D (SG-01). Betrifft Hauptrechner, Safety-Monitor und Endstufe. Timing-Analyse und HIL-Fehlerinjektion erforderlich.",
        "Kriterien:\n• Fehlerreaktionszeit ≤ 50 ms für alle 24 Fehlerfälle\n• Nachweis im HIL mit Fehlerinjektion\nNachweis: HIL-Bericht FI-2026-09 (24/24 i. O., max. 38 ms), siehe Nachweise.",
        "SW 2.3.0 / HW C2", [("e19a2c4", "Abschaltpfad: Watchdog-Fenster 20 ms"), ("77b03de", "Monitor: Stromgrenzwert-Überwachung")],
        [("CR", 60, P["safety"]), ("Analyse", 55, P["safety"]), ("Umsetzung", 48, P["sw"]), ("Verifikation", 20, P["test"]), ("Freigegeben", 9, P["safety"])], 1))
    attach(sync, S[-1], [report_png(os.path.join(ev, "HIL-Fehlerinjektion FI-2026-09.png"), "HIL-Fehlerinjektion FI-2026-09",
        "EMB Hinterachse · C2-Muster · Prüfstand HIL-3 · 24 Fehlerfälle",
        [["Fehlerfall", "Reaktion", "Zeit", "Ergebnis"], ["Kurzschluss Phase U", "Abschaltung", "31 ms", "i. O."],
         ["Drehzahlsensor eingefroren", "Moment halten", "38 ms", "i. O."], ["CAN-Timeout Anforderung", "Rampe auf 0", "22 ms", "i. O."],
         ["MCU-A Reset", "Monitor übernimmt", "17 ms", "i. O."]],
        "Bestanden: 24 von 24 · Maximalwert 38 ms · Grenze 50 ms",
        ("Fehlerreaktionszeit je Fehlerfall [ms]", [31, 38, 22, 17, 29, 35, 26, 19, 33, 28, 24, 30], 50))], P["test"], 20)
    S.append(card(sysb, sysc, "Freigegeben", "DFA-07 um Steckerausfall ergänzen", "mittel", "orange", P["hw"],
        "Auflage aus Confirmation Review CR-03.", "ASIL D (SG-01/02). Nur Analyse-Dokument, keine Designänderung erwartet.",
        "Kriterien:\n• Steckerausfall als gemeinsame Ursache bewertet\n• Maßnahme festgelegt\nNachweis: DFA-07 v1.5, Review RV-221 abgeschlossen.", "Doku C2", [],
        [("CR", 40, P["safety"]), ("Analyse", 38, P["hw"]), ("Umsetzung", 33, P["hw"]), ("Verifikation", 29, P["safety"]), ("Freigegeben", 27, P["safety"])], 2))
    S.append(card(sysb, sysc, "Verifikation", "SysRS-031 Parkbremse hält 30 % Gefälle", "hoch", "orange", P["test"],
        "Kundenanforderung Lastenheft 4.2.7.", "ASIL B (SG-03). Klemmkraft-Kennlinie, Nachspannfunktion. Regressionsumfang: Parkbrems-Tests PB-01…PB-12.",
        "Kriterien:\n• 30 % Gefälle, 2,5 t, 30 min ohne Rollen\n• Nachspannen bei Abkühlung\nNachweis: Prüfstand i. O. (siehe Nachweise), Fahrversuch Gefällestrecke offen.",
        "SW 2.4.0", [("c3d9f10", "Parkbremse: Nachspannen nach Temperaturmodell")],
        [("CR", 25, P["pm"]), ("Analyse", 22, P["safety"]), ("Umsetzung", 15, P["sw"]), ("Verifikation", 4, P["test"])], 3))
    attach(sync, S[-1], [report_png(os.path.join(ev, "Prüfstand Parkbremse PB-07.png"), "Prüfstand Parkbremse PB-07",
        "30 % Gefälle · 2,5 t · Klemmkraft über 30 min",
        [["Messpunkt", "Klemmkraft", "Weg", "Ergebnis"], ["0 min", "18,2 kN", "0,0 mm", "i. O."], ["10 min", "17,9 kN", "0,0 mm", "i. O."],
         ["30 min", "17,6 kN", "0,1 mm", "i. O."]], "Nachspannen ausgelöst bei 17,5 kN (Temperaturmodell)",
        ("Klemmkraft [kN] alle 3 min", [18.2, 18.1, 18.0, 17.9, 17.9, 17.8, 17.8, 17.7, 17.7, 17.6], 17.5))], P["test"], 4)
    S.append(card(sysb, sysc, "Umsetzung", "CR-118 Rekuperation: Bremskraftverteilung anpassen", "mittel", "blau", P["sw"],
        "Änderungswunsch Kunde (Rekuperation E-Achse vorn).",
        "ASIL D (SG-02) mittelbar: Verteilung darf Gesamtbremswirkung nicht mindern. Betrifft Hauptrechner (Regler), nicht Monitor. Regressions: HIL BR-01…BR-20, Fahrversuch Winter.",
        None, None, [("5aa0e71", "Regler: Verteilungskennfeld Rekuperation")],
        [("CR", 12, P["pm"]), ("Analyse", 9, P["safety"]), ("Umsetzung", 3, P["sw"])], 4))
    S.append(card(sysb, sysc, "Analyse", "CR-121 Neuer Drehzahlsensor (Lieferantenwechsel)", "hoch", "rot", P["safety"],
        "Einkauf: Sensor S2 wird abgekündigt.",
        "ASIL D betroffen (Drehzahl ist Eingang für FSR-02). FMEDA neu bewerten, SPFM/LFM prüfen, Qualifikation AEC-Q100, Software-Treiber.",
        None, None, [], [("CR", 6, P["pm"]), ("Analyse", 2, P["safety"])], 5))
    S.append(card(sysb, sysc, "CR", "CR-124 Diagnose: Verschleißanzeige Bremsbelag", "niedrig", "grün", None,
        "Wunsch Kundendienst.", None, None, None, [], [("CR", 1, P["pm"])], 6))

    mainb, mainc = board("Hauptrechner (MCU A) – ASIL C(D)", f_main, 2)
    ids["main_board"] = mainb
    M = []
    M.append(card(mainb, mainc, "Freigegeben", "SWRS-A-044 Plausibilisierung Bremsanforderung (2 Pfade)", "hoch", "rot", P["sw"],
        "Aus TSR-05.", "ASIL C(D). Neue SW-Einheit ReqPlaus; Schnittstellen CAN-Empfang und SENT-Pedalwert. Unabhängigkeit zum Monitor wahren (keine gemeinsame Bibliothek).",
        "Kriterien:\n• Abweichung > 8 % für > 20 ms → sicherer Zustand\n• MC/DC-Abdeckung 100 % (ASIL C)\nNachweis: Unit-Tests 64/64, MC/DC 100 %, Review RV-198.",
        "SW 2.3.0", [("91fe0b2", "ReqPlaus: Zwei-Pfad-Vergleich"), ("a07c331", "Tests: Grenzfälle ReqPlaus")],
        [("CR", 70, P["safety"]), ("Analyse", 66, P["sw"]), ("Umsetzung", 58, P["sw"]), ("Verifikation", 40, P["test"]), ("Freigegeben", 31, P["safety"])], 1))
    attach(sync, M[-1], [report_png(os.path.join(ev, "MC-DC Abdeckung SW 2.3.0.png"), "Strukturabdeckung SW 2.3.0 – Hauptrechner",
        "ISO 26262-6 Tab. 9 · ASIL C: MC/DC empfohlen ++",
        [["Einheit", "Anweisung", "Zweig", "MC/DC"], ["ReqPlaus", "100 %", "100 %", "100 %"], ["TorqueCtrl", "100 %", "100 %", "100 %"],
         ["ParkBrake", "100 %", "98,7 %", "98,7 %"]], "ParkBrake: 1 nicht erreichbarer Zweig begründet (RV-205)",
        ("MC/DC je Einheit [%]", [100, 100, 98.7, 100, 100, 99.4], 100))], P["test"], 40)
    M.append(card(mainb, mainc, "Verifikation", "SWRS-A-051 Momentenregler: Begrenzung 2 kNm/s", "hoch", "orange", P["test"],
        "", "ASIL C(D). Reglerparameter, Rampenbegrenzer. Regression: Back-to-Back Modell/Code.",
        "Kriterien:\n• Back-to-Back Modell ↔ Code, Abweichung < 1 %\n• HIL-Rampentests R-01…R-08\nNachweis: Back-to-Back i. O., HIL offen.",
        "SW 2.4.0", [("44d18aa", "TorqueCtrl: Gradientenbegrenzung")],
        [("CR", 30, P["safety"]), ("Analyse", 27, P["sw"]), ("Umsetzung", 18, P["sw"]), ("Verifikation", 5, P["test"])], 2))
    M.append(card(mainb, mainc, "Umsetzung", "SWRS-A-060 Treiber Drehzahlsensor S3", "hoch", "rot", P["sw"],
        "Folge von CR-121.", "ASIL C(D). Neuer Treiber, alte Schnittstelle bleibt. Statische Analyse (MISRA C:2012) und Unit-Tests.",
        None, None, [], [("CR", 2, P["safety"]), ("Analyse", 2, P["sw"]), ("Umsetzung", 1, P["sw"])], 3))
    M.append(card(mainb, mainc, "CR", "MISRA-Abweichung Regel 11.5 begründen", "niedrig", "grün", None, "", None, None, None, [],
        [("CR", 3, P["sw"])], 4))

    monb, monc = board("Safety-Monitor (MCU B) – ASIL A(D)", f_mon, 3)
    ids["mon_board"] = monb
    card(monb, monc, "Freigegeben", "SWRS-B-010 Unabhängiger Abschaltpfad", "hoch", "rot", P["sw"], "Aus FSR-03.",
        "ASIL A(D). Diversitäre Implementierung, keine gemeinsame Bibliothek mit MCU A (DFA-03).",
        "Kriterien:\n• Abschaltung ohne MCU A in ≤ 20 ms\nNachweis: HIL FI-2026-09 Fall 14–18 i. O.", "MON 1.2.0",
        [("0b7f2e9", "Monitor: Abschaltpfad über GPIO-Kette")],
        [("CR", 62, P["safety"]), ("Analyse", 60, P["sw"]), ("Umsetzung", 50, P["sw"]), ("Verifikation", 21, P["test"]), ("Freigegeben", 15, P["safety"])], 1)
    card(monb, monc, "Verifikation", "SWRS-B-014 Fensterwatchdog für MCU A", "hoch", "orange", P["test"], "",
        "ASIL A(D). Zeitfenster 10–30 ms; Fehlauslösung prüfen (Verfügbarkeit).",
        "Kriterien:\n• Auslösung bei < 10 ms und > 30 ms\n• Keine Fehlauslösung in 1000 h Dauerlauf\nNachweis: 640 h ohne Fehlauslösung (läuft).",
        "MON 1.3.0", [("e2c1d40", "Watchdog: Fenster 10–30 ms")],
        [("CR", 28, P["safety"]), ("Analyse", 26, P["sw"]), ("Umsetzung", 16, P["sw"]), ("Verifikation", 8, P["test"])], 2)
    card(monb, monc, "Analyse", "Monitor: Stromgrenze an Sensor S3 anpassen", "mittel", "blau", P["safety"], "Folge von CR-121.",
        "ASIL A(D). Nur Grenzwerte; Unabhängigkeit bleibt.", None, None, [], [("CR", 2, P["safety"]), ("Analyse", 1, P["safety"])], 3)

    probb, probc = board("Fehlerberichte (Problemlösung)", f_prob, 4)
    ids["prob_board"] = probb
    for col in ("Analyse", "Umsetzung", "Verifikation", "Freigegeben"):
        pass
    card(probb, probc, "Freigegeben", "PR-031 Fehlauslösung Watchdog bei Kaltstart −40 °C", "hoch", "rot", P["sw"],
        "Gefunden im Klimakammertest (Zulieferer).", "Verfügbarkeit, kein Sicherheitsziel verletzt (sicherer Zustand erreicht). Ursache: Oszillator-Anlaufzeit.",
        "Kriterien:\n• 50 Kaltstarts −40 °C ohne Fehlauslösung\nNachweis: Klimakammer 50/50 i. O.", "MON 1.2.1", [("d1f0a33", "Watchdog: Anlaufzeit Oszillator berücksichtigen")],
        [("CR", 35, P["test"]), ("Analyse", 34, P["sw"]), ("Umsetzung", 30, P["sw"]), ("Verifikation", 26, P["test"]), ("Freigegeben", 24, P["safety"])], 1)
    card(probb, probc, "Umsetzung", "PR-037 CAN-Fehlerzähler läuft nach Busoff nicht zurück", "mittel", "orange", P["sw"],
        "Fahrversuch Kalenderwoche 38.", "QM (Diagnose). Kein Einfluss auf SG-01…03.", None, None, [],
        [("CR", 9, P["test"]), ("Analyse", 7, P["sw"]), ("Umsetzung", 2, P["sw"])], 2)
    card(probb, probc, "CR", "PR-040 Geräusch beim Lösen der Parkbremse", "niedrig", "grün", None, "Kundendienst-Meldung.", None, None, None, [],
        [("CR", 1, P["pm"])], 3)

    # --- plan and checklist
    today = datetime.date.today()
    start = today - datetime.timedelta(days=150)
    def at(days): return (start + datetime.timedelta(days=days)).isoformat()
    ids["plan"] = sync.put("plan", {"name": "EMB Projektplan bis SOP", "order": 1, "mode": "timeline", "folder": root, "tasks": [
        {"x": "Konzeptphase (Teil 3)", "from": at(0), "to": at(40), "k": "blue"},
        {"x": "Confirmation Review HARA", "from": at(38), "to": at(38), "k": "purple", "m": True},
        {"x": "System (Teil 4) – TSC", "from": at(30), "to": at(90), "k": "orange"},
        {"x": "B-Muster", "from": at(60), "to": at(110), "k": "grey"},
        {"x": "HW (Teil 5) – FMEDA", "from": at(70), "to": at(140), "k": "pink"},
        {"x": "SW (Teil 6) – MCU A / MCU B", "from": at(80), "to": at(200), "k": "mint"},
        {"x": "C-Muster", "from": at(120), "to": at(190), "k": "grey"},
        {"x": "Integration und Test (Teil 4 §7)", "from": at(150), "to": at(230), "k": "orange"},
        {"x": "Functional Safety Assessment", "from": at(225), "to": at(235), "k": "purple"},
        {"x": "SOP", "from": at(250), "to": at(250), "k": "pink", "m": True}]}, None, notify=False)["id"]
    lst = sync.put("list", {"name": "Bestätigungsmaßnahmen (Teil 2)", "order": 3, "folder": f_rel}, None, notify=False)["id"]
    for i, (text, done) in enumerate([("Confirmation Review HARA (I3)", True), ("Confirmation Review Sicherheitsplan (I3)", True),
                                       ("Confirmation Review TSC (I3)", True), ("Confirmation Review Safety Case (I3)", False),
                                       ("Functional Safety Audit (I3)", True), ("Functional Safety Assessment (I3)", False)]):
        sync.put("item", {"list": lst, "text": text, "done": done, "order": i, "by": P["safety"]}, None, notify=False)
    ids["checklist"] = lst
    return ids


# ---------------------------------------------------------------- seed: software with AI

def seed_ai(sync, people):
    now = time.time()
    P = people
    root = sync.put("folder", {"name": "Fahrtenbuch-App", "order": 2}, None, notify=False)["id"]
    rules = sync.put("note", {"folder": root, "pinned": True, "created": now - 20 * DAY, "modified": now - 2 * DAY, "body": [
        {"t": "title", "x": "Arbeitsregeln für die KI"},
        {"t": "body", "x": "Diese Notiz ist mit dem KI-Konto geteilt. Sie gilt wie eine Absprache mit einem neuen Teammitglied."},
        {"t": "number", "x": "Arbeite nur an Karten, die dir zugewiesen sind. Schiebe sie beim Start nach „In Arbeit“."},
        {"t": "number", "x": "Ein Commit je Karte, die Karten-ID in eckigen Klammern in der Nachricht."},
        {"t": "number", "x": "Fertig heißt: Tests grün, Kommentar mit Ursache / Änderung / Test, Nachweise angehängt, Karte nach „Testing“."},
        {"t": "number", "x": "Nach „Erledigt“ schiebt nur ein Mensch. Bei Unklarheiten: Frage als Kommentar, Karte bleibt stehen."},
        {"t": "number", "x": "Keine Zugangsdaten, keine Kundendaten in Commits oder Karten."},
    ]}, None, notify=False)["id"]
    b = sync.put("board", {"name": "Fahrtenbuch – Entwicklung", "order": 1, "dev": True, "folder": root}, None, notify=False)["id"]
    names = ["Offen", "In Arbeit", "Testing", "Erledigt"]
    c = {n: sync.put("column", {"board": b, "name": n, "order": i}, None, notify=False)["id"] for i, n in enumerate(names)}
    ev = os.path.join(SCRATCH, "evidence-demo"); os.makedirs(ev, exist_ok=True)

    def card(column, title, prio, color, assignee, notes, verification, version, commits, steps, order):
        data = {"board": b, "column": c[column], "title": title, "order": order, "priority": prio, "color": color, "assignee": assignee,
                "notes": notes, "created": now - steps[0][1] * DAY, "created_by": steps[0][2],
                "history": [{"c": c[n], "n": n, "at": now - ago * DAY, "by": by} for n, ago, by in steps]}
        if verification: data["verification"] = verification
        if version: data["version"] = version
        if column == "Erledigt": data["done_at"] = now - steps[-1][1] * DAY
        card_id = sync.put("card", data, None, notify=False)["id"]
        if commits:  # the commit messages name the real card id, as the AI does
            sync.update(card_id, notify=False, commits=[{"h": h, "s": f"{s} [{card_id[:8]}]"} for h, s in commits])
        return card_id

    ai, me, tester = P["ai"], P["pm"], P["test"]
    ids = {"ai_root": root, "ai_board": b, "rules": rules}
    card("Erledigt", "Fahrten als CSV exportieren", "mittel", "blau", ai,
        "Für die Steuererklärung: alle Fahrten eines Jahres als CSV (Excel).\n\n[KI 28.09. 10:14] Änderung: Export-Menü „CSV (Excel)“, Semikolon und BOM für deutsches Excel, Kilometer mit Komma. Test: 3 neue Unit-Tests, Export von 120 Beispielfahrten geprüft.",
        "Kriterien:\n• Öffnet direkt in deutschem Excel\n• Summe km stimmt mit App überein\nNachweis: Testprotokoll und Screenshot angehängt.", "1.2.0",
        [("8c1f2d0", "Export: CSV mit Semikolon und BOM")],
        [("Offen", 9, me), ("In Arbeit", 8, ai), ("Testing", 7, ai), ("Erledigt", 6, me)], 1)
    t = card("Testing", "Privat- und Dienstfahrten trennen", "hoch", "orange", ai,
        "Finanzamt verlangt getrennte Summen.\n\n[KI 02.10. 16:40] Ursache/Plan: Fahrt bekommt ein Feld „Art“ (privat/dienstlich), Standard dienstlich. Änderung: Feld, Filter, Summen je Art im Jahresbericht. Test: 12 Unit-Tests, Migration alter Daten (alle → dienstlich), UI-Test.\n\n[Olaf 02.10. 18:05] Bitte im Jahresbericht die Summen fett.\n\n[KI 02.10. 18:22] Erledigt, Screenshot aktualisiert.",
        "Kriterien:\n• Jede Fahrt hat eine Art\n• Jahresbericht zeigt Summen getrennt\n• Alte Fahrten werden „dienstlich“\nNachweis: Testprotokoll (12/12), Screenshot Jahresbericht.", "1.3.0",
        [("f2a7b19", "Fahrtart privat/dienstlich"), ("0c9e4a8", "Jahresbericht: Summen fett")],
        [("Offen", 4, me), ("In Arbeit", 2, ai), ("Testing", 1, ai)], 2)
    ids["ai_card"] = t
    log = os.path.join(ev, "Testprotokoll 1.3.0.txt")
    open(log, "w").write(L("Testlauf 02.10.2026 18:20 – Commit 0c9e4a8\n\ntest_trip_kind.py ........ 8 bestanden\ntest_migration.py .... 4 bestanden\n\n12 bestanden, 0 fehlgeschlagen\n"))
    attach(sync, t, [log, report_png(os.path.join(ev, "Jahresbericht 2026 – Summen.png"), "Jahresbericht 2026",
        "Fahrtenbuch-App 1.3.0 · Beispieldaten", [["Art", "Fahrten", "Kilometer", ""], ["dienstlich", "214", "18 402 km", ""],
        ["privat", "96", "4 117 km", ""], ["gesamt", "310", "22 519 km", ""]], "Summen fett, getrennt nach Art")], ai, 1)
    card("In Arbeit", "Kilometerstand per Foto erfassen", "mittel", "lila", P["dev"],
        "Tacho fotografieren, Zahl wird erkannt (auf dem Gerät).", None, None, [], [("Offen", 3, me), ("In Arbeit", 1, P["dev"])], 3)
    card("In Arbeit", "Tests für Export ergänzen (Grenzfälle Jahreswechsel)", "niedrig", "grün", ai,
        "[KI 03.10. 08:02] Gestartet. Frage: Soll eine Fahrt über Silvester ins alte oder neue Jahr zählen?\n\n[Olaf 03.10. 08:10] Ins Jahr des Fahrtbeginns.",
        None, None, [], [("Offen", 2, tester), ("In Arbeit", 0.2, ai)], 4)
    card("Offen", "Dunkler Modus für den Jahresbericht", "niedrig", "blau", None, "", None, None, [], [("Offen", 1, me)], 5)
    card("Offen", "Fahrzeug wechseln (mehrere Autos)", "mittel", "orange", tester, "", None, None, [], [("Offen", 0.5, me)], 6)
    return ids


# ---------------------------------------------------------------- run

def open_card(win, card_id, scroll_to_evidence=False):
    from linotes.kanban import CardDialog
    dialog = CardDialog(win.board_view, win.sync.get(card_id))
    dialog.present(win)
    win._demo_dialog = dialog
    if scroll_to_evidence:
        GLib.timeout_add(450, lambda: (dialog.evidence_rows[-1].grab_focus(), False)[1])


def reports(sync, ids):
    import subprocess
    from linotes import report
    for key, name in (("sys_board", "bericht-system"), ("main_board", "bericht-hauptrechner"), ("ai_board", "bericht-ki")):
        path = os.path.join(OUT, name + ".pdf")
        report.write_pdf(report.build(sync, ids[key]), path)
        subprocess.run(["pdftoppm", "-r", "110", "-png", path, os.path.join(OUT, name)], check=True)
    print("Bild berichte", flush=True)


def run(app):
    win = app.get_active_window()
    sync = win.sync
    if not sync.is_local:
        win.on_local(None, "Olaf W.")
    if DARK:
        Adw.StyleManager.get_default().set_color_scheme(Adw.ColorScheme.FORCE_DARK)
    win.set_default_size(1560, 900)
    win.unmaximize()
    put, update = sync.put, sync.update
    sync.put = lambda kind, data, *args, **kwargs: put(kind, TRANSLATE(data), *args, **kwargs)
    sync.update = lambda object_id, *args, **fields: update(object_id, *args, **TRANSLATE(fields))
    model.ensure_defaults(sync)
    # Team members of the examples (only in this isolated demo data).
    people = {"pm": sync.user_id}
    for uid, (key, name) in enumerate([("safety", "Dr. K. Brandt (Safety)"), ("sw", "M. Yilmaz (SW)"), ("hw", "S. Hansen (HW)"),
                                       ("test", "Bremse Nord (Test)"), ("dev", "Lena (Entwicklung)"), ("ai", "Claude (KI-Konto)")], start=2):
        sync.state["users"].append({"id": uid, "name": L(name), "username": key})
        people[key] = uid
    ids = seed_automotive(sync, people)
    ids.update(seed_ai(sync, people))
    win.sidebar.refresh()
    sys_card = next(c["id"] for c in sync.objects("card") if c["data"].get("title", "").startswith("SysRS-012"))
    steps = [
        ("a1-projektordner", lambda: (win.sidebar.select("folder:" + ids["f_plan"]), win.select("folder:" + ids["f_plan"]), win.open_note(ids["plan_note"]))),
        ("a2-hara", lambda: win.open_note(ids["hara"])),
        ("a3-sicherheitskonzept", lambda: (win.sidebar.select("folder:" + ids["f_sys"]), win.select("folder:" + ids["f_sys"]), win.open_note(ids["tsc"]))),
        ("a4-systemboard", lambda: (win.sidebar.select("board:" + ids["sys_board"]), win.select("board:" + ids["sys_board"]), win.split.set_show_sidebar(False))),
        ("a5-karte", lambda: open_card(win, sys_card)),
        ("a6-nachweise", lambda: open_card(win, sys_card, True)),
        ("a7-hauptrechner", lambda: (win.select("board:" + ids["main_board"]))),
        ("a8-monitor", lambda: (win.select("board:" + ids["mon_board"]))),
        ("a9-fehlerberichte", lambda: (win.select("board:" + ids["prob_board"]))),
        ("a10-projektplan", lambda: (win.split.set_show_sidebar(True), win.sidebar.select("plan:" + ids["plan"]), win.select("plan:" + ids["plan"]))),
        ("a11-bestaetigung", lambda: (win.sidebar.select("list:" + ids["checklist"]), win.select("list:" + ids["checklist"]))),
        ("k1-regeln", lambda: (win.sidebar.select("folder:" + ids["ai_root"]), win.select("folder:" + ids["ai_root"]), win.open_note(ids["rules"]))),
        ("k2-board", lambda: (win.sidebar.select("board:" + ids["ai_board"]), win.select("board:" + ids["ai_board"]), win.split.set_show_sidebar(False))),
        ("k3-karte", lambda: open_card(win, ids["ai_card"])),
        ("k4-nachweise", lambda: open_card(win, ids["ai_card"], True)),
        ("berichte", lambda: reports(sync, ids)),
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
            if name != "berichte":
                shot(win, name)
            dialog = getattr(win, "_demo_dialog", None)
            if dialog is not None:
                dialog.close()
                win._demo_dialog = None
            GLib.timeout_add(200, lambda: next_step(index + 1))
            return False
        GLib.timeout_add(1300, after)
        return False
    GLib.timeout_add(1200, lambda: next_step(0))


app = App()
app.connect("activate", lambda a: GLib.idle_add(lambda: run(a) and False))
app.run([])
