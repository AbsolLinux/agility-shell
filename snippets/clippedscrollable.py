import math
import cairo
from typing import cast
from fabric.widgets.scrolledwindow import ScrolledWindow
from gi.repository import GLib, Gdk


class ClippingScrolledWindow(ScrolledWindow):
    BOUNCE_SPRING = 0.15     # Spring-back speed per tick (0.0–1.0, lower = bouncier)
    BOUNCE_THRESHOLD = 0.4   # Pixels from 0 at which we snap and stop
    BOUNCE_FPS = 14          # Tick interval in ms (lower = smoother)
    MAX_OVERSHOOT = 60       # Max pixels of visual overshoot allowed
    OVERSHOOT_SCALE = 20     # Pixels of overshoot per scroll delta unit
    BOUNDARY_EPSILON = 1.0   # Float tolerance for bottom boundary detection

    @staticmethod
    def render_shape(cr: cairo.Context, width: int, height: int, radius: int = 0):
        cr.move_to(radius, 0)
        cr.line_to(width - radius, 0)
        cr.arc(width - radius, radius, radius, -(math.pi / 2), 0)
        cr.line_to(width, height - radius)
        cr.arc(width - radius, height - radius, radius, 0, (math.pi / 2))
        cr.line_to(radius, height)
        cr.arc(radius, height - radius, radius, (math.pi / 2), math.pi)
        cr.line_to(0, radius)
        cr.arc(radius, radius, radius, math.pi, (3 * (math.pi / 2)))
        cr.close_path()

    def do_draw(self, cr: cairo.Context):
        cr.save()
        ClippingScrolledWindow.render_shape(
            cr,
            self.get_allocated_width(),
            self.get_allocated_height(),
            cast(
                int,
                self.get_style_context().get_property(
                    "border-radius", self.get_state_flags()
                ),
            ),
        )
        cr.clip()

        # Apply bounce offset purely at draw time — no layout changes at all
        if self._overshoot_offset != 0.0:
            cr.translate(0, self._overshoot_offset)

        ScrolledWindow.do_draw(self, cr)
        cr.restore()
        return True

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self._bounce_id = None
        self._overshoot_offset = 0.0
        self._is_bouncing = False
        self._bounce_velocity = 0.0
        self._scroll_velocity = 0.0
        self._last_adj_value = 0.0

        self.connect("map", self._on_map)
        self.connect("map", self._connect_adjustment)
        self.connect("scroll-event", self._on_scroll_event)

    def _connect_adjustment(self, _):
        adj = self.get_vadjustment()
        if adj:
            self._last_adj_value = adj.get_value()
            adj.connect("value-changed", self._on_adj_value_changed)

    def _on_adj_value_changed(self, adj):
        val = adj.get_value()
        delta = val - self._last_adj_value
        self._last_adj_value = val

        self._scroll_velocity = self._scroll_velocity * 0.6 + delta * 0.4

        lower = adj.get_lower()
        upper = adj.get_upper() - adj.get_page_size()

        at_top = val <= lower and delta < 0
        at_bottom = val >= upper - self.BOUNDARY_EPSILON and delta > 0

        if at_top or at_bottom:
            self._bounce_velocity = self._scroll_velocity * -0.5
            self._overshoot_offset = delta * -0.5
            self._overshoot_offset = max(-self.MAX_OVERSHOOT, min(self.MAX_OVERSHOOT, self._overshoot_offset))
            self._scroll_velocity = 0.0
            self._start_bounce()
            self.queue_draw()

    def _on_map(self, _):
        self.set_overlay_scrolling(False)
        self.set_overlay_scrolling(True)

    def _on_scroll_event(self, widget, event: Gdk.EventScroll):
        adj = self.get_vadjustment()
        if not adj:
            return False

        lower = adj.get_lower()
        upper = adj.get_upper() - adj.get_page_size()
        val = adj.get_value()

        if upper <= lower:
            return False

        ok, dx, dy = event.get_scroll_deltas()

        if not ok or (dx == 0.0 and dy == 0.0):
            if event.direction == Gdk.ScrollDirection.UP:
                dy = -1.0
            elif event.direction == Gdk.ScrollDirection.DOWN:
                dy = 1.0
            else:
                return False

        at_top = val <= lower and dy < 0
        at_bottom = val >= upper - self.BOUNDARY_EPSILON and dy > 0

        if at_top or at_bottom:
            self._bounce_velocity += dy * -8
            self._start_bounce()
            return True

        if self._is_bouncing:
            self._stop_bounce()

        return False

    def _start_bounce(self):
        self._is_bouncing = True
        if self._bounce_id is None:
            self._bounce_id = GLib.timeout_add(self.BOUNCE_FPS, self._bounce_tick)

    def _stop_bounce(self):
        if self._bounce_id is not None:
            GLib.source_remove(self._bounce_id)
            self._bounce_id = None
        self._overshoot_offset = 0.0
        self._is_bouncing = False
        self._scroll_velocity = 0.0
        self.queue_draw()

    def _bounce_tick(self) -> bool:
        # Apply velocity to offset
        self._overshoot_offset += self._bounce_velocity
        # Decay velocity (friction)
        self._bounce_velocity *= 0.75
        # Spring offset back to 0
        self._overshoot_offset *= (1.0 - self.BOUNCE_SPRING)

        # Clamp overshoot
        self._overshoot_offset = max(-self.MAX_OVERSHOOT, min(self.MAX_OVERSHOOT, self._overshoot_offset))

        if abs(self._overshoot_offset) < self.BOUNCE_THRESHOLD and abs(self._bounce_velocity) < 0.1:
            self._overshoot_offset = 0.0
            self._bounce_velocity = 0.0
            self._bounce_id = None
            self._is_bouncing = False
            self.queue_draw()
            return GLib.SOURCE_REMOVE

        self.queue_draw()
        return GLib.SOURCE_CONTINUE