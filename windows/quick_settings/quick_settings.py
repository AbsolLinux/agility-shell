from fabric.widgets.box import Box
from fabric.widgets.button import Button
from snippets import Applet, AppletPage, Icon
from icons import BatteryIcon
from services.singletons import brightness, battery
from .buttons import WifiButton, BluetoothButton, AirplaneModeButton, RecordButton, DarkModeButton, KeyboardButton, ScreenshotButton, NightModeButton, CaffieneButton, PowerModes
from .sliders import BrightnessSlider, VolumeSlider, MicrophoneSlider
from .menus import WifiMenu, BluetoothMenu, AudioMenu, KeyboardMenu, ScreenshotMenu, LogoutMenu, PowerMenu


class QuickSettingsMenu(AppletPage):
    def __init__(self, stack, **kwargs):
        super().__init__(
            first=True,
            header_left_children=Button(
                style_classes=["applet-misc-button", "battery"],
                child=BatteryIcon(size=16, percent=True) if battery and battery.available else Icon(icon_name="lightning-duotone"),
                on_clicked=lambda *_: stack.set_visible_child_name("power"),
            ),
            header_right_children=Button(
                style_classes=["applet-misc-button"],
                child=Icon(icon_name="power-duotone", icon_size=16),
                on_clicked=lambda *_: stack.set_visible_child_name("logout"),
            ),
            child=Box(
                orientation="v",
                spacing=12,
                children=[
                    Box(
                        orientation="v",
                        spacing=12,
                        children=[
                            VolumeSlider(stack=stack),
                            BrightnessSlider() if brightness and brightness.backend else MicrophoneSlider(stack=stack),
                        ],
                    ),
                    Box(
                        spacing=12,
                        children=[
                            Box(
                                orientation="v",
                                spacing=12,
                                children=[
                                    WifiButton(stack=stack),
                                    AirplaneModeButton(),
                                    DarkModeButton(),
                                    Box(
                                        spacing=12,
                                        children=[
                                            NightModeButton(),
                                            CaffieneButton(),
                                        ],
                                    ),
                                ],
                            ),
                            Box(
                                orientation="v",
                                spacing=12,
                                children=[
                                    BluetoothButton(stack=stack),
                                    ScreenshotButton(stack=stack),
                                    RecordButton(),
                                    PowerModes(),
                                ],
                            ),
                        ],
                    ),
                ],
            ),
            **kwargs,
        )


class QuickSettings(Applet):
    def __init__(self, parent, **kwargs):
        super().__init__(
            main_menu=QuickSettingsMenu(self),
            **kwargs,
        )
        self.add_menu("wifi", WifiMenu)
        self.add_menu("bt", BluetoothMenu)
        self.add_menu("audio", AudioMenu)
        self.add_menu("screenshot", ScreenshotMenu)
        self.add_menu("kb", KeyboardMenu)
        self.add_named(LogoutMenu(self, parent), "logout")
        self.add_menu("power", PowerMenu)