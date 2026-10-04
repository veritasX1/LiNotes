"""Uploads with a progress bar: photos and files go to the server in a thread, the window stays
usable, and a bar with the name and percent shows that something is on its way (so nobody
attaches the same photo twice)."""

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import GLib, Gtk

from .dialogs import run_async


class Upload:

    def __init__(self, name):
        self.name = name
        self.fraction = 0.0
        self.listeners = []

    def set_fraction(self, fraction):
        self.fraction = fraction
        for listener in list(self.listeners):
            listener(fraction)


class UploadRow(Gtk.Box):
    """Name, percent and a bar; follows its upload until it is removed."""

    def __init__(self, upload, **properties):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=6, **properties)
        self.upload = upload
        line = Gtk.Box(spacing=8)
        line.append(Gtk.Label(label=f"„{upload.name}“ wird hochgeladen", xalign=0, hexpand=True, ellipsize=3))
        self.percent = Gtk.Label(label="0 %", css_classes=["dim-label", "numeric"])
        line.append(self.percent)
        self.append(line)
        self.bar = Gtk.ProgressBar()
        self.append(self.bar)
        self.update(upload.fraction)
        upload.listeners.append(self.update)

    def update(self, fraction):
        self.bar.set_fraction(fraction)
        self.percent.set_label(f"{int(fraction * 100)} %")

    def detach(self):
        if self.update in self.upload.listeners:
            self.upload.listeners.remove(self.update)


def start(window, name, content, share, done):
    """Upload `content` in a thread; done(reference, error) runs on the main loop. Returns the
    Upload, so a dialog can show its own row for it."""
    upload = Upload(name)
    window.add_upload(upload)
    shown = [0.0]

    def progress(sent, total):
        # 100 % only once the server has it (it still stores the file after the last byte).
        fraction = min(sent / total if total else 1.0, 0.99)
        # At most every percent – the main loop is not flooded.
        if fraction - shown[0] >= 0.01 or fraction >= 0.99:
            shown[0] = fraction
            GLib.idle_add(lambda: (upload.set_fraction(fraction), False)[1])

    def finished(result, error):
        window.remove_upload(upload)
        done(result, error)

    run_async(lambda: window.sync.upload_file(content, share, progress), finished)
    return upload
