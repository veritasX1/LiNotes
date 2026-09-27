"""LiNotes HTTP API (version 2: end-to-end encrypted, key-based accounts)."""

import os
import re
import threading
import time
from collections import defaultdict, deque

from flask import Flask, abort, g, jsonify, request, send_file

from .store import Store


MAX_UPLOAD = 25 * 1024 * 1024
USERNAME = re.compile(r"^[a-z0-9._-]{2,32}$")
CHANNEL = re.compile(r"^[A-Za-z0-9_-]{16,40}$")


class Limiter:
    """Sliding-window limit per key."""

    def __init__(self, limit, window):
        self.limit = limit
        self.window = window
        self.events = defaultdict(deque)
        self.lock = threading.Lock()

    def hit(self, key):
        """Record an attempt; returns False if the limit is exceeded."""
        with self.lock:
            events = self.events[key]
            now = time.time()
            while events and events[0] < now - self.window:
                events.popleft()
            if len(events) >= self.limit:
                return False
            events.append(now)
            return True

    def blocked(self, key):
        with self.lock:
            events = self.events[key]
            while events and events[0] < time.time() - self.window:
                events.popleft()
            return len(events) >= self.limit


def create_app(data_dir=None):
    app = Flask(__name__)
    app.config["MAX_CONTENT_LENGTH"] = MAX_UPLOAD + 1024 * 1024
    store = Store(data_dir or os.environ.get("LINOTES_DATA", "./data"))
    app.store = store
    login_failures = Limiter(10, 900)
    link_requests_ip = Limiter(20, 3600)
    relay_posts = Limiter(120, 600)

    def address():
        return request.headers.get("X-Real-IP") or request.remote_addr or "?"

    def current_user():
        header = request.headers.get("Authorization", "")
        token = header[7:] if header.startswith("Bearer ") else None
        user = store.session_user(token)
        if user is None:
            abort(401)
        g.token = token
        return user

    def public_user(row):
        return {"id": row["id"], "username": row["username"], "name": row["display_name"], "identity": row["identity_pub"]}

    def session_response(user, device):
        token = store.create_session(user["id"], device)
        return jsonify(
            token=token, user=public_user(user), users=store.users(),
            identity={"pub": user["identity_pub"], "priv": __import__("json").loads(user["identity_sealed"])},
        )

    @app.after_request
    def headers(response):
        response.headers.setdefault("Cache-Control", "no-store")
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response

    for code, name in ((400, "invalid"), (401, "unauthorized"), (403, "forbidden"), (404, "not-found"),
                       (413, "too-large"), (429, "too-many-attempts")):
        app.register_error_handler(code, lambda _error, name=name, code=code: (jsonify(error=name), code))

    @app.get("/api/health")
    def health():
        return jsonify(ok=True, app="LiNotes", protocol=2)

    # --- accounts -----------------------------------------------

    @app.post("/api/register")
    def register():
        if login_failures.blocked(address()):
            return jsonify(error="too-many-attempts"), 429
        body = request.get_json(silent=True) or {}
        username = str(body.get("username", "")).strip().lower()
        auth = str(body.get("auth", ""))
        identity = body.get("identity") or {}
        if not USERNAME.match(username):
            return jsonify(error="invalid-username"), 400
        if len(auth) < 40 or not isinstance(identity.get("pub"), str) or not isinstance(identity.get("priv"), dict):
            return jsonify(error="invalid"), 400
        if store.user_by_name(username) is not None:
            return jsonify(error="username-taken"), 409
        user_id = store.register(str(body.get("invite", "")), username, str(body.get("name", "")).strip()[:60], auth, identity)
        if user_id is None:
            login_failures.hit(address())
            return jsonify(error="invalid-invite"), 403
        return session_response(store.user(user_id), str(body.get("device", "")))

    @app.post("/api/login")
    def login():
        if login_failures.blocked(address()):
            return jsonify(error="too-many-attempts"), 429
        body = request.get_json(silent=True) or {}
        user = store.user_by_name(str(body.get("username", "")))
        if user is None or not store.check_auth(user, str(body.get("auth", ""))):
            login_failures.hit(address())
            app.logger.warning("LiNotes login failed from %s", address())
            return jsonify(error="wrong-credentials"), 401
        return session_response(user, str(body.get("device", "")))

    @app.post("/api/logout")
    def logout():
        current_user()
        store.delete_session(g.token)
        return jsonify(ok=True)

    @app.get("/api/me")
    def me():
        user = current_user()
        return jsonify(user=public_user(user), users=store.users(), devices=store.sessions(user["id"]))

    @app.post("/api/me/name")
    def rename():
        user = current_user()
        name = str((request.get_json(silent=True) or {}).get("name", "")).strip()[:60]
        if name:
            store.rename(user["id"], name)
        return jsonify(ok=True)

    @app.post("/api/invites")
    def invite():
        user = current_user()
        return jsonify(code=store.create_invite(user["id"]))

    # --- sync ---------------------------------------------------

    @app.get("/api/sync")
    def pull():
        user = current_user()
        since = request.args.get("since", default=0, type=int)
        wait = min(request.args.get("wait", default=0, type=int), 30)
        if wait and store.current_version() <= since:
            store.wait_for_change(since, wait)
        known = store.current_version()
        objects = store.changes(user["id"], since)
        more = len(objects) >= 2000
        cursor = objects[-1]["version"] if more else max(since, known)
        return jsonify(objects=objects, cursor=cursor, more=more, users=store.users(),
                       shares=store.member_shares(user["id"]))

    @app.post("/api/sync")
    def push():
        user = current_user()
        changes = (request.get_json(silent=True) or {}).get("changes") or []
        if not isinstance(changes, list) or len(changes) > 500:
            return jsonify(error="invalid"), 400
        return jsonify(results=store.apply(user["id"], changes))

    @app.get("/api/objects/<object_id>")
    def get_object(object_id):
        user = current_user()
        obj = store.get(object_id[:80], user["id"])
        if obj is None:
            abort(404)
        return jsonify(obj)

    # --- files (already encrypted by the client) ----------------

    @app.post("/api/files")
    def upload():
        user = current_user()
        upload = request.files.get("file")
        if upload is None:
            abort(400)
        content = upload.read(MAX_UPLOAD + 1)
        if len(content) > MAX_UPLOAD:
            abort(413)
        share = request.form.get("share") or None
        file_id = store.add_file(user["id"], share, content)
        if file_id is None:
            abort(403)
        return jsonify(id=file_id)

    @app.get("/api/files/<file_id>")
    def download(file_id):
        user = current_user()
        if not re.fullmatch(r"[0-9a-f]{32}", file_id):
            abort(404)
        path = store.file(file_id, user["id"])
        if path is None or not path.exists():
            abort(404)
        response = send_file(path, mimetype="application/octet-stream", max_age=0)
        response.headers["Cache-Control"] = "private, max-age=31536000, immutable"
        return response

    # --- linking a new device / verifying a person --------------

    @app.post("/api/link/request")
    def link_request():
        """A new device asks to join an account (no login yet)."""
        body = request.get_json(silent=True) or {}
        user = store.user_by_name(str(body.get("username", "")))
        if not link_requests_ip.hit(address()):
            abort(429)
        if user is None:
            abort(404)
        if store.recent_channels(user["id"], "link", 600) >= 5:
            abort(429)
        channel = store.open_channel("link", user["id"], note=str(body.get("device", ""))[:80])
        return jsonify(channel=channel)

    @app.post("/api/verify/request")
    def verify_request():
        user = current_user()
        body = request.get_json(silent=True) or {}
        other = store.user(int(body.get("user", 0) or 0))
        if other is None or other["id"] == user["id"]:
            abort(404)
        if store.recent_channels(other["id"], "verify", 600) >= 10:
            abort(429)
        return jsonify(channel=store.open_channel("verify", other["id"], from_user=user["id"]))

    @app.get("/api/channels")
    def channels():
        user = current_user()
        return jsonify(channels=store.pending_channels(user["id"]))

    @app.post("/api/relay/<channel>")
    def relay_post(channel):
        if not CHANNEL.match(channel) or store.channel(channel) is None:
            abort(404)
        if not relay_posts.hit(address()):
            abort(429)
        body = request.get_json(silent=True) or {}
        role = str(body.get("role", ""))[:8]
        payload = str(body.get("body", ""))
        if role not in ("A", "B") or len(payload) > 16_000:
            abort(400)
        if not store.relay_post(channel, role, payload):
            abort(429)
        return jsonify(ok=True)

    @app.get("/api/relay/<channel>")
    def relay_get(channel):
        if not CHANNEL.match(channel) or store.channel(channel) is None:
            abort(404)
        after = request.args.get("after", default=0, type=int)
        wait = min(request.args.get("wait", default=0, type=int), 25)
        if wait:
            store.wait_relay(channel, after, wait)
        return jsonify(messages=store.relay_read(channel, after))

    @app.delete("/api/relay/<channel>")
    def relay_close(channel):
        if CHANNEL.match(channel):
            store.close_channel(channel)
        return jsonify(ok=True)

    return app
