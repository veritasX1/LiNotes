# LiNotes 2.3.0 – Transparenzbericht

> Erstellt von Richard 🟡 (Tester), Stand 08.10.2026 16:42, Vier-Augen-Prüfung durch Michelle 🔵. Mit „⏳“ markierte Stellen sind bekannte, noch nicht geprüfte Punkte.
> Geprüfte Fassungen: Quelltext main f86901e (entwicklung-2.1 gemergt). Release-APK 2.3.0 (Code 9, 16:38:15): SHA-256 3872b9b96eae2f16a62239462bfa074f13a909f2f3c70623d910a79ebba09365, Schlüssel 4673c332… (= Homepage), nicht debuggable. Ubuntu-Paket linotes-ubuntu-2.3.0.tar.gz: SHA-256 29cdecb288d5f3f6d2425741840280883fbaca1438757197b6668d524688b69c (60 Dateien, keine Tests, keine privaten Adressen).

## 1. Kurz gesagt
- LiNotes spricht mit **deinem eigenen Server**, den du selbst betreibst oder dem du vertraust, oder mit gar keinem („Ohne Server nutzen“).
- **Alles ist Ende-zu-Ende verschlüsselt** (AES-256-GCM) auf deinem Gerät, bevor es den Server erreicht: Notizen, Listen, Pläne, Ordnernamen, Bilder, Audio. Der Server sieht nur unlesbare Daten.
- Kein Passwort für den Account: Er ist durch einen Schlüssel geschützt, der nur auf deinen Geräten liegt.
- Keine Werbung, keine Käufe, keine Tracker, keine Analyse, keine Absturzberichte.
- **Keine KI in LiNotes.** „KI im Team“ heißt: Eine KI bekommt wie ein Mensch einen eigenen Account auf deinem Server, wenn du das willst. In der App steckt kein Modell und kein KI-Dienst.

## 2. Netzverbindungen

| Wann | Wohin | Was | Abschaltbar |
|---|---|---|---|
| Abgleich | **dein** LiNotes-Server (Adresse trägst du selbst ein) | verschlüsselte Objekte, Dateien, Geräte-Kopplung (relay) | „Ohne Server nutzen“ |
| Nur wenn eingeschaltet (ab Werk aus) | die Webseite eines Links, der allein in einer Zeile steht (Link-Vorschau) | Titel und Bild der Seite holen. Nur das Gerät, das den Link einfügt, fragt die Seite. Die Vorschau wird verschlüsselt in der Notiz gespeichert, andere Geräte holen nichts. Erkennbar als „LiNotes-Linkvorschau“. | Darstellung → Link-Vorschau |
| Nur auf Klick | lisoftware.de/linotes/, GitHub-Issues (Info-Fenster) | Browser des Systems | – |

Nachweise: linkpreview.py (ab Werk aus: uiprefs „link_previews“ False, window.py:1445), api.py (nur die eingetragene Serveradresse). Android-APK 2.3.0 (wie 2.2.1): Die einzigen Webadressen sind Namensräume (w3.org, Adobe XMP, Google Photos-Metadaten) und Fehlerberichts-Links aus Bibliotheken, die nie aufgerufen werden.
**Unverschlüsselte Verbindung:** Android erlaubt nur https zum Server (kein usesCleartextTraffic). Unter Ubuntu lässt sich bewusst eine http://-Adresse eintragen (z. B. für einen Server im eigenen Netz). Der Inhalt bleibt Ende-zu-Ende verschlüsselt, Anmeldedaten und Metadaten wie Zeitpunkte und Größen gehen dann aber unverschlüsselt durchs Netz. Die Link-Vorschau holt auch http://-Seiten. ⏳ Entscheidung, ob das so bleiben soll, oder ob https Pflicht wird (Vorschlag nach „Privatsphäre zuerst“: Pflicht, Ausnahme nur für Adressen im eigenen Netz mit deutlichem Hinweis).
⏳ Messung mit strace (Ubuntu) bzw. am Gerät (Android) gegen einen eigenen Testserver: Am 08.10. gab es bei den Nachtests fc38cfad und 5939587a am lokalen Testserver nur Verbindungen zu 127.0.0.1:8599, das war aber über das CLI, nicht über die App.

## 3. Berechtigungen (Android, APK 2.3.0, gleich wie 2.2.1)

| Berechtigung | Wozu |
|---|---|
| INTERNET, ACCESS_NETWORK_STATE | Abgleich mit deinem Server |
| CAMERA | Foto in eine Notiz, QR-Code beim Koppeln eines Geräts bzw. Bestätigen einer Person |
| RECORD_AUDIO | Sprachaufnahme in einer Notiz |
| USE_BIOMETRIC, USE_FINGERPRINT | gesperrte Notizen mit Fingerabdruck öffnen |
| POST_NOTIFICATIONS | Mitteilung bei Erwähnung (@Name) und Änderungen an geteilten Notizen |

⏳ Wann Android jeweils fragt: nur mit Test-App prüfbar, Karte folgt (Claude).
**Nicht** angefordert: Standort, Kontakte, Kalender, Speicher/Fotos (Bilder über die Systemauswahl), Telefon.
Android-Backup: aus (allowBackup=false, dataExtractionRules schließt cloud-backup und device-transfer für root, file, database, sharedpref aus). Hinweis: Die device_*-Bereiche stehen nicht in den Regeln. Nötig ist das nur, wenn LiNotes geräteverschlüsselten Speicher nutzt, nicht geprüft.
Von außen erreichbar: nur die Startseite und die Schnellnotiz-Kachel (geschützt durch BIND_QUICK_SETTINGS_TILE).

## 4. Speicher
Auf dem Gerät liegen die Daten verschlüsselt im Datenordner der App. Die Schlüssel liegen unter Ubuntu im GNOME-Schlüsselbund, unter Android ⏳ (Keystore, nicht geprüft). Ohne Server bleibt alles verschlüsselt auf dem Gerät. Die Schlüsseldatei zum Wiederherstellen sicherst du selbst (Passphrase). Details: docs/SECURITY.md.
**Teilen und Entfernen (neu in 2.3.0):** Wer jemanden aus einer Freigabe entfernt, erzeugt immer einen neuen Schlüssel. Fremde Inhalte zieht ihr Besitzer beim nächsten Abgleich um, bis dahin liefert der Server sie nur noch an die Verbliebenen aus. Die Grenzen stehen offen in SECURITY.md. Geprüft am eigenen Testserver, 08.10. (Karten fc38cfad, 5939587a).

## 5. Bibliotheken
**Ubuntu** (Rechtshinweis in der App, geprüft 08.10., 5f4aee29): QR Code generator library (Project Nayuki, MIT, mitgeliefert), GTK 4/libadwaita/GLib/Pango/GdkPixbuf, Graphene, GStreamer, libsecret, PyGObject, pycairo, python3-cryptography, Python 3, poppler-utils.
**Android** (APK 2.3.0, laut Paketnamen): AndroidX/Jetpack Compose, CameraX, Media3 (Audio), Guava (com.google.common), ZXing (QR), Kotlin-Coroutinen, Checker-Framework-Annotationen. ⏳ Vollständige Liste mit Versionen und Lizenzen. **Lücke:** Die Android-App zeigt keine Lizenzseite mit diesen Bibliotheken (shared/lizenzen enthält nur „ubuntu“). LiMail und LiCal haben eine. Vorschlag: gleiche Lizenzseite wie LiCal (eigene Karte).

## 6. Tracker
**Keine.** Gegenprobe am 08.10.2026 an der Release-APK 2.3.0 (3872b9b9…) und vorher an 2.2.1: 51 SDK-Präfixe, zwei Suchwege, je **0 Treffer**. Die Positivkontrolle findet Compose, CameraX, Guava und ZXing (tracker-suche-2.3.0.txt). Die APK ist nicht minifiziert, die Klassennamen sind also unverändert lesbar.

## 7. Abgleich mit dem Wertekompass
| Wert / Grundsatz | Erfüllt? | Nachweis |
|---|---|---|
| **1. Privatsphäre** | ✔ mit Hinweis | Ende-zu-Ende, eigener Server, keine Tracker, Backup aus, Schlüsselwechsel beim Entfernen. Hinweis: http zum Server unter Ubuntu möglich (Abschnitt 2) |
| **2. Kontrolle** | ✔ | Ohne Server nutzbar, Link-Vorschau ab Werk aus, Kamera/Mikrofon nur bei Benutzung |
| **3. Einfachheit** | ✔ / ⏳ | Hilfe mit Suche, HIG-Prüfungen 08.10.; Bedienungshilfen-Durchgang ⏳ |
| **4. Kostenlos für immer** | ✔ | keine Käufe, keine Billing-Bibliothek |
| **KI** aus, kein Modell | ✔ | keine KI in der App; KI nur als eingeladener Account auf deinem Server. KI-Suche an APK 2.3.0: 0 Modelldateien, 0 von 16 KI-Bibliotheken, 0 von 11 KI-Dienst-Adressen, Positivkontrolle Guava 2637 (tracker-ki-2.3.0.txt) |
| **Unabhängigkeit lehren** | ✔ | Anleitung „Eigener Server“ (server.html, ein Befehl) |
| **Transparenz** | ✔ / ⏳ | GPL-3.0, Quelltext auf GitHub; dieser Bericht |

---
Erstellt von Richard 🟡 (Tester). Rohdaten: ~/Team/Richard/nachweise/transparenz-linotes/ (ablauf.txt, apk-pruefung-2.2.1.txt, tracker-suche.txt), Nachtests nachweise/linotes-fc38cfad, linotes-5939587a.
