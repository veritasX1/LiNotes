"""LiNotes' own symbols, drawn as vectors in the widget's foreground color."""

import math

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Graphene", "1.0")

from gi.repository import Gdk, GLib, GObject, Graphene, Gtk


LINE = 1.35


def rounded_rectangle(cr, x, y, width, height, radius):
    radius = max(0.0, min(radius, width / 2, height / 2))
    cr.new_sub_path()
    cr.arc(x + width - radius, y + radius, radius, -math.pi / 2, 0)
    cr.arc(x + width - radius, y + height - radius, radius, 0, math.pi / 2)
    cr.arc(x + radius, y + height - radius, radius, math.pi / 2, math.pi)
    cr.arc(x + radius, y + radius, radius, math.pi, 1.5 * math.pi)
    cr.close_path()


def _stroke(cr, width=LINE):
    cr.set_line_width(width)
    cr.stroke()


def icon_sidebar(cr):
    rounded_rectangle(cr, 1.5, 2.5, 13, 11, 2.2)
    _stroke(cr)
    cr.move_to(6, 2.5)
    cr.line_to(6, 13.5)
    _stroke(cr)
    for y in (5.2, 7.2, 9.2):
        cr.move_to(3, y)
        cr.line_to(4.5, y)
    _stroke(cr, 1.0)


def icon_compose(cr):
    cr.move_to(8.5, 2.5)
    cr.line_to(3.5, 2.5)
    cr.curve_to(2.4, 2.5, 1.5, 3.4, 1.5, 4.5)
    cr.line_to(1.5, 12.5)
    cr.curve_to(1.5, 13.6, 2.4, 14.5, 3.5, 14.5)
    cr.line_to(11.5, 14.5)
    cr.curve_to(12.6, 14.5, 13.5, 13.6, 13.5, 12.5)
    cr.line_to(13.5, 7.5)
    _stroke(cr)
    cr.move_to(6.5, 9.5)
    cr.line_to(7, 7.4)
    cr.line_to(12.6, 1.8)
    cr.line_to(14.2, 3.4)
    cr.line_to(8.6, 9)
    cr.close_path()
    _stroke(cr, 1.15)


def icon_checklist(cr):
    for y in (4, 8, 12):
        cr.arc(3, y, 1.7, 0, 2 * math.pi)
        _stroke(cr, 1.1)
        cr.move_to(6.5, y)
        cr.line_to(14.5, y)
        _stroke(cr, 1.3)


def icon_format(cr):
    cr.move_to(1, 13)
    cr.line_to(5, 3)
    cr.line_to(9, 13)
    cr.move_to(2.4, 9.6)
    cr.line_to(7.6, 9.6)
    _stroke(cr, 1.3)
    cr.arc(12.2, 10.6, 2.3, 0, 2 * math.pi)
    _stroke(cr, 1.2)
    cr.move_to(14.5, 7.8)
    cr.line_to(14.5, 13)
    _stroke(cr, 1.2)


def icon_table(cr):
    cr.rectangle(1.5, 2.5, 13, 11)
    _stroke(cr, 1.2)
    for y in (6.2, 9.8):
        cr.move_to(1.5, y)
        cr.line_to(14.5, y)
    for x in (5.8, 10.2):
        cr.move_to(x, 2.5)
        cr.line_to(x, 13.5)
    _stroke(cr, 1.0)


def icon_photo(cr):
    rounded_rectangle(cr, 1.5, 2.5, 13, 11, 2)
    _stroke(cr)
    cr.arc(10.5, 6, 1.3, 0, 2 * math.pi)
    cr.fill()
    cr.move_to(1.5, 12)
    cr.line_to(5.5, 7.5)
    cr.line_to(9, 11)
    cr.line_to(10.8, 9.3)
    cr.line_to(14.5, 12.5)
    _stroke(cr, 1.2)


def icon_lock(cr):
    rounded_rectangle(cr, 3, 7, 10, 7.5, 1.6)
    _stroke(cr)
    cr.move_to(5, 7)
    cr.line_to(5, 5)
    cr.curve_to(5, 1.5, 11, 1.5, 11, 5)
    cr.line_to(11, 7)
    _stroke(cr)


def icon_lock_open(cr):
    rounded_rectangle(cr, 3, 7, 10, 7.5, 1.6)
    _stroke(cr)
    cr.move_to(5, 7)
    cr.line_to(5, 5)
    cr.curve_to(5, 1.5, 11, 1.5, 11, 4)
    _stroke(cr)


def icon_share(cr):
    cr.arc(6, 5, 2.6, 0, 2 * math.pi)
    _stroke(cr)
    cr.move_to(1.5, 14)
    cr.curve_to(1.5, 10, 10.5, 10, 10.5, 14)
    _stroke(cr)
    cr.move_to(13, 4)
    cr.line_to(13, 9)
    cr.move_to(10.5, 6.5)
    cr.line_to(15.5, 6.5)
    _stroke(cr)


def icon_export(cr):
    """Apple's export symbol: a tray with an arrow leaving upwards."""
    cr.move_to(5.5, 6.5)
    cr.line_to(3.5, 6.5)
    cr.line_to(3.5, 14.5)
    cr.line_to(12.5, 14.5)
    cr.line_to(12.5, 6.5)
    cr.line_to(10.5, 6.5)
    _stroke(cr)
    cr.move_to(8, 10)
    cr.line_to(8, 1.8)
    cr.move_to(5.3, 4.3)
    cr.line_to(8, 1.6)
    cr.line_to(10.7, 4.3)
    _stroke(cr)


def icon_trash(cr):
    cr.move_to(2, 4)
    cr.line_to(14, 4)
    _stroke(cr)
    cr.move_to(6, 4)
    cr.line_to(6.5, 2)
    cr.line_to(9.5, 2)
    cr.line_to(10, 4)
    _stroke(cr, 1.1)
    cr.move_to(3.5, 4)
    cr.line_to(4.5, 14.5)
    cr.line_to(11.5, 14.5)
    cr.line_to(12.5, 4)
    _stroke(cr)
    for x in (6.5, 9.5):
        cr.move_to(x, 6.5)
        cr.line_to(x, 12)
    _stroke(cr, 1.0)


def icon_search(cr):
    cr.arc(6.8, 6.8, 4.6, 0, 2 * math.pi)
    _stroke(cr)
    cr.move_to(10.2, 10.2)
    cr.line_to(14.2, 14.2)
    _stroke(cr, 1.8)


def icon_folder(cr):
    cr.move_to(1.5, 4)
    cr.curve_to(1.5, 3, 2, 2.5, 3, 2.5)
    cr.line_to(6, 2.5)
    cr.line_to(7.5, 4.5)
    cr.line_to(13, 4.5)
    cr.curve_to(14, 4.5, 14.5, 5, 14.5, 6)
    cr.line_to(14.5, 12.5)
    cr.curve_to(14.5, 13.5, 14, 14, 13, 14)
    cr.line_to(3, 14)
    cr.curve_to(2, 14, 1.5, 13.5, 1.5, 12.5)
    cr.close_path()
    _stroke(cr)
    cr.move_to(1.5, 6.5)
    cr.line_to(14.5, 6.5)
    _stroke(cr, 1.0)


def icon_folder_shared(cr):
    icon_folder(cr)
    cr.arc(8, 9, 1.3, 0, 2 * math.pi)
    cr.fill()
    cr.move_to(5.5, 12.8)
    cr.curve_to(5.5, 10.6, 10.5, 10.6, 10.5, 12.8)
    _stroke(cr, 1.0)


def icon_cart(cr):
    """A receipt (Kassenzettel) – a cart would suggest buying in the app."""
    cr.move_to(3, 14.5)
    cr.line_to(3, 1.5)
    cr.line_to(13, 1.5)
    cr.line_to(13, 14.5)
    for index, x in enumerate((11.33, 9.67, 8, 6.33, 4.67, 3)):
        cr.line_to(x, 13 if index % 2 == 0 else 14.5)
    cr.close_path()
    _stroke(cr)
    for y, end in ((4.5, 10.5), (7, 10.5), (9.5, 8.5)):
        cr.move_to(5.5, y)
        cr.line_to(end, y)
    _stroke(cr, 1.0)


def icon_board(cr):
    for x, height in ((1.5, 11), (6.2, 7), (10.9, 9)):
        rounded_rectangle(cr, x, 2.5, 3.6, height, 1)
        _stroke(cr, 1.2)


def icon_tag(cr):
    cr.move_to(3, 6)
    cr.line_to(14, 6)
    cr.move_to(2, 10.5)
    cr.line_to(13, 10.5)
    cr.move_to(6.5, 2)
    cr.line_to(5, 14.5)
    cr.move_to(11, 2)
    cr.line_to(9.5, 14.5)
    _stroke(cr, 1.3)


def icon_pin(cr):
    cr.move_to(5.5, 1.5)
    cr.line_to(10.5, 1.5)
    cr.move_to(6.5, 1.5)
    cr.line_to(6, 6.5)
    cr.line_to(3.5, 9)
    cr.line_to(12.5, 9)
    cr.line_to(10, 6.5)
    cr.line_to(9.5, 1.5)
    _stroke(cr)
    cr.move_to(8, 9)
    cr.line_to(8, 15)
    _stroke(cr)


def icon_list(cr):
    for y in (3.5, 8, 12.5):
        cr.move_to(1.5, y)
        cr.line_to(14.5, y)
    _stroke(cr, 1.4)


def icon_gallery(cr):
    for x in (1.5, 8.8):
        for y in (1.5, 8.8):
            rounded_rectangle(cr, x, y, 5.7, 5.7, 1.2)
            _stroke(cr, 1.2)


def icon_plus(cr):
    cr.move_to(8, 2)
    cr.line_to(8, 14)
    cr.move_to(2, 8)
    cr.line_to(14, 8)
    _stroke(cr, 1.6)


def icon_more(cr):
    cr.arc(8, 8, 6.7, 0, 2 * math.pi)
    _stroke(cr)
    for x in (5, 8, 11):
        cr.arc(x, 8, 0.95, 0, 2 * math.pi)
        cr.fill()


def icon_clock(cr):
    cr.arc(8, 8, 6.5, 0, 2 * math.pi)
    _stroke(cr)
    cr.move_to(8, 4)
    cr.line_to(8, 8)
    cr.line_to(11, 10)
    _stroke(cr)


def icon_person(cr):
    cr.arc(8, 5, 3, 0, 2 * math.pi)
    _stroke(cr)
    cr.move_to(2, 14.5)
    cr.curve_to(2, 9.5, 14, 9.5, 14, 14.5)
    _stroke(cr)


def icon_notes(cr):
    rounded_rectangle(cr, 2, 1.5, 12, 13, 2)
    _stroke(cr)
    cr.move_to(2, 5)
    cr.line_to(14, 5)
    _stroke(cr, 1.0)
    for y in (8, 10.5):
        cr.move_to(4.5, y)
        cr.line_to(11.5, y)
    _stroke(cr, 1.0)


def icon_cloud(cr):
    cr.move_to(4.5, 12.5)
    cr.curve_to(1.5, 12.5, 1, 8.5, 4, 8)
    cr.curve_to(4.2, 4, 10, 3.5, 11, 7)
    cr.curve_to(15, 7, 15.2, 12.5, 11.5, 12.5)
    cr.close_path()
    _stroke(cr, 1.3)


def icon_cloud_off(cr):
    icon_cloud(cr)
    cr.move_to(2, 2)
    cr.line_to(14, 14)
    _stroke(cr, 1.3)


def icon_back(cr):
    cr.move_to(10.5, 2.5)
    cr.line_to(5, 8)
    cr.line_to(10.5, 13.5)
    _stroke(cr, 1.8)


ICONS = {
    name[5:].replace("_", "-"): function
    for name, function in list(globals().items())
    if name.startswith("icon_")
}


class Icon(Gtk.Widget):
    """A symbol drawn with the widget's foreground color."""

    def __init__(self, name, size=16):
        super().__init__()
        self.name = name
        self.size = size
        self.accent = None
        self.set_valign(Gtk.Align.CENTER)
        self.set_halign(Gtk.Align.CENTER)

    def set_accent(self, color):
        """Optional color bar/fill, used by the color buttons."""
        self.accent = color
        self.queue_draw()

    def do_measure(self, orientation, for_size):
        return self.size, self.size, -1, -1

    def do_snapshot(self, snapshot):
        width = self.get_width()
        height = self.get_height()
        cr = snapshot.append_cairo(Graphene.Rect().init(0, 0, width, height))

        color = self.get_color()
        cr.set_source_rgba(color.red, color.green, color.blue, color.alpha)
        cr.translate((width - self.size) / 2, (height - self.size) / 2)
        cr.scale(self.size / 16, self.size / 16)
        cr.set_line_cap(1)
        cr.set_line_join(1)

        if self.accent:
            cr.set_source_rgba(*self.accent)
        ICONS[self.name](cr)


class Swatch(Gtk.Widget):
    """A round color swatch for color popovers."""

    def __init__(self, color, size=22):
        super().__init__()
        self.color = color
        self.size = size

    def do_measure(self, orientation, for_size):
        return self.size, self.size, -1, -1

    def do_snapshot(self, snapshot):
        size = self.size
        cr = snapshot.append_cairo(Graphene.Rect().init(0, 0, size, size))
        cr.arc(size / 2, size / 2, size / 2 - 1, 0, 2 * math.pi)
        if self.color is None:
            cr.set_source_rgb(1, 1, 1)
            cr.fill_preserve()
            cr.set_source_rgba(0, 0, 0, 0.25)
            cr.set_line_width(1)
            cr.stroke()
            cr.move_to(size * 0.25, size * 0.75)
            cr.line_to(size * 0.75, size * 0.25)
            cr.set_source_rgb(1.0, 0.23, 0.19)
            cr.set_line_width(1.6)
            cr.stroke()
            return
        cr.set_source_rgba(*self.color)
        cr.fill_preserve()
        cr.set_source_rgba(0, 0, 0, 0.18)
        cr.set_line_width(1)
        cr.stroke()


def accessible_label(widget, tooltip):
    """Screen readers read the tooltip's text without the shortcut hint."""
    widget.update_property([Gtk.AccessibleProperty.LABEL], [tooltip.split(" (")[0].rstrip(" …")])


def icon_button(name, tooltip, toggle=False, size=16):
    button = Gtk.ToggleButton() if toggle else Gtk.Button()
    button.set_child(Icon(name, size))
    button.set_tooltip_text(tooltip)
    accessible_label(button, tooltip)
    button.add_css_class("flat")
    return button


def icon_menu_button(name, tooltip, popover=None, size=16):
    button = Gtk.MenuButton()
    button.set_child(Icon(name, size))
    button.set_tooltip_text(tooltip)
    accessible_label(button, tooltip)
    button.add_css_class("flat")
    if popover is not None:
        button.set_popover(popover)
    return button


def drag_source(widget, payload):
    """Let `widget` be dragged (payload "<kind>:<id>"), e.g. onto a folder in the sidebar."""
    source = Gtk.DragSource(actions=Gdk.DragAction.MOVE)
    source.connect("prepare", lambda *_args: Gdk.ContentProvider.new_for_value(GObject.Value(GObject.TYPE_STRING, payload)))
    source.connect("drag-begin", lambda src, _drag: src.set_icon(Gtk.WidgetPaintable.new(widget), 20, 20))
    widget.add_controller(source)


def drop_target(widget, accept, on_drop):
    """Highlight `widget` while something hovers over it; on_drop(payload) moves it if accept(payload)."""
    target = Gtk.DropTarget.new(GObject.TYPE_STRING, Gdk.DragAction.MOVE)

    def dropped(_target, value, _x, _y):
        widget.remove_css_class("drop-hover")
        return isinstance(value, str) and accept(value) and bool(on_drop(value))

    target.connect("enter", lambda *_args: (widget.add_css_class("drop-hover"), Gdk.DragAction.MOVE)[1])
    target.connect("leave", lambda *_args: widget.remove_css_class("drop-hover"))
    target.connect("drop", dropped)
    widget.add_controller(target)


def drag_autoscroll(scroller, edge=56, fastest=22, sideways=False):
    """While something is dragged over `scroller`, scroll when the pointer nears an edge (top and
    bottom; left and right too with `sideways`) – GTK does not do this by itself, so a far-away
    folder or column was out of reach. The closer to the edge, the faster."""
    speed = {"x": 0.0, "y": 0.0}
    state = {"tick": None}

    def edge_speed(position, size):
        if position < edge:
            return -fastest * (edge - position) / edge
        if position > size - edge:
            return fastest * (position - (size - edge)) / edge
        return 0.0

    def nudge(adjustment, delta):
        if delta:
            top = adjustment.get_upper() - adjustment.get_page_size()
            adjustment.set_value(min(max(adjustment.get_value() + delta, adjustment.get_lower()), top))

    def step():
        if not speed["x"] and not speed["y"]:
            state["tick"] = None
            return False
        nudge(scroller.get_vadjustment(), speed["y"])
        nudge(scroller.get_hadjustment(), speed["x"])
        return True

    def moved(_controller, x, y):
        speed["y"] = edge_speed(y, scroller.get_height())
        speed["x"] = edge_speed(x, scroller.get_width()) if sideways else 0.0
        if (speed["x"] or speed["y"]) and state["tick"] is None:
            state["tick"] = GLib.timeout_add(16, step)

    def stopped(*_args):
        speed["x"] = speed["y"] = 0.0

    motion = Gtk.DropControllerMotion()
    motion.connect("enter", moved)
    motion.connect("motion", moved)
    motion.connect("leave", stopped)
    scroller.add_controller(motion)
    return speed
