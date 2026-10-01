"""SQLite storage for LiNotes (format version 2: everything end-to-end encrypted).

The server stores opaque, client-encrypted objects. It only knows who owns
an object and which share (if any) it belongs to, and enforces that only
the owner and the members of that share can read or change it.
"""

import hashlib
import json
import os
import secrets
import sqlite3
import threading
import time
from pathlib import Path


KINDS = {"folder", "note", "list", "item", "board", "column", "card", "share", "settings", "contacts", "vault"}
CONFLICT_KINDS = {"note"}
CHANNEL_LIFETIME = 10 * 60
SCHEMA_VERSION = "2"

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY,
    username TEXT UNIQUE NOT NULL,
    display_name TEXT NOT NULL,
    auth TEXT NOT NULL,
    identity_pub TEXT NOT NULL,
    identity_sealed TEXT NOT NULL,
    created REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS sessions (
    token TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id),
    device TEXT,
    created REAL NOT NULL,
    seen REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS invites (
    code TEXT PRIMARY KEY,
    created_by INTEGER,
    used_by INTEGER,
    created REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS shares (
    id TEXT PRIMARY KEY,
    owner INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS share_members (
    share_id TEXT NOT NULL,
    user_id INTEGER NOT NULL,
    PRIMARY KEY (share_id, user_id)
);
CREATE TABLE IF NOT EXISTS objects (
    id TEXT PRIMARY KEY,
    kind TEXT NOT NULL,
    share TEXT,
    owner INTEGER NOT NULL,
    data TEXT NOT NULL,
    deleted INTEGER NOT NULL DEFAULT 0,
    version INTEGER NOT NULL,
    updated REAL NOT NULL,
    updated_by INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS objects_version ON objects(version);
CREATE INDEX IF NOT EXISTS objects_share ON objects(share);
CREATE TABLE IF NOT EXISTS files (
    id TEXT PRIMARY KEY,
    owner INTEGER NOT NULL,
    share TEXT,
    size INTEGER NOT NULL,
    created REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS channels (
    id TEXT PRIMARY KEY,
    purpose TEXT NOT NULL,
    from_user INTEGER,
    to_user INTEGER NOT NULL,
    note TEXT,
    created REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS relay (
    channel TEXT NOT NULL,
    seq INTEGER NOT NULL,
    role TEXT NOT NULL,
    body TEXT NOT NULL,
    PRIMARY KEY (channel, seq)
);
CREATE TABLE IF NOT EXISTS meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""


def auth_hash(auth):
    # `auth` is a 256-bit random value derived on the device, so a plain
    # hash is enough (no password to brute force).
    return hashlib.sha256(("linotes-auth|" + auth).encode()).hexdigest()


def token_hash(token):
    return hashlib.sha256(token.encode()).hexdigest()


class Store:

    def __init__(self, data_dir):
        self.data_dir = Path(data_dir)
        self.files_dir = self.data_dir / "files"
        self.files_dir.mkdir(parents=True, exist_ok=True)
        self.path = self.data_dir / "linotes.db"
        self.local = threading.local()
        self.write_lock = threading.Lock()
        self.changed = threading.Condition()
        with self.connect() as db:
            db.executescript(SCHEMA)
            db.execute("INSERT OR IGNORE INTO meta(key, value) VALUES ('version', '0')")
            db.execute("INSERT OR IGNORE INTO meta(key, value) VALUES ('schema', ?)", (SCHEMA_VERSION,))
        os.chmod(self.path, 0o600)

    def connect(self):
        db = getattr(self.local, "db", None)
        if db is None:
            db = sqlite3.connect(self.path, timeout=30, check_same_thread=False)
            db.row_factory = sqlite3.Row
            db.execute("PRAGMA journal_mode=WAL")
            self.local.db = db
        return db

    def release(self):
        """Nach jedem Request: keine Transaktion (und damit kein veralteter
        Lese-Snapshot oder Schreib-Lock) bleibt am Thread hängen."""
        db = getattr(self.local, "db", None)
        if db is not None and db.in_transaction:
            db.rollback()

    def notify(self):
        with self.changed:
            self.changed.notify_all()

    # --- users --------------------------------------------------

    def create_user(self, db, username, display_name, auth, identity):
        cursor = db.execute(
            "INSERT INTO users(username, display_name, auth, identity_pub, identity_sealed, created) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (username, display_name or username, auth_hash(auth), identity["pub"],
             json.dumps(identity["priv"]), time.time()),
        )
        return cursor.lastrowid

    def register(self, invite, username, display_name, auth, identity):
        with self.write_lock, self.connect() as db:
            row = db.execute("SELECT * FROM invites WHERE code = ? AND used_by IS NULL", (invite.strip().upper(),)).fetchone()
            if row is None:
                return None
            user_id = self.create_user(db, username, display_name, auth, identity)
            db.execute("UPDATE invites SET used_by = ? WHERE code = ?", (user_id, row["code"]))
            return user_id

    def user_by_name(self, username):
        return self.connect().execute("SELECT * FROM users WHERE username = ?", (username.strip().lower(),)).fetchone()

    def user(self, user_id):
        return self.connect().execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()

    def check_auth(self, user, auth):
        return secrets.compare_digest(user["auth"], auth_hash(auth))

    def users(self):
        return [
            {"id": row["id"], "username": row["username"], "name": row["display_name"], "identity": row["identity_pub"]}
            for row in self.connect().execute("SELECT * FROM users ORDER BY id")
        ]

    def delete_user(self, username):
        """Remove an account and everything it owns (admin only). Shares the
        account owned disappear for their members as well."""
        with self.write_lock, self.connect() as db:
            row = db.execute("SELECT id FROM users WHERE username = ?", (username,)).fetchone()
            if row is None:
                return False
            user_id = row[0]
            owned = [r[0] for r in db.execute("SELECT id FROM shares WHERE owner = ?", (user_id,))]
            files = [r[0] for r in db.execute(
                "SELECT id FROM files WHERE owner = ? OR share IN (SELECT id FROM shares WHERE owner = ?)", (user_id, user_id))]
            for share in owned:
                db.execute("DELETE FROM objects WHERE share = ?", (share,))
                db.execute("DELETE FROM share_members WHERE share_id = ?", (share,))
                db.execute("DELETE FROM shares WHERE id = ?", (share,))
            db.execute("DELETE FROM objects WHERE owner = ? AND share IS NULL", (user_id,))
            db.execute("DELETE FROM share_members WHERE user_id = ?", (user_id,))
            db.executemany("DELETE FROM files WHERE id = ?", [(file_id,) for file_id in files])
            db.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,))
            db.execute("DELETE FROM channels WHERE from_user = ? OR to_user = ?", (user_id, user_id))
            db.execute("DELETE FROM users WHERE id = ?", (user_id,))
            # Everyone else must notice that the shares are gone.
            db.execute("UPDATE meta SET value = CAST(value AS INTEGER) + 1 WHERE key = 'version'")
        for file_id in files:
            (self.files_dir / file_id[:2] / file_id).unlink(missing_ok=True)
        return True

    def rename(self, user_id, name):
        with self.write_lock, self.connect() as db:
            db.execute("UPDATE users SET display_name = ? WHERE id = ?", (name, user_id))

    # --- sessions -----------------------------------------------

    def create_session(self, user_id, device):
        token = secrets.token_urlsafe(32)
        now = time.time()
        with self.write_lock, self.connect() as db:
            db.execute(
                "INSERT INTO sessions(token, user_id, device, created, seen) VALUES (?, ?, ?, ?, ?)",
                (token_hash(token), user_id, (device or "")[:80], now, now),
            )
        return token

    def session_user(self, token):
        if not token:
            return None
        db = self.connect()
        row = db.execute(
            "SELECT users.*, sessions.seen AS seen FROM sessions JOIN users ON users.id = sessions.user_id WHERE token = ?",
            (token_hash(token),),
        ).fetchone()
        if row is not None and row["seen"] < time.time() - 600:
            # "Zuletzt gesehen" ist unwichtig: nie den Request daran scheitern
            # lassen und nie eine offene Transaktion zurücklassen.
            now = time.time()
            try:
                with self.write_lock, db:
                    db.execute("UPDATE sessions SET seen = ? WHERE token = ?", (now, token_hash(token)))
            except sqlite3.OperationalError:
                pass
        return row

    def delete_session(self, token):
        with self.write_lock, self.connect() as db:
            db.execute("DELETE FROM sessions WHERE token = ?", (token_hash(token),))

    def sessions(self, user_id):
        return [
            {"device": row["device"], "created": row["created"], "seen": row["seen"]}
            for row in self.connect().execute("SELECT * FROM sessions WHERE user_id = ? ORDER BY seen DESC", (user_id,))
        ]

    # --- invites ------------------------------------------------

    def create_invite(self, created_by=None):
        code = "-".join(secrets.token_hex(2).upper() for _ in range(3))
        with self.write_lock, self.connect() as db:
            db.execute("INSERT INTO invites(code, created_by, created) VALUES (?, ?, ?)", (code, created_by, time.time()))
        return code

    # --- shares -------------------------------------------------

    def member_shares(self, user_id):
        return [row[0] for row in self.connect().execute("SELECT share_id FROM share_members WHERE user_id = ?", (user_id,))]

    def is_member(self, db, share_id, user_id):
        return db.execute(
            "SELECT 1 FROM share_members WHERE share_id = ? AND user_id = ?", (share_id, user_id),
        ).fetchone() is not None

    def share_members(self, share_id):
        return [row[0] for row in self.connect().execute("SELECT user_id FROM share_members WHERE share_id = ?", (share_id,))]

    # --- objects ------------------------------------------------

    def current_version(self):
        return int(self.connect().execute("SELECT value FROM meta WHERE key = 'version'").fetchone()[0])

    VISIBLE = "(owner = ? OR share IN (SELECT share_id FROM share_members WHERE user_id = ?))"

    def changes(self, user_id, since, limit=2000):
        rows = self.connect().execute(
            f"SELECT * FROM objects WHERE version > ? AND {self.VISIBLE} ORDER BY version LIMIT ?",
            (since, user_id, user_id, limit),
        ).fetchall()
        return [self.as_dict(row) for row in rows]

    def get(self, object_id, user_id):
        row = self.connect().execute(
            f"SELECT * FROM objects WHERE id = ? AND {self.VISIBLE}", (object_id, user_id, user_id),
        ).fetchone()
        return self.as_dict(row) if row else None

    @staticmethod
    def as_dict(row):
        return {
            "id": row["id"], "kind": row["kind"], "share": row["share"], "owner": row["owner"],
            "data": json.loads(row["data"]) if not row["deleted"] else {},
            "deleted": bool(row["deleted"]), "version": row["version"],
            "updated": row["updated"], "updated_by": row["updated_by"],
        }

    def apply(self, user_id, changes):
        results = []
        with self.write_lock:
            db = self.connect()
            with db:
                version = [self.current_version()]
                for change in changes:
                    results.append(self.apply_one(db, user_id, change, version))
                db.execute("UPDATE meta SET value = ? WHERE key = 'version'", (str(version[0]),))
        self.notify()
        return results

    def next_version(self, version):
        version[0] += 1
        return version[0]

    def apply_one(self, db, user_id, change, version):
        object_id = str(change.get("id", ""))[:80]
        kind = change.get("kind")
        share = change.get("share") or None
        if not object_id or kind not in KINDS:
            return {"id": object_id, "status": "invalid"}
        data = change.get("data") or {}
        deleted = bool(change.get("deleted"))
        encoded = json.dumps(data, separators=(",", ":"))
        if len(encoded) > 8 * 1024 * 1024:
            return {"id": object_id, "status": "too-large"}

        row = db.execute("SELECT * FROM objects WHERE id = ?", (object_id,)).fetchone()
        now = time.time()

        if kind == "share":
            return self.apply_share(db, user_id, object_id, change, row, encoded, deleted, version)

        if kind in ("settings", "contacts", "vault") and share is not None:
            return {"id": object_id, "status": "invalid"}

        if row is None:
            if share is not None and not self.is_member(db, share, user_id):
                return {"id": object_id, "status": "forbidden"}
            db.execute(
                "INSERT INTO objects(id, kind, share, owner, data, deleted, version, updated, updated_by) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (object_id, kind, share, user_id, "{}" if deleted else encoded, int(deleted),
                 self.next_version(version), now, user_id),
            )
            return {"id": object_id, "status": "ok", "version": version[0]}

        visible = row["owner"] == user_id or (row["share"] and self.is_member(db, row["share"], user_id))
        if not visible or row["kind"] != kind:
            return {"id": object_id, "status": "forbidden"}
        if share != row["share"]:
            # Moving between private and shared (or between shares) is up to the owner.
            if row["owner"] != user_id or (share is not None and not self.is_member(db, share, user_id)):
                return {"id": object_id, "status": "forbidden"}

        base = change.get("base")
        if (kind in CONFLICT_KINDS and not deleted and not row["deleted"] and base is not None
                and int(base) < row["version"] and row["updated_by"] != user_id):
            # The client keeps its version as a copy (it re-encrypts it).
            return {"id": object_id, "status": "conflict", "version": row["version"]}

        db.execute(
            "UPDATE objects SET share = ?, data = ?, deleted = ?, version = ?, updated = ?, updated_by = ? WHERE id = ?",
            (share, "{}" if deleted else encoded, int(deleted), self.next_version(version), now, user_id, object_id),
        )
        return {"id": object_id, "status": "ok", "version": version[0]}

    def apply_share(self, db, user_id, share_id, change, row, encoded, deleted, version):
        """A share object carries the wrapped keys; its member list is
        maintained by the server, and only the owner may change it."""
        existing = db.execute("SELECT * FROM shares WHERE id = ?", (share_id,)).fetchone()
        if existing is not None and existing["owner"] != user_id:
            return {"id": share_id, "status": "forbidden"}
        members = {int(member) for member in change.get("members") or [] if str(member).isdigit()}
        members.add(user_id)
        known = {row[0] for row in db.execute("SELECT id FROM users")}
        if not members <= known:
            return {"id": share_id, "status": "invalid"}
        now = time.time()
        if existing is None:
            db.execute("INSERT INTO shares(id, owner) VALUES (?, ?)", (share_id, user_id))
        before = {r[0] for r in db.execute("SELECT user_id FROM share_members WHERE share_id = ?", (share_id,))}
        if deleted:
            members = set()
        db.execute("DELETE FROM share_members WHERE share_id = ?", (share_id,))
        for member in members:
            db.execute("INSERT INTO share_members(share_id, user_id) VALUES (?, ?)", (share_id, member))
        if row is None:
            db.execute(
                "INSERT INTO objects(id, kind, share, owner, data, deleted, version, updated, updated_by) "
                "VALUES (?, 'share', ?, ?, ?, ?, ?, ?, ?)",
                (share_id, share_id, user_id, "{}" if deleted else encoded, int(deleted),
                 self.next_version(version), now, user_id),
            )
        else:
            db.execute(
                "UPDATE objects SET data = ?, deleted = ?, version = ?, updated = ?, updated_by = ? WHERE id = ?",
                ("{}" if deleted else encoded, int(deleted), self.next_version(version), now, user_id, share_id),
            )
        if members - before:
            # New members must receive everything that is already shared.
            for (object_id,) in db.execute("SELECT id FROM objects WHERE share = ? AND id != ?", (share_id, share_id)).fetchall():
                db.execute("UPDATE objects SET version = ? WHERE id = ?", (self.next_version(version), object_id))
        return {"id": share_id, "status": "ok", "version": version[0]}

    def wait_for_change(self, since, timeout):
        deadline = time.time() + timeout
        with self.changed:
            while self.current_version() <= since:
                remaining = deadline - time.time()
                if remaining <= 0:
                    return False
                self.changed.wait(min(remaining, 5))
        return True

    # --- files --------------------------------------------------

    def add_file(self, user_id, share, content):
        if share is not None and not self.is_member(self.connect(), share, user_id):
            return None
        file_id = secrets.token_hex(16)
        path = self.files_dir / file_id[:2]
        path.mkdir(exist_ok=True)
        (path / file_id).write_bytes(content)
        with self.write_lock, self.connect() as db:
            db.execute("INSERT INTO files(id, owner, share, size, created) VALUES (?, ?, ?, ?, ?)",
                       (file_id, user_id, share, len(content), time.time()))
        return file_id

    def file(self, file_id, user_id):
        db = self.connect()
        row = db.execute("SELECT * FROM files WHERE id = ?", (file_id,)).fetchone()
        if row is None:
            return None
        if row["owner"] != user_id and not (row["share"] and self.is_member(db, row["share"], user_id)):
            return None
        return self.files_dir / file_id[:2] / file_id

    # --- pairing and verification channels ----------------------

    def purge_channels(self, db):
        limit = time.time() - CHANNEL_LIFETIME
        old = [row[0] for row in db.execute("SELECT id FROM channels WHERE created < ?", (limit,))]
        for channel in old:
            db.execute("DELETE FROM relay WHERE channel = ?", (channel,))
            db.execute("DELETE FROM channels WHERE id = ?", (channel,))

    def open_channel(self, purpose, to_user, from_user=None, note=""):
        channel = secrets.token_urlsafe(18)
        with self.write_lock, self.connect() as db:
            self.purge_channels(db)
            db.execute(
                "INSERT INTO channels(id, purpose, from_user, to_user, note, created) VALUES (?, ?, ?, ?, ?, ?)",
                (channel, purpose, from_user, to_user, (note or "")[:80], time.time()),
            )
        self.notify()
        return channel

    def recent_channels(self, to_user, purpose, seconds):
        return self.connect().execute(
            "SELECT COUNT(*) FROM channels WHERE to_user = ? AND purpose = ? AND created > ?",
            (to_user, purpose, time.time() - seconds),
        ).fetchone()[0]

    def pending_channels(self, user_id):
        db = self.connect()
        limit = time.time() - CHANNEL_LIFETIME
        rows = db.execute(
            "SELECT * FROM channels WHERE to_user = ? AND created > ? ORDER BY created DESC", (user_id, limit),
        ).fetchall()
        return [
            {"channel": row["id"], "purpose": row["purpose"], "from": row["from_user"],
             "note": row["note"], "created": row["created"]}
            for row in rows
        ]

    def channel(self, channel):
        row = self.connect().execute(
            "SELECT * FROM channels WHERE id = ? AND created > ?", (channel, time.time() - CHANNEL_LIFETIME),
        ).fetchone()
        return row

    def relay_post(self, channel, role, body):
        with self.write_lock, self.connect() as db:
            count = db.execute("SELECT COUNT(*) FROM relay WHERE channel = ?", (channel,)).fetchone()[0]
            if count >= 12:
                return False
            db.execute("INSERT INTO relay(channel, seq, role, body) VALUES (?, ?, ?, ?)", (channel, count + 1, role, body))
        self.notify()
        return True

    def relay_read(self, channel, after):
        return [
            {"seq": row["seq"], "role": row["role"], "body": row["body"]}
            for row in self.connect().execute(
                "SELECT * FROM relay WHERE channel = ? AND seq > ? ORDER BY seq", (channel, after),
            )
        ]

    def wait_relay(self, channel, after, timeout):
        deadline = time.time() + timeout
        with self.changed:
            while not self.relay_read(channel, after):
                remaining = deadline - time.time()
                if remaining <= 0:
                    return
                self.changed.wait(min(remaining, 5))

    def close_channel(self, channel):
        with self.write_lock, self.connect() as db:
            db.execute("DELETE FROM relay WHERE channel = ?", (channel,))
            db.execute("DELETE FROM channels WHERE id = ?", (channel,))
