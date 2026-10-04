"""Kanban board for tasks: columns with cards, drag and drop between them."""

import datetime
import mimetypes
from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gdk, GLib, GObject, Gtk

from . import model
from . import smoothscroll
from . import uploads
from .dialogs import ask_text, confirm, error_text
from .icons import drag_autoscroll, icon_button
from .lists import share_label


MAX_ATTACHMENT = 24 * 1024 * 1024    # as for notes: the server takes 25 MB with encryption


def human_size(size):
    for unit in ("Bytes", "KB", "MB"):
        if size < 1024 or unit == "MB":
            return f"{size:.0f} {unit}" if unit != "MB" else f"{size:.1f} MB".replace(".", ",")
        size /= 1024


def is_image(item):
    return (item.get("m") or "").startswith("image/")


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


class CoverPicture(Gtk.Picture):
    """A card cover of fixed height: a Picture would grow with a portrait image
    (a long phone screenshot filled the whole column), so it is cropped instead."""

    HEIGHT = 96

    def do_measure(self, orientation, for_size):
        if orientation == Gtk.Orientation.VERTICAL:
            return self.HEIGHT, self.HEIGHT, -1, -1
        return 0, 0, -1, -1


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

        files = data.get("files") or []
        cover = next((item for item in files if is_image(item)), None)
        if cover is not None:
            # The first picture as a cover, as in Trello or Apple's Freeform.
            from .notes import load_thumbnail
            picture = CoverPicture(content_fit=Gtk.ContentFit.COVER, can_shrink=True)
            picture.add_css_class("card-cover")
            load_thumbnail(board.sync, cover["f"], picture, 360, share=card.get("share"))
            self.append(picture)

        title = Gtk.Label(label=data.get("title", ""), xalign=0, wrap=True, hexpand=True)
        title.add_css_class("card-title")
        mark = model.PRIORITY_MARKS.get(data.get("priority"))
        if mark:
            line = Gtk.Box(spacing=5)
            priority = Gtk.Label(label=mark, valign=Gtk.Align.START)
            priority.add_css_class("card-priority")
            priority.set_tooltip_text("Priorität: " + dict(model.PRIORITIES)[data["priority"]])
            line.append(priority)
            line.append(title)
            self.append(line)
        else:
            self.append(title)
        if data.get("notes"):
            # At most two lines, ending in "…" (like Mail's two-line preview); line breaks of the
            # notes become spaces so no line is wasted. The whole text is in the card dialog.
            preview = " ".join(data["notes"].split())[:400]
            notes = Gtk.Label(label=preview, xalign=0, wrap=True, wrap_mode=2, lines=2, ellipsize=3, max_width_chars=1)
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
        elif data.get("done_at") and board.is_last_column(data.get("column")):
            done = Gtk.Label(label="Erledigt: " + due_label(datetime.date.fromtimestamp(data["done_at"])), xalign=0)
            done.add_css_class("card-meta")
            meta.append(done)
        if board.is_dev():
            ident = Gtk.Label(label=model.short_id(card["id"]), xalign=0)
            ident.add_css_class("card-id")
            ident.set_tooltip_text("Karten-ID – in Commits und Berichten zitieren")
            meta.append(ident)
        if files:
            clip = Gtk.Label(label=f"📎 {len(files)}", xalign=0)
            clip.add_css_class("card-meta")
            clip.set_tooltip_text("Anhänge: " + ", ".join(item.get("n", "Datei") for item in files))
            meta.append(clip)
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
            board, column_id = self.board, self.column_id
            board.add_card(column_id, text)
            GLib.idle_add(lambda: (board.focus_add(column_id), board.reveal_add(column_id), False)[2])

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
        # Person with plus = invite people (as in Apple's apps); the tray with the arrow exports.
        people = icon_button("share", "Personen hinzufügen …")
        people.set_valign(Gtk.Align.CENTER)
        people.connect("clicked", lambda _button: self.window.share(self.board_id))
        header.append(people)
        export = icon_button("export", "Bericht exportieren (PDF oder CSV) …")
        export.set_valign(Gtk.Align.CENTER)
        export.connect("clicked", lambda _button: self.window.export_board(self.board_id))
        header.append(export)
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
        smoothscroll.enable(scroller)
        # Dragging a card to the edge scrolls on – to a far column or the top of a long one.
        drag_autoscroll(scroller, sideways=True)
        self.scroller = scroller
        scroller.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        self.append(scroller)

    # --- data ---------------------------------------------------

    def board(self):
        return self.sync.get(self.board_id)

    def is_dev(self):
        return model.is_dev_board(self.sync, self.board_id)

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
        # Neuaufbau (auch durch eigene Änderungen, die vom Server zurückkommen)
        # darf weder Scrollposition noch das gerade benutzte Eingabefeld verlieren.
        typing = None
        hadj, vadj = self.scroller.get_hadjustment(), self.scroller.get_vadjustment()
        scroll = (hadj.get_value(), vadj.get_value())
        root = self.get_root()
        focus = root.get_focus() if root else None
        total = 0
        child = self.columns_box.get_first_child()
        while child is not None:
            following = child.get_next_sibling()
            entry = child.add_entry
            # Der Fokus liegt im inneren Gtk.Text des Eingabefelds.
            focused = focus is not None and (focus is entry or focus.is_ancestor(entry))
            if focused or entry.get_text():
                typing = (child.column_id, entry.get_text(), entry.get_position(), focused)
            self.columns_box.remove(child)
            child = following
        for column in self.columns():
            cards = self.cards(column["id"])
            total += len(cards)
            self.columns_box.append(ColumnWidget(self, column, cards))
        where = share_label(self.sync, board)
        self.subtitle.set_label(f"{total} Karten · {where}" + (" · Entwicklungsprojekt" if self.is_dev() else ""))
        self.restore_scroll(scroll, typing[0] if typing and typing[3] else None)
        if typing:
            # Erst nach dem Layout lässt sich das neue Feld fokussieren.
            self.focus_add(*typing)
            GLib.idle_add(lambda: (self.focus_add(*typing), False)[1])

    def restore_scroll(self, scroll, column_id=None):
        def apply():
            self.scroller.get_hadjustment().set_value(scroll[0])
            vadj = self.scroller.get_vadjustment()
            vadj.set_value(scroll[1])
            if column_id:
                # Wer gerade Karten eintippt, behält das Eingabefeld im Blick.
                self.reveal_add(column_id)
            return False
        apply()
        GLib.idle_add(apply)

    def reveal_add(self, column_id):
        child = self.columns_box.get_first_child()
        while child is not None and child.column_id != column_id:
            child = child.get_next_sibling()
        if child is None:
            return
        found, bounds = child.add_entry.compute_bounds(self.columns_box)
        if not found:
            return
        vadj = self.scroller.get_vadjustment()
        bottom = bounds.get_y() + bounds.get_height() + 20
        if bottom > vadj.get_value() + vadj.get_page_size():
            vadj.set_value(min(bottom - vadj.get_page_size(), vadj.get_upper() - vadj.get_page_size()))

    def focus_add(self, column_id, text="", position=-1, focus=True):
        child = self.columns_box.get_first_child()
        while child is not None:
            if child.column_id == column_id:
                entry = child.add_entry
                entry.set_text(text)
                if focus:
                    entry.grab_focus_without_selecting()
                    entry.set_position(position)
            child = child.get_next_sibling()

    # --- actions ------------------------------------------------

    def add_card(self, column_id, title):
        board = self.board()
        cards = self.cards(column_id)
        order = (cards[-1]["data"].get("order", 0) + 1) if cards else 1
        self.sync.put("card", {
            "board": self.board_id, "column": column_id, "title": title,
            "order": order, **model.new_card_fields(self.sync, column_id),
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
        self.sync.update(card_id, order=order, **model.move_fields(self.sync, card, column_id))

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

        columns = board.columns()
        self.columns = columns
        self.column_row = Adw.ComboRow(title="Spalte", model=Gtk.StringList.new([c["data"].get("name", "") for c in columns]))
        column_ids = [c["id"] for c in columns]
        if data.get("column") in column_ids:
            self.column_row.set_selected(column_ids.index(data.get("column")))
        group.add(self.column_row)

        # Only people the board is shared with (and oneself) – not everyone one knows. Someone
        # assigned earlier who is no longer in the board stays visible, so it can be undone.
        in_board = set(self.sync.share_members(card.get("share"))) | {self.sync.user_id}
        assigned = data.get("assignee")
        people = in_board | ({assigned} if assigned is not None else set())
        users = [(None, "Niemand")] + sorted(
            ((uid, self.sync.user_name(uid) + ("" if uid in in_board else " (nicht im Board)")) for uid in people),
            key=lambda entry: entry[1].lower())
        self.users = users
        self.assignee = Adw.ComboRow(title="Zuständig", model=Gtk.StringList.new([name for _id, name in users]))
        ids = [user_id for user_id, _name in users]
        self.assignee.set_selected(ids.index(data.get("assignee")) if data.get("assignee") in ids else 0)
        group.add(self.assignee)

        priorities = [key for key, _label in model.PRIORITIES]
        self.priority_row = Adw.ComboRow(title="Priorität", model=Gtk.StringList.new([label for _key, label in model.PRIORITIES]))
        self.priority_row.set_selected(priorities.index(data.get("priority")) if data.get("priority") in priorities else 0)
        group.add(self.priority_row)

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
            button = Gtk.ToggleButton(valign=Gtk.Align.CENTER, halign=Gtk.Align.CENTER)
            button.set_size_request(26, 26)
            button.add_css_class("circular")
            button.add_css_class("color-swatch")
            if value:
                provider = Gtk.CssProvider()
                provider.load_from_string(f"button {{ background: {value}; }}")
                button.get_style_context().add_provider(provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
                # Haken zeigt die gewählte Farbe (wie auf Android/macOS).
                check = Gtk.Image(icon_name="object-select-symbolic", pixel_size=14)
                check.add_css_class("color-check")
                button.set_child(check)
            else:
                button.set_label("–")
            if group_button:
                button.set_group(group_button)
            group_button = group_button or button
            button.set_active(key == self.color)
            button.connect("toggled", self.on_color, key)
            button.connect("toggled", lambda _b: self.update_checks())
            self.color_buttons[key] = button
            color_box.append(button)
        self.update_checks()
        colors.add_suffix(color_box)
        group.add(colors)
        page.add(group)

        notes_group = Adw.PreferencesGroup(title="Notizen")
        self.notes = Gtk.TextView(wrap_mode=Gtk.WrapMode.WORD_CHAR)
        self.notes.get_buffer().set_text(data.get("notes") or "")
        self.notes.set_size_request(-1, 110)
        self.notes.add_css_class("card")
        self.notes.set_left_margin(10)
        self.notes.set_right_margin(10)
        self.notes.set_top_margin(8)
        self.notes.set_bottom_margin(8)
        notes_group.add(self.notes)
        page.add(notes_group)
        self.files_group = Adw.PreferencesGroup(title="Anhänge")
        page.add(self.files_group)
        self.file_rows = []
        self.fill_files()
        drop = Gtk.DropTarget.new(Gdk.FileList, Gdk.DragAction.COPY)
        drop.connect("drop", lambda _t, value, _x, _y: self.add_paths(
            [Path(f.get_path()) for f in value.get_files() if f.get_path()]) or True)
        page.add_controller(drop)
        dev = board.is_dev()
        dates = model.card_dates(card, dev)
        if dates:
            info = Gtk.Label(label=dates, xalign=0, wrap=True)
            info.add_css_class("card-dates")
            info.set_margin_top(8)
            notes_group.add(info)

        self.dev = dev
        if dev:
            self.impact = self.text_group(page, "Auswirkungsanalyse", card["data"].get("impact") or "",
                                          "Was ist betroffen, welche Risiken, was muss mitgeprüft werden?")
            self.verification = self.text_group(page, "Verifikation", card["data"].get("verification") or "",
                                                "Tests, Prüfungen und Nachweise")
            # Evidence right below the verification text, so test records travel with the card.
            self.evidence_group = Adw.PreferencesGroup(title="Nachweise")
            page.add(self.evidence_group)
            self.evidence_rows = []
            self.fill_files("evidence")
            evidence_drop = Gtk.DropTarget.new(Gdk.FileList, Gdk.DragAction.COPY)
            evidence_drop.connect("drop", lambda _t, value, _x, _y: self.add_paths(
                [Path(f.get_path()) for f in value.get_files() if f.get_path()], "evidence") or True)
            self.evidence_group.add_controller(evidence_drop)
            page.add(self.build_history(card))

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

    # ---- attachments ---------------------------------------------

    def card(self):
        return self.sync.get(self.card_id)

    # Attachments ("files") and verification evidence ("evidence") share one implementation.
    # Evidence also records its SHA-256, when and by whom it was added – a report can then
    # prove that a test record is the one that was attached.
    ATTACH_KINDS = {
        "files": ("Datei oder Bild hinzufügen …", "Datei oder Bild anhängen",
                  "Bilder, PDFs oder andere Dateien – verschlüsselt wie in Notizen. Auch per Ziehen.",
                  "Anhang entfernen"),
        "evidence": ("Nachweis hinzufügen …", "Nachweis anhängen",
                     "Prüfprotokolle, Screenshots, Messdaten – liegen verschlüsselt an der Karte und "
                     "erscheinen im Bericht mit Prüfsumme (SHA-256).",
                     "Nachweis entfernen"),
    }

    def fill_files(self, key="files"):
        group, rows = (self.files_group, self.file_rows) if key == "files" else (self.evidence_group, self.evidence_rows)
        for row in rows:
            group.remove(row)
        rows.clear()
        card = self.card()
        if card is None:
            return
        share = card.get("share")
        add_label, _title, hint, remove_label = self.ATTACH_KINDS[key]
        for index, item in enumerate(card["data"].get(key) or []):
            subtitle = human_size(item.get("b") or 0)
            if key == "evidence":
                details = [subtitle]
                if item.get("at"):
                    details.append(datetime.datetime.fromtimestamp(item["at"]).strftime("%d.%m.%Y %H:%M"))
                if item.get("by") is not None:
                    details.append(self.sync.user_name(item["by"]))
                if item.get("h"):
                    details.append("SHA-256 " + item["h"][:12] + "…")
                subtitle = " · ".join(details)
            row = Adw.ActionRow(title=GLib.markup_escape_text(item.get("n") or "Datei"),
                                subtitle=GLib.markup_escape_text(subtitle), activatable=True)
            row.set_tooltip_text("Öffnen" + (f"\nSHA-256 {item['h']}" if item.get("h") else ""))
            if is_image(item):
                from .notes import load_thumbnail
                # A fixed 40 px square (a Picture would take the image's own width).
                picture = Gtk.Image(pixel_size=40)
                picture.set_paintable = picture.set_from_paintable
                picture.add_css_class("card-thumb")
                load_thumbnail(self.sync, item["f"], picture, 80, share=share)
                row.add_prefix(picture)
            else:
                row.add_prefix(Gtk.Image(icon_name="text-x-generic-symbolic", pixel_size=24))
            remove = Gtk.Button(icon_name="user-trash-symbolic", valign=Gtk.Align.CENTER, tooltip_text=remove_label)
            remove.add_css_class("flat")
            remove.update_property([Gtk.AccessibleProperty.LABEL], [remove_label])
            remove.connect("clicked", lambda _b, i=index: self.remove_file(i, key))
            row.add_suffix(remove)
            row.connect("activated", lambda _r, it=item: self.board.window.open_attachment(it, share))
            group.add(row)
            rows.append(row)
        add = Adw.ButtonRow(title=add_label, start_icon_name="mail-attachment-symbolic")
        add.connect("activated", lambda _r: self.choose_files(key))
        group.add(add)
        rows.append(add)
        group.set_description(None if card["data"].get(key) else hint)

    def choose_files(self, key="files"):
        dialog = Gtk.FileDialog(title=self.ATTACH_KINDS[key][1])

        def chosen(dialog, result):
            try:
                files = dialog.open_multiple_finish(result)
            except GLib.Error:
                return
            self.add_paths([Path(f.get_path()) for f in files if f.get_path()], key)
        dialog.open_multiple(self.board.window, None, chosen)

    def add_paths(self, paths, key="files"):
        card = self.card()
        if card is None:
            return
        share = card.get("share")
        window = self.board.window
        group = self.files_group if key == "files" else self.evidence_group
        for path in paths:
            if not path.is_file():
                continue
            size = path.stat().st_size
            if size > MAX_ATTACHMENT:
                window.toast(f"„{path.name}“ ist zu groß (höchstens {MAX_ATTACHMENT // 1024 // 1024} MB).")
                continue
            mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
            content = path.read_bytes()
            entry = {"n": path.name, "m": mime, "b": size}
            if key == "evidence":
                entry.update(model.evidence_fields(self.sync, content))

            pending = []

            def done(reference, error, entry=entry, pending=pending):
                for row in pending:
                    row.get_child().detach()
                    if row.get_parent() is not None:
                        group.remove(row)
                if error is not None:
                    window.toast(error_text(error))
                    return
                # Saved to the card even if this dialog was closed meanwhile.
                current = self.sync.get(self.card_id)
                if current is None:
                    return
                items = list(current["data"].get(key) or [])
                items.append({"f": reference, **entry})
                self.sync.update(self.card_id, **{key: items})
                if self.get_root() is not None:
                    self.fill_files(key)
            upload = uploads.start(window, path.name, content, share, done)
            # Its own row in this card's list while it runs.
            row = Adw.PreferencesRow(activatable=False, child=uploads.UploadRow(
                upload, margin_top=10, margin_bottom=10, margin_start=12, margin_end=12))
            group.add(row)
            pending.append(row)

    def remove_file(self, index, key="files"):
        card = self.card()
        if card is None:
            return
        items = list(card["data"].get(key) or [])
        if 0 <= index < len(items):
            removed = items.pop(index)
            self.sync.update(self.card_id, **{key: items})
            self.fill_files(key)
            self.board.window.toast(f"„{removed.get('n', 'Datei')}“ entfernt")

    def text_group(self, page, title, text, hint):
        group = Adw.PreferencesGroup(title=title, description=hint)
        view = Gtk.TextView(wrap_mode=Gtk.WrapMode.WORD_CHAR)
        view.get_buffer().set_text(text)
        view.set_size_request(-1, 70)
        view.add_css_class("card")
        for margin in ("left", "right"):
            getattr(view, f"set_{margin}_margin")(10)
        view.set_top_margin(8)
        view.set_bottom_margin(8)
        group.add(view)
        page.add(group)
        return view

    def build_history(self, card):
        """Development projects: card id, version, linked commits and who moved
        the card where, when."""
        group = Adw.PreferencesGroup(title="Nachverfolgung")
        ident = Adw.ActionRow(title="Karten-ID", subtitle=card["id"])
        ident.set_subtitle_selectable(True)
        copy = Gtk.Button(icon_name="edit-copy-symbolic", valign=Gtk.Align.CENTER, tooltip_text="Kurz-ID kopieren")
        copy.add_css_class("flat")
        copy.connect("clicked", lambda _b: self.get_clipboard().set(model.short_id(card["id"])))
        ident.add_suffix(copy)
        group.add(ident)
        self.version_row = Adw.EntryRow(title="Umgesetzt in Version", text=card["data"].get("version") or "")
        group.add(self.version_row)
        commits = card["data"].get("commits") or []
        for commit in commits:
            row = Adw.ActionRow(title=commit.get("s", ""), subtitle="Commit " + commit.get("h", ""))
            row.set_subtitle_selectable(True)
            group.add(row)
        if not commits:
            group.add(Adw.ActionRow(title="Commits", subtitle="Noch keine – Commits mit der Karten-ID in der Nachricht werden verknüpft."))
        history = card["data"].get("history") or []
        if not history:
            group.add(Adw.ActionRow(title="Verlauf", subtitle="Noch kein Verlauf – er beginnt mit dem nächsten Verschieben."))
        for step in reversed(history):
            moment = datetime.datetime.fromtimestamp(step.get("at", 0))
            row = Adw.ActionRow(title=step.get("n") or "Spalte",
                                subtitle=f"{moment:%d.%m.%Y %H:%M} · {self.sync.user_name(step.get('by'))}")
            group.add(row)
        return group

    def update_checks(self):
        for button in self.color_buttons.values():
            check = button.get_child()
            if isinstance(check, Gtk.Image):
                check.set_opacity(1 if button.get_active() else 0)

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
            "priority": model.PRIORITIES[self.priority_row.get_selected()][0],
        }
        if self.dev:
            for key, view in (("impact", self.impact), ("verification", self.verification)):
                buffer = view.get_buffer()
                fields[key] = buffer.get_text(buffer.get_start_iter(), buffer.get_end_iter(), False).strip() or None
            fields["version"] = self.version_row.get_text().strip() or None
        if column and column != card["data"].get("column"):
            fields.update(model.move_fields(self.sync, card, column))
            others = self.board.cards(column)
            fields["order"] = (others[-1]["data"].get("order", 0) + 1) if others else 1
        if any(card["data"].get(key) != value for key, value in fields.items()):
            self.sync.update(self.card_id, **fields)

    def delete(self):
        self.deleted = True
        self.sync.delete(self.card_id)
        self.close()
