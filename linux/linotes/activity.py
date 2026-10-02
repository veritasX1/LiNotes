"""Changes by others in shared notes (like Apple's highlights and activity): what I saw last
of each shared note is remembered on this device; newer changes by someone else are marked."""

import time

from . import model, uiprefs

KEY = "seen_notes"


def _seen():
    return uiprefs.get(KEY, {})


def since():
    """Notes I have never opened count as new only for changes after this feature arrived."""
    first = uiprefs.get("activity_since")
    if first is None:
        first = time.time()
        uiprefs.put("activity_since", first)
    return first


def remember(note, blocks):
    """I have seen this version (opened it, or saved it myself)."""
    if not note.get("share"):
        return
    seen = _seen()
    seen[note["id"]] = {"t": model.modified(note), "l": model.block_lines(blocks)}
    uiprefs.put(KEY, seen)


def changed_by_other(note, me):
    return bool(note.get("share")) and note.get("updated_by") not in (None, 0, me)


def unread(note, me):
    """A dot in the list: someone else changed it since I looked (Apple: the blue dot)."""
    if not changed_by_other(note, me) or note["data"].get("trashed"):
        return False
    snapshot = _seen().get(note["id"])
    return model.modified(note) > (snapshot["t"] if snapshot else since()) + 1


def changes(note, blocks, me):
    """Lines changed by someone else since my last view (None: nothing to show)."""
    snapshot = _seen().get(note["id"])
    if snapshot is None or not unread(note, me):
        return None
    lines = model.changed_lines(snapshot["l"], model.block_lines(blocks))
    return lines or None
