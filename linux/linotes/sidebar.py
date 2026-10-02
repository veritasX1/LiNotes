"""Sidebar: folders, smart folders, shopping lists, boards and tags."""

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gdk, Gio, GLib, GObject, Gtk

from . import model
from . import smoothscroll
from . import uiprefs
from .icons import Icon, drag_source, drop_target


class SidebarRow(Gtk.ListBoxRow):

    def __init__(self, key, icon, label, count=None, owner_hint=None, depth=0, expander=None):
        super().__init__()
        self.key = key
        box = Gtk.Box(spacing=10)
        box.set_margin_top(5)
        box.set_margin_bottom(5)
        box.set_margin_start(6 + 16 * depth)
        box.set_margin_end(6)
        symbol = Icon(icon, 16)
        symbol.add_css_class("accent-icon")
        box.append(symbol)
        text = Gtk.Label(label=label, xalign=0, hexpand=True, ellipsize=3)
        box.append(text)
        if expander is not None:
            # Subfolders fold in and out like in Apple's Notes; the arrow sits on the
            # right so that all folder symbols of one level stay aligned.
            expanded, on_toggle = expander
            arrow = Gtk.Button(icon_name="pan-down-symbolic" if expanded else "pan-start-symbolic", valign=Gtk.Align.CENTER)
            arrow.add_css_class("flat")
            arrow.add_css_class("sidebar-expander")
            arrow.set_tooltip_text("Unterordner zuklappen" if expanded else "Unterordner aufklappen")
            arrow.connect("clicked", lambda _button: on_toggle())
            box.append(arrow)
        if owner_hint:
            hint = Gtk.Label(label=owner_hint)
            hint.add_css_class("sidebar-count")
            box.append(hint)
        if count is not None:
            number = Gtk.Label(label=str(count))
            number.add_css_class("sidebar-count")
            box.append(number)
        self.set_child(box)


class Sidebar(Gtk.Box):

    __gsignals__ = {
        "selected": (GObject.SignalFlags.RUN_FIRST, None, (str,)),
        "tags-changed": (GObject.SignalFlags.RUN_FIRST, None, ()),
    }

    def __init__(self, window):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self.window = window
        self.sync = window.sync
        self.selected_key = None
        self.collapsed = set()
        self.active_tags = set()
        self.updating = False

        self.list = Gtk.ListBox()
        self.list.add_css_class("navigation-sidebar")
        self.list.set_header_func(self.header_func)
        self.list.connect("row-selected", self.on_row_selected)

        click = Gtk.GestureClick(button=Gdk.BUTTON_SECONDARY)
        click.connect("pressed", self.on_context)
        self.list.add_controller(click)

        scroller = Gtk.ScrolledWindow(vexpand=True, child=self.list)
        smoothscroll.enable(scroller)
        scroller.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.append(scroller)

        # Tags: a small, collapsible section (like Apple's sidebar sections). Collapsed it shows
        # only the tags you filter by; hovering opens it gently, a click keeps it open or closed.
        self.tags_box = self.tag_flow()
        self.active_box = self.tag_flow()
        self.active_box.set_margin_bottom(6)
        heading = Gtk.Box(spacing=6)
        heading.add_css_class("tags-heading")
        self.tags_heading_label = Gtk.Label(label="Tags", xalign=0)
        self.tags_heading_label.add_css_class("sidebar-heading-text")
        self.tags_count = Gtk.Label(xalign=0)
        self.tags_count.add_css_class("tags-count")
        self.tags_chevron = Gtk.Image(icon_name="pan-end-symbolic", pixel_size=12)
        self.tags_chevron.add_css_class("tags-chevron")
        heading.append(self.tags_heading_label)
        heading.append(self.tags_count)
        heading.append(Gtk.Box(hexpand=True))
        heading.append(self.tags_chevron)
        self.tags_heading = Gtk.Button(child=heading, css_classes=["flat", "tags-toggle"])
        self.tags_heading.connect("clicked", lambda _b: self.pin_tags(not self.tags_revealer.get_reveal_child()))
        tags_scroller = Gtk.ScrolledWindow(child=self.tags_box, propagate_natural_height=True, max_content_height=140)
        tags_scroller.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        smoothscroll.enable(tags_scroller)
        self.tags_revealer = Gtk.Revealer(child=tags_scroller, transition_type=Gtk.RevealerTransitionType.SLIDE_UP,
                                          transition_duration=180)
        self.tags_section = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.tags_section.append(self.tags_heading)
        self.tags_section.append(self.active_box)
        self.tags_section.append(self.tags_revealer)
        self.append(self.tags_section)
        self.tags_pinned = bool(uiprefs.get("tags_open", False))
        self.tags_hover_source = None
        self.tags_revealer.set_reveal_child(self.tags_pinned)
        hover = Gtk.EventControllerMotion()
        hover.connect("enter", lambda *_args: self.hover_tags(True))
        hover.connect("leave", lambda *_args: self.hover_tags(False))
        self.tags_section.add_controller(hover)
        self.update_tags_heading()

        # Account and connection status at the bottom.
        account = Gtk.Box(spacing=8)
        account.set_margin_start(12)
        account.set_margin_end(8)
        account.set_margin_top(6)
        account.set_margin_bottom(8)
        self.status_icon = Icon("cloud", 16)
        account.append(self.status_icon)
        self.account_label = Gtk.Label(xalign=0, hexpand=True, ellipsize=3)
        account.append(self.account_label)
        menu = Gio.Menu()
        menu.append("Neuen Ordner", "win.new-folder")
        menu.append("Neue Liste", "win.new-list")
        menu.append("Neues Board", "win.new-board")
        menu.append("Neuer Plan", "win.new-plan")
        section = Gio.Menu()
        section.append("Mit Server verbinden …", "win.connect")
        section.append("Personen und Verifizierung …", "win.people")
        section.append("Einladungscode erzeugen …", "win.invite")
        section.append("Schlüsseldatei sichern …", "win.keyfile")
        section.append("Notizen-Passwort ändern …", "win.change-vault")
        section.append("Entsperrte Notizen jetzt sperren", "win.lock-all")
        menu.append_section(None, section)
        section = Gio.Menu()
        section.append("Tastenkürzel", "win.shortcuts")
        section.append("Hilfe", "win.help")
        section.append("Abmelden / Daten löschen …", "win.sign-out")
        menu.append_section(None, section)
        button = Gtk.MenuButton(menu_model=menu, icon_name="open-menu-symbolic")
        button.add_css_class("flat")
        button.set_tooltip_text("Konto und Neues")
        account.append(button)
        self.append(Gtk.Separator())
        self.append(account)

    # --- content ------------------------------------------------

    def refresh(self):
        self.updating = True
        selected = self.selected_key
        self.list.remove_all()
        sync = self.sync
        user_id = sync.user_id
        notes = [note for note in sync.objects("note")]
        live = [note for note in notes if not note["data"].get("trashed")]

        def count(predicate):
            return sum(1 for note in live if predicate(note))

        self.add(SidebarRow("all", "notes", "Alle Notizen", len(live)), "Notizen")

        folders = sync.objects("folder")
        self.add_folder_tree([f for f in folders if not f.get("share")], "Notizen", count)
        locked = count(lambda note: bool(note["data"].get("enc")))
        self.add(SidebarRow("locked", "lock", "Gesperrt", locked), "Notizen")
        trashed = sum(1 for note in notes if note["data"].get("trashed"))
        self.add(SidebarRow("trash", "trash", "Zuletzt gelöscht", trashed), "Notizen")

        self.add_folder_tree([f for f in folders if f.get("share")], "Geteilt", count)
        # Single notes shared with me (outside a shared folder of mine).
        loose = [note for note in live if note.get("share") and not self.sync.get(note["data"].get("folder") or "")]
        if loose:
            self.add(SidebarRow("shared-notes", "person", "Mit mir geteilt", len(loose)), "Geteilt")

        items = sync.objects("item")
        for shopping in sorted(sync.objects("list"), key=lambda l: (l["data"].get("order", 0), l["data"].get("name", ""))):
            open_items = sum(1 for item in items if item["data"].get("list") == shopping["id"] and not item["data"].get("done"))
            hint = self.place_hint(shopping)
            self.add(SidebarRow("list:" + shopping["id"], "cart", shopping["data"].get("name", "Liste"), open_items, hint), "Listen")

        cards = sync.objects("card")
        for board in sorted(sync.objects("board"), key=lambda b: (b["data"].get("order", 0), b["data"].get("name", ""))):
            open_cards = sum(1 for card in cards if card["data"].get("board") == board["id"] and not card["data"].get("archived"))
            hint = self.place_hint(board)
            self.add(SidebarRow("board:" + board["id"], "board", board["data"].get("name", "Board"), open_cards, hint), "Aufgaben")

        for plan in sorted(sync.objects("plan"), key=lambda p: (p["data"].get("order", 0), p["data"].get("name", ""))):
            self.add(SidebarRow("plan:" + plan["id"], "table", plan["data"].get("name") or "Plan", None, self.place_hint(plan)), "Pläne")

        self.refresh_tags(live)
        self.updating = False
        self.select(selected or "all", emit=False)

    def add_folder_tree(self, folders, section, count):
        hidden_below = None
        for folder, depth in model.folder_tree(self.sync, folders):
            if hidden_below is not None and depth > hidden_below:
                continue
            hidden_below = None
            has_children = any(model.folder_parent(self.sync, f) == folder["id"] for f in folders)
            expanded = folder["id"] not in self.collapsed
            if has_children and not expanded:
                hidden_below = depth
            shared = bool(folder.get("share"))
            owner_hint = None
            if shared and depth == 0 and folder["owner"] != self.sync.user_id:
                owner_hint = f"von {self.sync.user_name(folder['owner'])}"
            self.add(SidebarRow(
                "folder:" + folder["id"], "folder-shared" if shared and depth == 0 else "folder",
                folder["data"].get("name", "Ordner"),
                count(lambda note, fid=folder["id"]: note["data"].get("folder") == fid), owner_hint, depth,
                (expanded, lambda fid=folder["id"]: self.toggle_folder(fid)) if has_children else None,
            ), section)

    def place_hint(self, obj):
        """Folder name (if in a folder) and "geteilt" – the tabs stay grouped by place."""
        folder = self.sync.get(obj["data"].get("folder") or "")
        parts = ([folder["data"].get("name", "Ordner")] if folder else []) + (["geteilt"] if obj.get("share") else [])
        return " · ".join(parts) or None

    def toggle_folder(self, folder_id):
        self.collapsed ^= {folder_id}
        self.refresh()

    def add(self, row, section):
        row.section = section
        kind = row.key.partition(":")[0]
        if kind in ("folder", "list", "board", "plan"):
            drag_source(row, row.key)
        if kind == "folder":
            # Notes, folders, lists and boards can be dropped onto a folder (not board cards).
            drop_target(row, lambda payload, key=row.key: payload.partition(":")[0] in ("note", "folder", "list", "board", "plan")
                        and payload != key, lambda payload, key=row.key: self.window.drop_on(key, payload))
        self.list.append(row)

    def header_func(self, row, before):
        if before is None or before.section != row.section:
            label = Gtk.Label(label=row.section, xalign=0)
            label.add_css_class("sidebar-heading")
            # Dropping onto the heading takes a folder to the top / a list or board out of its folder.
            wanted = {"Notizen": "folder", "Listen": "list", "Aufgaben": "board", "Pläne": "plan"}.get(row.section)
            if wanted:
                drop_target(label, lambda payload, w=wanted: payload.partition(":")[0] == w,
                            lambda payload, section=row.section: self.window.drop_on(section, payload))
            row.set_header(label)
        else:
            row.set_header(None)

    @staticmethod
    def tag_flow():
        """Chips that wrap like words (libadwaita ≥ 1.7); older systems get a FlowBox."""
        if hasattr(Adw, "WrapBox"):
            box = Adw.WrapBox(child_spacing=4, line_spacing=4)
            box.set_margin_start(10)
            box.set_margin_end(10)
            box.set_margin_bottom(8)
            return box
        flow = Gtk.FlowBox(selection_mode=Gtk.SelectionMode.NONE, homogeneous=False)
        flow.set_max_children_per_line(8)
        flow.set_row_spacing(4)
        flow.set_column_spacing(4)
        flow.set_margin_start(10)
        flow.set_margin_end(10)
        flow.set_margin_bottom(8)
        return flow

    def update_tags_heading(self):
        open_ = self.tags_revealer.get_reveal_child()
        self.tags_chevron.set_from_icon_name("pan-down-symbolic" if open_ else "pan-end-symbolic")
        self.tags_heading.set_tooltip_text("Tags ausblenden" if open_ and self.tags_pinned else
                                           "Tags immer zeigen" if open_ else "Tags zeigen")
        # Collapsed, the tags you filter by stay visible.
        self.active_box.set_visible(not open_ and bool(self.active_tags))

    def show_tags(self, show):
        self.tags_revealer.set_reveal_child(show)
        self.update_tags_heading()

    def pin_tags(self, show):
        self.tags_pinned = show
        uiprefs.put("tags_open", show)
        self.show_tags(show)

    def hover_tags(self, inside):
        if self.tags_hover_source:
            GLib.source_remove(self.tags_hover_source)
            self.tags_hover_source = None
        if self.tags_pinned:
            return

        def apply():
            self.tags_hover_source = None
            self.show_tags(inside)
            return False
        # A short pause: passing by with the mouse does not make the list jump.
        self.tags_hover_source = GLib.timeout_add(250 if inside else 450, apply)

    def refresh_tags(self, notes):
        tags = {}
        for note in notes:
            for tag in model.note_tags(note):
                tags[tag] = tags.get(tag, 0) + 1
        self.active_tags &= set(tags)
        self.fill_active_tags()
        child = self.tags_box.get_first_child()
        while child is not None:
            following = child.get_next_sibling()
            self.tags_box.remove(child)
            child = following
        for tag in sorted(tags):
            button = Gtk.ToggleButton(label="#" + tag)
            button.add_css_class("tag-chip")
            button.set_active(tag in self.active_tags)
            button.connect("toggled", self.on_tag_toggled, tag)
            self.tags_box.append(button)
        self.tags_section.set_visible(bool(tags))
        self.tags_count.set_label(str(len(tags)))
        self.update_tags_heading()

    def fill_active_tags(self):
        while (child := self.active_box.get_first_child()) is not None:
            self.active_box.remove(child)
        for tag in sorted(self.active_tags):
            button = Gtk.ToggleButton(label="#" + tag, active=True, tooltip_text="Filter aufheben")
            button.add_css_class("tag-chip")
            button.connect("toggled", self.on_active_chip, tag)
            self.active_box.append(button)
        self.update_tags_heading()

    def on_active_chip(self, button, tag):
        if not button.get_active():
            self.active_tags.discard(tag)
            child = self.tags_box.get_first_child()
            while child is not None:
                chip = child.get_child() if isinstance(child, Gtk.FlowBoxChild) else child
                if isinstance(chip, Gtk.ToggleButton) and chip.get_label() == "#" + tag:
                    chip.set_active(False)          # emits tags-changed through on_tag_toggled
                    return
                child = child.get_next_sibling()
            GLib.idle_add(lambda: self.fill_active_tags() and False)
            self.emit("tags-changed")

    def on_tag_toggled(self, button, tag):
        if button.get_active():
            self.active_tags.add(tag)
        else:
            self.active_tags.discard(tag)
        GLib.idle_add(lambda: self.fill_active_tags() and False)
        self.emit("tags-changed")

    def select(self, key, emit=True):
        row = self.list.get_first_child()
        while row is not None:
            if isinstance(row, SidebarRow) and row.key == key:
                self.updating = not emit
                self.list.select_row(row)
                self.updating = False
                self.selected_key = key
                return True
            row = row.get_next_sibling()
        if key != "all":
            return self.select("all", emit)
        return False

    def on_row_selected(self, listbox, row):
        if row is None:
            return
        self.selected_key = row.key
        if not self.updating:
            self.emit("selected", row.key)

    def set_status(self, online):
        user = self.sync.user
        name = user["name"] if user else ""
        if self.sync.is_local:
            self.account_label.set_label(f"{name} · nur lokal")
            self.status_icon.name = "cloud-off"
            self.status_icon.queue_draw()
            self.account_label.remove_css_class("status-offline")
            return
        self.account_label.set_label(f"{name} · {'verbunden' if online else 'offline'}")
        self.status_icon.name = "cloud" if online else "cloud-off"
        self.status_icon.queue_draw()
        if online:
            self.account_label.remove_css_class("status-offline")
        else:
            self.account_label.add_css_class("status-offline")

    # --- context menu -------------------------------------------

    def on_context(self, gesture, n_press, x, y):
        row = self.list.get_row_at_y(int(y))
        if not isinstance(row, SidebarRow) or ":" not in row.key:
            # Free space, section headers and smart folders: offer "new …".
            self.window.popup_menu(self.window.new_menu, self.list, x, y)
            return
        kind, object_id = row.key.split(":", 1)
        self.window.object_menu(kind, object_id, self.list, x, y)
