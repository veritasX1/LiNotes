"""Shopping lists in the style of Apple's Reminders grocery lists."""

import math
import time

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gio, GLib, GObject, Graphene, Gtk

from . import model
from . import smoothscroll
from .icons import icon_menu_button
from .i18n import _


ACCENT = (0.90, 0.64, 0.0)


def share_label(sync, obj):
    """"nur für dich" / "geteilt mit Anna" / "von Anna geteilt"."""
    share = obj.get("share")
    if not share:
        return _("nur für dich")
    if obj.get("owner") != sync.user_id:
        return _("von {person} geteilt", person=sync.user_name(obj.get('owner')))
    others = [sync.user_name(uid) for uid in sync.share_members(share) if uid != sync.user_id]
    return _("geteilt mit ") + ", ".join(others) if others else "geteilt"


class CheckCircle(Gtk.Widget):
    """The round check button of Reminders."""

    __gsignals__ = {"toggled": (GObject.SignalFlags.RUN_FIRST, None, ())}

    def __init__(self, active=False, size=22):
        super().__init__()
        self.active = active
        self.size = size
        self.set_cursor_from_name("pointer")
        self.set_valign(Gtk.Align.CENTER)
        click = Gtk.GestureClick()
        click.connect("released", self.on_click)
        self.add_controller(click)
        self.set_focusable(True)
        self.set_tooltip_text(_("Abhaken"))

    def on_click(self, gesture, n_press, x, y):
        self.active = not self.active
        self.queue_draw()
        self.emit("toggled")

    def do_measure(self, orientation, for_size):
        return self.size, self.size, -1, -1

    def do_snapshot(self, snapshot):
        size = self.size
        cr = snapshot.append_cairo(Graphene.Rect().init(0, 0, size, size))
        center = size / 2
        radius = size / 2 - 1.5
        cr.arc(center, center, radius, 0, 2 * math.pi)
        if self.active:
            cr.set_source_rgb(*ACCENT)
            cr.fill()
            cr.set_source_rgb(1, 1, 1)
            cr.set_line_width(2)
            cr.set_line_cap(1)
            cr.set_line_join(1)
            cr.move_to(center - radius * 0.45, center + radius * 0.02)
            cr.line_to(center - radius * 0.1, center + radius * 0.38)
            cr.line_to(center + radius * 0.5, center - radius * 0.35)
            cr.stroke()
        else:
            color = self.get_color()
            cr.set_source_rgba(color.red, color.green, color.blue, 0.35)
            cr.set_line_width(1.5)
            cr.stroke()


class ItemRow(Gtk.ListBoxRow):

    def __init__(self, view, item):
        super().__init__(activatable=False)
        self.view = view
        self.item_id = item["id"]
        data = item["data"]
        self.set_focusable(False)

        box = Gtk.Box(spacing=12)
        box.add_css_class("item-row")
        if data.get("done"):
            box.add_css_class("item-done")
        circle = CheckCircle(bool(data.get("done")))
        circle.connect("toggled", lambda widget: view.set_done(self.item_id, widget.active))
        box.append(circle)

        self.label = Gtk.EditableLabel(text=data.get("text", ""), hexpand=True)
        self.label.connect("notify::editing", self.on_editing)
        box.append(self.label)

        if data.get("by") and data.get("by") != view.sync.user_id and view.shared:
            who = Gtk.Label(label=view.sync.user_name(data["by"])[:1])
            who.add_css_class("avatar-chip")
            who.set_tooltip_text(_("Hinzugefügt von {person}", person=view.sync.user_name(data['by'])))
            box.append(who)

        remove = Gtk.Button(icon_name="edit-delete-symbolic", valign=Gtk.Align.CENTER)
        remove.add_css_class("flat")
        remove.add_css_class("circular")
        remove.add_css_class("item-remove")
        remove.set_tooltip_text(_("Entfernen"))
        remove.connect("clicked", lambda _button: view.remove(self.item_id))
        box.append(remove)
        self.set_child(box)

    def on_editing(self, label, _param):
        if not label.get_editing():
            text = label.get_text().strip()
            if text:
                self.view.rename(self.item_id, text)
            else:
                self.view.remove(self.item_id)


class ShoppingListView(Gtk.Box):

    def __init__(self, window):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self.window = window
        self.sync = window.sync
        self.list_id = None
        self.shared = False
        self.show_done = True

        clamp = Adw.Clamp(maximum_size=720)
        column = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        column.set_margin_start(18)
        column.set_margin_end(18)
        column.set_margin_top(18)
        column.set_margin_bottom(24)

        header = Gtk.Box(spacing=8)
        titles = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, hexpand=True)
        self.title = Gtk.Label(xalign=0)
        self.title.add_css_class("list-title")
        titles.append(self.title)
        self.subtitle = Gtk.Label(xalign=0)
        self.subtitle.add_css_class("dim-label")
        titles.append(self.subtitle)
        header.append(titles)

        # Options in a ⋯ menu with check marks, like on Android.
        actions = Gio.SimpleActionGroup()
        self.group_action = Gio.SimpleAction.new_stateful("grocery", None, GLib.Variant.new_boolean(False))
        self.group_action.connect("change-state", self.on_group_changed)
        actions.add_action(self.group_action)
        self.done_action = Gio.SimpleAction.new_stateful("show-done", None, GLib.Variant.new_boolean(True))
        self.done_action.connect("change-state", self.on_done_changed)
        actions.add_action(self.done_action)
        self.clear_action = Gio.SimpleAction.new("clear-done", None)
        self.clear_action.connect("activate", lambda *_args: self.clear_done())
        actions.add_action(self.clear_action)
        self.insert_action_group("list", actions)
        menu = Gio.Menu()
        menu.append(_("Nach Warengruppen sortieren"), "list.grocery")
        menu.append(_("Erledigte einblenden"), "list.show-done")
        section = Gio.Menu()
        section.append(_("Erledigte löschen"), "list.clear-done")
        menu.append_section(None, section)
        options = icon_menu_button("more", _("Optionen"))
        options.set_menu_model(menu)
        options.set_valign(Gtk.Align.CENTER)
        options.add_css_class("circular")
        header.append(options)
        column.append(header)

        self.entry = Gtk.Entry(placeholder_text=_("Neuer Eintrag – z. B. „2 × Milch“"))
        self.entry.add_css_class("add-entry")
        self.entry.set_margin_top(14)
        self.entry.set_margin_bottom(6)
        self.entry.set_icon_from_icon_name(Gtk.EntryIconPosition.PRIMARY, "list-add-symbolic")
        self.entry.connect("activate", self.on_add)
        column.append(self.entry)

        self.items_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        column.append(self.items_box)

        self.clear_button = Gtk.Button(label=_("Erledigte löschen"), halign=Gtk.Align.START)
        self.clear_button.add_css_class("flat")
        self.clear_button.set_margin_top(12)
        self.clear_button.connect("clicked", lambda _button: self.clear_done())
        column.append(self.clear_button)

        clamp.set_child(column)
        scroller = Gtk.ScrolledWindow(vexpand=True, child=clamp)
        smoothscroll.enable(scroller)
        scroller.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.append(scroller)
        self.updating = False

    # --- data ---------------------------------------------------

    def list_object(self):
        return self.sync.get(self.list_id)

    def items(self):
        return [item for item in self.sync.objects("item") if item["data"].get("list") == self.list_id]

    def show(self, list_id):
        self.list_id = list_id
        self.refresh()

    def refresh(self):
        shopping = self.list_object()
        if shopping is None:
            return
        self.updating = True
        data = shopping["data"]
        self.shared = bool(shopping.get("share"))
        self.title.set_label(data.get("name", "Liste"))
        items = self.items()
        open_items = [item for item in items if not item["data"].get("done")]
        done_items = [item for item in items if item["data"].get("done")]
        where = share_label(self.sync, shopping)
        self.subtitle.set_label(_("{count} offen · {where}", count=len(open_items), where=where))
        grouped = bool(data.get("grocery"))
        self.group_action.set_state(GLib.Variant.new_boolean(grouped))
        self.clear_action.set_enabled(bool(done_items))

        child = self.items_box.get_first_child()
        while child is not None:
            following = child.get_next_sibling()
            self.items_box.remove(child)
            child = following

        def order(item):
            return (item["data"].get("order", 0), item.get("updated", 0))

        if grouped:
            by_category = {}
            for item in open_items:
                category = item["data"].get("category") or model.grocery_category(item["data"].get("text", ""))
                by_category.setdefault(category, []).append(item)
            for category in model.CATEGORY_ORDER:
                if category in by_category:
                    self.add_section(model.category_name(category), sorted(by_category[category], key=order))
        else:
            self.add_section(None, sorted(open_items, key=order))

        if done_items and self.show_done:
            self.add_section(_("Erledigt ({count})", count=len(done_items)), sorted(done_items, key=lambda i: -i.get("updated", 0)))
        self.clear_button.set_visible(bool(done_items))
        if not items:
            hint = Gtk.Label(label=_("Die Liste ist leer. Tippe oben einen Eintrag ein."))
            hint.add_css_class("dim-label")
            hint.set_margin_top(24)
            self.items_box.append(hint)
        self.updating = False

    def add_section(self, title, items):
        if not items:
            return
        if title:
            label = Gtk.Label(label=title, xalign=0)
            label.add_css_class("category-header")
            self.items_box.append(label)
        listbox = Gtk.ListBox(selection_mode=Gtk.SelectionMode.NONE)
        listbox.add_css_class("boxed-list")
        for item in items:
            listbox.append(ItemRow(self, item))
        self.items_box.append(listbox)

    # --- actions ------------------------------------------------

    def on_add(self, entry):
        text = entry.get_text()
        entry.set_text("")
        shopping = self.list_object()
        if shopping is None:
            return
        base = time.time()
        # Pasting several lines adds several items.
        for index, line in enumerate(part.strip(" -•\t") for part in text.splitlines()):
            if line:
                self.sync.put("item", {
                    "list": self.list_id, "text": line, "done": False,
                    "order": base + index * 0.001, "by": self.sync.user_id,
                }, shopping.get("share"))

    def set_done(self, item_id, done):
        self.sync.update(item_id, done=done, done_by=self.sync.user_id if done else None)

    def rename(self, item_id, text):
        item = self.sync.get(item_id)
        if item and item["data"].get("text") != text:
            self.sync.update(item_id, text=text, category=None)

    def remove(self, item_id):
        self.sync.delete(item_id)

    def clear_done(self):
        for item in self.items():
            if item["data"].get("done"):
                self.sync.delete(item["id"], notify=False)
        self.sync.emit({self.list_id})

    def on_group_changed(self, action, value):
        action.set_state(value)
        self.sync.update(self.list_id, grocery=value.get_boolean())

    def on_done_changed(self, action, value):
        action.set_state(value)
        self.show_done = value.get_boolean()
        self.refresh()
