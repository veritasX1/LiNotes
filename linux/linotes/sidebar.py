"""Sidebar: folders, smart folders, shopping lists, boards and tags."""

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Gdk, Gio, GLib, GObject, Gtk

from . import model
from .icons import Icon


class SidebarRow(Gtk.ListBoxRow):

    def __init__(self, key, icon, label, count=None, owner_hint=None):
        super().__init__()
        self.key = key
        box = Gtk.Box(spacing=10)
        box.set_margin_top(5)
        box.set_margin_bottom(5)
        box.set_margin_start(6)
        box.set_margin_end(6)
        symbol = Icon(icon, 16)
        symbol.add_css_class("accent-icon")
        box.append(symbol)
        text = Gtk.Label(label=label, xalign=0, hexpand=True, ellipsize=3)
        box.append(text)
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
        scroller.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.append(scroller)

        self.tags_box = Gtk.FlowBox(selection_mode=Gtk.SelectionMode.NONE)
        self.tags_box.set_max_children_per_line(6)
        self.tags_box.set_row_spacing(4)
        self.tags_box.set_column_spacing(4)
        self.tags_box.set_margin_start(10)
        self.tags_box.set_margin_end(10)
        self.tags_box.set_margin_bottom(8)
        self.tags_heading = Gtk.Label(label="Tags", xalign=0)
        self.tags_heading.add_css_class("sidebar-heading")
        self.append(self.tags_heading)
        self.append(self.tags_box)

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
        menu.append("Neue Einkaufsliste", "win.new-list")
        menu.append("Neues Board", "win.new-board")
        section = Gio.Menu()
        section.append("Personen und Verifizierung …", "win.people")
        section.append("Einladungscode erzeugen …", "win.invite")
        section.append("Schlüsseldatei sichern …", "win.keyfile")
        section.append("Notizen-Passwort ändern …", "win.change-vault")
        menu.append_section(None, section)
        section = Gio.Menu()
        section.append("Hilfe", "win.help")
        section.append("Dieses Gerät abmelden", "win.sign-out")
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

        folders = sorted(sync.objects("folder"), key=lambda f: (f["data"].get("order", 0), f["data"].get("name", "").lower()))
        for folder in folders:
            if folder.get("share"):
                continue
            self.add(SidebarRow(
                "folder:" + folder["id"], "folder", folder["data"].get("name", "Ordner"),
                count(lambda note, fid=folder["id"]: note["data"].get("folder") == fid),
            ), "Notizen")
        locked = count(lambda note: bool(note["data"].get("enc")))
        self.add(SidebarRow("locked", "lock", "Gesperrt", locked), "Notizen")
        trashed = sum(1 for note in notes if note["data"].get("trashed"))
        self.add(SidebarRow("trash", "trash", "Zuletzt gelöscht", trashed), "Notizen")

        for folder in folders:
            if not folder.get("share"):
                continue
            owner_hint = None if folder["owner"] == self.sync.user_id else f"von {self.sync.user_name(folder['owner'])}"
            self.add(SidebarRow(
                "folder:" + folder["id"], "folder-shared", folder["data"].get("name", "Ordner"),
                count(lambda note, fid=folder["id"]: note["data"].get("folder") == fid), owner_hint,
            ), "Geteilt")
        # Single notes shared with me (outside a shared folder of mine).
        loose = [note for note in live if note.get("share") and not self.sync.get(note["data"].get("folder") or "")]
        if loose:
            self.add(SidebarRow("shared-notes", "person", "Mit mir geteilt", len(loose)), "Geteilt")

        items = sync.objects("item")
        for shopping in sorted(sync.objects("list"), key=lambda l: (l["data"].get("order", 0), l["data"].get("name", ""))):
            open_items = sum(1 for item in items if item["data"].get("list") == shopping["id"] and not item["data"].get("done"))
            hint = "geteilt" if shopping.get("share") else None
            self.add(SidebarRow("list:" + shopping["id"], "cart", shopping["data"].get("name", "Liste"), open_items, hint), "Einkaufslisten")

        cards = sync.objects("card")
        for board in sorted(sync.objects("board"), key=lambda b: (b["data"].get("order", 0), b["data"].get("name", ""))):
            open_cards = sum(1 for card in cards if card["data"].get("board") == board["id"] and not card["data"].get("archived"))
            hint = "geteilt" if board.get("share") else None
            self.add(SidebarRow("board:" + board["id"], "board", board["data"].get("name", "Board"), open_cards, hint), "Aufgaben")

        self.refresh_tags(live)
        self.updating = False
        self.select(selected or "all", emit=False)

    def add(self, row, section):
        row.section = section
        self.list.append(row)

    def header_func(self, row, before):
        if before is None or before.section != row.section:
            label = Gtk.Label(label=row.section, xalign=0)
            label.add_css_class("sidebar-heading")
            row.set_header(label)
        else:
            row.set_header(None)

    def refresh_tags(self, notes):
        tags = {}
        for note in notes:
            for tag in model.note_tags(note):
                tags[tag] = tags.get(tag, 0) + 1
        self.active_tags &= set(tags)
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
        self.tags_heading.set_visible(bool(tags))
        self.tags_box.set_visible(bool(tags))

    def on_tag_toggled(self, button, tag):
        if button.get_active():
            self.active_tags.add(tag)
        else:
            self.active_tags.discard(tag)
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
            return
        kind, object_id = row.key.split(":", 1)
        self.window.object_menu(kind, object_id, self.list, x, y)
