# Projektplan LiNotes

Stand: 5. Oktober 2026 · veröffentlicht: 2.2.0 · in Entwicklung: 2.3

## Ziel
Notizen, Listen und Boards für Familie und kleine Teams – im Stil von Apples Notizen, Ende-zu-Ende verschlüsselt über den
eigenen Server, für Android und Ubuntu. Dazu Entwicklungsprojekte mit nachvollziehbaren Anforderungen.

## Grundsätze
- **Einfach für Tante Erna, mehr für Profis:** ab Werk schlicht; Gliederung, Fußnoten, Code, Formeln per Einstellung.
- **Privatsphäre:** Ende-zu-Ende verschlüsselt, eigener Server, keine Werbung, kein Tracking, keine KI in der App.
- **Schnell bleiben:** Ubuntu-App wird vor jeder Version gemessen.

## Erreicht
- Notizen mit Formatierung, Tabellen, Anhängen, Audio, Verlinkung, Sperre (PIN/Biometrie), Ordner und Unterordner.
- Listen und Boards mit Prioritäten, Fälligkeit, Zuweisungen, Badges für Änderungen anderer.
- Entwicklungsprojekte: Auswirkung, Verifikation, Version, Nachweise und Commits je Karte; Export als PDF/CSV.
- Homepage unter lisoft.goip.de/linotes, Server-Einzeiler.

## Nächste Meilensteine
1. **2.3 – Testing-Karten abschließen** (Hilfe mit Bildern, Archiv, Vorlagen, Formeln, Fußnoten, Code, Link-Vorschau).
2. **Mehrsprachig:** Englisch und Französisch (Zwischenstand vorhanden).
3. **Wissen verknüpfen:** Rückverweise, Tagesnotiz, Hashtags (auch verschachtelt), Graph-Ansicht, Import aus anderen Apps.
4. **Ubuntu-Paketquelle**, damit Updates ohne Handarbeit kommen.

## Risiken und offene Fragen
- Funktionsumfang wächst schnell – „Tante Erna zuerst“ bei jeder Karte prüfen.
- Leistung der Ubuntu-App bei großen Notizen und vielen Karten.

## Arbeitsweise
Board „LiNotes Change Requests“: CR → In Bearbeitung → Testing → Erledigt (Erledigt setzt der Produktverantwortliche).
Commits mit Karten-Id; `tools/linotes-cli.py trace-commits` hängt sie an die Karten.
