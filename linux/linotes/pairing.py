"""Linking devices and verifying people with a 6-digit code (SPAKE2).

Both flows run over a short-lived relay channel on the server. The code is
never sent to the server; a wrong guess makes the attempt fail and the
channel is closed. See docs/SECURITY.md.

QR codes carry the same information as the typed code:
    LINOTES|link|<channel>|<code>
    LINOTES|verify|<channel>|<code>
"""

import hashlib
import hmac
import json
import time

from . import e2e
from .api import ApiError
from .i18n import _


LINK_A, LINK_B = b"linotes-new-device", b"linotes-account"
VERIFY_A, VERIFY_B = b"linotes-verify-a", b"linotes-verify-b"


class PairingError(Exception):
    pass


def qr_text(purpose, channel, code):
    return f"LINOTES|{purpose}|{channel}|{code}"


def parse_qr(text):
    parts = text.strip().split("|")
    if len(parts) != 4 or parts[0] != "LINOTES" or parts[1] not in ("link", "verify"):
        raise PairingError(_("Kein LiNotes-Code"))
    return parts[1], parts[2], parts[3]


def wait_message(api, channel, after, role, timeout, cancelled=lambda: False):
    """Wait for the next relay message from the other side."""
    deadline = time.time() + timeout
    while time.time() < deadline and not cancelled():
        try:
            messages = api.relay_get(channel, after, wait=min(20, max(1, int(deadline - time.time()))))
        except ApiError as error:
            if error.status == 404:
                raise PairingError(_("Der Vorgang wurde abgebrochen oder ist abgelaufen.")) from None
            raise
        for message in messages:
            if message["role"] == role:
                return message
            after = message["seq"]
    raise PairingError(_("Zeitüberschreitung"))


def payload_key(ke):
    return e2e.hkdf(ke, "linotes v2 pairing payload")


def mac(ke, label, value):
    return hmac.new(payload_key(ke), label + value.encode(), hashlib.sha256).hexdigest()


# ================================================================
# LINKING A NEW DEVICE
# ================================================================

class NewDeviceLink:
    """Runs on the device that wants to join (role A)."""

    def __init__(self, api, username, device):
        self.api = api
        self.channel = api.link_request(username, device)
        self.code = e2e.new_code()
        self.qr = qr_text("link", self.channel, self.code)
        self.spake = e2e.Spake2("A", e2e.spake_w(self.code, self.channel), LINK_A, LINK_B)
        self.api.relay_post(self.channel, "A", self.spake.message.hex())

    def wait(self, cancelled=lambda: False):
        """Returns the account secret once the other device has confirmed."""
        message = wait_message(self.api, self.channel, 1, "B", 9 * 60, cancelled)
        reply = json.loads(message["body"])
        ke, confirmation, expected = self.spake.finish(bytes.fromhex(reply["p"]))
        if not hmac.compare_digest(reply.get("c", ""), expected.hex()):
            self.close()
            raise PairingError(_("Der Code war falsch. Bitte neu versuchen."))
        content = e2e.open_sealed(payload_key(ke), reply["k"], "link")
        self.api.relay_post(self.channel, "A", json.dumps({"ok": True, "c": confirmation.hex()}))
        return e2e.unb64(content["secret"])

    def close(self):
        try:
            self.api.relay_close(self.channel)
        except ApiError:
            pass


def approve_link(api, channel, code, account):
    """Runs on an already signed-in device (role B): sends the account
    secret, encrypted with the key agreed from the code."""
    first = wait_message(api, channel, 0, "A", 30)
    spake = e2e.Spake2("B", e2e.spake_w(code.strip(), channel), LINK_A, LINK_B)
    ke, confirmation, expected = spake.finish(bytes.fromhex(first["body"]))
    sealed = e2e.seal(payload_key(ke), {"secret": e2e.b64(account.secret)}, "link")
    api.relay_post(channel, "B", json.dumps({"p": spake.message.hex(), "c": confirmation.hex(), "k": sealed}))
    # A wrong code makes the new device reject the answer; it can not read
    # the secret either, because it lacks the agreed key.
    try:
        done = wait_message(api, channel, first["seq"], "A", 40)
    except PairingError:
        raise PairingError(_("Das neue Gerät hat nicht bestätigt – war der Code richtig?"))
    result = json.loads(done["body"])
    if not hmac.compare_digest(result.get("c", ""), expected.hex()):
        raise PairingError(_("Der Code war falsch."))
    return True


# ================================================================
# VERIFYING ANOTHER PERSON
# ================================================================

def _peer_public(users, user_id):
    for user in users:
        if user["id"] == user_id:
            return user["identity"]
    raise PairingError(_("Unbekannter Account"))


class VerifyShow:
    """The person who shows the code (role A)."""

    def __init__(self, api, other_id):
        self.api = api
        self.other_id = other_id
        self.channel = api.verify_request(other_id)
        self.code = e2e.new_code()
        self.qr = qr_text("verify", self.channel, self.code)
        self.spake = e2e.Spake2("A", e2e.spake_w(self.code, self.channel), VERIFY_A, VERIFY_B)
        api.relay_post(self.channel, "A", self.spake.message.hex())

    def wait(self, my_public, users, cancelled=lambda: False):
        message = wait_message(self.api, self.channel, 1, "B", 9 * 60, cancelled)
        reply = json.loads(message["body"])
        ke, confirmation, expected = self.spake.finish(bytes.fromhex(reply["p"]))
        if not hmac.compare_digest(reply.get("c", ""), expected.hex()):
            raise PairingError(_("Der eingegebene Code war falsch."))
        peer = _peer_public(users, self.other_id)
        if not hmac.compare_digest(reply.get("m", ""), mac(ke, VERIFY_B, peer)):
            raise PairingError(_("Der Schlüssel des anderen Accounts stimmt nicht mit dem Server überein!"))
        self.api.relay_post(self.channel, "A", json.dumps({"c": confirmation.hex(), "m": mac(ke, VERIFY_A, my_public)}))
        return e2e.fingerprint(peer)


def verify_enter(api, channel, code, other_id, my_public, users):
    """The person who types the code (role B)."""
    first = wait_message(api, channel, 0, "A", 30)
    spake = e2e.Spake2("B", e2e.spake_w(code.strip(), channel), VERIFY_A, VERIFY_B)
    ke, confirmation, expected = spake.finish(bytes.fromhex(first["body"]))
    api.relay_post(channel, "B", json.dumps({"p": spake.message.hex(), "c": confirmation.hex(),
                                             "m": mac(ke, VERIFY_B, my_public)}))
    done = json.loads(wait_message(api, channel, first["seq"], "A", 60)["body"])
    if not hmac.compare_digest(done.get("c", ""), expected.hex()):
        raise PairingError(_("Der Code war falsch."))
    peer = _peer_public(users, other_id)
    if not hmac.compare_digest(done.get("m", ""), mac(ke, VERIFY_A, peer)):
        raise PairingError(_("Der Schlüssel des anderen Accounts stimmt nicht mit dem Server überein!"))
    return e2e.fingerprint(peer)
