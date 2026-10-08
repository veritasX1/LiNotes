"""Board teilen verliert keine Karten anderer Personen (Karte fc38cfad, 08.10.2026: zweimal
Daten verloren). Personen hinzufügen behält die Freigabe und packt ihren Schlüssel nur für die
Neuen ein; Entfernen wechselt den Schlüssel nur, wenn alles im Board dem Teilenden gehört.
Läuft ohne Server: python3 tests/test_share_keeps_others.py"""

import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
TMP = tempfile.mkdtemp()
os.environ["XDG_DATA_HOME"] = os.path.join(TMP, "data")
os.environ["XDG_CACHE_HOME"] = os.path.join(TMP, "cache")
sys.path.insert(0, os.path.dirname(HERE))

from linotes import e2e, sync  # noqa: E402

sync.store_credentials = lambda *args: None
sync.load_credentials = lambda *args: (None, None)

BERND, CARLA = 2, 3


def readable(e, identity, uid, obj_id):
    """What the person [uid] would read of [obj_id]: unwrap their key from the share, open the server data."""
    obj = e.get(obj_id)
    share = e.get(obj["share"])
    wrapped = share["data"]["keys"].get(str(uid))
    if wrapped is None:
        return None
    key = e2e.unwrap_key(identity, wrapped, obj["share"])
    return e2e.open_sealed(key, e.encrypt(obj)["m"], f"{obj_id}|m")


def main():
    e = sync.SyncEngine()
    e.start_local("Olaf")
    people = {BERND: e2e.Identity(), CARLA: e2e.Identity()}
    for uid, identity in people.items():
        e.state["users"].append({"id": uid, "username": f"u{uid}", "name": f"P{uid}", "identity": identity.public})

    board = e.put("board", {"name": "Change Requests"}, notify=False)
    column = e.put("column", {"board": board["id"], "name": "CR"}, notify=False)
    mine = e.put("card", {"board": board["id"], "column": column["id"], "title": "Meine Karte"}, notify=False)
    first = e.set_sharing(board["id"], [BERND])
    # Bernd writes a card into the shared board – his, so only he could ever move it to another share.
    his = e.put("card", {"board": board["id"], "column": column["id"], "title": "Bernds Karte"}, first, notify=False)
    e.plain[his["id"]]["owner"] = BERND

    # Carla joins: same share, nothing moved, everyone (Carla too) reads every card.
    again = e.set_sharing(board["id"], [BERND, CARLA])
    assert again == first, (again, first)
    cards = [mine["id"], his["id"]]
    assert all(e.get(c)["share"] == first for c in cards), [e.get(c)["share"] for c in cards]
    for uid in (BERND, CARLA):
        assert [readable(e, people[uid], uid, c)["title"] for c in cards] == ["Meine Karte", "Bernds Karte"], uid
    assert sorted(e.get(first)["data"]["keys"]) == sorted([str(e.user_id), "2", "3"])

    # Carla leaves while Bernd's card is inside: no new key (it would strand his card), her key is gone.
    after = e.set_sharing(board["id"], [BERND])
    assert after == first and sorted(e.get(first)["data"]["keys"]) == sorted([str(e.user_id), "2"])
    assert readable(e, people[CARLA], CARLA, his["id"]) is None
    assert readable(e, people[BERND], BERND, his["id"])["title"] == "Bernds Karte"

    # A board that is all mine: removing someone still rotates the key, the old share is emptied (as before).
    solo = e.put("board", {"name": "Nur meins"}, notify=False)
    note = e.put("card", {"board": solo["id"], "title": "Allein"}, notify=False)
    s1 = e.set_sharing(solo["id"], [BERND, CARLA])
    s2 = e.set_sharing(solo["id"], [BERND])
    assert s2 != s1 and e.get(note["id"])["share"] == s2 and e.get(s1)["data"]["keys"] == {}
    assert readable(e, people[BERND], BERND, note["id"])["title"] == "Allein"
    print("ok: Hinzufügen behält die Freigabe (alle lesen alle Karten); Entfernen mit fremden Karten ohne "
          "Schlüsselwechsel; eigenes Board wechselt den Schlüssel wie bisher")


if __name__ == "__main__":
    main()
