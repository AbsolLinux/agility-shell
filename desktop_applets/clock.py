import datetime
import math
import cairo
from fabric.widgets.box import Box
from fabric.widgets.circularprogressbar import CircularProgressBar
from fabric.widgets.label import Label
from fabric.widgets.overlay import Overlay
from gi.repository import Gtk, GLib

DESKTOP_CLOCK_VARIANTS: list[tuple[str, str]] = [
    ("circular",         "Circular Progress Ring"),
    ("digital_clean",    "Modern Digital Clock"),
    ("digital_seconds",  "Digital with Seconds"),
    ("analog",           "Smooth Analog Dial"),
    ("minimal_vertical", "Minimalist Stacked"),
]


class AnalogClockArea(Gtk.DrawingArea):
    def __init__(self):
        super().__init__()
        self.set_hexpand(True)
        self.set_vexpand(True)
        self.connect("draw", self._on_draw)

    def _on_draw(self, widget, cr: cairo.Context):
        alloc = self.get_allocation()
        w, h = alloc.width, alloc.height
        cx, cy = w / 2.0, h / 2.0
        radius = max(20, min(w, h) / 2.0 - 10)

        now = datetime.datetime.now()
        hours = now.hour % 12
        minutes = now.minute
        seconds = now.second + now.microsecond / 1_000_000.0

        # Dial background
        cr.arc(cx, cy, radius, 0, 2 * math.pi)
        cr.set_source_rgba(1, 1, 1, 0.04)
        cr.fill_preserve()
        cr.set_source_rgba(1, 1, 1, 0.18)
        cr.set_line_width(2)
        cr.stroke()

        # Tick marks
        for i in range(12):
            angle = i * (math.pi / 6)
            is_major = (i % 3 == 0)
            inner_r = radius - (10 if is_major else 6)
            outer_r = radius - 3
            x1 = cx + inner_r * math.sin(angle)
            y1 = cy - inner_r * math.cos(angle)
            x2 = cx + outer_r * math.sin(angle)
            y2 = cy - outer_r * math.cos(angle)
            cr.move_to(x1, y1)
            cr.line_to(x2, y2)
            cr.set_line_width(2.5 if is_major else 1.2)
            cr.set_source_rgba(1, 1, 1, 0.7 if is_major else 0.35)
            cr.stroke()

        # Hour hand
        hour_angle = (hours + minutes / 60.0) * (math.pi / 6)
        hx = cx + (radius * 0.52) * math.sin(hour_angle)
        hy = cy - (radius * 0.52) * math.cos(hour_angle)
        cr.move_to(cx, cy)
        cr.line_to(hx, hy)
        cr.set_line_width(3.5)
        cr.set_line_cap(cairo.LineCap.ROUND)
        cr.set_source_rgba(1, 1, 1, 0.95)
        cr.stroke()

        # Minute hand
        min_angle = (minutes + seconds / 60.0) * (math.pi / 30)
        mx = cx + (radius * 0.75) * math.sin(min_angle)
        my = cy - (radius * 0.75) * math.cos(min_angle)
        cr.move_to(cx, cy)
        cr.line_to(mx, my)
        cr.set_line_width(2.2)
        cr.set_line_cap(cairo.LineCap.ROUND)
        cr.set_source_rgba(1, 1, 1, 0.85)
        cr.stroke()

        # Second hand
        sec_angle = seconds * (math.pi / 30)
        sx = cx + (radius * 0.84) * math.sin(sec_angle)
        sy = cy - (radius * 0.84) * math.cos(sec_angle)
        tx = cx - (radius * 0.16) * math.sin(sec_angle)
        ty = cy + (radius * 0.16) * math.cos(sec_angle)
        cr.move_to(tx, ty)
        cr.line_to(sx, sy)
        cr.set_line_width(1.5)
        cr.set_source_rgba(0.95, 0.35, 0.35, 0.95)
        cr.stroke()

        # Center cap
        cr.arc(cx, cy, 3.5, 0, 2 * math.pi)
        cr.set_source_rgba(0.95, 0.35, 0.35, 1.0)
        cr.fill()

        return False


class DesktopClock(Box):
    VARIANTS = [v[0] for v in DESKTOP_CLOCK_VARIANTS]

    def __init__(self, variant: str = "circular"):
        self._variant = variant or "circular"
        self._content_box = Box(orientation="v", h_expand=True, v_expand=True, h_align="fill", v_align="fill")
        self._analog_da: AnalogClockArea | None = None
        self._clock_progress: CircularProgressBar | None = None
        self._time_label: Label | None = None
        self._date_label: Label | None = None
        self._sec_label: Label | None = None

        self._build_ui()

        super().__init__(
            style_classes=["desktop-applet"],
            h_expand=True,
            v_expand=True,
            children=[self._content_box],
        )

        GLib.timeout_add(1000, self._update_time)
        self._update_time()

    def set_variant(self, variant: str):
        if self._variant == variant:
            return
        self._variant = variant
        self._build_ui()
        self._update_time()

    def _build_ui(self):
        for child in self._content_box.get_children():
            self._content_box.remove(child)
            child.destroy()

        self._analog_da = None
        self._clock_progress = None
        self._time_label = None
        self._date_label = None
        self._sec_label = None

        if self._variant == "analog":
            self._analog_da = AnalogClockArea()
            self._content_box.add(self._analog_da)

        elif self._variant == "digital_clean":
            self._time_label = Label(style="font-size: 32px; font-weight: 700; letter-spacing: 1px;")
            self._date_label = Label(style="font-size: 12px; opacity: 0.75; font-weight: 500;")
            
            box = Box(
                orientation="v",
                spacing=6,
                h_align="center",
                v_align="center",
                v_expand=True,
                h_expand=True,
                children=[self._time_label, self._date_label],
            )
            self._content_box.add(box)

        elif self._variant == "digital_seconds":
            self._time_label = Label(style="font-size: 30px; font-weight: 700;")
            self._sec_label = Label(style="font-size: 13px; font-weight: 600; opacity: 0.85; padding-top: 4px;")
            self._date_label = Label(style="font-size: 11px; opacity: 0.7; font-weight: 500;")

            time_row = Box(
                orientation="h",
                spacing=4,
                h_align="center",
                v_align="center",
                children=[self._time_label, self._sec_label],
            )
            box = Box(
                orientation="v",
                spacing=4,
                h_align="center",
                v_align="center",
                v_expand=True,
                h_expand=True,
                children=[time_row, self._date_label],
            )
            self._content_box.add(box)

        elif self._variant == "minimal_vertical":
            self._time_label = Label(style="font-size: 26px; font-weight: 800; line-height: 1.1;")
            self._time_label.set_justify(Gtk.Justification.CENTER)
            self._date_label = Label(style="font-size: 11px; opacity: 0.7; font-weight: 600; text-transform: uppercase;")
            self._date_label.set_justify(Gtk.Justification.CENTER)

            box = Box(
                orientation="v",
                spacing=6,
                h_align="center",
                v_align="center",
                v_expand=True,
                h_expand=True,
                children=[self._time_label, self._date_label],
            )
            self._content_box.add(box)

        else:  # default circular
            self._clock_progress = CircularProgressBar(
                style_classes=["progress-bar"],
                start_angle=270,
                end_angle=630,
                size=(138, 138),
                line_width=6,
                min_value=0,
                max_value=60,
                value=0,
            )
            self._time_label = Label(style_classes="lockscreen-clock-label")
            self._time_label.set_xalign(0.5)
            self._time_label.set_justify(Gtk.Justification.CENTER)
            clock_circle = Overlay(
                child=Box(
                    style_classes=["lockscreen-clock"],
                    h_expand=False,
                    h_align="center",
                    children=self._clock_progress,
                ),
                overlays=self._time_label,
            )
            self._content_box.add(clock_circle)

        self._content_box.show_all()

    def _update_time(self):
        now = datetime.datetime.now()

        if self._analog_da:
            self._analog_da.queue_draw()

        if self._clock_progress:
            self._clock_progress.value = int(now.strftime("%S"))

        if self._variant == "circular" and self._time_label:
            self._time_label.set_label(now.strftime("%H\n%M"))

        elif self._variant == "digital_clean":
            if self._time_label:
                self._time_label.set_label(now.strftime("%H:%M"))
            if self._date_label:
                self._date_label.set_label(now.strftime("%A, %B %d"))

        elif self._variant == "digital_seconds":
            if self._time_label:
                self._time_label.set_label(now.strftime("%H:%M"))
            if self._sec_label:
                self._sec_label.set_label(now.strftime(":%S"))
            if self._date_label:
                self._date_label.set_label(now.strftime("%a, %b %d"))

        elif self._variant == "minimal_vertical":
            if self._time_label:
                self._time_label.set_label(now.strftime("%H\n%M"))
            if self._date_label:
                self._date_label.set_label(now.strftime("%b %d"))

        return True