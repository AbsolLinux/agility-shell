import datetime
from fabric.widgets.box import Box
from fabric.widgets.label import Label
from gi.repository import Gtk, GLib
from services.singletons import weather
from snippets import Icon

DESKTOP_WEATHER_VARIANTS: list[tuple[str, str]] = [
    ("pixel_weather",       "Google Pixel Weather Card"),
    ("nothing_monochrome",  "Nothing OS Glyph Weather"),
    ("detailed",            "Detailed Hourly Forecast"),
]


class DesktopWeather(Box):
    VARIANTS = [v[0] for v in DESKTOP_WEATHER_VARIANTS]

    def __init__(self, variant: str = "pixel_weather", **kwargs):
        self._variant = variant or "pixel_weather"
        self._content_box = Box(orientation="v", h_expand=True, v_expand=True, h_align="fill", v_align="fill")

        self._hourly_box: Box | None = None
        self._temp_label: Label | None = None
        self._icon: Icon | None = None
        self._high_label: Label | None = None
        self._low_label: Label | None = None
        self._condition_label: Label | None = None

        self._build_ui()

        super().__init__(
            style_classes=["desktop-applet", "large"],
            orientation="v",
            v_align="fill",
            h_align="fill",
            v_expand=True,
            h_expand=True,
            children=[self._content_box],
            **kwargs
        )

        weather.connect("notify::hourly-forecast", lambda *_: self._rebuild_hourly())
        weather.connect("notify::temperature", lambda *_: self._update_current())
        weather.connect("notify::weather-icon", lambda *_: self._update_current())
        weather.connect("notify::daily-forecast", lambda *_: self._update_minmax())

        self._update_current()
        self._update_minmax()
        self._rebuild_hourly()

    def set_variant(self, variant: str):
        if self._variant == variant:
            return
        self._variant = variant
        self._build_ui()
        self._update_current()
        self._update_minmax()
        self._rebuild_hourly()

    def _build_ui(self):
        for child in self._content_box.get_children():
            self._content_box.remove(child)
            child.destroy()

        self._hourly_box = Box(spacing=20, style_classes=["hourly-forecast"], h_expand=True, h_align="center")
        self._temp_label = Label(style="font-size: 36px; font-weight: 800; font-family: monospace, sans-serif;")
        self._icon = Icon(icon_name="cloud-duotone", icon_size=40)
        self._high_label = Label(label="--°", style="font-size: 13px; font-weight: 700;")
        self._low_label = Label(label="--°", style="font-size: 13px; font-weight: 700; opacity: 0.7;")
        self._condition_label = Label(label="Weather", style="font-size: 12px; opacity: 0.85; font-weight: 600;")

        if self._variant == "nothing_monochrome":
            header = Label(label="WEATHER", style_classes=["nothing-header-badge"], h_align="start")
            
            main_row = Box(
                orientation="h",
                spacing=12,
                v_align="center",
                h_align="center",
                children=[
                    self._icon,
                    Box(
                        orientation="v",
                        spacing=2,
                        children=[self._temp_label, self._condition_label],
                    ),
                    Box(h_expand=True),
                    Box(
                        orientation="v",
                        spacing=4,
                        h_align="end",
                        style_classes=["desktop-system-module", "amoled"],
                        children=[
                            Box(spacing=4, children=[Label(label="H", style="font-size: 10px; color: #EB0029; font-weight: 700;"), self._high_label]),
                            Box(spacing=4, children=[Label(label="L", style="font-size: 10px; opacity: 0.5; font-weight: 700;"), self._low_label]),
                        ]
                    )
                ]
            )

            box = Box(
                orientation="v",
                spacing=12,
                v_expand=True,
                h_expand=True,
                v_align="center",
                children=[header, main_row, self._hourly_box]
            )
            self._content_box.add(box)

        elif self._variant == "detailed":
            main_row = Box(
                orientation="h",
                spacing=12,
                v_align="center",
                children=[
                    self._icon,
                    self._temp_label,
                    Box(h_expand=True),
                    Box(
                        orientation="v",
                        spacing=4,
                        h_align="end",
                        children=[
                            Box(spacing=4, children=[self._high_label, Icon(icon_name="caret-up-duotone", icon_size=16)]),
                            Box(spacing=4, children=[self._low_label, Icon(icon_name="caret-down-duotone", icon_size=16)]),
                        ]
                    )
                ]
            )
            box = Box(
                orientation="v",
                spacing=16,
                v_expand=True,
                h_expand=True,
                v_align="center",
                children=[main_row, self._hourly_box]
            )
            self._content_box.add(box)

        else:  # pixel_weather
            pill = Box(
                orientation="h",
                spacing=12,
                v_align="center",
                h_align="center",
                children=[
                    self._icon,
                    Box(
                        orientation="v",
                        spacing=2,
                        v_align="center",
                        children=[self._temp_label, self._condition_label],
                    ),
                    Box(h_expand=True),
                    Box(
                        orientation="h",
                        spacing=8,
                        h_align="end",
                        style_classes=["pixel-glance-pill"],
                        children=[
                            Box(spacing=2, children=[Icon(icon_name="arrow-up-duotone", icon_size=14), self._high_label]),
                            Box(spacing=2, children=[Icon(icon_name="arrow-down-duotone", icon_size=14), self._low_label]),
                        ]
                    )
                ]
            )
            box = Box(
                orientation="v",
                spacing=16,
                v_expand=True,
                h_expand=True,
                v_align="center",
                children=[pill, self._hourly_box]
            )
            self._content_box.add(box)

        self._content_box.show_all()

    def _update_current(self, *_):
        try:
            temp = weather.temperature
            if temp is not None:
                self._temp_label.set_label(f"{temp:.0f}°")
            else:
                self._temp_label.set_label("--°")
            if weather.weather_icon:
                self._icon.set_property("icon-name", weather.weather_icon)
            if hasattr(weather, "status") and weather.status:
                self._condition_label.set_label(str(weather.status).capitalize())
        except Exception:
            pass

    def _update_minmax(self, *_):
        try:
            daily = weather.daily_forecast
            if not daily:
                return
            today = daily[0]
            self._high_label.set_label(f"{round(today.get('temperature_max', 0))}°")
            self._low_label.set_label(f"{round(today.get('temperature_min', 0))}°")
        except Exception:
            pass

    def _rebuild_hourly(self, *_):
        if not self._hourly_box:
            return
        try:
            from windows.weather_popup import HourlyForecastItem
            for child in self._hourly_box.children:
                self._hourly_box.remove(child)
            for hour in (weather.hourly_forecast or [])[:5]:
                self._hourly_box.add(HourlyForecastItem(hour))
            self._hourly_box.show_all()
        except Exception:
            pass
