from gi.repository import Gtk, GLib
from fabric.widgets.box import Box
from fabric.widgets.label import Label
from fabric.widgets.circularprogressbar import CircularProgressBar
from fabric.widgets.overlay import Overlay
from snippets import Icon, FlatScale
from services.singletons import brightness

class DesktopBrightness(Box):
    def __init__(self, **kwargs):
        self._updating = False

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
        self.icon = Icon(icon_name="sun-dim-duotone", icon_size=24, h_align="center", v_align="center")
        self.progress_overlay = Overlay(
            child=self.progress_bar,
            overlays=self.icon,
        )

        self.title_label = Label(
            label="Brightness",
            style_classes=["desktop-system-module-label", "top"],
            v_expand=True,
            v_align="end",
            h_align="start",
        )
        self.val_label = Label(
            label="0%",
            style_classes=["desktop-system-module-label", "bottom"],
            v_expand=True,
            v_align="start",
            h_align="start",
        )

        self.slider = FlatScale(
            style_classes=["scale"],
            min_value=1,
            max_value=100,
            step=1,
            value=100,
            h_expand=True,
        )
        self.slider.connect("value-changed", self._on_slider_changed)

        header_box = Box(
            spacing=10,
            orientation="h",
            children=[
                self.progress_overlay,
                Box(
                    orientation="v",
                    children=[self.title_label, self.val_label],
                ),
            ],
        )

        super().__init__(
            orientation="v",
            spacing=12,
            style_classes=["desktop-applet"],
            h_expand=True,
            v_expand=True,
            children=[header_box, self.slider],
            **kwargs,
        )

        brightness.connect("screen", self._on_brightness_changed)
        self._sync()

    def _sync(self):
        try:
            if brightness.max_screen > 0:
                pct = int((brightness.screen_brightness / brightness.max_screen) * 100)
            else:
                pct = 100
            self._updating = True
            self.slider.value = pct
            self.progress_bar.value = pct
            self.val_label.set_label(f"{pct}%")
            self._updating = False
        except Exception:
            pass

    def _on_brightness_changed(self, _, percent: int):
        self._updating = True
        self.slider.value = percent
        self.progress_bar.value = percent
        self.val_label.set_label(f"{percent}%")
        self._updating = False

    def _on_slider_changed(self, scale, val):
        if self._updating or brightness.max_screen <= 0:
            return
        new_val = int((val / 100) * brightness.max_screen)
        brightness.screen_brightness = new_val
