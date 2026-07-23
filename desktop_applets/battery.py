import datetime
from fabric.widgets.box import Box
from fabric.widgets.circularprogressbar import CircularProgressBar
from fabric.widgets.label import Label
from fabric.widgets.overlay import Overlay
from gi.repository import Gtk, GLib
from services.singletons import battery
from icons import BatteryIcon

class DesktopBattery(Box):
    def __init__(self):
        self.clock_progress = CircularProgressBar(
            style_classes=["progress-bar"],
            start_angle=90,
            end_angle=450,
            size=(138, 138),
            line_width=6,
            min_value=0,
            max_value=100,
            value=0,
        )
        self.battery_label = Label(h_expand=True, h_align="center", style_classes="desktop-battery-label", label="100%")
        self.battery_label.set_xalign(0.5)
        self.battery_label.set_justify(Gtk.Justification.CENTER)
        self.battery = Overlay(
            child=Box(
                style_classes=["lockscreen-clock"],
                h_expand=False,
                h_align="center",
                children=self.clock_progress,
            ),
            overlays=Box(style="min-width: 60px;", h_expand=True, h_align="center", v_expand=True, v_align="center", orientation="v", spacing=4, children=[BatteryIcon(size=40, percent=False, h_align="center", h_expand=True), self.battery_label]),
        )
        super().__init__(
            children=self.battery
        )
        battery.connect("changed", self._update)
        if battery.available:
            GLib.timeout_add(1000, self._update)

    def _update(self, *_):
        bat = battery.percent
        self.battery_label.set_label(f"{round(bat)}%")
        self.clock_progress.value = round(bat)
        return False