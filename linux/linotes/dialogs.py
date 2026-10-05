"""Sign-in page and small dialogs."""

import threading

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, GLib, GObject, Gtk

from .api import OfflineError
from .i18n import _


ERRORS = {
    "wrong-credentials": _("Anmeldung fehlgeschlagen – der Schlüssel passt nicht zu diesem Konto."),
    "too-many-attempts": _("Zu viele Versuche. Bitte warte ein paar Minuten."),
    "invalid-invite": _("Dieser Einladungscode ist ungültig oder wurde schon verwendet."),
    "invalid-username": _("Der Benutzername darf nur aus Kleinbuchstaben, Ziffern, Punkt, Minus und Unterstrich bestehen (2–32 Zeichen)."),
    "username-taken": _("Dieser Benutzername ist schon vergeben."),
    "offline": _("Der Server ist nicht erreichbar. Prüfe die Internetverbindung."),
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
            # Bind it now: Python deletes "error" when the except block ends (NameError later).
            GLib.idle_add(lambda failure=error: (done(None, failure), False)[1])
    threading.Thread(target=worker, daemon=True).start()


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
        hint_entry = Gtk.Entry(placeholder_text=_("Merkhilfe (empfohlen)"))
        box.append(hint_entry)
    elif hint:
        label = Gtk.Label(label=_("Merkhilfe: {hint}", hint=hint), xalign=0, wrap=True)
        label.add_css_class("dim-label")
        box.append(label)
    dialog.set_extra_child(box)
    dialog.add_response("cancel", _("Abbrechen"))
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
                toast_error(parent, _("Das Passwort muss mindestens 6 Zeichen haben."))
                return
            if password != second.get_text():
                toast_error(parent, _("Die Passwörter stimmen nicht überein."))
                return
        callback(password, hint_entry.get_text() if hint_entry else None)

    dialog.connect("response", on_response)
    dialog.present(parent)
    GLib.idle_add(lambda: (first.grab_focus(), False)[1])


def toast_error(parent, text):
    if hasattr(parent, "toast"):
        parent.toast(text)


def ask_text(parent, heading, callback, text="", placeholder="", action=_("Sichern"), body=None, choices=None):
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
    dialog.add_response("cancel", _("Abbrechen"))
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
    dialog.add_response("cancel", _("Abbrechen"))
    dialog.add_response("ok", action)
    dialog.set_response_appearance(
        "ok", Adw.ResponseAppearance.DESTRUCTIVE if destructive else Adw.ResponseAppearance.SUGGESTED,
    )
    dialog.set_close_response("cancel")
    dialog.connect("response", lambda _dialog, response: response == "ok" and callback())
    dialog.present(parent)
