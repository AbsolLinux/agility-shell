from fabric.widgets.label import Label
from services.singletons import bluetooth
from .button import QSButton
from icons import BluetoothIcon

class BluetoothButton(QSButton):
    def __init__(self, stack, **kwargs):
        super().__init__(
            icon=BluetoothIcon(size=16),
            label=Label(label="Bluetooth"),
            on_activate=lambda _: bluetooth.set_property("enabled", True),
            on_deactivate=lambda _: bluetooth.set_property("enabled", False),
            menu_name="bt",
            stack=stack,
            **kwargs,
        )

        bluetooth.connect(
            "notify::state",
            lambda obj, _: setattr(
                self,
                "active",
                obj.state in ["on", "discovering"],
            ),
        )
        self.active = bluetooth.state in ["on", "discovering"]