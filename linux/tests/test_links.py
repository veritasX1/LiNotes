"""Card 0cb30240 (Michelle 07.10.): besides web addresses, mailto:, tel: and the way back into LiMail/LiCal are links."""

import os
import sys
import tempfile
from pathlib import Path

os.environ["XDG_DATA_HOME"] = os.environ["XDG_CONFIG_HOME"] = tempfile.mkdtemp(prefix="linotes-links-")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import gi  # noqa: E402

gi.require_version("Gtk", "4.0")
from linotes.editor import LINK  # noqa: E402


def found(text):
    return [m.group(0) for m in LINK.finditer(text)]


def test_links():
    assert found("— E-Mail von Bernd: Grillfest\nlimail://message/f4f65c84%40testmail.limail.test") == \
        ["limail://message/f4f65c84%40testmail.limail.test"]
    assert found("Siehe https://lisoftware.de/limail/. Danke") == ["https://lisoftware.de/limail/"]
    assert found("www.beispiel.de, mailto:anna@limail.test und tel:+4930123") == ["www.beispiel.de", "mailto:anna@limail.test", "tel:+4930123"]
    assert found("Termin: lical://event/abc123") == ["lical://event/abc123"]
    assert found("kein link: limail ohne Doppelpunkt, foo://bar") == []


if __name__ == "__main__":
    test_links()
    print("1/1 Tests grün")
