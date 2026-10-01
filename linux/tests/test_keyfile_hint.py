"""Karte a469da61: Die Schlüsseldatei wird nie beim ersten Start erzwungen, sondern
nach ein paar Tagen sanft empfohlen. Läuft ohne Server: python3 tests/test_keyfile_hint.py"""

import os
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
TMP = tempfile.mkdtemp()
os.environ["XDG_DATA_HOME"] = os.path.join(TMP, "data")
os.environ["XDG_CACHE_HOME"] = os.path.join(TMP, "cache")
sys.path.insert(0, os.path.dirname(HERE))

from linotes import sync  # noqa: E402

sync.store_credentials = lambda *args: None
sync.load_credentials = lambda *args: (None, None)


def main():
    e = sync.SyncEngine()
    e.start_local("Erna")
    assert not e.keyfile_hint_due(), "ohne Server gibt es keine Schlüsseldatei-Erinnerung"
    e.state["server"] = "https://example.invalid"  # behave like an account on a server
    assert not e.keyfile_hint_due(), "nie beim ersten Start"
    e.update_settings(since=time.time() - 4 * 86400)
    assert e.keyfile_hint_due(), "nach ein paar Tagen fällig"
    e.snooze_keyfile_hint()
    assert not e.keyfile_hint_due(), "nach „Später“ 30 Tage Ruhe"
    e.update_settings(keyfile_hint_until=0)
    e.mark_keyfile_saved()
    assert not e.keyfile_hint_due() and e.keyfile_saved(), "nach dem Sichern nie wieder"
    print("ok: Schlüsseldatei-Erinnerung – nicht beim Start, nach 3 Tagen, 30 Tage Ruhe, nach dem Sichern nie")


if __name__ == "__main__":
    main()
