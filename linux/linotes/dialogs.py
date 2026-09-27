"""Sign-in page and small dialogs."""

import threading

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, GLib, GObject, Gtk

from .api import Api, ApiError, OfflineError
from .sync import DEFAULT_SERVER, device_name


ERRORS = {
    "wrong-credentials": "Benutzername oder Passwort ist falsch.",
    "too-many-attempts": "Zu viele Versuche. Bitte warte ein paar Minuten.",
    "invalid-invite": "Dieser Einladungscode ist ungültig oder wurde schon verwendet.",
    "invalid-username": "Der Benutzername darf nur aus Kleinbuchstaben, Ziffern, Punkt, Minus und Unterstrich bestehen (2–32 Zeichen).",
    "password-too-short": "Das Passwort muss mindestens 8 Zeichen lang sein.",
    "username-taken": "Dieser Benutzername ist schon vergeben.",
    "offline": "Der Server ist nicht erreichbar. Prüfe die Internetverbindung.",
}


def error_text(error):
    if isinstance(error, OfflineError):
        return ERRORS["offline"]
    return ERRORS.get(getattr(error, "code", ""), f"Fehler: {error}")


def run_async(function, done):
    """Run a blocking call in a thread and hand the result to the main loop."""
    def worker():
        try:
            result = function()
            GLib.idle_add(lambda: (done(result, None), False)[1])
        except Exception as error:
            GLib.idle_add(lambda: (done(None, error), False)[1])
    threading.Thread(target=worker, daemon=True).start()


class LoginPage(Gtk.Box):

    __gsignals__ = {
        "signed-in": (GObject.SignalFlags.RUN_FIRST, None, (str, object)),
    }

    def __init__(self):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self.register_mode = False

        view = Adw.ToolbarView()
        header = Adw.HeaderBar()
        header.set_decoration_layout("close,minimize,maximize:")
        header.set_show_title(False)
        view.add_top_bar(header)

        clamp = Adw.Clamp(maximum_size=380, vexpand=True, valign=Gtk.Align.CENTER)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=18)
        box.set_margin_top(24)
        box.set_margin_bottom(24)
        box.set_margin_start(16)
        box.set_margin_end(16)

        icon = Gtk.Image.new_from_icon_name("io.github.veritasx1.LiNotes")
        icon.set_pixel_size(96)
        box.append(icon)
        title = Gtk.Label(label="LiNotes")
        title.add_css_class("large-title")
        box.append(title)
        self.subtitle = Gtk.Label(label="Melde dich mit deinem Konto an.", wrap=True, justify=Gtk.Justification.CENTER)
        self.subtitle.add_css_class("dim-label")
        box.append(self.subtitle)

        group = Adw.PreferencesGroup()
        self.invite = Adw.EntryRow(title="Einladungscode")
        self.invite.set_visible(False)
        group.add(self.invite)
        self.name = Adw.EntryRow(title="Dein Name (wie er angezeigt wird)")
        self.name.set_visible(False)
        group.add(self.name)
        self.username = Adw.EntryRow(title="Benutzername")
        group.add(self.username)
        self.password = Adw.PasswordEntryRow(title="Passwort")
        self.password.connect("entry-activated", lambda _row: self.submit())
        group.add(self.password)
        box.append(group)

        expander = Adw.PreferencesGroup()
        self.server = Adw.EntryRow(title="Server")
        self.server.set_text(DEFAULT_SERVER)
        advanced = Adw.ExpanderRow(title="Server", subtitle="linotes.goip.de")
        advanced.add_row(self.server)
        expander.add(advanced)
        box.append(expander)

        self.error = Gtk.Label(wrap=True, justify=Gtk.Justification.CENTER)
        self.error.add_css_class("error")
        self.error.set_visible(False)
        box.append(self.error)

        self.button = Gtk.Button(label="Anmelden")
        self.button.add_css_class("suggested-action")
        self.button.add_css_class("pill")
        self.button.connect("clicked", lambda _button: self.submit())
        box.append(self.button)

        self.switch = Gtk.Button(label="Neues Konto mit Einladungscode erstellen")
        self.switch.add_css_class("flat")
        self.switch.connect("clicked", lambda _button: self.toggle_mode())
        box.append(self.switch)

        clamp.set_child(box)
        view.set_content(clamp)
        view.set_vexpand(True)
        self.append(view)

    def toggle_mode(self):
        self.register_mode = not self.register_mode
        self.invite.set_visible(self.register_mode)
        self.name.set_visible(self.register_mode)
        self.button.set_label("Konto erstellen" if self.register_mode else "Anmelden")
        self.switch.set_label("Ich habe schon ein Konto" if self.register_mode else "Neues Konto mit Einladungscode erstellen")
        self.subtitle.set_label(
            "Gib den Einladungscode ein und wähle Benutzername und Passwort." if self.register_mode
            else "Melde dich mit deinem Konto an."
        )
        self.error.set_visible(False)

    def submit(self):
        server = self.server.get_text().strip() or DEFAULT_SERVER
        username = self.username.get_text().strip().lower()
        password = self.password.get_text()
        if not username or not password:
            self.show_error("Bitte Benutzername und Passwort eingeben.")
            return
        api = Api(server)
        self.button.set_sensitive(False)
        if self.register_mode:
            call = lambda: api.register(
                self.invite.get_text().strip(), username, self.name.get_text().strip(), password, device_name(),
            )
        else:
            call = lambda: api.login(username, password, device_name())
        run_async(call, lambda result, error: self.finished(server, result, error))

    def finished(self, server, result, error):
        self.button.set_sensitive(True)
        if error is not None:
            self.show_error(error_text(error))
            return
        self.password.set_text("")
        self.emit("signed-in", server, result)

    def show_error(self, text):
        self.error.set_label(text)
        self.error.set_visible(True)


def ask_password(parent, heading, body, callback, hint=None, confirm=False, action="OK"):
    """Ask for a password (optionally twice plus a hint). callback(password, hint)."""
    dialog = Adw.AlertDialog(heading=heading, body=body)
    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
    first = Gtk.PasswordEntry(show_peek_icon=True, activates_default=True)
    first.set_property("placeholder-text", "Passwort")
    box.append(first)
    second = hint_entry = None
    if confirm:
        second = Gtk.PasswordEntry(show_peek_icon=True, activates_default=True)
        second.set_property("placeholder-text", "Passwort bestätigen")
        box.append(second)
        hint_entry = Gtk.Entry(placeholder_text="Merkhilfe (empfohlen)")
        box.append(hint_entry)
    elif hint:
        label = Gtk.Label(label=f"Merkhilfe: {hint}", xalign=0, wrap=True)
        label.add_css_class("dim-label")
        box.append(label)
    dialog.set_extra_child(box)
    dialog.add_response("cancel", "Abbrechen")
    dialog.add_response("ok", action)
    dialog.set_response_appearance("ok", Adw.ResponseAppearance.SUGGESTED)
    dialog.set_default_response("ok")
    dialog.set_close_response("cancel")

    def on_response(dialog, response):
        if response != "ok":
            return
        password = first.get_text()
        if confirm:
            if len(password) < 6:
                toast_error(parent, "Das Passwort muss mindestens 6 Zeichen haben.")
                return
            if password != second.get_text():
                toast_error(parent, "Die Passwörter stimmen nicht überein.")
                return
        callback(password, hint_entry.get_text() if hint_entry else None)

    dialog.connect("response", on_response)
    dialog.present(parent)
    GLib.idle_add(lambda: (first.grab_focus(), False)[1])


def toast_error(parent, text):
    if hasattr(parent, "toast"):
        parent.toast(text)


def ask_text(parent, heading, callback, text="", placeholder="", action="Sichern", body=None, choices=None):
    """Ask for a name. With `choices`, also offer a dropdown; callback(text, choice)."""
    dialog = Adw.AlertDialog(heading=heading, body=body or "")
    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
    entry = Gtk.Entry(text=text, placeholder_text=placeholder, activates_default=True)
    box.append(entry)
    dropdown = None
    if choices:
        dropdown = Gtk.DropDown.new_from_strings([label for _key, label in choices])
        box.append(dropdown)
    dialog.set_extra_child(box)
    dialog.add_response("cancel", "Abbrechen")
    dialog.add_response("ok", action)
    dialog.set_response_appearance("ok", Adw.ResponseAppearance.SUGGESTED)
    dialog.set_default_response("ok")
    dialog.set_close_response("cancel")

    def on_response(dialog, response):
        value = entry.get_text().strip()
        if response == "ok" and value:
            choice = choices[dropdown.get_selected()][0] if choices else None
            callback(value, choice)

    dialog.connect("response", on_response)
    dialog.present(parent)
    GLib.idle_add(lambda: (entry.grab_focus(), False)[1])


def confirm(parent, heading, body, action, callback, destructive=True):
    dialog = Adw.AlertDialog(heading=heading, body=body)
    dialog.add_response("cancel", "Abbrechen")
    dialog.add_response("ok", action)
    dialog.set_response_appearance(
        "ok", Adw.ResponseAppearance.DESTRUCTIVE if destructive else Adw.ResponseAppearance.SUGGESTED,
    )
    dialog.set_close_response("cancel")
    dialog.connect("response", lambda _dialog, response: response == "ok" and callback())
    dialog.present(parent)
