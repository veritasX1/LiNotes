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
- [ ] Android v2: E2E.kt (gleiche Testvektoren), Sync v2, Einrichtung, QR-Scanner (ZXing), Teilen, Verifizieren, Schlüsseldatei (SAF), Biometrie/PIN/Muster für gesperrte Notizen, Auslagerung (Immer/90/30/7/Nur Server, Standard 90, Angeheftete + Listen/Boards immer)
- [ ] Server-Deployment v2: DB neu (alte v1-Daten leer), API auf linotesauth.goip.de (Nutzerwunsch), linotes.goip.de nur Homepage/Downloads
- [ ] Installer für eigene Server (server/install.sh: venv, systemd, nginx+certbot, Einladungscode)
- [ ] Hilfe/How-to auf Homepage; Homepage ohne Serveradresse
- [ ] Handy-Test (Nutzer per ntfy bitten, Handy anzuschließen)
