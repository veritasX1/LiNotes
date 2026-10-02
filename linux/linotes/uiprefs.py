"""Small per-device settings of the app (ui.json in the data folder): text size, seen mentions …"""

import json

from .sync import DATA_DIR

PREFS = DATA_DIR / "ui.json"


def get(key, default=None):
    try:
        return json.loads(PREFS.read_text()).get(key, default)
    except (OSError, ValueError, AttributeError):
        return default


def put(key, value):
    try:
        prefs = json.loads(PREFS.read_text())
    except (OSError, ValueError):
        prefs = {}
    prefs[key] = value
    PREFS.parent.mkdir(parents=True, exist_ok=True)
    PREFS.write_text(json.dumps(prefs))
