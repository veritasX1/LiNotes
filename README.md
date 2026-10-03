# LiNotes

Notizen, Listen, Aufgaben und Pläne für **Android** und **Ubuntu** – Ende-zu-Ende verschlüsselt,
auf deinem eigenen Server oder ganz ohne. So einfach wie Apples Notizen, aber die Daten bleiben bei dir.

**Website, Downloads und Hilfe:** https://lisoft.goip.de/linotes/
**Eigener Server in einem Befehl:** https://lisoft.goip.de/linotes/server.html

## Funktionen

- Notizen mit Überschriften, Checklisten, Tabellen, Rechnen (`=`), Fotos, PDFs, Audioaufnahmen,
  Verlinkungen (`>>`), @-Erwähnungen, einklappbaren Abschnitten, Markierungen und gesperrten Notizen
- Listen mit automatischer Sortierung nach Warengruppe
- Aufgaben-Boards, auf Wunsch als Entwicklungsprojekt mit Auswirkungsanalyse, Verifikation,
  verknüpften Commits und Traceability-Matrix
- Pläne als Raster (Stunden-, Dienst-, Putzplan mit Rotation) oder Zeitstrahl (Projektplan)
- Teilen mit verifizierten Personen; alles wird auf dem Gerät verschlüsselt (AES-256-GCM, P-256),
  der Server sieht nur unlesbare Daten – siehe [docs/SECURITY.md](docs/SECURITY.md)

## Aufbau

| Ordner | Inhalt |
|---|---|
| `android/` | Android-App (Kotlin, Jetpack Compose) |
| `linux/` | Ubuntu-App (Python, GTK 4, libadwaita) |
| `server/` | Server (Python, Flask, SQLite) mit Installer `install.sh` |
| `homepage/` | Website |
| `tools/` | Hilfswerkzeuge (Kommandozeilen-Client, Screenshot-Skript) |

## Tests

```sh
for t in linux/tests/test_*.py; do python3 "$t"; done     # Ubuntu-App
cd android && ./gradlew testDebugUnitTest                  # Android-App
```

## Lizenz

© 2026 Olaf Winkler. Entwickelt in Schleswig-Holstein.

LiNotes ist freie Software: Du kannst sie unter den Bedingungen der
[GNU General Public License, Version 3](LICENSE) weitergeben und verändern.
LiNotes wird ohne jede Gewährleistung bereitgestellt.

LiNotes ist ein unabhängiges Projekt und steht in keiner Verbindung zu Apple Inc.
