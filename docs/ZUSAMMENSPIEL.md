# Zusammenspiel LiMail · LiCal · LiNotes

Gleiche Datei in allen drei Repos (LiMail, LiCal, LiNotes). Änderungen bitte in allen dreien nachziehen.

## Grundsatz (Olaf, 05.10.2026)

> „also aktiv getriggerte austauschformate. nichts am user vorbei“

- Jede Übergabe passiert **nur auf Tipp** des Nutzers, nie im Hintergrund.
- Das Ziel zeigt **erst eine Vorschau** und speichert erst nach Bestätigung: Termin-Blatt in LiCal, Verfassen-Blatt in LiMail, Notiz-Vorschau in LiNotes.
- Keine App liest Daten einer anderen. LiMail hat **keine** Kalender- oder Notizen-Berechtigung; nach außen offen sind nur die Übergabe-Intents unten.
- Nur **Standardformate**, damit auch fremde Apps funktionieren (Thunderbird/K-9, Google Kalender, Etar, Notizen-Apps …). Eigene Extras höchstens zusätzlich.
- Alles bleibt auf dem Gerät. Kein Server, kein Konto.

## Android

| Von → Nach | Auslöser | Intent | Inhalt |
|---|---|---|---|
| LiMail → Kalender (LiCal oder jede Kalender-App) | Mail › Antworten-Menü › **Termin erstellen** | `ACTION_INSERT`, Daten `content://com.android.calendar/events` | `Events.TITLE` = Betreff (ohne Re:/AW:/Fwd:), `Events.DESCRIPTION` = eigener Text der Mail + Herkunft + Rücksprung-Link, `EXTRA_EVENT_BEGIN_TIME`/`END_TIME`/`EXTRA_EVENT_ALL_DAY`, wenn im Betreff oder Text ein Datum steht („am Samstag ab 18 Uhr“, „12.10.“, „morgen um 9:30“) |
| LiMail → Notizen (LiNotes oder jede App) | Mail › Antworten-Menü › **Als Notiz teilen** | `ACTION_SEND`, `text/plain`, Auswahl-Dialog | `EXTRA_SUBJECT` = Betreff, `EXTRA_TEXT` = Text + Herkunft + Rücksprung-Link |
| LiNotes / jede App → LiMail | „Teilen“ › LiMail | `ACTION_SEND` / `ACTION_SEND_MULTIPLE`, beliebiger Typ | `EXTRA_SUBJECT`, `EXTRA_TEXT`, `EXTRA_EMAIL`/`EXTRA_CC`/`EXTRA_BCC`, `EXTRA_STREAM` (Dateien werden Anhänge) → Verfassen-Blatt |
| Web / jede App → LiMail | mailto:-Link | `ACTION_SENDTO` oder `ACTION_VIEW` mit `mailto:` (RFC 6068: to, cc, bcc, subject, body) | → Verfassen-Blatt |
| Notiz / Termin → LiMail | Link in den Notizen antippen | `ACTION_VIEW` `limail://message/<Message-ID, URL-kodiert>` | öffnet die Mail, wenn sie auf dem Gerät ist; sonst passiert nichts |
| LiCal → LiMail (Einladung, Termin teilen) | in LiCal – **noch offen**, LiCal hat noch kein „Teilen“ | `ACTION_SEND` (`text/calendar` als `EXTRA_STREAM` oder Text) | → Verfassen-Blatt mit Anhang |

Der **Rücksprung-Link** `limail://message/…` enthält nur die Message-ID der Mail (steht ohnehin im Mail-Kopf), keine Inhalte. Andere Apps, die ihn aufrufen, können damit nur die Mail in LiMail öffnen lassen – sie bekommen nichts zurück.

Was LiCal annimmt: `ACTION_INSERT`/`ACTION_EDIT` auf `vnd.android.cursor.dir/event` mit den Standard-Extras (`Events.TITLE`, `EVENT_LOCATION`, `DESCRIPTION`, `RRULE`, `EXTRA_EVENT_BEGIN_TIME`, `EXTRA_EVENT_END_TIME`) – zeigt das Termin-Blatt (Incoming.kt).
Was LiNotes annimmt: `ACTION_SEND` `text/plain` mit `EXTRA_TEXT` (+ `EXTRA_SUBJECT`) – zeigt die Notiz-Vorschau.

## Ubuntu

| Von → Nach | Auslöser | Weg | Stand |
|---|---|---|---|
| LiMail → Kalender (LiCal oder jede Kalender-App) | Mail › ⋯ › **Termin erstellen …** | `.ics`-Datei (RFC 5545, ein VEVENT) im privaten Laufzeitordner, geöffnet mit der Standard-App für `text/calendar`; LiCal fragt vor dem Übernehmen (wie jede Kalender-App) | umgesetzt (LiMail Phase D) |
| LiMail → Notizen (LiNotes oder jede App) | Mail › ⋯ › **Als Notiz teilen …** | Text (Betreff, Text, Herkunft, Rücksprung-Link) in die Zwischenablage, Hinweis „in LiNotes oder einer anderen App einfügen“ | umgesetzt; später `linotes --neue-notiz --titel … --text …`, sobald LiNotes es annimmt |
| Web / jede App → LiMail | `mailto:`-Link | LiMail ist Mail-Programm (`x-scheme-handler/mailto`, install.sh setzt es nur, wenn noch keins gewählt ist) → Verfassen-Fenster | umgesetzt |
| Kommandozeile / LiNotes → LiMail | `limail --verfassen --an … --kopie … --betreff … --text … --anhang DATEI …` | Verfassen-Fenster mit allem ausgefüllt, nichts wird ohne Klick auf Senden verschickt | umgesetzt |
| Notiz / Termin → LiMail | Link `limail://message/<Message-ID>` | `x-scheme-handler/limail` → öffnet die Mail, wenn sie auf dem Computer ist | umgesetzt |
| LiCal → LiMail | in LiCal – noch offen | `limail --verfassen --anhang termin.ics` | wartet auf LiCal |

## Prüfung (Abnahme)

- Jede Richtung mit unseren Apps **und** einer fremden Gegen-App ausprobieren.
- Manifest: LiMail exportiert nur MainActivity (Start, mailto, Teilen, limail://) und das Widget; keine Content-Provider nach außen, keine Kalender-/Notizen-Berechtigung.
