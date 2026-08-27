import datetime
from fabric.widgets.box import Box
from fabric.widgets.label import Label
from gi.repository import Gtk, GLib

DESKTOP_DATE_VARIANTS: list[tuple[str, str]] = [
    ("pixel_pill",   "Google Pixel Calendar"),
    ("nothing_dot",  "Nothing OS Date Badge"),
    ("classic",      "Modern Classic Calendar"),
]


class DesktopDate(Box):
    VARIANTS = [v[0] for v in DESKTOP_DATE_VARIANTS]

    def __init__(self, variant: str = "pixel_pill"):
        self._variant = variant or "pixel_pill"
        self._content_box = Box(orientation="v", h_expand=True, v_expand=True, h_align="fill", v_align="fill")

        self.month_label: Label | None = None
        self.date_label: Label | None = None
        self.day_label: Label | None = None
        self.header_badge: Label | None = None

        self._build_ui()

        super().__init__(
            style_classes=["desktop-applet"],
            orientation="v",
            v_align="fill",
            h_align="fill",
            v_expand=True,
            h_expand=True,
            children=[self._content_box]
        )

        self._update_time()
        self._schedule_next()

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

        if self._variant == "nothing_dot":
            self.header_badge = Label(label="DATE", style_classes=["nothing-header-badge"], h_align="start")
            self.date_label = Label(style="font-size: 38px; font-weight: 700; font-family: monospace, sans-serif;")
            self.month_label = Label(style="font-size: 12px; font-weight: 700; opacity: 0.8;")
            self.day_label = Label(style="font-size: 11px; font-weight: 700; opacity: 0.6;")

            box = Box(
                orientation="v",
                spacing=4,
                h_align="center",
                v_align="center",
                v_expand=True,
                h_expand=True,
                children=[self.header_badge, self.date_label, self.month_label, self.day_label],
            )
            self._content_box.add(box)

        elif self._variant == "pixel_pill":
            self.month_label = Label(style="font-size: 13px; font-weight: 700; color: var(--primary);")
            self.date_label = Label(style="font-size: 42px; font-weight: 800;")
            self.day_label = Label(style="font-size: 12px; font-weight: 600; opacity: 0.85;")

            box = Box(
                orientation="v",
                spacing=6,
                h_align="center",
                v_align="center",
                v_expand=True,
                h_expand=True,
                children=[self.month_label, self.date_label, self.day_label],
            )
            self._content_box.add(box)

        else:  # classic
            self.month_label = Label(v_expand=True, v_align="end", style_classes=["desktop-date-label", "month"])
            self.date_label = Label(v_expand=True, v_align="center", style_classes=["desktop-date-label", "date"])
            self.day_label = Label(v_expand=True, v_align="start", style_classes=["desktop-date-label", "day"])

            box = Box(
                orientation="v",
                v_align="center",
                v_expand=True,
                spacing=6,
                children=[self.month_label, self.date_label, self.day_label]
            )
            for child in box.children:
                child.set_xalign(0.5)
                child.set_justify(Gtk.Justification.CENTER)
            self._content_box.add(box)

        self._content_box.show_all()

    def _seconds_until_midnight(self):
        now = datetime.datetime.now()
        midnight = (now + datetime.timedelta(days=1)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        return (midnight - now).seconds

    def _schedule_next(self):
        ms = self._seconds_until_midnight() * 1000
        GLib.timeout_add(ms, self._on_day_change)

    def _on_day_change(self):
        self._update_time()
        self._schedule_next()
        return GLib.SOURCE_REMOVE

    def _update_time(self):
        now = datetime.datetime.now()
        if self.month_label:
            if self._variant in ("nothing_dot", "pixel_pill"):
                self.month_label.set_label(now.strftime("%B").upper())
            else:
                self.month_label.set_label(now.strftime("%B"))
        if self.date_label:
            self.date_label.set_label(str(now.day))
        if self.day_label:
            if self._variant == "nothing_dot":
                self.day_label.set_label(now.strftime("%A").upper())
            else:
                self.day_label.set_label(now.strftime("%A"))