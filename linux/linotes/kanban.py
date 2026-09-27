"""Kanban board for tasks: columns with cards, drag and drop between them."""

import datetime

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gdk, GLib, GObject, Gtk

from .dialogs import ask_text, confirm
from .lists import share_label


LABEL_COLORS = [
    ("rot", "#e0463a"), ("orange", "#f08c00"), ("gelb", "#e6b800"),
    ("grün", "#2fa84f"), ("blau", "#2b7de0"), ("lila", "#9b59d0"),
]


def parse_due(text):
    try:
        return datetime.date.fromisoformat(text)
    except (TypeError, ValueError):
        return None


def due_label(day):
    today = datetime.date.today()
    delta = (day - today).days
    if delta == 0:
        return "Heute"
    if delta == 1:
        return "Morgen"
    if delta == -1:
        return "Gestern"
    return day.strftime("%d.%m.")


class CardWidget(Gtk.Box):

    def __init__(self, board, card):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self.board = board
        self.card_id = card["id"]
        data = card["data"]
        self.add_css_class("board-card")
        self.set_cursor_from_name("pointer")

        color = dict(LABEL_COLORS).get(data.get("color"))
        if color:
            strip = Gtk.Box(halign=Gtk.Align.START)
            strip.add_css_class("card-label")
            provider = Gtk.CssProvider()
            provider.load_from_string(f"box {{ background-color: {color}; }}")
            strip.get_style_context().add_provider(provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
            self.append(strip)

        title = Gtk.Label(label=data.get("title", ""), xalign=0, wrap=True)
        title.add_css_class("card-title")
        self.append(title)
        if data.get("notes"):
            notes = Gtk.Label(label=data["notes"][:140], xalign=0, wrap=True)
            notes.add_css_class("card-meta")
            self.append(notes)

        meta = Gtk.Box(spacing=8)
        day = parse_due(data.get("due"))
        if day:
            due = Gtk.Label(label="Fällig: " + due_label(day), xalign=0)
            due.add_css_class("card-meta")
            if day < datetime.date.today() and not board.is_last_column(data.get("column")):
                due.add_css_class("card-overdue")
            meta.append(due)
        spacer = Gtk.Box(hexpand=True)
        meta.append(spacer)
        if data.get("assignee"):
            name = board.sync.user_name(data["assignee"])
            chip = Gtk.Label(label=name)
            chip.add_css_class("avatar-chip")
            chip.set_tooltip_text(f"Zuständig: {name}")
            meta.append(chip)
        if meta.get_first_child() is not spacer or data.get("assignee"):
            self.append(meta)

        click = Gtk.GestureClick()
        click.connect("released", lambda *_args: board.edit_card(self.card_id))
        self.add_controller(click)

        drag = Gtk.DragSource(actions=Gdk.DragAction.MOVE)
        drag.connect("prepare", self.on_prepare)
        drag.connect("drag-begin", self.on_drag_begin)
        self.add_controller(drag)

    def on_prepare(self, source, x, y):
        return Gdk.ContentProvider.new_for_value(GObject.Value(GObject.TYPE_STRING, "card:" + self.card_id))

    def on_drag_begin(self, source, drag):
        source.set_icon(Gtk.WidgetPaintable.new(self), 20, 20)


class ColumnWidget(Gtk.Box):

    def __init__(self, board, column, cards):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self.board = board
        self.column_id = column["id"]
        self.add_css_class("board-column")
        self.set_size_request(280, -1)
        self.set_valign(Gtk.Align.START)

        header = Gtk.Box(spacing=6)
        title = Gtk.Label(label=column["data"].get("name", "Spalte"), xalign=0)
        title.add_css_class("column-title")
        header.append(title)
        count = Gtk.Label(label=str(len(cards)))
        count.add_css_class("column-count")
        header.append(count)
        header.append(Gtk.Box(hexpand=True))
        menu_button = Gtk.MenuButton(icon_name="view-more-symbolic")
        menu_button.add_css_class("flat")
        menu_button.set_popover(self.column_menu())
        header.append(menu_button)
        self.append(header)

        self.cards_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        for card in cards:
            self.cards_box.append(CardWidget(board, card))
        self.append(self.cards_box)

        self.add_entry = Gtk.Entry(placeholder_text="Karte hinzufügen …")
        self.add_entry.set_icon_from_icon_name(Gtk.EntryIconPosition.PRIMARY, "list-add-symbolic")
        self.add_entry.connect("activate", self.on_add)
        self.append(self.add_entry)

        target = Gtk.DropTarget.new(GObject.TYPE_STRING, Gdk.DragAction.MOVE)
        target.connect("drop", self.on_drop)
        target.connect("enter", lambda *_args: (self.add_css_class("drop-target"), Gdk.DragAction.MOVE)[1])
        target.connect("leave", lambda *_args: self.remove_css_class("drop-target"))
        self.add_controller(target)

    def column_menu(self):
        popover = Gtk.Popover()
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        for label, callback in (
            ("Umbenennen …", lambda: self.board.rename_column(self.column_id)),
            ("Nach links", lambda: self.board.move_column(self.column_id, -1)),
            ("Nach rechts", lambda: self.board.move_column(self.column_id, 1)),
            ("Spalte löschen …", lambda: self.board.delete_column(self.column_id)),
        ):
            button = Gtk.Button(label=label)
            button.add_css_class("flat")
            button.connect("clicked", lambda _button, function=callback: (popover.popdown(), function()))
            box.append(button)
        popover.set_child(box)
        return popover

    def on_add(self, entry):
        text = entry.get_text().strip()
        entry.set_text("")
        if text:
            self.board.add_card(self.column_id, text)
            GLib.idle_add(lambda: (self.board.focus_add(self.column_id), False)[1])

    def on_drop(self, target, value, x, y):
        self.remove_css_class("drop-target")
        if not value.startswith("card:"):
            return False
        card_id = value[5:]
        # Find the insert position from the pointer height.
        index = 0
        child = self.cards_box.get_first_child()
        while child is not None:
            found, bounds = child.compute_bounds(self)
            if found and y > bounds.get_y() + bounds.get_height() / 2:
                index += 1
            child = child.get_next_sibling()
        GLib.idle_add(lambda: (self.board.move_card(card_id, self.column_id, index), False)[1])
        return True


class BoardView(Gtk.Box):

    def __init__(self, window):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self.window = window
        self.sync = window.sync
        self.board_id = None

        header = Gtk.Box(spacing=8)
        header.set_margin_start(20)
        header.set_margin_end(20)
        header.set_margin_top(16)
        titles = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, hexpand=True)
        self.title = Gtk.Label(xalign=0)
        self.title.add_css_class("list-title")
        titles.append(self.title)
        self.subtitle = Gtk.Label(xalign=0)
        self.subtitle.add_css_class("dim-label")
        titles.append(self.subtitle)
        header.append(titles)
        add_column = Gtk.Button(label="Spalte hinzufügen", valign=Gtk.Align.CENTER)
        add_column.connect("clicked", lambda _button: self.add_column())
        header.append(add_column)
        self.append(header)

        self.columns_box = Gtk.Box(spacing=14)
        self.columns_box.set_margin_start(20)
        self.columns_box.set_margin_end(20)
        self.columns_box.set_margin_top(14)
        self.columns_box.set_margin_bottom(20)
        scroller = Gtk.ScrolledWindow(vexpand=True, child=self.columns_box)
        scroller.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        self.append(scroller)

    # --- data ---------------------------------------------------

    def board(self):
        return self.sync.get(self.board_id)

    def columns(self):
        return sorted(
            (column for column in self.sync.objects("column") if column["data"].get("board") == self.board_id),
            key=lambda column: column["data"].get("order", 0),
        )

    def cards(self, column_id):
        return sorted(
            (card for card in self.sync.objects("card")
             if card["data"].get("column") == column_id and not card["data"].get("archived")),
            key=lambda card: card["data"].get("order", 0),
        )

    def is_last_column(self, column_id):
        columns = self.columns()
        return bool(columns) and columns[-1]["id"] == column_id

    def show(self, board_id):
        self.board_id = board_id
        self.refresh()

    def refresh(self):
        board = self.board()
        if board is None:
            return
        self.title.set_label(board["data"].get("name", "Board"))
        total = 0
        child = self.columns_box.get_first_child()
        while child is not None:
            following = child.get_next_sibling()
            self.columns_box.remove(child)
            child = following
        for column in self.columns():
            cards = self.cards(column["id"])
            total += len(cards)
            self.columns_box.append(ColumnWidget(self, column, cards))
        where = share_label(self.sync, board)
        self.subtitle.set_label(f"{total} Karten · {where}")

    def focus_add(self, column_id):
        child = self.columns_box.get_first_child()
        while child is not None:
            if child.column_id == column_id:
                child.add_entry.grab_focus()
            child = child.get_next_sibling()

    # --- actions ------------------------------------------------

    def add_card(self, column_id, title):
        board = self.board()
        cards = self.cards(column_id)
        order = (cards[-1]["data"].get("order", 0) + 1) if cards else 1
        self.sync.put("card", {
            "board": self.board_id, "column": column_id, "title": title,
            "order": order, "created_by": self.sync.user_id,
        }, board.get("share"))

    def move_card(self, card_id, column_id, index):
        card = self.sync.get(card_id)
        if card is None:
            return
        others = [c for c in self.cards(column_id) if c["id"] != card_id]
        index = max(0, min(index, len(others)))
        before = others[index - 1]["data"].get("order", 0) if index > 0 else None
        after = others[index]["data"].get("order", 0) if index < len(others) else None
        if before is None and after is None:
            order = 1
        elif before is None:
            order = after - 1
        elif after is None:
            order = before + 1
        else:
            order = (before + after) / 2
        self.sync.update(card_id, column=column_id, order=order)

    def add_column(self):
        def create(name, _choice):
            columns = self.columns()
            order = (columns[-1]["data"].get("order", 0) + 1) if columns else 0
            self.sync.put("column", {"board": self.board_id, "name": name, "order": order}, self.board().get("share"))
        ask_text(self.window, "Neue Spalte", create, placeholder="Name der Spalte", action="Hinzufügen")

    def rename_column(self, column_id):
        column = self.sync.get(column_id)
        ask_text(self.window, "Spalte umbenennen",
                 lambda name, _choice: self.sync.update(column_id, name=name),
                 text=column["data"].get("name", ""))

    def move_column(self, column_id, direction):
        columns = self.columns()
        ids = [column["id"] for column in columns]
        index = ids.index(column_id)
        target = index + direction
        if not 0 <= target < len(columns):
            return
        ids[index], ids[target] = ids[target], ids[index]
        for order, identifier in enumerate(ids):
            self.sync.update(identifier, notify=False, order=order)
        self.sync.emit({self.board_id})

    def delete_column(self, column_id):
        cards = self.cards(column_id)

        def remove():
            for card in cards:
                self.sync.delete(card["id"], notify=False)
            self.sync.delete(column_id)

        confirm(self.window, "Spalte löschen?",
                f"Die Spalte und ihre {len(cards)} Karten werden gelöscht." if cards else "Die leere Spalte wird gelöscht.",
                "Löschen", remove)

    def edit_card(self, card_id):
        card = self.sync.get(card_id)
        if card is not None:
            CardDialog(self, card).present(self.window)


class CardDialog(Adw.Dialog):

    def __init__(self, board, card):
        super().__init__(title="Karte")
        self.board = board
        self.sync = board.sync
        self.card_id = card["id"]
        data = card["data"]
        self.set_content_width(460)

        view = Adw.ToolbarView()
        header = Adw.HeaderBar()
        view.add_top_bar(header)
        page = Adw.PreferencesPage()
        group = Adw.PreferencesGroup()

        self.title_row = Adw.EntryRow(title="Titel", text=data.get("title", ""))
        group.add(self.title_row)

        users = [(None, "Niemand")] + [(user["id"], user["name"]) for user in self.sync.state["users"]]
        self.users = users
        self.assignee = Adw.ComboRow(title="Zuständig", model=Gtk.StringList.new([name for _id, name in users]))
        ids = [user_id for user_id, _name in users]
        self.assignee.set_selected(ids.index(data.get("assignee")) if data.get("assignee") in ids else 0)
        group.add(self.assignee)

        columns = board.columns()
        self.columns = columns
        self.column_row = Adw.ComboRow(title="Spalte", model=Gtk.StringList.new([c["data"].get("name", "") for c in columns]))
        column_ids = [c["id"] for c in columns]
        if data.get("column") in column_ids:
            self.column_row.set_selected(column_ids.index(data.get("column")))
        group.add(self.column_row)

        self.due_switch = Adw.SwitchRow(title="Fälligkeitsdatum")
        day = parse_due(data.get("due"))
        self.due_switch.set_active(day is not None)
        group.add(self.due_switch)
        self.calendar = Gtk.Calendar()
        if day:
            self.calendar.select_day(GLib.DateTime.new_local(day.year, day.month, day.day, 0, 0, 0))
        calendar_row = Adw.PreferencesRow(child=self.calendar)
        calendar_row.set_activatable(False)
        self.due_switch.bind_property("active", calendar_row, "visible", GObject.BindingFlags.SYNC_CREATE)
        group.add(calendar_row)

        colors = Adw.ActionRow(title="Farbe")
        color_box = Gtk.Box(spacing=6, valign=Gtk.Align.CENTER)
        self.color = data.get("color")
        self.color_buttons = {}
        group_button = None
        for key, value in [(None, None)] + LABEL_COLORS:
            button = Gtk.ToggleButton()
            button.set_size_request(26, 26)
            button.add_css_class("circular")
            if value:
                provider = Gtk.CssProvider()
                provider.load_from_string(f"button {{ background: {value}; min-width: 22px; min-height: 22px; }}")
                button.get_style_context().add_provider(provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
            else:
                button.set_label("–")
            if group_button:
                button.set_group(group_button)
            group_button = group_button or button
            button.set_active(key == self.color)
            button.connect("toggled", self.on_color, key)
            color_box.append(button)
        colors.add_suffix(color_box)
        group.add(colors)
        page.add(group)

        notes_group = Adw.PreferencesGroup(title="Notizen")
        self.notes = Gtk.TextView(wrap_mode=Gtk.WrapMode.WORD_CHAR)
        self.notes.get_buffer().set_text(data.get("notes", ""))
        self.notes.set_size_request(-1, 110)
        self.notes.add_css_class("card")
        self.notes.set_left_margin(10)
        self.notes.set_right_margin(10)
        self.notes.set_top_margin(8)
        self.notes.set_bottom_margin(8)
        notes_group.add(self.notes)
        page.add(notes_group)

        actions = Adw.PreferencesGroup()
        buttons = Gtk.Box(spacing=8, halign=Gtk.Align.END)
        delete = Gtk.Button(label="Karte löschen")
        delete.add_css_class("destructive-action")
        delete.connect("clicked", lambda _button: self.delete())
        buttons.append(delete)
        done = Gtk.Button(label="Fertig")
        done.add_css_class("suggested-action")
        done.connect("clicked", lambda _button: self.close())
        buttons.append(done)
        actions.add(buttons)
        page.add(actions)

        view.set_content(page)
        self.set_child(view)
        self.connect("closed", lambda _dialog: self.save())
        self.deleted = False

    def on_color(self, button, key):
        if button.get_active():
            self.color = key

    def save(self):
        if self.deleted or self.sync.get(self.card_id) is None:
            return
        buffer = self.notes.get_buffer()
        due = None
        if self.due_switch.get_active():
            date = self.calendar.get_date()
            due = f"{date.get_year():04d}-{date.get_month():02d}-{date.get_day_of_month():02d}"
        column = self.columns[self.column_row.get_selected()]["id"] if self.columns else None
        card = self.sync.get(self.card_id)
        fields = {
            "title": self.title_row.get_text().strip() or card["data"].get("title", ""),
            "notes": buffer.get_text(buffer.get_start_iter(), buffer.get_end_iter(), False),
            "assignee": self.users[self.assignee.get_selected()][0],
            "due": due,
            "color": self.color,
        }
        if column and column != card["data"].get("column"):
            fields["column"] = column
            others = self.board.cards(column)
            fields["order"] = (others[-1]["data"].get("order", 0) + 1) if others else 1
        if any(card["data"].get(key) != value for key, value in fields.items()):
            self.sync.update(self.card_id, **fields)

    def delete(self):
        self.deleted = True
        self.sync.delete(self.card_id)
        self.close()
