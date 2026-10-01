"""Regression (01.10.2026): Der Titel gesperrter Notizen ging beim Abgleich
mit dem Server verloren, weil encrypt() ihn bei Notizen ohne "body" entfernte.
Gesperrte Notizen behalten den Titel (wie in Apples Notizen), die Vorschau nicht.
Läuft ohne Server: python3 tests/test_locked_title.py"""

import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
TMP = tempfile.mkdtemp()
os.environ["XDG_DATA_HOME"] = os.path.join(TMP, "data")
os.environ["XDG_CACHE_HOME"] = os.path.join(TMP, "cache")
sys.path.insert(0, os.path.dirname(HERE))

from linotes import model, sync, vault  # noqa: E402

sync.store_credentials = lambda *args: None
sync.load_credentials = lambda *args: (None, None)


def round_trip(engine, obj):
    remote = {k: obj[k] for k in ("id", "kind", "share", "owner", "deleted", "version", "updated", "updated_by")}
    remote["data"] = engine.encrypt(obj)
    return engine.decrypt(remote)


def main():
    engine = sync.SyncEngine()
    engine.start_local("Test")
    _vault, key = vault.create_vault("geheim")
    body = [{"t": "title", "x": "Bankdaten"}, {"t": "body", "x": "IBAN geheim"}]
    locked = engine.put("note", {"folder": "f", "enc": vault.seal(key, {"body": body}),
                                 "title": model.blocks_title(body), "created": 1, "modified": 1}, notify=False)
    back = round_trip(engine, locked)
    assert model.note_title(back) == "Bankdaten", back["data"]
    assert "preview" not in back["data"] and "body" not in back["data"], back["data"]
    plain = engine.put("note", {"folder": "f", "body": body, "created": 1, "modified": 1}, notify=False)
    assert model.note_title(round_trip(engine, plain)) == "Bankdaten"
    print("ok: Titel gesperrter Notizen übersteht den Server-Abgleich, Vorschau bleibt verborgen")


if __name__ == "__main__":
    main()
