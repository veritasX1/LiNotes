#!/usr/bin/env python3
"""LiNotes ohne Oberfläche – für das Claude-Konto (Kanban-Boards lesen/bearbeiten).

Nutzt die Sync-Engine der Ubuntu-App (linux/linotes), aber mit eigenem
Datenordner und Schlüsseln nur in ~/.config/linotes-cli/<profil>/ (Datei, 600)
statt im GNOME-Schlüsselbund.

    linotes-cli.py register <server> <einladung> <benutzername> <anzeigename>
    linotes-cli.py status | people | sync
    linotes-cli.py verify-show <person>      # zeigt Code, die andere Person tippt ihn ein
    linotes-cli.py verify-answer [code]      # wartet auf Anfrage, gibt den Code ein
    linotes-cli.py boards
    linotes-cli.py board <board>             # Spalten + Karten (mit Kurz-Ids)
    linotes-cli.py card <karte>              # Details
    linotes-cli.py move <karte> <spalte>
    linotes-cli.py comment <karte> <text>    # hängt Text an die Notizen an
    linotes-cli.py priority <karte> <hoch|mittel|niedrig|keine>
    linotes-cli.py export <board> <datei.pdf|datei.csv>
    linotes-cli.py trace-commits <board> [repo]   # Commits mit [karten-id] an die Karten hängen
    linotes-cli.py add <board> <spalte> <titel> [notizen]
    linotes-cli.py field <karte> <impact|verification|version> <text>   # Feld eines Entwicklungsprojekts setzen
    linotes-cli.py dump <board> [datei.json]     # alle Karten mit Spalte, Notizen, Feldern, Commits
"""

import json
import os
import sys
import time
from pathlib import Path

PROFILE = os.environ.get("LINOTES_PROFILE", "claude")
BASE = Path.home() / ".config" / "linotes-cli" / PROFILE
BASE.mkdir(parents=True, exist_ok=True, mode=0o700)
os.environ["XDG_DATA_HOME"] = str(BASE / "data")
os.environ["XDG_CACHE_HOME"] = str(BASE / "cache")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "linux"))

from linotes import e2e, model, pairing, sync  # noqa: E402
from linotes.api import Api  # noqa: E402

CREDS = BASE / "credentials.json"


def _store(server, username, token, secret):
    CREDS.touch(mode=0o600)
    CREDS.write_text(json.dumps({"server": server, "username": username, "token": token,
                                 "secret": e2e.b64(secret)}))
    os.chmod(CREDS, 0o600)


def _load(server, username):
    if not CREDS.exists():
        return None, None
    data = json.loads(CREDS.read_text())
    return data["token"], e2e.unb64(data["secret"])


def _clear(server, username):
    CREDS.unlink(missing_ok=True)


def contacts_id(eng):
    return f"contacts-{eng.user_id}"


# Wie linotes.security_ui (dort mit GTK-Import).
def verified_state(eng, user):
    contacts = eng.get(contacts_id(eng))
    stored = (contacts or {}).get("data", {}).get("verified", {}).get(str(user["id"]))
    if not stored:
        return "unverified"
    return "verified" if stored == e2e.fingerprint(user["identity"]) else "changed"


def mark_verified(eng, user_id, fingerprint):
    contacts = eng.get(contacts_id(eng))
    data = dict(contacts["data"]) if contacts else {"verified": {}}
    data["verified"] = {**data.get("verified", {}), str(user_id): fingerprint}
    eng.put("contacts", data, None, contacts_id(eng), notify=False)


sync.store_credentials, sync.load_credentials, sync.clear_credentials = _store, _load, _clear
sync.device_name = lambda: f"CLI ({PROFILE})"


def engine(pull=True):
    eng = sync.SyncEngine()
    if not CREDS.exists():
        sys.exit("Nicht angemeldet – erst `register`.")
    if not eng.restore():
        sys.exit("Anmeldedaten fehlen.")
    if pull:
        eng.sync_now()
    return eng


def flush(eng):
    for _ in range(20):
        if not eng.state["pending"]:
            break
        eng.push_once()
    eng.save()


def find(eng, kind, ref, **where):
    ref = ref.lower()
    items = [o for o in eng.objects(kind) if all(o["data"].get(k) == v for k, v in where.items())]
    hits = [o for o in items if o["id"].startswith(ref)] or \
           [o for o in items if (o["data"].get("name") or o["data"].get("title") or "").lower() == ref] or \
           [o for o in items if ref in (o["data"].get("name") or o["data"].get("title") or "").lower()]
    if len(hits) != 1:
        sys.exit(f"{kind} „{ref}“: {len(hits)} Treffer")
    return hits[0]


def columns(eng, board_id):
    return sorted((c for c in eng.objects("column") if c["data"].get("board") == board_id),
                  key=lambda c: c["data"].get("order", 0))


def cards(eng, column_id):
    return sorted((c for c in eng.objects("card")
                   if c["data"].get("column") == column_id and not c["data"].get("archived")),
                  key=lambda c: c["data"].get("order", 0))


def person(eng, ref):
    ref = ref.lower()
    hits = [u for u in eng.users() if u["id"] != eng.user_id and
            (str(u["id"]) == ref or u["username"].lower() == ref or u["name"].lower() == ref)]
    if len(hits) != 1:
        sys.exit(f"Person „{ref}“ nicht eindeutig gefunden")
    return hits[0]


def cmd_register(server, invite, username, name):
    eng = sync.SyncEngine()
    account, identity = e2e.Account.create(), e2e.Identity()
    response = Api(server).register(invite, username.lower(), name, account.auth,
                                    identity.export_sealed(account), sync.device_name())
    eng.sign_in(server, response, account)
    keyfile = BASE / "notfall-schluessel.json"
    passphrase = e2e.b64(os.urandom(18))
    keyfile.write_text(json.dumps(e2e.export_keyfile(server, username, account, passphrase)))
    (BASE / "notfall-passphrase.txt").write_text(passphrase + "\n")
    for f in (keyfile, BASE / "notfall-passphrase.txt"):
        os.chmod(f, 0o600)
    print("Registriert:", response["user"])


def cmd_status():
    eng = engine()
    print("Server:", eng.server, "| Ich:", eng.user, "| ausstehend:", len(eng.state["pending"]))
    print("Fingerabdruck:", e2e.fingerprint(eng.identity.public))


def cmd_people():
    eng = engine()
    for u in eng.users():
        mark = "ich" if u["id"] == eng.user_id else verified_state(eng, u)
        print(f"{u['id']:>4}  {u['username']:<12} {u['name']:<20} {mark}")


def cmd_verify_show(ref):
    eng = engine()
    other = person(eng, ref)
    show = pairing.VerifyShow(eng.api, other["id"])
    print(f"Code für {other['name']}: {show.code[:3]} {show.code[3:]}", flush=True)
    print("Sicherheitsnummer:", e2e.safety_number(eng.identity.public, other["identity"]), flush=True)
    fingerprint = show.wait(eng.identity.public, eng.users())
    mark_verified(eng, other["id"], fingerprint)
    flush(eng)
    print(f"{other['name']} ist verifiziert ✓")


def cmd_verify_answer(code=None):
    eng = engine()
    deadline = time.time() + 600
    while time.time() < deadline:
        pending = [c for c in eng.api.channels() if c.get("purpose") == "verify"]
        if pending:
            break
        time.sleep(3)
    else:
        sys.exit("Keine Verifizierungsanfrage bekommen.")
    channel = pending[0]
    eng.pull_once()
    other = eng.user_by_id(channel.get("from"))
    print(f"Anfrage von {other['name']}", flush=True)
    code = (code or input("Code: ")).replace(" ", "")
    fingerprint = pairing.verify_enter(eng.api, channel["channel"], code, other["id"],
                                       eng.identity.public, eng.users())
    mark_verified(eng, other["id"], fingerprint)
    flush(eng)
    print(f"{other['name']} ist verifiziert ✓")


def cmd_sync():
    eng = engine()
    flush(eng)
    print("ok")


def cmd_boards():
    eng = engine()
    for b in eng.objects("board"):
        owner = eng.user_name(b.get("owner"))
        print(f"{b['id'][:8]}  {b['data'].get('name', 'Board'):<30} von {owner}  ({b['space']})")


def cmd_board(ref):
    eng = engine()
    board = find(eng, "board", ref)
    print("#", board["data"].get("name"))
    for col in columns(eng, board["id"]):
        print(f"\n## {col['data'].get('name')}  [{col['id'][:8]}]")
        for card in cards(eng, col["id"]):
            d = card["data"]
            extra = []
            if d.get("assignee"):
                extra.append("→ " + eng.user_name(d["assignee"]))
            if d.get("due"):
                extra.append("fällig " + d["due"])
            if d.get("color"):
                extra.append(d["color"])
            print(f"- [{card['id'][:8]}] {d.get('title', '')}" + (f"  ({', '.join(extra)})" if extra else ""))
            if d.get("notes"):
                for line in d["notes"].splitlines():
                    print("      " + line)


def cmd_card(ref):
    eng = engine()
    card = find(eng, "card", ref)
    print(json.dumps({**card, "data": card["data"]}, indent=2, ensure_ascii=False, default=str))


def cmd_move(card_ref, column_ref):
    eng = engine()
    card = find(eng, "card", card_ref)
    col = find(eng, "column", column_ref, board=card["data"]["board"])
    others = cards(eng, col["id"])
    order = (others[-1]["data"].get("order", 0) + 1) if others else 1
    eng.update(card["id"], notify=False, order=order, **model.move_fields(eng, card, col["id"]))
    flush(eng)
    print(f"„{card['data'].get('title')}“ → {col['data'].get('name')}")


def cmd_priority(card_ref, level):
    level = {"keine": None, "niedrig": "niedrig", "mittel": "mittel", "hoch": "hoch"}[level.lower()]
    eng = engine()
    card = find(eng, "card", card_ref)
    eng.update(card["id"], notify=False, priority=level)
    flush(eng)
    print(f"„{card['data'].get('title')}“ → Priorität {level or 'keine'}")


def cmd_trace_commits(board_ref, repo="."):
    """Bidirectional traceability: every commit whose message names a card id
    ("[693b0b1f] …") is listed on that card (field "commits")."""
    import re
    import subprocess
    log = subprocess.run(["git", "-C", repo, "log", "--reverse", "--format=%h%x1f%s%x1f%b%x1e"],
                         capture_output=True, text=True, check=True).stdout
    eng = engine()
    board = find(eng, "board", board_ref)
    cards_by_id = {c["id"][:8]: c for c in eng.objects("card") if c["data"].get("board") == board["id"]}
    found = {}
    for entry in log.split("\x1e"):
        parts = entry.strip("\n").split("\x1f")
        if len(parts) < 3:
            continue
        short, subject, body = parts
        for card_id in dict.fromkeys(re.findall(r"\[([0-9a-f]{8})\]", subject + "\n" + body)):
            if card_id in cards_by_id:
                found.setdefault(card_id, []).append({"h": short, "s": subject})
    changed = 0
    for card_id, commits in found.items():
        card = cards_by_id[card_id]
        known = list(card["data"].get("commits") or [])
        hashes = {c["h"] for c in known}
        merged = known + [c for c in commits if c["h"] not in hashes]
        if merged != known:
            eng.update(card["id"], notify=False, commits=merged)
            changed += 1
            print(f"[{card_id}] {card['data'].get('title', '')[:50]}: " + ", ".join(c["h"] for c in merged))
    flush(eng)
    print(f"{changed} Karten aktualisiert")


def cmd_export(board_ref, path):
    """Board report as PDF (or CSV when the file name ends in .csv)."""
    from linotes import report
    eng = engine()
    board = find(eng, "board", board_ref)
    data = report.build(eng, board["id"])
    (report.write_csv if path.lower().endswith(".csv") else report.write_pdf)(data, path)
    print(f"{len(data['rows'])} Karten → {path}")


def cmd_comment(card_ref, text):
    eng = engine()
    card = find(eng, "card", card_ref)
    notes = card["data"].get("notes", "")
    stamp = time.strftime("%d.%m. %H:%M")
    notes = (notes.rstrip() + "\n\n" if notes.strip() else "") + f"[Claude {stamp}] {text}"
    eng.update(card["id"], notify=False, notes=notes)
    flush(eng)
    print("ok")


def cmd_add(board_ref, column_ref, title, notes=""):
    eng = engine()
    board = find(eng, "board", board_ref)
    col = find(eng, "column", column_ref, board=board["id"])
    others = cards(eng, col["id"])
    order = (others[-1]["data"].get("order", 0) + 1) if others else 1
    eng.put("card", {"board": board["id"], "column": col["id"], "title": title,
                     "notes": notes, "order": order, **model.new_card_fields(eng, col["id"])},
            board.get("share"), notify=False)
    flush(eng)
    print("ok")


DEV_FIELDS = ("impact", "verification", "version")


def cmd_field(card_ref, name, text):
    """Fill a field of a development project card (as in the Ubuntu app's card dialog)."""
    if name not in DEV_FIELDS:
        sys.exit("Feld muss eines von " + ", ".join(DEV_FIELDS) + " sein")
    eng = engine()
    card = find(eng, "card", card_ref)
    eng.update(card["id"], notify=False, **{name: text.strip() or None})
    flush(eng)
    print(f"„{card['data'].get('title')}“: {name} gesetzt")


def cmd_dump(board_ref, path=None):
    eng = engine()
    board = find(eng, "board", board_ref)
    out = {"board": board["data"].get("name"), "dev": bool(board["data"].get("dev")), "cards": []}
    for col in columns(eng, board["id"]):
        for card in cards(eng, col["id"]):
            d = card["data"]
            out["cards"].append({"id": card["id"][:8], "column": col["data"].get("name"), "title": d.get("title"),
                                 "notes": d.get("notes") or "", "commits": [c.get("s") for c in d.get("commits") or []],
                                 **{k: d.get(k) for k in DEV_FIELDS}})
    text = json.dumps(out, indent=1, ensure_ascii=False)
    if path:
        open(path, "w").write(text)
        print(f"{len(out['cards'])} Karten → {path}")
    else:
        print(text)


def main():
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help"):
        print(__doc__)
        return
    name = "cmd_" + sys.argv[1].replace("-", "_")
    func = globals().get(name)
    if not func:
        sys.exit("Unbekannter Befehl: " + sys.argv[1])
    func(*sys.argv[2:])


if __name__ == "__main__":
    main()
