"""Pairing and verification against a real (local) server."""

import os
import sys
import tempfile
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(HERE)), "server"))

from werkzeug.serving import make_server

from linotes import e2e, pairing
from linotes.api import Api
from linotes_server.app import create_app


def start_server():
    app = create_app(tempfile.mkdtemp())
    server = make_server("127.0.0.1", 0, app, threaded=True)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return app, f"http://127.0.0.1:{server.server_port}"


def register(app, url, username):
    account = e2e.Account.create()
    identity = e2e.Identity()
    response = Api(url).register(app.store.create_invite(), username, username.title(), account.auth,
                                 identity.export_sealed(account), "test")
    return account, identity, Api(url, response["token"]), response["user"]["id"]


def test_link_and_verify():
    app, url = start_server()
    olaf_account, olaf_identity, olaf, olaf_id = register(app, url, "olaf")
    anna_account, anna_identity, anna, anna_id = register(app, url, "anna")

    # --- link a new device with the right code ---
    new = pairing.NewDeviceLink(Api(url), "olaf", "Ubuntu-Test")
    result = {}
    thread = threading.Thread(target=lambda: result.update(secret=new.wait()))
    thread.start()
    channel = olaf.channels()[0]
    assert channel["purpose"] == "link"
    pairing.approve_link(olaf, channel["channel"], new.code, olaf_account)
    thread.join(10)
    assert result["secret"] == olaf_account.secret

    # --- a wrong code fails on both sides and reveals nothing ---
    new = pairing.NewDeviceLink(Api(url), "olaf", "Angreifer")
    outcome = {}
    def attempt():
        try:
            new.wait()
            outcome["new"] = "ok"
        except pairing.PairingError as error:
            outcome["new"] = str(error)
    thread = threading.Thread(target=attempt)
    thread.start()
    channel = [c for c in olaf.channels() if c["channel"] == new.channel][0]
    wrong = "000000" if new.code != "000000" else "111111"
    try:
        pairing.approve_link(olaf, channel["channel"], wrong, olaf_account)
        outcome["old"] = "ok"
    except pairing.PairingError as error:
        outcome["old"] = str(error)
    thread.join(10)
    assert outcome["new"] != "ok" and outcome["old"] != "ok", outcome

    # --- verify each other ---
    users = olaf.me()["users"]
    show = pairing.VerifyShow(olaf, anna_id)
    got = {}
    thread = threading.Thread(target=lambda: got.update(olaf=show.wait(olaf_identity.public, users)))
    thread.start()
    request = [c for c in anna.channels() if c["purpose"] == "verify"][0]
    assert request["from"] == olaf_id
    got["anna"] = pairing.verify_enter(anna, request["channel"], show.code, olaf_id, anna_identity.public, users)
    thread.join(10)
    assert got["olaf"] == e2e.fingerprint(anna_identity.public)
    assert got["anna"] == e2e.fingerprint(olaf_identity.public)

    # --- a server that swaps keys is detected ---
    fake = e2e.Identity()
    tampered = [dict(u, identity=fake.public) if u["id"] == anna_id else u for u in users]
    show = pairing.VerifyShow(olaf, anna_id)
    caught = {}
    def olaf_side():
        try:
            show.wait(olaf_identity.public, tampered)
            caught["olaf"] = "trusted"
        except pairing.PairingError as error:
            caught["olaf"] = str(error)
    thread = threading.Thread(target=olaf_side)
    thread.start()
    request = [c for c in anna.channels() if c["channel"] == show.channel][0]
    try:
        pairing.verify_enter(anna, request["channel"], show.code, olaf_id, anna_identity.public, users)
    except pairing.PairingError:
        pass
    thread.join(10)
    assert "stimmt nicht" in caught["olaf"], caught
    print("Koppeln und Verifizieren: alle Tests bestanden")


if __name__ == "__main__":
    test_link_and_verify()
