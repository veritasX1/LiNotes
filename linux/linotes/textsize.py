"""Text size of notes, per device (like Apple's Notes: Settings → default text size, ⌘+/⌘−)."""

import json

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")

from gi.repository import Gdk, Gtk

from .sync import DATA_DIR

SIZES = [(0.85, "Klein"), (1.0, "Normal"), (1.15, "Groß"), (1.3, "Sehr groß"), (1.5, "Riesig")]
NORMAL = 1
BASE_PT = 11.25  # .note-editor in style.css
PREFS = DATA_DIR / "ui.json"

_provider = None


def load():
    try:
        level = int(json.loads(PREFS.read_text()).get("text_size", NORMAL))
    except (OSError, ValueError, AttributeError):
        level = NORMAL
    return max(0, min(len(SIZES) - 1, level))


def save(level):
    try:
        prefs = json.loads(PREFS.read_text())
    except (OSError, ValueError):
        prefs = {}
    prefs["text_size"] = level
    PREFS.parent.mkdir(parents=True, exist_ok=True)
    PREFS.write_text(json.dumps(prefs))


def apply(level):
    """Set the note text size in every window (main editor and note windows)."""
    global _provider
    display = Gdk.Display.get_default()
    if _provider is None:
        _provider = Gtk.CssProvider()
        Gtk.StyleContext.add_provider_for_display(display, _provider, Gtk.STYLE_PROVIDER_PRIORITY_USER)
    size = round(BASE_PT * SIZES[level][0], 2)
    _provider.load_from_string(f".note-editor, .note-editor text {{ font-size: {size}pt; }}")
