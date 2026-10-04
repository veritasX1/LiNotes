"""Set-up, device linking, verification, key file, sharing and help (GTK)."""

import json
import threading
from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("Graphene", "1.0")

from gi.repository import Adw, Gio, GLib, GObject, Graphene, Gtk

from . import e2e, pairing
from . import smoothscroll
from .api import Api, ApiError, OfflineError
from .dialogs import error_text, run_async
from .qrcodegen import QrCode
from .sync import device_name


def contacts_id(sync):
    return f"contacts-{sync.user_id}"


def verified_state(sync, user):
    """"verified", "unverified" or "changed" (key differs from the verified one)."""
    contacts = sync.get(contacts_id(sync))
    stored = (contacts or {}).get("data", {}).get("verified", {}).get(str(user["id"]))
    if stored is None:
        return "unverified"
    return "verified" if stored == e2e.fingerprint(user["identity"]) else "changed"


def mark_verified(sync, user_id, fingerprint):
    contacts = sync.get(contacts_id(sync))
    data = dict(contacts["data"]) if contacts else {"verified": {}}
    verified = dict(data.get("verified", {}))
    verified[str(user_id)] = fingerprint
    data["verified"] = verified
    sync.put("contacts", data, None, contacts_id(sync))


def other_users(sync):
    return [user for user in sync.users() if user["id"] != sync.user_id]


# ================================================================
# QR CODE
# ================================================================

class QrView(Gtk.Widget):

    def __init__(self, text, size=220):
        super().__init__()
        self.qr = QrCode.encode_text(text, QrCode.Ecc.MEDIUM)
        self.size = size
        self.set_halign(Gtk.Align.CENTER)

    def do_measure(self, orientation, for_size):
        return self.size, self.size, -1, -1

    def do_snapshot(self, snapshot):
        size = self.size
        cr = snapshot.append_cairo(Graphene.Rect().init(0, 0, size, size))
        modules = self.qr.get_size() + 8
        scale = size / modules
        cr.set_source_rgb(1, 1, 1)
        cr.rectangle(0, 0, size, size)
        cr.fill()
        cr.set_source_rgb(0, 0, 0)
        for y in range(self.qr.get_size()):
            for x in range(self.qr.get_size()):
                if self.qr.get_module(x, y):
                    cr.rectangle((x + 4) * scale, (y + 4) * scale, scale + 0.3, scale + 0.3)
        cr.fill()


def code_label(code):
    label = Gtk.Label(label=f"{code[:3]} {code[3:]}")
    label.add_css_class("pairing-code")
    return label


def page(title, description=None):
    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
    box.set_margin_top(24)
    box.set_margin_bottom(24)
    box.set_margin_start(20)
    box.set_margin_end(20)
    heading = Gtk.Label(label=title, wrap=True, justify=Gtk.Justification.CENTER)
    heading.add_css_class("title-1")
    box.append(heading)
    if description:
        text = Gtk.Label(label=description, wrap=True, justify=Gtk.Justification.CENTER)
        text.add_css_class("dim-label")
        box.append(text)
    return box


def pill(label, suggested=True):
    button = Gtk.Button(label=label)
    button.add_css_class("pill")
    if suggested:
        button.add_css_class("suggested-action")
    return button


# ================================================================
# SET-UP (first start on this device)
# ================================================================

class Onboarding(Gtk.Box):
    """Server address, then: new account, link to an existing device, or
    restore from a key file."""

    __gsignals__ = {
        "signed-in": (GObject.SignalFlags.RUN_FIRST, None, (str, object, object)),
        "local": (GObject.SignalFlags.RUN_FIRST, None, (str,)),
        "cancelled": (GObject.SignalFlags.RUN_FIRST, None, ()),
    }

    def __init__(self, window):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self.window = window
        self.server = None
        self.cancelled = False
        # True when LiNotes was used without a server and now gets one.
        self.connecting = False

        view = Adw.ToolbarView()
        header = Adw.HeaderBar(show_title=False)
        header.set_decoration_layout("close,minimize,maximize:")
        self.back = Gtk.Button(icon_name="go-previous-symbolic", visible=False)
        self.back.connect("clicked", lambda _b: self.go_back())
        header.pack_start(self.back)
        help_button = Gtk.Button(icon_name="help-about-symbolic", tooltip_text="Hilfe")
        help_button.connect("clicked", lambda _b: show_help(self.window))
        header.pack_end(help_button)
        view.add_top_bar(header)

        self.stack = Gtk.Stack(transition_type=Gtk.StackTransitionType.SLIDE_LEFT_RIGHT, vexpand=True)
        view.set_content(self.stack)
        self.append(view)
        view.set_vexpand(True)

        self.build_server()
        self.build_choice()
        self.build_register()
        self.build_link()
        self.build_keyfile()
        self.build_local()
        self.show("server")

    def show(self, name):
        self.cancelled = True
        self.back.set_visible(name != "server" or self.connecting)
        self.stack.set_visible_child_name(name)

    def go_back(self):
        if self.stack.get_visible_child_name() == "server":
            self.emit("cancelled")
        else:
            self.show("server")

    def set_connecting(self, connecting):
        self.connecting = connecting
        self.local_button.set_visible(not connecting)
        self.server_title.set_label("Mit Server verbinden" if connecting else "LiNotes")
        self.show("server")

    def wrap(self, child, name):
        clamp = Adw.Clamp(maximum_size=420, child=child, valign=Gtk.Align.CENTER)
        scroller = Gtk.ScrolledWindow(child=clamp)
        smoothscroll.enable(scroller)
        scroller.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.stack.add_named(scroller, name)

    def error_label(self):
        label = Gtk.Label(wrap=True, justify=Gtk.Justification.CENTER, visible=False)
        label.add_css_class("error")
        return label

    def fail(self, label, text):
        label.set_label(text)
        label.set_visible(True)

    # --- server ------------------------------------------------

    def build_server(self):
        box = page("LiNotes", "Deine Notizen liegen auf deinem eigenen Server – Ende-zu-Ende verschlüsselt.")
        self.server_title = box.get_first_child()
        icon = Gtk.Image.new_from_icon_name("io.github.veritasx1.LiNotes")
        icon.set_pixel_size(96)
        box.prepend(icon)
        group = Adw.PreferencesGroup(description="Die Adresse bekommst du von der Person, die den Server betreibt.")
        self.server_row = Adw.EntryRow(title="Serveradresse, z. B. notizen.example.org")
        self.server_row.connect("entry-activated", lambda _r: self.check_server())
        group.add(self.server_row)
        box.append(group)
        self.server_error = self.error_label()
        box.append(self.server_error)
        button = pill("Weiter")
        button.connect("clicked", lambda _b: self.check_server())
        box.append(button)
        self.local_button = Gtk.Button(label="Ohne Server nutzen", halign=Gtk.Align.CENTER,
                                       tooltip_text="Einfach als Notizen-Programm auf diesem Computer. Einen Server kannst du später eintragen.")
        self.local_button.add_css_class("flat")
        self.local_button.connect("clicked", lambda _b: self.show("local"))
        box.append(self.local_button)
        self.wrap(box, "server")

    def build_local(self):
        box = page("Ohne Server", "Deine Notizen, Listen und Aufgaben liegen verschlüsselt nur auf diesem Computer. "
                   "Geht er verloren, sind sie weg – verbinde LiNotes später mit einem Server (Kontomenü), "
                   "um sie zu sichern und zu teilen.")
        group = Adw.PreferencesGroup()
        name_row = Adw.EntryRow(title="Dein Name (optional)")
        group.add(name_row)
        box.append(group)
        button = pill("Los geht’s")
        button.connect("clicked", lambda _b: self.emit("local", name_row.get_text().strip()))
        name_row.connect("entry-activated", lambda _r: self.emit("local", name_row.get_text().strip()))
        box.append(button)
        self.wrap(box, "local")

    def check_server(self):
        text = self.server_row.get_text().strip().rstrip("/")
        if not text:
            return
        if not text.startswith(("http://", "https://")):
            text = "https://" + text
        self.server_error.set_visible(False)

        def done(result, error):
            if error is not None or result.get("app") != "LiNotes":
                self.fail(self.server_error, "Unter dieser Adresse läuft kein LiNotes-Server." if error is None else error_text(error))
                return
            if result.get("protocol") != 2:
                self.fail(self.server_error, "Dieser Server ist zu alt für diese App.")
                return
            self.server = text
            self.show("choice")
        run_async(lambda: Api(text).health(), done)

    # --- choice ------------------------------------------------

    def build_choice(self):
        box = page("Wie möchtest du starten?")
        group = Adw.PreferencesGroup()
        for title, subtitle, target in (
            ("Neues Konto erstellen", "Du hast einen Einladungscode bekommen.", "register"),
            ("Mit anderem Gerät verbinden", "Dein Konto gibt es schon, z. B. auf dem Handy.", "link"),
            ("Mit Schlüsseldatei wiederherstellen", "Aus deiner Notfall-Sicherung.", "keyfile"),
        ):
            row = Adw.ActionRow(title=title, subtitle=subtitle, activatable=True)
            row.add_suffix(Gtk.Image.new_from_icon_name("go-next-symbolic"))
            row.connect("activated", lambda _row, t=target: self.show(t))
            group.add(row)
        box.append(group)
        self.wrap(box, "choice")

    # --- new account -------------------------------------------

    def build_register(self):
        box = page("Neues Konto", "Es gibt kein Passwort: Dein Konto ist durch einen Schlüssel geschützt, der nur auf deinen Geräten liegt.")
        group = Adw.PreferencesGroup()
        self.invite_row = Adw.EntryRow(title="Einladungscode")
        self.username_row = Adw.EntryRow(title="Benutzername (klein, ohne Leerzeichen)")
        self.name_row = Adw.EntryRow(title="Dein Name")
        for row in (self.invite_row, self.username_row, self.name_row):
            group.add(row)
        box.append(group)
        self.register_error = self.error_label()
        box.append(self.register_error)
        button = pill("Konto erstellen")
        button.connect("clicked", lambda _b: self.register())
        box.append(button)
        self.wrap(box, "register")

    def register(self):
        if self.connecting:
            # Register the keys this computer already uses.
            account, identity = self.window.sync.account, self.window.sync.identity
        else:
            account = e2e.Account.create()
            identity = e2e.Identity()
        username = self.username_row.get_text().strip().lower()
        server = self.server

        def call():
            return Api(server).register(self.invite_row.get_text().strip(), username, self.name_row.get_text().strip(),
                                        account.auth, identity.export_sealed(account), device_name())

        def done(response, error):
            if error is not None:
                self.fail(self.register_error, error_text(error))
                return
            # No key file dialog right away: it is recommended later, never forced at the first start.
            self.emit("signed-in", server, response, account)
        run_async(call, done)

    # --- link --------------------------------------------------

    def build_link(self):
        self.link_box = page("Mit anderem Gerät verbinden", "Gib deinen Benutzernamen ein. Danach bestätigst du auf dem anderen Gerät.")
        group = Adw.PreferencesGroup()
        self.link_user = Adw.EntryRow(title="Benutzername")
        self.link_user.connect("entry-activated", lambda _r: self.start_link())
        group.add(self.link_user)
        self.link_box.append(group)
        self.link_error = self.error_label()
        self.link_box.append(self.link_error)
        self.link_button = pill("Verbinden")
        self.link_button.connect("clicked", lambda _b: self.start_link())
        self.link_box.append(self.link_button)
        self.link_code_area = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        self.link_box.append(self.link_code_area)
        self.wrap(self.link_box, "link")

    def start_link(self):
        username = self.link_user.get_text().strip().lower()
        if not username:
            return
        server = self.server
        self.cancelled = False
        self.link_error.set_visible(False)
        child = self.link_code_area.get_first_child()
        while child:
            following = child.get_next_sibling()
            self.link_code_area.remove(child)
            child = following

        def created(link, error):
            if error is not None:
                message = "Diesen Benutzernamen gibt es auf dem Server nicht." if getattr(error, "status", 0) == 404 else error_text(error)
                self.fail(self.link_error, message)
                return
            info = Gtk.Label(wrap=True, justify=Gtk.Justification.CENTER,
                             label="Auf deinem anderen Gerät erscheint „Neues Gerät verbinden“. Gib dort diesen Code ein oder scanne den QR-Code:")
            self.link_code_area.append(info)
            self.link_code_area.append(code_label(link.code))
            self.link_code_area.append(QrView(link.qr))
            waiting = Gtk.Spinner(spinning=True)
            self.link_code_area.append(waiting)

            def finished(secret, failure):
                waiting.set_spinning(False)
                if failure is not None:
                    self.fail(self.link_error, str(failure) if isinstance(failure, pairing.PairingError) else error_text(failure))
                    return
                account = e2e.Account(secret)

                def signed(response, login_error):
                    if login_error is not None:
                        self.fail(self.link_error, error_text(login_error))
                        return
                    self.emit("signed-in", server, response, account)
                run_async(lambda: Api(server).login(username, account.auth, device_name()), signed)
            run_async(lambda: link.wait(lambda: self.cancelled), finished)

        run_async(lambda: pairing.NewDeviceLink(Api(server), username, device_name()), created)

    # --- key file ----------------------------------------------

    def build_keyfile(self):
        box = page("Wiederherstellen", "Wähle deine Schlüsseldatei und gib die Passphrase ein, mit der du sie geschützt hast.")
        self.keyfile_path = None
        choose = Gtk.Button(label="Schlüsseldatei auswählen …")
        choose.connect("clicked", lambda _b: self.choose_keyfile())
        box.append(choose)
        self.keyfile_label = Gtk.Label(wrap=True)
        self.keyfile_label.add_css_class("dim-label")
        box.append(self.keyfile_label)
        group = Adw.PreferencesGroup()
        self.passphrase_row = Adw.PasswordEntryRow(title="Passphrase")
        self.passphrase_row.connect("entry-activated", lambda _r: self.restore())
        group.add(self.passphrase_row)
        box.append(group)
        self.keyfile_error = self.error_label()
        box.append(self.keyfile_error)
        button = pill("Wiederherstellen")
        button.connect("clicked", lambda _b: self.restore())
        box.append(button)
        self.wrap(box, "keyfile")

    def choose_keyfile(self):
        dialog = Gtk.FileDialog(title="Schlüsseldatei")

        def chosen(dialog, result):
            try:
                self.keyfile_path = dialog.open_finish(result).get_path()
                self.keyfile_label.set_label(Path(self.keyfile_path).name)
            except GLib.Error:
                pass
        dialog.open(self.window, None, chosen)

    def restore(self):
        if not self.keyfile_path:
            self.fail(self.keyfile_error, "Bitte zuerst die Schlüsseldatei auswählen.")
            return
        passphrase = self.passphrase_row.get_text()

        def call():
            data = json.loads(Path(self.keyfile_path).read_text())
            server, username, account = e2e.import_keyfile(data, passphrase)
            return server, account, Api(server).login(username, account.auth, device_name())

        def done(result, error):
            if error is not None:
                message = "Falsche Passphrase oder keine gültige Schlüsseldatei." if isinstance(error, (e2e.CryptoError, ValueError, KeyError)) else error_text(error)
                self.fail(self.keyfile_error, message)
                return
            server, account, response = result
            self.emit("signed-in", server, response, account)
        run_async(call, done)


# ================================================================
# KEY FILE EXPORT
# ================================================================

class KeyfileDialog(Adw.Dialog):

    def __init__(self, window):
        super().__init__(title="Schlüsseldatei sichern")
        self.window = window
        self.sync = window.sync
        self.set_content_width(440)
        view = Adw.ToolbarView()
        view.add_top_bar(Adw.HeaderBar())
        box = page(
            "Notfall-Schlüssel",
            "Nur mit dieser Datei oder einem deiner Geräte kommst du an deine Notizen. "
            "Lege sie z. B. auf einen USB-Stick an einen sicheren Ort. Die Passphrase schützt die Datei, "
              "falls sie in falsche Hände gerät – merke sie dir gut.",
        )
        group = Adw.PreferencesGroup()
        self.first = Adw.PasswordEntryRow(title="Passphrase (mind. 10 Zeichen)")
        self.second = Adw.PasswordEntryRow(title="Passphrase wiederholen")
        group.add(self.first)
        group.add(self.second)
        box.append(group)
        self.error = Gtk.Label(wrap=True, visible=False)
        self.error.add_css_class("error")
        box.append(self.error)
        save = pill("Schlüsseldatei speichern …")
        save.connect("clicked", lambda _b: self.save())
        box.append(save)
        view.set_content(box)
        self.set_child(view)

    def save(self):
        passphrase = self.first.get_text()
        if len(passphrase) < 10:
            self.error.set_label("Die Passphrase muss mindestens 10 Zeichen haben.")
            self.error.set_visible(True)
            return
        if passphrase != self.second.get_text():
            self.error.set_label("Die Passphrasen stimmen nicht überein.")
            self.error.set_visible(True)
            return
        dialog = Gtk.FileDialog(title="Schlüsseldatei speichern")
        dialog.set_initial_name(f"LiNotes-{self.sync.user['username']}.linoteskey")

        def chosen(dialog, result):
            try:
                path = dialog.save_finish(result).get_path()
            except GLib.Error:
                return
            data = e2e.export_keyfile(self.sync.server, self.sync.user["username"], self.sync.account, passphrase)
            Path(path).write_text(json.dumps(data, indent=1))
            Path(path).chmod(0o600)
            self.sync.mark_keyfile_saved()
            self.window.toast("Schlüsseldatei gespeichert")
            self.close()
        dialog.save(self.window, None, chosen)


# ================================================================
# APPROVING A NEW DEVICE (incoming request)
# ================================================================

def approve_device(window, channel):
    sync = window.sync
    dialog = Adw.AlertDialog(
        heading="Neues Gerät verbinden?",
        body=f"„{channel.get('note') or 'Ein neues Gerät'}“ möchte sich mit deinem Konto verbinden. "
             "Gib den 6-stelligen Code ein, der dort angezeigt wird. Wenn du das nicht selbst warst, tippe auf „Ablehnen“.",
    )
    entry = Gtk.Entry(placeholder_text="123 456", max_length=7, input_purpose=Gtk.InputPurpose.DIGITS, activates_default=True)
    dialog.set_extra_child(entry)
    dialog.add_response("reject", "Ablehnen")
    dialog.add_response("ok", "Verbinden")
    dialog.set_response_appearance("ok", Adw.ResponseAppearance.SUGGESTED)
    dialog.set_default_response("ok")

    def on_response(_dialog, response):
        if response != "ok":
            run_async(lambda: sync.api.relay_close(channel["channel"]), lambda *_a: None)
            return
        code = entry.get_text().replace(" ", "")

        def done(_result, error):
            if error is not None:
                window.toast(str(error) if isinstance(error, pairing.PairingError) else error_text(error))
            else:
                window.toast("Neues Gerät verbunden")
        run_async(lambda: pairing.approve_link(sync.api, channel["channel"], code, sync.account), done)
    dialog.connect("response", on_response)
    dialog.present(window)


# ================================================================
# PEOPLE AND VERIFICATION
# ================================================================

class PeopleDialog(Adw.Dialog):

    def __init__(self, window):
        super().__init__(title="Personen")
        self.window = window
        self.sync = window.sync
        self.set_content_width(460)
        view = Adw.ToolbarView()
        view.add_top_bar(Adw.HeaderBar())
        self.page = Adw.PreferencesPage()
        view.set_content(self.page)
        self.set_child(view)
        self.fill()

    def fill(self):
        if hasattr(self, "group"):
            self.page.remove(self.group)
        self.group = Adw.PreferencesGroup(
            description="Bevor du etwas teilst, verifiziert ihr euch einmal gegenseitig – "
                        "so kann niemand, auch nicht der Server, einen falschen Schlüssel unterschieben.",
        )
        users = other_users(self.sync)
        if not users:
            self.group.add(Adw.ActionRow(title="Noch niemand", subtitle="Erzeuge einen Einladungscode im Kontomenü."))
        for user in users:
            state = verified_state(self.sync, user)
            subtitle = {"verified": "✓ verifiziert", "unverified": "noch nicht verifiziert",
                        "changed": "⚠ Schlüssel hat sich geändert – bitte neu verifizieren"}[state]
            row = Adw.ActionRow(title=user["name"], subtitle=f"@{user['username']} · {subtitle}")
            if state != "verified":
                button = Gtk.Button(label="Verifizieren", valign=Gtk.Align.CENTER)
                button.connect("clicked", lambda _b, u=user: VerifyDialog(self.window, u, on_done=self.fill).present(self.window))
                row.add_suffix(button)
            safety = e2e.safety_number(self.sync.identity.public, user["identity"])
            row.set_tooltip_text(f"Sicherheitsnummer: {safety}")
            self.group.add(row)
        self.page.add(self.group)


class VerifyDialog(Adw.Dialog):
    """Show a code (the other person types it or scans the QR code)."""

    def __init__(self, window, user, on_done=None):
        super().__init__(title=f"{user['name']} verifizieren")
        self.window = window
        self.sync = window.sync
        self.user = user
        self.on_done = on_done
        self.closed = False
        self.set_content_width(420)
        view = Adw.ToolbarView()
        view.add_top_bar(Adw.HeaderBar())
        self.box = page(f"{user['name']} verifizieren",
                        f"Auf dem Gerät von {user['name']} erscheint gleich eine Anfrage. "
                        "Dort diesen Code eintippen (oder vorlesen lassen) oder den QR-Code scannen.")
        self.spinner = Gtk.Spinner(spinning=True)
        self.box.append(self.spinner)
        safety = Gtk.Label(label="Sicherheitsnummer zum Vergleichen:\n" + e2e.safety_number(self.sync.identity.public, user["identity"]),
                           justify=Gtk.Justification.CENTER, selectable=True)
        safety.add_css_class("caption")
        safety.add_css_class("dim-label")
        self.safety = safety
        view.set_content(self.box)
        self.set_child(view)
        self.connect("closed", lambda _d: setattr(self, "closed", True))
        run_async(lambda: pairing.VerifyShow(self.sync.api, user["id"]), self.started)

    def started(self, show, error):
        if error is not None:
            self.window.toast(error_text(error))
            self.close()
            return
        self.box.insert_child_after(code_label(show.code), self.spinner)
        self.box.append(QrView(show.qr, 200))
        self.box.append(self.safety)

        def done(fingerprint, failure):
            if failure is not None:
                if not self.closed:
                    self.window.toast(str(failure) if isinstance(failure, pairing.PairingError) else error_text(failure))
                    self.close()
                return
            mark_verified(self.sync, self.user["id"], fingerprint)
            self.window.toast(f"{self.user['name']} ist jetzt verifiziert ✓")
            if self.on_done:
                self.on_done()
            self.close()
        run_async(lambda: show.wait(self.sync.identity.public, self.sync.users(), lambda: self.closed), done)


def answer_verification(window, channel):
    """Someone shows me a code: I type it in."""
    sync = window.sync
    other = sync.user_by_id(channel.get("from"))
    if other is None:
        return
    dialog = Adw.AlertDialog(
        heading=f"{other['name']} möchte euch verifizieren",
        body=f"Gib den Code ein, den {other['name']} dir zeigt oder vorliest.",
    )
    entry = Gtk.Entry(placeholder_text="123 456", max_length=7, input_purpose=Gtk.InputPurpose.DIGITS, activates_default=True)
    dialog.set_extra_child(entry)
    dialog.add_response("cancel", "Abbrechen")
    dialog.add_response("ok", "Bestätigen")
    dialog.set_response_appearance("ok", Adw.ResponseAppearance.SUGGESTED)
    dialog.set_default_response("ok")

    def on_response(_dialog, response):
        if response != "ok":
            return
        code = entry.get_text().replace(" ", "")

        def done(fingerprint, error):
            if error is not None:
                window.toast(str(error) if isinstance(error, pairing.PairingError) else error_text(error))
                return
            mark_verified(sync, other["id"], fingerprint)
            window.toast(f"{other['name']} ist jetzt verifiziert ✓")
        run_async(lambda: pairing.verify_enter(sync.api, channel["channel"], code, other["id"],
                                               sync.identity.public, sync.users()), done)
    dialog.connect("response", on_response)
    dialog.present(window)


# ================================================================
# SHARING
# ================================================================

class ShareDialog(Adw.Dialog):

    def __init__(self, window, obj):
        kinds = {"folder": "Ordner", "note": "Notiz", "list": "Liste", "board": "Board"}
        super().__init__(title=f"{kinds.get(obj['kind'], 'Objekt')} teilen")
        self.window = window
        self.sync = window.sync
        self.obj = obj
        self.set_content_width(440)
        view = Adw.ToolbarView()
        view.add_top_bar(Adw.HeaderBar())
        page_widget = Adw.PreferencesPage()
        description = "Wähle, wer mitlesen und mitbearbeiten darf."
        if obj["kind"] == "folder":
            description += " Alles in diesem Ordner wird mitgeteilt – Unterordner, Notizen, Listen und Boards."
        group = Adw.PreferencesGroup(title=obj["data"].get("name") or "", description=description)
        current = set(self.sync.share_members(obj.get("share"))) - {self.sync.user_id}
        self.checks = {}
        users = other_users(self.sync)
        if not users:
            group.add(Adw.ActionRow(title="Noch niemand zum Teilen da",
                                    subtitle="Erzeuge im Kontomenü einen Einladungscode."))
        for user in users:
            state = verified_state(self.sync, user)
            row = Adw.ActionRow(title=user["name"])
            if state == "verified":
                check = Gtk.CheckButton(active=user["id"] in current, valign=Gtk.Align.CENTER)
                row.add_prefix(check)
                row.set_activatable_widget(check)
                row.set_subtitle("✓ verifiziert")
                self.checks[user["id"]] = check
            else:
                row.set_subtitle("Erst verifizieren, dann teilen")
                button = Gtk.Button(label="Verifizieren", valign=Gtk.Align.CENTER)
                button.connect("clicked", lambda _b, u=user: (self.close(), VerifyDialog(window, u).present(window)))
                row.add_suffix(button)
            group.add(row)
        page_widget.add(group)
        if obj["owner"] != self.sync.user_id:
            group.set_description(f"Geteilt von {self.sync.user_name(obj['owner'])}. Nur wer es erstellt hat, kann die Freigabe ändern.")
            for check in self.checks.values():
                check.set_sensitive(False)
        actions = Adw.PreferencesGroup()
        save = pill("Übernehmen")
        save.set_sensitive(obj["owner"] == self.sync.user_id)
        save.connect("clicked", lambda _b: self.apply())
        actions.add(save)
        page_widget.add(actions)
        view.set_content(page_widget)
        self.set_child(view)

    def apply(self):
        members = [uid for uid, check in self.checks.items() if check.get_active()]
        if self.obj["kind"] == "note" and self.obj["data"].get("enc") and members:
            self.window.toast("Gesperrte Notizen können nicht geteilt werden.")
            return
        sync = self.sync

        def done(_result, error):
            if error is not None:
                self.window.toast(f"Teilen fehlgeschlagen: {error}")
            else:
                self.window.toast("Geteilt" if members else "Nicht mehr geteilt")
            self.window.refresh_all()
        # Re-encrypting (and re-uploading pictures) may take a moment.
        run_async(lambda: sync.set_sharing(self.obj["id"], members), done)
        self.close()


# ================================================================
# HELP
# ================================================================

HELP = [
    ("Erste Schritte", [
        ("Ohne Server", "Beim ersten Start „Ohne Server nutzen“ wählen: LiNotes ist dann einfach ein Notizen-Programm, alles liegt "
         "verschlüsselt nur auf diesem Computer. Später im Kontomenü „Mit Server verbinden …“ wählen – deine Notizen werden dann "
         "hochgeladen und lassen sich teilen und auf anderen Geräten nutzen."),
        ("Konto anlegen", "Beim ersten Start gibst du die Adresse deines LiNotes-Servers ein und wählst „Neues Konto erstellen“. "
         "Dafür brauchst du einen Einladungscode von der Person, die den Server betreibt. Ein Passwort gibt es nicht – "
         "dein Konto ist durch einen Schlüssel geschützt, der nur auf deinen Geräten liegt."),
        ("Schlüsseldatei sichern", "Speichere direkt danach die Schlüsseldatei (Kontomenü → „Schlüsseldatei sichern“) "
         "und lege sie z. B. auf einem USB-Stick an einen sicheren Ort. Ohne Gerät und ohne Schlüsseldatei kann niemand "
         "– auch nicht der Server-Betreiber – deine Notizen wiederherstellen."),
        ("Weiteres Gerät", "Auf dem neuen Gerät „Mit anderem Gerät verbinden“ wählen und deinen Benutzernamen eingeben. "
         "Auf einem Gerät, auf dem du schon angemeldet bist, erscheint dann eine Anfrage: dort den 6-stelligen Code "
         "eintippen oder mit dem Handy den QR-Code scannen."),
    ]),
    ("Notizen", [
        ("Formatieren", "Über „Aa“ wählst du Titel, Überschrift, Unterüberschrift, Text, Monospace, Listen oder Zitat. "
         "Tastenkürzel wie auf dem Mac: Strg+Umschalt+T (Titel), +H (Überschrift), +J (Unterüberschrift), +B (Text), "
         "+L (Checkliste), +7/8/9 (Listen); Strg+B/I/U für fett, kursiv, unterstrichen."),
        ("Checklisten", "Kreis anklicken, um einen Punkt abzuhaken. Tab rückt ein, Umschalt+Tab aus. Eine leere Zeile "
         "beendet die Liste. Im Format-Menü kannst du abgehakte Punkte automatisch nach unten sortieren lassen."),
        ("Tags", "Schreibe #Wort in eine Notiz – der Tag erscheint unten in der Seitenleiste zum Filtern."),
        ("Gesperrte Notizen", "Über das Schloss sperrst du eine Notiz mit deinem Notizen-Passwort. Sie wird zusätzlich "
         "verschlüsselt und sperrt sich nach 10 Minuten ohne Benutzung wieder. Geteilte Notizen können nicht gesperrt werden."),
        ("Gelöschte Notizen", "Gelöschte Notizen liegen 30 Tage in „Zuletzt gelöscht“ und lassen sich dort wiederherstellen."),
    ]),
    ("Teilen", [
        ("Personen verifizieren", "Bevor du etwas teilst, verifiziert ihr euch einmal: Kontomenü → „Personen“ → „Verifizieren“. "
         "Dein Gerät zeigt einen Code, die andere Person tippt ihn ein oder scannt den QR-Code. So kann niemand – auch "
         "nicht der Server – euch einen falschen Schlüssel unterschieben."),
        ("Etwas teilen", "Rechtsklick auf einen Ordner, eine Liste, ein Board oder eine Notiz → „Teilen …“ und die Personen "
         "auswählen. Wird ein Ordner geteilt, gilt das für alle Notizen darin. Entfernst du jemanden, wird neu verschlüsselt."),
    ]),
    ("Listen und Aufgaben", [
        ("Listen", "Einträge oben eintippen – sie landen automatisch in der passenden Warengruppe. Mehrere Zeilen "
         "einfügen legt mehrere Einträge an. Abgehakt wird mit dem Kreis."),
        ("Aufgaben-Board", "Karten per Ziehen zwischen Spalten verschieben. Ein Klick öffnet Fälligkeit, Zuständigkeit, "
         "Priorität, Farbe und Notizen."),
        ("Entwicklungsprojekt", "Rechtsklick auf ein Board → „Als Entwicklungsprojekt führen“. Dann zeigen die Karten "
         "ihre Kurz-ID (zum Zitieren in Commits und Berichten) und im Dialog den Verlauf: wer die Karte wann in welche "
         "Spalte geschoben hat. Unter „Verifikation“ hängst du Nachweise an – Prüfprotokolle, Screenshots, Messdaten. "
         "Sie liegen verschlüsselt an der Karte, mit Zeitpunkt, Person und Prüfsumme (SHA-256). "
         "Für einfache Boards bleibt alles wie gewohnt."),
        ("Bericht", "Export-Symbol (Kasten mit Pfeil) oben im Board oder Rechtsklick aufs Board → „Bericht exportieren“: der aktuelle Stand "
         "als PDF (z. B. als Nachweis für Kunden) oder als CSV für Excel. Bei Entwicklungsprojekten mit "
         "Traceability-Matrix (Karte ↔ Commits ↔ Verifikation ↔ Abnahme); Nachweise stehen mit Prüfsumme darin, Bilder eingebettet."),
    ]),
    ("Agiles Arbeiten", [
        ("Das agile Manifest", "Manifest für Agile Softwareentwicklung\n\nWir erschließen bessere Wege, Software zu entwickeln, indem wir es selbst tun und anderen dabei helfen. Durch diese Tätigkeit haben wir diese Werte zu schätzen gelernt:\n\nIndividuen und Interaktionen mehr als Prozesse und Werkzeuge\nFunktionierende Software mehr als umfassende Dokumentation\nZusammenarbeit mit dem Kunden mehr als Vertragsverhandlung\nReagieren auf Veränderung mehr als das Befolgen eines Plans\n\nDas heißt, obwohl wir die Werte auf der rechten Seite wichtig finden, schätzen wir die Werte auf der linken Seite höher ein.\n\nKent Beck, Mike Beedle, Arie van Bennekum, Alistair Cockburn, Ward Cunningham, Martin Fowler, James Grenning, Jim Highsmith, Andrew Hunt, Ron Jeffries, Jon Kern, Brian Marick, Robert C. Martin, Steve Mellor, Ken Schwaber, Jeff Sutherland, Dave Thomas\n\n© 2001, the above authors – this declaration may be freely copied in any form, but only in its entirety through this notice.\n\nWortlaut und deutsche Übersetzung: agilemanifesto.org/iso/de/manifesto.html"),
        ("Die zwölf Prinzipien – kurz gefasst", "1. Früh und regelmäßig etwas Nützliches liefern – das stellt Kunden am besten zufrieden.\n2. Geänderte Anforderungen sind willkommen, auch spät.\n3. In kurzen Abständen funktionierende Ergebnisse liefern, lieber Wochen als Monate.\n4. Fachleute und Entwickler arbeiten täglich zusammen.\n5. Projekte um motivierte Menschen bauen, ihnen Umfeld, Unterstützung und Vertrauen geben.\n6. Am besten informiert das direkte Gespräch.\n7. Fortschritt misst sich an dem, was funktioniert.\n8. Ein Tempo halten, das alle dauerhaft durchhalten können.\n9. Technische Qualität und gutes Design machen beweglich.\n10. Einfachheit: möglichst viel Arbeit gar nicht erst tun müssen.\n11. Gute Lösungen entstehen in Teams, die sich selbst organisieren.\n12. Regelmäßig innehalten, gemeinsam besser werden und das Vorgehen anpassen.\n\nIn eigenen Worten zusammengefasst; Wortlaut: agilemanifesto.org/iso/de/principles.html"),
        ("Agil arbeiten mit LiNotes", "Ein Board zeigt den Arbeitsfluss auf einen Blick: Spalten wie „Offen – In Arbeit – Erledigt“, jede Karte ein kleines, abgeschlossenes Stück Arbeit. So passen die vier Werte dazu:\n• Individuen und Interaktionen: Boards teilen, Karten zuweisen und mit @-Erwähnungen ins Gespräch holen – LiNotes unterstützt das Gespräch, ersetzt es aber nicht.\n• Funktionierende Software: Karten klein schneiden und erst nach „Erledigt“ schieben, wenn es wirklich funktioniert; bei Entwicklungsprojekten belegen Nachweise das.\n• Zusammenarbeit mit dem Kunden: Auftraggeber ins Board einladen: Sie schreiben Wünsche als Karten und nehmen selbst ab – z. B. so vereinbart, dass nur sie nach „Erledigt“ schieben.\n• Reagieren auf Veränderung: Prioritäten jederzeit ändern und Karten umsortieren; Pläne zeigen verschobene Meilensteine offen, statt sie zu verstecken.\n\nRegelmäßig reflektieren: den Bericht als PDF erzeugen und gemeinsam durchgehen – was lief gut, was ändern wir? Dokumentation nur so viel wie nötig: Auswirkungsanalyse, Verifikation und Nachweise sind für Projekte gedacht, die sie brauchen (z. B. nach ISO 26262 oder Automotive SPICE) – einfache Boards bleiben schlank."),
    ]),
    ("Datenschutz", [
        ("Was der Server weiß", "Alles – Notizen, Listen, Boards, Ordnernamen und Bilder – wird auf deinem Gerät verschlüsselt, "
         "bevor es den Server erreicht. Der Server sieht nur, dass es Einträge gibt, wie groß sie sind und wann sie "
         "geändert wurden – nicht, was darin steht."),
    ]),
]


def show_help(parent):
    dialog = Adw.Dialog(title="Hilfe")
    dialog.set_content_width(560)
    dialog.set_content_height(640)
    view = Adw.ToolbarView()
    view.add_top_bar(Adw.HeaderBar())
    page_widget = Adw.PreferencesPage()
    for section, entries in HELP:
        group = Adw.PreferencesGroup(title=section)
        for title, text in entries:
            row = Adw.ExpanderRow(title=title)
            label = Gtk.Label(label=text, wrap=True, xalign=0)
            label.set_margin_top(10)
            label.set_margin_bottom(10)
            label.set_margin_start(12)
            label.set_margin_end(12)
            row.add_row(Adw.PreferencesRow(child=label, activatable=False))
            group.add(row)
        page_widget.add(group)
    view.set_content(page_widget)
    dialog.set_child(view)
    dialog.present(parent)
