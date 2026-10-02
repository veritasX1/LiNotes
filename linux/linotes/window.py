"""The LiNotes main window."""

import mimetypes
import re
import shutil
import tempfile
import time
from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("Pango", "1.0")

from gi.repository import Adw, Gdk, Gio, GLib, GObject, Gtk, Pango

from . import model, vault
from .dialogs import ask_password, ask_text, confirm, error_text, run_async
from . import security_ui, textsize
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

def text_size_step(keyval):
    """Ctrl with +, - or 0 (also on the number pad): +1, -1, 0 (normal); None otherwise."""
    if keyval in (Gdk.KEY_plus, Gdk.KEY_KP_Add, Gdk.KEY_equal):
        return 1
    if keyval in (Gdk.KEY_minus, Gdk.KEY_KP_Subtract):
        return -1
    if keyval in (Gdk.KEY_0, Gdk.KEY_KP_0):
        return 0
    return None


HIGHLIGHT_MENU = [("h", "Gelb"), ("h:orange", "Orange"), ("h:pink", "Pink"), ("h:purple", "Lila"),
                  ("h:mint", "Mint"), ("h:blue", "Blau"), (None, "Markierung entfernen")]

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
        self.note_windows = set()

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
        # Like Apple's "Ansicht → Sortieren nach": applies to all folders and both devices.
        sort_menu = Gio.Menu()
        section = Gio.Menu()
        for key, label in model.NOTE_SORTS:
            section.append(label, f"win.sort-notes::{key}")
        sort_menu.append_section("Notizen sortieren nach", section)
        # Like Apple's default text size: per device, Ctrl+Plus/Minus/0.
        sizes = Gio.Menu()
        for level, (_factor, label) in enumerate(textsize.SIZES):
            sizes.append(label, f"win.text-size::{level}")
        sort_menu.append_section("Textgröße (Strg + / Strg −)", sizes)
        self.sort_button = icon_menu_button("more", "Sortieren und Textgröße", Gtk.PopoverMenu.new_from_model(sort_menu))
        header.pack_start(self.sort_button)
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
        # A friendly reminder after a few days of use – never at the first start.
        self.keyfile_banner = Adw.Banner(title="Sichere dein Konto mit einer Schlüsseldatei – falls ein Gerät verloren geht.",
                                         button_label="Jetzt sichern")
        self.keyfile_banner.connect("button-clicked", lambda _b: (self.keyfile_banner.set_revealed(False),
                                                                  security_ui.KeyfileDialog(self).present(self)))
        content.add_top_bar(self.keyfile_banner)

        self.stack = Gtk.Stack(transition_type=Gtk.StackTransitionType.CROSSFADE)
        paned = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL, shrink_start_child=False)
        self.note_list = NoteList(self.sync)
        self.note_list.set_size_request(280, -1)
        self.note_list.connect("note-selected", lambda _list, note_id: (self.open_note(note_id), self.show_note_narrow()))
        self.note_list.connect("context", self.on_note_context)
        self.note_list.connect("open-window", lambda _list, note_id: self.open_note_window(note_id))
        self.note_list.connect("open-key", lambda _list, key: self.sidebar.select(key) or self.select(key))
        self.note_list.search.connect("search-changed", lambda _entry: self.show_notes())
        self.note_pane = NotePane(self.sync)
        self.note_pane.editor.connect("edited", lambda _editor: self.save_current())
        self.note_pane.editor.note_title = self.link_title
        self.note_pane.editor.connect("link-requested", lambda _editor: self.show_link_choice())
        self.note_pane.editor.connect("open-note", lambda _editor, note_id: self.open_linked_note(note_id))
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

    def build_format_popover(self, editor=None):
        """The format menu – of the main editor, or of a note in its own window (editor)."""
        popover = Gtk.Popover()
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        box.set_margin_start(6)
        box.set_margin_end(6)
        box.set_margin_top(6)
        box.set_margin_bottom(6)
        inline = Gtk.Box(homogeneous=True)
        inline.add_css_class("linked")
        for key, label, css in (("b", "B", "text-bold"), ("i", "I", "text-italic"),
                                ("u", "U", "text-underline"), ("s", "S", "text-strike")):
            button = Gtk.Button(label=label)
            button.add_css_class(css)
            button.set_tooltip_text({"b": "Fett", "i": "Kursiv", "u": "Unterstrichen", "s": "Durchgestrichen"}[key])
            button.connect("clicked", lambda _button, name=key: self.inline(name, editor))
            inline.append(button)
        box.append(inline)
        # Highlight colors like in Apple's Notes; a click on the active color removes it again.
        colors = Gtk.Box(spacing=6, margin_top=6, margin_start=4)
        colors.append(Gtk.Label(label="Markieren", xalign=0, hexpand=True))
        for name, tooltip in HIGHLIGHT_MENU:
            swatch = Gtk.Button(tooltip_text=tooltip)
            swatch.add_css_class("highlight-swatch")
            swatch.add_css_class("swatch-" + (name.partition(":")[2] or "yellow") if name else "swatch-none")
            if not name:
                swatch.set_label("✕")
            swatch.connect("clicked", lambda _button, color=name: self.highlight(color, editor))
            colors.append(swatch)
        box.append(colors)
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
            row.connect("clicked", lambda _button, name=style: (popover.popdown(), self.paragraph(name, editor)))
            box.append(row)
        divider = Gtk.Button()
        divider.add_css_class("flat")
        line = Gtk.Box(spacing=16)
        line.append(Gtk.Label(label="Trennlinie", xalign=0, hexpand=True))
        hint = Gtk.Label(label="--- ↵")
        hint.add_css_class("dim-label")
        line.append(hint)
        divider.set_child(line)
        divider.set_tooltip_text("Oder auf einer leeren Zeile --- tippen und Enter drücken")
        divider.connect("clicked", lambda _button: (popover.popdown(), self.insert_divider(editor)))
        box.append(divider)
        box.append(Gtk.Separator(margin_top=4, margin_bottom=4))
        sort_checked = Gtk.CheckButton(label="Abgehakte Objekte nach unten sortieren")
        sort_checked.connect("toggled", lambda button: setattr(editor or self.note_pane.editor, "auto_sort_checked", button.get_active()))
        box.append(sort_checked)
        if editor is None:
            self.sort_checked = sort_checked
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
        if self.sync.keyfile_hint_due():
            # Shown for this session, then again in 30 days at the earliest.
            self.keyfile_banner.set_revealed(True)
            self.sync.snooze_keyfile_hint()
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
        self.sort_button.set_visible(visible)
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

    def folder_extras(self, key):
        """Subfolders, lists and boards of a folder – shown above its notes."""
        kind, _sep, folder_id = key.partition(":")
        if kind != "folder":
            return []
        sync = self.sync
        live = [n for n in sync.objects("note") if not n["data"].get("trashed")]
        entries = []
        for folder in sorted((f for f in sync.objects("folder") if model.folder_parent(sync, f) == folder_id), key=model.folder_sort_key):
            entries.append(("folder:" + folder["id"], "folder", folder["data"].get("name", "Ordner"),
                            sum(1 for n in live if n["data"].get("folder") == folder["id"]), "Ordner"))
        items = sync.objects("item")
        for shopping in sorted((l for l in sync.objects("list") if l["data"].get("folder") == folder_id), key=lambda l: l["data"].get("name", "").lower()):
            entries.append(("list:" + shopping["id"], "cart", shopping["data"].get("name", "Liste"),
                            sum(1 for i in items if i["data"].get("list") == shopping["id"] and not i["data"].get("done")), "Listen"))
        cards = sync.objects("card")
        for board in sorted((b for b in sync.objects("board") if b["data"].get("folder") == folder_id), key=lambda b: b["data"].get("name", "").lower()):
            entries.append(("board:" + board["id"], "board", board["data"].get("name", "Board"),
                            sum(1 for c in cards if c["data"].get("board") == board["id"] and not c["data"].get("archived")), "Boards"))
        return entries

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
        self.note_list.show_extras([] if query else self.folder_extras(self.current_key))
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
        if note["data"].get("enc") and self.vault_key is None:
            self.note_pane.show_locked(note_id)
            self.update_note_actions()
            return
        blocks = self.note_body(note)
        if blocks is None:
            self.toast("Diese Notiz konnte nicht entschlüsselt werden.")
            self.note_pane.show_locked(note_id)
            return
        self.editing_blocks = blocks
        self.note_pane.show_note(note, blocks, editable=not note["data"].get("trashed"))
        self.update_note_actions()

    def note_body(self, note):
        """The blocks of a note, decrypted if it is locked; None while locked."""
        if not note["data"].get("enc"):
            return model.note_blocks(note)
        if self.vault_key is None:
            return None
        try:
            blocks = vault.open_box(self.vault_key, note["data"]["enc"])["body"]
        except Exception:
            return None
        self.touch_vault()
        if not note["data"].get("title") and model.blocks_title(blocks):
            # Notes locked before titles stayed visible get theirs now.
            self.sync.update(note["id"], title=model.blocks_title(blocks))
        return blocks

    # --- notes in their own window (like Apple: double-click) ---

    def open_note_window(self, note_id=None):
        from .note_window import NoteWindow
        note_id = note_id or self.current_note
        note = self.sync.get(note_id) if note_id else None
        if note is None or note["data"].get("trashed"):
            return
        for window in self.note_windows:
            if window.note_id == note_id:
                window.present()
                return
        if note["data"].get("enc") and self.vault_key is None:
            self.with_vault(lambda: self.open_note_window(note_id))
            return
        if note_id == self.current_note:
            self.note_pane.editor.flush()
        NoteWindow(self, note_id).present()

    # --- links between notes (">>", like Apple's Notes) ---

    def link_title(self, note_id):
        note = self.sync.get(note_id)
        return model.note_title(note) if note and not note["data"].get("trashed") else None

    def show_link_choice(self, editor=None, exclude=None):
        """After ">>": a list of notes at the cursor. Typing on filters it, ↑/↓ and
        Enter pick one, Esc (or leaving the line) keeps the ">>" as text."""
        editor = editor or self.note_pane.editor
        exclude = exclude or self.current_note
        listbox = Gtk.ListBox(selection_mode=Gtk.SelectionMode.BROWSE)
        listbox.add_css_class("navigation-sidebar")
        popover = Gtk.Popover(autohide=False, has_arrow=True, position=Gtk.PositionType.BOTTOM, can_focus=False)
        popover.set_child(Gtk.ScrolledWindow(child=listbox, propagate_natural_height=True, propagate_natural_width=True,
                                             max_content_height=320, hscrollbar_policy=Gtk.PolicyType.NEVER))
        listbox.set_size_request(300, -1)
        popover.set_parent(editor)
        found = []

        def close(note=None):
            editor.link_keys = None
            editor.buffer.disconnect(handler)
            popover.popdown()
            popover.unparent()
            editor.finish_link(note["id"] if note else None, model.note_title(note) if note else None)

        def fill():
            query = editor.pending_link_query()
            if query is None or len(query) > 60:
                GLib.idle_add(lambda: close() and False)
                return
            found[:] = model.link_choices(self.sync.objects("note"), exclude=exclude, query=query)
            while (row := listbox.get_row_at_index(0)) is not None:
                listbox.remove(row)
            for note in found:
                box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, margin_top=4, margin_bottom=4)
                box.append(Gtk.Label(label=model.note_title(note), xalign=0, ellipsize=Pango.EllipsizeMode.END))
                folder = self.sync.get(note["data"].get("folder") or "")
                if folder:
                    place = Gtk.Label(label=folder["data"].get("name", "Ordner"), xalign=0)
                    place.add_css_class("dim-label")
                    place.add_css_class("caption")
                    box.append(place)
                listbox.append(box)
            if not found:
                listbox.append(Gtk.Label(label="Keine passende Notiz", margin_top=6, margin_bottom=6, sensitive=False))
            else:
                listbox.select_row(listbox.get_row_at_index(0))
            popover.set_pointing_to(editor.cursor_rect())

        def keys(keyval):
            row = listbox.get_selected_row()
            index = row.get_index() if row else 0
            if keyval in (Gdk.KEY_Down, Gdk.KEY_Up) and found:
                index = max(0, min(len(found) - 1, index + (1 if keyval == Gdk.KEY_Down else -1)))
                listbox.select_row(listbox.get_row_at_index(index))
                return True
            if keyval in (Gdk.KEY_Return, Gdk.KEY_KP_Enter, Gdk.KEY_Tab) and found:
                close(found[index])
                return True
            if keyval == Gdk.KEY_Escape:
                close()
                return True
            return False

        listbox.connect("row-activated", lambda _list, row: found and close(found[row.get_index()]))
        handler = editor.buffer.connect_after("changed", lambda _buffer: fill())
        editor.link_keys = keys
        fill()
        popover.popup()

    def open_linked_note(self, note_id):
        note = self.sync.get(note_id)
        if note is None or note["data"].get("trashed"):
            self.toast("Die verlinkte Notiz gibt es nicht mehr.")
            return
        self.note_pane.editor.flush()
        if self.stack.get_visible_child_name() != "notes" or note_id not in {n["id"] for n in self.notes_for(self.current_key)[0]}:
            self.sidebar.select("all", emit=False)
            self.current_key = "all"
            self.stack.set_visible_child_name("notes")
            self.show_note_tools(True)
        self.open_note(note_id)
        self.show_notes(keep_note=True)
        self.show_note_narrow()

    def save_current(self):
        note = self.sync.get(self.current_note) if self.current_note else None
        if note is None or note["data"].get("trashed"):
            return
        blocks = self.note_pane.editor.to_blocks()
        if blocks == self.editing_blocks:
            return
        self.editing_blocks = blocks
        self.store_note(note["id"], blocks, self.note_pane.editor)

    def store_note(self, note_id, blocks, source):
        """Save edited blocks (from the main editor or a note window) and show them in
        the other places the note is open."""
        note = self.sync.get(note_id)
        if note is None or note["data"].get("trashed"):
            return
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
        if note_id == self.current_note and self.note_pane.get_visible_child_name() == "editor":
            if source is not self.note_pane.editor:
                self.editing_blocks = blocks
                self.note_pane.editor.load_blocks(blocks, keep_cursor=True)
            self.note_pane.update_date(self.sync.get(note_id))
        for window in list(self.note_windows):
            if window.note_id == note_id and window.editor is not source:
                window.load(keep_cursor=True)
        self.refresh_list_only()

    def refresh_list_only(self):
        self.sidebar.refresh()
        self.show_notes()

    def update_note_actions(self):
        note = self.sync.get(self.current_note) if self.current_note else None
        has = note is not None
        for name in ("delete-note", "toggle-lock", "lock-button", "move-note", "pin-note", "duplicate-note", "insert-photo",
                     "export-note", "print-note"):
            self.lookup_action(name).set_enabled(has)
        if has:
            locked = bool(note["data"].get("enc"))
            # Like Apple: the open lock in an unlocked note locks it again right away.
            unlocked = locked and self.vault_key is not None
            self.lock_button.get_child().name = "lock-open" if unlocked else "lock"
            self.lock_button.set_tooltip_text("Jetzt sperren" if unlocked else "Entsperren" if locked else "Notiz sperren")
            self.lock_button.get_child().queue_draw()
            self.lookup_action("insert-photo").set_enabled(not locked and not note["data"].get("trashed"))
            # A locked note can only be exported or printed while it is open.
            for name in ("export-note", "print-note"):
                self.lookup_action(name).set_enabled(not locked or unlocked)

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

    def note_for_print(self):
        """Title, PDF header and content of the open note (as shown, so an unlocked note works too)."""
        note = self.sync.get(self.current_note) if self.current_note else None
        if note is None:
            return None
        blocks = self.note_pane.editor.to_blocks() if self.note_pane.get_visible_child_name() == "editor" \
            else model.note_blocks(note)
        title = model.blocks_title(blocks) or "Notiz"
        modified = time.strftime("%d.%m.%Y %H:%M", time.localtime(note["data"].get("modified") or time.time()))
        return note, title, f"{title} · {modified}", blocks

    def write_note_pdf(self, path):
        from . import report
        note, title, header, blocks = self.note_for_print()
        report.write_note_pdf(blocks, path, header,
                              image_path=lambda reference: self.sync.fetch_file(reference, note.get("share")))
        return title

    def export_note(self):
        """Like Apple's "Als PDF exportieren …"."""
        found = self.note_for_print()
        if found is None:
            return
        safe = re.sub(r'[/\\:*?"<>|]', "_", found[1])[:80]
        dialog = Gtk.FileDialog(title="Als PDF exportieren")
        dialog.set_initial_name(f"{safe}.pdf")

        def chosen(dialog, result):
            try:
                path = dialog.save_finish(result).get_path()
            except GLib.Error:
                return
            path = path if path.lower().endswith(".pdf") else path + ".pdf"
            self.write_note_pdf(path)
            self.toast(f"PDF gespeichert: {Path(path).name}")
        dialog.save(self, None, chosen)

    def print_note(self):
        """The usual print dialog; the note goes to the printer as PDF."""
        if self.note_for_print() is None:
            return
        folder = Path(tempfile.mkdtemp(prefix="linotes-print-"))
        path = str(folder / "notiz.pdf")
        title = self.write_note_pdf(path)
        dialog = Gtk.PrintUnixDialog(title="Drucken", transient_for=self, modal=True)
        dialog.set_manual_capabilities(Gtk.PrintCapabilities.COPIES | Gtk.PrintCapabilities.PAGE_SET)

        def finished(*_args):
            shutil.rmtree(folder, ignore_errors=True)

        def response(dialog, answer):
            printer = dialog.get_selected_printer()
            settings, setup = dialog.get_settings(), dialog.get_page_setup()
            dialog.destroy()
            if answer != Gtk.ResponseType.OK or printer is None:
                finished()
                return
            if not printer.accepts_pdf():
                self.toast("Dieser Drucker nimmt kein PDF an – bitte als PDF exportieren und von dort drucken.")
                finished()
                return
            job = Gtk.PrintJob.new(title, printer, settings, setup)
            try:
                job.set_source_file(path)
            except GLib.Error as error:
                self.toast(f"Drucken nicht möglich: {error.message}")
                finished()
                return
            job.send(lambda _job, error: (finished(), error and self.toast(f"Drucken fehlgeschlagen: {error.message}")))
            self.toast(f"„{title}“ wird gedruckt.")
        dialog.connect("response", response)
        dialog.present()

    def move_note(self, note_id=None):
        note = self.sync.get(note_id or self.current_note)
        if note is None:
            return
        folders = sorted(self.sync.objects("folder"), key=lambda f: (bool(f.get("share")), model.folder_path(self.sync, f).lower()))
        choices = [(f["id"], model.folder_path(self.sync, f) + (" (geteilt)" if f.get("share") else ""))
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
            if response == "ok":
                self.move_note_to(note["id"], choices[dropdown.get_selected()][0])

        dialog.connect("response", on_response)
        dialog.present(self)

    def move_note_to(self, note_id, folder_id):
        """Move a note into a folder (from the dialog or by drag and drop)."""
        note = self.sync.get(note_id)
        folder = self.sync.get(folder_id) if folder_id else None
        if note is None or folder is None or note["data"].get("folder") == folder_id:
            return
        share = folder.get("share")
        if share and note["data"].get("enc"):
            self.toast("Gesperrte Notizen können nicht geteilt werden. Entferne zuerst die Sperre.")
            return
        if share != note.get("share") and note["owner"] != self.sync.user_id:
            self.toast("Nur wer die Notiz erstellt hat, kann sie in einen anderen Bereich verschieben.")
            return

        def move():
            current = self.sync.get(note_id)
            data = self.sync.rekey_files(current, share) if share != current.get("share") else dict(current["data"])
            data["folder"] = folder["id"]
            self.sync.put("note", data, share, current["id"], notify=False)
            self.sync.emit_from_thread({note_id})

        run_async(move, lambda _r, error: (self.toast(f"Verschieben fehlgeschlagen: {error}") if error
                                           else self.toast(f"Nach „{folder['data'].get('name')}“ verschoben"),
                                           self.refresh_list_only()))

    def move_object_to(self, object_id, folder_id):
        """Move a folder, list or board into a folder (None = top / no folder) – dialog or drag and drop."""
        obj = self.sync.get(object_id)
        if obj is None:
            return
        if obj["kind"] == "folder" and folder_id and folder_id in (model.folder_descendants(self.sync, object_id) | {object_id}):
            self.toast("Ein Ordner kann nicht in sich selbst liegen.")
            return
        field = "parent" if obj["kind"] == "folder" else "folder"
        if (obj["data"].get(field) or None) == folder_id:
            return
        if self.sync.share_after_move(obj, folder_id) != obj.get("share") and obj["owner"] != self.sync.user_id:
            self.toast("Nur wer es erstellt hat, kann es in einen anderen Bereich verschieben.")
            return
        if folder_id:
            self.sidebar.collapsed.discard(folder_id)
        # Into or out of a shared folder everything inside is re-encrypted – may take a moment.
        run_async(lambda: self.sync.move_to_folder(object_id, folder_id),
                  lambda _result, error: (self.toast(f"Verschieben fehlgeschlagen: {error}") if error else self.toast("Verschoben"),
                                          self.refresh_all()))

    def drop_on(self, target, payload):
        """Drag and drop onto the sidebar. target: "folder:<id>" or a section ("Notizen",
        "Listen", "Aufgaben" = take out of its folder). payload: "<kind>:<id>"."""
        kind, _sep, object_id = payload.partition(":")
        if target.startswith("folder:"):
            folder_id = target.partition(":")[2]
            if kind == "note":
                self.move_note_to(object_id, folder_id)
            elif kind in ("folder", "list", "board"):
                self.move_object_to(object_id, folder_id)
            return True
        section_kinds = {"Notizen": "folder", "Listen": "list", "Aufgaben": "board"}
        if section_kinds.get(target) == kind:
            self.move_object_to(object_id, None)
            return True
        return False

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

    def format_target(self, editor):
        """The editor a format command goes to (None: the main editor, if a note is open)."""
        if editor is not None:
            return editor
        return self.note_pane.editor if self.note_pane.get_visible_child_name() == "editor" else None

    def paragraph(self, style, editor=None):
        if (target := self.format_target(editor)):
            target.apply_paragraph(style)
            target.grab_focus()

    def insert_divider(self, editor=None):
        if (target := self.format_target(editor)) and target.get_editable():
            target.insert_divider()
            target.grab_focus()

    def highlight(self, name, editor=None):
        if (target := self.format_target(editor)):
            target.set_highlight(name)
            target.grab_focus()

    def inline(self, name, editor=None):
        if (target := self.format_target(editor)):
            target.toggle_inline(name)

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
            menu.append("In eigenem Fenster öffnen", "win.note-window")
            menu.append("Lösen" if note["data"].get("pinned") else "Anheften", "win.pin-note")
            menu.append("Teilen …", "win.share-note")
            menu.append("Verschieben nach …", "win.move-note")
            menu.append("Duplizieren", "win.duplicate-note")
            menu.append("Als PDF exportieren …", "win.export-note")
            menu.append("Drucken …", "win.print-note")
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
        for window in list(self.note_windows):
            if window.locked:
                window.close()
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
            # Locking hides the content right away (and every other open locked note).
            self.lock_all()
            self.refresh_list_only()
            self.note_pane.show_locked(current["id"])
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

    def new_folder(self, parent_id=None):
        parent = self.sync.get(parent_id) if parent_id else None

        def create(name, _choice):
            data = {"name": name, "order": time.time()}
            if parent is not None:
                data["parent"] = parent["id"]
            # A subfolder lives where its parent lives (private or in the parent's share).
            folder = self.sync.put("folder", data, parent.get("share") if parent else None)
            if parent is not None:
                self.sidebar.collapsed.discard(parent["id"])
            self.sidebar.refresh()
            self.sidebar.select("folder:" + folder["id"])
        if parent is not None:
            ask_text(self, "Neuer Unterordner", create, placeholder="Name", action="Erstellen",
                     body=f"Neuer Ordner in „{parent['data'].get('name', 'Ordner')}“.")
        else:
            ask_text(self, "Neuer Ordner", create, placeholder="Name", action="Erstellen",
                     body="Neue Ordner sind privat. Mit Rechtsklick → „Teilen …“ kannst du sie freigeben.")

    def move_folder(self, folder_id):
        """Move a folder (into another folder or to the top) or a list/board into a
        folder (or out of it), like dragging in Notes."""
        folder = self.sync.get(folder_id)
        if folder is None or folder["kind"] not in ("folder", "list", "board"):
            return
        is_folder = folder["kind"] == "folder"
        blocked = (model.folder_descendants(self.sync, folder_id) | {folder_id}) if is_folder else set()
        targets = [f for f in self.sync.objects("folder") if f["id"] not in blocked]
        targets.sort(key=lambda f: (bool(f.get("share")), model.folder_path(self.sync, f).lower()))
        choices = [(None, "Oberste Ebene" if is_folder else "Kein Ordner")] + [
            (f["id"], model.folder_path(self.sync, f) + (" (geteilt)" if f.get("share") else "")) for f in targets]
        current = model.folder_parent(self.sync, folder) if is_folder else (folder["data"].get("folder") or None)
        choices = [choice for choice in choices if choice[0] != current]
        dialog = Adw.AlertDialog(heading=f"„{folder['data'].get('name', 'Ordner')}“ verschieben nach",
                                 body="In einem geteilten Ordner sehen alle, mit denen er geteilt ist, auch den Inhalt.")
        dropdown = Gtk.DropDown.new_from_strings([label for _id, label in choices])
        dialog.set_extra_child(dropdown)
        dialog.add_response("cancel", "Abbrechen")
        dialog.add_response("ok", "Verschieben")
        dialog.set_response_appearance("ok", Adw.ResponseAppearance.SUGGESTED)

        def on_response(_dialog, response):
            if response != "ok":
                return
            self.move_object_to(folder_id, choices[dropdown.get_selected()][0])

        dialog.connect("response", on_response)
        dialog.present(self)

    def target_folder(self, folder_id=None):
        """The folder a new list/board goes into: the given one, else the selected folder."""
        if folder_id is None and self.current_key.startswith("folder:"):
            folder_id = self.current_key.partition(":")[2]
        folder = self.sync.get(folder_id) if folder_id else None
        return folder if folder is not None and folder["kind"] == "folder" else None

    def new_list(self, folder_id=None):
        folder = self.target_folder(folder_id)

        def create(name, _choice):
            data = {"name": name, "grocery": True, "order": time.time()}
            if folder is not None:
                data["folder"] = folder["id"]
            shopping = self.sync.put("list", data, folder.get("share") if folder else None)
            self.sidebar.refresh()
            self.sidebar.select("list:" + shopping["id"])
        ask_text(self, "Neue Liste", create, placeholder="z. B. Drogerie", action="Erstellen")

    def new_board(self, folder_id=None):
        folder = self.target_folder(folder_id)

        def create(name, _choice):
            data = {"name": name, "order": time.time()}
            if folder is not None:
                data["folder"] = folder["id"]
            share = folder.get("share") if folder else None
            board = self.sync.put("board", data, share)
            for order, (_key, column) in enumerate(model.DEFAULT_COLUMNS):
                self.sync.put("column", {"board": board["id"], "name": column, "order": order}, share, notify=False)
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
        if kind == "folder":
            menu.append("Neuer Unterordner …", "win.new-subfolder")
            menu.append("Neue Liste hier …", "win.new-list-here")
            menu.append("Neues Board hier …", "win.new-board-here")
        if kind in ("folder", "list", "board"):
            menu.append("Verschieben nach …", "win.move-object")
        if kind == "board":
            menu.append("Bericht exportieren …", "win.export-object")
            menu.append("Entwicklungsprojekt ausschalten" if obj["data"].get("dev") else "Als Entwicklungsprojekt führen",
                        "win.toggle-dev")
        protected = object_id == model.default_private_folder(self.sync.user_id)
        if not protected:
            menu.append("Löschen …", "win.delete-object")
        self.popup_menu(menu, widget, x, y)

    def export_board(self, board_id):
        """Report of a board as PDF (or CSV for spreadsheets) – a traceability
        matrix for development projects."""
        board = self.sync.get(board_id)
        if board is None:
            return
        from . import report
        name = board["data"].get("name", "Board")
        dialog = Gtk.FileDialog(title="Bericht exportieren")
        dialog.set_initial_name(f"{name} – Stand {time.strftime('%Y-%m-%d')}.pdf")
        filters = Gio.ListStore.new(Gtk.FileFilter)
        for label, pattern in (("PDF-Bericht", "*.pdf"), ("Tabelle (CSV, z. B. für Excel)", "*.csv")):
            file_filter = Gtk.FileFilter(name=label)
            file_filter.add_pattern(pattern)
            filters.append(file_filter)
        dialog.set_filters(filters)

        def chosen(dialog, result):
            try:
                path = dialog.save_finish(result).get_path()
            except GLib.Error:
                return
            data = report.build(self.sync, board_id)
            if path.lower().endswith(".csv"):
                report.write_csv(data, path)
            else:
                path = path if path.lower().endswith(".pdf") else path + ".pdf"
                report.write_pdf(data, path)
            self.toast(f"Bericht gespeichert: {Path(path).name}")
        dialog.save(self, None, chosen)

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
            if kind == "folder":
                body = (f"„{name}“, seine Unterordner und ihre Notizen werden gelöscht (Notizen landen in "
                        "„Zuletzt gelöscht“). Listen und Boards darin bleiben erhalten – ohne Ordner.")

        def remove():
            if kind == "folder":
                # The folder, its subfolders and all their notes (notes go to "Zuletzt gelöscht").
                doomed = model.folder_descendants(self.sync, obj["id"]) | {obj["id"]}
                for note in self.sync.objects("note"):
                    if note["data"].get("folder") in doomed:
                        self.sync.update(note["id"], notify=False, trashed=time.time())
                for folder_id in doomed - {obj["id"]}:
                    self.sync.delete(folder_id, notify=False)
                # Lists and boards have no trash: they stay, just without a folder.
                for item in self.sync.objects("list") + self.sync.objects("board"):
                    if item["data"].get("folder") in doomed:
                        self.sync.update(item["id"], notify=False, folder=None)
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
        for window in list(self.note_windows):
            window.on_sync_changed(ids)
        order = self.sync.settings().get("note_sort", "modified")
        if self.sort_action.get_state().get_string() != order:
            self.sort_action.set_state(GLib.Variant.new_string(order))
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
            "export-note": self.export_note,
            "print-note": self.print_note,
            "note-window": lambda: self.open_note_window(),
            "shortcuts": lambda: self.show_shortcuts(),
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
            "new-subfolder": lambda: self.new_folder(getattr(self, "menu_target", None)),
            "new-list-here": lambda: self.new_list(getattr(self, "menu_target", None)),
            "new-board-here": lambda: self.new_board(getattr(self, "menu_target", None)),
            "move-object": lambda: self.move_folder(getattr(self, "menu_target", "")),
            "export-object": lambda: self.export_board(getattr(self, "menu_target", "")),
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
        self.text_size_action = Gio.SimpleAction.new_stateful(
            "text-size", GLib.VariantType.new("s"), GLib.Variant.new_string(str(textsize.load())))
        self.text_size_action.connect("activate", lambda _action, value: self.set_text_size(int(value.get_string())))
        self.add_action(self.text_size_action)
        textsize.apply(textsize.load())
        current = self.sync.settings().get("note_sort", "modified")
        self.sort_action = Gio.SimpleAction.new_stateful("sort-notes", GLib.VariantType.new("s"), GLib.Variant.new_string(current))
        self.sort_action.connect("activate", lambda action, value: self.sort_notes(value.get_string()))
        self.add_action(self.sort_action)

    def show_shortcuts(self):
        from .shortcuts import shortcuts_dialog
        shortcuts_dialog().present(self)

    def set_text_size(self, level):
        level = max(0, min(len(textsize.SIZES) - 1, level))
        textsize.save(level)
        textsize.apply(level)
        self.text_size_action.set_state(GLib.Variant.new_string(str(level)))

    def change_text_size(self, step):
        """Ctrl+Plus / Ctrl+Minus (step 0: back to normal)."""
        current = int(self.text_size_action.get_state().get_string())
        self.set_text_size(current + step if step else textsize.NORMAL)

    def sort_notes(self, order):
        self.sort_action.set_state(GLib.Variant.new_string(order))
        if self.sync.settings().get("note_sort", "modified") != order:
            self.sync.update_settings(note_sort=order)
        self.show_notes()

    def on_key(self, controller, keyval, keycode, state):
        control = bool(state & Gdk.ModifierType.CONTROL_MASK)
        if not control:
            return False
        shift = bool(state & Gdk.ModifierType.SHIFT_MASK)
        alt = bool(state & Gdk.ModifierType.ALT_MASK)
        key = Gdk.keyval_to_lower(keyval)
        text_size = text_size_step(keyval)
        if text_size is not None:
            self.change_text_size(text_size)
            return True
        if keyval == Gdk.KEY_question:
            self.show_shortcuts()
            return True
        if key == Gdk.KEY_o and not shift:
            self.open_note_window()
            return True
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
