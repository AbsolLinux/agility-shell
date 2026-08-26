import psutil
import time
from gi.repository import GLib, Gtk
from fabric.widgets.box import Box
from fabric.widgets.label import Label
from fabric.widgets.circularprogressbar import CircularProgressBar
from fabric.widgets.overlay import Overlay
from snippets import Icon
from services.singletons import network

class DesktopNetwork(Box):
    def __init__(self, **kwargs):
        self._last_net_bytes = None
        self._last_net_time = None

        self.progress_bar = CircularProgressBar(
            style_classes=["progress-bar"],
            start_angle=90,
            end_angle=450,
            size=(48, 48),
            line_width=3,
            min_value=0,
            max_value=100,
            value=0,
        )
        self.icon = Icon(icon_name="wifi-high-duotone", icon_size=24, h_align="center", v_align="center")
        self.progress_overlay = Overlay(
            child=self.progress_bar,
            overlays=self.icon,
        )

        self.ssid_label = Label(
            label="Disconnected",
            style_classes=["desktop-system-module-label", "top"],
            v_expand=True,
            v_align="end",
            h_align="start",
        )
        self.ip_label = Label(
            label="Offline",
            style_classes=["desktop-system-module-label", "bottom"],
            v_expand=True,
            v_align="start",
            h_align="start",
        )

        self.speed_down_label = Label(
            label="↓ 0 KB/s",
            style="font-size: 11px; font-weight: 600; font-family: apply(mixed-mono);",
            h_align="start",
        )
        self.speed_up_label = Label(
            label="↑ 0 KB/s",
            style="font-size: 11px; opacity: 0.75; font-family: apply(mixed-mono);",
            h_align="start",
        )

        header_box = Box(
            spacing=8,
            orientation="h",
            children=[
                self.progress_overlay,
                Box(
                    orientation="v",
                    children=[self.ssid_label, self.ip_label],
                ),
            ],
        )

        speeds_box = Box(
            style_classes=["desktop-system-module"],
            orientation="h",
            spacing=12,
            h_align="fill",
            children=[
                self.speed_down_label,
                Box(h_expand=True),
                self.speed_up_label,
            ],
        )

        super().__init__(
            orientation="v",
            spacing=12,
            style_classes=["desktop-applet"],
            h_expand=True,
            v_expand=True,
            children=[header_box, speeds_box],
            **kwargs,
        )

        if hasattr(network, "connect"):
            network.connect("changed", self._on_network_changed)
        if hasattr(network, "wifi") and network.wifi:
            network.wifi.connect("changed", self._on_network_changed)

        self._timer = GLib.timeout_add(1000, self._update_stats)
        self._update_stats()
        self._on_network_changed()

    def _on_network_changed(self, *_):
        try:
            if network.wifi and network.wifi.enabled:
                ssid = network.wifi.ssid or "Wi-Fi"
                strength = max(0, network.wifi.strength)
                self.ssid_label.set_label(ssid)
                self.progress_bar.value = strength
                if strength > 70:
                    self.icon.set_property("icon-name", "wifi-high-duotone")
                elif strength > 30:
                    self.icon.set_property("icon-name", "wifi-medium-duotone")
                else:
                    self.icon.set_property("icon-name", "wifi-low-duotone")
            elif getattr(network, "ethernet", None):
                self.ssid_label.set_label("Ethernet")
                self.progress_bar.value = 100
                self.icon.set_property("icon-name", "globe-duotone")
            else:
                self.ssid_label.set_label("Disconnected")
                self.progress_bar.value = 0
                self.icon.set_property("icon-name", "wifi-slash-duotone")
        except Exception:
            pass

    def _update_stats(self) -> bool:
        try:
            net = psutil.net_io_counters()
            now = time.time()
            if self._last_net_bytes is not None and self._last_net_time is not None:
                dt = max(0.1, now - self._last_net_time)
                down_rate = (net.bytes_recv - self._last_net_bytes[0]) / dt
                up_rate = (net.bytes_sent - self._last_net_bytes[1]) / dt

                def fmt_rate(b):
                    if b >= 1024 * 1024:
                        return f"{b / (1024 * 1024):.1f} MB/s"
                    return f"{b / 1024:.0f} KB/s"

                self.speed_down_label.set_label(f"↓ {fmt_rate(down_rate)}")
                self.speed_up_label.set_label(f"↑ {fmt_rate(up_rate)}")

            self._last_net_bytes = (net.bytes_recv, net.bytes_sent)
            self._last_net_time = now

            addrs = psutil.net_if_addrs()
            ip = "Offline"
            for iface, if_addrs in addrs.items():
                if iface.startswith("lo") or iface.startswith("docker") or iface.startswith("veth"):
                    continue
                for addr in if_addrs:
                    if addr.family == 2:  # AF_INET
                        ip = addr.address
                        break
                if ip != "Offline":
                    break
            self.ip_label.set_label(ip)
        except Exception:
            pass
        return True
