from gi.repository import Gtk, GLib
from fabric.widgets.box import Box
from fabric.widgets.label import Label
from fabric.widgets.button import Button
from fabric.widgets.circularprogressbar import CircularProgressBar
from fabric.widgets.overlay import Overlay
from snippets import Icon
from services.singletons import bluetooth

class DesktopBluetooth(Box):
    def __init__(self, **kwargs):
        self.progress_bar = CircularProgressBar(
            style_classes=["progress-bar"],
            start_angle=90,
            end_angle=450,
            size=(52, 52),
            line_width=4,
            min_value=0,
            max_value=100,
            value=0,
        )
        self.icon = Icon(icon_name="bluetooth-duotone", icon_size=24, h_align="center", v_align="center")
        self.progress_overlay = Overlay(
            child=self.progress_bar,
            overlays=self.icon,
        )

        self.title_label = Label(
            label="Bluetooth",
            style_classes=["desktop-system-module-label", "top"],
            v_expand=True,
            v_align="end",
            h_align="start",
        )
        self.device_label = Label(
            label="Off",
            style_classes=["desktop-system-module-label", "bottom"],
            v_expand=True,
            v_align="start",
            h_align="start",
        )

        header_box = Box(
            spacing=10,
            orientation="h",
            children=[
                self.progress_overlay,
                Box(
                    orientation="v",
                    children=[self.title_label, self.device_label],
                ),
            ],
        )

        self.toggle_btn = Button(
            child=Label(label="Turn On", style="font-size: 11px; font-weight: 600;"),
            style_classes=["option-selection-button"],
            h_expand=True,
            on_clicked=self._on_toggle,
        )

        super().__init__(
            orientation="v",
            spacing=12,
            style_classes=["desktop-applet"],
            h_expand=True,
            v_expand=True,
            children=[header_box, self.toggle_btn],
            **kwargs,
        )

        bluetooth.connect("changed", self._sync)
        bluetooth.connect("notify::enabled", self._sync)
        bluetooth.connect("notify::connected-devices", self._sync)
        self._sync()

    def _on_toggle(self, *_):
        try:
            if hasattr(bluetooth, "toggle_power"):
                bluetooth.toggle_power()
            elif hasattr(bluetooth, "enabled"):
                bluetooth.enabled = not bluetooth.enabled
        except Exception:
            pass

    def _sync(self, *_):
        is_on = getattr(bluetooth, "enabled", False) or getattr(bluetooth, "state", "") in ["on", "discovering"]
        connected = getattr(bluetooth, "connected_devices", [])

        if connected:
            self.progress_bar.value = 100
            name = getattr(connected[0], "name", None) or getattr(connected[0], "alias", "Connected")
            self.device_label.set_label(name)
            self.icon.set_property("icon-name", "bluetooth-connected-duotone")
            self.toggle_btn.set_label("Connected")
            self.toggle_btn.add_style_class("active")
        elif is_on:
            self.progress_bar.value = 50
            self.device_label.set_label("Ready / Disconnected")
            self.icon.set_property("icon-name", "bluetooth-duotone")
            self.toggle_btn.set_label("Turn Off")
            self.toggle_btn.add_style_class("active")
        else:
            self.progress_bar.value = 0
            self.device_label.set_label("Disabled")
            self.icon.set_property("icon-name", "bluetooth-slash-duotone")
            self.toggle_btn.set_label("Turn On")
            self.toggle_btn.remove_style_class("active")
