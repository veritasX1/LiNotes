"""Overview of the keyboard shortcuts (Ctrl+? or F1), like the list in Apple's Notes help."""

import gi

gi.require_version("Adw", "1")

from gi.repository import Adw

SECTIONS = [
    ("Allgemein", [
        ("Neue Notiz", "<Control>n"),
        ("Neuer Ordner", "<Control><Shift>n"),
        ("Suchen", "<Control>f"),
        ("Notiz duplizieren", "<Control>d"),
        ("Notiz in eigenem Fenster öffnen (oder Doppelklick)", "<Control>o"),
        ("Notizfenster schließen", "<Control>w"),
        ("Als Liste / als Galerie anzeigen", "<Control>1 <Control>2"),
        ("Textgröße größer / kleiner / normal", "<Control>plus <Control>minus <Control>0"),
        ("Als PDF exportieren", "<Control><Shift>e"),
        ("Drucken", "<Control>p"),
        ("Gesperrte Notizen sperren", "<Control><Alt>l"),
        ("Tastenkürzel anzeigen", "<Control>question F1"),
        ("Beenden", "<Control>q"),
    ]),
    ("Text formatieren", [
        ("Fett", "<Control>b"),
        ("Kursiv", "<Control>i"),
        ("Unterstrichen", "<Control>u"),
        ("Markieren (gelb)", "<Control><Alt>h"),
        ("Titel", "<Control><Shift>t"),
        ("Überschrift", "<Control><Shift>h"),
        ("Unterüberschrift", "<Control><Shift>j"),
        ("Text", "<Control><Shift>b"),
        ("Monospace", "<Control><Shift>m"),
        ("Zitat", "<Control>apostrophe"),
        ("Trennlinie (oder --- und Enter)", "<Control><Shift>d"),
        ("Mit Notiz verlinken (oder >> tippen)", "<Control>k"),
    ]),
    ("Listen", [
        ("Aufzählung", "<Control><Shift>7"),
        ("Liste mit Strichen", "<Control><Shift>8"),
        ("Nummerierte Liste", "<Control><Shift>9"),
        ("Checkliste", "<Control><Shift>l"),
        ("Abhaken / Haken entfernen", "<Control><Shift>u"),
        ("Einrücken / Ausrücken", "Tab <Shift>Tab"),
        ("Zeile nach oben / unten verschieben", "<Control><Alt>Up <Control><Alt>Down"),
    ]),
]


def shortcuts_dialog():
    dialog = Adw.ShortcutsDialog()
    for title, items in SECTIONS:
        section = Adw.ShortcutsSection(title=title)
        for label, accelerator in items:
            section.add(Adw.ShortcutsItem(title=label, accelerator=accelerator))
        dialog.add(section)
    return dialog
