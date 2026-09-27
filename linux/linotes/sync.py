"""Offline-first synchronisation with the LiNotes server.

All objects are kept in a local state file. Local edits are applied at once
and queued; a pusher thread sends them, a puller thread long-polls for
changes from other devices. The UI is told about changes on the GLib main
loop.
"""

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

from .api import Api, ApiError, OfflineError


DATA_DIR = Path(GLib.get_user_data_dir()) / "linotes"
CACHE_DIR = Path(GLib.get_user_cache_dir()) / "linotes"
DEFAULT_SERVER = "https://linotes.goip.de"

SECRET_SCHEMA = Secret.Schema.new(
    "io.github.veritasx1.LiNotes",
    Secret.SchemaFlags.NONE,
    {"server": Secret.SchemaAttributeType.STRING, "username": Secret.SchemaAttributeType.STRING},
)


def new_id():
    return uuid.uuid4().hex


def device_name():
    return f"Ubuntu ({socket.gethostname()})"


def store_token(server, username, token):
    Secret.password_store_sync(
        SECRET_SCHEMA, {"server": server, "username": username},
        Secret.COLLECTION_DEFAULT, f"LiNotes ({username})", token, None,
    )


def load_token(server, username):
    return Secret.password_lookup_sync(SECRET_SCHEMA, {"server": server, "username": username}, None)


def clear_token(server, username):
    Secret.password_clear_sync(SECRET_SCHEMA, {"server": server, "username": username}, None)


class SyncEngine:

    def __init__(self):
        DATA_DIR.mkdir(parents=True, exist_ok=True, mode=0o700)
        CACHE_DIR.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.path = DATA_DIR / "state.json"
        self.lock = threading.RLock()
        self.save_lock = threading.Lock()
        self.listeners = []
        self.status_listeners = []
        self.wake = threading.Event()
        self.stopping = threading.Event()
        self.threads = []
        self.online = False
        self.api = None
        self.state = self.load()

    # --- persistence --------------------------------------------

    def load(self):
        try:
            with open(self.path) as handle:
                state = json.load(handle)
        except (OSError, ValueError):
            state = {}
        state.setdefault("server", DEFAULT_SERVER)
        state.setdefault("user", None)
        state.setdefault("users", [])
        state.setdefault("cursor", 0)
        state.setdefault("objects", {})
        state.setdefault("pending", [])
        return state

    def save(self):
        # Pusher, puller and the UI all save; one writer at a time.
        with self.save_lock:
            with self.lock:
                data = json.dumps(self.state, ensure_ascii=False)
            temp = self.path.with_name(f"state.{threading.get_ident()}.tmp")
            fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
            with os.fdopen(fd, "w") as handle:
                handle.write(data)
            os.replace(temp, self.path)

    # --- account ------------------------------------------------

    @property
    def user(self):
        return self.state.get("user")

    @property
    def user_id(self):
        return self.user["id"] if self.user else None

    @property
    def signed_in(self):
        return self.user is not None and self.api is not None and self.api.token

    def restore(self):
        """Resume a saved session; returns True if signed in."""
        user = self.state.get("user")
        if not user:
            return False
        token = load_token(self.state["server"], user["username"])
        if not token:
            return False
        self.api = Api(self.state["server"], token)
        return True

    def sign_in(self, server, response):
        server = server.rstrip("/")
        with self.lock:
            if self.state.get("server") != server or (
                self.state.get("user") and self.state["user"]["id"] != response["user"]["id"]
            ):
                # Different account or server: start from scratch.
                self.state = {"server": server, "user": None, "users": [], "cursor": 0,
                              "objects": {}, "pending": []}
            self.state["server"] = server
            self.state["user"] = response["user"]
            self.state["users"] = response.get("users", [])
        store_token(server, response["user"]["username"], response["token"])
        self.api = Api(server, response["token"])
        self.save()

    def sign_out(self):
        self.stop()
        try:
            if self.api:
                self.api.logout()
        except ApiError:
            pass
        if self.user:
            clear_token(self.state["server"], self.user["username"])
        self.state = {"server": self.state["server"], "user": None, "users": [], "cursor": 0,
                      "objects": {}, "pending": []}
        self.api = None
        self.save()

    def user_name(self, user_id):
        for user in self.state["users"]:
            if user["id"] == user_id:
                return user["name"]
        return "?"

    # --- local objects ------------------------------------------

    def objects(self, kind=None, include_deleted=False):
        with self.lock:
            return [
                obj for obj in self.state["objects"].values()
                if (kind is None or obj["kind"] == kind)
                and (include_deleted or not obj.get("deleted"))
            ]

    def get(self, object_id):
        with self.lock:
            obj = self.state["objects"].get(object_id)
            return obj if obj and not obj.get("deleted") else None

    def put(self, kind, data, space="private", object_id=None, notify=True):
        """Create or update an object locally and queue it for the server."""
        with self.lock:
            object_id = object_id or new_id()
            existing = self.state["objects"].get(object_id)
            obj = {
                "id": object_id,
                "kind": kind,
                "space": space,
                "owner": existing["owner"] if existing else self.user_id,
                "data": copy.deepcopy(data),
                "deleted": False,
                "version": existing.get("version", 0) if existing else 0,
                "updated": time.time(),
                "updated_by": self.user_id,
            }
            self.state["objects"][object_id] = obj
            self.queue(obj)
        if notify:
            self.emit({object_id})
        return obj

    def update(self, object_id, notify=True, **fields):
        obj = self.get(object_id)
        if obj is None:
            return None
        data = dict(obj["data"])
        data.update(fields)
        return self.put(obj["kind"], data, obj["space"], object_id, notify)

    def delete(self, object_id, notify=True):
        with self.lock:
            obj = self.state["objects"].get(object_id)
            if obj is None:
                return
            obj["deleted"] = True
            obj["data"] = {}
            self.queue(obj)
        if notify:
            self.emit({object_id})

    def queue(self, obj):
        change = {
            "id": obj["id"], "kind": obj["kind"], "space": obj["space"],
            "data": obj["data"], "deleted": obj["deleted"], "base": obj.get("version", 0),
        }
        pending = self.state["pending"]
        for index, existing in enumerate(pending):
            if existing["id"] == obj["id"]:
                change["base"] = existing["base"]
                pending[index] = change
                break
        else:
            pending.append(change)
        self.wake.set()

    # --- notifications ------------------------------------------

    def connect(self, callback):
        self.listeners.append(callback)

    def connect_status(self, callback):
        self.status_listeners.append(callback)

    def emit(self, ids):
        for callback in list(self.listeners):
            callback(set(ids))

    def emit_from_thread(self, ids):
        GLib.idle_add(lambda: (self.emit(ids), False)[1])

    def set_online(self, online):
        if online != self.online:
            self.online = online
            GLib.idle_add(lambda: ([callback(online) for callback in self.status_listeners], False)[1])

    # --- background work ----------------------------------------

    def start(self):
        if self.threads:
            return
        self.stopping.clear()
        for target in (self.push_loop, self.pull_loop):
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
            # Collect edits made in quick succession (typing) into one push.
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
                # Never let the sync thread die silently.
                print("LiNotes: Fehler beim Senden:", repr(error))
                time.sleep(5)
                self.wake.set()

    def push_once(self):
        with self.lock:
            batch = copy.deepcopy(self.state["pending"][:200])
        if not batch:
            return
        results = self.api.push(batch)
        self.set_online(True)
        changed = set()
        with self.lock:
            for sent, result in zip(batch, results):
                obj = self.state["objects"].get(sent["id"])
                if result.get("version") and obj is not None:
                    obj["version"] = result["version"]
                # Remove from the queue unless it was edited again meanwhile.
                pending = self.state["pending"]
                for index, current in enumerate(pending):
                    if current["id"] == sent["id"]:
                        if current["data"] == sent["data"] and current["deleted"] == sent["deleted"]:
                            del pending[index]
                        else:
                            current["base"] = result.get("version", current["base"])
                        break
                if result.get("status") in ("forbidden", "invalid"):
                    changed.add(sent["id"])
        self.save()
        if changed:
            self.emit_from_thread(changed)
        if self.state["pending"]:
            self.wake.set()

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
            pending_ids = {change["id"] for change in self.state["pending"]}
            for obj in response["objects"]:
                if obj["id"] in pending_ids:
                    # Our local edit wins until it has been sent.
                    local = self.state["objects"].get(obj["id"])
                    if local is not None:
                        local["version"] = obj["version"]
                    continue
                self.state["objects"][obj["id"]] = obj
                changed.add(obj["id"])
            self.state["cursor"] = response["cursor"]
            if response.get("users"):
                self.state["users"] = response["users"]
        self.save()
        if changed:
            self.emit_from_thread(changed)
        if response.get("more"):
            self.pull_once()

    def sync_now(self):
        """Blocking pull, used once at start-up."""
        self.pull_once()

    def handle_logged_out(self):
        GLib.idle_add(lambda: ([callback(None) for callback in self.status_listeners], False)[1])

    # --- files --------------------------------------------------

    def file_path(self, file_id):
        return CACHE_DIR / "files" / file_id

    def fetch_file(self, file_id):
        """Return the local path of an attachment, downloading if needed."""
        path = self.file_path(file_id)
        if not path.exists():
            content = self.api.download(file_id)
            path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            path.write_bytes(content)
        return path

    def upload_file(self, content, mime, space):
        file_id = self.api.upload(content, mime, space)
        path = self.file_path(file_id)
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        path.write_bytes(content)
        return file_id
