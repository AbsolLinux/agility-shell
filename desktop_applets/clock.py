import datetime
from fabric.widgets.box import Box
from fabric.widgets.circularprogressbar import CircularProgressBar
from fabric.widgets.label import Label
from fabric.widgets.overlay import Overlay
from gi.repository import Gtk, GLib



class DesktopClock(Box):
    def __init__(self):
        self.clock_progress = CircularProgressBar(
            style_classes=["progress-bar"],
            start_angle=270,
            end_angle=630,
            size=(138, 138),
            line_width=6,
            min_value=0,
            max_value=60,
            value=0,
        )
        self.clock_label = Label(style_classes="lockscreen-clock-label")
        self.clock_label.set_xalign(0.5)
        self.clock_label.set_justify(Gtk.Justification.CENTER)
        self.clock_circle = Overlay(
            child=Box(
                style_classes=["lockscreen-clock"],
                h_expand=False,
                h_align="center",
                children=self.clock_progress,
            ),
            overlays=self.clock_label,
        )
        super().__init__(
            children=self.clock_circle
        )
        GLib.timeout_add(1000, self._update_time)
        self._update_time()

    def _update_time(self):
        now = datetime.datetime.now()
        self.clock_label.set_label(now.strftime("%H\n%M"))
        self.clock_progress.value = int(now.strftime("%S"))
        return True