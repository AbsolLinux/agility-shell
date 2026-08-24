from fabric.widgets.label import Label
from fabric.widgets.box import Box
from services.singletons import bluetooth
from .button import QSButton
from icons import BluetoothIcon

class BluetoothButton(QSButton):
    def __init__(self, stack, **kwargs):
        self._title_label = Label(label="Bluetooth", h_align="start")
        self._status_label = Label(label="Off", style="font-size: 11px; opacity: 0.7;", h_align="start")
        self._label_box = Box(
            orientation="v",
            spacing=0,
            children=[self._title_label, self._status_label],
        )

        super().__init__(
            icon=BluetoothIcon(size=16),
            label=self._label_box,
            on_activate=lambda _: setattr(bluetooth, "enabled", True),
            on_deactivate=lambda _: setattr(bluetooth, "enabled", False),
            menu_name="bt",
            stack=stack,
            **kwargs,
        )

        bluetooth.connect("notify::state", self._sync_state)
        bluetooth.connect("notify::enabled", self._sync_state)
        bluetooth.connect("notify::connected-devices", self._sync_state)
        bluetooth.connect("changed", self._sync_state)
        self._sync_state()

    def _sync_state(self, *_):
        is_on = bluetooth.enabled or bluetooth.state in ["on", "discovering"]
        self.active = is_on
        connected = bluetooth.connected_devices
        if connected:
            first_name = connected[0].name or connected[0].alias or "Connected"
            if len(connected) > 1:
                self._status_label.set_label(f"{first_name} (+{len(connected) - 1})")
            else:
                self._status_label.set_label(first_name)
        elif is_on:
            self._status_label.set_label("On")
        else:
            self._status_label.set_label("Off")