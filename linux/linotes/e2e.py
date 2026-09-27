"""End-to-end encryption for LiNotes (format version 2).

Everything the server stores is encrypted on the devices. See
docs/SECURITY.md for the design; the Android client implements the very
same functions in data/E2E.kt, with shared test vectors.

Building blocks (all standard, all available on Android without extra
libraries): P-256, ECDH, HKDF-SHA256, AES-256-GCM, HMAC-SHA256, PBKDF2 and
SPAKE2 (RFC 9382) for the 6-digit codes.
"""

import base64
import hashlib
import hmac
import json
import os
import struct

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC


class CryptoError(Exception):
    pass


def b64(data):
    return base64.b64encode(data).decode()


def unb64(text):
    return base64.b64decode(text)


def hkdf(secret, info, length=32, salt=None):
    return HKDF(algorithm=hashes.SHA256(), length=length, salt=salt, info=info.encode() if isinstance(info, str) else info).derive(secret)


# ================================================================
# SYMMETRIC ENCRYPTION
# ================================================================

def seal(key, value, aad=""):
    """Encrypt a JSON value. `aad` binds the ciphertext to its place
    (e.g. object id and field), so the server cannot swap blobs."""
    nonce = os.urandom(12)
    plain = json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode()
    return {"n": b64(nonce), "c": b64(AESGCM(key).encrypt(nonce, plain, aad.encode()))}


def open_sealed(key, box, aad=""):
    try:
        plain = AESGCM(key).decrypt(unb64(box["n"]), unb64(box["c"]), aad.encode())
    except (InvalidTag, KeyError, ValueError) as error:
        raise CryptoError("decryption failed") from error
    return json.loads(plain)


def seal_bytes(key, data, aad=""):
    nonce = os.urandom(12)
    return nonce + AESGCM(key).encrypt(nonce, data, aad.encode())


def open_bytes(key, blob, aad=""):
    try:
        return AESGCM(key).decrypt(blob[:12], blob[12:], aad.encode())
    except (InvalidTag, ValueError) as error:
        raise CryptoError("decryption failed") from error


def new_key():
    return os.urandom(32)


# ================================================================
# ACCOUNT KEYS
# ================================================================

class Account:
    """All keys of an account derive from one 32-byte secret R, which is
    what the QR code / 6-digit linking and the key file transfer."""

    def __init__(self, secret):
        self.secret = secret
        # Proves the account to the server (the server keeps only its hash).
        self.auth = b64(hkdf(secret, "linotes v2 auth"))
        # Encrypts everything private.
        self.private_key = hkdf(secret, "linotes v2 private data")
        # Encrypts the identity key pair stored on the server.
        self.identity_wrap_key = hkdf(secret, "linotes v2 identity")

    @staticmethod
    def create():
        return Account(os.urandom(32))


class Identity:
    """P-256 key pair: receives share keys from others (ECIES)."""

    def __init__(self, private=None):
        self.private = private or ec.generate_private_key(ec.SECP256R1())
        self.public_bytes = self.private.public_key().public_bytes(
            serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint,
        )

    @property
    def public(self):
        return b64(self.public_bytes)

    def export_sealed(self, account):
        raw = self.private.private_numbers().private_value.to_bytes(32, "big")
        return {"pub": self.public, "priv": seal(account.identity_wrap_key, b64(raw), "identity")}

    @staticmethod
    def from_sealed(account, data):
        raw = unb64(open_sealed(account.identity_wrap_key, data["priv"], "identity"))
        private = ec.derive_private_key(int.from_bytes(raw, "big"), ec.SECP256R1())
        identity = Identity(private)
        if identity.public != data["pub"]:
            raise CryptoError("identity mismatch")
        return identity


def wrap_key(key, recipient_public, aad):
    """ECIES: encrypt a 32-byte key for the holder of `recipient_public`."""
    recipient = ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), unb64(recipient_public))
    ephemeral = ec.generate_private_key(ec.SECP256R1())
    shared = ephemeral.exchange(ec.ECDH(), recipient)
    epub = ephemeral.public_key().public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)
    wrapping = hkdf(shared, b"linotes v2 wrap" + epub + unb64(recipient_public))
    nonce = os.urandom(12)
    return {"e": b64(epub), "n": b64(nonce), "c": b64(AESGCM(wrapping).encrypt(nonce, key, aad.encode()))}


def unwrap_key(identity, wrapped, aad):
    try:
        epub = unb64(wrapped["e"])
        ephemeral = ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), epub)
        shared = identity.private.exchange(ec.ECDH(), ephemeral)
        wrapping = hkdf(shared, b"linotes v2 wrap" + epub + identity.public_bytes)
        return AESGCM(wrapping).decrypt(unb64(wrapped["n"]), unb64(wrapped["c"]), aad.encode())
    except (InvalidTag, KeyError, ValueError) as error:
        raise CryptoError("unwrap failed") from error


def fingerprint(public):
    """Safety fingerprint of an identity key (shown in QR codes)."""
    return hashlib.sha256(b"linotes v2 fingerprint" + unb64(public)).hexdigest()


def safety_number(public_a, public_b):
    """The same 20 digits on both devices, for reading aloud if wanted."""
    first, second = sorted([unb64(public_a), unb64(public_b)])
    digest = hashlib.sha256(b"linotes v2 safety" + first + second).digest()
    number = int.from_bytes(digest[:12], "big") % 10**20
    text = f"{number:020d}"
    return " ".join(text[index:index + 5] for index in range(0, 20, 5))


# ================================================================
# KEY FILE (emergency backup, e.g. on a USB stick in a safe)
# ================================================================

KEYFILE_ITERATIONS = 600_000


def export_keyfile(server, username, account, passphrase):
    salt = os.urandom(16)
    key = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=KEYFILE_ITERATIONS).derive(passphrase.encode())
    content = {"server": server, "username": username, "secret": b64(account.secret)}
    return {
        "format": "linotes-key", "version": 1, "username": username,
        "kdf": "pbkdf2-sha256", "iterations": KEYFILE_ITERATIONS, "salt": b64(salt),
        "box": seal(key, content, "linotes-key"),
    }


def import_keyfile(data, passphrase):
    if data.get("format") != "linotes-key":
        raise CryptoError("not a LiNotes key file")
    key = PBKDF2HMAC(
        algorithm=hashes.SHA256(), length=32, salt=unb64(data["salt"]),
        iterations=int(data.get("iterations", KEYFILE_ITERATIONS)),
    ).derive(passphrase.encode())
    content = open_sealed(key, data["box"], "linotes-key")
    return content["server"], content["username"], Account(unb64(content["secret"]))


# ================================================================
# P-256 ARITHMETIC (for SPAKE2, which needs point addition)
# ================================================================

P = 0xFFFFFFFF00000001000000000000000000000000FFFFFFFFFFFFFFFFFFFFFFFF
A = P - 3
B = 0x5AC635D8AA3A93E7B3EBBD55769886BC651D06B0CC53B0F63BCE3C3E27D2604B
N = 0xFFFFFFFF00000000FFFFFFFFFFFFFFFFBCE6FAADA7179E84F3B9CAC2FC632551
G = (0x6B17D1F2E12C4247F8BCE6E563A440F277037D812DEB33A0F4A13945D898C296,
     0x4FE342E2FE1A7F9B8EE7EB4A7C0F9E162BCE33576B315ECECBB6406837BF51F5)


def point_add(p1, p2):
    if p1 is None:
        return p2
    if p2 is None:
        return p1
    x1, y1 = p1
    x2, y2 = p2
    if x1 == x2 and (y1 + y2) % P == 0:
        return None
    if p1 == p2:
        slope = (3 * x1 * x1 + A) * pow(2 * y1, -1, P) % P
    else:
        slope = (y2 - y1) * pow(x2 - x1, -1, P) % P
    x3 = (slope * slope - x1 - x2) % P
    return x3, (slope * (x1 - x3) - y1) % P


def point_neg(point):
    return None if point is None else (point[0], (-point[1]) % P)


def point_mul(scalar, point):
    result = None
    addend = point
    scalar %= N
    while scalar:
        if scalar & 1:
            result = point_add(result, addend)
        addend = point_add(addend, addend)
        scalar >>= 1
    return result


def encode_point(point):
    return b"\x04" + point[0].to_bytes(32, "big") + point[1].to_bytes(32, "big")


def decode_point(data):
    if len(data) == 65 and data[0] == 4:
        x = int.from_bytes(data[1:33], "big")
        y = int.from_bytes(data[33:], "big")
    elif len(data) == 33 and data[0] in (2, 3):
        x = int.from_bytes(data[1:], "big")
        y = pow((x * x * x + A * x + B) % P, (P + 1) // 4, P)
        if y % 2 != data[0] % 2:
            y = P - y
    else:
        raise CryptoError("bad point")
    if (y * y - (x * x * x + A * x + B)) % P != 0:
        raise CryptoError("point not on curve")
    return x, y


SPAKE_M = decode_point(bytes.fromhex("02886e2f97ace46e55ba9dd7242579f2993b64e16ef3dcab95afd497333d8fa12f"))
SPAKE_N = decode_point(bytes.fromhex("03d8bbd6c639c62937b04d997f38c3770719c629d7014d49a24b4f98baa1292b49"))


# ================================================================
# SPAKE2 (RFC 9382, P256-SHA256-HKDF-HMAC)
# ================================================================

def spake_w(code, context):
    """Derive the SPAKE2 scalar w from the short code and the session."""
    digest = hashlib.sha256(b"linotes v2 spake2 " + context.encode() + b"|" + code.encode()).digest()
    return int.from_bytes(digest, "big") % N


def _length_prefixed(*parts):
    return b"".join(struct.pack("<Q", len(part)) + part for part in parts)


class Spake2:
    """One side of SPAKE2. Role "A" sends first; both then confirm."""

    def __init__(self, role, w, identity_a=b"", identity_b=b"", scalar=None):
        self.role = role
        self.w = w
        self.identity_a = identity_a
        self.identity_b = identity_b
        self.scalar = scalar if scalar is not None else int.from_bytes(os.urandom(32), "big") % N
        blind = SPAKE_M if role == "A" else SPAKE_N
        self.message = encode_point(point_add(point_mul(self.scalar, G), point_mul(w, blind)))

    def finish(self, peer_message):
        """Returns (Ke, my_confirmation, expected_peer_confirmation)."""
        peer = decode_point(peer_message)
        unblind = SPAKE_N if self.role == "A" else SPAKE_M
        shared = point_mul(self.scalar, point_add(peer, point_neg(point_mul(self.w, unblind))))
        if shared is None:
            raise CryptoError("bad SPAKE2 message")
        if self.role == "A":
            p_a, p_b = self.message, peer_message
        else:
            p_a, p_b = peer_message, self.message
        transcript = _length_prefixed(
            self.identity_a, self.identity_b, p_a, p_b, encode_point(shared), self.w.to_bytes(32, "big"),
        )
        digest = hashlib.sha256(transcript).digest()
        ke, ka = digest[:16], digest[16:]
        confirmation = HKDF(algorithm=hashes.SHA256(), length=32, salt=None, info=b"ConfirmationKeys").derive(ka)
        kc_a, kc_b = confirmation[:16], confirmation[16:]
        c_a = hmac.new(kc_a, transcript, hashlib.sha256).digest()
        c_b = hmac.new(kc_b, transcript, hashlib.sha256).digest()
        self.transcript = transcript
        if self.role == "A":
            return ke, c_a, c_b
        return ke, c_b, c_a


def new_code():
    """A random 6-digit code for linking or verifying."""
    return f"{int.from_bytes(os.urandom(4), 'big') % 1_000_000:06d}"
