from gi.repository import Gtk, GLib
from fabric.widgets.box import Box
from fabric.widgets.label import Label
from fabric.widgets.button import Button
from fabric.widgets.circularprogressbar import CircularProgressBar
from fabric.widgets.overlay import Overlay
from snippets import Icon, FlatScale
from services.singletons import audio

DESKTOP_VOLUME_VARIANTS: list[tuple[str, str]] = [
    ("pixel_slider",   "Google Pixel Pill Volume"),
    ("nothing_glyph",  "Nothing OS Glyph Volume"),
]


class DesktopVolume(Box):
    VARIANTS = [v[0] for v in DESKTOP_VOLUME_VARIANTS]

    def __init__(self, variant: str = "pixel_slider", **kwargs):
        self._variant = variant or "pixel_slider"
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
        self.icon = Icon(icon_name="speaker-simple-high-duotone", icon_size=24, h_align="center", v_align="center")
        self.progress_overlay = Overlay(
            child=self.progress_bar,
            overlays=self.icon,
        )

        self.title_label = Label(
            label="Audio",
            style_classes=["desktop-system-module-label", "top"],
            v_expand=True,
            v_align="end",
            h_align="start",
        )
        self.vol_label = Label(
            label="0%",
            style_classes=["desktop-system-module-label", "bottom"],
            v_expand=True,
            v_align="start",
            h_align="start",
        )

        self.slider = FlatScale(
            style_classes=["scale"],
            min_value=0,
            max_value=100,
            step=1,
            value=0,
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
                    children=[self.title_label, self.vol_label],
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

        audio.connect("speaker-changed", self._on_speaker_changed)
        if audio.speaker:
            self._on_speaker_changed()

    def set_variant(self, variant: str):
        self._variant = variant
        if variant == "nothing_glyph":
            self.title_label.set_label("VOLUME")
            self.title_label.set_style("font-size: 11px; font-weight: 700; color: #EB0029; font-family: monospace;")
        else:
            self.title_label.set_label("Audio")
            self.title_label.set_style("font-size: 14px; font-weight: 700;")
        self._sync()

    def _on_speaker_changed(self, *_):
        if not audio.speaker:
            return
        audio.speaker.connect("notify::volume", self._on_volume_notify)
        audio.speaker.connect("notify::muted", self._on_volume_notify)
        self._sync()

    def _on_volume_notify(self, *_):
        self._sync()

    def _sync(self):
        if not audio.speaker:
            return
        vol = max(0, min(100, int(audio.speaker.volume)))
        is_muted = getattr(audio.speaker, "muted", False)

        self._updating = True
        self.slider.value = vol
        self.progress_bar.value = vol
        self._updating = False

        if is_muted:
            self.vol_label.set_label("Muted")
            self.icon.set_property("icon-name", "speaker-simple-slash-duotone")
        else:
            self.vol_label.set_label(f"{vol}%")
            if vol > 66:
                self.icon.set_property("icon-name", "speaker-simple-high-duotone")
            elif vol > 33:
                self.icon.set_property("icon-name", "speaker-simple-medium-duotone")
            else:
                self.icon.set_property("icon-name", "speaker-simple-low-duotone")

    def _on_slider_changed(self, scale, val):
        if self._updating or not audio.speaker:
            return
        audio.speaker.volume = int(val)
