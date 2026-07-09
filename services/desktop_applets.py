import gi
gi.require_version("Gtk", "3.0")

from gi.repository import Gtk, Gdk, GLib, GtkLayerShell
from fabric.core.service import Service, Signal
from fabric.widgets.wayland import WaylandWindow
from fabric.widgets.box import Box
from loguru import logger

from user_options import user_options
from desktop_applets import DESKTOP_APPLET_SIZES, DESKTOP_APPLET_WIDGETS, DESKTOP_CANVAS_SIZES
CELL      = 81   # px per grid square
GAP       = 12   # px between squares
CELL_STEP = CELL + GAP   # 93 px


def _applet_pixel_size(key: str) -> tuple[int, int]:
    cols, rows = DESKTOP_CANVAS_SIZES.get(key, (1, 1))
    w = cols * 2 * CELL + (cols * 2 - 1) * GAP
    h = rows * 2 * CELL + (rows * 2 - 1) * GAP
    return w, h


def _grid_to_pixel(grid_x: int, grid_y: int) -> tuple[int, int]:
    """Convert grid cell indices to top-left pixel offset (before padding)."""
    return grid_x * CELL_STEP, grid_y * CELL_STEP

class DesktopAppletWindow(WaylandWindow):

    def __init__(self, monitor_id: int) -> None:
        self._monitor_id  = monitor_id
        self._fixed       = Gtk.Fixed()
        self._children: dict[str, Gtk.Widget] = {}  # key → widget
        self._pad_x = 0
        self._pad_y = 0
        self._root = Box(h_expand=True, v_expand=True)
        self._root.add(self._fixed)

        super().__init__(
            monitor=monitor_id,
            anchor="left right top bottom",
            exclusivity="ignore",
            layer="background",
            child=self._root,
            visible=True,
            name=f"desktop-applets-{monitor_id}",
        )
        # self.show_all()
        GtkLayerShell.set_exclusive_zone(self, -1)
        self._force_refresh()
        self.connect("size-allocate", self._on_size_allocate)


    def _on_size_allocate(self, widget, alloc: Gdk.Rectangle) -> None:
        w, h = alloc.width, alloc.height
        if w < 1 or h < 1:
            return
        cols = max(1, w // CELL_STEP)
        rows = max(1, h // CELL_STEP)
        self._pad_x = (w - cols * CELL_STEP + GAP) // 2
        self._pad_y = (h - rows * CELL_STEP + GAP) // 2
        self._reposition_all()

    def _reposition_all(self) -> None:
        entries = user_options.desktop_canvas.get_applets(self._monitor_id)
        for entry in entries:
            key    = entry["key"]
            grid_x = entry["grid_x"]
            grid_y = entry["grid_y"]
            widget = self._children.get(key)
            if widget is None:
                continue
            px, py = _grid_to_pixel(grid_x, grid_y)
            self._fixed.move(widget, self._pad_x + px, self._pad_y + py)

    def rebuild(self) -> None:
        for widget in self._children.values():
            self._fixed.remove(widget)
            widget.destroy()
        self._children.clear()

        entries = user_options.desktop_canvas.get_applets(self._monitor_id)
        for entry in entries:
            key    = entry["key"]
            cls    = DESKTOP_APPLET_WIDGETS.get(key)
            if cls is None:
                logger.warning(f"[DesktopAppletService] unknown applet key {key!r}")
                continue
            try:
                widget = cls()
                w_px, h_px = _applet_pixel_size(key)
                widget.set_size_request(w_px, h_px)

                eb = Gtk.EventBox()
                eb.set_size_request(w_px, h_px)
                eb.add(widget)
                eb.connect("button-press-event", self._on_applet_right_click, key)
                eb.show_all()

                self._fixed.put(eb, 0, 0)
                self._children[key] = eb
            except Exception as e:
                logger.error(f"[DesktopAppletService] failed to build {key!r}: {e}")

        self._reposition_all()
        self._force_refresh()

    def add_applet(self, key: str, grid_x: int, grid_y: int) -> None:
        if key in self._children:
            return
        cls = DESKTOP_APPLET_WIDGETS.get(key)
        if cls is None:
            return
        try:
            widget = cls()
            w_px, h_px = _applet_pixel_size(key)
            widget.set_size_request(w_px, h_px)

            eb = Gtk.EventBox()
            eb.set_size_request(w_px, h_px)
            eb.add(widget)
            eb.connect("button-press-event", self._on_applet_right_click, key)
            eb.show_all()

            self._fixed.put(eb, 0, 0)
            self._children[key] = eb
            self._reposition_all()
            self._force_refresh()
        except Exception as e:
            logger.error(f"[DesktopAppletService] failed to build {key!r}: {e}")

    def remove_applet(self, key: str) -> None:
        widget = self._children.pop(key, None)
        if widget:
            self._fixed.remove(widget)
            widget.destroy()
            
    def _on_applet_right_click(self, eb, event: Gdk.EventButton, key: str) -> bool:
        if event.button != 3:
            return False

        menu = Gtk.Menu()

        remove_item = Gtk.MenuItem(label=f"Remove {key}")
        remove_item.connect("activate", lambda _: DesktopAppletService.get_instance().remove(self._monitor_id, key))
        menu.append(remove_item)

        menu.show_all()
        menu.popup_at_pointer(event)
        return True
    def _force_refresh(self):
        #For some reason niri needs this
        self.hide()
        self.show_all()
        return False
class DesktopAppletService(Service):
    _instance: "DesktopAppletService | None" = None

    @staticmethod
    def get_instance() -> "DesktopAppletService":
        if DesktopAppletService._instance is None:
            DesktopAppletService._instance = DesktopAppletService()
        return DesktopAppletService._instance

    @Signal
    def applets_changed(self, monitor_id: int) -> None: ...

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._windows: dict[int, DesktopAppletWindow] = {}

        display = Gdk.Display.get_default()
        if display:
            display.connect("monitor-added",   self._on_monitor_added)
            display.connect("monitor-removed", self._on_monitor_removed)

        self._sync_monitors()

        for mid, win in self._windows.items():
            win.rebuild()

    def _sync_monitors(self) -> None:
        display  = Gdk.Display.get_default()
        current  = set(range(display.get_n_monitors()))
        existing = set(self._windows.keys())
        for mid in existing - current:
            self._remove_window(mid)
        for mid in current - existing:
            self._add_window(mid)

    def _add_window(self, monitor_id: int) -> None:
        if monitor_id in self._windows:
            return
        win = DesktopAppletWindow(monitor_id)
        self._windows[monitor_id] = win
        logger.info(f"[DesktopAppletService] window created for monitor {monitor_id}")

    def _remove_window(self, monitor_id: int) -> None:
        win = self._windows.pop(monitor_id, None)
        if win:
            win.destroy()
            logger.info(f"[DesktopAppletService] window removed for monitor {monitor_id}")

    def _on_monitor_added(self, _display, _monitor) -> None:
        logger.info("[DesktopAppletService] monitor added, resyncing...")
        self._sync_monitors()

    def _on_monitor_removed(self, _display, _monitor) -> None:
        logger.info("[DesktopAppletService] monitor removed, resyncing...")
        self._sync_monitors()

    def place(self, monitor_id: int, key: str, grid_x: int, grid_y: int) -> bool:
        placed = user_options.desktop_canvas.place(monitor_id, key, grid_x, grid_y)
        if not placed:
            return False
        user_options.save()
        win = self._windows.get(monitor_id)
        if win:
            win.add_applet(key, grid_x, grid_y)
        self.applets_changed(monitor_id)

        return True

    def remove(self, monitor_id: int, key: str) -> bool:
        removed = user_options.desktop_canvas.remove(monitor_id, key)
        if not removed:
            return False
        user_options.save()

        win = self._windows.get(monitor_id)
        if win:
            win.remove_applet(key)
        self.applets_changed(monitor_id)
        return True

    def move(self, monitor_id: int, key: str, grid_x: int, grid_y: int) -> None:
        user_options.desktop_canvas.move(monitor_id, key, grid_x, grid_y)
        user_options.save()

        win = self._windows.get(monitor_id)
        if win:
            win.remove_applet(key)
            win.add_applet(key, grid_x, grid_y)

        self.applets_changed(monitor_id)

    def get_window(self, monitor_id: int) -> "DesktopAppletWindow | None":
        return self._windows.get(monitor_id)