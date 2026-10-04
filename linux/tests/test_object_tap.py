"""Card 900036dc: a click on a picture opens it in the quick look, a click on a recording's card plays
or pauses it inside the note (Apple-style player: ±15 s, seek) – the cursor stays where it was."""

import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ["XDG_DATA_HOME"] = os.environ["XDG_CONFIG_HOME"] = os.environ["XDG_CACHE_HOME"] = tempfile.mkdtemp()
import gi  # noqa: E402

gi.require_version("Gtk", "4.0")
from gi.repository import GLib, Gtk  # noqa: E402

from linotes import audio  # noqa: E402
from linotes.editor import NoteEditor  # noqa: E402


def settle(seconds):
    context = GLib.MainContext.default()
    end = time.time() + seconds
    while time.time() < end:
        context.iteration(False)
        time.sleep(0.01)


def click(widget):
    for controller in widget.observe_controllers():
        if isinstance(controller, Gtk.GestureClick) and controller.get_button() in (0, 1):
            controller.emit("released", 1, 5.0, 5.0)
            return
    raise AssertionError("kein Klick")


def main():
    # Title and date line like Apple's (same rules as AudioNotes.label on Android).
    assert audio.recording_label({"n": "Aufnahme 2026-10-04 14-22.ogg", "d": 7.4}) == ("Aufnahme", "4. Okt. 2026, 14:22 · 0:07")
    assert audio.recording_label({"n": "Interview.m4a", "d": 65}) == ("Interview", "1:05")
    assert audio.recording_label({"n": "Aufnahme 2026-13-04 14-22.ogg"}) == ("Aufnahme 2026-13-04 14-22", "")
    assert audio.recording_label({}) == ("Audioaufnahme", "")

    folder = Path(tempfile.mkdtemp())
    sound = folder / "ton.ogg"
    subprocess.run(["gst-launch-1.0", "-q", "audiotestsrc", "num-buffers=1500", "!", "audioconvert", "!", "opusenc", "!", "oggmux",
                    "!", "filesink", f"location={sound}"], check=True)
    editor = NoteEditor()
    editor.image_loader = lambda file_id: sound
    blocks = [{"t": "title", "x": "Urlaub"}, {"t": "body", "x": "Text davor"}, {"t": "image", "f": "srv1:bild"},
              {"t": "file", "f": "srv1:ton", "n": "Aufnahme 2026-10-04 14-22.ogg", "m": "audio/ogg", "b": 1000, "d": 30.0},
              {"t": "body", "x": "Text danach"}]
    editor.load_blocks(blocks)
    window = Gtk.Window(child=editor)
    window.present()
    settle(0.3)
    buffer = editor.get_buffer()
    buffer.place_cursor(buffer.get_iter_at_offset(3))

    opened = []
    editor.connect("open-file", lambda _editor, block: opened.append(block))
    picture = next(entry["picture"] for entry in editor.anchors.values() if "file" in entry)
    click(picture)
    assert opened and opened[0]["f"] == "srv1:bild" and opened[0]["m"].startswith("image/"), opened

    entry = next(entry for entry in editor.anchors.values() if "player" in entry)
    _toggle, show = entry["player"]
    click(entry["picture"])
    settle(1.0)
    assert editor.player.on_state is show and not editor.player.paused, "spielt nicht"
    editor.player.jump(15)
    settle(0.4)
    assert editor.player.position() >= 14.5, editor.player.position()
    click(entry["picture"])  # the card again: pause
    assert editor.player.paused
    editor.player.seek(2.0)
    settle(0.3)
    assert 1.5 <= editor.player.position() <= 3.0, editor.player.position()
    assert buffer.get_iter_at_mark(buffer.get_insert()).get_offset() == 3, "Cursor ist gesprungen"
    editor.player.stop()
    assert editor.player.on_state is None
    assert [{k: v for k, v in b.items() if v is not None} for b in editor.to_blocks()] == blocks, editor.to_blocks()
    window.destroy()
    print("ok – Bilder und Aufnahmen antippen")


if __name__ == "__main__":
    main()
