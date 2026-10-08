"""Using LiNotes without a server, then moving everything into an account.

Needs a test server and the desktop keyring:
    LINOTES_TEST_SERVER=http://127.0.0.1:8499 LINOTES_TEST_INVITE=<code> \\
    XDG_DATA_HOME=$(mktemp -d) XDG_CACHE_HOME=$(mktemp -d) python3 tests/test_local.py
"""

import os
import shutil
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from linotes import model
from linotes import sync as S
from linotes.api import Api


def test_local_then_connect():
    server, invite = os.environ["LINOTES_TEST_SERVER"], os.environ["LINOTES_TEST_INVITE"]
    engine = S.SyncEngine()
    engine.start_local("Olaf")
    assert engine.is_local and engine.user_id == S.LOCAL_USER
    model.ensure_defaults(engine)
    picture = engine.upload_file(b"\x01\x02\x03", None)
    assert picture.startswith("local:")
    note = engine.put("note", {"folder": model.default_private_folder(engine.user_id),
                               "body": [{"t": "title", "x": "Offline"}, {"t": "image", "f": picture}],
                               "created": time.time(), "modified": time.time()})
    engine.put("item", {"list": model.default_list(engine.user_id), "text": "Milch", "by": engine.user_id})
    time.sleep(1)  # saved shortly after each change

    again = S.SyncEngine()
    assert again.restore() and again.is_local and again.get(note["id"])
    response = Api(server).register(invite, f"offline{int(time.time())}", "Offline", again.account.auth,
                                    again.identity.export_sealed(again.account), "test")
    again.connect_local(server, response, again.account)
    again.sync_now()
    uid = again.user_id
    moved = again.get(note["id"])
    assert moved["data"]["folder"] == f"notes-{uid}"
    reference = moved["data"]["body"][1]["f"]
    assert not reference.startswith("local:")
    shutil.rmtree(S.CACHE_DIR / "files", ignore_errors=True)
    assert again.fetch_file(reference).read_bytes() == b"\x01\x02\x03"
    item = again.objects("item")[0]
    assert item["data"]["list"] == f"list-{uid}" and item["data"]["by"] == uid
    ids = [o["id"] for o in again.api.pull(0)["objects"]]
    assert note["id"] in ids and not any(f"-{S.LOCAL_USER}" in i.replace(f"-{uid}", "") for i in ids)
    again.stop()
    S.clear_credentials(again.server, response["user"]["username"])
    print("ohne Server → Account: OK")


if __name__ == "__main__":
    test_local_then_connect()
