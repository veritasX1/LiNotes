# LiNotes – Sicherheitskonzept (Version 2)

Ziel: Der Server speichert nur verschlüsselte Daten. Niemand mit Zugriff auf
den Server – auch nicht der Betreiber – kann Notizen, Listen, Boards, Ordner-
namen oder Bilder lesen. Geteilte Inhalte können nur die Konten lesen, mit
denen sie geteilt wurden.

## Bausteine (auf Linux und Android identisch)

P-256, ECDH, HKDF-SHA256, AES-256-GCM, HMAC-SHA256, PBKDF2-SHA256 und SPAKE2
nach RFC 9382 (P256-SHA256-HKDF-HMAC). Umsetzung: `linux/linotes/e2e.py` und
`android/.../data/E2E.kt`, geprüft mit den offiziellen RFC-Testvektoren und
gegenseitig (Linux verschlüsselt ⇄ Android entschlüsselt).

## Konto

- Beim ersten Gerät entsteht ein zufälliges 32-Byte-Kontogeheimnis **R**.
- Daraus per HKDF: `auth` (Anmeldung – der Server speichert nur SHA-256 davon),
  `K_private` (alles Private), `K_identity` (schützt den Identitätsschlüssel).
- **Identitätsschlüssel**: P-256-Schlüsselpaar. Der öffentliche Teil liegt auf
  dem Server (für Freigaben), der private Teil liegt dort nur mit `K_identity`
  verschlüsselt, damit weitere Geräte ihn übernehmen können.
- Es gibt kein Passwort. Wer R hat, hat das Konto.

## Weitere Geräte koppeln (wie bei Signal)

1. Neues Gerät: Serveradresse und Benutzername eingeben. Es zeigt einen
   **6-stelligen Code** und denselben Code als **QR-Code**.
2. Bereits angemeldetes Gerät desselben Kontos meldet „Neues Gerät möchte sich
   verbinden“; dort Code eintippen oder QR-Code scannen.
3. Beide führen SPAKE2 mit dem Code über ein Relais auf dem Server aus. Der Code
   selbst geht nie über den Server; ein Angreifer (auch ein manipulierter Server)
   hat genau einen Rateversuch (1 : 1 000 000), danach ist der Vorgang ungültig.
4. Mit dem ausgehandelten Schlüssel wird R an das neue Gerät übertragen.

## Schlüsseldatei (Notfall)

Enthält Serveradresse, Benutzername und R, verschlüsselt mit einer
Passphrase (PBKDF2, 600 000 Runden → AES-GCM). Für den Tresor / USB-Stick.
Ohne Gerät und ohne Schlüsseldatei sind die Daten verloren – das ist gewollt.

## Daten

- Jedes Objekt (Ordner, Notiz, Liste, Eintrag, Board, Spalte, Karte) liegt als
  `{"v":2,"m":…,"b":…}` auf dem Server: `m` = Metadaten (Titel, Ordner,
  Datum …), `b` = Inhalt (nur Notizen). Beide AES-GCM-verschlüsselt, per AAD an
  Objekt-ID und Feld gebunden.
- Privat: Schlüssel `K_private`. Geteilt: Schlüssel der Freigabe.
- Der Server sieht nur: Objekt-ID, Art (Notiz/Liste …), Besitzer, Freigabe-ID,
  Zeitpunkt, Größe.

## Teilen

- Eine **Freigabe** hat einen zufälligen Schlüssel S und eine Mitgliederliste.
  S wird für jedes Mitglied mit dessen öffentlichem Identitätsschlüssel
  verpackt (ECIES). Der Server kennt nur die Mitgliederliste und setzt sie
  durch (wer kein Mitglied ist, bekommt die Daten gar nicht).
- Teilbar: einzelne Notizen, Listen, Boards oder ganze Ordner.
- Wird jemand entfernt, erzeugt der Besitzer einen neuen Schlüssel und
  verschlüsselt neu.

## Vertrauen (Verifizieren)

Bevor geteilt wird, muss das Gegenüber verifiziert sein – damit niemand (auch
nicht der Server) einen falschen Schlüssel unterschieben kann:

- **QR-Code**: Der QR-Code enthält den Fingerabdruck des Identitätsschlüssels;
  das andere Gerät scannt und vergleicht.
- **PIN**: Ein Gerät zeigt einen 6-stelligen Code, der andere tippt ihn ein;
  SPAKE2 bestätigt gegenseitig die Identitätsschlüssel.
- Zusätzlich gibt es eine 20-stellige Sicherheitsnummer zum Vergleichen.

## Gesperrte Notizen

Zusätzliche Schicht mit eigenem Notizen-Passwort (PBKDF2 → AES-GCM). Auf
Android kann die Entsperrung zusätzlich über Fingerabdruck/Gesicht, PIN oder
Muster des Geräts erfolgen (Android-Keystore mit Benutzer-Authentifizierung).

## Auf dem Gerät

- Notizen entstehen auf dem Gerät und werden hochgeladen.
- Pro Notiz wählbar, wie lange der Inhalt auf dem Gerät bleibt: Immer, 90, 30,
  7 Tage ohne Öffnen oder „Nur auf dem Server“. Standard 90 Tage; angeheftete
  Notizen, Listen und Boards bleiben immer. Danach bleiben nur Titel und Datum,
  der Inhalt wird beim Öffnen geladen.

## Server

- Nur mit Einladungscode kann ein Konto entstehen; keine Standard-Serveradresse
  in den Apps.
- HTTPS, Anmeldeversuche begrenzt, keine Zugriffsprotokolle.
