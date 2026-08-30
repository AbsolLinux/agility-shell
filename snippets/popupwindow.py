from fabric.widgets.wayland import WaylandWindow
from gi.repository import Gtk, GtkLayerShell, Gdk, GLib

EDGE_MARGIN = 0

def _get_monitor_geometry(widget: Gtk.Widget | None) -> tuple[int, int, int]:
    if widget is not None:
        if hasattr(widget, "gdk_monitor") and widget.gdk_monitor:
            geo = widget.gdk_monitor.get_geometry()
            return geo.x, geo.width, geo.height
        if hasattr(widget, "monitor_id") and widget.monitor_id is not None:
            display = Gdk.Display.get_default()
            if display and 0 <= widget.monitor_id < display.get_n_monitors():
                mon = display.get_monitor(widget.monitor_id)
                if mon:
                    geo = mon.get_geometry()
                    return geo.x, geo.width, geo.height

    screen = Gdk.Screen.get_default()
    if widget is not None:
        toplevel = widget.get_toplevel() if hasattr(widget, "get_toplevel") else None
        if toplevel and hasattr(toplevel, "get_window"):
            window = toplevel.get_window()
            if window is not None and screen is not None:
                monitor_index = screen.get_monitor_at_window(window)
                geo = screen.get_monitor_geometry(monitor_index)
                return geo.x, geo.width, geo.height

    if screen is not None:
        return 0, screen.get_width(), screen.get_height()
    return 0, 1920, 1080

class PopupWindow(WaylandWindow):
    def __init__(
        self,
        parent: WaylandWindow | None = None,
        pointing_to: Gtk.Widget | None = None,
        margin: tuple[int, ...] | str = "0px 0px 0px 0px",
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.exclusivity = "none"

        self._parent = parent
        self._pointing_widget = pointing_to
        self._base_margin = self.extract_margin(margin)
        self.margin = tuple(self._base_margin.values()) if hasattr(self._base_margin, "values") else self._base_margin
        self._initial_position = True

        self.connect("notify::visible", self.do_update_handlers)

    def get_coords_for_widget(self, widget: Gtk.Widget) -> tuple[int, int]:
        if not ((toplevel := widget.get_toplevel()) and toplevel.is_toplevel()):
            return 0, 0
        coords = widget.translate_coordinates(toplevel, 0, 0)
        if coords is not None:
            return coords[0], coords[1]
        allocation = widget.get_allocation()
        return allocation.x, allocation.y

    def set_pointing_to(self, widget: Gtk.Widget | None):
        if self._pointing_widget:
            try:
                self._pointing_widget.disconnect_by_func(self.do_handle_size_allocate)
            except Exception:
                pass
        self._pointing_widget = widget
        return self.do_update_handlers()

    def do_update_handlers(self, *_):
        if not self._pointing_widget:
            return

        if not self.get_visible():
            try:
                self._pointing_widget.disconnect_by_func(self.do_handle_size_allocate)
                self.disconnect_by_func(self.do_handle_size_allocate)
            except Exception:
                pass
            return

        try:
            self._pointing_widget.disconnect_by_func(self.do_handle_size_allocate)
            self.disconnect_by_func(self.do_handle_size_allocate)
        except Exception:
            pass

        self._pointing_widget.connect("size-allocate", self.do_handle_size_allocate)
        self.connect("size-allocate", self.do_handle_size_allocate)

        GLib.timeout_add(10, self._do_delayed_reposition)

    def _do_delayed_reposition(self):
        self._initial_position = True
        self.do_reposition(self.do_calculate_edges())
        return False

    def do_handle_size_allocate(self, *_):
        if not self.get_visible():
            return
        return self.do_reposition(self.do_calculate_edges())

    def do_calculate_edges(self):
        move_axe = "x"
        if not self._parent:
            self.anchor = "left top"
            return move_axe

        alignment = getattr(self._parent, "alignment", None)
        if alignment == "bottom":
            self.anchor = "left bottom"
        elif alignment == "top":
            self.anchor = "left top"
        elif GtkLayerShell.get_anchor(self._parent, GtkLayerShell.Edge.BOTTOM):
            self.anchor = "left bottom"
        else:
            self.anchor = "left top"

        return move_axe

    def do_reposition(self, move_axe: str = "x"):
        if not self._parent:
            return

        self.do_calculate_edges()

        monitor_x, monitor_width, monitor_height = _get_monitor_geometry(self._parent)
        width = self.get_allocated_width()
        if width <= 1 and hasattr(self, "_content_box"):
            width = self._content_box.get_preferred_size()[1].width
        if width <= 1:
            width = self.get_preferred_size()[1].width

        height = self.get_allocated_height()
        bar_width = self._parent.get_allocated_width()
        if bar_width <= 1:
            bar_width = self._parent.get_preferred_size()[1].width

        parent_margin = self._parent.margin if hasattr(self._parent, "margin") else (0, 0, 0, 0)
        parent_margin_vals = tuple(parent_margin) if hasattr(parent_margin, "__iter__") else (0, 0, 0, 0)
        parent_right_margin = parent_margin_vals[1] if len(parent_margin_vals) > 1 else 0
        parent_left_margin = parent_margin_vals[3] if len(parent_margin_vals) > 3 else 0

        h_align = getattr(self._parent, "horizontal_alignment", "center")
        min_width = getattr(self._parent, "min_width", False)

        is_left = GtkLayerShell.get_anchor(self._parent, GtkLayerShell.Edge.LEFT)
        is_right = GtkLayerShell.get_anchor(self._parent, GtkLayerShell.Edge.RIGHT)

        if not min_width or (is_left and is_right):
            bar_screen_left = parent_left_margin
        elif h_align == "left" or (is_left and not is_right):
            bar_screen_left = parent_left_margin
        elif h_align == "right" or (is_right and not is_left):
            bar_screen_left = monitor_width - bar_width - parent_right_margin
        else:
            bar_screen_left = (monitor_width - bar_width) // 2

        if self._pointing_widget:
            coords = self.get_coords_for_widget(self._pointing_widget)
            widget_width = self._pointing_widget.get_allocated_width()
            widget_center_in_bar = coords[0] + (widget_width / 2.0)
        else:
            widget_center_in_bar = bar_width / 2.0

        screen_widget_center_x = bar_screen_left + widget_center_in_bar
        raw_margin_left = round(screen_widget_center_x - (width / 2.0))

        min_margin = EDGE_MARGIN
        max_margin = max(0, monitor_width - width - EDGE_MARGIN)
        clamped_left = max(min_margin, min(raw_margin_left, max_margin))

        base_vals = list(self._base_margin.values()) if hasattr(self._base_margin, "values") else [0, 0, 0, 0]
        base_top = base_vals[0] if len(base_vals) > 0 else 0
        base_right = base_vals[1] if len(base_vals) > 1 else 0
        base_bottom = base_vals[2] if len(base_vals) > 2 else 0
        base_left = base_vals[3] if len(base_vals) > 3 else 0

        is_bottom = (
            getattr(self._parent, "alignment", None) == "bottom"
            or GtkLayerShell.get_anchor(self._parent, GtkLayerShell.Edge.BOTTOM)
        )

        if is_bottom:
            new_margin = (0, max(0, base_right), max(0, base_bottom), max(0, clamped_left + base_left))
        else:
            new_margin = (max(0, base_top), max(0, base_right), 0, max(0, clamped_left + base_left))

        if self.margin != new_margin:
            self.margin = new_margin

        self._initial_position = False