#!/bin/bash
# LiNotes-Server mit einem Befehl einrichten (Debian, Ubuntu, Raspberry Pi OS):
#
#   curl -fsSL https://linotes.goip.de/install-server.sh | sudo bash -s notizen.example.org
#
# Lädt das Server-Paket, prüft die Prüfsumme und startet den Installer aus dem Paket
# (Dienst, nginx mit HTTPS, nächtliche Sicherung, erster Einladungscode).
# Darf erneut laufen – so kommen auch Updates auf den Server.
set -euo pipefail

VERSION=2.1.0
BASE=https://linotes.goip.de/download
DOMAIN="${1:-}"
DATA="${2:-/var/lib/linotes}"

if [ -z "$DOMAIN" ]; then
    echo "Aufruf: curl -fsSL https://linotes.goip.de/install-server.sh | sudo bash -s <deine-domain>"
    exit 1
fi
if [ "$(id -u)" != 0 ]; then
    echo "Bitte mit sudo ausführen."
    exit 1
fi
command -v curl >/dev/null || { apt-get update -qq && apt-get install -y -qq curl; }

WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT
cd "$WORK"
echo "LiNotes-Server $VERSION wird geladen …"
curl -fsSLO "$BASE/linotes-server-$VERSION.tar.gz"
curl -fsSLO "$BASE/SHA256SUMS"
grep " linotes-server-$VERSION.tar.gz\$" SHA256SUMS | sha256sum -c --quiet - || { echo "Prüfsumme stimmt nicht – Abbruch."; exit 1; }
tar xzf "linotes-server-$VERSION.tar.gz"
./linotes-server/install.sh "$DOMAIN" "$DATA"
