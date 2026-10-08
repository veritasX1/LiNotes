"""Offline-first, end-to-end encrypted synchronisation (protocol v2).

The server only ever sees encrypted objects. This engine keeps the
encrypted server copies in a local state file, decrypts them into memory
for the UI, encrypts local edits before queueing them, and manages shares
(the keys that let other accounts read shared containers).

UI-facing object format (plain):
    {"id", "kind", "share", "space", "owner", "data", "deleted",
     "version", "updated", "updated_by"}
where "space" is "shared" if the object belongs to a share, else "private".
"""

import base64
import copy
import json
import os
import socket
import threading
import time
import uuid
from pathlib import Path

import gi

gi.require_version("Secret", "1")

from gi.repository import GLib, Secret

from . import e2e
from .api import Api, ApiError, OfflineError
from .i18n import _


DATA_DIR = Path(GLib.get_user_data_dir()) / "linotes"
LOCAL_FILES = DATA_DIR / "local-files"
# User id while LiNotes is used without a server.
LOCAL_USER = -1
CACHE_DIR = Path(GLib.get_user_cache_dir()) / "linotes"

SECRET_SCHEMA = Secret.Schema.new(
    "io.github.veritasx1.LiNotes.v2",
    Secret.SchemaFlags.NONE,
    {"server": Secret.SchemaAttributeType.STRING, "username": Secret.SchemaAttributeType.STRING},
)

# Container kinds whose children follow their share.
CHILDREN = {"folder": ("note", "folder"), "list": ("item", "list"), "board": (("column", "card"), "board")}


def new_id():
    return uuid.uuid4().hex


def device_name():
    return _("Ubuntu ({gethostname})", gethostname=socket.gethostname())


def store_credentials(server, username, token, secret):
    value = json.dumps({"token": token, "secret": e2e.b64(secret)})
    Secret.password_store_sync(
        SECRET_SCHEMA, {"server": server, "username": username},
        Secret.COLLECTION_DEFAULT, _("LiNotes ({username})", username=username), value, None,
    )


def load_credentials(server, username):
    value = Secret.password_lookup_sync(SECRET_SCHEMA, {"server": server, "username": username}, None)
    if not value:
        return None, None
    data = json.loads(value)
    return data["token"], e2e.unb64(data["secret"])


def clear_credentials(server, username):
    Secret.password_clear_sync(SECRET_SCHEMA, {"server": server, "username": username}, None)


class VaultConflict(Exception):
    """Both the device and the account have a notes password."""


def remap_id(object_id, uid):
    """notes--1 -> notes-7, board--1-offen -> board-7-offen (see LOCAL_USER)."""
    for prefix in ("notes", "list", "board", "vault", "settings", "contacts"):
        local = f"{prefix}-{LOCAL_USER}"
        if object_id == local or object_id.startswith(local + "-"):
            return f"{prefix}-{uid}" + object_id[len(local):]
    return object_id


def remap_data(value, mapping, uid):
    if isinstance(value, dict):
        return {k: (uid if k in ("by", "created_by", "assignee") and v == LOCAL_USER else remap_data(v, mapping, uid))
                for k, v in value.items()}
    if isinstance(value, list):
        return [remap_data(v, mapping, uid) for v in value]
    if isinstance(value, str):
        return mapping.get(value, value)
    return value


def empty_state(server=""):
    return {"server": server, "user": None, "users": [], "cursor": 0, "remote": {},
            "pending": [], "identity": None, "member_shares": []}


class SyncEngine:

    def __init__(self):
        DATA_DIR.mkdir(parents=True, exist_ok=True, mode=0o700)
        CACHE_DIR.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.path = DATA_DIR / "state-v2.json"
        self.lock = threading.RLock()
        self.save_lock = threading.Lock()
        self.listeners = []
        self.status_listeners = []
        self.channel_listeners = []
        self.wake = threading.Event()
        self.stopping = threading.Event()
        self.threads = []
        self.online = False
        self.api = None
        self.account = None
        self.identity = None
        self.share_keys = {}
        self.plain = {}
        self.seen_channels = set()
        self.save_timer = None
        self.state = self.load()

    # ========================================================
    # PERSISTENCE
    # ========================================================

    def load(self):
        try:
            with open(self.path) as handle:
                state = json.load(handle)
        except (OSError, ValueError):
            state = {}
        base = empty_state()
        base.update(state)
        return base

    def save_soon(self):
        """Write local changes to disk shortly (also offline and without a server)."""
        with self.lock:
            if self.save_timer is not None:
                self.save_timer.cancel()
            self.save_timer = threading.Timer(0.4, self.save)
            self.save_timer.start()

    def save(self):
        """Write the state file. Under the lock only a shallow copy is taken (remote objects and pending
        changes are replaced as a whole, never changed inside); the JSON is then written object by
        object outside the lock, so the window keeps working meanwhile – one big json.dumps held the
        lock and the interpreter for a third of a second after every edit (card b9046682)."""
        with self.save_lock:
            with self.lock:
                snapshot = {key: (dict(value) if key == "remote" else list(value) if key == "pending" else copy.deepcopy(value))
                            for key, value in self.state.items()}
            temp = self.path.with_name(f"state.{threading.get_ident()}.tmp")
            fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
            with os.fdopen(fd, "w") as handle:
                handle.write("{")
                for index, (key, value) in enumerate(snapshot.items()):
                    handle.write(("," if index else "") + json.dumps(key) + ":")
                    if key == "remote":
                        handle.write("{")
                        for number, (object_id, stored) in enumerate(value.items()):
                            handle.write(("," if number else "") + json.dumps(object_id) + ":" + json.dumps(stored, ensure_ascii=False))
                        handle.write("}")
                    elif key == "pending":
                        handle.write("[" + ",".join(json.dumps(change, ensure_ascii=False) for change in value) + "]")
                    else:
                        handle.write(json.dumps(value, ensure_ascii=False))
                handle.write("}")
            os.replace(temp, self.path)

    # ========================================================
    # ACCOUNT
    # ========================================================

    @property
    def user(self):
        return self.state.get("user")

    @property
    def user_id(self):
        return self.user["id"] if self.user else None

    @property
    def server(self):
        return self.state.get("server")

    def restore(self):
        user = self.user
        if not user:
            return False
        token, secret = load_credentials(self.server, user["username"])
        if not secret or (self.server and not token):
            return False
        self.api = Api(self.server, token) if self.server else None
        self.account = e2e.Account(secret)
        self.unlock_identity()
        self.rebuild()
        return True

    def unlock_identity(self):
        sealed = self.state.get("identity")
        if sealed:
            self.identity = e2e.Identity.from_sealed(self.account, sealed)

    def sign_in(self, server, response, account):
        """Store a fresh session (after register, login, link or key file)."""
        server = server.rstrip("/")
        with self.lock:
            same = (self.state.get("server") == server and self.user and self.user["id"] == response["user"]["id"])
            if not same:
                self.state = empty_state(server)
            self.state["server"] = server
            self.state["user"] = response["user"]
            self.state["users"] = response.get("users", [])
            self.state["identity"] = response["identity"]
        store_credentials(server, response["user"]["username"], response["token"], account.secret)
        self.api = Api(server, response["token"])
        self.account = account
        self.unlock_identity()
        self.rebuild()
        self.save()

    # ========================================================
    # WITHOUT A SERVER (everything stays on this computer)
    # ========================================================

    @property
    def is_local(self):
        return bool(self.user) and not self.server

    def start_local(self, name):
        account = e2e.Account.create()
        identity = e2e.Identity()
        with self.lock:
            self.state = empty_state("")
            self.state["user"] = {"id": LOCAL_USER, "username": "", "name": name or _("Ich"), "identity": identity.public}
            self.state["users"] = [self.state["user"]]
            self.state["identity"] = identity.export_sealed(account)
        store_credentials("", "", "", account.secret)
        self.api = None
        self.account = account
        self.unlock_identity()
        self.rebuild()
        self.save()

    def connect_local(self, server, response, account):
        """Move everything made without a server into a server account (new,
        or existing via linking / key file). Blocking. Raises VaultConflict
        before changing anything if both have a notes password."""
        old_account = self.account
        uid = response["user"]["id"]
        temp = Api(server.rstrip("/"), response["token"])
        with self.lock:
            local = [copy.deepcopy(obj) for obj in self.plain.values() if not obj["deleted"]]
        has_vault = any(o["kind"] == "vault" for o in local) and any(o["kind"] == "note" and o["data"].get("enc") for o in local)
        if has_vault:
            try:
                temp.get_object(f"vault-{uid}")
                raise VaultConflict()
            except ApiError:
                pass
        mapping = {}
        if LOCAL_FILES.exists():
            for path in LOCAL_FILES.iterdir():
                content = e2e.open_bytes(old_account.private_key, path.read_bytes(), path.name)
                file_id = temp.upload(e2e.seal_bytes(account.private_key, content, path.name), None)
                mapping[f"local:{path.name}"] = f"{file_id}:{path.name}"
        for obj in local:
            mapping[obj["id"]] = remap_id(obj["id"], uid)
        clear_credentials("", "")
        self.sign_in(server, response, account)
        try:
            self.pull_once()
        except (ApiError, OfflineError):
            pass
        containers = {"folder", "list", "board", "column", "settings", "contacts", "vault"}
        for obj in local:
            new = mapping[obj["id"]]
            # An existing account keeps its own default folder, list and board.
            if new != obj["id"] and obj["kind"] in containers and self.get(new):
                continue
            self.put(obj["kind"], remap_data(obj["data"], mapping, uid), None, new, notify=False)
        if LOCAL_FILES.exists():
            for path in LOCAL_FILES.iterdir():
                path.unlink()
        self.save()
        self.emit_from_thread(set(self.plain))

    def sign_out(self):
        self.stop()
        try:
            if self.api:
                self.api.logout()
        except ApiError:
            pass
        if self.user:
            clear_credentials(self.server, self.user["username"])
        if LOCAL_FILES.exists():
            for path in LOCAL_FILES.iterdir():
                path.unlink()
        self.state = empty_state(self.server or "")
        self.api = self.account = self.identity = None
        self.plain = {}
        self.share_keys = {}
        self.save()

    def users(self):
        return self.state["users"]

    def user_name(self, user_id):
        for user in self.state["users"]:
            if user["id"] == user_id:
                return user["name"]
        return "?"

    def user_by_id(self, user_id):
        return next((user for user in self.state["users"] if user["id"] == user_id), None)

    # ========================================================
    # ENCRYPTION
    # ========================================================

    def key_for(self, share):
        if share is None:
            return self.account.private_key
        return self.share_keys.get(share)

    def encrypt(self, obj):
        """Plain object -> server data."""
        data = obj["data"]
        object_id = obj["id"]
        if obj["kind"] == "share":
            key = self.share_keys[object_id]
            return {"v": 2, "keys": data.get("keys", {}),
                    "m": e2e.seal(key, {k: v for k, v in data.items() if k != "keys"}, f"{object_id}|m")}
        key = self.key_for(obj.get("share"))
        if obj["kind"] == "note":
            body = {k: data[k] for k in ("body", "enc") if k in data}
            meta = {k: v for k, v in data.items() if k not in ("body", "enc")}
            if "body" in data:
                # Title and first line stay readable (for us) when a phone only
                # keeps the note's metadata – see "Auf dem Gerät behalten".
                lines = [b.get("x", "").strip() for b in data["body"] if b.get("x", "").strip()]
                meta["title"] = lines[0][:120] if lines else ""
                meta["preview"] = " ".join(lines[1:])[:160]
            else:
                # Locked notes keep their title visible (like Apple's Notes) – it stays
                # end-to-end encrypted like all metadata; the preview would leak content.
                if "enc" not in data:
                    meta.pop("title", None)
                meta.pop("preview", None)
            return {"v": 2, "m": e2e.seal(key, meta, f"{object_id}|m"), "b": e2e.seal(key, body, f"{object_id}|b")}
        return {"v": 2, "m": e2e.seal(key, data, f"{object_id}|m")}

    def decrypt(self, remote):
        """Server object -> plain object (None if we lack the key)."""
        obj = {key: remote[key] for key in ("id", "kind", "share", "owner", "deleted", "version", "updated", "updated_by")}
        obj["space"] = "shared" if remote.get("share") else "private"
        if remote.get("deleted"):
            obj["data"] = {}
            return obj
        data = remote.get("data") or {}
        try:
            if remote["kind"] == "share":
                wrapped = data.get("keys", {}).get(str(self.user_id))
                if wrapped is None:
                    return None
                key = e2e.unwrap_key(self.identity, wrapped, remote["id"])
                self.share_keys[remote["id"]] = key
                plain = e2e.open_sealed(key, data["m"], f"{remote['id']}|m") if "m" in data else {}
                plain["keys"] = data.get("keys", {})
                obj["data"] = plain
                return obj
            key = self.key_for(remote.get("share"))
            if key is None:
                return None
            plain = e2e.open_sealed(key, data["m"], f"{remote['id']}|m")
            if "b" in data:
                plain.update(e2e.open_sealed(key, data["b"], f"{remote['id']}|b"))
            obj["data"] = plain
            return obj
        except (e2e.CryptoError, KeyError, TypeError) as error:
            print("LiNotes: Objekt nicht lesbar:", remote.get("id"), error)
            return None

    def rebuild(self):
        """Decrypt the local copy of all server objects (shares first)."""
        with self.lock:
            self.plain = {}
            self.share_keys = {}
            remote = self.state["remote"]
            ordered = sorted(remote.values(), key=lambda item: item["kind"] != "share")
            for item in ordered:
                plain = self.decrypt(item)
                if plain is not None:
                    self.plain[item["id"]] = plain
            # Local edits not yet on the server win (they are stored
            # encrypted too, so decrypt them the same way).
            pending = sorted(self.state["pending"], key=lambda change: change["kind"] != "share")
            for change in pending:
                plain = self.decrypt(self.pending_as_remote(change))
                if plain is not None:
                    self.plain[change["id"]] = plain

    def pending_as_remote(self, change):
        existing = self.state["remote"].get(change["id"])
        return {
            "id": change["id"], "kind": change["kind"], "share": change.get("share"),
            "owner": existing["owner"] if existing else self.user_id,
            "data": change["data"], "deleted": change["deleted"], "version": change.get("base", 0),
            "updated": change.get("updated", time.time()), "updated_by": self.user_id,
        }

    # ========================================================
    # LOCAL OBJECTS
    # ========================================================

    def objects(self, kind=None, include_deleted=False):
        with self.lock:
            return [
                obj for obj in self.plain.values()
                if (kind is None or obj["kind"] == kind) and (include_deleted or not obj.get("deleted"))
            ]

    def get(self, object_id):
        with self.lock:
            obj = self.plain.get(object_id)
            return obj if obj and not obj.get("deleted") else None

    def put(self, kind, data, share=None, object_id=None, notify=True, members=None):
        """Create or update an object locally, encrypt it and queue it."""
        with self.lock:
            object_id = object_id or new_id()
            existing = self.plain.get(object_id)
            obj = {
                "id": object_id, "kind": kind, "share": share,
                "space": "shared" if share else "private",
                "owner": existing["owner"] if existing else self.user_id,
                "data": copy.deepcopy(data), "deleted": False,
                "version": existing.get("version", 0) if existing else 0,
                "updated": time.time(), "updated_by": self.user_id,
            }
            self.plain[object_id] = obj
            self.queue(obj, members)
        if notify:
            self.emit({object_id})
        return obj

    def update(self, object_id, notify=True, **fields):
        obj = self.get(object_id)
        if obj is None:
            return None
        data = dict(obj["data"])
        data.update(fields)
        return self.put(obj["kind"], data, obj.get("share"), object_id, notify)

    def delete(self, object_id, notify=True):
        with self.lock:
            obj = self.plain.get(object_id)
            if obj is None:
                return
            obj = dict(obj, deleted=True, data={})
            self.plain[object_id] = obj
            self.queue(obj)
        if notify:
            self.emit({object_id})

    def queue(self, obj, members=None):
        change = {
            "id": obj["id"], "kind": obj["kind"], "share": obj.get("share"),
            "data": {} if obj["deleted"] else self.encrypt(obj),
            "deleted": obj["deleted"], "base": obj.get("version", 0), "updated": obj["updated"],
        }
        if obj["kind"] == "share":
            change["members"] = members if members is not None else [
                int(uid) for uid in obj["data"].get("keys", {}) if int(uid) != self.user_id
            ]
        pending = self.state["pending"]
        for index, existing in enumerate(pending):
            if existing["id"] == obj["id"]:
                change["base"] = existing["base"]
                # Move to the end: a new share must reach the server before
                # the objects that were just moved into it.
                del pending[index]
                break
        pending.append(change)
        self.wake.set()
        self.save_soon()

    # ========================================================
    # SHARES
    # ========================================================

    def container_members(self, obj):
        """Objects that move together with `obj` into or out of a share.
        A folder takes everything inside along (like Apple's shared folders):
        subfolders, their notes, lists with their items, boards with columns and cards."""
        kind = obj["kind"]
        result = [obj]
        if kind == "folder":
            tree, todo = {obj["id"]}, [obj["id"]]
            folders = self.objects("folder")
            while todo:
                parent = todo.pop()
                for folder in folders:
                    if folder["data"].get("parent") == parent and folder["id"] not in tree:
                        tree.add(folder["id"])
                        todo.append(folder["id"])
                        result.append(folder)
            result += [n for n in self.objects("note") if n["data"].get("folder") in tree]
            for container in self.objects("list") + self.objects("board") + self.objects("plan"):
                if container["data"].get("folder") in tree:
                    result += self.container_members(container)
        elif kind == "list":
            result += [i for i in self.objects("item") if i["data"].get("list") == obj["id"]]
        elif kind == "board":
            result += [c for c in self.objects("column") + self.objects("card") if c["data"].get("board") == obj["id"]]
        return result

    def share_after_move(self, obj, folder_id):
        field = "parent" if obj["kind"] == "folder" else "folder"
        target = self.get(folder_id) if folder_id else None
        old_place = self.get(obj["data"].get(field) or "")
        if target is not None and target.get("share"):
            return target["share"]
        if obj.get("share") and old_place is not None and old_place.get("share") == obj.get("share"):
            return None  # it was shared through its old folder
        return obj.get("share")

    def move_to_folder(self, object_id, folder_id):
        """Move a folder (field "parent"), list or board (field "folder") into a folder
        (None = top / no folder). Into a shared folder it takes on the folder's share
        with everything inside (re-encrypted); out of it, it becomes private again –
        unless it was shared on its own. Blocking (pictures are uploaded again)."""
        obj = self.get(object_id)
        if obj is None:
            return
        field = "parent" if obj["kind"] == "folder" else "folder"
        share = self.share_after_move(obj, folder_id)
        # Runs in a worker thread: the window is told on the main loop (GTK is not thread-safe).
        if share == obj.get("share"):
            self.update(object_id, notify=False, **{field: folder_id})
            self.emit_from_thread({object_id})
            return
        for item in self.container_members(obj):
            data = self.rekey_files(item, share)
            if item["id"] == object_id:
                data[field] = folder_id
            self.put(item["kind"], data, share, item["id"], notify=False)
        self.emit_from_thread({object_id})

    def share_members(self, share_id):
        share = self.get(share_id) if share_id else None
        if share is None:
            return []
        return sorted(int(uid) for uid in share["data"].get("keys", {}))

    def set_sharing(self, object_id, member_ids):
        """Share a container (or single note) with exactly `member_ids`
        (besides the owner). An empty list makes it private again.
        Removing someone always rotates the key (card 5939587a, Olaf: „Privatsphäre
        first“): own objects move at once; other people's stay readable in the old
        share for those who remain until their owners move them (follow_moved_shares)."""
        obj = self.get(object_id)
        if obj is None:
            return
        member_ids = sorted(set(member_ids) - {self.user_id})
        current = obj.get("share")
        current_members = [uid for uid in self.share_members(current) if uid != self.user_id]
        if current and set(member_ids) == set(current_members):
            return current
        old = self.get(current) if current else None
        own_share = old is not None and old["owner"] == self.user_id and old["data"].get("target") == object_id
        foreign = [item for item in self.container_members(obj) if item["owner"] != self.user_id]
        # Card fc38cfad (lost cards twice on 08.10.): the server lets only an object's owner move it to another share, so
        # other people's cards stayed behind in the old share – whose keys were then emptied. Adding people keeps the
        # share and wraps its key for them.
        if own_share and set(current_members) <= set(member_ids):
            self.rewrap_share(current, member_ids)
            self.emit_from_thread({object_id})
            return current

        new_share = None
        if member_ids:
            new_share = "share-" + new_id()
            key = e2e.new_key()
            self.share_keys[new_share] = key
            keys = {}
            for uid in [self.user_id] + member_ids:
                user = self.user_by_id(uid)
                if user is None or not user.get("identity"):
                    raise ValueError(_("Unbekannter Account {uid}", uid=uid))
                keys[str(uid)] = e2e.wrap_key(key, user["identity"], new_share)
            self.put("share", {"keys": keys, "target": object_id, "name": obj["data"].get("name") or obj["kind"]},
                     new_share, new_share, notify=False, members=member_ids)

        # Re-encrypt the container and its content with the new key
        # (attachments are uploaded again, encrypted with the new key).
        for item in self.container_members(obj):
            if item["owner"] != self.user_id:
                continue   # the server would refuse it; it stays readable in the share it is in (card fc38cfad)
            data = self.rekey_files(item, new_share)
            self.put(item["kind"], data, new_share, item["id"], notify=False)
        # The old share is emptied only when it was this object's own and nothing of anyone else is left in it – a
        # folder's share stays for the folder (card fc38cfad). With others' objects inside it keeps only those who stay
        # and points to the new share: their owners move them there on their next sync (card 5939587a).
        if current and current != new_share and own_share:
            if foreign:
                stay = {str(uid) for uid in [self.user_id] + member_ids}
                keys = {uid: wrapped for uid, wrapped in old["data"].get("keys", {}).items() if uid in stay}
                self.put("share", dict(old["data"], keys=keys, moved_to=new_share), current, current, notify=False, members=member_ids)
            else:
                self.put("share", dict(old["data"], keys={}), current, current, notify=False, members=[])
        # Called from a worker thread (run_async): tell the window on the main loop.
        self.emit_from_thread({object_id})
        return new_share

    def follow_moved_shares(self):
        """Someone was removed from a share holding my objects (card 5939587a): the share now points to its successor –
        I move mine there, re-encrypted with its key. The share's owner empties it once nothing is left inside."""
        moves = []
        with self.lock:
            for share in [o for o in self.plain.values() if o["kind"] == "share" and not o["deleted"]]:
                target = share["data"].get("moved_to")
                if not target or target not in self.share_keys:
                    continue
                inside = [o for o in self.plain.values() if o.get("share") == share["id"] and o["kind"] != "share" and not o["deleted"]]
                mine = [o for o in inside if o["owner"] == self.user_id]
                moves.append((share, target, mine, len(inside) - len(mine)))
        for share, target, mine, others in moves:
            for item in mine:
                self.put(item["kind"], self.rekey_files(item, target), target, item["id"], notify=False)
            if share["owner"] == self.user_id and not others and share["data"].get("keys"):
                self.put("share", dict(share["data"], keys={}), share["id"], share["id"], notify=False, members=[])
        return any(mine for _s, _t, mine, _o in moves)

    def rewrap_share(self, share_id, member_ids):
        """The share's key, wrapped for exactly the owner and `member_ids`: those who stay keep their entry, new
        ones get the same key – nothing is re-encrypted, nobody's objects move (card fc38cfad)."""
        old = self.get(share_id)
        key = self.share_keys[share_id]
        keys = {}
        for uid in [self.user_id] + member_ids:
            wrapped = old["data"].get("keys", {}).get(str(uid))
            if wrapped is None:
                user = self.user_by_id(uid)
                if user is None or not user.get("identity"):
                    raise ValueError(_("Unbekannter Account {uid}", uid=uid))
                wrapped = e2e.wrap_key(key, user["identity"], share_id)
            keys[str(uid)] = wrapped
        self.put("share", dict(old["data"], keys=keys), share_id, share_id, notify=False, members=member_ids)

    def rekey_files(self, item, new_share):
        data = copy.deepcopy(item["data"])
        for block in data.get("body") or []:
            # Pictures, attached files and link-preview pictures are encrypted with the share's key.
            if block.get("t") in ("image", "file", "link") and block.get("f"):
                try:
                    content = self.fetch_file(block["f"], item.get("share")).read_bytes()
                    block["f"] = self.upload_file(content, new_share)
                except (ApiError, e2e.CryptoError, OSError) as error:
                    print("LiNotes: Bild konnte nicht neu verschlüsselt werden:", error)
        return data

    # ========================================================
    # KEY FILE – recommended, never forced (first start stays simple)
    # ========================================================

    def settings(self):
        obj = self.get(f"settings-{self.user_id}")
        return dict(obj["data"]) if obj else {}

    def update_settings(self, **fields):
        data = self.settings()
        data.update(fields)
        self.put("settings", data, None, f"settings-{self.user_id}")

    def pro_features(self):
        """Profi-Funktionen (code colors, footnotes …): off by default so the app stays simple
        ("Tante Erna" first); a setting of the account, so every device follows."""
        return bool(self.settings().get("pro"))

    def set_pro_features(self, on):
        self.update_settings(pro=bool(on))

    def keyfile_saved(self):
        return bool(self.settings().get("keyfile_saved"))

    def mark_keyfile_saved(self):
        self.update_settings(keyfile_saved=time.time())

    def keyfile_hint_due(self):
        """A gentle reminder once the account has been in use for a few days."""
        if not self.server or self.keyfile_saved():
            return False
        data = self.settings()
        if not data.get("since"):
            self.update_settings(since=time.time())
            return False
        return time.time() - data["since"] > 3 * 86400 and time.time() > data.get("keyfile_hint_until", 0)

    def snooze_keyfile_hint(self):
        self.update_settings(keyfile_hint_until=time.time() + 30 * 86400)

    # ========================================================
    # NOTIFICATIONS
    # ========================================================

    def connect(self, callback):
        self.listeners.append(callback)

    def connect_status(self, callback):
        self.status_listeners.append(callback)

    def connect_channels(self, callback):
        self.channel_listeners.append(callback)

    def emit(self, ids):
        for callback in list(self.listeners):
            callback(set(ids))

    def emit_from_thread(self, ids):
        GLib.idle_add(lambda: (self.emit(ids), False)[1])

    def set_online(self, online):
        if online != self.online:
            self.online = online
            GLib.idle_add(lambda: ([callback(online) for callback in self.status_listeners], False)[1])

    # ========================================================
    # BACKGROUND WORK
    # ========================================================

    def start(self):
        if self.threads or not self.api:
            return
        self.stopping.clear()
        for target in (self.push_loop, self.pull_loop, self.channel_loop):
            thread = threading.Thread(target=target, daemon=True)
            thread.start()
            self.threads.append(thread)
        self.wake.set()

    def stop(self):
        self.stopping.set()
        self.wake.set()
        self.threads = []

    def push_loop(self):
        delay = 2
        while not self.stopping.is_set():
            self.wake.wait(30)
            self.wake.clear()
            if self.stopping.is_set():
                return
            time.sleep(0.6)
            try:
                self.push_once()
                delay = 2
            except OfflineError:
                self.set_online(False)
                time.sleep(delay)
                delay = min(delay * 2, 60)
                self.wake.set()
            except ApiError as error:
                if error.status == 401:
                    self.handle_logged_out()
                    return
                time.sleep(5)
            except Exception as error:
                print("LiNotes: Fehler beim Senden:", repr(error))
                time.sleep(5)
                self.wake.set()

    def push_once(self):
        with self.lock:
            batch = copy.deepcopy(self.state["pending"][:200])
        if not batch:
            return
        wire = [{k: v for k, v in change.items() if k != "updated"} for change in batch]
        results = self.api.push(wire)
        self.set_online(True)
        changed = set()
        conflicts = []
        with self.lock:
            for sent, result in zip(batch, results):
                status = result.get("status")
                pending = self.state["pending"]
                index = next((i for i, c in enumerate(pending) if c["id"] == sent["id"]), None)
                if status == "conflict":
                    conflicts.append(sent)
                    if index is not None:
                        del pending[index]
                    continue
                if status == "ok":
                    stored = {k: sent[k] for k in ("id", "kind", "share", "data", "deleted")}
                    owner = self.plain.get(sent["id"], {}).get("owner", self.user_id)
                    stored.update(owner=owner, version=result["version"],
                                  updated=time.time(), updated_by=self.user_id)
                    self.state["remote"][sent["id"]] = stored
                    if sent["id"] in self.plain:
                        self.plain[sent["id"]]["version"] = result["version"]
                if index is not None:
                    current = pending[index]
                    if current["data"] == sent["data"] and current["deleted"] == sent["deleted"] or status != "ok":
                        del pending[index]
                    else:
                        current["base"] = result.get("version", current["base"])
                if status in ("forbidden", "invalid", "too-large"):
                    print("LiNotes: Server lehnt ab:", sent["id"], status)
                    changed.add(sent["id"])
        for sent in conflicts:
            self.resolve_conflict(sent)
            changed.add(sent["id"])
        self.save()
        if changed:
            with self.lock:
                self.rebuild()
            self.emit_from_thread(changed)
        if self.state["pending"]:
            self.wake.set()

    def resolve_conflict(self, sent):
        """Someone else changed the note meanwhile: keep theirs, save ours as a copy."""
        try:
            remote = self.api.get_object(sent["id"])
        except ApiError:
            return
        with self.lock:
            self.state["remote"][remote["id"]] = remote
            mine = self.decrypt(self.pending_as_remote(sent))
        if mine and not mine.get("deleted"):
            data = dict(mine["data"])
            data["conflict"] = True
            body = data.get("body")
            if body and body[0].get("x") is not None:
                body = copy.deepcopy(body)
                body[0]["x"] = body[0]["x"] + _(" (Konflikt)")
                data["body"] = body
            self.put("note", data, mine.get("share"), notify=False)

    def pull_loop(self):
        delay = 2
        while not self.stopping.is_set():
            try:
                self.pull_once(wait=25)
                delay = 2
            except OfflineError:
                self.set_online(False)
                self.stopping.wait(delay)
                delay = min(delay * 2, 60)
            except ApiError as error:
                if error.status == 401:
                    self.handle_logged_out()
                    return
                self.stopping.wait(10)
            except Exception as error:
                print("LiNotes: Fehler beim Abrufen:", repr(error))
                self.stopping.wait(5)

    def pull_once(self, wait=0):
        response = self.api.pull(self.state["cursor"], wait)
        self.set_online(True)
        changed = set()
        with self.lock:
            remote = self.state["remote"]
            for item in response["objects"]:
                remote[item["id"]] = item
                changed.add(item["id"])
            # Drop what is no longer shared with us.
            member = set(response.get("shares", []))
            for object_id, item in list(remote.items()):
                if item.get("share") and item["share"] not in member and item.get("owner") != self.user_id:
                    del remote[object_id]
                    changed.add(object_id)
            self.state["member_shares"] = sorted(member)
            self.state["cursor"] = response["cursor"]
            if response.get("users"):
                self.state["users"] = response["users"]
            if changed:
                self.rebuild()
        self.save()
        if changed:
            self.follow_moved_shares()   # card 5939587a
            self.emit_from_thread(changed)
        if response.get("more"):
            self.pull_once()

    def sync_now(self):
        if not self.api:
            return
        self.push_once()
        self.pull_once()

    def channel_loop(self):
        """Watch for devices that want to join and people who want to verify."""
        while not self.stopping.is_set():
            try:
                for channel in self.api.channels():
                    if channel["channel"] not in self.seen_channels:
                        self.seen_channels.add(channel["channel"])
                        # Someone new (e.g. just registered): refresh the list of people first.
                        if channel.get("from") and self.user_by_id(channel["from"]) is None:
                            try:
                                self.pull_once()
                            except Exception:
                                pass
                        GLib.idle_add(lambda c=channel: ([cb(c) for cb in self.channel_listeners], False)[1])
            except Exception:
                pass
            self.stopping.wait(4)

    def handle_logged_out(self):
        GLib.idle_add(lambda: ([callback(None) for callback in self.status_listeners], False)[1])

    # ========================================================
    # FILES (encrypted with the key of their container)
    # ========================================================

    def file_path(self, file_id):
        return CACHE_DIR / "files" / file_id

    def fetch_file(self, reference, share=None):
        """Local path of a decrypted attachment (downloads if needed).
        `reference` is "<server file id>:<name>"; the name is the AAD."""
        file_id, _sep, name = reference.partition(":")
        name = name or file_id
        path = self.file_path(name)
        if not path.exists() and file_id == "local":
            content = e2e.open_bytes(self.key_for(None), (LOCAL_FILES / name).read_bytes(), name)
            path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            path.write_bytes(content)
        elif not path.exists():
            blob = self.api.download(file_id)
            content = e2e.open_bytes(self.key_for(share), blob, name)
            path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            path.write_bytes(content)
        return path

    def upload_file(self, content, share=None, progress=None):
        # The file id is unknown before the upload, so the AAD is a
        # separate random name kept inside the encrypted note.
        name = new_id()
        blob = e2e.seal_bytes(self.key_for(share), content, name)
        if not self.server:
            # Without a server: keep it (encrypted) on this computer.
            LOCAL_FILES.mkdir(parents=True, exist_ok=True, mode=0o700)
            (LOCAL_FILES / name).write_bytes(blob)
            file_id = "local"
        else:
            file_id = self.api.upload(blob, share, progress=progress)
        path = self.file_path(name)
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        path.write_bytes(content)
        return f"{file_id}:{name}"
