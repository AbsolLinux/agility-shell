import gi
gi.require_version("Gtk", "3.0")

from urllib.parse import unquote
from gi.repository import Gtk, Gdk, GLib, GtkLayerShell
from fabric.core.service import Service, Signal
from fabric.widgets.wayland import WaylandWindow
from fabric.widgets.box import Box
from loguru import logger

from user_options import user_options
from utils.helpers import popup_with_blur
from desktop_applets import DESKTOP_APPLET_SIZES, DESKTOP_APPLET_WIDGETS, DESKTOP_CANVAS_SIZES
from .themes import wallpaper
from snippets import Animator
CELL      = 81
GAP       = 12
CELL_STEP = CELL + GAP


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
        self._children: dict[str, Gtk.Widget] = {}
        self._pad_x = 0
        self._pad_y = 0
        self._cols = 0
        self._rows = 0
        self._old_w = 0
        self._old_h = 0
        self._recalc_in_progress = False
        self._pending_recalc = False
        self._recalc_timer: int | None = None
        self._fade_in_timer: int | None = None
        self._ready = False
        self.bar_manager = None
        self._root = Box(h_expand=True, v_expand=True)
        self._root.add(self._fixed)
        self._in_size_allocate = False

        self._fade_animator = Animator(
            bezier_curve=(0.4, 0.0, 0.2, 1.0),
            duration=0.4,
            min_value=0.0,
            max_value=1.0,
            tick_widget=self._root,
        )
        self._fade_animator.connect("notify::value", self._on_fade_value)
        self._fade_animator.connect("finished", self._on_fade_finished)


        self._fade_out_animator = Animator(
            bezier_curve=(0.4, 0.0, 0.2, 1.0),
            duration=0.2,
            min_value=0.0,
            max_value=1.0,
            tick_widget=self._root,
        )
        self._fade_out_animator.connect("notify::value", self._on_fade_out_value)
        self._fade_out_animator.connect("finished", self._on_fade_out_finished)
        self._fixed.set_opacity(0.0)

        super().__init__(
            monitor=monitor_id,
            anchor="left right top bottom",
            exclusivity="ignore",
            layer="bottom",
            child=self._root,
            visible=True,
            title=f"caffyne-shell-desktop-applets",
        )
        # GtkLayerShell.set_exclusive_zone(self, -1)
        self.connect("size-allocate", self._on_size_allocate)
        self.connect("button-press-event", self._on_button_press)
        self._setup_drag_and_drop()
        
        GLib.timeout_add(2000, self._initial_build)

    def _initial_build(self) -> bool:
        self._ready = True
        self.recalculate_grid()
        # self._fade_in()
        return False
    def _schedule_fade_in(self) -> None:
        if self._fade_in_timer is not None:
            GLib.source_remove(self._fade_in_timer)
        self._fade_in_timer = GLib.timeout_add(300, self._do_fade_in)

    def _do_fade_in(self) -> bool:
        self._fade_in_timer = None
        self._fade_in()
        return False
    def _on_fade_value(self, animator, _) -> None:
        self._fixed.set_opacity(animator.value)

    def _on_fade_finished(self, animator) -> None:
        self._fixed.set_opacity(1.0)

    def _fade_in(self) -> None:
        if self._fade_animator.playing:
            return
        self._fade_out_animator.pause()
        self._fade_animator.value = self._fixed.get_opacity()
        self._fade_animator.min_value = self._fixed.get_opacity()
        self._fade_animator.max_value = 1.0
        self._fade_animator.play()

    def _fade_out(self) -> None:
        self._fade_animator.pause()
        self._fade_out_animator.min_value = 0.0
        self._fade_out_animator.max_value = self._fixed.get_opacity()
        self._fade_out_animator.value = self._fixed.get_opacity()
        self._fade_out_animator.play()

    def _on_fade_out_value(self, animator, _) -> None:
        self._fixed.set_opacity(animator.value)

    def _on_fade_out_finished(self, animator) -> None:
        self._fixed.set_opacity(0.0)
    def _on_button_press(self, widget, event: Gdk.EventButton) -> bool:
        if event.button != 3:
            return False

        from services.singletons import bar_manager

        menu = Gtk.Menu()

        bar_count = sum(
            1
            for bar in bar_manager._bars.values()
            if bar.monitor_id == self._monitor_id
        )

        if bar_count < 2:
            add_item = Gtk.MenuItem(label="Add Bar")
            add_item.connect(
                "activate",
                lambda _: bar_manager.add_bar_for_monitor(Gdk.Display.get_default().get_monitor(self._monitor_id)),
            )
            menu.append(add_item)
        else:
            item = Gtk.MenuItem(label="Maximum bars (2) reached on this monitor")
            item.set_sensitive(False)
            menu.append(item)

        if user_options.theme.blur:
            popup_with_blur(menu, event)
        else:
            menu.show_all()
            menu.popup_at_pointer(event)

        return True

    def _setup_drag_and_drop(self) -> None:
        self.drag_dest_set(Gtk.DestDefaults.ALL, [], Gdk.DragAction.COPY)
        self.drag_dest_set_target_list(Gtk.TargetList.new([]))
        target_list = self.drag_dest_get_target_list()
        if target_list:
            target_list.add_text_targets(0)
            target_list.add_uri_targets(0)

        self.connect("drag-data-received", self._on_drag_data_received)
        self.connect("drag-motion",        self._on_drag_motion)
        self.connect("drag-drop",          self._on_drag_drop)

    def _on_drag_motion(self, widget, context, x, y, timestamp) -> bool:
        Gdk.drag_status(context, Gdk.DragAction.COPY, timestamp)
        return True

    def _on_drag_drop(self, widget, context, x, y, timestamp) -> bool:
        for target in context.list_targets():
            name = target.name()
            if name in ("text/uri-list", "text/plain", "STRING"):
                self.drag_get_data(context, Gdk.Atom.intern(name, False), timestamp)
                return True
        return False

    def _on_drag_data_received(self, widget, context, x, y, data, info, timestamp) -> None:
        if data and data.get_data():
            text = data.get_data().decode("utf-8", errors="ignore")
            for line in text.strip().splitlines():
                line = line.strip()
                if line and not line.startswith("#"):
                    text = line
                    break

            path = unquote(text.replace("file://", "").strip())

            if path.lower().endswith((".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif")):
                alloc = self.get_allocation()
                nx = x / alloc.width  if alloc.width  > 0 else 0.5
                ny = 1.0 - (y / alloc.height if alloc.height > 0 else 0.5)
                nx = max(0.0, min(1.0, nx))
                ny = max(0.0, min(1.0, ny))

                logger.info(f"Drop on monitor {self._monitor_id}: {path!r} at ({nx:.3f}, {ny:.3f})")

                wallpaper.set_wallpaper(path, pos=(nx, ny))

        context.finish(True, False, timestamp)


    def _on_size_allocate(self, widget, alloc: Gdk.Rectangle) -> None:
        if not self._ready or self._in_size_allocate:
            return

        w, h = alloc.width, alloc.height
        if w < 1 or h < 1:
            return

        if w != self._old_w or h != self._old_h:
            self._old_w = w
            self._old_h = h
            if self._recalc_in_progress:
                self._pending_recalc = True
                return
            if self._fade_in_timer is not None:
                GLib.source_remove(self._fade_in_timer)
                self._fade_in_timer = None
            if self._recalc_timer is not None:
                GLib.source_remove(self._recalc_timer)
                self._recalc_timer = None

            # Only start a fade-out if we're not already doing one
            # self._fade_animator.pause()
            if self._fade_out_animator.value != 0:
                self._fade_out()

            self._recalc_timer = GLib.timeout_add(300, self._deferred_recalc)
    def _deferred_recalc(self) -> bool:
        self._recalc_timer = None
        self._recalc_in_progress = True
        self._fixed.hide()
        GLib.timeout_add(50, self._do_window_resize)
        return False
    
    def _do_window_resize(self) -> bool:
        self._in_size_allocate = True
        self.hide()
        self.show()
        GLib.timeout_add(50, self._do_recalc)
        return False

    def _do_recalc(self) -> bool:
        self._in_size_allocate = False
        self.recalculate_grid()
        self._fixed.set_opacity(0.0)
        self._fixed.show()
        self._recalc_in_progress = False

        if self._pending_recalc:
            self._pending_recalc = False
            self._old_w = 0
            self._old_h = 0
            self._fade_out()
            self._recalc_timer = GLib.timeout_add(300, self._deferred_recalc)
        else:
            self._schedule_fade_in()

        return False
    
    def recalculate_grid(self) -> None:
        alloc = self.get_allocation()
        w, h = alloc.width, alloc.height
        if w < 1 or h < 1:
            return
        new_cols  = max(2, (w // CELL_STEP) & ~1)
        new_pad_x = (w - (new_cols * CELL_STEP - GAP)) // 2
        new_rows  = max(1, (h - new_pad_x * 2 - GAP) // CELL_STEP)
        new_pad_y = new_pad_x

        if new_cols != self._cols or new_rows != self._rows:
            self._cols  = new_cols
            self._rows  = new_rows
            self._pad_x = new_pad_x
            self._pad_y = new_pad_y
            user_options.desktop_canvas.resolve(self._monitor_id, self._cols, self._rows)
            user_options.save()
            self._reposition_all()
            # self._force_refresh()
        else:
            self._pad_x = new_pad_x
            self._pad_y = new_pad_y

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

    @property
    def cols(self) -> int:
        return self._cols

    @property
    def rows(self) -> int:
        return self._rows

    def rebuild(self) -> None:
        for widget in self._children.values():
            self._fixed.remove(widget)
            widget.destroy()
        self._children.clear()

        entries = user_options.desktop_canvas.get_applets(self._monitor_id)
        for entry in entries:
            key = entry["key"]
            cls = DESKTOP_APPLET_WIDGETS.get(key)
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
        # self._force_refresh()

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
            # self._force_refresh()
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
        remove_item.connect(
            "activate",
            lambda _: DesktopAppletService.get_instance().remove(self._monitor_id, key),
        )
        menu.append(remove_item)
        menu.show_all()
        menu.popup_at_pointer(event)
        return True

    # def _force_refresh(self):
    #     # Niri needs this
    #     self.hide()
    #     self.show_all()
    #     return False

# --------------------------------------------------------------------------- #
#  Service                                                                     #
# --------------------------------------------------------------------------- #

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
        win = self._windows.get(monitor_id)
        cols = win.cols if win and win.cols > 0 else 1
        rows = win.rows if win and win.rows > 0 else 1
        ry = grid_y / rows

        placed = user_options.desktop_canvas.place(monitor_id, key, grid_x, grid_y, cols, ry)
        if not placed:
            return False
        user_options.save()
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