"""End-to-end encryption for locked ("secret") notes.

Same scheme on every platform:
    key  = PBKDF2-HMAC-SHA256(password, salt, iterations, 32 bytes)
    box  = AES-256-GCM(key, 12-byte random nonce), no associated data
    JSON = {"n": base64(nonce), "c": base64(ciphertext + tag)}
The server only ever sees salt, iteration count, hint and ciphertext.
"""

import base64
import json
import os

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC


ITERATIONS = 200_000
CHECK = "LiNotes"


def b64(data):
    return base64.b64encode(data).decode()


def unb64(text):
    return base64.b64decode(text)


def derive(password, salt, iterations=ITERATIONS):
    kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=iterations)
    return kdf.derive(password.encode())


def seal(key, value):
    nonce = os.urandom(12)
    plain = json.dumps(value, ensure_ascii=False).encode()
    return {"n": b64(nonce), "c": b64(AESGCM(key).encrypt(nonce, plain, None))}


def open_box(key, box):
    plain = AESGCM(key).decrypt(unb64(box["n"]), unb64(box["c"]), None)
    return json.loads(plain)


class WrongPassword(Exception):
    pass


def create_vault(password, hint=""):
    """Return (vault data for the server, key)."""
    salt = os.urandom(16)
    key = derive(password, salt)
    return {
        "salt": b64(salt),
        "iter": ITERATIONS,
        "hint": hint,
        "check": seal(key, CHECK),
    }, key


def unlock(vault, password):
    key = derive(password, unb64(vault["salt"]), int(vault.get("iter", ITERATIONS)))
    try:
        if open_box(key, vault["check"]) != CHECK:
            raise WrongPassword()
    except (InvalidTag, ValueError, KeyError):
        raise WrongPassword() from None
    return key
