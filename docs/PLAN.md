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
- [ ] Server
- [ ] Deployment Pi (DNS, nginx, TLS, systemd, Watchdog)
- [ ] Ubuntu-App: Notizen, Editor, geheime Notizen, Listen, Kanban
- [ ] Android-App: dasselbe
- [ ] Homepage mit Downloads, F-Droid-Repo
- [ ] Zugangsdaten für Olaf, Einladungscode für seine Frau
