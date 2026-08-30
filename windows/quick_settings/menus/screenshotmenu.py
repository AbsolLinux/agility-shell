from fabric.widgets.box import Box
from fabric.widgets.button import Button
from fabric.widgets.label import Label
from fabric.widgets.centerbox import CenterBox
from snippets import Icon, ClippingScrolledWindow
from .menu import QSAppletPage
from services.singletons import screenshot


class ScreenshotModeButton(Button):
    def __init__(
        self,
        icon_name: str,
        title: str,
        subtitle: str,
        on_click,
        **kwargs,
    ):
        self._icon = Icon(icon_name=icon_name, icon_size=20)
        self._title_label = Label(
            label=title,
            style="font-size: 13px; font-weight: 600;",
            h_align="start",
        )
        self._subtitle_label = Label(
            label=subtitle,
            style="font-size: 11px; opacity: 0.65;",
            h_align="start",
        )

        text_box = Box(
            orientation="v",
            spacing=2,
            h_align="start",
            v_align="center",
            children=[self._title_label, self._subtitle_label],
        )

        content = Box(
            orientation="h",
            spacing=12,
            h_align="start",
            v_align="center",
            children=[self._icon, text_box],
        )

        super().__init__(
            style_classes=["qs-screenshot-mode-button"],
            child=content,
            on_clicked=lambda *_: on_click(),
            **kwargs,
        )


class DelayPill(Button):
    def __init__(self, delay_sec: int, label_text: str, is_active: bool, on_select, **kwargs):
        self.delay_sec = delay_sec
        self._on_select = on_select

        self._label = Label(
            label=label_text,
            style="font-size: 12px; font-weight: 500;",
            v_align="center",
            h_align="center",
        )

        classes = ["qs-delay-button"]
        if is_active:
            classes.append("active")

        super().__init__(
            style_classes=classes,
            child=self._label,
            h_expand=True,
            on_clicked=lambda *_: self._on_select(self.delay_sec),
            **kwargs,
        )

    def set_active(self, active: bool):
        if active:
            self.add_style_class("active")
        else:
            self.remove_style_class("active")


class ScreenshotMenu(QSAppletPage):
    def __init__(self, parent=None, stack=None, **kwargs):
        self._delay: int = 0
        self._delay_pills: list[DelayPill] = []

        # Mode Buttons
        self._fullscreen_btn = ScreenshotModeButton(
            icon_name="desktop-duotone",
            title="Full Screen",
            subtitle="Capture the entire monitor display",
            on_click=lambda: screenshot.capture_fullscreen(delay=self._delay),
        )

        self._region_btn = ScreenshotModeButton(
            icon_name="crop-duotone",
            title="Selected Area",
            subtitle="Drag cursor to select custom rectangle",
            on_click=lambda: screenshot.capture_region(delay=self._delay),
        )

        self._window_btn = ScreenshotModeButton(
            icon_name="app-window-duotone",
            title="Active Window",
            subtitle="Capture the currently active application window",
            on_click=lambda: screenshot.capture_window(delay=self._delay),
        )

        # Delay Selector
        delay_options = [(0, "Instant"), (3, "3s Delay"), (5, "5s Delay")]
        self._delay_pills = [
            DelayPill(
                delay_sec=sec,
                label_text=text,
                is_active=(sec == self._delay),
                on_select=self._set_delay,
            )
            for sec, text in delay_options
        ]

        delay_bar = Box(
            orientation="h",
            spacing=4,
            h_expand=True,
            style_classes=["qs-delay-selector-box"],
            children=self._delay_pills,
        )

        delay_container = Box(
            orientation="v",
            spacing=6,
            children=[
                Label(
                    label="Timer Delay",
                    style="font-size: 11px; opacity: 0.7; font-weight: 500;",
                    h_align="start",
                ),
                delay_bar,
            ],
        )

        content_box = Box(
            orientation="v",
            spacing=10,
            children=[
                delay_container,
                self._fullscreen_btn,
                self._region_btn,
                self._window_btn,
            ],
        )

        super().__init__(
            title="Screenshot",
            stack=stack,
            child=ClippingScrolledWindow(
                style_classes=["scrollable"],
                style="min-width: 324px; min-height: 276px;",
                max_content_size=(324, 276),
                child=content_box,
                overlay_scroll=True,
            ),
            **kwargs,
        )

    def _set_delay(self, sec: int):
        self._delay = sec
        for pill in self._delay_pills:
            pill.set_active(pill.delay_sec == sec)
