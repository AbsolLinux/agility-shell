import datetime
from fabric.widgets.box import Box
from fabric.widgets.label import Label
from gi.repository import Gtk, GLib


class DesktopDate(Box):
    def __init__(self):
        self.month_label = Label(v_expand=True, v_align="end", style_classes=["desktop-date-label", "month"])
        self.date_label = Label(v_expand=True, v_align="center", style_classes=["desktop-date-label", "date"])
        self.day_label = Label(v_expand=True, v_align="start", style_classes=["desktop-date-label", "day"])

        super().__init__(
            style_classes=["desktop-applet"],
            orientation="v",
            v_align="center",
            v_expand=True,
            spacing=6,
            children=[self.month_label, self.date_label, self.day_label]
        )

        for child in self.children:
            child.set_xalign(0.5)
            child.set_justify(Gtk.Justification.CENTER)

        self._update_time()
        self._schedule_next()

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
        self.month_label.set_label(now.strftime("%B"))
        self.date_label.set_label(str(now.day))
        self.day_label.set_label(now.strftime("%A"))