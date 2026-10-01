"""Geteilte Ordner teilen alles mit (Karte 2b78279a): Verschieben in einen geteilten
Ordner übernimmt dessen Freigabe für Unterordner, Notizen, Listen (mit Einträgen) und
Boards (mit Spalten/Karten); heraus wird alles wieder privat – außer was einzeln
geteilt war. Läuft ohne Server: python3 tests/test_shared_folders.py"""

import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
TMP = tempfile.mkdtemp()
os.environ["XDG_DATA_HOME"] = os.path.join(TMP, "data")
os.environ["XDG_CACHE_HOME"] = os.path.join(TMP, "cache")
sys.path.insert(0, os.path.dirname(HERE))

from linotes import e2e, model, sync  # noqa: E402

sync.store_credentials = lambda *args: None
sync.load_credentials = lambda *args: (None, None)


def main():
    e = sync.SyncEngine()
    e.start_local("Test")
    # A share as if it had been set up with someone (the key is all encryption needs).
    e.share_keys["share-team"] = e2e.new_key()
    e.share_keys["share-solo"] = e2e.new_key()
    team = e.put("folder", {"name": "Team"}, "share-team", notify=False)
    project = e.put("folder", {"name": "Projekt"}, notify=False)
    sub = e.put("folder", {"name": "Unterordner", "parent": project["id"]}, notify=False)
    note = e.put("note", {"folder": sub["id"], "body": [{"t": "title", "x": "Plan"}]}, notify=False)
    shopping = e.put("list", {"name": "Einkauf", "folder": project["id"]}, notify=False)
    item = e.put("item", {"list": shopping["id"], "text": "Milch"}, notify=False)
    board = e.put("board", {"name": "Aufgaben", "folder": sub["id"]}, notify=False)
    column = e.put("column", {"board": board["id"], "name": "Offen"}, notify=False)
    card = e.put("card", {"board": board["id"], "column": column["id"], "title": "Los"}, notify=False)
    tree = [project, sub, note, shopping, item, board, column, card]

    members = {m["id"] for m in e.container_members(project)}
    assert members == {o["id"] for o in tree}, members

    e.move_to_folder(project["id"], team["id"])
    assert all(e.get(o["id"]).get("share") == "share-team" for o in tree), [e.get(o["id"]).get("share") for o in tree]
    assert e.get(project["id"])["data"]["parent"] == team["id"]

    e.move_to_folder(project["id"], None)
    assert all(e.get(o["id"]).get("share") is None for o in tree)

    solo = e.put("list", {"name": "Einzeln geteilt"}, "share-solo", notify=False)
    e.move_to_folder(solo["id"], project["id"])
    assert e.get(solo["id"]).get("share") == "share-solo" and e.get(solo["id"])["data"]["folder"] == project["id"]
    print("ok: Ordner samt Unterordnern, Notizen, Listen und Boards wandern in die Freigabe und wieder heraus; "
          "einzeln Geteiltes behält seine Freigabe")


if __name__ == "__main__":
    main()
