"""Regression (29.09.–01.10.): ein gescheitertes "zuletzt gesehen"-UPDATE ließ
die Transaktion eines Threads offen, danach war die Datenbank für diesen
Thread dauerhaft gesperrt ("database is locked")."""

import os
import sys
import tempfile
import threading

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(HERE)), "linux"))

from test_api import register  # noqa: E402
from linotes_server.app import create_app  # noqa: E402


def in_thread(func):
    result = {}
    thread = threading.Thread(target=lambda: result.update(value=func()))
    thread.start()
    thread.join()
    return result.get("value")


def test_stale_transaction_is_released():
    app = create_app(tempfile.mkdtemp())
    client = app.test_client()
    _account, _identity, headers, _uid = register(client, app, "olaf", "Olaf")
    store = app.store
    token = headers["Authorization"][7:]
    store.connect().execute("UPDATE sessions SET seen = 0")
    store.connect().commit()

    # Dieser Thread hält einen alten Lese-Snapshot …
    db = store.connect()
    db.execute("BEGIN")
    db.execute("SELECT COUNT(*) FROM users").fetchone()
    # … während ein anderer Thread schreibt.
    in_thread(lambda: store.create_invite())

    # Früher: OperationalError und für immer offene Transaktion.
    assert store.session_user(token) is not None
    store.release()
    assert not db.in_transaction
    store.create_invite()

    # Über die App: nach jedem Request ist die Verbindung frei.
    assert client.get("/api/me", headers=headers).status_code == 200
    assert not store.connect().in_transaction
