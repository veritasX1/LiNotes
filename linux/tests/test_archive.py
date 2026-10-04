"""Archive: a mark on the object (for everyone it is shared with) – set and taken off again."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from linotes import model  # noqa: E402


class Sync:
    def __init__(self):
        self.objects = {"b1": {"id": "b1", "kind": "board", "share": "s1", "data": {"name": "Garten"}}}
        self.puts = []

    def get(self, object_id):
        return self.objects.get(object_id)

    def put(self, kind, data, share, object_id):
        self.puts.append((kind, share, object_id))
        self.objects[object_id] = {**self.objects[object_id], "data": data}


def main():
    sync = Sync()
    assert not model.archived(sync.get("b1")) and not model.archived(None)
    model.set_archived(sync, "b1", True)
    assert model.archived(sync.get("b1")) and sync.puts == [("board", "s1", "b1")]  # stays in its share
    assert sync.get("b1")["data"]["name"] == "Garten"
    model.set_archived(sync, "b1", False)
    assert not model.archived(sync.get("b1")) and "archived" not in sync.get("b1")["data"]
    model.set_archived(sync, "fehlt", True)  # unknown id: nothing happens
    print("ok – Archiv")


if __name__ == "__main__":
    main()
