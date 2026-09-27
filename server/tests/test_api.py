"""API tests: python -m pytest or run directly."""

import io
import os
import sys
import tempfile
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from linotes_server.app import create_app


def make():
    directory = tempfile.mkdtemp()
    app = create_app(directory)
    app.store.create_user("olaf", "Olaf", "geheim123")
    return app, app.test_client()


def login(client, username="olaf", password="geheim123"):
    response = client.post("/api/login", json={"username": username, "password": password, "device": "test"})
    assert response.status_code == 200, response.json
    return {"Authorization": "Bearer " + response.json["token"]}


def test_all():
    app, client = make()
    assert client.post("/api/login", json={"username": "olaf", "password": "falsch"}).status_code == 401
    olaf = login(client)
    assert client.get("/api/me").status_code == 401

    # Invite and register the second account.
    code = client.post("/api/invites", headers=olaf).json["code"]
    bad = client.post("/api/register", json={"invite": "XXXX", "username": "anna", "password": "12345678"})
    assert bad.status_code == 403
    short = client.post("/api/register", json={"invite": code, "username": "anna", "password": "123"})
    assert short.status_code == 400
    reg = client.post("/api/register", json={"invite": code, "username": "anna", "name": "Anna", "password": "annas-passwort"})
    assert reg.status_code == 200, reg.json
    anna = {"Authorization": "Bearer " + reg.json["token"]}
    again = client.post("/api/register", json={"invite": code, "username": "anna2", "password": "12345678"})
    assert again.status_code == 403, "invite must be single use"

    # Private vs shared visibility.
    changes = [
        {"id": "n1", "kind": "note", "space": "private", "data": {"title": "Olafs privat"}},
        {"id": "n2", "kind": "note", "space": "shared", "data": {"title": "Geteilt"}},
    ]
    results = client.post("/api/sync", json={"changes": changes}, headers=olaf).json["results"]
    assert [r["status"] for r in results] == ["ok", "ok"]
    seen_by_anna = {o["id"] for o in client.get("/api/sync?since=0", headers=anna).json["objects"]}
    assert seen_by_anna == {"n2"}, seen_by_anna
    seen_by_olaf = {o["id"] for o in client.get("/api/sync?since=0", headers=olaf).json["objects"]}
    assert seen_by_olaf == {"n1", "n2"}

    # Anna cannot overwrite or reveal Olaf's private note.
    hijack = client.post("/api/sync", json={"changes": [{"id": "n1", "kind": "note", "space": "shared", "data": {}}]}, headers=anna).json
    assert hijack["results"][0]["status"] == "forbidden"

    # Cursor: nothing new after the last pull.
    pull = client.get("/api/sync?since=0", headers=olaf).json
    cursor = pull["cursor"]
    assert client.get(f"/api/sync?since={cursor}", headers=olaf).json["objects"] == []

    # Concurrent edit of a shared note by the other person -> conflict copy.
    base = [o for o in pull["objects"] if o["id"] == "n2"][0]["version"]
    client.post("/api/sync", json={"changes": [{"id": "n2", "kind": "note", "space": "shared", "data": {"title": "Anna"}, "base": base}]}, headers=anna)
    clash = client.post("/api/sync", json={"changes": [{"id": "n2", "kind": "note", "space": "shared", "data": {"title": "Olaf"}, "base": base}]}, headers=olaf).json
    assert clash["results"][0]["status"] == "conflict"
    # Shopping list items are last writer wins.
    client.post("/api/sync", json={"changes": [{"id": "i1", "kind": "item", "space": "shared", "data": {"text": "Milch"}}]}, headers=olaf)
    lww = client.post("/api/sync", json={"changes": [{"id": "i1", "kind": "item", "space": "shared", "data": {"text": "Hafermilch"}, "base": 0}]}, headers=anna).json
    assert lww["results"][0]["status"] == "ok"

    # Deletion becomes a tombstone without data.
    client.post("/api/sync", json={"changes": [{"id": "i1", "kind": "item", "space": "shared", "deleted": True}]}, headers=anna)
    tomb = [o for o in client.get(f"/api/sync?since={cursor}", headers=olaf).json["objects"] if o["id"] == "i1"][-1]
    assert tomb["deleted"] and tomb["data"] == {}

    # Invalid input.
    assert client.post("/api/sync", json={"changes": [{"id": "x", "kind": "evil", "space": "shared"}]}, headers=olaf).json["results"][0]["status"] == "invalid"
    assert client.post("/api/sync", json={"changes": [{"id": "v", "kind": "vault", "space": "shared"}]}, headers=olaf).json["results"][0]["status"] == "invalid"

    # Long poll wakes up on a change from the other account.
    now = client.get("/api/sync?since=0", headers=anna).json["cursor"]
    got = {}

    def waiter():
        start = time.time()
        other = app.test_client()
        got["response"] = other.get(f"/api/sync?since={now}&wait=10", headers=anna).json
        got["seconds"] = time.time() - start

    thread = threading.Thread(target=waiter)
    thread.start()
    time.sleep(0.5)
    client.post("/api/sync", json={"changes": [{"id": "n9", "kind": "note", "space": "shared", "data": {"title": "live"}}]}, headers=olaf)
    thread.join(15)
    assert [o["id"] for o in got["response"]["objects"]] == ["n9"], got
    assert got["seconds"] < 6, got["seconds"]

    # Files: private files are not visible to the other account.
    private = client.post("/api/files", data={"file": (io.BytesIO(b"\x89PNGdata"), "a.png", "image/png"), "space": "private"}, headers=olaf).json["id"]
    shared = client.post("/api/files", data={"file": (io.BytesIO(b"\x89PNGdata"), "b.png", "image/png"), "space": "shared"}, headers=olaf).json["id"]
    assert client.get(f"/api/files/{private}", headers=olaf).status_code == 200
    assert client.get(f"/api/files/{private}", headers=anna).status_code == 404
    assert client.get(f"/api/files/{shared}", headers=anna).status_code == 200
    assert client.get("/api/files/../../etc/passwd", headers=olaf).status_code == 404

    # Password change logs out every device.
    changed = client.post("/api/password", json={"old": "annas-passwort", "new": "neues-passwort"}, headers=anna)
    assert changed.status_code == 200
    assert client.get("/api/me", headers=anna).status_code == 401
    assert client.get("/api/me", headers={"Authorization": "Bearer " + changed.json["token"]}).status_code == 200

    # Brute force protection.
    for _ in range(10):
        client.post("/api/login", json={"username": "olaf", "password": "x"})
    assert client.post("/api/login", json={"username": "olaf", "password": "geheim123"}).status_code == 429

    # Logout.
    client.post("/api/logout", headers=olaf)
    assert client.get("/api/me", headers=olaf).status_code == 401
    print("alle Server-Tests bestanden")


if __name__ == "__main__":
    test_all()
