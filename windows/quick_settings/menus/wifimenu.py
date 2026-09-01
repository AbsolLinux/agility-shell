from fabric.widgets.box import Box
from fabric.widgets.label import Label
from fabric.widgets.button import Button
from fabric.widgets.stack import Stack
from snippets import Icon, SmoothSwitch, AnimatedScroll
from .menu import QSAppletPage
from .tab import TabStack, TabMenu
from services.singletons import network
from gi.repository import GLib
from .wifi_password import WifiPasswordMenu
from enum import Enum, auto


class APState(Enum):
    IDLE = auto()
    CONNECTED = auto()
    CONNECTING = auto()
    FAILED = auto()


class AccessPoint:
    def __init__(self, ap_dict: dict, device):
        self._dict = ap_dict
        self._device = device

    @property
    def ssid(self): return self._dict.get("ssid", "")
    @property
    def strength(self): return self._dict.get("strength", 0)
    @property
    def security(self): return self._dict.get("security", None)
    @property
    def psk(self): return self._dict.get("psk", None)
    @property
    def is_connected(self):
        active = self._dict.get("active-ap")
        if not active:
            return False
        try:
            return self._dict.get("bssid") == active.get_bssid()
        except Exception:
            return False

    def connect_to_graphical(self):
        from services.singletons import network
        network.connect_wifi_bssid(self._dict.get("bssid"))

    def disconnect_from(self):
        self._device._device.disconnect(None)

    def connect(self, signal, callback):
        pass


class WifiIcon(Icon):
    def __init__(self, ap: AccessPoint, **kwargs):
        super().__init__(icon_name=self._get_icon(ap.strength), **kwargs)

    def _get_icon(self, strength: int) -> str:
        if strength >= 75:   return "wifi-high-duotone"
        elif strength >= 50: return "wifi-medium-duotone"
        elif strength >= 25: return "wifi-low-duotone"
        else:                return "wifi-none-duotone"


class AccessPointItem(Box):
    def __init__(self, ap: AccessPoint, on_connect, wifi, tab=None, **kwargs):
        self.ap = ap
        self._wifi = wifi
        self._tab = tab
        self._on_connect = on_connect
        self._state = APState.IDLE
        self._state_signal: int | None = None
        self._failed_timer: int | None = None

        self._icon = WifiIcon(ap)
        self._ssid_label = Label(
            label=ap.ssid or "Unknown Network",
            style_classes=["menu-device-label"],
            h_align="start",
            ellipsize=True,
            max_chars_width=18,
        )

        self._status_badge = Label(label="", style="font-size: 11px; font-weight: 500;", visible=False)
        self._status_icon = Icon(icon_name="check-circle-duotone", icon_size=14, visible=False)

        self._status_box = Box(
            orientation="h",
            spacing=4,
            h_align="end",
            v_align="center",
            children=[self._status_icon, self._status_badge],
        )

        self._sec_icon = Icon(
            icon_name=self._get_security_icon(ap),
            icon_size=16,
            h_align="end",
        ) if ap.security else Box()

        right_box = Box(
            orientation="h",
            spacing=8,
            h_align="end",
            h_expand=True,
            v_align="center",
            children=[self._status_box, self._sec_icon],
        )

        self.main_btn = Button(
            events=["click"],
            child=Box(
                spacing=8,
                children=[
                    self._icon,
                    self._ssid_label,
                    right_box,
                ],
            ),
            on_clicked=lambda _: self._handle_click(),
            style_classes=["menu-device-item"],
        )

        self._confirm_prompt = Label(
            label="Disconnect?",
            style="font-size: 12px; font-weight: 500; opacity: 0.85;",
            h_align="start",
            h_expand=True,
        )
        self._disconnect_btn = Button(
            label="Disconnect",
            style_classes=["wifi-disconnect-btn"],
            on_clicked=lambda _: self._confirm_disconnect(),
        )
        self._cancel_btn = Button(
            label="Cancel",
            style_classes=["wifi-cancel-btn"],
            on_clicked=lambda _: self._hide_disconnect_confirm(),
        )

        self.confirm_box = Box(
            orientation="h",
            spacing=6,
            style_classes=["wifi-disconnect-confirm-box"],
            visible=False,
            children=[
                self._confirm_prompt,
                self._cancel_btn,
                self._disconnect_btn,
            ],
        )

        super().__init__(
            orientation="v",
            spacing=2,
            children=[
                self.main_btn,
                self.confirm_box,
            ],
            **kwargs,
        )

        self._state_signal = wifi._device.connect(
            "notify::state", lambda *_: self._refresh_state()
        )
        self._refresh_state()

    def _refresh_state(self):
        if self.get_parent() is None:
            return
        active_ap = self._wifi._device.get_active_access_point()
        bssid = self.ap._dict.get("bssid")
        if active_ap and active_ap.get_bssid() == bssid:
            self._set_state(APState.CONNECTED)
        elif self._state != APState.CONNECTING:
            self._set_state(APState.IDLE)

    def _set_state(self, state: APState):
        self._state = state
        if state != APState.CONNECTED:
            self._hide_disconnect_confirm()

        for cls in ["active", "connecting", "failed", "connected"]:
            self.main_btn.remove_style_class(cls)
            self.remove_style_class(cls)

        if state == APState.CONNECTED:
            self.main_btn.add_style_class("active")
            self.main_btn.add_style_class("connected")
            self.add_style_class("active")
            self.add_style_class("connected")
            self._status_badge.set_label("Connected")
            self._status_badge.set_visible(True)
            self._status_icon.set_property("icon-name", "check-circle-duotone")
            self._status_icon.set_visible(True)
        elif state == APState.CONNECTING:
            self.main_btn.add_style_class("connecting")
            self.add_style_class("connecting")
            self._status_badge.set_label("Connecting…")
            self._status_badge.set_visible(True)
            self._status_icon.set_property("icon-name", "arrows-clockwise-duotone")
            self._status_icon.set_visible(True)
        elif state == APState.FAILED:
            self.main_btn.add_style_class("failed")
            self.add_style_class("failed")
            self._status_badge.set_label("Failed")
            self._status_badge.set_visible(True)
            self._status_icon.set_property("icon-name", "warning-circle-duotone")
            self._status_icon.set_visible(True)
        else:
            self._status_badge.set_visible(False)
            self._status_icon.set_visible(False)

        if self._tab:
            self._tab.sort_items()

    def _handle_click(self):
        if self._state == APState.CONNECTED:
            self.confirm_box.set_visible(not self.confirm_box.get_visible())
        elif self._state != APState.CONNECTING:
            self._hide_disconnect_confirm()
            self._set_state(APState.CONNECTING)
            self._on_connect(self.ap)

    def _confirm_disconnect(self):
        self._hide_disconnect_confirm()
        self._wifi._device.disconnect(None)
        self._set_state(APState.IDLE)

    def _hide_disconnect_confirm(self):
        self.confirm_box.set_visible(False)

    def set_failed(self):
        self._set_state(APState.FAILED)
        if self._failed_timer:
            GLib.source_remove(self._failed_timer)

        def _reset():
            self._failed_timer = None
            if self.get_parent() is not None:
                self._set_state(APState.IDLE)
            return False

        self._failed_timer = GLib.timeout_add(5000, _reset)

    def destroy(self):
        if self._failed_timer:
            GLib.source_remove(self._failed_timer)
            self._failed_timer = None
        if self._state_signal is not None:
            try:
                self._wifi._device.disconnect(self._state_signal)
            except Exception:
                pass
            self._state_signal = None
        super().destroy()

    def _get_security_icon(self, ap: AccessPoint) -> str:
        return "shield-check-duotone" if ap.psk else "shield-duotone"


class _WifiTab:
    """Owns the UI and signal lifetime for one wifi device's tab."""

    def __init__(self, wifi, tab_stack: "TabStack", on_connect):
        self._wifi = wifi
        self._tab_stack = tab_stack
        self._on_connect = on_connect
        self._ap_items: dict[str, AccessPointItem] = {}
        self._device_signals: list[int] = []

        nm_device = wifi._device
        self._tab_name = nm_device.get_iface()
        tab_label = nm_device.get_description() or self._tab_name

        self._ap_box = Box(orientation="v", spacing=6)

        self._placeholder = Box(
            style_classes=["menu-list-placeholder", "tab"],
            h_align="fill", v_align="fill", h_expand=True, v_expand=True,
            children=[
                Label(
                    v_expand=True, v_align="center",
                    h_expand=True, h_align="center",
                    label="No networks found",
                    style_classes=["menu-list-placeholder-label"],
                )
            ],
        )

        self._content_stack = Stack(
            transition_duration=200,
            transition_type="crossfade",
            children=[
                self._ap_box,
                self._placeholder,
            ],
        )

        for nm_ap in nm_device.get_access_points():
            self._add_ap_from_nm(nm_ap)

        self._update_placeholder()
        self.sort_items()

        self._device_signals.append(
            nm_device.connect(
                "access-point-added",
                lambda _, nm_ap: self._on_ap_added(nm_ap),
            )
        )
        self._device_signals.append(
            nm_device.connect(
                "access-point-removed",
                lambda _, nm_ap: self._on_ap_removed(nm_ap),
            )
        )

        tab_stack.add_tab(
            name=self._tab_name,
            label=tab_label,
            content=TabMenu(child=self._content_stack),
        )

    # ------------------------------------------------------------------ #

    def _make_ap_dict(self, nm_ap) -> dict:
        from gi.repository import NM
        ssid_data = nm_ap.get_ssid()
        return {
            "bssid": nm_ap.get_bssid(),
            "last_seen": nm_ap.get_last_seen(),
            "ssid": NM.utils_ssid_to_utf8(ssid_data.get_data()) if ssid_data else "Unknown",
            "active-ap": self._wifi._ap,
            "strength": nm_ap.get_strength(),
            "frequency": nm_ap.get_frequency(),
            "security": nm_ap.get_rsn_flags() or nm_ap.get_wpa_flags(),
            "psk": bool(nm_ap.get_rsn_flags() or nm_ap.get_wpa_flags()),
        }

    def _add_ap_from_nm(self, nm_ap):
        ap_dict = self._make_ap_dict(nm_ap)
        bssid = ap_dict.get("bssid")
        if not bssid or bssid in self._ap_items:
            return
        ap = AccessPoint(ap_dict, self._wifi)
        item = AccessPointItem(ap, on_connect=self._on_connect, wifi=self._wifi, tab=self)
        self._ap_items[bssid] = item
        self._ap_box.add(item)

    def sort_items(self):
        active_ap = self._wifi._device.get_active_access_point()
        active_bssid = active_ap.get_bssid() if active_ap else None

        items = list(self._ap_items.values())
        items.sort(key=lambda item: (
            item.ap._dict.get("bssid") == active_bssid or item._state == APState.CONNECTED,
            item.ap.strength,
        ), reverse=True)

        for i, item in enumerate(items):
            if item.get_parent() == self._ap_box:
                self._ap_box.reorder_child(item, i)

    def _on_ap_added(self, nm_ap):
        self._add_ap_from_nm(nm_ap)
        self.sort_items()
        self._update_placeholder()

    def _on_ap_removed(self, nm_ap):
        bssid = nm_ap.get_bssid()
        item = self._ap_items.pop(bssid, None)
        if item:
            self._ap_box.remove(item)
            item.destroy()
        self.sort_items()
        self._update_placeholder()

    def _update_placeholder(self):
        if self._ap_items:
            self._content_stack.set_visible_child(
                self._content_stack.get_children()[0]
            )
        else:
            self._content_stack.set_visible_child(self._placeholder)

    def get_ap_item(self, bssid: str) -> AccessPointItem | None:
        return self._ap_items.get(bssid)

    # ------------------------------------------------------------------ #

    def destroy(self):
        for sig_id in self._device_signals:
            try:
                self._wifi._device.disconnect(sig_id)
            except Exception:
                pass
        self._device_signals.clear()

        for item in list(self._ap_items.values()):
            item.destroy()
        self._ap_items.clear()

        self._tab_stack.remove_tab(self._tab_name)


class WifiMenu(QSAppletPage):
    def __init__(self, parent=None, stack=None, **kwargs):
        self.stack = stack
        self.tab_stack = TabStack()
        self._wifi_tabs: dict[str, _WifiTab] = {}   # iface -> _WifiTab

        self.switch = SmoothSwitch(
            style_classes=["smooth-switch"],
            active=False,
            v_align="center",
            v_expand=False,
            on_user_toggle=self._on_user_toggled_wifi,
            width=48,
        )
        super().__init__(
            title="Wifi",
            stack=stack if not parent else None,
            switch=self.switch,
            button_icon_name="arrows-clockwise-duotone",
            button_action=lambda btn: self._scan(btn),
            child=self.tab_stack,
            **kwargs,
        )

        network.connect("device-added",   self._on_network_device_added)
        network.connect("device-removed", self._on_network_device_removed)
        network.connect("device-ready",   self._on_device_ready)

        # populate any devices already present
        for iface, wifi in network.wifi_devices.items():
            self._add_wifi_tab(iface, wifi)
        self._sync_switch()

        self._password_menu = WifiPasswordMenu(stack=stack)
        self.connect("realize", self._add_password_menu)

    # ------------------------------------------------------------------ #
    # Switch

    def _sync_switch(self):
        # enabled if any device is on
        enabled = any(w.enabled for w in network.wifi_devices.values())
        self.switch.set_active(enabled)

    def _on_user_toggled_wifi(self, val: bool):
        for wifi in network.wifi_devices.values():
            GLib.idle_add(lambda w=wifi: setattr(w, "enabled", val))

    # ------------------------------------------------------------------ #
    # Device lifecycle

    def _on_device_ready(self, *_):
        # legacy signal — sync switch state
        self._sync_switch()

    def _on_network_device_added(self, _, iface: str):
        wifi = network.wifi_devices.get(iface)
        if wifi and iface not in self._wifi_tabs:
            self._add_wifi_tab(iface, wifi)
        self._sync_switch()

    def _on_network_device_removed(self, _, iface: str):
        tab = self._wifi_tabs.pop(iface, None)
        if tab:
            tab.destroy()
        self._sync_switch()

    def _add_wifi_tab(self, iface: str, wifi):
        if iface in self._wifi_tabs:
            self._wifi_tabs.pop(iface).destroy()
        tab = _WifiTab(wifi, self.tab_stack, on_connect=self._handle_ap_connect)
        wifi.connect("notify::enabled", lambda *_: self._sync_switch())
        self._wifi_tabs[iface] = tab

    # ------------------------------------------------------------------ #
    # Password menu

    def _add_password_menu(self, *_):
        self.stack.add_named(self._password_menu, "wifi-password")

    # ------------------------------------------------------------------ #
    # Scan

    def _scan(self, button):
        for wifi in network.wifi_devices.values():
            wifi.scan()
        button.get_child().set_active(True)
        GLib.timeout_add(
            5_000,
            lambda: (button.get_child().set_active(False), False)[1],
        )

    # ------------------------------------------------------------------ #
    # AP connection handling (shared across all tabs)

    def get_ap_item(self, bssid: str) -> AccessPointItem | None:
        for tab in self._wifi_tabs.values():
            item = tab.get_ap_item(bssid)
            if item:
                return item
        return None

    def _handle_ap_connect(self, ap: AccessPoint):
        iface = (ap._device._device.get_iface() if hasattr(ap._device, "_device") and ap._device._device else None)
        bssid = ap._dict.get("bssid", "")
        ssid = ap.ssid

        if not ap.psk:
            def _cb(success: bool, msg: str):
                if not success:
                    item = self.get_ap_item(bssid)
                    if item:
                        item.set_failed()
            network.connect_wifi_bssid(bssid, ssid=ssid, iface=iface, callback=_cb)
            return

        if network.is_network_saved(ssid):
            def _cb(success: bool, msg: str):
                if not success:
                    item = self.get_ap_item(bssid)
                    if item:
                        item.set_failed()
                    self._password_menu.load(
                        ssid=ssid,
                        bssid=bssid,
                        on_submit=self._on_password_submit,
                        on_cancel=lambda: self._reset_ap_item(bssid),
                    )
                    self._password_menu.show_error("Saved credentials failed. Please re-enter password.")
                    if self.stack:
                        self.stack.set_visible_child_name("wifi-password")
            network.connect_wifi_bssid(bssid, ssid=ssid, iface=iface, callback=_cb)
            return

        self._password_menu.load(
            ssid=ssid,
            bssid=bssid,
            on_submit=self._on_password_submit,
            on_cancel=lambda: self._reset_ap_item(bssid),
        )
        if self.stack:
            self.stack.set_visible_child_name("wifi-password")

    def _reset_ap_item(self, bssid: str):
        item = self.get_ap_item(bssid)
        if item:
            item._set_state(APState.IDLE)

    def _on_password_submit(self, bssid: str, password: str):
        item = self.get_ap_item(bssid)
        ssid = item.ap.ssid if item else None
        iface = (item._wifi._device.get_iface() if item and hasattr(item._wifi, "_device") and item._wifi._device else None)

        def _result(success: bool, message: str):
            if success:
                self._password_menu.show_connected()
                GLib.timeout_add(
                    1500,
                    lambda: (
                        self.stack.set_visible_child_name("wifi") if self.stack else None,
                        False,
                    )[1],
                )
            else:
                self._password_menu.show_error(message)
                item = self.get_ap_item(bssid)
                if item:
                    item.set_failed()

        network.connect_wifi_with_password(bssid, password, ssid=ssid, iface=iface, callback=_result)