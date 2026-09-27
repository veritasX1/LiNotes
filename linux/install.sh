#!/bin/sh
# Install LiNotes for the current user (launcher, icon, `linotes` command).
set -e
cd "$(dirname "$0")"
ROOT="$(pwd)"
APP_ID=io.github.veritasx1.LiNotes
DATA="${XDG_DATA_HOME:-$HOME/.local/share}"
mkdir -p "$HOME/.local/bin" "$DATA/applications" "$DATA/icons/hicolor/scalable/apps"
cat > "$HOME/.local/bin/linotes" <<SCRIPT
#!/bin/sh
exec /usr/bin/python3 "$ROOT/main.py" "\$@"
SCRIPT
chmod +x "$HOME/.local/bin/linotes"
cp "data/$APP_ID.svg" "$DATA/icons/hicolor/scalable/apps/$APP_ID.svg"
sed "s|@EXEC@|$HOME/.local/bin/linotes|" "data/$APP_ID.desktop.in" > "$DATA/applications/$APP_ID.desktop"
update-desktop-database "$DATA/applications" 2>/dev/null || true
gtk-update-icon-cache -q "$DATA/icons/hicolor" 2>/dev/null || true
echo "LiNotes installiert – im Anwendungsmenü oder mit: linotes"
