"""Audio in notes (like Apple's audio recordings, without transcription): record with the
microphone into Opus/Ogg, attach it encrypted like any file, play it back inside the note."""

import time
from datetime import datetime
from pathlib import Path

import gi

gi.require_version("Gst", "1.0")
gi.require_version("Adw", "1")
gi.require_version("Gtk", "4.0")
from gi.repository import Adw, GLib, Gst, Gtk

MIME = "audio/ogg"


def ensure_gst():
    if not Gst.is_initialized():
        Gst.init(None)


def duration_text(seconds):
    """0:07, 12:34, 1:02:03"""
    seconds = int(round(seconds or 0))
    hours, rest = divmod(seconds, 3600)
    minutes, seconds = divmod(rest, 60)
    return f"{hours}:{minutes:02d}:{seconds:02d}" if hours else f"{minutes}:{seconds:02d}"


def recording_name(moment=None):
    return (moment or datetime.now()).strftime("Aufnahme %Y-%m-%d %H-%M.ogg")


def is_audio(block):
    return (block.get("m") or "").startswith("audio/")


class Recorder:
    """Microphone → Opus/Ogg file. stop() finishes the file (EOS) and returns its length."""

    def __init__(self, path):
        ensure_gst()
        self.path = Path(path)
        self.pipeline = Gst.parse_launch(
            "autoaudiosrc ! audioconvert ! audioresample ! opusenc bitrate=32000 ! oggmux ! filesink name=sink")
        self.pipeline.get_by_name("sink").set_property("location", str(self.path))
        self.started = None
        self.error = None

    def start(self):
        if self.pipeline.set_state(Gst.State.PLAYING) == Gst.StateChangeReturn.FAILURE:
            raise RuntimeError("Das Mikrofon lässt sich nicht öffnen.")
        self.started = time.monotonic()

    def elapsed(self):
        return time.monotonic() - self.started if self.started else 0

    def stop(self, keep=True):
        length = self.elapsed()
        if keep:
            # End of stream lets oggmux write a complete file.
            self.pipeline.send_event(Gst.Event.new_eos())
            message = self.pipeline.get_bus().timed_pop_filtered(5 * Gst.SECOND, Gst.MessageType.EOS | Gst.MessageType.ERROR)
            if message is not None and message.type == Gst.MessageType.ERROR:
                self.error = message.parse_error()[0].message
        self.pipeline.set_state(Gst.State.NULL)
        return length


class RecordDialog(Adw.Dialog):
    """Red dot, running time, "Fertig" attaches, "Abbrechen" throws it away."""

    def __init__(self, path, done):
        super().__init__(title="Audioaufnahme", content_width=320)
        self.done = done
        self.recorder = Recorder(path)
        self.finished = False

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=18, margin_top=24, margin_bottom=24,
                      margin_start=24, margin_end=24)
        row = Gtk.Box(spacing=10, halign=Gtk.Align.CENTER)
        row.append(Gtk.Box(css_classes=["recording-dot"], valign=Gtk.Align.CENTER))
        self.time = Gtk.Label(label="0:00", css_classes=["title-1", "numeric"])
        row.append(self.time)
        box.append(row)
        box.append(Gtk.Label(label="Aufnahme läuft …", css_classes=["dim-label"]))
        buttons = Gtk.Box(spacing=12, halign=Gtk.Align.CENTER, homogeneous=True)
        cancel = Gtk.Button(label="Abbrechen", css_classes=["pill"])
        cancel.connect("clicked", lambda _button: self.finish(False))
        stop = Gtk.Button(label="Fertig", css_classes=["pill", "suggested-action"])
        stop.connect("clicked", lambda _button: self.finish(True))
        buttons.append(cancel)
        buttons.append(stop)
        box.append(buttons)
        toolbar = Adw.ToolbarView(content=box)
        toolbar.add_top_bar(Adw.HeaderBar(show_end_title_buttons=False))
        self.set_child(toolbar)
        self.set_default_widget(stop)
        self.connect("closed", lambda _dialog: self.finish(False))

        self.recorder.start()
        self.tick = GLib.timeout_add(250, self.update)

    def update(self):
        self.time.set_label(duration_text(self.recorder.elapsed()))
        return True

    def finish(self, keep):
        if self.finished:
            return
        self.finished = True
        GLib.source_remove(self.tick)
        length = self.recorder.stop(keep)
        self.close()
        if keep and self.recorder.error is None and self.recorder.path.exists() and length >= 0.5:
            self.done(self.recorder.path, length, None)
        elif keep:
            self.done(None, 0, self.recorder.error or "Die Aufnahme war zu kurz.")
        else:
            self.recorder.path.unlink(missing_ok=True)


class Player:
    """Plays one recording at a time inside a note."""

    def __init__(self):
        self.playbin = None
        self.on_state = None  # callback(playing: bool)

    def play(self, path, on_state):
        ensure_gst()
        self.stop()
        self.on_state = on_state
        self.playbin = Gst.ElementFactory.make("playbin", None)
        self.playbin.set_property("uri", Path(path).resolve().as_uri())
        bus = self.playbin.get_bus()
        bus.add_signal_watch()
        bus.connect("message::eos", lambda *_args: self.stop())
        bus.connect("message::error", lambda *_args: self.stop())
        self.playbin.set_state(Gst.State.PLAYING)
        on_state(True)

    def stop(self):
        if self.playbin is not None:
            self.playbin.get_bus().remove_signal_watch()
            self.playbin.set_state(Gst.State.NULL)
            self.playbin = None
        if self.on_state is not None:
            callback, self.on_state = self.on_state, None
            callback(False)
