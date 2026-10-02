"""Smooth mouse-wheel scrolling (like macOS): a wheel notch glides instead of jumping.

GTK scrolls touchpads smoothly already (with momentum); a mouse wheel moves in hard steps.
enable(scroller) makes the notches glide the same distance GTK would jump. With nested
scroll areas (Kanban: columns inside the board) the innermost one that can still move in
that direction gets the wheel. Follows GNOME's "Animations" switch (reduce motion)."""

import math

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
from gi.repository import Gdk, GLib, Gtk

EASE = 14.0          # per second; a notch has settled after about 0.3 s


def animations_enabled():
    settings = Gtk.Settings.get_default()
    return settings is None or settings.get_property("gtk-enable-animations")


def enable(scroller):
    controller = Gtk.EventControllerScroll(flags=Gtk.EventControllerScrollFlags.BOTH_AXES)
    controller.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
    controller.connect("scroll", _on_scroll, scroller)
    scroller.add_controller(controller)
    return scroller


def _can_move(scroller, adjustment, delta):
    if delta == 0:
        return False
    policy = scroller.get_policy()[0 if adjustment is scroller.get_hadjustment() else 1]
    if policy == Gtk.PolicyType.NEVER or adjustment.get_upper() - adjustment.get_page_size() < 1:
        return False
    if delta < 0:
        return adjustment.get_value() > adjustment.get_lower() + 0.5
    return adjustment.get_value() < adjustment.get_upper() - adjustment.get_page_size() - 0.5


def _target(scroller, controller, dx, dy):
    """The innermost scroll area under the pointer that can move this way."""
    event = controller.get_current_event()
    native = scroller.get_native()
    widget = None
    if event is not None and native is not None:
        found, x, y = event.get_position()
        if found:
            ox, oy = native.get_surface_transform()
            widget = native.pick(x - ox, y - oy, Gtk.PickFlags.DEFAULT)
    while widget is not None:
        if isinstance(widget, Gtk.ScrolledWindow):
            adjustment = widget.get_vadjustment() if dy else widget.get_hadjustment()
            if _can_move(widget, adjustment, dy or dx):
                return widget, adjustment
        if widget is scroller:
            break
        widget = widget.get_parent()
    return None, None


def _on_scroll(controller, dx, dy, scroller):
    if controller.get_unit() != Gdk.ScrollUnit.WHEEL:
        return False                     # touchpads: GTK's own smooth scrolling
    state = controller.get_current_event_state()
    if state & Gdk.ModifierType.CONTROL_MASK:
        return False                     # Ctrl+wheel belongs to zooming
    if state & Gdk.ModifierType.SHIFT_MASK and dy and not dx:
        dx, dy = dy, 0                   # Shift+wheel scrolls sideways, as in GTK
    if not dx and not dy:
        return False
    target, adjustment = _target(scroller, controller, dx, dy)
    if target is not scroller:
        return False                     # an inner area (or nobody) takes it
    delta = (dy or dx) * adjustment.get_page_size() ** (2 / 3)
    glide(scroller, adjustment, delta)
    return True


def glide(widget, adjustment, delta):
    limit = adjustment.get_upper() - adjustment.get_page_size()
    animations = widget.__dict__.setdefault("_smooth_scrolls", {})
    current = animations.get(adjustment)
    start = current["target"] if current else adjustment.get_value()
    target = max(adjustment.get_lower(), min(limit, start + delta))
    if not animations_enabled():
        adjustment.set_value(target)
        return
    if current:
        current["target"] = target
        return
    state = {"target": target, "last": None}
    animations[adjustment] = state

    def frame(_widget, clock):
        now = clock.get_frame_time() / 1e6
        elapsed = 1 / 60 if state["last"] is None else min(0.05, now - state["last"])
        state["last"] = now
        value = adjustment.get_value()
        if abs(state["target"] - value) < 0.5:
            adjustment.set_value(state["target"])
            del animations[adjustment]
            return GLib.SOURCE_REMOVE
        adjustment.set_value(value + (state["target"] - value) * (1 - math.exp(-EASE * elapsed)))
        return GLib.SOURCE_CONTINUE
    widget.add_tick_callback(frame)
