import cairo
from gi.repository import Gtk, GLib
from fabric.widgets.box import Box
from snippets.animator import Animator


class DashReveal(Box):

    SCALE_START = 0.8

    def __init__(
        self,
        child: Gtk.Widget | None = None,
        open_bezier: tuple[float, float, float, float] = (0.05, 0.9, 0.1, 1.0),
        close_bezier: tuple[float, float, float, float] = (0.16, 1.0, 0.3, 1.0),
        open_duration: float = 0.25,
        close_duration: float = 0.22,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self._progress = 0.0
        self._target = 0.0
        self._on_close_callbacks: list = []
        self._cached_surface: cairo.ImageSurface | None = None
        self.progress_cb = None
        
        self.open_bezier = open_bezier
        self.close_bezier = close_bezier
        self.open_duration = open_duration
        self.close_duration = close_duration

        self.active_animator = None

        if child:
            self.add(child)

        self.set_app_paintable(True)
        self.show_all()

    def _update_cache(self):
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

    def _set_progress(self, value: float):
        self._progress = max(0.0, min(value, 1.0))
        if hasattr(self, 'progress_cb') and self.progress_cb:
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

    @property
    def progress(self) -> float:
        return self._progress

    def do_draw(self, cr: cairo.Context) -> bool:
        p = self._progress
        if p <= 0.0:
            return True

        if p >= 1.0 and self._cached_surface is None:
            return Gtk.Box.do_draw(self, cr)

        w = self.get_allocated_width()
        h = self.get_allocated_height()

        scale = self.SCALE_START + (1.0 - self.SCALE_START) * p

        cx = w / 2.0
        cy = h / 2.0

        cr.save()
        cr.translate(cx, cy)
        cr.scale(scale, scale)
        cr.translate(-cx, -cy)

        if self._cached_surface:
            cr.set_source_surface(self._cached_surface, 0, 0)
            cr.paint_with_alpha(p)
        else:
            Gtk.Box.do_draw(self, cr)

        cr.restore()
        return True