#!/bin/bash
# LiNotes-Server installieren (Debian, Ubuntu, Raspberry Pi OS).
#
#   sudo ./install.sh notizen.example.org [/pfad/zu/den/daten]
#
# Richtet ein: Systembenutzer „linotes“, Programm in /opt/linotes (Python-venv),
# Daten standardmäßig in /var/lib/linotes, systemd-Dienst, nginx mit HTTPS
# (Let's Encrypt), nächtliche Sicherung – und gibt den ersten Einladungscode aus.
# Das Skript darf mehrfach laufen (z. B. für Updates).
set -euo pipefail

DOMAIN="${1:-}"
DATA="${2:-/var/lib/linotes}"
APP=/opt/linotes
PORT=8430
HERE="$(cd "$(dirname "$0")" && pwd)"

if [ -z "$DOMAIN" ]; then
    echo "Aufruf: sudo $0 <domain> [datenverzeichnis]"
    echo "Die Domain muss schon auf diesen Rechner zeigen (Port 80 und 443 offen)."
    exit 1
fi
if [ "$(id -u)" != 0 ]; then
    echo "Bitte mit sudo ausführen."
    exit 1
fi

say() { printf '\n\033[1m%s\033[0m\n' "$*"; }

say "1/6 Pakete"
apt-get update -qq
apt-get install -y -qq python3 python3-venv rsync curl nginx certbot python3-certbot-nginx sqlite3 >/dev/null

say "2/6 Benutzer und Verzeichnisse"
id linotes >/dev/null 2>&1 || useradd --system --home "$APP" --shell /usr/sbin/nologin linotes
mkdir -p "$APP" "$DATA" "$DATA-backup"
rsync -a --delete --exclude tests --exclude __pycache__ --exclude venv --exclude install.sh "$HERE/" "$APP/"
chown -R root:root "$APP"
chown linotes:linotes "$DATA" "$DATA-backup"
chmod 700 "$DATA" "$DATA-backup"

say "3/6 Python-Umgebung"
[ -d "$APP/venv" ] || python3 -m venv "$APP/venv"
"$APP/venv/bin/pip" install -q --upgrade pip
"$APP/venv/bin/pip" install -q -r "$APP/requirements.txt"

say "4/6 Dienst"
cat > /etc/systemd/system/linotes.service <<EOF
[Unit]
Description=LiNotes-Server (Ende-zu-Ende verschlüsselte Notizen)
After=network.target
RequiresMountsFor=$DATA

[Service]
User=linotes
WorkingDirectory=$APP
Environment=LINOTES_DATA=$DATA
ExecStart=$APP/venv/bin/gunicorn --workers 1 --threads 24 --timeout 90 --bind 127.0.0.1:$PORT --error-logfile - wsgi:app
Restart=on-failure
RestartSec=5
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ReadWritePaths=$DATA
ProtectHome=true

[Install]
WantedBy=multi-user.target
EOF

cat > "$APP/backup.sh" <<EOF
#!/bin/bash
# Tägliche Sicherung: konsistente Kopie der Datenbank (14 Tage) und der Dateien.
# Tipp: $DATA-backup auf eine zweite Festplatte legen.
set -euo pipefail
day=\$(date +%F)
$APP/venv/bin/python - "$DATA/linotes.db" "$DATA-backup/linotes-\$day.db" <<'PY'
import sqlite3, sys
source = sqlite3.connect(sys.argv[1])
target = sqlite3.connect(sys.argv[2])
source.backup(target)
target.close()
PY
chmod 600 "$DATA-backup/linotes-\$day.db"
mkdir -p "$DATA/files"
rsync -a --delete "$DATA/files/" "$DATA-backup/files/"
find "$DATA-backup" -maxdepth 1 -name "linotes-*.db" -mtime +14 -delete
EOF
chmod 755 "$APP/backup.sh"
cat > /etc/systemd/system/linotes-backup.service <<EOF
[Unit]
Description=LiNotes-Sicherung

[Service]
Type=oneshot
User=linotes
ExecStart=$APP/backup.sh
EOF
cat > /etc/systemd/system/linotes-backup.timer <<EOF
[Unit]
Description=LiNotes-Sicherung jede Nacht

[Timer]
OnCalendar=*-*-* 03:40
Persistent=true

[Install]
WantedBy=timers.target
EOF
systemctl daemon-reload
systemctl enable --now linotes.service linotes-backup.timer >/dev/null
systemctl restart linotes.service

say "5/6 nginx und HTTPS"
cat > /etc/nginx/sites-available/linotes <<EOF
# LiNotes-API. Keine Zugriffsprotokolle.
server {
    listen 80;
    listen [::]:80;
    server_name $DOMAIN;
    access_log off;
    client_max_body_size 30m;
    add_header Referrer-Policy "no-referrer" always;
    add_header X-Content-Type-Options "nosniff" always;

    location /api/ {
        proxy_pass http://127.0.0.1:$PORT;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_read_timeout 75s;
        proxy_buffering off;
    }

    location / {
        return 404;
    }
}
EOF
ln -sf /etc/nginx/sites-available/linotes /etc/nginx/sites-enabled/linotes
nginx -t -q
systemctl reload nginx
if [ ! -d "/etc/letsencrypt/live/$DOMAIN" ]; then
    certbot --nginx -d "$DOMAIN" --redirect --non-interactive --agree-tos --register-unsafely-without-email \
        || echo "HTTPS konnte nicht eingerichtet werden – zeigt die Domain auf diesen Rechner? Später: sudo certbot --nginx -d $DOMAIN"
fi

say "6/6 Prüfen"
sleep 2
if curl -fsS "http://127.0.0.1:$PORT/api/health" | grep -q '"protocol":2'; then
    echo "Der Server läuft."
else
    echo "Der Server antwortet nicht – siehe: journalctl -u linotes"
    exit 1
fi

INVITE=$(sudo -u linotes env LINOTES_DATA="$DATA" "$APP/venv/bin/python" -m linotes_server.admin invite)
cat <<EOF

Fertig!

  Serveradresse für die Apps:  $DOMAIN
  Erster Einladungscode:       $INVITE

In der App die Serveradresse eingeben, „Neues Konto erstellen“ wählen und den
Code eingeben. Weitere Einladungen gibt es danach direkt in der App oder mit:

  sudo -u linotes env LINOTES_DATA=$DATA $APP/venv/bin/python -m linotes_server.admin invite

Der Server speichert nur verschlüsselte Daten – auch du als Betreiber kannst
die Notizen deiner Nutzer nicht lesen.
EOF
