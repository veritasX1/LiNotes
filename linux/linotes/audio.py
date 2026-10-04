"""Audio in notes (like Apple's audio recordings, without transcription): record with the
microphone into Opus/Ogg, attach it encrypted like any file, play it back inside the note."""

import re
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


BARS = 36          # bars of the waveform in the message bubble
WAVE_RATE = 4000   # samples per second read for the waveform


def peaks(samples, bars=BARS):
    """Loudness per bar of the waveform, 0.08…1 (square root, so quiet speech still shows), like the
    bars of a voice message in Apple's Messages. Same rules as AudioNotes.peaks on Android."""
    count = len(samples)
    if count == 0:
        return [0.08] * bars
    values = []
    for index in range(bars):
        start = index * count // bars
        end = max(start + 1, (index + 1) * count // bars)
        values.append(max(abs(sample) for sample in samples[start:end]))
    top = max(values) or 1
    return [round(max(0.08, (value / top) ** 0.5), 3) for value in values]


def waveform(path, bars=BARS):
    """Read a recording (any format GStreamer knows) and give its waveform – blocking, run it in a
    thread. Only loudness leaves this function, nothing is stored."""
    from array import array
    ensure_gst()
    pipeline = Gst.parse_launch("filesrc name=source ! decodebin ! audioconvert ! audioresample ! "
                                f"audio/x-raw,format=S16LE,channels=1,rate={WAVE_RATE} ! appsink name=sink sync=false")
    pipeline.get_by_name("source").set_property("location", str(path))
    sink = pipeline.get_by_name("sink")
    pipeline.set_state(Gst.State.PLAYING)
    data = bytearray()
    try:
        while True:
            sample = sink.emit("try-pull-sample", 5 * Gst.SECOND)
            if sample is None:
                break
            buffer = sample.get_buffer()
            ok, info = buffer.map(Gst.MapFlags.READ)
            if ok:
                data += info.data
                buffer.unmap(info)
    finally:
        pipeline.set_state(Gst.State.NULL)
    samples = array("h")
    samples.frombytes(bytes(data[:len(data) // 2 * 2]))
    return peaks(samples, bars)


MONTHS = ("Jan.", "Feb.", "März", "Apr.", "Mai", "Juni", "Juli", "Aug.", "Sept.", "Okt.", "Nov.", "Dez.")


def recording_label(block, today=None):
    """Title and line below it on the player card, like Apple's: ("Aufnahme", "4. Okt. 2026 · 0:07").
    Same rules as AudioNotes.label on Android (test_audio.py / AudioLabelTest)."""
    name = block.get("n") or ""
    match = re.match(r"^(.*?)\s*(\d{4})-(\d{2})-(\d{2})[ _](\d{2})-(\d{2})\.\w+$", name)
    duration = duration_text(block.get("d")) if block.get("d") else ""
    if match and 1 <= int(match.group(3)) <= 12:
        title = match.group(1).strip() or "Aufnahme"
        date = f"{int(match.group(4))}. {MONTHS[int(match.group(3)) - 1]} {match.group(2)}, {match.group(5)}:{match.group(6)}"
        return title, " · ".join(part for part in (date, duration) if part)
    title = name.rsplit(".", 1)[0] if "." in name else name
    return title or "Audioaufnahme", duration


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
    """Plays one recording at a time inside a note; pause and seek (the message bubble in the note)."""

    def __init__(self):
        self.playbin = None
        self.on_state = None  # callback(state: "playing" | "paused" | "stopped")
        self.paused = False

    def play(self, path, on_state):
        ensure_gst()
        self.stop()
        self.on_state = on_state
        self.paused = False
        self.playbin = Gst.ElementFactory.make("playbin", None)
        self.playbin.set_property("uri", Path(path).resolve().as_uri())
        bus = self.playbin.get_bus()
        bus.add_signal_watch()
        bus.connect("message::eos", lambda *_args: self.stop())
        bus.connect("message::error", lambda *_args: self.stop())
        self.playbin.set_state(Gst.State.PLAYING)
        on_state("playing")

    def toggle(self):
        """Pause or go on."""
        if self.playbin is None:
            return
        self.paused = not self.paused
        self.playbin.set_state(Gst.State.PAUSED if self.paused else Gst.State.PLAYING)
        if self.on_state is not None:
            self.on_state("paused" if self.paused else "playing")

    def position(self):
        if self.playbin is None:
            return 0.0
        ok, value = self.playbin.query_position(Gst.Format.TIME)
        return value / Gst.SECOND if ok else 0.0

    def duration(self):
        if self.playbin is None:
            return 0.0
        ok, value = self.playbin.query_duration(Gst.Format.TIME)
        return value / Gst.SECOND if ok and value > 0 else 0.0

    def seek(self, seconds):
        if self.playbin is None:
            return
        length = self.duration()
        seconds = max(0.0, min(seconds, length - 0.05) if length else seconds)
        self.playbin.seek_simple(Gst.Format.TIME, Gst.SeekFlags.FLUSH | Gst.SeekFlags.KEY_UNIT, int(seconds * Gst.SECOND))

    def stop(self):
        if self.playbin is not None:
            self.playbin.get_bus().remove_signal_watch()
            self.playbin.set_state(Gst.State.NULL)
            self.playbin = None
        self.paused = False
        if self.on_state is not None:
            callback, self.on_state = self.on_state, None
            callback("stopped")
