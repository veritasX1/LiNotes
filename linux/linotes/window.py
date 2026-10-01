"""The LiNotes main window."""

import mimetypes
import time
from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gdk, Gio, GLib, GObject, Gtk

from . import model, vault
from .dialogs import ask_password, ask_text, confirm, error_text, run_async
from . import security_ui
from .icons import Icon, icon_button, icon_menu_button
from .kanban import BoardView
from .lists import ShoppingListView
from .notes import NoteList, NotePane
from .sidebar import Sidebar
from . import sync as sync_module
from .sync import device_name


DECORATION_LAYOUT = "close,minimize,maximize:"
# Like Apple: an unlocked note stays open for a few minutes of inactivity.
AUTO_LOCK_SECONDS = 5 * 60
TRASH_DAYS = 30

PARAGRAPH_MENU = [
    ("title", "Titel", "<Control><Shift>t"),
    ("heading", "Überschrift", "<Control><Shift>h"),
    ("subheading", "Unterüberschrift", "<Control><Shift>j"),
    ("body", "Text", "<Control><Shift>b"),
    ("mono", "Monospace", "<Control><Shift>m"),
    ("bullet", "• Aufzählung", "<Control><Shift>7"),
    ("dash", "– Liste mit Strichen", "<Control><Shift>8"),
    ("number", "1. Nummerierte Liste", "<Control><Shift>9"),
    ("check", "Checkliste", "<Control><Shift>l"),
    ("quote", "Zitat", "<Control>apostrophe"),
]


class LiNotesWindow(Adw.ApplicationWindow):

    def __init__(self, app, sync):
        super().__init__(application=app)
        self.sync = sync
        self.set_default_size(1180, 760)
        self.set_title("LiNotes")
        self.vault_key = None
        self.vault_used = 0
        self.current_key = "all"
        self.current_note = None
        self.editing_blocks = None

        self.toasts = Adw.ToastOverlay()
        self.set_content(self.toasts)
        self.pages = Gtk.Stack(transition_type=Gtk.StackTransitionType.CROSSFADE)
        self.toasts.set_child(self.pages)

        self.login = security_ui.Onboarding(self)
        self.login.connect("signed-in", self.on_signed_in)
        self.login.connect("local", self.on_local)
        self.login.connect("cancelled", lambda _l: self.pages.set_visible_child_name("main"))
        self.pages.add_named(self.login, "login")

        self.build_main()
        self.install_actions()

        sync.connect(self.on_sync_changed)
        sync.connect_status(self.on_status)
        sync.connect_channels(self.on_channel)
        GLib.timeout_add_seconds(30, self.check_auto_lock)
        self.watch_screen_lock()

        if sync.restore():
            self.enter_main()
        else:
            self.pages.set_visible_child_name("login")

    # ========================================================
    # LAYOUT
    # ========================================================

    def build_main(self):
        self.split = Adw.OverlaySplitView(min_sidebar_width=210, max_sidebar_width=260)

        sidebar_view = Adw.ToolbarView()
        sidebar_header = Adw.HeaderBar(show_title=False, show_end_title_buttons=False)
        sidebar_header.set_decoration_layout(DECORATION_LAYOUT)
        new_menu = Gio.Menu()
        new_menu.append("Neuer Ordner", "win.new-folder")
        new_menu.append("Neue Liste", "win.new-list")
        new_menu.append("Neues Board", "win.new-board")
        self.new_menu = new_menu
        new_button = icon_menu_button("plus", "Neu …")
        new_button.set_menu_model(new_menu)
        sidebar_header.pack_end(new_button)
        sidebar_view.add_top_bar(sidebar_header)
        self.sidebar = Sidebar(self)
        self.sidebar.connect("selected", lambda _sidebar, key: self.select(key))
        self.sidebar.connect("tags-changed", lambda _sidebar: self.show_notes())
        sidebar_view.set_content(self.sidebar)
        self.split.set_sidebar(sidebar_view)

        content = Adw.ToolbarView()
        header = Adw.HeaderBar()
        header.set_decoration_layout(DECORATION_LAYOUT)
        self.split.bind_property(
            "show-sidebar", header, "show-start-title-buttons",
            GObject.BindingFlags.SYNC_CREATE | GObject.BindingFlags.INVERT_BOOLEAN,
        )
        header.set_title_widget(Gtk.Box())
        toggle = icon_button("sidebar", "Seitenleiste", toggle=True)
        self.split.bind_property("show-sidebar", toggle, "active",
                                 GObject.BindingFlags.SYNC_CREATE | GObject.BindingFlags.BIDIRECTIONAL)
        header.pack_start(toggle)
        # Narrow windows show list and note one after the other; this leads back to the list.
        self.back_button = icon_button("back", "Zurück zur Liste")
        self.back_button.set_visible(False)
        self.back_button.connect("clicked", lambda _button: self.show_list_narrow())
        header.pack_start(self.back_button)

        self.view_toggle = Gtk.Box()
        self.view_toggle.add_css_class("linked")
        self.list_mode = icon_button("list", "Liste (Strg+1)", toggle=True)
        self.gallery_mode = icon_button("gallery", "Galerie (Strg+2)", toggle=True)
        self.gallery_mode.set_group(self.list_mode)
        self.list_mode.set_active(True)
        self.list_mode.connect("toggled", lambda button: button.get_active() and self.set_note_mode("list"))
        self.gallery_mode.connect("toggled", lambda button: button.get_active() and self.set_note_mode("gallery"))
        self.view_toggle.append(self.list_mode)
        self.view_toggle.append(self.gallery_mode)
        header.pack_start(self.view_toggle)
        self.delete_button = icon_button("trash", "Löschen")
        self.delete_button.set_action_name("win.delete-note")
        header.pack_start(self.delete_button)

        self.note_tools = Gtk.Box(spacing=4)
        compose = icon_button("compose", "Neue Notiz (Strg+N)")
        compose.set_action_name("win.new-note")
        self.note_tools.append(compose)
        self.format_button = icon_menu_button("format", "Format", self.build_format_popover())
        self.note_tools.append(self.format_button)
        checklist = icon_button("checklist", "Checkliste (Strg+Shift+L)")
        checklist.connect("clicked", lambda _button: self.paragraph("check"))
        self.note_tools.append(checklist)
        photo = icon_button("photo", "Foto einfügen")
        photo.set_action_name("win.insert-photo")
        self.note_tools.append(photo)
        self.lock_button = icon_button("lock", "Notiz sperren")
        self.lock_button.set_action_name("win.lock-button")
        self.note_tools.append(self.lock_button)
        self.share_button = icon_button("share", "Notiz teilen …")
        self.share_button.set_action_name("win.share-note")
        self.note_tools.append(self.share_button)
        header.pack_end(self.note_tools)
        content.add_top_bar(header)

        self.stack = Gtk.Stack(transition_type=Gtk.StackTransitionType.CROSSFADE)
        paned = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL, shrink_start_child=False)
        self.note_list = NoteList(self.sync)
        self.note_list.set_size_request(280, -1)
        self.note_list.connect("note-selected", lambda _list, note_id: (self.open_note(note_id), self.show_note_narrow()))
        self.note_list.connect("context", self.on_note_context)
        self.note_list.search.connect("search-changed", lambda _entry: self.show_notes())
        self.note_pane = NotePane(self.sync)
        self.note_pane.editor.connect("edited", lambda _editor: self.save_current())
        self.note_pane.connect("unlock-requested", lambda _pane: self.unlock_current())
        self.note_pane.connect("restore-requested", lambda _pane: self.restore_current())
        paned.set_start_child(self.note_list)
        paned.set_end_child(self.note_pane)
        paned.set_position(320)
        self.stack.add_named(paned, "notes")
        self.list_view = ShoppingListView(self)
        self.stack.add_named(self.list_view, "list")
        self.board_view = BoardView(self)
        self.stack.add_named(self.board_view, "board")
        content.set_content(self.stack)
        self.split.set_content(content)
        self.pages.add_named(self.split, "main")
        self.build_breakpoints()

        keys = Gtk.EventControllerKey()
        keys.connect("key-pressed", self.on_key)
        self.add_controller(keys)
        activity = Gtk.EventControllerKey()
        activity.connect("key-pressed", lambda *_args: self.touch_vault() or False)
        self.add_controller(activity)

    def build_breakpoints(self):
        """Adapt to the window width like GNOME apps: the sidebar folds away below 900 px,
        below 620 px the note list and the note are shown one after the other."""
        self.narrow = False
        self.narrow_note = False
        self.set_size_request(360, 420)
        sidebar = Adw.Breakpoint.new(Adw.BreakpointCondition.parse("max-width: 900sp"))
        sidebar.add_setter(self.split, "collapsed", True)
        sidebar.add_setter(self.split, "show-sidebar", False)
        self.add_breakpoint(sidebar)
        # Only one breakpoint applies at a time, so the narrow one folds the sidebar too.
        single = Adw.Breakpoint.new(Adw.BreakpointCondition.parse("max-width: 620sp"))
        single.add_setter(self.split, "collapsed", True)
        single.add_setter(self.split, "show-sidebar", False)
        single.connect("apply", lambda _bp: self.set_narrow(True))
        single.connect("unapply", lambda _bp: self.set_narrow(False))
        self.add_breakpoint(single)

    def set_narrow(self, narrow):
        self.narrow = narrow
        self.update_narrow()

    def show_note_narrow(self):
        self.narrow_note = True
        self.update_narrow()

    def show_list_narrow(self):
        self.narrow_note = False
        self.update_narrow()

    def update_narrow(self):
        note = self.narrow and self.narrow_note and self.current_note is not None
        self.note_list.set_visible(not self.narrow or not note)
        self.note_pane.set_visible(not self.narrow or note)
        self.back_button.set_visible(note and self.stack.get_visible_child_name() == "notes")

    def build_format_popover(self):
        popover = Gtk.Popover()
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        box.set_margin_start(6)
        box.set_margin_end(6)
        box.set_margin_top(6)
        box.set_margin_bottom(6)
        inline = Gtk.Box(homogeneous=True)
        inline.add_css_class("linked")
        for key, label, css in (("b", "B", "text-bold"), ("i", "I", "text-italic"),
                                ("u", "U", "text-underline"), ("s", "S", "text-strike"),
                                ("h", "✎", "text-highlight")):
            button = Gtk.Button(label=label)
            button.add_css_class(css)
            button.set_tooltip_text({"b": "Fett", "i": "Kursiv", "u": "Unterstrichen",
                                     "s": "Durchgestrichen", "h": "Hervorheben"}[key])
            button.connect("clicked", lambda _button, name=key: self.inline(name))
            inline.append(button)
        box.append(inline)
        box.append(Gtk.Separator(margin_top=4, margin_bottom=4))
        for style, label, accel in PARAGRAPH_MENU:
            row = Gtk.Button()
            row.add_css_class("flat")
            line = Gtk.Box(spacing=16)
            text = Gtk.Label(label=label, xalign=0, hexpand=True)
            if style in ("title", "heading", "subheading"):
                text.add_css_class({"title": "title-3", "heading": "heading", "subheading": "heading"}[style])
            if style == "mono":
                text.add_css_class("monospace")
            line.append(text)
            hint = Gtk.Label(label=Gtk.accelerator_get_label(*Gtk.accelerator_parse(accel)[1:]))
            hint.add_css_class("dim-label")
            line.append(hint)
            row.set_child(line)
            row.connect("clicked", lambda _button, name=style: (popover.popdown(), self.paragraph(name)))
            box.append(row)
        box.append(Gtk.Separator(margin_top=4, margin_bottom=4))
        self.sort_checked = Gtk.CheckButton(label="Abgehakte Objekte nach unten sortieren")
        self.sort_checked.connect("toggled", lambda button: setattr(self.note_pane.editor, "auto_sort_checked", button.get_active()))
        box.append(self.sort_checked)
        popover.set_child(box)
        return popover

    def toast(self, text):
        toast = Adw.Toast(title=text)
        toast.set_timeout(3)
        self.toasts.add_toast(toast)

    # ========================================================
    # ACCOUNT
    # ========================================================

    def on_signed_in(self, login, server, response, account):
        if login.connecting:
            # Used without a server so far: move everything into the account.
            def done(_result, error):
                if isinstance(error, sync_module.VaultConflict):
                    self.toast("Dieses Konto hat schon ein Notizen-Passwort. Entferne zuerst die Sperre deiner gesperrten Notizen.")
                    return
                if error is not None:
                    self.toast(f"Verbinden fehlgeschlagen: {error_text(error)}")
                    return
                login.set_connecting(False)
                self.vault_key = None
                self.enter_main()
                self.toast("Mit dem Server verbunden – deine Notizen werden hochgeladen.")
            run_async(lambda: self.sync.connect_local(server, response, account), done)
            return
        self.sync.sign_in(server, response, account)
        self.enter_main()

    def on_local(self, _login, name):
        self.sync.start_local(name)
        self.enter_main()

    def connect_server(self):
        self.login.set_connecting(True)
        self.pages.set_visible_child_name("login")

    def needs_server(self, then):
        """Sharing, people and key files only make sense with a server."""
        if self.sync.is_local:
            self.toast("Dafür brauchst du einen Server – Kontomenü → „Mit Server verbinden …“")
        else:
            then()

    def update_account_actions(self):
        local = self.sync.is_local
        self.lookup_action("connect").set_enabled(local)
        for name in ("people", "invite", "keyfile"):
            self.lookup_action(name).set_enabled(not local)

    def enter_main(self):
        self.pages.set_visible_child_name("main")
        self.update_account_actions()

        def first_sync():
            self.sync.sync_now()

        def done(_result, error):
            if error is not None:
                self.toast("Offline – Änderungen werden später übertragen.")
            model.ensure_defaults(self.sync)
            self.purge_trash()
            self.sync.start()
            self.refresh_all()
            self.on_status(self.sync.online)

        self.refresh_all()
        # Start in the note list, not in the search field (Ctrl+F still goes there).
        GLib.idle_add(lambda: self.note_list.list.grab_focus() and False)
        run_async(first_sync, done)

    def on_status(self, online):
        if online is None:
            # This device was signed out on the server.
            self.sync.sign_out()
            self.pages.set_visible_child_name("login")
            self.toast("Dieses Gerät wurde abgemeldet.")
            return
        self.sidebar.set_status(bool(online))

    def on_channel(self, channel):
        """Another device wants to join, or someone wants to verify."""
        if channel["purpose"] == "link":
            security_ui.approve_device(self, channel)
        elif channel["purpose"] == "verify":
            security_ui.answer_verification(self, channel)

    def sign_out(self):
        def really():
            self.sync.sign_out()
            self.vault_key = None
            self.login.set_connecting(False)
            self.pages.set_visible_child_name("login")
        if self.sync.is_local:
            confirm(self, "Alle Daten löschen?",
                    "Alle Notizen, Listen und Aufgaben auf diesem Computer werden endgültig gelöscht.", "Löschen", really)
            return
        confirm(self, "Dieses Gerät abmelden?",
                "Die Notizen bleiben auf dem Server. Zum erneuten Anmelden brauchst du ein anderes Gerät oder deine Schlüsseldatei.",
                "Abmelden", really)

    def invite(self):
        def done(code, error):
            if error is not None:
                self.toast(error_text(error))
                return
            dialog = Adw.AlertDialog(
                heading="Einladungscode",
                body=f"Mit diesem Code kann einmalig ein neues Konto erstellt werden:\n\n{code}\n\n"
                     f"Server: {self.sync.server}\nIn der App „Neues Konto erstellen“ wählen.",
            )
            dialog.add_response("copy", "Kopieren")
            dialog.add_response("ok", "Fertig")
            dialog.connect("response", lambda _d, r: r == "copy" and self.get_clipboard().set(code))
            dialog.present(self)
        run_async(self.sync.api.invite, done)

    def share(self, object_id):
        obj = self.sync.get(object_id)
        if obj is not None:
            self.needs_server(lambda: security_ui.ShareDialog(self, obj).present(self))

    # ========================================================
    # NAVIGATION
    # ========================================================

    def refresh_all(self):
        self.sidebar.refresh()
        self.select(self.current_key, keep_note=True)

    def select(self, key, keep_note=False):
        if key != self.current_key:
            self.narrow_note = False
        self.current_key = key
        kind, _sep, object_id = key.partition(":")
        if kind == "list" and self.sync.get(object_id):
            self.note_pane.editor.flush()
            self.list_view.show(object_id)
            self.stack.set_visible_child_name("list")
            self.show_note_tools(False)
            return
        if kind == "board" and self.sync.get(object_id):
            self.note_pane.editor.flush()
            self.board_view.show(object_id)
            self.stack.set_visible_child_name("board")
            self.show_note_tools(False)
            return
        self.stack.set_visible_child_name("notes")
        self.show_note_tools(True)
        self.show_notes(keep_note)

    def show_note_tools(self, visible):
        self.note_tools.set_visible(visible)
        self.view_toggle.set_visible(visible)
        self.delete_button.set_visible(visible)
        self.update_narrow()

    def notes_for(self, key):
        notes = self.sync.objects("note")
        kind, _sep, object_id = key.partition(":")
        if key == "trash":
            return [n for n in notes if n["data"].get("trashed")], "Zuletzt gelöscht"
        notes = [n for n in notes if not n["data"].get("trashed")]
        if key == "locked":
            return [n for n in notes if n["data"].get("enc")], "Gesperrt"
        if key == "shared-notes":
            return [n for n in notes if n.get("share") and not self.sync.get(n["data"].get("folder") or "")], "Mit mir geteilt"
        if kind == "folder":
            folder = self.sync.get(object_id)
            name = folder["data"].get("name", "Ordner") if folder else "Ordner"
            return [n for n in notes if n["data"].get("folder") == object_id], name
        return notes, "Alle Notizen"

    def show_notes(self, keep_note=True):
        notes, title = self.notes_for(self.current_key)
        tags = self.sidebar.active_tags
        if tags:
            notes = [n for n in notes if tags <= model.note_tags(n)]
            title += " · " + " ".join("#" + tag for tag in sorted(tags))
        query = self.note_list.search.get_text().strip().lower()
        if query:
            notes = [n for n in notes if query in model.note_text(n).lower()
                     or query in model.note_title(n).lower()]
            title = f"Suche: {query}"
        selected = self.current_note if keep_note else None
        if selected and selected not in {n["id"] for n in notes}:
            selected = None
        self.note_list.show(title, notes, selected, "Keine Treffer" if query else "Keine Notizen")
        if selected is None:
            if notes and not keep_note:
                first = sorted(notes, key=lambda n: (not n["data"].get("pinned"), -model.modified(n)))[0]
                self.open_note(first["id"])
                self.note_list.show(title, notes, first["id"])
            elif not notes:
                self.current_note = None
                self.note_pane.show_empty()
        self.update_note_actions()

    def set_note_mode(self, mode):
        self.note_list.set_mode(mode)
        self.show_notes()

    # ========================================================
    # NOTES
    # ========================================================

    def current_folder_for_new(self):
        kind, _sep, object_id = self.current_key.partition(":")
        if kind == "folder" and self.sync.get(object_id):
            return self.sync.get(object_id)
        return self.sync.get(model.default_private_folder(self.sync.user_id))

    def new_note(self):
        if self.stack.get_visible_child_name() != "notes" or self.current_key in ("trash", "locked"):
            self.sidebar.select("all", emit=False)
            self.current_key = "all"
            self.stack.set_visible_child_name("notes")
            self.show_note_tools(True)
        self.note_pane.editor.flush()
        folder = self.current_folder_for_new()
        now = time.time()
        note = self.sync.put("note", {
            "folder": folder["id"] if folder else None,
            "body": model.empty_note_body(),
            "created": now, "modified": now,
        }, folder.get("share") if folder else None, notify=False)
        self.current_note = note["id"]
        self.sidebar.refresh()
        self.show_notes()
        self.open_note(note["id"])
        self.show_note_narrow()
        self.note_pane.editor.grab_focus()

    def open_note(self, note_id):
        if note_id != self.current_note:
            self.note_pane.editor.flush()
        note = self.sync.get(note_id)
        self.current_note = note_id
        if note is None:
            self.note_pane.show_empty()
            return
        if note["data"].get("enc"):
            if self.vault_key is None:
                self.note_pane.show_locked(note_id)
                self.update_note_actions()
                return
            try:
                blocks = vault.open_box(self.vault_key, note["data"]["enc"])["body"]
            except Exception:
                self.toast("Diese Notiz konnte nicht entschlüsselt werden.")
                self.note_pane.show_locked(note_id)
                return
            self.touch_vault()
            if not note["data"].get("title") and model.blocks_title(blocks):
                # Notes locked before titles stayed visible get theirs now.
                self.sync.update(note_id, title=model.blocks_title(blocks))
        else:
            blocks = model.note_blocks(note)
        self.editing_blocks = blocks
        self.note_pane.show_note(note, blocks, editable=not note["data"].get("trashed"))
        self.update_note_actions()

    def save_current(self):
        note = self.sync.get(self.current_note) if self.current_note else None
        if note is None or note["data"].get("trashed"):
            return
        blocks = self.note_pane.editor.to_blocks()
        if blocks == self.editing_blocks:
            return
        self.editing_blocks = blocks
        data = dict(note["data"])
        data["modified"] = time.time()
        if data.get("enc"):
            if self.vault_key is None:
                return
            data["enc"] = vault.seal(self.vault_key, {"body": blocks})
            data["title"] = model.blocks_title(blocks)
            self.touch_vault()
        else:
            data["body"] = blocks
        self.sync.put("note", data, note.get("share"), note["id"], notify=False)
        self.note_pane.update_date(self.sync.get(note["id"]))
        self.refresh_list_only()

    def refresh_list_only(self):
        self.sidebar.refresh()
        self.show_notes()

    def update_note_actions(self):
        note = self.sync.get(self.current_note) if self.current_note else None
        has = note is not None
        for name in ("delete-note", "toggle-lock", "lock-button", "move-note", "pin-note", "duplicate-note", "insert-photo"):
            self.lookup_action(name).set_enabled(has)
        if has:
            locked = bool(note["data"].get("enc"))
            # Like Apple: the open lock in an unlocked note locks it again right away.
            unlocked = locked and self.vault_key is not None
            self.lock_button.get_child().name = "lock-open" if unlocked else "lock"
            self.lock_button.set_tooltip_text("Jetzt sperren" if unlocked else "Entsperren" if locked else "Notiz sperren")
            self.lock_button.get_child().queue_draw()
            self.lookup_action("insert-photo").set_enabled(not locked and not note["data"].get("trashed"))

    def delete_note(self, note_id=None):
        note_id = note_id or self.current_note
        note = self.sync.get(note_id)
        if note is None:
            return
        if note["data"].get("trashed"):
            confirm(self, "Endgültig löschen?", "Die Notiz wird auf allen Geräten gelöscht.", "Löschen",
                    lambda: (self.sync.delete(note_id), self.after_delete()))
            return
        self.sync.update(note_id, trashed=time.time())
        self.after_delete()
        self.toast("In „Zuletzt gelöscht“ verschoben")

    def after_delete(self):
        self.current_note = None
        self.sidebar.refresh()
        self.show_notes(keep_note=False)

    def restore_current(self):
        note = self.sync.get(self.current_note)
        if note is None:
            return
        data = dict(note["data"])
        data.pop("trashed", None)
        if not self.sync.get(data.get("folder") or ""):
            data["folder"] = model.default_private_folder(self.sync.user_id)
            self.sync.put("note", data, None if note["owner"] == self.sync.user_id else note.get("share"), note["id"])
        else:
            self.sync.put("note", data, note.get("share"), note["id"])
        self.toast("Notiz wiederhergestellt")
        self.refresh_list_only()
        self.open_note(note["id"])

    def purge_trash(self):
        limit = time.time() - TRASH_DAYS * 86400
        for note in self.sync.objects("note"):
            trashed = note["data"].get("trashed")
            if trashed and trashed < limit and (note["owner"] == self.sync.user_id or note["space"] == "shared"):
                self.sync.delete(note["id"], notify=False)

    def toggle_pin(self, note_id=None):
        note = self.sync.get(note_id or self.current_note)
        if note:
            self.sync.update(note["id"], pinned=not note["data"].get("pinned"))
            self.refresh_list_only()

    def duplicate(self, note_id=None):
        note = self.sync.get(note_id or self.current_note)
        if note is None or note["data"].get("enc"):
            return
        data = dict(note["data"])
        data["modified"] = data["created"] = time.time()
        data.pop("pinned", None)
        copy = self.sync.put("note", data, note.get("share"))
        self.current_note = copy["id"]
        self.refresh_list_only()
        self.open_note(copy["id"])

    def move_note(self, note_id=None):
        note = self.sync.get(note_id or self.current_note)
        if note is None:
            return
        folders = sorted(self.sync.objects("folder"), key=lambda f: (bool(f.get("share")), f["data"].get("name", "")))
        choices = [(f["id"], f["data"].get("name", "") + (" (geteilt)" if f.get("share") else ""))
                   for f in folders if f["id"] != note["data"].get("folder")]
        if not choices:
            return
        dialog = Adw.AlertDialog(heading="Verschieben nach",
                                 body="Notizen in geteilten Ordnern sehen alle, mit denen der Ordner geteilt ist.")
        dropdown = Gtk.DropDown.new_from_strings([label for _id, label in choices])
        dialog.set_extra_child(dropdown)
        dialog.add_response("cancel", "Abbrechen")
        dialog.add_response("ok", "Verschieben")
        dialog.set_response_appearance("ok", Adw.ResponseAppearance.SUGGESTED)

        def on_response(_dialog, response):
            if response != "ok":
                return
            folder = self.sync.get(choices[dropdown.get_selected()][0])
            share = folder.get("share")
            if share and note["data"].get("enc"):
                self.toast("Gesperrte Notizen können nicht geteilt werden. Entferne zuerst die Sperre.")
                return
            if share != note.get("share") and note["owner"] != self.sync.user_id:
                self.toast("Nur wer die Notiz erstellt hat, kann sie in einen anderen Bereich verschieben.")
                return
            current = self.sync.get(note["id"])

            def move():
                data = self.sync.rekey_files(current, share) if share != current.get("share") else dict(current["data"])
                data["folder"] = folder["id"]
                self.sync.put("note", data, share, current["id"])

            run_async(move, lambda *_a: (self.toast(f"Nach „{folder['data'].get('name')}“ verschoben"), self.refresh_list_only()))

        dialog.connect("response", on_response)
        dialog.present(self)

    def insert_photo(self):
        note = self.sync.get(self.current_note)
        if note is None or note["data"].get("enc"):
            return
        dialog = Gtk.FileDialog(title="Foto einfügen")
        filters = Gio.ListStore.new(Gtk.FileFilter)
        images = Gtk.FileFilter(name="Bilder")
        images.add_mime_type("image/*")
        filters.append(images)
        dialog.set_filters(filters)

        def chosen(dialog, result):
            try:
                file = dialog.open_finish(result)
            except GLib.Error:
                return
            path = Path(file.get_path())
            mime = mimetypes.guess_type(path.name)[0] or "image/jpeg"
            content = path.read_bytes()

            def done(file_id, error):
                if error is not None:
                    self.toast(error_text(error))
                    return
                self.note_pane.editor.insert_image(file_id)
            run_async(lambda: self.sync.upload_file(content, note.get("share")), done)

        dialog.open(self, None, chosen)

    def paragraph(self, style):
        if self.note_pane.get_visible_child_name() == "editor":
            self.note_pane.editor.apply_paragraph(style)
            self.note_pane.editor.grab_focus()

    def inline(self, name):
        if self.note_pane.get_visible_child_name() == "editor":
            self.note_pane.editor.toggle_inline(name)

    def on_note_context(self, _list, note_id, widget, x, y):
        note = self.sync.get(note_id)
        if note is None:
            return
        self.open_note(note_id)
        menu = Gio.Menu()
        if note["data"].get("trashed"):
            menu.append("Wiederherstellen", "win.restore-note")
            menu.append("Endgültig löschen", "win.delete-note")
        else:
            menu.append("Lösen" if note["data"].get("pinned") else "Anheften", "win.pin-note")
            menu.append("Teilen …", "win.share-note")
            menu.append("Verschieben nach …", "win.move-note")
            menu.append("Duplizieren", "win.duplicate-note")
            menu.append("Sperre entfernen" if note["data"].get("enc") else "Notiz sperren", "win.toggle-lock")
            menu.append("Löschen", "win.delete-note")
        self.popup_menu(menu, widget, x, y)

    def popup_menu(self, menu, widget, x, y):
        popover = Gtk.PopoverMenu.new_from_model(menu)
        popover.set_parent(widget)
        popover.set_has_arrow(False)
        rect = Gdk.Rectangle()
        rect.x, rect.y, rect.width, rect.height = int(x), int(y), 1, 1
        popover.set_pointing_to(rect)
        popover.connect("closed", lambda p: GLib.idle_add(lambda: (p.unparent(), False)[1]))
        popover.popup()

    # ========================================================
    # LOCKED NOTES
    # ========================================================

    def vault_object(self):
        return self.sync.get(f"vault-{self.sync.user_id}")

    def touch_vault(self):
        if self.vault_key is not None:
            self.vault_used = time.time()

    def check_auto_lock(self):
        if self.vault_key is not None and time.time() - self.vault_used > AUTO_LOCK_SECONDS:
            self.lock_all()
        return True

    def lock_all(self):
        if self.vault_key is None:
            return
        self.note_pane.editor.flush()
        self.vault_key = None
        note = self.sync.get(self.current_note) if self.current_note else None
        if note is not None and note["data"].get("enc"):
            self.note_pane.show_locked(note["id"])
        self.update_note_actions()

    def with_vault(self, then, reason="Gib dein Notizen-Passwort ein."):
        """Make sure the vault is unlocked (creating it first if needed)."""
        if self.vault_key is not None:
            self.touch_vault()
            then()
            return
        existing = self.vault_object()
        if existing is None:
            def create(password, hint):
                data, key = vault.create_vault(password, hint or "")
                self.sync.put("vault", data, None, f"vault-{self.sync.user_id}")
                self.vault_key = key
                self.touch_vault()
                then()
            ask_password(
                self, "Notizen-Passwort festlegen",
                "Gesperrte Notizen werden auf deinem Gerät mit diesem Passwort verschlüsselt – "
                "nicht einmal der Server kann sie lesen. Wenn du das Passwort vergisst, "
                "lassen sich gesperrte Notizen nicht wiederherstellen.",
                create, confirm=True, action="Festlegen",
            )
            return

        def unlock(password, _hint):
            def derive():
                return vault.unlock(existing["data"], password)

            def done(key, error):
                if error is not None:
                    self.toast("Falsches Passwort.")
                    return
                self.vault_key = key
                self.touch_vault()
                then()
            run_async(derive, done)
        ask_password(self, "Gesperrte Notizen", reason, unlock, hint=existing["data"].get("hint"), action="Entsperren")

    def on_lock_button(self):
        note = self.sync.get(self.current_note) if self.current_note else None
        if note is None or not note["data"].get("enc"):
            self.toggle_lock()
        elif self.vault_key is not None:
            self.lock_all()
        else:
            self.unlock_current()

    def watch_screen_lock(self):
        """Like Apple when the device sleeps: locking the screen locks the notes."""
        def on_signal(_connection, _sender, _path, _iface, _signal, params, *_args):
            if params.unpack()[0]:
                self.lock_all()
        try:
            bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
            bus.signal_subscribe(None, "org.gnome.ScreenSaver", "ActiveChanged", "/org/gnome/ScreenSaver",
                                 None, Gio.DBusSignalFlags.NONE, on_signal)
        except GLib.Error:
            pass

    def unlock_current(self):
        note_id = self.current_note
        self.with_vault(lambda: self.open_note(note_id))

    def toggle_lock(self):
        note = self.sync.get(self.current_note)
        if note is None:
            return
        if note["data"].get("enc"):
            def remove():
                current = self.sync.get(note["id"])
                body = vault.open_box(self.vault_key, current["data"]["enc"])["body"]
                data = dict(current["data"])
                data.pop("enc")
                data.pop("title", None)
                data["body"] = body
                self.sync.put("note", data, current.get("share"), current["id"])
                self.toast("Sperre entfernt")
                self.refresh_list_only()
                self.open_note(current["id"])
            self.with_vault(remove, "Gib dein Notizen-Passwort ein, um die Sperre zu entfernen.")
            return
        if note["space"] == "shared":
            self.toast("Geteilte Notizen können nicht gesperrt werden – wie in Apples Notizen.")
            return

        def lock():
            self.note_pane.editor.flush()
            current = self.sync.get(note["id"])
            data = dict(current["data"])
            body = data.pop("body", [])
            data["enc"] = vault.seal(self.vault_key, {"body": body})
            data["title"] = model.blocks_title(body)
            data["modified"] = time.time()
            self.sync.put("note", data, current.get("share"), current["id"])
            self.toast("Notiz gesperrt")
            self.refresh_list_only()
            self.open_note(current["id"])
        self.with_vault(lock)

    def change_vault_password(self):
        existing = self.vault_object()
        if existing is None:
            self.toast("Du hast noch kein Notizen-Passwort festgelegt.")
            return

        def got_old(old, _hint):
            try:
                old_key = vault.unlock(existing["data"], old)
            except vault.WrongPassword:
                self.toast("Falsches Passwort.")
                return

            def got_new(new, hint):
                data, new_key = vault.create_vault(new, hint or "")
                count = 0
                for note in self.sync.objects("note"):
                    if note["data"].get("enc") and note["owner"] == self.sync.user_id:
                        content = vault.open_box(old_key, note["data"]["enc"])
                        updated = dict(note["data"])
                        updated["enc"] = vault.seal(new_key, content)
                        self.sync.put("note", updated, note.get("share"), note["id"], notify=False)
                        count += 1
                self.sync.put("vault", data, None, existing["id"])
                self.vault_key = new_key
                self.touch_vault()
                self.toast(f"Notizen-Passwort geändert, {count} Notizen neu verschlüsselt.")
            ask_password(self, "Neues Notizen-Passwort", "", got_new, confirm=True, action="Ändern")
        ask_password(self, "Notizen-Passwort ändern", "Gib dein aktuelles Notizen-Passwort ein.", got_old,
                     hint=existing["data"].get("hint"))

    # ========================================================
    # FOLDERS, LISTS, BOARDS
    # ========================================================

    def new_folder(self):
        def create(name, _choice):
            folder = self.sync.put("folder", {"name": name, "order": time.time()})
            self.sidebar.refresh()
            self.sidebar.select("folder:" + folder["id"])
        ask_text(self, "Neuer Ordner", create, placeholder="Name", action="Erstellen",
                 body="Neue Ordner sind privat. Mit Rechtsklick → „Teilen …“ kannst du sie freigeben.")

    def new_list(self):
        def create(name, _choice):
            shopping = self.sync.put("list", {"name": name, "grocery": True, "order": time.time()})
            self.sidebar.refresh()
            self.sidebar.select("list:" + shopping["id"])
        ask_text(self, "Neue Liste", create, placeholder="z. B. Drogerie", action="Erstellen")

    def new_board(self):
        def create(name, _choice):
            board = self.sync.put("board", {"name": name, "order": time.time()})
            for order, (_key, column) in enumerate(model.DEFAULT_COLUMNS):
                self.sync.put("column", {"board": board["id"], "name": column, "order": order}, None, notify=False)
            self.sidebar.refresh()
            self.sidebar.select("board:" + board["id"])
        ask_text(self, "Neues Board", create, placeholder="z. B. Haushalt", action="Erstellen")

    def object_menu(self, kind, object_id, widget, x, y):
        obj = self.sync.get(object_id)
        if obj is None:
            return
        self.menu_target = object_id
        menu = Gio.Menu()
        menu.append("Teilen …", "win.share-object")
        menu.append("Umbenennen …", "win.rename-object")
        if kind == "board":
            menu.append("Entwicklungsprojekt ausschalten" if obj["data"].get("dev") else "Als Entwicklungsprojekt führen",
                        "win.toggle-dev")
        protected = object_id == model.default_private_folder(self.sync.user_id)
        if not protected:
            menu.append("Löschen …", "win.delete-object")
        self.popup_menu(menu, widget, x, y)

    def toggle_dev(self):
        """Development projects show card ids, the status history and the trace fields."""
        board = self.sync.get(getattr(self, "menu_target", ""))
        if board is None or board["kind"] != "board":
            return
        dev = not board["data"].get("dev")
        self.sync.update(board["id"], dev=dev)
        self.toast(f"„{board['data'].get('name', 'Board')}“ ist jetzt ein Entwicklungsprojekt." if dev
                   else f"„{board['data'].get('name', 'Board')}“ ist wieder ein einfaches Board.")
        self.refresh_all()

    def rename_object(self):
        obj = self.sync.get(getattr(self, "menu_target", ""))
        if obj is None:
            return
        ask_text(self, "Umbenennen", lambda name, _c: (self.sync.update(obj["id"], name=name), self.refresh_all()),
                 text=obj["data"].get("name", ""))

    def delete_object(self):
        obj = self.sync.get(getattr(self, "menu_target", ""))
        if obj is None:
            return
        kind = obj["kind"]
        name = obj["data"].get("name", "")
        if obj["space"] == "shared" and obj["owner"] != self.sync.user_id:
            body = f"„{name}“ gehört allen – es wird auch für die anderen gelöscht."
        else:
            body = f"„{name}“ und alles darin wird gelöscht."

        def remove():
            if kind == "folder":
                for note in self.sync.objects("note"):
                    if note["data"].get("folder") == obj["id"]:
                        self.sync.update(note["id"], notify=False, trashed=time.time())
            elif kind == "list":
                for item in self.sync.objects("item"):
                    if item["data"].get("list") == obj["id"]:
                        self.sync.delete(item["id"], notify=False)
            elif kind == "board":
                for child in self.sync.objects("card") + self.sync.objects("column"):
                    if child["data"].get("board") == obj["id"]:
                        self.sync.delete(child["id"], notify=False)
            self.sync.delete(obj["id"])
            self.current_key = "all"
            self.refresh_all()
        confirm(self, "Löschen?", body, "Löschen", remove)

    # ========================================================
    # SYNC EVENTS
    # ========================================================

    def on_sync_changed(self, ids):
        if self.pages.get_visible_child_name() != "main":
            return
        self.sidebar.refresh()
        visible = self.stack.get_visible_child_name()
        if visible == "list":
            self.list_view.refresh()
        elif visible == "board":
            self.board_view.refresh()
        else:
            self.show_notes()
            # A note open here was changed on another device: reload it
            # unless there are local edits that have not been saved yet.
            if self.current_note in ids and self.note_pane.editor.edit_source is None:
                note = self.sync.get(self.current_note)
                if note is None:
                    self.note_pane.show_empty()
                elif not note["data"].get("enc") and model.note_blocks(note) != self.editing_blocks:
                    self.editing_blocks = model.note_blocks(note)
                    self.note_pane.editor.load_blocks(self.editing_blocks, keep_cursor=True)
                    self.note_pane.update_date(note)
        self.update_note_actions()

    # ========================================================
    # ACTIONS AND KEYS
    # ========================================================

    def install_actions(self):
        actions = {
            "new-note": self.new_note,
            "delete-note": self.delete_note,
            "restore-note": self.restore_current,
            "pin-note": self.toggle_pin,
            "duplicate-note": self.duplicate,
            "move-note": self.move_note,
            "toggle-lock": self.toggle_lock,
            "lock-button": self.on_lock_button,
            "lock-all": self.lock_all,
            "insert-photo": self.insert_photo,
            "new-folder": self.new_folder,
            "new-list": self.new_list,
            "new-board": self.new_board,
            "rename-object": self.rename_object,
            "toggle-dev": self.toggle_dev,
            "delete-object": self.delete_object,
            "invite": self.invite,
            "people": lambda: security_ui.PeopleDialog(self).present(self),
            "keyfile": lambda: security_ui.KeyfileDialog(self).present(self),
            "help": lambda: security_ui.show_help(self),
            "share-note": lambda: self.current_note and self.share(self.current_note),
            "share-object": lambda: self.share(getattr(self, "menu_target", "")),
            "change-vault": self.change_vault_password,
            "sign-out": self.sign_out,
            "connect": self.connect_server,
            "search": lambda: (self.select("all"), self.note_list.search.grab_focus()),
            "list-view": lambda: self.list_mode.set_active(True),
            "gallery-view": lambda: self.gallery_mode.set_active(True),
        }
        for name, callback in actions.items():
            action = Gio.SimpleAction.new(name, None)
            action.connect("activate", lambda _a, _p, function=callback: function())
            self.add_action(action)

    def on_key(self, controller, keyval, keycode, state):
        control = bool(state & Gdk.ModifierType.CONTROL_MASK)
        if not control:
            return False
        shift = bool(state & Gdk.ModifierType.SHIFT_MASK)
        alt = bool(state & Gdk.ModifierType.ALT_MASK)
        key = Gdk.keyval_to_lower(keyval)
        if key == Gdk.KEY_n and shift:
            self.new_folder()
            return True
        if key == Gdk.KEY_n:
            self.new_note()
            return True
        if key == Gdk.KEY_d and not shift:
            self.duplicate()
            return True
        if key == Gdk.KEY_f and (alt or not self.note_pane.editor.has_focus()):
            self.activate_action("win.search")
            return True
        if key == Gdk.KEY_1:
            self.list_mode.set_active(True)
            return True
        if key == Gdk.KEY_2:
            self.gallery_mode.set_active(True)
            return True
        if key == Gdk.KEY_l and not shift and alt:
            self.lock_all()
            return True
        return False
