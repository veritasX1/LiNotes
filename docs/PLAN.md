# LiNotes – Plan und Fortschritt

Notizen, Einkaufslisten und Kanban-Board für Olaf und seine Frau.
Server auf dem Pi (linotes.goip.de), Clients für Ubuntu (GTK4/libadwaita)
und Android (Kotlin/Compose), Gestaltung nach Apples Notizen / HIG.

## Architektur
- **Server** `server/`: Flask + SQLite (gunicorn, 1 Prozess, Threads),
  Daten auf `/media/olaf/5TB1/linotes` (nie auf die SD-Karte!).
  nginx + certbot auf linotes.goip.de, systemd `linotes.service`.
- **Sync**: generische Objekte `{id, kind, space, owner, data, deleted, version}`.
  `GET /api/sync?since=N&wait=25` (Long-Poll), `POST /api/sync` mit Änderungen.
  Sichtbar: `space == "shared"` oder eigener Besitz. Konflikt bei Notizen → Kopie.
- **Kinds**: folder, note, list, item (Listeneintrag), board, column, card, vault.
- **Spaces**: `private` (nur Besitzer), `shared` (alle Konten des Servers = Haushalt).
- **Geheime Notizen**: Ende-zu-Ende verschlüsselt mit eigenem Notizen-Passwort.
  PBKDF2-HMAC-SHA256 (200 000 Iterationen, 16-Byte-Salt) → AES-256-GCM,
  12-Byte-Nonce, Base64. Klartext = JSON `{"title","body"}`. Tresor-Objekt
  `vault-<user>` enthält Salt + verschlüsselten Prüfwert „LiNotes“.
- **Notizformat**: Blöcke `{"t": title|heading|subheading|body|mono|bullet|dash|number|check|image,
  "x": Text, "s": [[start,end,"b|i|u|s"]], "c": abgehakt, "f": Datei-ID, "l": Einzug}`.
- **Konten**: Olaf (angelegt), Frau registriert sich selbst mit Einladungscode.

## Stand
- [x] Server (Tests: server/tests/test_api.py)
- [x] Deployment Pi: ~/linotes (Code+venv), Daten /media/olaf/5TB1/linotes, linotes.service :8430, nginx+TLS, beide Watchdogs, Backup-Timer 03:40 nach /media/olaf/6TB/linotes-backup
- [x] Ubuntu-App (linux/): Notizen+Editor, gesperrte Notizen (E2E), Papierkorb, Tags, Suche, Galerie, Einkaufslisten, Kanban, Live-Sync. Headless getestet gegen lokalen Testserver.
- [x] Android-App (android/): Compose im iOS-Stil, RichEditor (EditText+Spans), Keystore-Token, E2E kompatibel, Listen, Kanban. Tests: Robolectric InteropTest + Roborazzi-Screenshots (./gradlew recordRoborazziDebug, Testserver 127.0.0.1:8499 nötig)
- [x] Homepage linotes.goip.de (homepage/, Downloads APK + Ubuntu-Tarball), F-Droid-Repo fdroid-apps (Watcher auf fdroid-apps korrigiert), Release-Key android/linotes-release.jks (Backup 6TB/linotes-backup/android-signing)
- [x] Konto olaf + Einladungscode → ~/LiNotes-Zugang.txt (600) auf dem ThinkPad

## Version 2 (Wunsch vom 27.09.): Ende-zu-Ende, Schlüssel statt Passwort
Konzept: docs/SECURITY.md
- [x] Krypto-Kern Linux (linux/linotes/e2e.py, RFC-9382-Testvektoren: linux/tests/test_e2e.py)
- [x] Server v2 (Freigaben, Relais, Einzelabruf) – server/tests/test_api.py
- [x] Koppeln/Verifizieren (linux/linotes/pairing.py, linux/tests/test_pairing.py)
- [x] Ubuntu-App v2: Einrichtung (Server/Neues Konto/Gerät verbinden/Schlüsseldatei), Teilen-Dialog, Personen/Verifizieren, Schlüsseldatei-Export, Hilfe. GUI-Ende-zu-Ende-Test mit 2. Konto bestanden.
- [x] Ubuntu-Symbol: Installer baut Icon-Cache mit -t und legt PNGs ab
- [x] Android v2: E2E.kt (gleiche Testvektoren), Sync v2, Einrichtung, QR-Scanner (ZXing), Teilen, Verifizieren, Schlüsseldatei (SAF), Biometrie/PIN/Muster für gesperrte Notizen, Auslagerung (Immer/90/30/7/Nur Server, Standard 90, Angeheftete + Listen/Boards immer). Robolectric-Screenshots gegen frischen Testserver: Scratchpad `android_srv.sh` (Port 8499, Konto anna + Einladung für olaf in android_invite.txt), dann `./gradlew testDebugUnitTest -Proborazzi.test.record=true`
- [x] Server-Deployment v2 (27.09.): DB neu (v1 archiviert in /media/olaf/5TB1/linotes/v1-alt-20260927), API auf linotesauth.goip.de (Nutzerwunsch), linotes.goip.de nur Homepage/Downloads; DNS, nginx-vhost linotesauth, certbot, Watchdog-URLs angepasst; Einladungscodes in ~/LiNotes-Zugang.txt
- [x] Installer für eigene Server (nur Syntax geprüft, noch nicht auf frischem System gelaufen) (server/install.sh: venv, systemd, nginx+certbot, Einladungscode)
- [x] Hilfe/How-to auf Homepage (#anleitung, #server); Downloads 2.0 (APK, Ubuntu, Server) + F-Droid
- [ ] Handy-Test (Nutzer per ntfy bitten, Handy anzuschließen)
- [x] Fix: geänderte Objekte rücken in der Warteschlange ans Ende (sonst kam ein Objekt vor seiner neuen Freigabe beim Server an → „forbidden“, Objekt verschwand). Linux + Android.
- [x] .gitignore-Regel `data/` war zu weit (Android-Datenschicht war nicht eingecheckt) → `/data/`, `server/data/`
- [x] Ohne Server (Nutzerwunsch 27.09.): „Ohne Server nutzen“ bei der Einrichtung; Konto-Id -1, Standard-Ids `notes--1` usw., Bilder verschlüsselt lokal (`local:<name>`). Später „Mit Server verbinden …“: neues Konto (mit denselben Schlüsseln), Gerät verbinden oder Schlüsseldatei; `connect_local`/`connectLocal` benennt Ids um, lädt Bilder hoch, bestehende Standard-Ordner/Liste/Board des Kontos bleiben. Konflikt, wenn beide ein Notizen-Passwort haben → Hinweis, vorher Sperren entfernen. Tests: android LocalModeTest, linux/tests/test_local.py
- [x] Handy-Test auf moto g84 (live-Server, Testkonten): Registrierung, Schlüsseldatei, Verifizieren, Teilen, Live-Abgleich, Gerät verbinden, Auslagern + Nachladen, ohne Server → verbinden
- [ ] Noch vom Nutzer zu testen: Fingerabdruck/PIN/Muster, QR-Scanner mit der Kamera
