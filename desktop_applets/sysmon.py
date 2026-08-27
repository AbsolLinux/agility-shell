import os
import psutil
from gi.repository import GLib, Gtk
from fabric.widgets.box import Box
from fabric.widgets.label import Label
from snippets import Icon, Graph


class MetricGraphCard(Box):
    def __init__(
        self,
        icon_name: str,
        name: str,
        initial_val: str = "0%",
        min_val: float = 0.0,
        max_val: float = 100.0,
        dynamic: bool = False,
        overlay_class: str = "",
        **kwargs,
    ):
        self.icon = Icon(icon_name=icon_name, icon_size=16)
        self.title_label = Label(
            label=name,
            style="font-size: 11px; font-weight: 600;",
            h_align="start",
        )
        self.value_label = Label(
            label=initial_val,
            style="font-size: 11px; font-weight: 700;",
            h_align="end",
        )
        self.sub_label = Label(
            label="",
            style="font-size: 10px; opacity: 0.7;",
            h_align="end",
        )

        header = Box(
            orientation="h",
            spacing=6,
            h_align="fill",
            children=[
                self.icon,
                self.title_label,
                Box(h_expand=True),
                self.sub_label,
                self.value_label,
            ],
        )

        graph_classes = ["graph"]
        if overlay_class:
            graph_classes.append(overlay_class)

        self.graph = Graph(
            data=[0.0] * 16,
            min_value=min_val,
            max_value=max_val,
            line_width=2.0,
            fill=True,
            smooth=True,
            dynamic=dynamic,
            size=(60, 32),
            style_classes=graph_classes,
            h_expand=True,
            v_expand=True,
        )

        super().__init__(
            orientation="v",
            spacing=4,
            style_classes=["graph-container", "desktop-system-module"],
            h_expand=True,
            v_expand=True,
            children=[header, self.graph],
            **kwargs,
        )

    def update_metric(self, value_num: float, value_str: str, sub_str: str = ""):
        self.value_label.set_label(value_str)
        if sub_str:
            self.sub_label.set_label(sub_str)
            self.sub_label.show()
        else:
            self.sub_label.hide()
        self.graph.push(float(value_num))


DESKTOP_SYSMON_VARIANTS: list[tuple[str, str]] = [
    ("pixel_cards",        "Google Pixel Hardware Monitor"),
    ("nothing_telemetry",  "Nothing OS Telemetry"),
    ("compact",            "Compact Graphs"),
]


class DesktopSysMon(Box):
    VARIANTS = [v[0] for v in DESKTOP_SYSMON_VARIANTS]

    def __init__(self, variant: str = "pixel_cards", **kwargs):
        super().__init__(
            orientation="v",
            spacing=8,
            style_classes=["desktop-applet"],
            h_expand=True,
            v_expand=True,
            **kwargs,
        )
        self._variant = variant or "pixel_cards"
        self.cpu_card = MetricGraphCard(
            icon_name="cpu-duotone",
            name="CPU",
            initial_val="0%",
        )
        self.ram_card = MetricGraphCard(
            icon_name="chart-line-up-duotone",
            name="RAM",
            initial_val="0%",
            overlay_class="overlayed",
        )
        self.disk_card = MetricGraphCard(
            icon_name="hard-drives-duotone",
            name="Disk",
            initial_val="0%",
        )
        self.disk_card.set_no_show_all(True)
        self.disk_card.hide()

        self.net_card = MetricGraphCard(
            icon_name="arrows-down-up-duotone",
            name="Network",
            initial_val="0 KB/s",
            dynamic=True,
            overlay_class="overlayed",
        )
        self.net_card.set_no_show_all(True)
        self.net_card.hide()

        self.primary_box = Box(
            orientation="v",
            spacing=8,
            h_expand=True,
            v_expand=True,
            children=[self.cpu_card, self.ram_card],
        )

        self.extra_box = Box(
            orientation="v",
            spacing=8,
            h_expand=True,
            v_expand=True,
            children=[self.disk_card, self.net_card],
        )
        self.extra_box.set_no_show_all(True)
        self.extra_box.hide()

        self._container_box = Box(
            orientation="v",
            spacing=8,
            h_expand=True,
            v_expand=True,
            children=[self.primary_box, self.extra_box],
        )
        self.add(self._container_box)

        self._last_net_bytes = None
        self._last_net_time = None

        self.connect("size-allocate", self._on_size_allocate)

        self._timer_id = GLib.timeout_add(1000, self._update_stats)
        self._update_stats()

    def set_variant(self, variant: str):
        self._variant = variant
        if variant == "nothing_telemetry":
            self.cpu_card.title_label.set_style("font-size: 11px; font-weight: 700; color: #EB0029; font-family: monospace;")
            self.ram_card.title_label.set_style("font-size: 11px; font-weight: 700; color: #EB0029; font-family: monospace;")
        else:
            self.cpu_card.title_label.set_style("font-size: 11px; font-weight: 600;")
            self.ram_card.title_label.set_style("font-size: 11px; font-weight: 600;")

    def _on_size_allocate(self, widget, alloc):
        w = alloc.width
        h = alloc.height

        if h >= 250 or w >= 380:
            if not self.extra_box.get_visible():
                self.disk_card.show()
                self.net_card.show()
                self.extra_box.show()
            if w >= 380:
                self.container.set_orientation(Gtk.Orientation.HORIZONTAL)
            else:
                self.container.set_orientation(Gtk.Orientation.VERTICAL)
        else:
            if self.extra_box.get_visible():
                self.extra_box.hide()
                self.disk_card.hide()
                self.net_card.hide()
            self.container.set_orientation(Gtk.Orientation.VERTICAL)

    def _update_stats(self) -> bool:
        try:
            # CPU
            cpu_pct = psutil.cpu_percent(interval=None)
            self.cpu_card.update_metric(cpu_pct, f"{round(cpu_pct)}%")

            # RAM
            ram = psutil.virtual_memory()
            ram_pct = ram.percent
            used_gb = ram.used / (1024 ** 3)
            total_gb = ram.total / (1024 ** 3)
            self.ram_card.update_metric(
                ram_pct,
                f"{round(ram_pct)}%",
                sub_str=f"{used_gb:.1f}/{total_gb:.0f}GB",
            )

            # Disk
            if self.extra_box.get_visible():
                disk = psutil.disk_usage("/")
                disk_pct = disk.percent
                d_used_gb = disk.used / (1024 ** 3)
                d_total_gb = disk.total / (1024 ** 3)
                self.disk_card.update_metric(
                    disk_pct,
                    f"{round(disk_pct)}%",
                    sub_str=f"{d_used_gb:.0f}/{d_total_gb:.0f}GB",
                )

                # Network
                now = GLib.get_monotonic_time()
                net_io = psutil.net_io_counters()
                cur_bytes = net_io.bytes_sent + net_io.bytes_recv

                if self._last_net_bytes is not None and self._last_net_time is not None:
                    dt = max(0.001, (now - self._last_net_time) / 1_000_000.0)
                    speed_bps = max(0.0, (cur_bytes - self._last_net_bytes) / dt)
                    if speed_bps >= 1024 * 1024:
                        speed_str = f"{speed_bps / (1024 * 1024):.1f} MB/s"
                    elif speed_bps >= 1024:
                        speed_str = f"{int(speed_bps / 1024)} KB/s"
                    else:
                        speed_str = f"{int(speed_bps)} B/s"
                    self.net_card.update_metric(speed_bps / 1024.0, speed_str)

                self._last_net_bytes = cur_bytes
                self._last_net_time = now

        except Exception:
            pass
        return True
