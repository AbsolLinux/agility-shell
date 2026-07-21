import cairo
from gi.repository import Gtk, Gdk, GLib
from fabric.widgets.box import Box
from fabric.widgets.eventbox import EventBox

import bar as _bar_module
from desktop_applets import DESKTOP_APPLET_SIZES, DESKTOP_CANVAS_SIZES
from user_options import user_options
from services.desktop_applets import DesktopAppletService
CELL      = 81
GAP       = 12
CELL_STEP = CELL + GAP   # 93

_APPLET_TARGET = Gtk.TargetEntry.new("text/plain", Gtk.TargetFlags.SAME_APP, 0)


def _applet_cell_size(key: str) -> tuple[int, int]:
    cols, rows = DESKTOP_CANVAS_SIZES.get(key, (1, 1))
    return cols * 2, rows * 2


def _pixel_size(key: str) -> tuple[int, int]:
    cc, cr = _applet_cell_size(key)
    w = cc * CELL + (cc - 1) * GAP
    h = cr * CELL + (cr - 1) * GAP
    return w, h


def _fits(grid_x: int, grid_y: int, key: str, cols: int, rows: int) -> bool:
    cc, cr = _applet_cell_size(key)
    return grid_x + cc <= cols and grid_y + cr <= rows


def _conflicts(
    grid_x: int, grid_y: int, key: str,
    placed: list[dict], cols: int, rows: int,
) -> bool:
    cc, cr = _applet_cell_size(key)
    new_cells = {
        (grid_x + dx, grid_y + dy)
        for dx in range(cc)
        for dy in range(cr)
    }
    for entry in placed:
        ec, er = _applet_cell_size(entry["key"])
        existing_cells = {
            (entry["grid_x"] + dx, entry["grid_y"] + dy)
            for dx in range(ec)
            for dy in range(er)
        }
        if new_cells & existing_cells:
            return True
    return False


class DashCanvas(EventBox):
    def __init__(self, dash, monitor_id_getter):
        """
        dash              : the Dash instance (for toggling / syncing header)
        monitor_id_getter : callable() → int | None — active monitor id
        """
        self._dash             = dash
        self._monitor_id_getter = monitor_id_getter
        self._dragging_key: str | None = None

        self._ph_grid_x: int | None = None
        self._ph_grid_y: int | None = None
        self._ph_valid:  bool       = False

        self._cols   = 0
        self._rows   = 0
        self._pad_x  = 0
        self._pad_y  = 0
        self._win_w  = 0
        self._win_h  = 0

        self._drawing = Gtk.DrawingArea()
        self._drawing.set_hexpand(True)
        self._drawing.set_vexpand(True)
        self._drawing.connect("draw", self._on_draw)

        super().__init__(
            h_expand=True,
            v_expand=True,
            visible=False,
        )
        self.add(self._drawing)

        # Accept applet drags
        self.drag_dest_set(
            Gtk.DestDefaults.ALL,
            [_APPLET_TARGET],
            Gdk.DragAction.MOVE,
        )
        self.show_all()
        self.connect("drag-motion",        self._on_drag_motion)
        self.connect("drag-leave",         self._on_drag_leave)
        self.connect("drag-data-received", self._on_drag_received)
        self.connect("size-allocate",      self._on_size_allocate)

    # ── geometry ──────────────────────────────────────────────────────────

    def _on_size_allocate(self, widget, alloc: Gdk.Rectangle) -> None:
        w, h = alloc.width, alloc.height
        if w == self._win_w and h == self._win_h:
            return
        self._win_w = w
        self._win_h = h
        self._recompute_grid(w, h)
        self._drawing.queue_draw()
        
    def _recompute_grid(self, w: int, h: int) -> None:
        self._cols  = max(2, (w // CELL_STEP) & ~1)
        self._rows  = max(1, h // CELL_STEP)
        self._pad_x = (w - (self._cols * CELL_STEP - GAP)) // 2
        self._pad_y = self._pad_x

    def _xy_to_grid(self, x: float, y: float) -> tuple[int, int]:
        gx = max(0, min(self._cols - 1, int((x - self._pad_x) / CELL_STEP)))
        gy = max(0, min(self._rows - 1, int((y - self._pad_y) / CELL_STEP)))
        return gx, gy

    def _on_draw(self, widget, cr: cairo.Context) -> bool:
        if self._cols == 0 or self._rows == 0:
            return False

        empty_r,    empty_g,    empty_b,    empty_a    = self._get_canvas_color("canvas-empty")
        occupied_r, occupied_g, occupied_b, occupied_a = self._get_canvas_color("canvas-occupied")
        border_r,   border_g,   border_b,   border_a   = self._get_canvas_color("canvas-border")
        ph_valid_r, ph_valid_g, ph_valid_b, ph_valid_a = self._get_canvas_color("canvas-placeholder-valid")
        ph_invalid_r, ph_invalid_g, ph_invalid_b, ph_invalid_a = self._get_canvas_color("canvas-placeholder-invalid")
        ph_valid_border_r, ph_valid_border_g, ph_valid_border_b, ph_valid_border_a = self._get_canvas_color("canvas-placeholder-valid-border")
        ph_invalid_border_r, ph_invalid_border_g, ph_invalid_border_b, ph_invalid_border_a = self._get_canvas_color("canvas-placeholder-invalid-border")

        mid    = self._monitor_id_getter()
        placed = user_options.desktop_canvas.get_applets(mid) if mid is not None else []

        occupied: set[tuple[int, int]] = set()
        for entry in placed:
            ec, er = _applet_cell_size(entry["key"])
            for dx in range(ec):
                for dy in range(er):
                    occupied.add((entry["grid_x"] + dx, entry["grid_y"] + dy))

        ph_cells: set[tuple[int, int]] = set()
        if self._ph_grid_x is not None and self._dragging_key is not None:
            cc, cr_span = _applet_cell_size(self._dragging_key)
            for dx in range(cc):
                for dy in range(cr_span):
                    ph_cells.add((self._ph_grid_x + dx, self._ph_grid_y + dy))

        for gy in range(self._rows):
            for gx in range(self._cols):
                px = self._pad_x + gx * CELL_STEP
                py = self._pad_y + gy * CELL_STEP
                radius = 6.0
                x0, y0, x1, y1 = px, py, px + CELL, py + CELL

                def rounded_rect():
                    cr.new_sub_path()
                    cr.arc(x1 - radius, y0 + radius, radius, -1.5707963, 0)
                    cr.arc(x1 - radius, y1 - radius, radius, 0,          1.5707963)
                    cr.arc(x0 + radius, y1 - radius, radius, 1.5707963,  3.1415926)
                    cr.arc(x0 + radius, y0 + radius, radius, 3.1415926,  4.7123889)
                    cr.close_path()

                # Fill
                if (gx, gy) in ph_cells:
                    if self._ph_valid:
                        cr.set_source_rgba(ph_valid_r, ph_valid_g, ph_valid_b, ph_valid_a)
                    else:
                        cr.set_source_rgba(ph_invalid_r, ph_invalid_g, ph_invalid_b, ph_invalid_a)
                elif (gx, gy) in occupied:
                    cr.set_source_rgba(occupied_r, occupied_g, occupied_b, occupied_a)
                else:
                    cr.set_source_rgba(empty_r, empty_g, empty_b, empty_a)
                rounded_rect()
                cr.fill()

                if (gx, gy) in ph_cells:
                    if self._ph_valid:
                        cr.set_source_rgba(ph_valid_border_r, ph_valid_border_g, ph_valid_border_b, ph_valid_border_a)
                    else:
                        cr.set_source_rgba(ph_invalid_border_r, ph_invalid_border_g, ph_invalid_border_b, ph_invalid_border_a)
                else:
                    cr.set_source_rgba(border_r, border_g, border_b, border_a)
                rounded_rect()
                cr.set_line_width(1.0)
                cr.stroke()

        return False

    def _on_drag_motion(self, widget, ctx, x, y, time):
        key = _bar_module._dragging_key
        if key is None or key not in DESKTOP_APPLET_SIZES:
            Gdk.drag_status(ctx, 0, time)
            return True

        gx, gy = self._xy_to_grid(x, y)
        mid     = self._monitor_id_getter()
        placed  = user_options.desktop_canvas.get_applets(mid) if mid is not None else []

        valid = (
            _fits(gx, gy, key, self._cols, self._rows)
            and not _conflicts(gx, gy, key, placed, self._cols, self._rows)
        )

        if gx != self._ph_grid_x or gy != self._ph_grid_y or valid != self._ph_valid:
            self._ph_grid_x = gx
            self._ph_grid_y = gy
            self._ph_valid  = valid
            self._drawing.queue_draw()

        Gdk.drag_status(ctx, Gdk.DragAction.MOVE if valid else 0, time)
        return True

    def _on_drag_leave(self, widget, ctx, time):
        self._ph_grid_x = None
        self._ph_grid_y = None
        self._ph_valid  = False
        self._drawing.queue_draw()

    def _get_canvas_color(self, name: str) -> tuple[float, float, float, float]:
        ctx = self.get_style_context()
        found, color = ctx.lookup_color(name)
        if found:
            return color.red, color.green, color.blue, color.alpha
        return (1.0, 1.0, 1.0, 0.08)  # fallback
    
    def _on_drag_received(self, widget, ctx, x, y, data_obj, info, time):
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
        mid     = self._monitor_id_getter()
        placed  = user_options.desktop_canvas.get_applets(mid) if mid is not None else []

        if not _fits(gx, gy, key, self._cols, self._rows):
            Gtk.drag_finish(ctx, False, False, time)
            return
        if _conflicts(gx, gy, key, placed, self._cols, self._rows):
            Gtk.drag_finish(ctx, False, False, time)
            return

        if mid is not None:
            DesktopAppletService.get_instance().place(mid, key, gx, gy)

        from utils.sounds import play_sound
        play_sound("widget-placed")

        Gtk.drag_finish(ctx, True, False, time)

        # Exit canvas mode
        self._dash._on_canvas_drop_complete()


    def enter(self, dragging_key: str) -> None:
        """Show the canvas for the given applet being dragged."""
        self._dragging_key = dragging_key
        self._ph_grid_x    = None
        self._ph_grid_y    = None
        self._ph_valid     = False

        alloc = self.get_allocation()
        if alloc.width > 1:
            self._recompute_grid(alloc.width, alloc.height)

        self.set_visible(True)
        self._drawing.queue_draw()

    def exit(self) -> None:
        """Hide the canvas and reset state."""
        self._dragging_key = None
        self._ph_grid_x    = None
        self._ph_grid_y    = None
        self._ph_valid     = False
        self.set_visible(False)