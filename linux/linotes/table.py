"""A table inside a note (like Apple's tables): a grid of cells edited in place. Tab goes to the
next cell (a new row after the last one), right-click adds or removes rows and columns."""

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gdk, GLib, Gtk
from .i18n import _


class NoteTable(Gtk.Grid):

    def __init__(self, rows, on_change, on_delete):
        super().__init__(css_classes=["note-table"], column_homogeneous=False, halign=Gtk.Align.START)
        self.on_change = on_change
        self.on_delete = on_delete
        self.cells = []
        self.build(rows)

    # --- content ---

    def rows(self):
        return [[cell.get_text() for cell in row] for row in self.cells]

    def build(self, rows, focus=None):
        while (child := self.get_first_child()) is not None:
            self.remove(child)
        self.cells = []
        for r, row in enumerate(rows):
            line = []
            for c, text in enumerate(row):
                cell = Gtk.Entry(text=text, has_frame=False, width_chars=12, css_classes=["table-cell"])
                if r == 0:
                    cell.add_css_class("table-first-row")
                cell.connect("changed", lambda _cell: self.on_change())
                keys = Gtk.EventControllerKey()
                keys.connect("key-pressed", self.on_key, r, c)
                cell.add_controller(keys)
                menu = Gtk.GestureClick(button=Gdk.BUTTON_SECONDARY)
                menu.connect("pressed", self.on_menu, cell, r, c)
                cell.add_controller(menu)
                self.attach(cell, c, r, 1, 1)
                line.append(cell)
            self.cells.append(line)
        if focus is not None:
            r, c = focus
            r = min(max(r, 0), len(self.cells) - 1)
            c = min(max(c, 0), len(self.cells[0]) - 1)
            self.cells[r][c].grab_focus()

    def change(self, rows, focus=None):
        self.build(rows, focus)
        self.on_change()

    # --- keys: Tab / Shift+Tab / Enter move between cells ---

    def on_key(self, _controller, keyval, _keycode, state, r, c):
        rows, columns = len(self.cells), len(self.cells[0])
        if keyval in (Gdk.KEY_Tab, Gdk.KEY_ISO_Left_Tab):
            back = keyval == Gdk.KEY_ISO_Left_Tab or state & Gdk.ModifierType.SHIFT_MASK
            index = r * columns + c + (-1 if back else 1)
            if index >= rows * columns:
                # Like Apple: Tab in the last cell adds a row.
                self.change(self.rows() + [[""] * columns], (rows, 0))
            elif index >= 0:
                self.cells[index // columns][index % columns].grab_focus()
            return True
        if keyval in (Gdk.KEY_Return, Gdk.KEY_KP_Enter):
            if r + 1 < rows:
                self.cells[r + 1][c].grab_focus()
            return True
        if keyval == Gdk.KEY_Up and r > 0:
            self.cells[r - 1][c].grab_focus()
            return True
        if keyval == Gdk.KEY_Down and r + 1 < rows:
            self.cells[r + 1][c].grab_focus()
            return True
        return False

    # --- right-click: rows and columns ---

    def on_menu(self, gesture, _n, x, y, cell, r, c):
        gesture.set_state(Gtk.EventSequenceState.CLAIMED)
        popover = Gtk.Popover(has_arrow=True)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        rows, columns = len(self.cells), len(self.cells[0])

        def item(label, action, enabled=True, destructive=False):
            button = Gtk.Button(label=label, css_classes=["flat"] + (["error"] if destructive else []), sensitive=enabled)
            button.get_child().set_xalign(0)
            button.connect("clicked", lambda _button: (popover.popdown(), GLib.idle_add(lambda: action() and False)))
            box.append(button)

        item(_("Zeile darüber einfügen"), lambda: self.add_row(r))
        item(_("Zeile darunter einfügen"), lambda: self.add_row(r + 1))
        item(_("Spalte links einfügen"), lambda: self.add_column(c))
        item(_("Spalte rechts einfügen"), lambda: self.add_column(c + 1))
        box.append(Gtk.Separator())
        item(_("Zeile löschen"), lambda: self.remove_row(r), rows > 1)
        item(_("Spalte löschen"), lambda: self.remove_column(c), columns > 1)
        item(_("Tabelle löschen"), self.on_delete, destructive=True)
        popover.set_child(box)
        popover.set_parent(cell)
        rect = Gdk.Rectangle()
        rect.x, rect.y, rect.width, rect.height = int(x), int(y), 1, 1
        popover.set_pointing_to(rect)
        popover.connect("closed", lambda p: p.unparent())
        popover.popup()

    def add_row(self, at):
        rows = self.rows()
        rows.insert(at, [""] * len(rows[0]))
        self.change(rows, (at, 0))

    def add_column(self, at):
        self.change([row[:at] + [""] + row[at:] for row in self.rows()], (0, at))

    def remove_row(self, at):
        rows = self.rows()
        del rows[at]
        self.change(rows, (at, 0))

    def remove_column(self, at):
        self.change([row[:at] + row[at + 1:] for row in self.rows()], (0, at))
