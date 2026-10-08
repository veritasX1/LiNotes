"""Text size of notes, per device (like Apple's Notes: Settings → default text size, ⌘+/⌘−)."""

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")

from gi.repository import Gdk, Gtk

from . import uiprefs
from .i18n import _

SIZES = [(0.85, _("Klein")), (1.0, _("Normal")), (1.15, _("Groß")), (1.3, _("Sehr groß")), (1.5, _("Riesig"))]
NORMAL = 1
BASE_PT = 11.25  # .note-editor in style.css
PREFS = uiprefs.PREFS

_provider = None


def load():
    try:
        level = int(uiprefs.get("text_size", NORMAL))
    except (TypeError, ValueError):
        level = NORMAL
    return max(0, min(len(SIZES) - 1, level))


def save(level):
    uiprefs.put("text_size", level)


def apply(level):
    """Set the note text size in every window (main editor and note windows)."""
    global _provider
    display = Gdk.Display.get_default()
    if _provider is None:
        _provider = Gtk.CssProvider()
        Gtk.StyleContext.add_provider_for_display(display, _provider, Gtk.STYLE_PROVIDER_PRIORITY_USER)
    size = round(BASE_PT * SIZES[level][0], 2)
    _provider.load_from_string(f".note-editor, .note-editor text {{ font-size: {size}pt; }}")


def load_justify():
    """Blocksatz in notes, per device (Android has the same switch in its settings)."""
    return bool(uiprefs.get("justify", False))


def save_justify(on):
    uiprefs.put("justify", bool(on))
