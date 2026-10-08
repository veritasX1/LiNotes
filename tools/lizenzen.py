#!/usr/bin/env python3
"""Rechtshinweis (Richard/Michelle 08.10., card 5f4aee29; wie LiMail 91b79ccc): baut shared/lizenzen/lizenzen.json –
LiNotes selbst, was es mitliefert (QR-Code-Bibliothek) und was es unter Ubuntu vom System nutzt, jeweils mit Lizenz.
Ubuntu zeigt es im Info-Dialog unter „Rechtliches“.

    python3 tools/lizenzen.py

Die Texte kommen aus der mitgelieferten Datei selbst (Kopf von qrcodegen.py) und aus
/usr/share/common-licenses (GPL-3). Neue Bibliothek: unten eintragen, Skript laufen lassen, Datei committen."""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "shared" / "lizenzen" / "lizenzen.json"
LINOTES = ROOT / "linux" / "linotes"

# Name, Version, Lizenz (SPDX), Text-Schlüssel ("" = kein Text, Systempaket), Verwendung
SHIPPED = [
    ("QR Code generator library (Project Nayuki)", "–", "MIT", "qrcodegen", "QR-Codes zum Teilen und Anmelden (mitgeliefert)"),
]
UBUNTU = [
    ("GTK 4, libadwaita, GLib, Pango, GdkPixbuf", "Ubuntu", "LGPL-2.1-or-later", "", "Oberfläche (Ubuntu-Pakete, nicht mitgeliefert)"),
    ("Graphene", "Ubuntu", "MIT", "", "Grafik der Oberfläche (Ubuntu-Paket)"),
    ("GStreamer", "Ubuntu", "LGPL-2.1-or-later", "", "Sprachnotizen (Ubuntu-Paket)"),
    ("libsecret", "Ubuntu", "LGPL-2.1-or-later", "", "Schlüsselbund (Ubuntu-Paket)"),
    ("PyGObject", "Ubuntu", "LGPL-2.1-or-later", "", "Python-Anbindung (Ubuntu-Paket)"),
    ("pycairo", "Ubuntu", "LGPL-2.1-only / MPL-1.1", "", "Zeichnen und PDF (Ubuntu-Paket)"),
    ("python3-cryptography", "Ubuntu", "Apache-2.0 / BSD", "", "Ende-zu-Ende-Verschlüsselung (Ubuntu-Paket)"),
    ("Python 3", "Ubuntu", "PSF-2.0", "", "Programmiersprache (Ubuntu-Paket)"),
    ("poppler-utils", "Ubuntu", "GPL-2.0-or-later", "", "PDF-Vorschau (als Programm aufgerufen)"),
]


def reflow(text):
    """Hard line breaks inside a paragraph become spaces so the text wraps in a narrow column (as in LiMail);
    blank lines, indented lines and list items keep their own line."""
    out, para = [], []
    def flush():
        if para:
            out.append(" ".join(para))
            para.clear()
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            flush(); out.append("")
        elif stripped[:2] in ("- ", "* ", "• ") or (stripped[:1].isdigit() and stripped[1:3].strip(". )") == ""):
            flush(); out.append(line.rstrip())
        elif line[:1] in (" ", "\t") and out and out[-1].strip() and not para:
            out[-1] = out[-1].rstrip() + " " + stripped
        elif line[:1] in (" ", "\t"):
            flush(); out.append(line.rstrip())
        else:
            para.append(stripped)
    flush()
    return "\n".join(out).strip() + "\n"


def qrcodegen_text():
    """The MIT notice from the head of qrcodegen.py, without the comment marks."""
    lines = []
    for line in (LINOTES / "qrcodegen.py").read_text(encoding="utf-8").splitlines():
        if not line.startswith("#"):
            break
        lines.append(line[1:].strip())
    return "\n".join(lines).strip()


def main():
    texts = {
        "GPL-3": Path("/usr/share/common-licenses/GPL-3").read_text(encoding="utf-8"),
        "qrcodegen": qrcodegen_text(),
    }
    texts = {name: reflow(text) for name, text in texts.items()}
    entry = lambda e: dict(zip(("name", "version", "license", "text", "use"), e))
    data = {
        "app": {"name": "LiNotes", "license": "GPL-3.0-or-later", "text": "GPL-3", "copyright": "© 2026 Olaf Winkler"},
        "ubuntu": [entry(e) for e in SHIPPED + UBUNTU],
        "texts": texts,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"{OUT.relative_to(ROOT)}: {len(data['ubuntu'])} Einträge, {len(texts)} Lizenztexte, {OUT.stat().st_size // 1024} KB")


if __name__ == "__main__":
    main()
