"""API tests for protocol version 2, using the real client crypto."""

import base64
import io
import json
import os
import sys
import tempfile
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(HERE)), "linux"))

from linotes import e2e
from linotes_server.app import create_app


def register(client, app, username, name):
    code = app.store.create_invite()
    account = e2e.Account.create()
    identity = e2e.Identity()
    response = client.post("/api/register", json={
        "invite": code, "username": username, "name": name, "auth": account.auth,
        "identity": identity.export_sealed(account), "device": "test",
    })
    assert response.status_code == 200, response.json
    return account, identity, {"Authorization": "Bearer " + response.json["token"]}, response.json["user"]["id"]


def test_all():
    app = create_app(tempfile.mkdtemp())
    client = app.test_client()
    olaf_account, olaf_id_key, olaf, olaf_id = register(client, app, "olaf", "Olaf")
    anna_account, anna_id_key, anna, anna_id = register(client, app, "anna", "Anna")

    # No registration without invite; invites are single use.
    bad = client.post("/api/register", json={"invite": "XXXX", "username": "evil", "auth": "a" * 44,
                                             "identity": {"pub": "x", "priv": {}}})
    assert bad.status_code == 403

    # Login with the derived auth value; a new device restores the identity.
    login = client.post("/api/login", json={"username": "olaf", "auth": olaf_account.auth, "device": "zweites Gerät"})
    assert login.status_code == 200
    restored = e2e.Identity.from_sealed(olaf_account, login.json["identity"])
    assert restored.public == olaf_id_key.public
    assert client.post("/api/login", json={"username": "olaf", "auth": anna_account.auth}).status_code == 401

    # Private objects are opaque to the server and invisible to others.
    box = e2e.seal(olaf_account.private_key, {"title": "Kontodaten"}, "n1|m")
    client.post("/api/sync", json={"changes": [{"id": "n1", "kind": "note", "data": {"v": 2, "m": box}}]}, headers=olaf)
    raw = app.store.connect().execute("SELECT data FROM objects WHERE id='n1'").fetchone()[0]
    assert "Kontodaten" not in raw
    assert [o["id"] for o in client.get("/api/sync?since=0", headers=anna).json["objects"]] == []
    assert client.get("/api/objects/n1", headers=anna).status_code == 404
    assert client.get("/api/objects/n1", headers=olaf).json["id"] == "n1"

    # A shared list: Olaf creates a share with Anna and a list in it.
    share_key = e2e.new_key()
    keys = {str(olaf_id): e2e.wrap_key(share_key, olaf_id_key.public, "s1"),
            str(anna_id): e2e.wrap_key(share_key, anna_id_key.public, "s1")}
    result = client.post("/api/sync", json={"changes": [
        {"id": "s1", "kind": "share", "members": [anna_id], "data": {"keys": keys}},
        {"id": "l1", "kind": "list", "share": "s1", "data": {"v": 2, "m": e2e.seal(share_key, {"name": "Einkauf"}, "l1|m")}},
    ]}, headers=olaf).json["results"]
    assert [r["status"] for r in result] == ["ok", "ok"]
    pulled = client.get("/api/sync?since=0", headers=anna).json
    assert {o["id"] for o in pulled["objects"]} == {"s1", "l1"} and pulled["shares"] == ["s1"]
    share = [o for o in pulled["objects"] if o["id"] == "s1"][0]
    anna_key = e2e.unwrap_key(anna_id_key, share["data"]["keys"][str(anna_id)], "s1")
    listing = [o for o in pulled["objects"] if o["id"] == "l1"][0]
    assert e2e.open_sealed(anna_key, listing["data"]["m"], "l1|m") == {"name": "Einkauf"}

    # Anna may add items but not change the members or steal the list.
    ok = client.post("/api/sync", json={"changes": [{"id": "i1", "kind": "item", "share": "s1", "data": {"v": 2}}]}, headers=anna).json
    assert ok["results"][0]["status"] == "ok"
    steal = client.post("/api/sync", json={"changes": [{"id": "l1", "kind": "list", "share": None, "data": {}}]}, headers=anna).json
    assert steal["results"][0]["status"] == "forbidden"
    members = client.post("/api/sync", json={"changes": [{"id": "s1", "kind": "share", "members": [], "data": {}}]}, headers=anna).json
    assert members["results"][0]["status"] == "forbidden"
    outsider = client.post("/api/sync", json={"changes": [{"id": "x1", "kind": "note", "share": "nope", "data": {}}]}, headers=anna).json
    assert outsider["results"][0]["status"] == "forbidden"

    # Removing Anna: she no longer receives the share.
    client.post("/api/sync", json={"changes": [{"id": "s1", "kind": "share", "members": [], "data": {"keys": {}}}]}, headers=olaf)
    after = client.get("/api/sync?since=0", headers=anna).json
    assert after["shares"] == [] and not [o for o in after["objects"] if o["id"] == "l1"]

    # Adding her again later: she gets the older objects too.
    cursor = client.get("/api/sync?since=0", headers=anna).json["cursor"]
    client.post("/api/sync", json={"changes": [{"id": "s1", "kind": "share", "members": [anna_id], "data": {"keys": keys}}]}, headers=olaf)
    again = client.get(f"/api/sync?since={cursor}", headers=anna).json
    assert {"l1", "i1"} <= {o["id"] for o in again["objects"]}

    # Conflicts on notes are reported, not merged by the server.
    client.post("/api/sync", json={"changes": [{"id": "n2", "kind": "note", "share": "s1", "data": {"v": 2}}]}, headers=olaf)
    version = client.get("/api/objects/n2", headers=anna).json["version"]
    client.post("/api/sync", json={"changes": [{"id": "n2", "kind": "note", "share": "s1", "data": {"a": 1}, "base": version}]}, headers=anna)
    clash = client.post("/api/sync", json={"changes": [{"id": "n2", "kind": "note", "share": "s1", "data": {"o": 1}, "base": version}]}, headers=olaf).json
    assert clash["results"][0]["status"] == "conflict"

    # Files follow the same rules.
    private = client.post("/api/files", data={"file": (io.BytesIO(b"blob"), "x")}, headers=olaf).json["id"]
    shared = client.post("/api/files", data={"file": (io.BytesIO(b"blob"), "x"), "share": "s1"}, headers=olaf).json["id"]
    assert client.get(f"/api/files/{private}", headers=anna).status_code == 404
    assert client.get(f"/api/files/{shared}", headers=anna).status_code == 200

    # Linking a new device with a 6-digit code over the relay (SPAKE2).
    channel = client.post("/api/link/request", json={"username": "olaf", "device": "Ubuntu"}).json["channel"]
    pending = client.get("/api/channels", headers=olaf).json["channels"]
    assert pending[0]["channel"] == channel and pending[0]["purpose"] == "link"
    code = e2e.new_code()
    new_device = e2e.Spake2("A", e2e.spake_w(code, channel))
    old_device = e2e.Spake2("B", e2e.spake_w(code, channel))
    post = lambda role, body: client.post(f"/api/relay/{channel}", json={"role": role, "body": body})
    post("A", new_device.message.hex())
    msg_a = client.get(f"/api/relay/{channel}?after=0").json["messages"][0]["body"]
    ke_b, conf_b, expect_a = old_device.finish(bytes.fromhex(msg_a))
    post("B", json.dumps({"p": old_device.message.hex(), "c": conf_b.hex(),
                          "k": e2e.seal(ke_b + ke_b, {"secret": base64.b64encode(olaf_account.secret).decode()}, "link")}))
    reply = json.loads(client.get(f"/api/relay/{channel}?after=1").json["messages"][0]["body"])
    ke_a, conf_a, expect_b = new_device.finish(bytes.fromhex(reply["p"]))
    assert reply["c"] == expect_b.hex()
    secret = base64.b64decode(e2e.open_sealed(ke_a + ke_a, reply["k"], "link")["secret"])
    assert e2e.Account(secret).auth == olaf_account.auth
    stored = " ".join(row[0] for row in app.store.connect().execute("SELECT body FROM relay"))
    assert base64.b64encode(olaf_account.secret).decode() not in stored and code not in stored

    # Link requests are rate limited per account.
    for _ in range(6):
        last = client.post("/api/link/request", json={"username": "olaf"})
    assert last.status_code == 429

    # Long poll wakes on a change.
    now = client.get("/api/sync?since=0", headers=anna).json["cursor"]
    got = {}
    def waiter():
        got["r"] = app.test_client().get(f"/api/sync?since={now}&wait=10", headers=anna).json
    thread = threading.Thread(target=waiter)
    thread.start()
    time.sleep(0.4)
    client.post("/api/sync", json={"changes": [{"id": "i9", "kind": "item", "share": "s1", "data": {"v": 2}}]}, headers=olaf)
    thread.join(15)
    assert [o["id"] for o in got["r"]["objects"]] == ["i9"]

    # Brute force protection.
    for _ in range(10):
        client.post("/api/login", json={"username": "olaf", "auth": "falsch"})
    assert client.post("/api/login", json={"username": "olaf", "auth": olaf_account.auth}).status_code == 429
    print("alle Server-Tests (v2) bestanden")


if __name__ == "__main__":
    test_all()
