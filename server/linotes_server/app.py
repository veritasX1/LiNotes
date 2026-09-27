"""LiNotes HTTP API."""

import os
import re
import threading
import time
from collections import defaultdict, deque

from flask import Flask, abort, g, jsonify, request, send_file

from .store import Store, check_password


MAX_UPLOAD = 25 * 1024 * 1024
USERNAME = re.compile(r"^[a-z0-9._-]{2,32}$")
ALLOWED_MIME = {
    "image/jpeg", "image/png", "image/webp", "image/gif", "image/heic",
    "application/pdf", "application/octet-stream",
}


class LoginLimiter:
    """At most 10 failed logins per address within 15 minutes."""

    def __init__(self, limit=10, window=900):
        self.limit = limit
        self.window = window
        self.failures = defaultdict(deque)
        self.lock = threading.Lock()

    def blocked(self, address):
        with self.lock:
            attempts = self.failures[address]
            while attempts and attempts[0] < time.time() - self.window:
                attempts.popleft()
            return len(attempts) >= self.limit

    def fail(self, address):
        with self.lock:
            self.failures[address].append(time.time())


def create_app(data_dir=None):
    app = Flask(__name__)
    app.config["MAX_CONTENT_LENGTH"] = MAX_UPLOAD + 1024 * 1024
    store = Store(data_dir or os.environ.get("LINOTES_DATA", "./data"))
    limiter = LoginLimiter()
    app.store = store

    def client_address():
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
        return {"id": row["id"], "username": row["username"], "name": row["display_name"]}

    @app.after_request
    def no_cache(response):
        response.headers.setdefault("Cache-Control", "no-store")
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response

    @app.errorhandler(401)
    def unauthorized(_error):
        return jsonify(error="unauthorized"), 401

    @app.errorhandler(403)
    def forbidden(_error):
        return jsonify(error="forbidden"), 403

    @app.errorhandler(404)
    def not_found(_error):
        return jsonify(error="not-found"), 404

    @app.errorhandler(413)
    def too_large(_error):
        return jsonify(error="too-large"), 413

    @app.get("/api/health")
    def health():
        return jsonify(ok=True, version=store.current_version(), app="LiNotes")

    # --- accounts -----------------------------------------------

    @app.post("/api/login")
    def login():
        address = client_address()
        if limiter.blocked(address):
            return jsonify(error="too-many-attempts"), 429
        body = request.get_json(silent=True) or {}
        user = store.user_by_name(str(body.get("username", "")))
        if user is None or not check_password(str(body.get("password", "")), user["password"]):
            limiter.fail(address)
            app.logger.warning("LiNotes login failed from %s", address)
            return jsonify(error="wrong-credentials"), 401
        token = store.create_session(user["id"], str(body.get("device", "")))
        return jsonify(token=token, user=public_user(user), users=store.users())

    @app.post("/api/register")
    def register():
        address = client_address()
        if limiter.blocked(address):
            return jsonify(error="too-many-attempts"), 429
        body = request.get_json(silent=True) or {}
        username = str(body.get("username", "")).strip().lower()
        password = str(body.get("password", ""))
        if not USERNAME.match(username):
            return jsonify(error="invalid-username"), 400
        if len(password) < 8:
            return jsonify(error="password-too-short"), 400
        if store.user_by_name(username) is not None:
            return jsonify(error="username-taken"), 409
        user_id = store.use_invite(
            str(body.get("invite", "")), username, str(body.get("name", "")), password,
        )
        if user_id is None:
            limiter.fail(address)
            return jsonify(error="invalid-invite"), 403
        user = store.user(user_id)
        token = store.create_session(user_id, str(body.get("device", "")))
        return jsonify(token=token, user=public_user(user), users=store.users())

    @app.post("/api/logout")
    def logout():
        current_user()
        store.delete_session(g.token)
        return jsonify(ok=True)

    @app.get("/api/me")
    def me():
        user = current_user()
        return jsonify(user=public_user(user), users=store.users())

    @app.post("/api/password")
    def change_password():
        user = current_user()
        body = request.get_json(silent=True) or {}
        if not check_password(str(body.get("old", "")), user["password"]):
            return jsonify(error="wrong-credentials"), 403
        new = str(body.get("new", ""))
        if len(new) < 8:
            return jsonify(error="password-too-short"), 400
        store.set_password(user["id"], new)
        token = store.create_session(user["id"], str(body.get("device", "")))
        return jsonify(token=token)

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
        # Everything up to this version is committed and will be seen below.
        known = store.current_version()
        objects = store.changes(user["id"], since)
        more = len(objects) >= 2000
        cursor = objects[-1]["version"] if more else max(since, known)
        return jsonify(objects=objects, cursor=cursor, more=more, users=store.users())

    @app.post("/api/sync")
    def push():
        user = current_user()
        body = request.get_json(silent=True) or {}
        changes = body.get("changes") or []
        if not isinstance(changes, list) or len(changes) > 500:
            return jsonify(error="invalid"), 400
        return jsonify(results=store.apply(user["id"], changes))

    # --- files --------------------------------------------------

    @app.post("/api/files")
    def upload():
        user = current_user()
        upload = request.files.get("file")
        if upload is None:
            return jsonify(error="invalid"), 400
        content = upload.read(MAX_UPLOAD + 1)
        if len(content) > MAX_UPLOAD:
            return jsonify(error="too-large"), 413
        mime = upload.mimetype or "application/octet-stream"
        if mime not in ALLOWED_MIME:
            mime = "application/octet-stream"
        space = request.form.get("space", "private")
        if space not in ("private", "shared"):
            space = "private"
        return jsonify(id=store.add_file(user["id"], space, mime, content))

    @app.get("/api/files/<file_id>")
    def download(file_id):
        user = current_user()
        if not re.fullmatch(r"[0-9a-f]{32}", file_id):
            abort(404)
        row, path = store.file(file_id, user["id"])
        if row is None or not path.exists():
            abort(404)
        response = send_file(path, mimetype=row["mime"], max_age=0)
        response.headers["Cache-Control"] = "private, max-age=31536000, immutable"
        return response

    return app
