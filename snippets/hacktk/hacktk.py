import math
import cairo
from cffi import FFI
from typing import cast
from fabric.widgets.stack import Stack
from fabric.widgets.revealer import Revealer
from snippets.animator import Animator
from fabric.utils import get_relative_path

ffi = FFI()

ffi.cdef("""
    typedef struct _GtkStack GtkStack;
    typedef struct _GtkRevealer GtkRevealer;

    // Stack functions
    void gtk_stack_begin_transition (GtkStack *stack, int transition_type);
    void gtk_stack_set_timeline      (GtkStack *stack, double p, int transition_type);
    void gtk_stack_end_transition    (GtkStack *stack);

    // Revealer functions
    void gtk_revealer_set_timeline   (GtkRevealer *revealer, double pos);
    void gtk_revealer_finish_transition(GtkRevealer *revealer);
    void gtk_revealer_fix_windows(GtkRevealer *revealer, double pos);

""")

import os
import subprocess

_so_path = get_relative_path("./lib/libhacktk.so")
if not os.path.exists(_so_path):
    _makefile_dir = get_relative_path("./lib")
    if os.path.exists(os.path.join(_makefile_dir, "Makefile")):
        try:
            subprocess.run(["make", "-C", _makefile_dir], check=True, capture_output=True)
        except Exception:
            pass

libhacktk = ffi.dlopen(_so_path)

SLIDE_LEFT_RIGHT = 2

class HackedStack(Stack):
    def __init__(
        self,
        bezier_curve: tuple[float, float, float, float] = (0, 1.67, 1, -0.67),
        duration: float = 1.5,
        **kwargs,
    ):
        super().__init__(transition_duration=500, **kwargs)

        self._ptr = ffi.cast("GtkStack *", hash(self))
        self._bezier_curve = bezier_curve
        self._transition_direction = 4

        self.animator = (
            Animator(
                bezier_curve=bezier_curve,
                duration=duration,
                min_value=0.0,
                max_value=1.0,
                tick_widget=self,
                notify_value=lambda p, *_: libhacktk.gtk_stack_set_timeline(
                    self._ptr, p.value, self._transition_direction
                ),
            )
            .build()
            .unwrap()
        )
        self.animator.connect("finished", lambda *_: libhacktk.gtk_stack_end_transition(self._ptr))

    def set_visible_child_name(self, name: str):
        if self.get_visible_child_name() == name:
            return
        super().set_visible_child_name(name)
        libhacktk.gtk_stack_begin_transition(self._ptr, SLIDE_LEFT_RIGHT)
        self.animator.pause()
        self.animator.play()

    def do_draw(self, cr: cairo.Context):
        cr.save()
        width = self.get_allocated_width()
        height = self.get_allocated_height()
        radius = cast(
            int,
            self.get_style_context().get_property(
                "border-radius", self.get_state_flags()
            ),
        )
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
        cr.clip()
        Stack.do_draw(self, cr)
        cr.restore()
        return True

    @property
    def bezier_curve(self):
        return self._bezier_curve

    @bezier_curve.setter
    def bezier_curve(self, value: tuple[float, float, float, float]):
        self._bezier_curve = value
        self.animator.bezier_curve = value

class HackedRevealer(Revealer):
    def __init__(
        self,
        bezier_curve: tuple[float, float, float, float] = (0, 1.67, 1, -0.67),
        duration: float = 0.45,
        **kwargs,
    ):
        super().__init__(**kwargs)

        self._ptr = ffi.cast("GtkRevealer *", hash(self))
        self._bezier_curve = bezier_curve
        self._reveal_child = False
        self._animating = False
        self._current_pos = 0.0

        self._progress_cb = None

        self.animator = (
            Animator(
                bezier_curve=bezier_curve,
                duration=duration,
                min_value=0.0,
                max_value=1.0,
                tick_widget=self,
            )
            .build()
            .unwrap()
        )
        self.animator.connect("notify::value", self._on_animator_value)
        self.animator.connect("finished", self._on_animation_finished)
        self.connect("size-allocate", self._on_size_allocate)

    def _on_animator_value(self, animator, _pspec):
        self._current_pos = animator.value
        libhacktk.gtk_revealer_set_timeline(self._ptr, animator.value)
        if self._progress_cb:
            self._progress_cb(animator.value)
    def _on_size_allocate(self, widget, allocation):
        if not self._animating:
            return
        libhacktk.gtk_revealer_fix_windows(self._ptr, self._current_pos)

    def _on_animation_finished(self, *args):
        self._animating = False
        if not self._reveal_child:
            libhacktk.gtk_revealer_finish_transition(self._ptr)
            super().set_reveal_child(False)

    def set_reveal_child(self, reveal: bool):
        if not hasattr(self, 'animator'):
            return super().set_reveal_child(reveal)

        if self._reveal_child == reveal:
            if not self._animating:
                return
            return

        self._reveal_child = reveal
        self._animating = True
        self.animator.pause()

        start_pos = self._current_pos
        if reveal:
            self.animator.min_value = start_pos
            self.animator.max_value = 1.0
            self.animator.value = start_pos
            super().set_reveal_child(True)
        else:
            self.animator.min_value = start_pos
            self.animator.max_value = 0.0
            self.animator.value = start_pos

        self.animator._start_time = None
        self.animator.play()

    def toggle(self):
        self.set_reveal_child(not self._reveal_child)