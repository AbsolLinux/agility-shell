import cairo
from urllib.parse import unquote

import gi
gi.require_version("Gtk", "3.0")
import math
from gi.repository import Gtk, Gdk, GLib, GtkLayerShell
from fabric.core.service import Service, Signal
from fabric.widgets.wayland import WaylandWindow
from fabric.widgets.box import Box
from fabric.widgets.label import Label
from fabric.widgets.overlay import Overlay
from loguru import logger

from user_options import user_options
from utils.helpers import popup_with_blur
from desktop_applets import DESKTOP_APPLET_SIZES, DESKTOP_APPLET_WIDGETS, DESKTOP_CANVAS_SIZES
from .themes import wallpaper
from snippets import Animator, disable_blur, free_blur, set_blur_regions_from_widget, enable_blur, trace_widget_regions, Icon
from snippets.blur.blur import set_blur_regions

CELL      = 81
GAP       = 12
CELL_STEP = CELL + GAP  # 93

_APPLET_TARGET = Gtk.TargetEntry.new("text/plain", Gtk.TargetFlags.SAME_APP, 0)


def _applet_pixel_size(key: str, span_x: int | None = None, span_y: int | None = None) -> tuple[int, int]:
    base_cols, base_rows = DESKTOP_CANVAS_SIZES.get(key, (1, 1))
    cols = span_x if span_x is not None else base_cols
    rows = span_y if span_y is not None else base_rows
    w = cols * 2 * CELL + (cols * 2 - 1) * GAP
    h = rows * 2 * CELL + (rows * 2 - 1) * GAP
    return w, h


def _applet_cell_size(key: str, span_x: int | None = None, span_y: int | None = None) -> tuple[int, int]:
    """Return the (cols, rows) cell footprint for a canvas applet key."""
    base_cols, base_rows = DESKTOP_CANVAS_SIZES.get(key, (1, 1))
    cols = span_x if span_x is not None else base_cols
    rows = span_y if span_y is not None else base_rows
    return cols * 2, rows * 2


def _grid_to_pixel(grid_x: int, grid_y: int) -> tuple[int, int]:
    return grid_x * CELL_STEP, grid_y * CELL_STEP


def _fits(grid_x: int, grid_y: int, key: str, cols: int, rows: int, span_x: int | None = None, span_y: int | None = None) -> bool:
    cc, cr = _applet_cell_size(key, span_x, span_y)
    return grid_x + cc <= cols and grid_y + cr <= rows


def _conflicts(
    grid_x: int, grid_y: int, key: str,
    placed: list[dict], cols: int, rows: int,
    ignore_key: str | None = None,
    span_x: int | None = None, span_y: int | None = None,
) -> bool:
    cc, cr = _applet_cell_size(key, span_x, span_y)
    new_cells = {
        (grid_x + dx, grid_y + dy)
        for dx in range(cc)
        for dy in range(cr)
    }
    for entry in placed:
        if ignore_key and entry["key"] == ignore_key:
            continue
        ec, er = _applet_cell_size(entry["key"], entry.get("span_x"), entry.get("span_y"))
        existing = {
            (entry["grid_x"] + dx, entry["grid_y"] + dy)
            for dx in range(ec)
            for dy in range(er)
        }
        if new_cells & existing:
            return True
    return False


def _render_shape(cr: cairo.Context, x: float, y: float, w: float, h: float, radius: float) -> None:
    cr.new_sub_path()
    cr.arc(x + w - radius, y + radius,         radius, -math.pi / 2, 0)
    cr.arc(x + w - radius, y + h - radius,     radius, 0,             math.pi / 2)
    cr.arc(x + radius,     y + h - radius,     radius, math.pi / 2,  math.pi)
    cr.arc(x + radius,     y + radius,         radius, math.pi,      3 * math.pi / 2)
    cr.close_path()


class _CanvasDrawingArea(Gtk.DrawingArea):
    _PREVIEW_CLASS         = "desktop-applet-preview"
    _PREVIEW_VALID_CLASS   = "valid"
    _PREVIEW_INVALID_CLASS = "invalid"

    def __init__(self, window: "DesktopAppletWindow"):
        super().__init__()
        self._win = window
        self.set_hexpand(True)
        self.set_vexpand(True)

        self.add_events(Gdk.EventMask.LEAVE_NOTIFY_MASK)
        self.connect("draw",               self._on_draw)
        self.connect("leave-notify-event", self._on_leave)

    def _get_color(self, name: str) -> tuple[float, float, float, float]:
        ctx = self._win.get_style_context()
        found, color = ctx.lookup_color(name)
        if found:
            return color.red, color.green, color.blue, color.alpha
        return (1.0, 1.0, 1.0, 0.08)

    def _get_preview_styles(self, valid: bool) -> tuple[tuple, tuple, float]:
        ctx = self.get_style_context()
        ctx.add_class(self._PREVIEW_CLASS)
        if valid:
            ctx.add_class(self._PREVIEW_VALID_CLASS)
            ctx.remove_class(self._PREVIEW_INVALID_CLASS)
        else:
            ctx.add_class(self._PREVIEW_INVALID_CLASS)
            ctx.remove_class(self._PREVIEW_VALID_CLASS)

        bg     = ctx.get_background_color(self.get_state_flags())
        border = ctx.get_border_color(self.get_state_flags())
        radius = ctx.get_property("border-radius", self.get_state_flags())

        ctx.remove_class(self._PREVIEW_CLASS)
        ctx.remove_class(self._PREVIEW_VALID_CLASS)
        ctx.remove_class(self._PREVIEW_INVALID_CLASS)

        return (
            (bg.red,     bg.green,     bg.blue,     bg.alpha),
            (border.red, border.green, border.blue, border.alpha),
            float(radius if isinstance(radius, (int, float)) else 12.0),
        )

    def _on_leave(self, widget, event: Gdk.EventCrossing) -> bool:
        win = self._win
        if win._ph_grid_x is not None:
            win._ph_grid_x = None
            win._ph_grid_y = None
            win._ph_valid  = False
            self.queue_draw()
        return False

    def _on_draw(self, widget, cr: cairo.Context) -> bool:
        win = self._win
        if win._cols == 0 or win._rows == 0:
            return False

        empty_r,    empty_g,    empty_b,    empty_a    = self._get_color("canvas-empty")
        occupied_r, occupied_g, occupied_b, occupied_a = self._get_color("canvas-occupied")
        border_r,   border_g,   border_b,   border_a   = self._get_color("canvas-border")

        placed = user_options.desktop_canvas.get_applets(win._monitor_id)

        occupied: set[tuple[int, int]] = set()
        for entry in placed:
            if entry["key"] == win._dragging_key:
                continue
            ec, er = _applet_cell_size(entry["key"], entry.get("span_x"), entry.get("span_y"))
            for dx in range(ec):
                for dy in range(er):
                    occupied.add((entry["grid_x"] + dx, entry["grid_y"] + dy))

        cell_radius = 6.0

        for gy in range(win._rows):
            for gx in range(win._cols):
                px = win._pad_x + gx * CELL_STEP
                py = win._pad_y + gy * CELL_STEP

                if (gx, gy) in occupied:
                    cr.set_source_rgba(occupied_r, occupied_g, occupied_b, occupied_a)
                else:
                    cr.set_source_rgba(empty_r, empty_g, empty_b, empty_a)
                _render_shape(cr, px, py, CELL, CELL, cell_radius)
                cr.fill()

                cr.set_source_rgba(border_r, border_g, border_b, border_a)
                _render_shape(cr, px, py, CELL, CELL, cell_radius)
                cr.set_line_width(1.0)
                cr.stroke()

        if win._ph_grid_x is not None and win._dragging_key is not None:
            px = win._pad_x + win._ph_grid_x * CELL_STEP
            py = win._pad_y + win._ph_grid_y * CELL_STEP
            pw, ph = _applet_pixel_size(win._dragging_key, getattr(win, "_dragging_span_x", None), getattr(win, "_dragging_span_y", None))

            bg_rgba, border_rgba, preview_radius = self._get_preview_styles(win._ph_valid)

            # Fill
            cr.set_source_rgba(*bg_rgba)
            _render_shape(cr, px, py, pw, ph, preview_radius)
            cr.fill()

            # Border
            cr.set_source_rgba(*border_rgba)
            _render_shape(cr, px, py, pw, ph, preview_radius)
            cr.set_line_width(2.0)
            cr.stroke()

        return False



class DesktopAppletWindow(WaylandWindow):

    def __init__(self, monitor_id: int) -> None:
        self._monitor_id   = monitor_id
        self._fixed        = Gtk.Fixed()
        self._children: dict[str, Gtk.Widget] = {}

        self._pad_x = 0
        self._pad_y = 0
        self._cols  = 12
        self._rows  = 6
        self._old_w = 0
        self._old_h = 0

        self._recalc_in_progress = False
        self._pending_recalc     = False
        self._recalc_timer: int | None = None
        self._ready              = True
        self._blur_ctx = None

        self._canvas_active  = False
        self._dragging_key: str | None = None
        self._drag_origin: tuple[int, int] | None = None
        self._dragging_span_x: int | None = None
        self._dragging_span_y: int | None = None
        self._resizing_key: str | None = None
        self._resize_start_pos: tuple[float, float] | None = None
        self._resize_start_span: tuple[int, int] | None = None
        self._resize_start_pixels: tuple[int, int] | None = None
        self._ph_grid_x: int | None = None
        self._ph_grid_y: int | None = None
        self._ph_valid:  bool       = False

        self._canvas_da = _CanvasDrawingArea(self)
        self._canvas_da.set_no_show_all(True)

        self._overlay = Overlay(h_expand=True, v_expand=True)
        self._overlay.add(self._fixed)
        self._overlay.add_overlay(self._canvas_da)
        self._overlay.set_overlay_pass_through(self._canvas_da, True)

        self._root = Box(h_expand=True, v_expand=True)
        self._root.add(self._overlay)

        super().__init__(
            monitor=monitor_id,
            anchor="left right top bottom",
            exclusivity="ignore",
            layer="bottom",
            child=self._root,
            visible=True,
            title="agility-shell-desktop-applets",
        )

        self.connect("size-allocate",      self._on_size_allocate)
        self.connect("button-press-event", self._on_button_press)
        self._setup_drag_and_drop()
        self.show_all()
        self._canvas_da.hide()
        
        GLib.timeout_add(100, self._initial_build)

    def _initial_build(self) -> bool:
        self._ready = True
        self.recalculate_grid()
        self.rebuild()
        return False

    def _apply_blur(self) -> None:
        if not user_options.theme.blur:
            return
        from .singletons import style_service

        style_service.connect("notify::style-changed", self._retrace_blur)

        self._blur_ctx = enable_blur(self)
        if not self._blur_ctx:
            return

        self._retrace_blur()

    def _retrace_blur(self) -> None:
        if not self._blur_ctx:
            return

        rects = []
        for key, eb in self._children.items():
            if not eb.get_visible():
                continue
            coords = eb.translate_coordinates(self, 0, 0)
            if not coords:
                continue
            cx, cy = coords
            traced = trace_widget_regions(eb, accuracy=1, erode=0)
            for r in traced:
                rects.append((cx + r.x, cy + r.y, r.width, r.height))

        if not rects:
            disable_blur(self._blur_ctx)
            free_blur(self._blur_ctx)
            self._blur_ctx = None
            return

        set_blur_regions(self._blur_ctx, rects)

    def _show_canvas(self) -> None:
        self._overlay.set_overlay_pass_through(self._canvas_da, False)
        self._canvas_da.show()
        self._canvas_da.queue_draw()

    def _hide_canvas(self) -> None:
        self._overlay.set_overlay_pass_through(self._canvas_da, True)
        self._canvas_da.hide()

    def enter_canvas_mode(self, key: str, origin: tuple[int, int] | None = None, span_x: int | None = None, span_y: int | None = None) -> None:
        self._canvas_active = True
        self._dragging_key  = key
        self._drag_origin   = origin
        self._dragging_span_x = span_x
        self._dragging_span_y = span_y
        self._ph_grid_x     = None
        self._ph_grid_y     = None
        self._ph_valid      = False

        try:
            GtkLayerShell.set_layer(self, GtkLayerShell.Layer.OVERLAY)
        except Exception:
            self.layer = "overlay"

        self._show_canvas()

    def exit_canvas_mode(self, restore: bool = False) -> None:
        if restore and self._drag_origin is not None and self._dragging_key is not None:
            key = self._dragging_key
            gx, gy = self._drag_origin
            DesktopAppletService.get_instance().place(self._monitor_id, key, gx, gy, span_x=self._dragging_span_x, span_y=self._dragging_span_y)

        self._canvas_active = False
        self._dragging_key  = None
        self._drag_origin   = None
        self._dragging_span_x = None
        self._dragging_span_y = None
        self._ph_grid_x     = None
        self._ph_grid_y     = None
        self._ph_valid      = False

        try:
            GtkLayerShell.set_layer(self, GtkLayerShell.Layer.BOTTOM)
        except Exception:
            self.layer = "bottom"
        self._hide_canvas()

    def _xy_to_grid(self, x: float, y: float) -> tuple[int, int]:
        gx = max(0, min(self._cols - 1, int((x - self._pad_x) / CELL_STEP)))
        gy = max(0, min(self._rows - 1, int((y - self._pad_y) / CELL_STEP)))
        return gx, gy
    
    def _on_canvas_drag_motion(self, widget, ctx, x, y, time):
        key = self._dragging_key
        if key is None:
            Gdk.drag_status(ctx, 0, time)
            return True

        gx, gy = self._xy_to_grid(x, y)
        placed  = user_options.desktop_canvas.get_applets(self._monitor_id)

        valid = (
            _fits(gx, gy, key, self._cols, self._rows, span_x=self._dragging_span_x, span_y=self._dragging_span_y)
            and not _conflicts(gx, gy, key, placed, self._cols, self._rows,
                               ignore_key=key, span_x=self._dragging_span_x, span_y=self._dragging_span_y)
        )

        if gx != self._ph_grid_x or gy != self._ph_grid_y or valid != self._ph_valid:
            self._ph_grid_x = gx
            self._ph_grid_y = gy
            self._ph_valid  = valid
            self._canvas_da.queue_draw()

        Gdk.drag_status(ctx, Gdk.DragAction.MOVE if valid else 0, time)
        return True

    def _on_canvas_drag_leave(self, widget, ctx, time):
        self._ph_grid_x = None
        self._ph_grid_y = None
        self._ph_valid  = False
        self._canvas_da.queue_draw()

    def _on_canvas_drag_received(self, widget, ctx, x, y, data_obj, info, time):
        payload = data_obj.get_text() or ""
        parts   = payload.split(":")
        if len(parts) != 2 or parts[0] != "applet":
            Gtk.drag_finish(ctx, False, False, time)
            return

        key = parts[1]
        if key not in DESKTOP_APPLET_SIZES:
            Gtk.drag_finish(ctx, False, False, time)
            return

        gx, gy = self._xy_to_grid(x, y)
        placed  = user_options.desktop_canvas.get_applets(self._monitor_id)

        span_x = getattr(self, "_dragging_span_x", None)
        span_y = getattr(self, "_dragging_span_y", None)

        if not _fits(gx, gy, key, self._cols, self._rows, span_x=span_x, span_y=span_y):
            Gtk.drag_finish(ctx, False, False, time)
            self.exit_canvas_mode(restore=False)
            return

        if _conflicts(gx, gy, key, placed, self._cols, self._rows, ignore_key=key, span_x=span_x, span_y=span_y):
            Gtk.drag_finish(ctx, False, False, time)
            self.exit_canvas_mode(restore=False)
            return

        DesktopAppletService.get_instance().remove(self._monitor_id, key)
        DesktopAppletService.get_instance().place(self._monitor_id, key, gx, gy, span_x=span_x, span_y=span_y)

        from utils.sounds import play_sound
        play_sound("widget-placed")

        self._drop_success = True
        Gtk.drag_finish(ctx, True, False, time)
        self.exit_canvas_mode()

        DesktopAppletService.get_instance().canvas_drop_complete(self._monitor_id)

    def _on_size_allocate(self, widget, alloc: Gdk.Rectangle) -> None:
        if not self._ready:
            return
        w, h = alloc.width, alloc.height
        if w < 1 or h < 1:
            return
        if w != self._old_w or h != self._old_h:
            self._old_w = w
            self._old_h = h
            self.recalculate_grid()

    def recalculate_grid(self) -> None:
        alloc = self.get_allocation()
        w, h = alloc.width, alloc.height
        if w < 1 or h < 1:
            return
        new_cols  = max(2, (w // CELL_STEP) & ~1)
        new_pad_x = (w - (new_cols * CELL_STEP - GAP)) // 2
        new_rows  = max(1, (h - new_pad_x - GAP) // CELL_STEP)
        new_pad_y = new_pad_x
        if new_cols != self._cols or new_rows != self._rows:
            self._cols  = new_cols
            self._rows  = new_rows
            self._pad_x = new_pad_x
            self._pad_y = new_pad_y
            user_options.desktop_canvas.resolve(self._monitor_id, self._cols, self._rows)
            user_options.save()
            self._reposition_all()
        else:
            self._pad_x = new_pad_x
            self._pad_y = new_pad_y
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
        GLib.idle_add(self._retrace_blur)

    @property
    def cols(self) -> int:
        return self._cols

    @property
    def rows(self) -> int:
        return self._rows

    def _build_applet_entry(self, entry: dict) -> Gtk.EventBox | None:
        key = entry["key"]
        cls = DESKTOP_APPLET_WIDGETS.get(key)
        if cls is None:
            logger.warning(f"[DesktopAppletService] unknown applet key {key!r}")
            return None
        try:
            span_x = entry.get("span_x")
            span_y = entry.get("span_y")
            w_px, h_px = _applet_pixel_size(key, span_x, span_y)

            variant = entry.get("variant")
            if variant:
                try:
                    widget = cls(variant=variant)
                except TypeError:
                    widget = cls()
                    if hasattr(widget, "set_variant"):
                        widget.set_variant(variant)
            else:
                widget = cls()

            widget.set_size_request(w_px, h_px)

            theme = entry.get("theme") or user_options.desktop_canvas.get_theme(self._monitor_id, key) or "normal"
            color = entry.get("color") or user_options.desktop_canvas.get_color(self._monitor_id, key) or ""
            op = entry.get("opacity")
            if op is None:
                op = getattr(user_options.settings, "desktop_widget_opacity", 1.0)

            # Apply classes to widget
            if hasattr(widget, "get_style_context"):
                ctx = widget.get_style_context()
                ctx.add_class("desktop-applet")
                ctx.add_class(f"desktop-applet-surface-{theme}")
                if (span_x and span_x > 1) or key in ("Weather", "Media"):
                    ctx.add_class("large")

            # Apply custom styles (opacity, custom color)
            custom_css = []
            if color:
                custom_css.append(f"* {{ color: {color}; }}")
            if op < 1.0:
                custom_css.append(f"* {{ opacity: {op:.2f}; }}")
            
            if custom_css and hasattr(widget, "set_style"):
                widget.set_style(" ".join(custom_css))

            overlay = Overlay(h_expand=True, v_expand=True)
            overlay.set_size_request(w_px, h_px)
            overlay.add(widget)

            eb = Gtk.EventBox()
            eb.set_size_request(w_px, h_px)
            eb.add(overlay)
            eb.connect("button-press-event", self._on_applet_right_click, key)
            eb.show_all()

            self._setup_applet_drag(eb, key)
            return eb
        except Exception as e:
            logger.error(f"[DesktopAppletService] failed to build {key!r}: {e}")
            return None

    def _on_resize_handle_press(self, widget, event: Gdk.EventButton, key: str) -> bool:
        if event.button != 1:
            return False
        placed = user_options.desktop_canvas.get_applets(self._monitor_id)
        entry = next((e for e in placed if e["key"] == key), None)
        if not entry:
            return False
        base_cols, base_rows = DESKTOP_CANVAS_SIZES.get(key, (1, 1))
        cur_span_x = entry.get("span_x", base_cols)
        cur_span_y = entry.get("span_y", base_rows)

        self._resizing_key = key
        self._resize_start_pos = (event.x_root, event.y_root)
        self._resize_start_span = (cur_span_x, cur_span_y)
        self._resize_start_pixels = _applet_pixel_size(key, cur_span_x, cur_span_y)

        self._ph_grid_x = entry["grid_x"]
        self._ph_grid_y = entry["grid_y"]
        self._dragging_key = key
        self._dragging_span_x = cur_span_x
        self._dragging_span_y = cur_span_y
        self._ph_valid = True

        self._show_canvas()
        self._canvas_da.queue_draw()
        return True

    def _on_resize_handle_motion(self, widget, event: Gdk.EventMotion, key: str) -> bool:
        if self._resizing_key != key or not self._resize_start_pos or not self._resize_start_pixels:
            return False

        dx = event.x_root - self._resize_start_pos[0]
        dy = event.y_root - self._resize_start_pos[1]

        init_w, init_h = self._resize_start_pixels
        cur_w = max(100, init_w + dx)
        cur_h = max(100, init_h + dy)

        cand_span_x = max(1, min(6, round((cur_w + GAP) / (2 * CELL_STEP))))
        cand_span_y = max(1, min(4, round((cur_h + GAP) / (2 * CELL_STEP))))

        placed = user_options.desktop_canvas.get_applets(self._monitor_id)
        entry = next((e for e in placed if e["key"] == key), None)
        if not entry:
            return False

        gx = entry["grid_x"]
        gy = entry["grid_y"]

        valid = (
            _fits(gx, gy, key, self._cols, self._rows, span_x=cand_span_x, span_y=cand_span_y)
            and not _conflicts(gx, gy, key, placed, self._cols, self._rows, ignore_key=key, span_x=cand_span_x, span_y=cand_span_y)
        )

        if cand_span_x != self._dragging_span_x or cand_span_y != self._dragging_span_y or valid != self._ph_valid:
            self._dragging_span_x = cand_span_x
            self._dragging_span_y = cand_span_y
            self._ph_valid = valid
            self._canvas_da.queue_draw()

        return True

    def _on_resize_handle_release(self, widget, event: Gdk.EventButton, key: str) -> bool:
        if self._resizing_key != key:
            return False

        target_span_x = self._dragging_span_x
        target_span_y = self._dragging_span_y
        valid = self._ph_valid

        self._resizing_key = None
        self._resize_start_pos = None
        self._resize_start_span = None
        self._resize_start_pixels = None
        self._dragging_span_x = None
        self._dragging_span_y = None
        self._ph_grid_x = None
        self._ph_grid_y = None
        self._dragging_key = None
        self._ph_valid = False
        self._hide_canvas()

        if valid and target_span_x and target_span_y:
            DesktopAppletService.get_instance().set_applet_size(self._monitor_id, key, target_span_x, target_span_y)
            from utils.sounds import play_sound
            play_sound("widget-placed")

        return True

    def rebuild(self) -> None:
        for widget in list(self._children.values()):
            self._fixed.remove(widget)
            widget.destroy()
        self._children.clear()

        entries = user_options.desktop_canvas.get_applets(self._monitor_id)
        for entry in entries:
            eb = self._build_applet_entry(entry)
            if eb:
                self._fixed.put(eb, 0, 0)
                self._children[entry["key"]] = eb

        self._reposition_all()
        self._fixed.show_all()
        self._overlay.show_all()
        self._canvas_da.hide()

    def add_applet(self, key: str, grid_x: int, grid_y: int) -> None:
        if key in self._children:
            self.remove_applet(key)
        placed = user_options.desktop_canvas.get_applets(self._monitor_id)
        entry = next((e for e in placed if e["key"] == key), None)
        if not entry:
            entry = {"key": key, "grid_x": grid_x, "grid_y": grid_y}
        eb = self._build_applet_entry(entry)
        if eb:
            self._fixed.put(eb, 0, 0)
            self._children[key] = eb
            self._reposition_all()
            eb.show_all()
            self._fixed.show_all()
            self._canvas_da.hide()

            if not self._blur_ctx and user_options.theme.blur:
                self._apply_blur()

    def remove_applet(self, key: str) -> None:
        eb = self._children.pop(key, None)
        if eb:
            self._fixed.remove(eb)
            eb.destroy()
            self._reposition_all()
            GLib.idle_add(self._retrace_blur)

    def resize_applet(self, key: str, span_x: int, span_y: int) -> None:
        eb = self._children.get(key)
        if not eb:
            return
        w_px, h_px = _applet_pixel_size(key, span_x, span_y)
        eb.set_size_request(w_px, h_px)
        overlay = eb.get_child()
        if overlay:
            overlay.set_size_request(w_px, h_px)
            widget = overlay.get_child()
            if widget:
                widget.set_size_request(w_px, h_px)
        self._reposition_all()
        GLib.idle_add(self._retrace_blur)

    def apply_applet_opacity(self, key: str, opacity: float) -> None:
        eb = self._children.get(key)
        if not eb:
            return
        overlay = eb.get_child()
        if not overlay:
            return
        widget = overlay.get_child()
        if widget and hasattr(widget, "set_style"):
            color = user_options.desktop_canvas.get_color(self._monitor_id, key)
            custom_css = []
            if color:
                custom_css.append(f"@define-color primary {color}; @define-color accent {color}; @define-color on_primary #FFFFFF; * {{ color: @primary; }}")
            if opacity < 1.0:
                custom_css.append(f"* {{ opacity: {opacity:.2f}; }}")
            widget.set_style(" ".join(custom_css))

    def apply_applet_theme(self, key: str, theme: str) -> None:
        eb = self._children.get(key)
        if not eb:
            return
        overlay = eb.get_child()
        if not overlay:
            return
        widget = overlay.get_child()
        if widget and hasattr(widget, "get_style_context"):
            ctx = widget.get_style_context()
            for t in ("normal", "blur", "glassy", "transparent", "amoled", "tonal"):
                ctx.remove_class(f"desktop-applet-surface-{t}")
            ctx.add_class(f"desktop-applet-surface-{theme}")
        GLib.idle_add(self._retrace_blur)

    def apply_applet_color(self, key: str, color: str) -> None:
        eb = self._children.get(key)
        if not eb:
            return
        overlay = eb.get_child()
        if not overlay:
            return
        widget = overlay.get_child()
        if widget and hasattr(widget, "set_style"):
            op = user_options.desktop_canvas.get_opacity(self._monitor_id, key)
            if op is None:
                op = getattr(user_options.settings, "desktop_widget_opacity", 1.0)
            custom_css = []
            if color:
                custom_css.append(f"* {{ color: {color}; }}")
            if op < 1.0:
                custom_css.append(f"* {{ opacity: {op:.2f}; }}")
            widget.set_style(" ".join(custom_css))

    def apply_applet_variant(self, key: str, variant: str) -> None:
        eb = self._children.get(key)
        if not eb:
            return
        overlay = eb.get_child()
        if not overlay:
            return
        widget = overlay.get_child()
        if widget and hasattr(widget, "set_variant"):
            widget.set_variant(variant)

    def _setup_applet_drag(self, eb: Gtk.EventBox, key: str) -> None:
        eb.drag_source_set(
            Gdk.ModifierType.BUTTON1_MASK,
            [_APPLET_TARGET],
            Gdk.DragAction.MOVE,
        )
        target_list = eb.drag_source_get_target_list()
        if target_list:
            target_list.add_text_targets(0)

        eb.connect("drag-begin",    self._on_applet_drag_begin,    key)
        eb.connect("drag-data-get", self._on_applet_drag_data_get, key)
        eb.connect("drag-end",      self._on_applet_drag_end,      key)
        eb.connect("drag-failed",   self._on_applet_drag_failed,   key)

    def _on_applet_drag_begin(self, eb, ctx, key: str) -> None:
        placed = user_options.desktop_canvas.get_applets(self._monitor_id)
        entry = next((e for e in placed if e["key"] == key), None)
        origin = (entry["grid_x"], entry["grid_y"]) if entry else None
        span_x = entry.get("span_x") if entry else None
        span_y = entry.get("span_y") if entry else None
        eb.hide()
        self._drop_success = False
        self.enter_canvas_mode(key, origin=origin, span_x=span_x, span_y=span_y)

    def _on_applet_drag_data_get(self, eb, ctx, data_obj, info, time, key: str) -> None:
        data_obj.set_text(f"applet:{key}", -1)

    def _on_applet_drag_end(self, eb, ctx, key: str) -> None:
        if self._drop_success:
            eb.hide()
        else:
            eb.show()
            if self._canvas_active and self._dragging_key == key:
                self.exit_canvas_mode(restore=False)
        GLib.idle_add(self._retrace_blur)

    def _on_applet_drag_failed(self, eb, ctx, result, key: str) -> bool:
        eb.show()
        if self._canvas_active and self._dragging_key == key:
            self.exit_canvas_mode(restore=False)
            GLib.idle_add(self._retrace_blur)
        return True

    def _on_applet_right_click(self, eb, event: Gdk.EventButton, key: str) -> bool:
        if event.button != 3:
            return False
        menu = Gtk.Menu()
        menu.set_reserve_toggle_size(False)
        placed = user_options.desktop_canvas.get_applets(self._monitor_id)
        entry = next((e for e in placed if e["key"] == key), None)

        # Header Title
        title_item = Gtk.MenuItem()
        title_box = Box(orientation="h", spacing=6)
        title_icon = Icon(icon_name="gear-six-duotone", icon_size=14)
        title_lbl = Label(label=f"{key} Widget", style="font-weight: 700; font-size: 13px;")
        title_box.add(title_icon)
        title_box.add(title_lbl)
        title_item.add(title_box)
        title_item.set_sensitive(False)
        menu.append(title_item)

        sep_header = Gtk.SeparatorMenuItem()
        menu.append(sep_header)

        # 1. Widget Style / Variant Submenu
        variants_list = None
        if key == "Clock":
            from desktop_applets.clock import DESKTOP_CLOCK_VARIANTS
            variants_list = DESKTOP_CLOCK_VARIANTS
        elif key == "Calendar":
            from desktop_applets.date import DESKTOP_DATE_VARIANTS
            variants_list = DESKTOP_DATE_VARIANTS
        elif key == "Weather":
            from desktop_applets.weather import DESKTOP_WEATHER_VARIANTS
            variants_list = DESKTOP_WEATHER_VARIANTS
        elif key == "Energy":
            from desktop_applets.battery import DESKTOP_BATTERY_VARIANTS
            variants_list = DESKTOP_BATTERY_VARIANTS
        elif key == "Media":
            from desktop_applets.media import DESKTOP_MEDIA_VARIANTS
            variants_list = DESKTOP_MEDIA_VARIANTS
        elif key == "SysMon":
            from desktop_applets.sysmon import DESKTOP_SYSMON_VARIANTS
            variants_list = DESKTOP_SYSMON_VARIANTS
        elif key == "Settings":
            from desktop_applets.quick_settings import DESKTOP_QUICK_SETTINGS_VARIANTS
            variants_list = DESKTOP_QUICK_SETTINGS_VARIANTS
        elif key == "Volume":
            from desktop_applets.volume import DESKTOP_VOLUME_VARIANTS
            variants_list = DESKTOP_VOLUME_VARIANTS
        elif key == "Brightness":
            from desktop_applets.brightness import DESKTOP_BRIGHTNESS_VARIANTS
            variants_list = DESKTOP_BRIGHTNESS_VARIANTS

        if variants_list:
            style_item = Gtk.MenuItem(label="Widget Style")
            style_sub = Gtk.Menu()
            style_sub.set_reserve_toggle_size(False)
            current_var = entry.get("variant", variants_list[0][0]) if entry else variants_list[0][0]
            for v_key, v_label in variants_list:
                lbl = f"✓  {v_label}" if current_var == v_key else f"    {v_label}"
                it = Gtk.MenuItem(label=lbl)
                it.connect("activate", lambda _, vk=v_key, k=key: DesktopAppletService.get_instance().set_applet_variant(self._monitor_id, k, vk))
                style_sub.append(it)
            style_item.set_submenu(style_sub)
            menu.append(style_item)

        # 2. Surface Theme Submenu
        theme_item = Gtk.MenuItem(label="Surface Theme")
        theme_sub = Gtk.Menu()
        theme_sub.set_reserve_toggle_size(False)
        current_theme = user_options.desktop_canvas.get_theme(self._monitor_id, key)

        themes = [
            ("Normal (Solid)", "normal"),
            ("Blur (Frosted Glass)", "blur"),
            ("Glassy (Glossy Translucent)", "glassy"),
            ("Transparent (Outlined)", "transparent"),
            ("AMOLED Stark (Nothing Black)", "amoled"),
            ("Material Tonal (Pixel Soft)", "tonal"),
        ]
        for t_label, t_key in themes:
            lbl = f"✓  {t_label}" if current_theme == t_key else f"    {t_label}"
            it = Gtk.MenuItem(label=lbl)
            it.connect("activate", lambda _, tk=t_key, k=key: DesktopAppletService.get_instance().set_applet_theme(self._monitor_id, k, tk))
            theme_sub.append(it)
        theme_item.set_submenu(theme_sub)
        menu.append(theme_item)

        # 3. Color & Accent Submenu
        color_item = Gtk.MenuItem(label="Color & Accent")
        color_sub = Gtk.Menu()
        color_sub.set_reserve_toggle_size(False)
        current_color = user_options.desktop_canvas.get_color(self._monitor_id, key)

        colors = [
            ("System Theme (Default)", ""),
            ("🔴 Nothing Red (#EB0029)", "#EB0029"),
            ("🟠 Pixel Coral (#FF6F61)", "#FF6F61"),
            ("🟢 Mint Green (#4ECCA3)", "#4ECCA3"),
            ("🔵 Sky Blue (#38BDF8)", "#38BDF8"),
            ("🟣 Lavender (#A78BFA)", "#A78BFA"),
            ("🟡 Sunflower (#FBBF24)", "#FBBF24"),
            ("⚪ Monochrome White (#FFFFFF)", "#FFFFFF"),
            ("🔘 Minimal Slate (#64748B)", "#64748B"),
        ]
        for c_label, c_val in colors:
            is_active = (current_color.lower() == c_val.lower())
            lbl = f"✓  {c_label}" if is_active else f"    {c_label}"
            it = Gtk.MenuItem(label=lbl)
            it.connect("activate", lambda _, cv=c_val, k=key: DesktopAppletService.get_instance().set_applet_color(self._monitor_id, k, cv))
            color_sub.append(it)

        sep_col = Gtk.SeparatorMenuItem()
        color_sub.append(sep_col)

        custom_col_item = Gtk.MenuItem(label="🎨 Custom Color...")
        custom_col_item.connect("activate", lambda _, k=key: self._open_color_picker_dialog(k))
        color_sub.append(custom_col_item)

        reset_col_item = Gtk.MenuItem(label="↺ Reset Color")
        reset_col_item.connect("activate", lambda _, k=key: DesktopAppletService.get_instance().set_applet_color(self._monitor_id, k, ""))
        color_sub.append(reset_col_item)

        color_item.set_submenu(color_sub)
        menu.append(color_item)

        # 4. Opacity Submenu
        opacity_menu_item = Gtk.MenuItem(label="Opacity")
        opacity_sub = Gtk.Menu()
        opacity_sub.set_reserve_toggle_size(False)
        current_op = user_options.desktop_canvas.get_opacity(self._monitor_id, key)
        if current_op is None:
            current_op = getattr(user_options.settings, "desktop_widget_opacity", 1.0)

        presets = [
            ("100% Solid", 1.0),
            ("85% High", 0.85),
            ("70% Medium", 0.70),
            ("50% Translucent", 0.50),
            ("30% Low", 0.30),
            ("15% Dim", 0.15),
        ]
        for label, val in presets:
            lbl = f"✓  {label}" if abs(current_op - val) < 0.05 else f"    {label}"
            it = Gtk.MenuItem(label=lbl)
            it.connect("activate", lambda _, v=val, k=key: DesktopAppletService.get_instance().set_applet_opacity(self._monitor_id, k, v))
            opacity_sub.append(it)
        opacity_menu_item.set_submenu(opacity_sub)
        menu.append(opacity_menu_item)

        # 5. Size Submenu
        size_menu_item = Gtk.MenuItem(label="Size")
        size_sub = Gtk.Menu()
        size_sub.set_reserve_toggle_size(False)
        base_cols, base_rows = DESKTOP_CANVAS_SIZES.get(key, (1, 1))
        cur_sx = entry.get("span_x", base_cols) if entry else base_cols
        cur_sy = entry.get("span_y", base_rows) if entry else base_rows

        size_presets = [
            ("1 × 1 Compact", 1, 1),
            ("2 × 1 Wide", 2, 1),
            ("1 × 2 Tall", 1, 2),
            ("2 × 2 Large", 2, 2),
            ("3 × 2 Extra Wide", 3, 2),
            ("4 × 2 Panoramic", 4, 2),
        ]
        gx = entry["grid_x"] if entry else 0
        gy = entry["grid_y"] if entry else 0

        for label, sx, sy in size_presets:
            is_cur = (cur_sx == sx and cur_sy == sy)
            lbl = f"✓  {label}" if is_cur else f"    {label}"
            it = Gtk.MenuItem(label=lbl)
            fits = _fits(gx, gy, key, self._cols, self._rows, span_x=sx, span_y=sy)
            conflicts = _conflicts(gx, gy, key, placed, self._cols, self._rows, ignore_key=key, span_x=sx, span_y=sy)
            if not fits or conflicts:
                if not is_cur:
                    it.set_sensitive(False)
            it.connect("activate", lambda _, s_x=sx, s_y=sy, k=key: DesktopAppletService.get_instance().set_applet_size(self._monitor_id, k, s_x, s_y))
            size_sub.append(it)

        size_menu_item.set_submenu(size_sub)
        menu.append(size_menu_item)

        sep = Gtk.SeparatorMenuItem()
        menu.append(sep)

        remove_item = Gtk.MenuItem(label=f"✕  Remove {key}")
        remove_item.connect(
            "activate",
            lambda _: DesktopAppletService.get_instance().remove(self._monitor_id, key),
        )
        menu.append(remove_item)

        if user_options.theme.blur:
            popup_with_blur(menu, event)
        else:
            menu.show_all()
            menu.popup_at_pointer(event)
        return True

    def _open_color_picker_dialog(self, key: str):
        dialog = Gtk.ColorChooserDialog(title=f"Choose Color for {key}", transient_for=None)
        current_color_str = user_options.desktop_canvas.get_color(self._monitor_id, key)
        if current_color_str:
            rgba = Gdk.RGBA()
            if rgba.parse(current_color_str):
                dialog.set_rgba(rgba)
        
        response = dialog.run()
        if response == Gtk.ResponseType.OK:
            chosen_rgba = dialog.get_rgba()
            hex_color = f"#{int(chosen_rgba.red*255):02x}{int(chosen_rgba.green*255):02x}{int(chosen_rgba.blue*255):02x}"
            DesktopAppletService.get_instance().set_applet_color(self._monitor_id, key, hex_color)
        dialog.destroy()

    def _on_button_press(self, widget, event: Gdk.EventButton) -> bool:
        if event.button != 3:
            return False

        from services.singletons import bar_manager
        from windows.dash.settings import WIDGET_ICONS

        menu = Gtk.Menu()
        menu.set_reserve_toggle_size(False)

        # Add Applet Submenu
        applet_item = Gtk.MenuItem(label="Add Applet")
        applet_sub = Gtk.Menu()
        applet_sub.set_reserve_toggle_size(False)

        gx, gy = self._xy_to_grid(event.x, event.y)
        placed = user_options.desktop_canvas.get_applets(self._monitor_id)
        placed_keys = {e["key"] for e in placed}

        for key in DESKTOP_APPLET_WIDGETS.keys():
            item = Gtk.MenuItem()
            box = Box(orientation="h", spacing=8)
            icon_name = WIDGET_ICONS.get(key, "app-window-duotone")
            icon = Icon(icon_name=icon_name, icon_size=16)
            lbl = Label(label=key)
            box.add(icon)
            box.add(lbl)
            item.add(box)

            if key in placed_keys:
                item.set_sensitive(False)
                lbl.set_text(f"{key} (Placed)")

            def _on_add_applet(_, applet_key=key, target_gx=gx, target_gy=gy):
                cur_placed = user_options.desktop_canvas.get_applets(self._monitor_id)
                if not _fits(target_gx, target_gy, applet_key, self._cols, self._rows) or _conflicts(target_gx, target_gy, applet_key, cur_placed, self._cols, self._rows):
                    found = False
                    for try_y in range(self._rows):
                        for try_x in range(self._cols):
                            if _fits(try_x, try_y, applet_key, self._cols, self._rows) and not _conflicts(try_x, try_y, applet_key, cur_placed, self._cols, self._rows):
                                target_gx, target_gy = try_x, try_y
                                found = True
                                break
                        if found:
                            break
                DesktopAppletService.get_instance().place(self._monitor_id, applet_key, target_gx, target_gy)
                from utils.sounds import play_sound
                play_sound("widget-placed")

            item.connect("activate", _on_add_applet)
            applet_sub.append(item)

        applet_item.set_submenu(applet_sub)
        menu.append(applet_item)

        sep = Gtk.SeparatorMenuItem()
        menu.append(sep)

        bar_count = sum(
            1 for bar in bar_manager._bars.values()
            if bar.monitor_id == self._monitor_id
        )

        if bar_count < 2:
            add_item = Gtk.MenuItem(label="Add Bar")
            add_item.connect(
                "activate",
                lambda _: bar_manager.add_bar_for_monitor(
                    Gdk.Display.get_default().get_monitor(self._monitor_id)
                ),
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
        self.drag_dest_set(
            Gtk.DestDefaults.ALL,
            [_APPLET_TARGET],
            Gdk.DragAction.MOVE | Gdk.DragAction.COPY,
        )
        target_list = self.drag_dest_get_target_list()
        if target_list:
            target_list.add_text_targets(0)
            target_list.add_uri_targets(0)
        self.connect("drag-motion",        self._on_drag_motion)
        self.connect("drag-leave",         self._on_drag_leave)
        self.connect("drag-data-received", self._on_drag_data_received)

    def _on_drag_motion(self, widget, ctx, x, y, time) -> bool:
        targets = [t.name() for t in ctx.list_targets()]
        if "text/plain" in targets and self._canvas_active:
            return self._on_canvas_drag_motion(widget, ctx, x, y, time)
        Gdk.drag_status(ctx, Gdk.DragAction.COPY, time)
        return True

    def _on_drag_leave(self, widget, ctx, time) -> None:
        if self._canvas_active:
            self._on_canvas_drag_leave(widget, ctx, time)

    def _on_drag_data_received(self, widget, ctx, x, y, data, info, time) -> None:
        payload = (data.get_text() or "") if data else ""
        if payload.startswith("applet:"):
            parts = payload.split(":")
            if len(parts) == 2:
                self._on_canvas_drag_received(widget, ctx, x, y, data, info, time)
            else:
                Gtk.drag_finish(ctx, False, False, time)
            return

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
        ctx.finish(True, False, time)
        
    def destroy(self) -> None:
        if self._blur_ctx:
            disable_blur(self._blur_ctx)
            free_blur(self._blur_ctx)
            self._blur_ctx = None
        super().destroy()

class DesktopAppletService(Service):
    _instance: "DesktopAppletService | None" = None

    @staticmethod
    def get_instance() -> "DesktopAppletService":
        if DesktopAppletService._instance is None:
            DesktopAppletService._instance = DesktopAppletService()
        return DesktopAppletService._instance

    @Signal
    def applets_changed(self, monitor_id: int) -> None: ...

    @Signal
    def canvas_drop_complete(self, monitor_id: int) -> None: ...

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._windows: dict[int, DesktopAppletWindow] = {}

        display = Gdk.Display.get_default()
        if display:
            display.connect("monitor-added",   self._on_monitor_added)
            display.connect("monitor-removed", self._on_monitor_removed)

        self._sync_monitors()
        for win in self._windows.values():
            win.rebuild()

        if user_options.theme.blur:
            GLib.timeout_add(2000, self._initial_blur)

    def _initial_blur(self) -> bool:
        self.apply_blur(True)
        return False

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

    def apply_blur(self, enabled: bool) -> None:
        for win in self._windows.values():
            if enabled:
                win._apply_blur()
            else:
                if win._blur_ctx:
                    disable_blur(win._blur_ctx)
                    free_blur(win._blur_ctx)
                    win._blur_ctx = None

    def place(self, monitor_id: int, key: str, grid_x: int, grid_y: int, span_x: int | None = None, span_y: int | None = None, opacity: float | None = None) -> bool:
        win  = self._windows.get(monitor_id)
        cols = win.cols if win and win.cols > 0 else 1
        rows = win.rows if win and win.rows > 0 else 1
        ry   = grid_y / rows

        placed = user_options.desktop_canvas.place(monitor_id, key, grid_x, grid_y, cols, ry, span_x=span_x, span_y=span_y, opacity=opacity)
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
        win = self._windows.get(monitor_id)
        cols = win.cols if win and win.cols > 0 else 12
        user_options.desktop_canvas.move(monitor_id, key, grid_x, grid_y, cols)
        user_options.save()
        if win:
            win.remove_applet(key)
            win.add_applet(key, grid_x, grid_y)
        self.applets_changed(monitor_id)

    def set_applet_opacity(self, monitor_id: int, key: str, opacity: float) -> None:
        user_options.desktop_canvas.set_opacity(monitor_id, key, opacity)
        user_options.save()
        win = self._windows.get(monitor_id)
        if win:
            win.apply_applet_opacity(key, opacity)

    def set_applet_theme(self, monitor_id: int, key: str, theme: str) -> None:
        user_options.desktop_canvas.set_theme(monitor_id, key, theme)
        user_options.save()
        win = self._windows.get(monitor_id)
        if win:
            win.apply_applet_theme(key, theme)

    def set_applet_color(self, monitor_id: int, key: str, color: str) -> None:
        user_options.desktop_canvas.set_color(monitor_id, key, color)
        user_options.save()
        win = self._windows.get(monitor_id)
        if win:
            win.apply_applet_color(key, color)

    def set_applet_variant(self, monitor_id: int, key: str, variant: str) -> None:
        user_options.desktop_canvas.set_variant(monitor_id, key, variant)
        user_options.save()
        win = self._windows.get(monitor_id)
        if win:
            win.apply_applet_variant(key, variant)

    def set_applet_size(self, monitor_id: int, key: str, span_x: int, span_y: int) -> bool:
        win = self._windows.get(monitor_id)
        if not win:
            return False
        placed = user_options.desktop_canvas.get_applets(monitor_id)
        entry = next((e for e in placed if e["key"] == key), None)
        if not entry:
            return False
        gx = entry["grid_x"]
        gy = entry["grid_y"]
        if not _fits(gx, gy, key, win.cols, win.rows, span_x=span_x, span_y=span_y):
            return False
        if _conflicts(gx, gy, key, placed, win.cols, win.rows, ignore_key=key, span_x=span_x, span_y=span_y):
            return False
        user_options.desktop_canvas.set_span(monitor_id, key, span_x, span_y)
        user_options.save()
        win.resize_applet(key, span_x, span_y)
        self.applets_changed(monitor_id)
        return True

    def enter_canvas_mode(self, monitor_id: int, key: str) -> None:
        """Called from the dash to begin a new placement drag."""
        win = self._windows.get(monitor_id)
        if win:
            win.enter_canvas_mode(key, origin=None)

    def exit_canvas_mode(self, monitor_id: int, restore: bool = False) -> None:
        """Called from the dash to cancel canvas mode."""
        win = self._windows.get(monitor_id)
        if win:
            win.exit_canvas_mode(restore=restore)

    def get_window(self, monitor_id: int) -> "DesktopAppletWindow | None":
        if monitor_id not in self._windows:
            self._sync_monitors()
        return self._windows.get(monitor_id)

    def apply_desktop_widget_opacity(self, opacity: float) -> None:
        opacity = max(0.0, min(1.0, float(opacity)))
        for win in self._windows.values():
            for key, eb in win._children.items():
                win.apply_applet_opacity(key, opacity)