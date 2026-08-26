from gi.repository import Gtk, GLib
from fabric.widgets.box import Box
from fabric.widgets.label import Label
from fabric.widgets.button import Button
from fabric.widgets.circularprogressbar import CircularProgressBar
from fabric.widgets.overlay import Overlay
from snippets import Icon
from services.singletons import caffeine

class DesktopCaffeine(Box):
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
        self.icon = Icon(icon_name="coffee-duotone", icon_size=24, h_align="center", v_align="center")
        self.progress_overlay = Overlay(
            child=self.progress_bar,
            overlays=self.icon,
        )

        self.title_label = Label(
            label="Caffeine",
            style_classes=["desktop-system-module-label", "top"],
            v_expand=True,
            v_align="end",
            h_align="start",
        )
        self.status_label = Label(
            label="Normal Sleep",
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
                    children=[self.title_label, self.status_label],
                ),
            ],
        )

        self.toggle_btn = Button(
            child=Label(label="Keep Awake", style="font-size: 11px; font-weight: 600;"),
            style_classes=["option-selection-button"],
            h_expand=True,
            on_clicked=lambda *_: caffeine.toggle(),
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

        caffeine.connect("notify::enabled", self._sync)
        self._sync()

    def _sync(self, *_):
        is_active = bool(caffeine.enabled)
        if is_active:
            self.progress_bar.value = 100
            self.status_label.set_label("Screen Kept Awake")
            self.toggle_btn.set_label("Deactivate")
            self.toggle_btn.add_style_class("active")
        else:
            self.progress_bar.value = 0
            self.status_label.set_label("Normal Sleep Mode")
            self.toggle_btn.set_label("Keep Awake")
            self.toggle_btn.remove_style_class("active")
