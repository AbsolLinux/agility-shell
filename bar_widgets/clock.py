import time
from gi.repository import GLib, Gtk
from .base import BaseButton
from snippets import Icon

VARIANT_ICON_LABEL = "icon+label"
VARIANT_LABEL = "label"
VARIANT_12H = "12h"
VARIANT_SECONDS = "seconds"
VARIANT_DATE = "date"
VARIANT_VERTICAL = "vertical"


class ClockButton(BaseButton):
    VARIANTS = [
        VARIANT_ICON_LABEL,
        VARIANT_LABEL,
        VARIANT_12H,
        VARIANT_SECONDS,
        VARIANT_DATE,
        VARIANT_VERTICAL,
    ]

    def __init__(self, monitor_id, vertical, variant=None, **kwargs):
        self._variant_name = variant or VARIANT_ICON_LABEL
        base_variant = VARIANT_LABEL if self._variant_name in (VARIANT_LABEL, VARIANT_12H, VARIANT_SECONDS, VARIANT_DATE, VARIANT_VERTICAL) else VARIANT_ICON_LABEL

        super().__init__(
            icon=Icon(icon_name="clock-duotone", icon_size=16),
            label=self._get_label(),
            variant=base_variant,
            **kwargs,
        )

        self._variant = self._variant_name
        self.add_style_class("clock")
        if self._variant_name == VARIANT_VERTICAL:
            self._label_widget.set_justify(Gtk.Justification.CENTER)
            self._label_widget.set_line_wrap(True)

        GLib.timeout_add(1000, self._tick)

    def _get_label(self) -> str:
        var = getattr(self, "_variant", getattr(self, "_variant_name", VARIANT_ICON_LABEL))
        if var == VARIANT_12H:
            return time.strftime("%I:%M %p").lstrip("0")
        elif var == VARIANT_SECONDS:
            return time.strftime("%H:%M:%S")
        elif var == VARIANT_DATE:
            return time.strftime("%H:%M  %a, %b %d")
        elif var == VARIANT_VERTICAL:
            return time.strftime("%H\n%M")
        return time.strftime("%H:%M")

    def _tick(self):
        self._update_label(self._get_label())
        return True