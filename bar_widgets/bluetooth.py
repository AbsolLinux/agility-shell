from .base import BaseButton, VARIANT_ICON, VARIANT_ICON_LABEL, VARIANT_LABEL
from icons import BluetoothIcon
from services.singletons import bluetooth

class BluetoothButton(BaseButton):
    VARIANTS = [VARIANT_ICON, VARIANT_ICON_LABEL, VARIANT_LABEL]

    def __init__(self, monitor_id, vertical, variant=None, **kwargs):
        self._bt_icon = BluetoothIcon(16)
        super().__init__(
            icon=self._bt_icon,
            label="Bluetooth",
            variant=variant or VARIANT_ICON,
            **kwargs,
        )
        bluetooth.connect("changed", self._sync)
        bluetooth.connect("notify::state", self._sync)
        bluetooth.connect("notify::enabled", self._sync)
        bluetooth.connect("notify::connected-devices", self._sync)
        self._sync()

    def _sync(self, *_):
        is_on = bluetooth.enabled or bluetooth.state in ["on", "discovering"]
        connected = bluetooth.connected_devices
        for cls in ("bt-off", "bt-on", "bt-connected", "active"):
            self.remove_style_class(cls)
            child = self.get_child()
            if child:
                child.remove_style_class(cls)

        if connected:
            self.add_style_class("bt-connected")
            child = self.get_child()
            if child:
                child.add_style_class("bt-connected")
            name = connected[0].name or connected[0].alias or "Connected"
            self._update_label(name)
        elif is_on:
            self.add_style_class("bt-on")
            child = self.get_child()
            if child:
                child.add_style_class("bt-on")
            self._update_label("On")
        else:
            self.add_style_class("bt-off")
            child = self.get_child()
            if child:
                child.add_style_class("bt-off")
            self._update_label("Off")
 