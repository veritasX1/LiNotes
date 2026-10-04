"""Quick look at an attachment without leaving LiNotes (like Quick Look on the Mac, a small
Prevux): pictures, PDFs, text, audio and video are shown in a dialog; "Teilen" opens it in
another app, saves a copy or puts it on the clipboard."""

import mimetypes
import shutil
import subprocess
import threading
from pathlib import Path

import gi

gi.require_version("Adw", "1")
gi.require_version("Gdk", "4.0")
gi.require_version("Gtk", "4.0")
from gi.repository import Adw, Gdk, Gio, GLib, Gtk

from . import smoothscroll
from .icons import Icon

TEXT_TYPES = {"application/json", "application/xml", "application/x-yaml", "application/javascript",
              "application/x-sh", "application/sql", "application/csv"}
TEXT_LIMIT = 1024 * 1024
PDF_PAGE_LIMIT = 300
ZOOM_STEPS = (0.25, 0.5, 0.75, 1.0, 1.5, 2.0, 3.0, 4.0)


def size_text(size):
    for unit in ("Bytes", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            return f"{size:.0f} {unit}" if unit == "Bytes" else f"{size:.1f} {unit}".replace(".", ",")
        size /= 1024


def kind_of(path, mime):
    mime = mime or mimetypes.guess_type(path.name)[0] or ""
    if mime.startswith("image/"):
        return "image"
    if mime == "application/pdf" or path.suffix.lower() == ".pdf":
        return "pdf"
    if mime.startswith(("audio/", "video/")):
        return "media"
    if mime.startswith("text/") or mime in TEXT_TYPES:
        return "text"
    return "other"


class PagePicture(Gtk.Picture):
    """A PDF page as wide as the dialog, as high as its proportions ask (a plain Picture in a
    vertical box would shrink to a strip)."""

    def do_get_request_mode(self):
        return Gtk.SizeRequestMode.HEIGHT_FOR_WIDTH

    def do_measure(self, orientation, for_size):
        paintable = self.get_paintable()
        if paintable is None:
            return 0, 0, -1, -1
        width, height = paintable.get_intrinsic_width(), paintable.get_intrinsic_height()
        if orientation == Gtk.Orientation.HORIZONTAL:
            return 0, width, -1, -1
        if for_size < 0 or not width:
            return 0, height, -1, -1
        size = round(for_size * height / width)
        return size, size, -1, -1


class QuickLook(Adw.Dialog):

    def __init__(self, window, path, name=None, mime=None):
        path = Path(path)
        name = name or path.name
        super().__init__(title=name, content_width=780, content_height=860)
        self.window = window
        self.path = path
        self.name = name
        self.pages_dir = None
        self.closed = False

        header = Adw.HeaderBar()
        title = Adw.WindowTitle(title=name, subtitle=size_text(path.stat().st_size))
        header.set_title_widget(title)

        actions = Gio.SimpleActionGroup()
        for action_name, callback in (("open-with", self.open_with), ("save-as", self.save_as),
                                      ("copy", self.copy), ("show-in-files", self.show_in_files)):
            action = Gio.SimpleAction.new(action_name, None)
            action.connect("activate", lambda _a, _p, function=callback: function())
            actions.add_action(action)
        self.insert_action_group("look", actions)
        menu = Gio.Menu()
        menu.append("Mit anderer App öffnen …", "look.open-with")
        menu.append("Kopie speichern unter …", "look.save-as")
        menu.append("Kopieren", "look.copy")
        menu.append("Im Dateimanager zeigen", "look.show-in-files")
        share = Gtk.MenuButton(child=Icon("export", 16), menu_model=menu, tooltip_text="Teilen")
        header.pack_end(share)

        kind = kind_of(path, mime)
        if kind == "image":
            content = self.image_view(header)
        elif kind == "pdf" and shutil.which("pdftoppm"):
            content = self.pdf_view()
        elif kind == "media":
            content = Gtk.Video(file=Gio.File.new_for_path(str(path)), autoplay=False, vexpand=True)
        elif kind == "text":
            content = self.text_view()
        else:
            content = self.other_view(mime)

        toolbar = Adw.ToolbarView(content=content)
        toolbar.add_top_bar(header)
        self.set_child(toolbar)
        self.connect("closed", self.on_closed)

    # --- pictures ------------------------------------------------

    def image_view(self, header):
        """Fitted to the window; zoom with the buttons, Strg+Rad or two fingers."""
        texture = None
        try:
            texture = Gdk.Texture.new_from_filename(str(self.path))
        except GLib.Error:
            return self.other_view("image/*")
        self.texture = texture
        self.zoom = None  # None = fit
        self.picture = Gtk.Picture(paintable=texture, content_fit=Gtk.ContentFit.CONTAIN, can_shrink=True,
                                   hexpand=True, vexpand=True)
        self.scroller = Gtk.ScrolledWindow(child=self.picture, hexpand=True, vexpand=True)
        smoothscroll.enable(self.scroller)

        zoom_box = Gtk.Box(css_classes=["linked"])
        for icon, tooltip, step in (("zoom-out-symbolic", "Verkleinern", -1),
                                    ("zoom-fit-best-symbolic", "Einpassen", 0),
                                    ("zoom-in-symbolic", "Vergrößern", 1)):
            button = Gtk.Button(icon_name=icon, tooltip_text=tooltip)
            button.connect("clicked", lambda _b, s=step: self.step_zoom(s))
            zoom_box.append(button)
        header.pack_start(zoom_box)

        wheel = Gtk.EventControllerScroll(flags=Gtk.EventControllerScrollFlags.VERTICAL)
        wheel.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
        wheel.connect("scroll", self.on_wheel)
        self.scroller.add_controller(wheel)
        pinch = Gtk.GestureZoom()
        pinch.connect("begin", lambda _g, _s: setattr(self, "pinch_start", self.current_zoom()))
        pinch.connect("scale-changed", lambda _g, scale: self.set_zoom(self.pinch_start * scale))
        self.scroller.add_controller(pinch)
        return self.scroller

    def current_zoom(self):
        if self.zoom is not None:
            return self.zoom
        width, height = self.scroller.get_width(), self.scroller.get_height()
        if not width or not height:
            return 1.0
        return min(width / self.texture.get_width(), height / self.texture.get_height(), 1.0)

    def set_zoom(self, zoom):
        if zoom is None:
            self.zoom = None
            self.picture.set_can_shrink(True)
            self.picture.set_size_request(-1, -1)
            return
        self.zoom = max(0.05, min(zoom, 8.0))
        self.picture.set_can_shrink(False)
        self.picture.set_size_request(int(self.texture.get_width() * self.zoom),
                                      int(self.texture.get_height() * self.zoom))

    def step_zoom(self, direction):
        if direction == 0:
            self.set_zoom(None)
            return
        now = self.current_zoom()
        if direction > 0:
            self.set_zoom(next((z for z in ZOOM_STEPS if z > now + 0.01), ZOOM_STEPS[-1]))
        else:
            self.set_zoom(next((z for z in reversed(ZOOM_STEPS) if z < now - 0.01), ZOOM_STEPS[0]))

    def on_wheel(self, controller, _dx, dy):
        if not controller.get_current_event_state() & Gdk.ModifierType.CONTROL_MASK:
            return False
        self.step_zoom(-1 if dy > 0 else 1)
        return True

    # --- PDF -------------------------------------------------------

    def pdf_view(self):
        """Pages rendered one by one with poppler-utils (part of Ubuntu), the first shows at once."""
        self.pages = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12, margin_top=12, margin_bottom=12,
                             margin_start=12, margin_end=12)
        self.pdf_status = Gtk.Label(label="PDF wird geladen …", css_classes=["dim-label"], margin_top=24)
        self.pages.append(self.pdf_status)
        scroller = Gtk.ScrolledWindow(child=self.pages, hexpand=True, vexpand=True)
        scroller.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        smoothscroll.enable(scroller)
        self.pages_dir = Path(GLib.get_user_cache_dir()) / "linotes" / "look" / GLib.uuid_string_random()
        self.pages_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        threading.Thread(target=self.render_pdf, daemon=True).start()
        return scroller

    def page_count(self):
        try:
            info = subprocess.run(["pdfinfo", str(self.path)], capture_output=True, text=True, timeout=20).stdout
        except (OSError, subprocess.SubprocessError):
            return None
        for line in info.splitlines():
            if line.startswith("Pages:"):
                return int(line.split()[1])
        return None

    def render_pdf(self):
        count = self.page_count() or 1
        shown = 0
        for page in range(1, min(count, PDF_PAGE_LIMIT) + 1):
            if self.closed:
                return
            prefix = self.pages_dir / f"p{page}"
            try:
                subprocess.run(["pdftoppm", "-f", str(page), "-l", str(page), "-png", "-singlefile",
                                "-scale-to-x", "1400", "-scale-to-y", "-1", str(self.path), str(prefix)],
                               capture_output=True, timeout=60, check=True)
            except (OSError, subprocess.SubprocessError):
                break
            GLib.idle_add(self.add_page, prefix.with_suffix(".png"))
            shown += 1
        GLib.idle_add(self.pdf_done, shown, count)

    def add_page(self, png):
        if self.closed or not png.exists():
            return False
        if self.pdf_status.get_parent() is not None:
            self.pages.remove(self.pdf_status)
        picture = PagePicture(file=Gio.File.new_for_path(str(png)), content_fit=Gtk.ContentFit.CONTAIN,
                              can_shrink=True, css_classes=["look-page"])
        self.pages.append(picture)
        return False

    def pdf_done(self, shown, count):
        if self.closed:
            return False
        if shown == 0:
            self.pdf_status.set_label("Das PDF lässt sich hier nicht anzeigen – über „Teilen“ in einer anderen App öffnen.")
        elif shown < count:
            more = Gtk.Label(label=f"Die ersten {shown} von {count} Seiten – alle über „Teilen“ in einer anderen App.",
                             css_classes=["dim-label"], wrap=True)
            self.pages.append(more)
        return False

    # --- text and everything else ---------------------------------

    def text_view(self):
        data = self.path.read_bytes()[:TEXT_LIMIT]
        text = data.decode("utf-8", errors="replace")
        view = Gtk.TextView(editable=False, cursor_visible=False, monospace=True, wrap_mode=Gtk.WrapMode.WORD_CHAR,
                            top_margin=12, bottom_margin=12, left_margin=12, right_margin=12)
        view.get_buffer().set_text(text)
        scroller = Gtk.ScrolledWindow(child=view, hexpand=True, vexpand=True)
        smoothscroll.enable(scroller)
        return scroller

    def other_view(self, mime):
        content_type = Gio.content_type_from_mime_type(mime or "") or "application/octet-stream"
        page = Adw.StatusPage(title=self.name, description="Für diese Datei gibt es keine Vorschau.",
                              vexpand=True)
        page.set_paintable(None)
        page.set_icon_name(Gio.content_type_get_generic_icon_name(content_type) or "text-x-generic")
        button = Gtk.Button(label="Mit anderer App öffnen …", halign=Gtk.Align.CENTER, css_classes=["pill", "suggested-action"])
        button.connect("clicked", lambda _b: self.open_with())
        page.set_child(button)
        return page

    # --- sharing ---------------------------------------------------

    def open_with(self):
        launcher = Gtk.FileLauncher(file=Gio.File.new_for_path(str(self.path)))
        launcher.set_always_ask(True)
        launcher.launch(self.window, None, None)

    def show_in_files(self):
        Gtk.FileLauncher(file=Gio.File.new_for_path(str(self.path))).open_containing_folder(self.window, None, None)

    def save_as(self):
        dialog = Gtk.FileDialog(title="Kopie speichern", initial_name=self.name)

        def chosen(dialog, result):
            try:
                target = dialog.save_finish(result)
            except GLib.Error:
                return
            try:
                shutil.copyfile(self.path, target.get_path())
            except OSError as error:
                self.window.toast(f"Speichern nicht möglich: {error.strerror}")
                return
            self.window.toast("Kopie gespeichert")
        dialog.save(self.window, None, chosen)

    def copy(self):
        """As a file (paste into Files, mail, chat); pictures also as an image."""
        file = Gio.File.new_for_path(str(self.path))
        providers = [Gdk.ContentProvider.new_for_value(Gdk.FileList.new_from_list([file]))]
        texture = getattr(self, "texture", None)
        if texture is not None:
            providers.insert(0, Gdk.ContentProvider.new_for_value(texture))
        self.get_clipboard().set_content(Gdk.ContentProvider.new_union(providers))
        self.window.toast("Kopiert")

    def on_closed(self, _dialog):
        self.closed = True
        if self.pages_dir is not None:
            shutil.rmtree(self.pages_dir, ignore_errors=True)
