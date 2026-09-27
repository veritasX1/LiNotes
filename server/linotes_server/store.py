"""SQLite storage for LiNotes.

Everything the clients sync is an *object*: ``{id, kind, space, owner, data,
deleted, version}``. ``version`` is a server-wide, ever increasing number, so
a client only needs to remember the highest version it has seen.
"""

import hashlib
import json
import os
import secrets
import sqlite3
import threading
import time
from pathlib import Path


KINDS = {"folder", "note", "list", "item", "board", "column", "card", "vault", "settings"}
SPACES = {"private", "shared"}

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY,
    username TEXT UNIQUE NOT NULL,
    display_name TEXT NOT NULL,
    password TEXT NOT NULL,
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
CREATE TABLE IF NOT EXISTS objects (
    id TEXT PRIMARY KEY,
    kind TEXT NOT NULL,
    space TEXT NOT NULL,
    owner INTEGER NOT NULL,
    data TEXT NOT NULL,
    deleted INTEGER NOT NULL DEFAULT 0,
    version INTEGER NOT NULL,
    updated REAL NOT NULL,
    updated_by INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS objects_version ON objects(version);
CREATE TABLE IF NOT EXISTS files (
    id TEXT PRIMARY KEY,
    owner INTEGER NOT NULL,
    space TEXT NOT NULL,
    mime TEXT NOT NULL,
    size INTEGER NOT NULL,
    created REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""


def hash_password(password, salt=None):
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=2**15, r=8, p=1, maxmem=64 * 1024 * 1024)
    return "scrypt$" + salt.hex() + "$" + digest.hex()


def check_password(password, stored):
    try:
        _scheme, salt, digest = stored.split("$")
    except ValueError:
        return False
    candidate = hash_password(password, bytes.fromhex(salt)).split("$")[2]
    return secrets.compare_digest(candidate, digest)


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
        # Woken whenever something changes, for long-polling clients.
        self.changed = threading.Condition()
        with self.connect() as db:
            db.executescript(SCHEMA)
            db.execute("INSERT OR IGNORE INTO meta(key, value) VALUES ('version', '0')")
        os.chmod(self.path, 0o600)

    def connect(self):
        db = getattr(self.local, "db", None)
        if db is None:
            db = sqlite3.connect(self.path, timeout=30, check_same_thread=False)
            db.row_factory = sqlite3.Row
            db.execute("PRAGMA journal_mode=WAL")
            db.execute("PRAGMA foreign_keys=ON")
            self.local.db = db
        return db

    # --- users --------------------------------------------------

    def create_user(self, username, display_name, password):
        username = username.strip().lower()
        with self.write_lock, self.connect() as db:
            cursor = db.execute(
                "INSERT INTO users(username, display_name, password, created) VALUES (?, ?, ?, ?)",
                (username, display_name.strip() or username, hash_password(password), time.time()),
            )
            return cursor.lastrowid

    def user_by_name(self, username):
        return self.connect().execute(
            "SELECT * FROM users WHERE username = ?", (username.strip().lower(),)
        ).fetchone()

    def user(self, user_id):
        return self.connect().execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()

    def users(self):
        return [
            {"id": row["id"], "username": row["username"], "name": row["display_name"]}
            for row in self.connect().execute("SELECT * FROM users ORDER BY id")
        ]

    def set_password(self, user_id, password):
        with self.write_lock, self.connect() as db:
            db.execute("UPDATE users SET password = ? WHERE id = ?", (hash_password(password), user_id))
            # Log out every other device.
            db.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,))

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
            "SELECT users.* FROM sessions JOIN users ON users.id = sessions.user_id WHERE token = ?",
            (token_hash(token),),
        ).fetchone()
        if row is not None:
            now = time.time()
            # Update "last seen" at most every ten minutes.
            db.execute(
                "UPDATE sessions SET seen = ? WHERE token = ? AND seen < ?",
                (now, token_hash(token), now - 600),
            )
            db.commit()
        return row

    def delete_session(self, token):
        with self.write_lock, self.connect() as db:
            db.execute("DELETE FROM sessions WHERE token = ?", (token_hash(token),))

    # --- invites ------------------------------------------------

    def create_invite(self, created_by=None):
        code = "-".join(secrets.token_hex(2).upper() for _ in range(3))
        with self.write_lock, self.connect() as db:
            db.execute(
                "INSERT INTO invites(code, created_by, created) VALUES (?, ?, ?)",
                (code, created_by, time.time()),
            )
        return code

    def use_invite(self, code, username, display_name, password):
        code = code.strip().upper()
        with self.write_lock, self.connect() as db:
            row = db.execute(
                "SELECT * FROM invites WHERE code = ? AND used_by IS NULL", (code,)
            ).fetchone()
            if row is None:
                return None
            cursor = db.execute(
                "INSERT INTO users(username, display_name, password, created) VALUES (?, ?, ?, ?)",
                (username.strip().lower(), display_name.strip() or username, hash_password(password), time.time()),
            )
            db.execute("UPDATE invites SET used_by = ? WHERE code = ?", (cursor.lastrowid, code))
            return cursor.lastrowid

    # --- objects ------------------------------------------------

    def current_version(self):
        return int(self.connect().execute("SELECT value FROM meta WHERE key = 'version'").fetchone()[0])

    def visible(self, row, user_id):
        return row["space"] == "shared" or row["owner"] == user_id

    def changes(self, user_id, since, limit=2000):
        rows = self.connect().execute(
            "SELECT * FROM objects WHERE version > ? AND (space = 'shared' OR owner = ?) "
            "ORDER BY version LIMIT ?",
            (since, user_id, limit),
        ).fetchall()
        return [self.as_dict(row) for row in rows]

    @staticmethod
    def as_dict(row):
        return {
            "id": row["id"],
            "kind": row["kind"],
            "space": row["space"],
            "owner": row["owner"],
            "data": json.loads(row["data"]) if not row["deleted"] else {},
            "deleted": bool(row["deleted"]),
            "version": row["version"],
            "updated": row["updated"],
            "updated_by": row["updated_by"],
        }

    def apply(self, user_id, changes):
        """Apply client changes. Returns one result per change."""
        results = []
        with self.write_lock:
            db = self.connect()
            with db:
                version = self.current_version()
                for change in changes:
                    result = self.apply_one(db, user_id, change, version)
                    if result.get("version"):
                        version = max(version, result["version"])
                    results.append(result)
                db.execute("UPDATE meta SET value = ? WHERE key = 'version'", (str(version),))
        with self.changed:
            self.changed.notify_all()
        return results

    def apply_one(self, db, user_id, change, version):
        object_id = str(change.get("id", ""))[:80]
        kind = change.get("kind")
        space = change.get("space", "private")
        if not object_id or kind not in KINDS or space not in SPACES:
            return {"id": object_id, "status": "invalid"}
        if kind in ("vault", "settings") and space != "private":
            return {"id": object_id, "status": "invalid"}

        data = change.get("data") or {}
        deleted = bool(change.get("deleted"))
        base = change.get("base")
        encoded = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
        if len(encoded) > 8 * 1024 * 1024:
            return {"id": object_id, "status": "too-large"}

        row = db.execute("SELECT * FROM objects WHERE id = ?", (object_id,)).fetchone()
        now = time.time()

        if row is None:
            version += 1
            db.execute(
                "INSERT INTO objects(id, kind, space, owner, data, deleted, version, updated, updated_by) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (object_id, kind, space, user_id, "{}" if deleted else encoded, int(deleted), version, now, user_id),
            )
            return {"id": object_id, "status": "ok", "version": version}

        if not self.visible(row, user_id):
            return {"id": object_id, "status": "forbidden"}
        # Only the owner may move an object between private and shared.
        if space != row["space"] and row["owner"] != user_id:
            return {"id": object_id, "status": "forbidden"}

        # Concurrent edits of a note are kept as a copy rather than lost.
        if (
            kind == "note" and not deleted and not row["deleted"]
            and base is not None and int(base) < row["version"]
            and row["updated_by"] != user_id
        ):
            copy_id = object_id + "-k" + secrets.token_hex(3)
            data = dict(data)
            data["conflict"] = True
            version += 1
            db.execute(
                "INSERT INTO objects(id, kind, space, owner, data, deleted, version, updated, updated_by) "
                "VALUES (?, ?, ?, ?, ?, 0, ?, ?, ?)",
                (copy_id, kind, space, user_id, json.dumps(data, ensure_ascii=False), version, now, user_id),
            )
            return {"id": object_id, "status": "conflict", "copy": copy_id, "version": version}

        version += 1
        db.execute(
            "UPDATE objects SET kind = ?, space = ?, data = ?, deleted = ?, version = ?, updated = ?, updated_by = ? "
            "WHERE id = ?",
            (kind, space, "{}" if deleted else encoded, int(deleted), version, now, user_id, object_id),
        )
        return {"id": object_id, "status": "ok", "version": version}

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

    def add_file(self, user_id, space, mime, content):
        file_id = secrets.token_hex(16)
        path = self.files_dir / file_id[:2]
        path.mkdir(exist_ok=True)
        (path / file_id).write_bytes(content)
        with self.write_lock, self.connect() as db:
            db.execute(
                "INSERT INTO files(id, owner, space, mime, size, created) VALUES (?, ?, ?, ?, ?, ?)",
                (file_id, user_id, space, mime, len(content), time.time()),
            )
        return file_id

    def file(self, file_id, user_id):
        row = self.connect().execute("SELECT * FROM files WHERE id = ?", (file_id,)).fetchone()
        if row is None or not (row["space"] == "shared" or row["owner"] == user_id):
            return None, None
        return row, self.files_dir / file_id[:2] / file_id
