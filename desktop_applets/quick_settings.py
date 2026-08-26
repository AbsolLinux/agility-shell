from gi.repository import Gtk, GLib
from fabric.widgets.box import Box
from fabric.widgets.label import Label
from fabric.widgets.button import Button
from snippets import Icon
from services.singletons import network, bluetooth, night_mode, caffeine
from user_options import user_options

class QuickToggleTile(Button):
    def __init__(self, icon_name: str, label: str, on_toggle, is_active_getter):
        self._on_toggle = on_toggle
        self._is_active_getter = is_active_getter
        self.icon = Icon(icon_name=icon_name, icon_size=18)
        self.label = Label(label=label, style="font-size: 11px; font-weight: 600;")

        box = Box(
            orientation="v",
            spacing=4,
            h_align="center",
            v_align="center",
            children=[self.icon, self.label],
        )

        super().__init__(
            child=box,
            style_classes=["option-selection-button"],
            h_expand=True,
            v_expand=True,
            on_clicked=self._clicked,
        )
        self.sync()

    def _clicked(self, *_):
        self._on_toggle()
        GLib.timeout_add(100, self.sync)

    def sync(self):
        active = self._is_active_getter()
        if active:
            self.add_style_class("active")
        else:
            self.remove_style_class("active")
        return False

class DesktopQuickSettings(Box):
    def __init__(self, **kwargs):
        self.title_label = Label(
            label="Quick Controls",
            style="font-size: 13px; font-weight: 700;",
            h_align="start",
        )

        header = Box(
            orientation="h",
            spacing=8,
            children=[
                Icon(icon_name="sliders-horizontal-duotone", icon_size=18),
                self.title_label,
            ],
        )

        # Tiles
        self.wifi_tile = QuickToggleTile(
            "wifi-high-duotone",
            "Wi-Fi",
            lambda: network.wifi.toggle_wifi() if getattr(network, "wifi", None) else None,
            lambda: bool(getattr(network, "wifi", None) and network.wifi.enabled),
        )
        self.bt_tile = QuickToggleTile(
            "bluetooth-duotone",
            "Bluetooth",
            lambda: bluetooth.toggle_power() if hasattr(bluetooth, "toggle_power") else setattr(bluetooth, "enabled", not bluetooth.enabled),
            lambda: bool(getattr(bluetooth, "enabled", False) or getattr(bluetooth, "state", "") == "on"),
        )
        self.night_tile = QuickToggleTile(
            "moon-stars-duotone",
            "Night Light",
            lambda: night_mode.toggle(),
            lambda: bool(night_mode.enabled),
        )
        self.caffeine_tile = QuickToggleTile(
            "coffee-duotone",
            "Caffeine",
            lambda: caffeine.toggle(),
            lambda: bool(caffeine.enabled),
        )

        row1 = Box(orientation="h", spacing=6, h_expand=True, children=[self.wifi_tile, self.bt_tile])
        row2 = Box(orientation="h", spacing=6, h_expand=True, children=[self.night_tile, self.caffeine_tile])

        grid = Box(orientation="v", spacing=6, h_expand=True, v_expand=True, children=[row1, row2])

        super().__init__(
            orientation="v",
            spacing=10,
            style_classes=["desktop-applet"],
            h_expand=True,
            v_expand=True,
            children=[header, grid],
            **kwargs,
        )

        if hasattr(network, "connect"):
            network.connect("changed", lambda *_: self.wifi_tile.sync())
        if hasattr(bluetooth, "connect"):
            bluetooth.connect("changed", lambda *_: self.bt_tile.sync())
        night_mode.connect("notify::enabled", lambda *_: self.night_tile.sync())
        caffeine.connect("notify::enabled", lambda *_: self.caffeine_tile.sync())
