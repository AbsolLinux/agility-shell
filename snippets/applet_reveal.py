import math
import cairo
from typing import Literal, Callable
from gi.repository import Gtk
from fabric.widgets.box import Box
from snippets.animator import Animator


class AppletReveal(Box):
    SCALE_START = 0.6

    def __init__(
        self,
        direction: Literal["down", "up"] = "down",
        child: Gtk.Widget | None = None,
        open_bezier: tuple[float, float, float, float] = (0.16, 1.0, 0.3, 1.0),
        close_bezier: tuple[float, float, float, float] = (0.16, 1.0, 0.3, 1.0),
        open_duration: float = 0.22,
        close_duration: float = 0.16,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self._direction = direction
        self._progress = 0.0
        self._target = 0.0
        self._on_close_callbacks: list = []
        self.progress_cb: Callable[[float], None] | None = None

        self.open_bezier = open_bezier
        self.close_bezier = close_bezier
        self.open_duration = open_duration
        self.close_duration = close_duration

        self._cached_surface: cairo.ImageSurface | None = None
        self.active_animator: Animator | None = None
        self.show_all()

        if child:
            self.add(child)

        self.set_app_paintable(True)

    def _update_cache(self):
        """Snapshots the applet hierarchy into a static Cairo surface."""
        w = self.get_allocated_width()
        h = self.get_allocated_height()
        if w <= 1 or h <= 1:
            return

        self._cached_surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, w, h)
        cr = cairo.Context(self._cached_surface)
        Gtk.Box.do_draw(self, cr)

    def _clear_cache(self):
        self._cached_surface = None

    def open(self):
        """Animate the applet in. Safe to call mid-close."""
        self._target = 1.0

        if self.active_animator:
            self.active_animator.pause()
            self.active_animator = None

        self._update_cache()

        start_val = self._progress
        end_val = 1.0
        distance = abs(end_val - start_val)

        if distance < 0.001:
            self._set_progress(1.0)
            self._clear_cache()
            return

        effective_duration = max(0.01, self.open_duration * distance)

        self.active_animator = (
            Animator(
                bezier_curve=self.open_bezier,
                duration=effective_duration,
                min_value=start_val,
                max_value=end_val,
                tick_widget=self,
            )
            .build()
            .unwrap()
        )

        self.active_animator.connect(
            "notify::value", lambda a, _: self._set_progress(a.value)
        )
        self.active_animator.connect("finished", self._on_open_finished)
        self.active_animator.play()

    def close(self, on_done=None):
        """Animate the applet out. on_done called when animation finishes."""
        self._target = 0.0

        if on_done:
            def _once(*_):
                on_done()
                try:
                    self._on_close_callbacks.remove(_once)
                except ValueError:
                    pass
            self._on_close_callbacks.append(_once)

        if self.active_animator:
            self.active_animator.pause()
            self.active_animator = None

        self._update_cache()

        start_val = self._progress
        end_val = 0.0
        distance = abs(end_val - start_val)

        if distance < 0.001:
            self._set_progress(0.0)
            self._on_close_finished()
            return

        effective_duration = max(0.01, self.close_duration * distance)

        self.active_animator = (
            Animator(
                bezier_curve=self.close_bezier,
                duration=effective_duration,
                min_value=start_val,
                max_value=end_val,
                tick_widget=self,
            )
            .build()
            .unwrap()
        )

        self.active_animator.connect(
            "notify::value", lambda a, _: self._set_progress(a.value)
        )
        self.active_animator.connect("finished", self._on_close_finished)
        self.active_animator.play()

    @property
    def direction(self) -> str:
        return self._direction

    @direction.setter
    def direction(self, value: Literal["down", "up"]):
        self._direction = value
        self.queue_draw()

    @property
    def progress(self) -> float:
        return self._progress

    def _set_progress(self, value: float):
        self._progress = max(0.0, min(value, 1.0))
        if self.progress_cb:
            self.progress_cb(self._progress)
        self.queue_draw()

    def _on_open_finished(self, *_):
        self._set_progress(1.0)
        self._clear_cache()

    def _on_close_finished(self, *_):
        self._set_progress(0.0)
        self._clear_cache()
        if self._target == 0.0:
            for cb in self._on_close_callbacks:
                cb()

    def do_draw(self, cr: cairo.Context) -> bool:
        p = self._progress
        if p <= 0.0:
            return True

        # When fully open and not animating, draw live widget tree for input/hover events
        if p >= 1.0 and self._cached_surface is None:
            return Gtk.Box.do_draw(self, cr)

        w = self.get_allocated_width()
        h = self.get_allocated_height()

        scale = self.SCALE_START + (1.0 - self.SCALE_START) * p

        anchor_x = w / 2.0
        anchor_y = 0.0 if self._direction == "down" else float(h)

        cr.save()

        cr.translate(anchor_x, anchor_y)
        cr.scale(scale, scale)
        cr.translate(-anchor_x, -anchor_y)

        if self._cached_surface:
            cr.set_source_surface(self._cached_surface, 0, 0)
            cr.paint_with_alpha(p)
        else:
            Gtk.Box.do_draw(self, cr)

        cr.restore()
        return True