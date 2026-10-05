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
from . import smoothscroll
from .dialogs import ask_password, ask_text, confirm, error_text, run_async
from . import activity, audio, linkpreview, security_ui, textsize, uiprefs, uploads
from .icons import Icon, icon_button, icon_menu_button
from .kanban import BoardView
from .lists import ShoppingListView
from .notes import NoteList, NotePane
from .sidebar import Sidebar
from . import sync as sync_module
from .sync import device_name
from .i18n import _


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


MAX_ATTACHMENT = 24 * 1024 * 1024  # the server takes 25 MB including encryption

HIGHLIGHT_MENU = [("h", _("Gelb")), ("h:orange", _("Orange")), ("h:pink", _("Pink")), ("h:purple", _("Lila")),
                  ("h:mint", _("Mint")), ("h:blue", _("Blau")), (None, _("Markierung entfernen"))]

TEXT_COLOR_MENU = [("c:purple", _("Lila")), ("c:pink", _("Pink")), ("c:orange", _("Orange")), ("c:mint", _("Mint")),
                   ("c:blue", _("Blau")), (None, _("Standardfarbe"))]

PARAGRAPH_MENU = [
    ("title", _("Titel"), "<Control><Shift>t"),
    ("heading", _("Überschrift"), "<Control><Shift>h"),
    ("subheading", _("Unterüberschrift"), "<Control><Shift>j"),
    ("body", _("Text"), "<Control><Shift>b"),
    ("mono", _("Monospace"), "<Control><Shift>m"),
    ("bullet", _("• Aufzählung"), "<Control><Shift>7"),
    ("dash", _("– Liste mit Strichen"), "<Control><Shift>8"),
    ("number", _("1. Nummerierte Liste"), "<Control><Shift>9"),
    ("check", _("Checkliste"), "<Control><Shift>l"),
    ("quote", _("Zitat"), "<Control>apostrophe"),
]


class LiNotesWindow(Adw.ApplicationWindow):

    def __init__(self, app, sync):
        super().__init__(application=app)
        self.sync = sync
        self.set_default_size(1180, 760)
        self.set_title(_("LiNotes"))
        self.vault_key = None
        self.vault_used = 0
        self.current_key = "all"
        self.current_note = None
        # A note made here that is still empty is dropped when it is left (like Apple).
        self.fresh_note = None
        self.editing_blocks = None
        self.note_windows = set()

        self.toasts = Adw.ToastOverlay()
        self.set_content(self.toasts)
        self.pages = Gtk.Stack(transition_type=Gtk.StackTransitionType.CROSSFADE)
        # Running uploads float at the bottom, the window stays usable meanwhile.
        overlay = Gtk.Overlay(child=self.pages)
        self.uploads_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10, halign=Gtk.Align.CENTER,
                                   valign=Gtk.Align.END, margin_bottom=72, visible=False, css_classes=["upload-card"])
        self.uploads_box.set_size_request(360, -1)
        overlay.add_overlay(self.uploads_box)
        self.toasts.set_child(overlay)

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
        self.split = Adw.OverlaySplitView(min_sidebar_width=210, max_sidebar_width=300)

        sidebar_view = Adw.ToolbarView()
        sidebar_header = Adw.HeaderBar(show_title=False, show_end_title_buttons=False)
        sidebar_header.set_decoration_layout(DECORATION_LAYOUT)
        new_menu = Gio.Menu()
        new_menu.append(_("Neue Notiz aus Vorlage …"), "win.new-from-template")
        new_menu.append(_("Neuer Ordner"), "win.new-folder")
        new_menu.append(_("Neue Liste"), "win.new-list")
        new_menu.append(_("Neues Board"), "win.new-board")
        new_menu.append(_("Neuer Plan …"), "win.new-plan")
        self.new_menu = new_menu
        new_button = icon_menu_button("plus", _("Neu …"))
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
        toggle = icon_button("sidebar", _("Seitenleiste"), toggle=True)
        self.split.bind_property("show-sidebar", toggle, "active",
                                 GObject.BindingFlags.SYNC_CREATE | GObject.BindingFlags.BIDIRECTIONAL)
        header.pack_start(toggle)
        # Narrow windows show list and note one after the other; this leads back to the list.
        self.back_button = icon_button("back", _("Zurück zur Liste"))
        self.back_button.set_visible(False)
        self.back_button.connect("clicked", lambda _button: self.show_list_narrow())
        header.pack_start(self.back_button)

        self.view_toggle = Gtk.Box()
        self.view_toggle.add_css_class("linked")
        self.list_mode = icon_button("list", _("Liste (Strg+1)"), toggle=True)
        self.gallery_mode = icon_button("gallery", _("Galerie (Strg+2)"), toggle=True)
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
        sort_menu.append_section(_("Notizen sortieren nach"), section)
        # Like Apple's default text size: per device, Ctrl+Plus/Minus/0.
        sizes = Gio.Menu()
        for level, (_factor, label) in enumerate(textsize.SIZES):
            sizes.append(label, f"win.text-size::{level}")
        sort_menu.append_section(_("Textgröße (Strg + / Strg −)"), sizes)
        layout = Gio.Menu()
        layout.append(_("Blocksatz"), "win.justify")
        # Off by default: a preview means fetching the page, the site then sees this computer's address.
        layout.append(_("Link-Vorschau (Webseite abrufen)"), "win.link-previews")
        # Off by default ("Tante Erna" first): code colors, footnotes … only when switched on (all devices).
        layout.append(_("Profi-Funktionen"), "win.pro-features")
        sort_menu.append_section(None, layout)
        # Language: like the system, or chosen here (takes effect at the next start).
        from . import i18n
        languages = Gio.Menu()
        languages.append(_("Wie das System"), "win.language::system")
        for code, name in i18n.LANGUAGES.items():
            languages.append(name, f"win.language::{code}")
        sort_menu.append_submenu(_("Sprache"), languages)
        self.sort_button = icon_menu_button("more", _("Sortieren und Darstellung"), Gtk.PopoverMenu.new_from_model(sort_menu))
        header.pack_start(self.sort_button)
        self.delete_button = icon_button("trash", _("Löschen"))
        self.delete_button.set_action_name("win.delete-note")
        header.pack_start(self.delete_button)

        self.note_tools = Gtk.Box(spacing=4)
        compose = icon_button("compose", _("Neue Notiz (Strg+N)"))
        compose.set_action_name("win.new-note")
        self.note_tools.append(compose)
        self.format_button = icon_menu_button("format", _("Format"), self.build_format_popover())
        self.note_tools.append(self.format_button)
        checklist = icon_button("checklist", _("Checkliste (Strg+Shift+L)"))
        checklist.connect("clicked", lambda _button: self.paragraph("check"))
        self.note_tools.append(checklist)
        table = icon_button("table", _("Tabelle einfügen"))
        table.set_action_name("win.insert-table")
        self.note_tools.append(table)
        photo = icon_button("photo", _("Foto einfügen"))
        photo.set_action_name("win.insert-photo")
        self.note_tools.append(photo)
        attach = Gtk.Button(icon_name="mail-attachment-symbolic", tooltip_text=_("Datei anhängen (PDF, Dokument …)"))
        attach.set_action_name("win.attach-file")
        self.note_tools.append(attach)
        record = Gtk.Button(icon_name="audio-input-microphone-symbolic", tooltip_text=_("Audio aufnehmen"))
        record.set_action_name("win.record-audio")
        self.note_tools.append(record)
        self.lock_button = icon_button("lock", _("Notiz sperren"))
        self.lock_button.set_action_name("win.lock-button")
        self.note_tools.append(self.lock_button)
        self.share_button = icon_button("share", _("Notiz teilen …"))
        self.share_button.set_action_name("win.share-note")
        self.note_tools.append(self.share_button)
        header.pack_end(self.note_tools)
        content.add_top_bar(header)
        # A friendly reminder after a few days of use – never at the first start.
        self.keyfile_banner = Adw.Banner(title=_("Sichere dein Konto mit einer Schlüsseldatei – falls ein Gerät verloren geht."),
                                         button_label=_("Jetzt sichern"))
        self.keyfile_banner.connect("button-clicked", lambda _b: (self.keyfile_banner.set_revealed(False),
                                                                  security_ui.KeyfileDialog(self).present(self)))
        content.add_top_bar(self.keyfile_banner)

        self.stack = Gtk.Stack(transition_type=Gtk.StackTransitionType.CROSSFADE)
        paned = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL, shrink_start_child=False)
        self.note_list = NoteList(self.sync)
        self.note_list.set_size_request(280, -1)
        self.note_list.connect("note-selected", lambda _list, note_id: (self.open_note(note_id), self.show_note_narrow()))
        self.note_list.connect("context", self.on_note_context)
        self.note_list.is_unread = lambda note: activity.unread(note, self.sync.user_id)
        self.note_list.connect("open-window", lambda _list, note_id: self.open_note_window(note_id))
        self.note_list.connect("open-key", lambda _list, key: self.sidebar.select(key) or self.select(key))
        self.note_list.search.connect("search-changed", lambda _entry: self.show_notes())
        self.note_pane = NotePane(self.sync)
        self.note_pane.editor.connect("edited", lambda _editor: self.save_current())
        self.note_pane.editor.note_title = self.link_title
        self.note_pane.editor.user_name = self.mention_name
        self.note_pane.editor.mention_people = lambda: self.mention_people(self.current_note)
        self.note_pane.editor.connect("link-requested", lambda _editor: self.show_link_choice())
        self.note_pane.editor.connect("open-note", lambda _editor, note_id: self.open_linked_note(note_id))
        self.note_pane.editor.connect("open-file", lambda _editor, block: self.open_attachment(block, self.note_pane.image_share))
        self.note_pane.editor.connect("link-line", lambda editor, url: self.make_link_preview(editor, self.current_note, url))
        # Drop files from the file manager into the note (like Apple): photos as photos, the rest attached.
        drop = Gtk.DropTarget.new(Gio.File, Gdk.DragAction.COPY)
        drop.connect("drop", lambda _target, file, _x, _y: self.drop_file(file))
        self.note_pane.editor.add_controller(drop)
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
        from .plan_view import PlanView
        self.plan_view = PlanView(self)
        self.stack.add_named(self.plan_view, "plan")
        content.set_content(self.stack)
        self.split.set_content(content)
        self.pages.add_named(self.split, "main")
        self.build_breakpoints()

        keys = Gtk.EventControllerKey()
        keys.connect("key-pressed", self.on_key)
        self.add_controller(keys)
        self.connect("close-request", lambda _window: self.drop_fresh_note() or False)
        vault_activity = Gtk.EventControllerKey()
        vault_activity.connect("key-pressed", lambda *_args: self.touch_vault() or False)
        self.add_controller(vault_activity)

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
            button.set_tooltip_text({"b": _("Fett"), "i": _("Kursiv"), "u": _("Unterstrichen"), "s": _("Durchgestrichen")}[key])
            button.connect("clicked", lambda _button, name=key: self.inline(name, editor))
            inline.append(button)
        box.append(inline)
        # Highlight colors like in Apple's Notes; a click on the active color removes it again.
        colors = Gtk.Box(spacing=6, margin_top=6, margin_start=4)
        colors.append(Gtk.Label(label=_("Markieren"), xalign=0, hexpand=True))
        for name, tooltip in HIGHLIGHT_MENU:
            swatch = Gtk.Button(tooltip_text=tooltip)
            swatch.add_css_class("highlight-swatch")
            swatch.add_css_class("swatch-" + (name.partition(":")[2] or "yellow") if name else "swatch-none")
            if not name:
                swatch.set_label("✕")
            swatch.connect("clicked", lambda _button, color=name: self.highlight(color, editor))
            colors.append(swatch)
        box.append(colors)
        # Text color, font and alignment (like Format → Font / Text in Notes).
        text_colors = Gtk.Box(spacing=6, margin_top=6, margin_start=4)
        text_colors.append(Gtk.Label(label=_("Textfarbe"), xalign=0, hexpand=True))
        for name, tooltip in TEXT_COLOR_MENU:
            swatch = Gtk.Button(tooltip_text=tooltip)
            swatch.add_css_class("highlight-swatch")
            swatch.add_css_class("text-" + name.partition(":")[2] if name else "swatch-none")
            if name:
                swatch.set_label("A")
            else:
                swatch.set_label("✕")
            swatch.connect("clicked", lambda _button, color=name: self.text_color(color, editor))
            text_colors.append(swatch)
        box.append(text_colors)
        fonts = Gtk.Box(homogeneous=True, margin_top=6)
        fonts.add_css_class("linked")
        for name, label, css in ((None, _("Standard"), None), ("f:serif", _("Serif"), "font-serif"), ("f:mono", _("Mono"), "monospace")):
            button = Gtk.Button(label=label, tooltip_text=_("Schrift: ") + label)
            if css:
                button.add_css_class(css)
            button.connect("clicked", lambda _button, font=name: self.font(font, editor))
            fonts.append(button)
        box.append(fonts)
        aligns = Gtk.Box(homogeneous=True, margin_top=6)
        aligns.add_css_class("linked")
        for name, icon, tooltip in ((None, "format-justify-left-symbolic", _("Linksbündig")),
                                    ("center", "format-justify-center-symbolic", _("Zentriert")),
                                    ("right", "format-justify-right-symbolic", _("Rechtsbündig"))):
            button = Gtk.Button(icon_name=icon, tooltip_text=tooltip)
            button.connect("clicked", lambda _button, align=name: self.align(align, editor))
            aligns.append(button)
        box.append(aligns)
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
        line.append(Gtk.Label(label=_("Trennlinie"), xalign=0, hexpand=True))
        hint = Gtk.Label(label="--- ↵")
        hint.add_css_class("dim-label")
        line.append(hint)
        divider.set_child(line)
        divider.set_tooltip_text(_("Oder auf einer leeren Zeile --- tippen und Enter drücken"))
        divider.connect("clicked", lambda _button: (popover.popdown(), self.insert_divider(editor)))
        box.append(divider)
        # Profi-Funktionen: only shown when switched on (Tante Erna sees a calm menu).
        pro = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        code_row = Gtk.Box(spacing=6, margin_start=10, margin_top=2)
        code_row.append(Gtk.Label(label=_("Code"), xalign=0, hexpand=True, css_classes=["monospace"]))
        languages = Gtk.Box(css_classes=["linked"])
        from . import syntax
        for lang, label in syntax.LANGUAGES.items():
            button = Gtk.Button(label=label, tooltip_text=_("Markierte Zeilen als {label}-Code mit Syntaxfarben", label=label))
            button.connect("clicked", lambda _b, lang=lang: (popover.popdown(), (editor or self.note_pane.editor).make_code(lang)))
            languages.append(button)
        code_row.append(languages)
        pro.append(code_row)
        footnote = Gtk.Button(css_classes=["flat"], tooltip_text=_("Hochgestellte Nummer an der Cursorstelle, der Text steht unter der Notiz"))
        footnote_line = Gtk.Box(spacing=16)
        footnote_line.append(Gtk.Label(label=_("Fußnote / Quelle …"), xalign=0, hexpand=True))
        footnote.set_child(footnote_line)
        footnote.connect("clicked", lambda _b: (popover.popdown(), self.ask_footnote(editor or self.note_pane.editor)))
        pro.append(footnote)
        formula = Gtk.Button(css_classes=["flat"], tooltip_text=_("Mathematische Formel in LaTeX-Schreibweise, z. B. \\frac{a}{b}"))
        formula_line = Gtk.Box(spacing=16)
        formula_line.append(Gtk.Label(label=_("Formel (LaTeX) …"), xalign=0, hexpand=True))
        formula.set_child(formula_line)
        formula.connect("clicked", lambda _b: (popover.popdown(), self.insert_math(editor)))
        pro.append(formula)
        box.append(pro)
        popover.connect("show", lambda _p: pro.set_visible(self.pro_features()))
        box.append(Gtk.Separator(margin_top=4, margin_bottom=4))
        sort_checked = Gtk.CheckButton(label=_("Abgehakte Objekte nach unten sortieren"))
        sort_checked.connect("toggled", lambda button: setattr(editor or self.note_pane.editor, "auto_sort_checked", button.get_active()))
        box.append(sort_checked)
        if editor is None:
            self.sort_checked = sort_checked
        popover.set_child(box)
        return popover

    def add_upload(self, upload):
        from .uploads import UploadRow
        self.uploads_box.append(UploadRow(upload))
        self.uploads_box.set_visible(True)

    def remove_upload(self, upload):
        child = self.uploads_box.get_first_child()
        while child is not None:
            following = child.get_next_sibling()
            if child.upload is upload:
                child.detach()
                self.uploads_box.remove(child)
            child = following
        self.uploads_box.set_visible(self.uploads_box.get_first_child() is not None)

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
                    self.toast(_("Dieses Konto hat schon ein Notizen-Passwort. Entferne zuerst die Sperre deiner gesperrten Notizen."))
                    return
                if error is not None:
                    self.toast(_("Verbinden fehlgeschlagen: {error_text}", error_text=error_text(error)))
                    return
                login.set_connecting(False)
                self.vault_key = None
                self.enter_main()
                self.toast(_("Mit dem Server verbunden – deine Notizen werden hochgeladen."))
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
            self.toast(_("Dafür brauchst du einen Server – Kontomenü → „Mit Server verbinden …“"))
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
                self.toast(_("Offline – Änderungen werden später übertragen."))
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
            self.toast(_("Dieses Gerät wurde abgemeldet."))
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
            confirm(self, _("Alle Daten löschen?"),
                    _("Alle Notizen, Listen und Aufgaben auf diesem Computer werden endgültig gelöscht."), _("Löschen"), really)
            return
        confirm(self, _("Dieses Gerät abmelden?"),
                _("Die Notizen bleiben auf dem Server. Zum erneuten Anmelden brauchst du ein anderes Gerät oder deine Schlüsseldatei."),
                _("Abmelden"), really)

    def invite(self):
        def done(code, error):
            if error is not None:
                self.toast(error_text(error))
                return
            dialog = Adw.AlertDialog(
                heading=_("Einladungscode"),
                body=_("Mit diesem Code kann einmalig ein neues Konto erstellt werden:\n\n{code}\n\nServer: {server}\nIn der App „Neues Konto erstellen“ wählen.", code=code, server=self.sync.server),
            )
            dialog.add_response("copy", _("Kopieren"))
            dialog.add_response("ok", _("Fertig"))
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
        self.pro_features()  # the menu check follows the account setting (other devices)
        self.sidebar.refresh()
        self.select(self.current_key, keep_note=True)

    def select(self, key, keep_note=False):
        if key != self.current_key:
            self.narrow_note = False
        self.current_key = key
        kind, _sep, object_id = key.partition(":")
        if kind in ("list", "board", "plan") and self.sync.get(object_id):
            self.note_pane.editor.flush()
            self.drop_fresh_note()
        if self.stack.get_visible_child_name() == "plan":
            self.plan_view.flush()
        if kind == "plan" and self.sync.get(object_id):
            self.plan_view.show(object_id)
            self.stack.set_visible_child_name("plan")
            self.show_note_tools(False)
            return
        if kind == "list" and self.sync.get(object_id):
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
            return [n for n in notes if n["data"].get("trashed")], _("Zuletzt gelöscht")
        notes = [n for n in notes if not n["data"].get("trashed")]
        if key == "archive":
            return [n for n in notes if model.archived(n)], _("Archiv")
        if not getattr(self, "searching_archive", False):
            notes = [n for n in notes if not model.archived(n)]
        if key == "locked":
            return [n for n in notes if n["data"].get("enc")], _("Gesperrt")
        if key == "shared-notes":
            return [n for n in notes if n.get("share") and not self.sync.get(n["data"].get("folder") or "")], _("Mit mir geteilt")
        if kind == "folder":
            folder = self.sync.get(object_id)
            name = folder["data"].get("name", "Ordner") if folder else _("Ordner")
            return [n for n in notes if n["data"].get("folder") == object_id], name
        return notes, _("Alle Notizen")

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
                            sum(1 for n in live if n["data"].get("folder") == folder["id"]), _("Ordner")))
        items = sync.objects("item")
        for shopping in sorted((l for l in sync.objects("list") if l["data"].get("folder") == folder_id and not model.archived(l)),
                               key=lambda l: l["data"].get("name", "").lower()):
            entries.append(("list:" + shopping["id"], "cart", shopping["data"].get("name", "Liste"),
                            sum(1 for i in items if i["data"].get("list") == shopping["id"] and not i["data"].get("done")), _("Listen")))
        cards = sync.objects("card")
        for board in sorted((b for b in sync.objects("board") if b["data"].get("folder") == folder_id and not model.archived(b)),
                            key=lambda b: b["data"].get("name", "").lower()):
            entries.append(("board:" + board["id"], "board", board["data"].get("name", "Board"),
                            sum(1 for c in cards if c["data"].get("board") == board["id"] and not c["data"].get("archived")), _("Boards")))
        return entries

    def show_notes(self, keep_note=True):
        # A search also finds what is in the archive (marked "im Archiv" in the list).
        self.searching_archive = bool(self.note_list.search.get_text().strip())
        notes, title = self.notes_for(self.current_key)
        self.searching_archive = False
        tags = self.sidebar.active_tags
        if tags:
            notes = [n for n in notes if tags <= model.note_tags(n)]
            title += " · " + " ".join("#" + tag for tag in sorted(tags))
        query = self.note_list.search.get_text().strip().lower()
        if query:
            notes = [n for n in notes if query in model.note_text(n).lower()
                     or query in model.note_title(n).lower()]
            title = _("Suche: {query}", query=query)
        selected = self.current_note if keep_note else None
        if selected and selected not in {n["id"] for n in notes}:
            selected = None
        self.note_list.show(title, notes, selected, _("Keine Treffer") if query else _("Keine Notizen"))
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
        self.drop_fresh_note()
        self.current_note = note["id"]
        self.fresh_note = note["id"]
        self.sidebar.refresh()
        self.show_notes()
        self.open_note(note["id"])
        self.show_note_narrow()
        self.note_pane.editor.grab_focus()

    def open_note(self, note_id):
        if note_id != self.current_note:
            self.note_pane.editor.flush()
        if note_id != self.fresh_note and self.fresh_note is not None:
            self.drop_fresh_note(refresh=True)
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
            self.toast(_("Diese Notiz konnte nicht entschlüsselt werden."))
            self.note_pane.show_locked(note_id)
            return
        self.editing_blocks = blocks
        was_unread = activity.unread(note, self.sync.user_id)
        changes = activity.changes(note, blocks, self.sync.user_id)
        self.note_pane.show_note(note, blocks, editable=not note["data"].get("trashed"))
        if changes:
            self.note_pane.show_changes(changes, self.sync.user_name(note["updated_by"]), model.modified(note))
        activity.remember(note, blocks)
        if was_unread:
            GLib.idle_add(lambda: self.refresh_list_only() and False)  # the dot goes away
        self.update_note_actions()

    def drop_fresh_note(self, refresh=False):
        """Delete the note made here if it is still empty now that it is left (Apple does the same:
        no stray "Neue Notiz"). Notes that were empty before are never touched."""
        note_id, self.fresh_note = self.fresh_note, None
        if note_id is None:
            return
        self.note_pane.editor.flush()
        note = self.sync.get(note_id)
        if note is None or note["data"].get("trashed") or note["data"].get("enc"):
            return
        if not model.is_empty_body(model.note_blocks(note)):
            return
        self.sync.delete(note_id)
        if self.current_note == note_id:
            self.current_note = None
        if refresh:
            GLib.idle_add(lambda: (self.sidebar.refresh(), self.refresh_list_only()) and False)
        else:
            self.sidebar.refresh()

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
        popover.set_child(smoothscroll.enable(Gtk.ScrolledWindow(child=listbox, propagate_natural_height=True, propagate_natural_width=True,
                                             max_content_height=320, hscrollbar_policy=Gtk.PolicyType.NEVER)))
        listbox.set_size_request(300, -1)
        popover.set_parent(editor)
        found = []

        mention = editor.link_kind == "mention"

        def close(choice=None):
            editor.link_keys = None
            editor.buffer.disconnect(handler)
            popover.popdown()
            popover.unparent()
            editor.finish_link(choice[0] if choice else None, choice[1] if choice else None)

        def fill():
            query = editor.pending_link_query()
            if query is None or len(query) > 60:
                GLib.idle_add(lambda: close() and False)
                return
            if mention:
                found[:] = [(uid, name, "") for uid, name in editor.mention_people() if query.lower() in name.lower()]
            else:
                found[:] = [(note["id"], model.note_title(note),
                             (self.sync.get(note["data"].get("folder") or "") or {}).get("data", {}).get("name", ""))
                            for note in model.link_choices(self.sync.objects("note"), exclude=exclude, query=query)]
            while (row := listbox.get_row_at_index(0)) is not None:
                listbox.remove(row)
            for _id, title, place_name in found:
                box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, margin_top=4, margin_bottom=4)
                box.append(Gtk.Label(label=("@" if mention else "") + title, xalign=0, ellipsize=Pango.EllipsizeMode.END))
                if place_name:
                    place = Gtk.Label(label=place_name, xalign=0)
                    place.add_css_class("dim-label")
                    place.add_css_class("caption")
                    box.append(place)
                listbox.append(box)
            if not found:
                listbox.append(Gtk.Label(label=_("Keine passende Person") if mention else _("Keine passende Notiz"),
                                         margin_top=6, margin_bottom=6, sensitive=False))
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

    def notify_mentions(self, ids):
        """Someone @-mentioned me in a shared note: a system notification (once per mention),
        a click opens the note."""
        me = self.sync.user_id
        seen = uiprefs.get("mentions_seen", {})
        changed = False
        for note_id in ids:
            note = self.sync.get(note_id)
            if note is None or not note.get("share") or note["data"].get("enc") or note["data"].get("trashed"):
                continue
            count = model.mentions_of(model.note_blocks(note), me)
            known = seen.get(note_id, 0)
            if count != known:
                seen[note_id] = count
                changed = True
            if count > known and note.get("updated_by") not in (None, 0, me):
                notification = Gio.Notification.new(f"{self.sync.user_name(note['updated_by'])} hat dich erwähnt")
                notification.set_body(_("in „{note_title}“", note_title=model.note_title(note)))
                notification.set_default_action_and_target("app.open-note", GLib.Variant.new_string(note_id))
                self.get_application().send_notification(f"mention-{note_id}", notification)
        if changed:
            uiprefs.put("mentions_seen", seen)

    def mention_name(self, user_id):
        name = self.sync.user_name(user_id)
        return None if name == "?" else name

    def mention_people(self, note_id):
        """Whom one can @-mention in a note: the people it is shared with (like Apple)."""
        note = self.sync.get(note_id) if note_id else None
        if note is None or not note.get("share"):
            return []
        return [(uid, self.sync.user_name(uid)) for uid in self.sync.share_members(note["share"]) if uid != self.sync.user_id]

    def open_linked_note(self, note_id):
        note = self.sync.get(note_id)
        if note is None or note["data"].get("trashed"):
            self.toast(_("Die verlinkte Notiz gibt es nicht mehr."))
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
        activity.remember(self.sync.get(note_id), blocks)
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
        for name in ("delete-note", "toggle-lock", "lock-button", "move-note", "pin-note", "duplicate-note", "insert-photo", "insert-table", "attach-file",
                     "export-note", "print-note"):
            self.lookup_action(name).set_enabled(has)
        if has:
            locked = bool(note["data"].get("enc"))
            # Like Apple: the open lock in an unlocked note locks it again right away.
            unlocked = locked and self.vault_key is not None
            self.lock_button.get_child().name = "lock-open" if unlocked else "lock"
            self.lock_button.set_tooltip_text(_("Jetzt sperren") if unlocked else _("Entsperren") if locked else _("Notiz sperren"))
            self.lock_button.get_child().queue_draw()
            self.lookup_action("insert-photo").set_enabled(not locked and not note["data"].get("trashed"))
            self.lookup_action("attach-file").set_enabled(not locked and not note["data"].get("trashed"))
            # A locked note can only be exported or printed while it is open.
            for name in ("export-note", "print-note"):
                self.lookup_action(name).set_enabled(not locked or unlocked)

    def delete_note(self, note_id=None):
        note_id = note_id or self.current_note
        note = self.sync.get(note_id)
        if note is None:
            return
        if note["data"].get("trashed"):
            confirm(self, _("Endgültig löschen?"), _("Die Notiz wird auf allen Geräten gelöscht."), _("Löschen"),
                    lambda: (self.sync.delete(note_id), self.after_delete()))
            return
        self.sync.update(note_id, trashed=time.time())
        self.after_delete()
        self.toast(_("In „Zuletzt gelöscht“ verschoben"))

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
        self.toast(_("Notiz wiederhergestellt"))
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
        title = model.blocks_title(blocks) or _("Notiz")
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
        dialog = Gtk.FileDialog(title=_("Als PDF exportieren"))
        dialog.set_initial_name(f"{safe}.pdf")

        def chosen(dialog, result):
            try:
                path = dialog.save_finish(result).get_path()
            except GLib.Error:
                return
            path = path if path.lower().endswith(".pdf") else path + ".pdf"
            self.write_note_pdf(path)
            self.toast(_("PDF gespeichert: {name}", name=Path(path).name))
        dialog.save(self, None, chosen)

    def print_note(self):
        """The usual print dialog; the note goes to the printer as PDF."""
        if self.note_for_print() is None:
            return
        folder = Path(tempfile.mkdtemp(prefix="linotes-print-"))
        path = str(folder / "notiz.pdf")
        title = self.write_note_pdf(path)
        dialog = Gtk.PrintUnixDialog(title=_("Drucken"), transient_for=self, modal=True)
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
                self.toast(_("Dieser Drucker nimmt kein PDF an – bitte als PDF exportieren und von dort drucken."))
                finished()
                return
            job = Gtk.PrintJob.new(title, printer, settings, setup)
            try:
                job.set_source_file(path)
            except GLib.Error as error:
                self.toast(_("Drucken nicht möglich: {message}", message=error.message))
                finished()
                return
            job.send(lambda _job, error: (finished(), error and self.toast(_("Drucken fehlgeschlagen: {message}", message=error.message))))
            self.toast(_("„{title}“ wird gedruckt.", title=title))
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
        dialog = Adw.AlertDialog(heading=_("Verschieben nach"),
                                 body=_("Notizen in geteilten Ordnern sehen alle, mit denen der Ordner geteilt ist."))
        dropdown = Gtk.DropDown.new_from_strings([label for _id, label in choices])
        dialog.set_extra_child(dropdown)
        dialog.add_response("cancel", _("Abbrechen"))
        dialog.add_response("ok", _("Verschieben"))
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
            self.toast(_("Gesperrte Notizen können nicht geteilt werden. Entferne zuerst die Sperre."))
            return
        if share != note.get("share") and note["owner"] != self.sync.user_id:
            self.toast(_("Nur wer die Notiz erstellt hat, kann sie in einen anderen Bereich verschieben."))
            return

        def move():
            current = self.sync.get(note_id)
            data = self.sync.rekey_files(current, share) if share != current.get("share") else dict(current["data"])
            data["folder"] = folder["id"]
            self.sync.put("note", data, share, current["id"], notify=False)
            self.sync.emit_from_thread({note_id})

        run_async(move, lambda _r, error: (self.toast(_("Verschieben fehlgeschlagen: {error}", error=error)) if error
                                           else self.toast(_("Nach „{name}“ verschoben", name=folder['data'].get('name'))),
                                           self.refresh_list_only()))

    def move_object_to(self, object_id, folder_id):
        """Move a folder, list or board into a folder (None = top / no folder) – dialog or drag and drop."""
        obj = self.sync.get(object_id)
        if obj is None:
            return
        if obj["kind"] == "folder" and folder_id and folder_id in (model.folder_descendants(self.sync, object_id) | {object_id}):
            self.toast(_("Ein Ordner kann nicht in sich selbst liegen."))
            return
        field = "parent" if obj["kind"] == "folder" else "folder"
        if (obj["data"].get(field) or None) == folder_id:
            return
        if self.sync.share_after_move(obj, folder_id) != obj.get("share") and obj["owner"] != self.sync.user_id:
            self.toast(_("Nur wer es erstellt hat, kann es in einen anderen Bereich verschieben."))
            return
        if folder_id:
            self.sidebar.collapsed.discard(folder_id)
        # Into or out of a shared folder everything inside is re-encrypted – may take a moment.
        run_async(lambda: self.sync.move_to_folder(object_id, folder_id),
                  lambda _result, error: (self.toast(_("Verschieben fehlgeschlagen: {error}", error=error)) if error else self.toast(_("Verschoben")),
                                          self.refresh_all()))

    def drop_on(self, target, payload):
        """Drag and drop onto the sidebar. target: "folder:<id>" or a section ("Notizen",
        "Listen", "Aufgaben" = take out of its folder). payload: "<kind>:<id>"."""
        kind, _sep, object_id = payload.partition(":")
        if target.startswith("folder:"):
            folder_id = target.partition(":")[2]
            if kind == "note":
                self.move_note_to(object_id, folder_id)
            elif kind in ("folder", "list", "board", "plan"):
                self.move_object_to(object_id, folder_id)
            return True
        section_kinds = {"Notizen": "folder", "Listen": "list", "Aufgaben": "board", "Pläne": "plan"}
        if section_kinds.get(target) == kind:
            self.move_object_to(object_id, None)
            return True
        return False

    def insert_photo(self):
        note = self.sync.get(self.current_note)
        if note is None or note["data"].get("enc"):
            return
        dialog = Gtk.FileDialog(title=_("Foto einfügen"))
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
                self.deliver_upload(note["id"], self.note_pane.editor, {"t": "image", "f": file_id})
            uploads.start(self, path.name, content, note.get("share"), done)

        dialog.open(self, None, chosen)

    def attach_file(self, editor=None, note_id=None):
        """Like Apple: attach a PDF or any other file; it is encrypted like photos."""
        editor = editor or self.note_pane.editor
        note = self.sync.get(note_id or self.current_note) if (note_id or self.current_note) else None
        if note is None or note["data"].get("enc"):
            return
        dialog = Gtk.FileDialog(title=_("Datei anhängen"))

        def chosen(dialog, result):
            try:
                file = dialog.open_finish(result)
            except GLib.Error:
                return
            self.attach_path(Path(file.get_path()), editor, note)

        dialog.open(self, None, chosen)

    def attach_path(self, path, editor, note):
        size = path.stat().st_size
        if size > MAX_ATTACHMENT:
            self.toast(_("„{name}“ ist zu groß (höchstens {value} MB).", name=path.name, value=MAX_ATTACHMENT // 1024 // 1024))
            return
        mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        content = path.read_bytes()

        def done(file_id, error):
            if error is not None:
                self.toast(error_text(error))
                return
            self.deliver_upload(note["id"], editor, {"t": "file", "f": file_id, "n": path.name, "m": mime, "b": size})
        uploads.start(self, path.name, content, note.get("share"), done)

    def record_audio(self, editor=None, note_id=None):
        """Like Apple: record with the microphone; the recording is attached encrypted."""
        editor = editor or self.note_pane.editor
        note = self.sync.get(note_id or self.current_note) if (note_id or self.current_note) else None
        if note is None or note["data"].get("enc") or note["data"].get("trashed"):
            return
        folder = Path(GLib.get_user_cache_dir()) / "linotes" / "recordings"
        folder.mkdir(parents=True, exist_ok=True, mode=0o700)
        name = audio.recording_name()

        def recorded(path, length, error):
            if error is not None:
                self.toast(error)
                return
            content = path.read_bytes()
            path.unlink(missing_ok=True)
            if len(content) > MAX_ATTACHMENT:
                self.toast(_("Die Aufnahme ist zu lang (höchstens {value} MB, etwa 90 Minuten).", value=MAX_ATTACHMENT // 1024 // 1024))
                return

            def done(file_id, error):
                if error is not None:
                    self.toast(error_text(error))
                    return
                self.deliver_upload(note["id"], editor, {"t": "file", "f": file_id, "n": name, "m": audio.MIME,
                                                         "b": len(content), "d": round(length, 1)})
            uploads.start(self, name, content, note.get("share"), done)
        try:
            dialog = audio.RecordDialog(folder / name, recorded)
        except Exception as error:
            self.toast(_("Aufnahme nicht möglich: {error}", error=error))
            return
        dialog.present(self)

    def drop_file(self, file):
        note = self.sync.get(self.current_note) if self.current_note else None
        path = Path(file.get_path() or "")
        if note is None or note["data"].get("enc") or note["data"].get("trashed") or not path.is_file():
            return False
        if (mimetypes.guess_type(path.name)[0] or "").startswith("image/"):
            content = path.read_bytes()

            def done(file_id, error):
                if error is not None:
                    self.toast(error_text(error))
                else:
                    self.deliver_upload(note["id"], self.note_pane.editor, {"t": "image", "f": file_id})
            uploads.start(self, path.name, content, note.get("share"), done)
        else:
            self.attach_path(path, self.note_pane.editor, note)
        return True

    # --- templates (Vorlagen) ---

    def toggle_template(self, note_id):
        note = self.sync.get(note_id) if note_id else None
        if note is None or "enc" in note["data"]:
            return
        data = dict(note["data"])
        if data.get("template"):
            data.pop("template")
            self.toast(_("Keine Vorlage mehr"))
        else:
            data["template"] = True
            self.toast(_("Als Vorlage gemerkt – „Neu …“ → „Neue Notiz aus Vorlage“"))
        self.sync.put("note", data, note.get("share"), note_id)
        self.refresh_all()

    def choose_template(self):
        """Neu → Neue Notiz aus Vorlage: own templates first, then the shipped ones."""
        own = sorted((n for n in self.sync.objects("note") if n["data"].get("template") and not n["data"].get("trashed")
                      and "enc" not in n["data"]), key=lambda n: model.note_title(n).lower())
        dialog = Adw.Dialog(title=_("Neue Notiz aus Vorlage"), content_width=420)
        page = Adw.PreferencesPage()

        def row(title, subtitle, action):
            entry = Adw.ActionRow(title=GLib.markup_escape_text(title), subtitle=GLib.markup_escape_text(subtitle), activatable=True)
            entry.add_suffix(Gtk.Image(icon_name="go-next-symbolic"))
            entry.connect("activated", lambda _r: (dialog.close(), action()))
            return entry
        if own:
            group = Adw.PreferencesGroup(title=_("Eigene Vorlagen"))
            for note in own:
                group.add(row(model.note_title(note), model.note_preview(note) or "",
                              lambda note=note: self.new_from_template(model.note_blocks(note), note)))
            page.add(group)
        group = Adw.PreferencesGroup(title=_("Mitgeliefert"),
                                     description=_("Eigene Vorlagen: eine Notiz anlegen, Rechtsklick → „Als Vorlage verwenden“. {{Datum}}, {{Uhrzeit}} und {{Wochentag}} werden beim Anlegen ersetzt."))
        for _key, name, blocks in model.BUILTIN_TEMPLATES:
            group.add(row(name, " · ".join(b["x"] for b in blocks[1:4] if b.get("x")) or "",
                          lambda blocks=blocks: self.new_from_template(blocks, None)))
        page.add(group)
        view = Adw.ToolbarView(content=page)
        view.add_top_bar(Adw.HeaderBar())
        dialog.set_child(view)
        dialog.present(self)

    def new_from_template(self, blocks, source):
        """A new note in the current folder with the template's content and the placeholders filled in."""
        import datetime
        if self.stack.get_visible_child_name() != "notes" or self.current_key in ("trash", "locked", "archive"):
            self.sidebar.select("all", emit=False)
            self.current_key = "all"
            self.stack.set_visible_child_name("notes")
            self.show_note_tools(True)
        self.note_pane.editor.flush()
        folder = self.current_folder_for_new()
        share = folder.get("share") if folder else None
        body = model.fill_template(blocks, datetime.datetime.now())

        def build():
            data = {"body": body}
            if source is not None and source.get("share") != share:
                # Pictures and files of the template are encrypted for its own place – re-encrypt them.
                data = self.sync.rekey_files({"data": data, "share": source.get("share")}, share)
            return data

        def done(data, error):
            if error is not None:
                self.toast(error_text(error))
                return
            now = time.time()
            note = self.sync.put("note", {"folder": folder["id"] if folder else None, "body": data["body"],
                                          "created": now, "modified": now}, share)
            self.current_note = note["id"]
            self.sidebar.refresh()
            self.show_notes()
            self.open_note(note["id"])
            self.show_note_narrow()
        run_async(build, done)

    def toggle_archive(self, object_id):
        """Into the archive or back – for everyone the item is shared with (Olaf, 04.10.2026)."""
        obj = self.sync.get(object_id) if object_id else None
        if obj is None:
            return
        on = not model.archived(obj)
        model.set_archived(self.sync, object_id, on)
        self.toast(_("Ins Archiv verschoben") if on else _("Aus dem Archiv geholt"))
        if obj["kind"] == "note" and on and self.current_key != "archive":
            self.current_note = None
        self.refresh_all()

    def make_link_preview(self, editor, note_id, url):
        """A web address alone on a line becomes a preview card – only if switched on, never in
        locked notes. Only this computer fetches the page; the card (with picture) is stored
        encrypted in the note. Fails quietly: the address simply stays a link."""
        if not uiprefs.get("link_previews", False) or not note_id:
            return
        note = self.sync.get(note_id)
        if note is None or "enc" in note["data"] or note["data"].get("trashed"):
            return
        share = note.get("share")

        def work():
            found = linkpreview.fetch(url)
            reference = self.sync.upload_file(found["picture"], share) if found.get("picture") else None
            return linkpreview.block(url, found, reference)

        def done(block, error):
            if error is not None:
                print("LiNotes: keine Link-Vorschau:", error)
                return
            still_there = editor.get_root() is not None and (editor is not self.note_pane.editor or self.current_note == note_id)
            if still_there:
                editor.replace_url_line(url, block)
        run_async(work, done)

    def deliver_upload(self, note_id, editor, block):
        """A finished upload goes into the editor if it still shows that note – meanwhile one may
        have switched notes or closed the note window – otherwise to the end of the note."""
        showing = editor.get_root() is not None and (editor is not self.note_pane.editor or self.current_note == note_id)
        if showing:
            if block["t"] == "image":
                editor.insert_image(block["f"])
            else:
                editor.insert_file(block)
            return
        note = self.sync.get(note_id)
        if note is None or "enc" in note["data"] or note["data"].get("trashed"):
            return
        self.sync.update(note_id, body=list(model.note_blocks(note)) + [block], modified=time.time())

    def open_attachment(self, block, share):
        """Decrypt the file into a private folder under its own name and show it in a quick look
        inside LiNotes (another app only via "Teilen")."""
        def fetch():
            source = self.sync.fetch_file(block["f"], share)
            folder = Path(GLib.get_user_cache_dir()) / "linotes" / "open" / block["f"].partition(":")[2][:12]
            folder.mkdir(parents=True, exist_ok=True, mode=0o700)
            target = folder / (Path(block.get("n") or "Datei").name)
            shutil.copyfile(source, target)
            return target

        def done(target, error):
            if error is not None:
                self.toast(error_text(error))
                return
            from .quicklook import QuickLook
            QuickLook(self, target, block.get("n"), block.get("m")).present(self)
        run_async(fetch, done)

    def format_target(self, editor):
        """The editor a format command goes to (None: the main editor, if a note is open)."""
        if editor is not None:
            return editor
        return self.note_pane.editor if self.note_pane.get_visible_child_name() == "editor" else None

    def paragraph(self, style, editor=None):
        if (target := self.format_target(editor)):
            target.apply_paragraph(style)
            target.grab_focus()

    def insert_table(self, editor=None):
        """Like Apple: a 3×3 table; Tab moves on, right-click adds rows and columns."""
        if (target := self.format_target(editor)) and target.get_editable():
            target.insert_table()

    def insert_divider(self, editor=None):
        if (target := self.format_target(editor)) and target.get_editable():
            target.insert_divider()
            target.grab_focus()

    def text_color(self, name, editor=None):
        if (target := self.format_target(editor)):
            target.set_text_color(name)
            target.grab_focus()

    def font(self, name, editor=None):
        if (target := self.format_target(editor)):
            target.set_font(name)
            target.grab_focus()

    def align(self, name, editor=None):
        if (target := self.format_target(editor)):
            target.set_alignment(name)
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
            menu.append(_("Wiederherstellen"), "win.restore-note")
            menu.append(_("Endgültig löschen"), "win.delete-note")
        else:
            menu.append(_("In eigenem Fenster öffnen"), "win.note-window")
            menu.append(_("Lösen") if note["data"].get("pinned") else _("Anheften"), "win.pin-note")
            menu.append(_("Teilen …"), "win.share-note")
            menu.append(_("Verschieben nach …"), "win.move-note")
            menu.append(_("Duplizieren"), "win.duplicate-note")
            menu.append(_("Aus dem Archiv holen") if model.archived(note) else _("Archivieren"), "win.archive-note")
            menu.append(_("Nicht mehr als Vorlage") if note["data"].get("template") else _("Als Vorlage verwenden"), "win.template-note")
            menu.append(_("Als PDF exportieren …"), "win.export-note")
            menu.append(_("Drucken …"), "win.print-note")
            menu.append(_("Sperre entfernen") if note["data"].get("enc") else _("Notiz sperren"), "win.toggle-lock")
            menu.append(_("Löschen"), "win.delete-note")
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

    def with_vault(self, then, reason=_("Gib dein Notizen-Passwort ein.")):
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
                self, _("Notizen-Passwort festlegen"),
                _("Gesperrte Notizen werden auf deinem Gerät mit diesem Passwort verschlüsselt – nicht einmal der Server kann sie lesen. Wenn du das Passwort vergisst, lassen sich gesperrte Notizen nicht wiederherstellen."),
                create, confirm=True, action=_("Festlegen"),
            )
            return

        def unlock(password, _hint):
            def derive():
                return vault.unlock(existing["data"], password)

            def done(key, error):
                if error is not None:
                    self.toast(_("Falsches Passwort."))
                    return
                self.vault_key = key
                self.touch_vault()
                then()
            run_async(derive, done)
        ask_password(self, _("Gesperrte Notizen"), reason, unlock, hint=existing["data"].get("hint"), action=_("Entsperren"))

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
                self.toast(_("Sperre entfernt"))
                self.refresh_list_only()
                self.open_note(current["id"])
            self.with_vault(remove, _("Gib dein Notizen-Passwort ein, um die Sperre zu entfernen."))
            return
        if note["space"] == "shared":
            self.toast(_("Geteilte Notizen können nicht gesperrt werden – wie in Apples Notizen."))
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
            self.toast(_("Notiz gesperrt"))
            # Locking hides the content right away (and every other open locked note).
            self.lock_all()
            self.refresh_list_only()
            self.note_pane.show_locked(current["id"])
        self.with_vault(lock)

    def change_vault_password(self):
        existing = self.vault_object()
        if existing is None:
            self.toast(_("Du hast noch kein Notizen-Passwort festgelegt."))
            return

        def got_old(old, _hint):
            try:
                old_key = vault.unlock(existing["data"], old)
            except vault.WrongPassword:
                self.toast(_("Falsches Passwort."))
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
                self.toast(_("Notizen-Passwort geändert, {count} Notizen neu verschlüsselt.", count=count))
            ask_password(self, _("Neues Notizen-Passwort"), "", got_new, confirm=True, action=_("Ändern"))
        ask_password(self, _("Notizen-Passwort ändern"), _("Gib dein aktuelles Notizen-Passwort ein."), got_old,
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
            ask_text(self, _("Neuer Unterordner"), create, placeholder=_("Name"), action=_("Erstellen"),
                     body=_("Neuer Ordner in „{name}“.", name=parent['data'].get('name', 'Ordner')))
        else:
            ask_text(self, _("Neuer Ordner"), create, placeholder=_("Name"), action=_("Erstellen"),
                     body=_("Neue Ordner sind privat. Mit Rechtsklick → „Teilen …“ kannst du sie freigeben."))

    def move_folder(self, folder_id):
        """Move a folder (into another folder or to the top) or a list/board/plan into a
        folder (or out of it), like dragging in Notes."""
        folder = self.sync.get(folder_id)
        if folder is None or folder["kind"] not in ("folder", "list", "board", "plan"):
            return
        is_folder = folder["kind"] == "folder"
        blocked = (model.folder_descendants(self.sync, folder_id) | {folder_id}) if is_folder else set()
        targets = [f for f in self.sync.objects("folder") if f["id"] not in blocked]
        targets.sort(key=lambda f: (bool(f.get("share")), model.folder_path(self.sync, f).lower()))
        choices = [(None, _("Oberste Ebene") if is_folder else _("Kein Ordner"))] + [
            (f["id"], model.folder_path(self.sync, f) + (" (geteilt)" if f.get("share") else "")) for f in targets]
        current = model.folder_parent(self.sync, folder) if is_folder else (folder["data"].get("folder") or None)
        choices = [choice for choice in choices if choice[0] != current]
        dialog = Adw.AlertDialog(heading=_("„{name}“ verschieben nach", name=folder['data'].get('name', 'Ordner')),
                                 body=_("In einem geteilten Ordner sehen alle, mit denen er geteilt ist, auch den Inhalt."))
        dropdown = Gtk.DropDown.new_from_strings([label for _id, label in choices])
        dialog.set_extra_child(dropdown)
        dialog.add_response("cancel", _("Abbrechen"))
        dialog.add_response("ok", _("Verschieben"))
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
        ask_text(self, _("Neue Liste"), create, placeholder=_("z. B. Drogerie"), action=_("Erstellen"))

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
        ask_text(self, _("Neues Board"), create, placeholder=_("z. B. Haushalt"), action=_("Erstellen"))

    def new_plan(self, folder_id=None):
        """Like a list or board: a plan from a template (timetable, shifts, cleaning rota …)."""
        from . import plans
        folder = self.target_folder(folder_id)
        choices = [(key, f"{title} – {hint}") for key, title, hint in plans.TEMPLATES]

        def create(name, choice):
            data = {**plans.template(choice or "leer"), "name": name, "order": time.time()}
            if folder is not None:
                data["folder"] = folder["id"]
            plan = self.sync.put("plan", data, folder.get("share") if folder else None)
            self.sidebar.refresh()
            self.sidebar.select("plan:" + plan["id"])
        ask_text(self, _("Neuer Plan"), create, placeholder=_("z. B. Putzplan WG"), action=_("Erstellen"), choices=choices)

    def export_plan(self, plan_id):
        """A plan as PDF (to hang up) – saved, or printed from the PDF viewer."""
        plan = self.sync.get(plan_id)
        if plan is None:
            return
        from . import report
        name = plan["data"].get("name") or _("Plan")
        dialog = Gtk.FileDialog(title=_("Plan als PDF speichern"), initial_name=f"{name}.pdf")

        def chosen(dialog, result):
            try:
                file = dialog.save_finish(result)
            except GLib.Error:
                return
            try:
                report.write_plan_pdf(plan["data"], file.get_path(), self.sync.user_name)
            except Exception as error:
                self.toast(_("PDF nicht möglich: {error}", error=error))
                return
            self.toast(_("Plan als PDF gespeichert"))
            Gtk.FileLauncher.new(file).launch(self, None, None)
        dialog.save(self, None, chosen)

    def object_menu(self, kind, object_id, widget, x, y):
        obj = self.sync.get(object_id)
        if obj is None:
            return
        self.menu_target = object_id
        menu = Gio.Menu()
        menu.append(_("Teilen …"), "win.share-object")
        menu.append(_("Umbenennen …"), "win.rename-object")
        if kind == "folder":
            menu.append(_("Neuer Unterordner …"), "win.new-subfolder")
            menu.append(_("Neue Liste hier …"), "win.new-list-here")
            menu.append(_("Neues Board hier …"), "win.new-board-here")
        if kind in ("folder", "list", "board", "plan"):
            menu.append(_("Verschieben nach …"), "win.move-object")
        if kind in ("list", "board", "plan"):
            menu.append(_("Aus dem Archiv holen") if model.archived(obj) else _("Archivieren"), "win.archive-object")
        if kind == "plan":
            menu.append(_("Als PDF …"), "win.export-plan")
        if kind == "board":
            menu.append(_("Bericht exportieren …"), "win.export-object")
            menu.append(_("Entwicklungsprojekt ausschalten") if obj["data"].get("dev") else _("Als Entwicklungsprojekt führen"),
                        "win.toggle-dev")
        protected = object_id == model.default_private_folder(self.sync.user_id)
        if not protected:
            menu.append(_("Löschen …"), "win.delete-object")
        self.popup_menu(menu, widget, x, y)

    def export_board(self, board_id):
        """Report of a board as PDF (or CSV for spreadsheets) – a traceability
        matrix for development projects."""
        board = self.sync.get(board_id)
        if board is None:
            return
        from . import report
        name = board["data"].get("name", "Board")
        dialog = Gtk.FileDialog(title=_("Bericht exportieren"))
        dialog.set_initial_name(f"{name} – Stand {time.strftime('%Y-%m-%d')}.pdf")
        filters = Gio.ListStore.new(Gtk.FileFilter)
        for label, pattern in ((_("PDF-Bericht"), "*.pdf"), (_("Tabelle (CSV, z. B. für Excel)"), "*.csv")):
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
            self.toast(_("Bericht gespeichert: {name}", name=Path(path).name))
        dialog.save(self, None, chosen)

    def toggle_dev(self):
        """Development projects show card ids, the status history and the trace fields."""
        board = self.sync.get(getattr(self, "menu_target", ""))
        if board is None or board["kind"] != "board":
            return
        dev = not board["data"].get("dev")
        self.sync.update(board["id"], dev=dev)
        self.toast(_("„{name}“ ist jetzt ein Entwicklungsprojekt.", name=board['data'].get('name', 'Board')) if dev
                   else _("„{name}“ ist wieder ein einfaches Board.", name=board['data'].get('name', 'Board')))
        self.refresh_all()

    def rename_object(self):
        obj = self.sync.get(getattr(self, "menu_target", ""))
        if obj is None:
            return
        ask_text(self, _("Umbenennen"), lambda name, _c: (self.sync.update(obj["id"], name=name), self.refresh_all()),
                 text=obj["data"].get("name", ""))

    def delete_object(self):
        obj = self.sync.get(getattr(self, "menu_target", ""))
        if obj is None:
            return
        kind = obj["kind"]
        name = obj["data"].get("name", "")
        if obj["space"] == "shared" and obj["owner"] != self.sync.user_id:
            body = _("„{name}“ gehört allen – es wird auch für die anderen gelöscht.", name=name)
        else:
            body = _("„{name}“ und alles darin wird gelöscht.", name=name)
            if kind == "folder":
                body = (_("„{name}“, seine Unterordner und ihre Notizen werden gelöscht (Notizen landen in „Zuletzt gelöscht“). Listen und Boards darin bleiben erhalten – ohne Ordner.", name=name))

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
        confirm(self, _("Löschen?"), body, _("Löschen"), remove)

    # ========================================================
    # SYNC EVENTS
    # ========================================================

    def on_sync_changed(self, ids):
        if self.pages.get_visible_child_name() != "main":
            return
        self.notify_mentions(ids)
        for window in list(self.note_windows):
            window.on_sync_changed(ids)
        order = self.sync.settings().get("note_sort", "modified")
        if self.sort_action.get_state().get_string() != order:
            self.sort_action.set_state(GLib.Variant.new_string(order))
        self.sidebar.refresh()
        visible = self.stack.get_visible_child_name()
        if visible == "plan":
            if self.sync.get(self.plan_view.plan_id or "") is None:
                self.current_key = "all"
                self.select("all")
            else:
                self.plan_view.refresh()
        elif visible == "list":
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
                    # Changed elsewhere while open: someone else's changes are marked right away.
                    before = self.editing_blocks or []
                    self.editing_blocks = model.note_blocks(note)
                    self.note_pane.editor.load_blocks(self.editing_blocks, keep_cursor=True)
                    self.note_pane.update_date(note)
                    if activity.changed_by_other(note, self.sync.user_id):
                        lines = model.changed_lines(model.block_lines(before), model.block_lines(self.editing_blocks))
                        if lines:
                            self.note_pane.show_changes(lines, self.sync.user_name(note["updated_by"]), model.modified(note))
                    activity.remember(note, self.editing_blocks)
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
            "insert-table": self.insert_table,
            "attach-file": self.attach_file,
            "record-audio": self.record_audio,
            "new-folder": self.new_folder,
            "new-list": self.new_list,
            "new-board": self.new_board,
            "new-plan": self.new_plan,
            "export-plan": lambda: self.export_plan(getattr(self, "menu_target", "")),
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
            "archive-note": lambda: self.toggle_archive(self.current_note),
            "template-note": lambda: self.toggle_template(self.current_note),
            "new-from-template": self.choose_template,
            "archive-object": lambda: self.toggle_archive(self.menu_target),
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
        self.pro_action = Gio.SimpleAction.new_stateful("pro-features", None, GLib.Variant.new_boolean(False))
        self.pro_action.connect("activate", lambda action, _value: self.set_pro_features(not action.get_state().get_boolean()))
        self.add_action(self.pro_action)
        previews = Gio.SimpleAction.new_stateful("link-previews", None, GLib.Variant.new_boolean(bool(uiprefs.get("link_previews", False))))
        previews.connect("activate", lambda action, _value: (uiprefs.put("link_previews", not action.get_state().get_boolean()),
                                                             action.set_state(GLib.Variant.new_boolean(bool(uiprefs.get("link_previews", False))))))
        self.add_action(previews)
        self.justify_action = Gio.SimpleAction.new_stateful("justify", None, GLib.Variant.new_boolean(textsize.load_justify()))
        self.justify_action.connect("activate", lambda action, _value: self.set_justified(not action.get_state().get_boolean()))
        self.add_action(self.justify_action)
        current = self.sync.settings().get("note_sort", "modified")
        self.sort_action = Gio.SimpleAction.new_stateful("sort-notes", GLib.VariantType.new("s"), GLib.Variant.new_string(current))
        self.sort_action.connect("activate", lambda action, value: self.sort_notes(value.get_string()))
        self.add_action(self.sort_action)
        # Language: takes effect after a restart (texts are created once when the window is built).
        chosen = uiprefs.get("language") or "system"
        self.language_action = Gio.SimpleAction.new_stateful("language", GLib.VariantType.new("s"), GLib.Variant.new_string(chosen))
        self.language_action.connect("activate", lambda action, value: self.choose_language(value.get_string()))
        self.add_action(self.language_action)

    def choose_language(self, code):
        from . import i18n
        i18n.set_language(None if code == "system" else code)
        self.language_action.set_state(GLib.Variant.new_string(code))
        self.toast(_("Die Sprache wechselt beim nächsten Start von LiNotes."))

    def show_shortcuts(self):
        from .shortcuts import shortcuts_dialog
        shortcuts_dialog().present(self)

    def set_text_size(self, level):
        level = max(0, min(len(textsize.SIZES) - 1, level))
        textsize.save(level)
        textsize.apply(level)
        # Formulas are set once at a size taken from the text – set them again at the new one.
        GLib.idle_add(lambda: [editor.refresh_math() for editor in [self.note_pane.editor] + [w.editor for w in self.note_windows]] and False)
        self.text_size_action.set_state(GLib.Variant.new_string(str(level)))

    def insert_math(self, editor=None):
        editor = editor or self.note_pane.editor
        if not self.pro_features() or not editor.get_editable():
            return
        editor.insert_math()

    def ask_footnote(self, editor):
        """Format → Fußnote / Quelle (Profi-Funktion)."""
        def done(text, _choice):
            if text.strip():
                editor.insert_footnote(text)
        ask_text(self, _("Fußnote oder Quelle"), done, placeholder=_("z. B. Müller, Gartenbau, 2020, S. 41"), action=_("Einfügen"),
                 body=_("An der Cursorstelle erscheint eine hochgestellte Nummer, der Text steht unter der Notiz und im PDF."))

    def set_pro_features(self, on):
        self.sync.set_pro_features(on)
        self.pro_action.set_state(GLib.Variant.new_boolean(on))
        self.toast(_("Profi-Funktionen an") if on else _("Profi-Funktionen aus"))

    def pro_features(self):
        """Current state (the menu check follows syncs from other devices when asked)."""
        on = self.sync.pro_features() if self.sync.user_id is not None else False
        if self.pro_action.get_state().get_boolean() != on:
            self.pro_action.set_state(GLib.Variant.new_boolean(on))
        return on

    def set_justified(self, on):
        textsize.save_justify(on)
        self.justify_action.set_state(GLib.Variant.new_boolean(on))
        for editor in [self.note_pane.editor] + [window.editor for window in self.note_windows]:
            editor.set_justified(on)

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
        if key == Gdk.KEY_f and self.stack.get_visible_child_name() == "board":
            self.board_view.start_search()  # find cards in the open board
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
