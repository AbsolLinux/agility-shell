import datetime
from fabric.widgets.box import Box
from fabric.widgets.circularprogressbar import CircularProgressBar
from fabric.widgets.label import Label
from fabric.widgets.overlay import Overlay
from gi.repository import Gtk, GLib
from services.singletons import battery
from icons import BatteryIcon
from snippets import Icon

DESKTOP_BATTERY_VARIANTS: list[tuple[str, str]] = [
    ("pixel_battery", "Google Pixel Battery Card"),
    ("nothing_glyph", "Nothing OS Glyph Battery"),
    ("circular",      "Circular Progress Ring"),
]


class DesktopBattery(Box):
    VARIANTS = [v[0] for v in DESKTOP_BATTERY_VARIANTS]

    def __init__(self, variant: str = "pixel_battery"):
        self._variant = variant or "pixel_battery"
        self._content_box = Box(orientation="v", h_expand=True, v_expand=True, h_align="fill", v_align="fill")

        self.clock_progress: CircularProgressBar | None = None
        self.battery_label: Label | None = None
        self.status_label: Label | None = None
        self.icon_widget = None

        self._build_ui()

        super().__init__(
            style_classes=["desktop-applet"],
            orientation="v",
            v_align="fill",
            h_align="fill",
            h_expand=True,
            v_expand=True,
            children=[self._content_box],
        )

        battery.connect("changed", self._update)
        if battery.available:
            GLib.timeout_add(1000, self._update)
        self._update()

    def set_variant(self, variant: str):
        if self._variant == variant:
            return
        self._variant = variant
        self._build_ui()
        self._update()

    def _build_ui(self):
        for child in self._content_box.get_children():
            self._content_box.remove(child)
            child.destroy()

        if self._variant == "nothing_glyph":
            header = Label(label="ENERGY", style_classes=["nothing-header-badge"], h_align="start")
            self.battery_label = Label(style="font-size: 38px; font-weight: 700; font-family: monospace, sans-serif;")
            self.status_label = Label(style="font-size: 11px; font-weight: 700; opacity: 0.75;")
            
            icon = Icon(icon_name="lightning-duotone", icon_size=28, style="color: #EB0029;")

            row = Box(
                orientation="h",
                spacing=8,
                h_align="center",
                v_align="center",
                children=[icon, self.battery_label],
            )

            box = Box(
                orientation="v",
                spacing=6,
                h_align="center",
                v_align="center",
                v_expand=True,
                h_expand=True,
                children=[header, row, self.status_label],
            )
            self._content_box.add(box)

        elif self._variant == "pixel_battery":
            self.battery_label = Label(style="font-size: 34px; font-weight: 800; font-family: monospace, sans-serif;")
            self.status_label = Label(style="font-size: 12px; font-weight: 600; opacity: 0.85;")
            
            bat_icon = BatteryIcon(size=36, percent=False, h_align="center")

            pill = Box(
                orientation="h",
                spacing=8,
                h_align="center",
                v_align="center",
                style_classes=["pixel-glance-pill"],
                children=[self.status_label],
            )

            box = Box(
                orientation="v",
                spacing=8,
                h_align="center",
                v_align="center",
                v_expand=True,
                h_expand=True,
                children=[bat_icon, self.battery_label, pill],
            )
            self._content_box.add(box)

        else:  # circular
            self.clock_progress = CircularProgressBar(
                style_classes=["progress-bar"],
                start_angle=90,
                end_angle=450,
                size=(120, 120),
                line_width=6,
                min_value=0,
                max_value=100,
                value=0,
            )
            self.battery_label = Label(h_expand=True, h_align="center", style_classes="desktop-battery-label", label="100%")
            self.battery_label.set_xalign(0.5)
            self.battery_label.set_justify(Gtk.Justification.CENTER)
            self.status_label = Label(style="font-size: 11px; opacity: 0.7;", label="Discharging")

            overlay = Overlay(
                child=Box(
                    style_classes=["lockscreen-clock"],
                    h_expand=False,
                    h_align="center",
                    children=self.clock_progress,
                ),
                overlays=Box(
                    style="min-width: 60px;",
                    h_expand=True,
                    h_align="center",
                    v_expand=True,
                    v_align="center",
                    orientation="v",
                    spacing=2,
                    children=[
                        BatteryIcon(size=32, percent=False, h_align="center", h_expand=True),
                        self.battery_label,
                    ]
                ),
            )
            self._content_box.add(overlay)

        self._content_box.show_all()

    def _update(self, *_):
        try:
            bat = battery.percent if hasattr(battery, "percent") and battery.percent is not None else 100
            val = round(bat)
            
            charging = getattr(battery, "charging", False) or getattr(battery, "state", 0) == 1
            status_text = "Charging ⚡" if charging else "Discharging"

            if self.battery_label:
                self.battery_label.set_label(f"{val}%")
            if self.status_label:
                self.status_label.set_label(status_text)
            if self.clock_progress:
                self.clock_progress.value = val
        except Exception:
            pass
        return False