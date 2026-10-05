"""Overview of the keyboard shortcuts (Ctrl+? or F1), like the list in Apple's Notes help."""

import gi

gi.require_version("Adw", "1")

from gi.repository import Adw
from .i18n import _

SECTIONS = [
    (_("Allgemein"), [
        (_("Neue Notiz"), "<Control>n"),
        (_("Neuer Ordner"), "<Control><Shift>n"),
        (_("Suchen (im Board: Karten suchen)"), "<Control>f"),
        (_("Notiz duplizieren"), "<Control>d"),
        (_("Notiz in eigenem Fenster öffnen (oder Doppelklick)"), "<Control>o"),
        (_("Notizfenster schließen"), "<Control>w"),
        (_("Als Liste / als Galerie anzeigen"), "<Control>1 <Control>2"),
        (_("Textgröße größer / kleiner / normal"), "<Control>plus <Control>minus <Control>0"),
        (_("Als PDF exportieren"), "<Control><Shift>e"),
        (_("Drucken"), "<Control>p"),
        (_("Gesperrte Notizen sperren"), "<Control><Alt>l"),
        (_("Tastenkürzel anzeigen"), "<Control>question F1"),
        (_("Beenden"), "<Control>q"),
    ]),
    (_("Text formatieren"), [
        (_("Fett"), "<Control>b"),
        (_("Kursiv"), "<Control>i"),
        (_("Unterstrichen"), "<Control>u"),
        (_("Markieren (gelb)"), "<Control><Alt>h"),
        (_("Titel"), "<Control><Shift>t"),
        (_("Überschrift"), "<Control><Shift>h"),
        (_("Unterüberschrift"), "<Control><Shift>j"),
        (_("Text"), "<Control><Shift>b"),
        (_("Monospace"), "<Control><Shift>m"),
        (_("Zitat"), "<Control>apostrophe"),
        (_("Trennlinie (oder --- und Enter)"), "<Control><Shift>d"),
        (_("Mit Notiz verlinken (oder >> tippen)"), "<Control>k"),
    ]),
    (_("Listen"), [
        (_("Aufzählung"), "<Control><Shift>7"),
        (_("Liste mit Strichen"), "<Control><Shift>8"),
        (_("Nummerierte Liste"), "<Control><Shift>9"),
        (_("Checkliste"), "<Control><Shift>l"),
        (_("Abhaken / Haken entfernen"), "<Control><Shift>u"),
        (_("Einrücken / Ausrücken"), _("Tab <Shift>Tab")),
        (_("Zeile nach oben / unten verschieben"), "<Control><Alt>Up <Control><Alt>Down"),
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
