from fabric.widgets.box import Box
from fabric.widgets.button import Button
from fabric.widgets.label import Label
from fabric.widgets.entry import Entry
from fabric.widgets.grid import Grid
from gi.repository import Gtk, Gdk, GLib
from .components import DashPage, DashGrid
from snippets import Icon, ClippingScrolledWindow, SmoothSwitch
from services.awe_service import AweService, AWE_THEMES
from utils.sounds import play_sound

AWE_WIDGETS_DATA: list[dict] = [
    {
        "id": "resourcewheel",
        "name": "Resource Wheel",
        "desc": "CPU, RAM, Disk & Temp dial",
        "icon": "gauge-duotone",
        "qml": "ResourceWheelWidget.qml",
    },
    {
        "id": "clock",
        "name": "Clock",
        "desc": "Customizable desktop clock styles",
        "icon": "clock-duotone",
        "qml": "Clock.qml",
    },
    {
        "id": "calendar",
        "name": "Calendar",
        "desc": "Interactive desktop monthly calendar",
        "icon": "calendar-blank-duotone",
        "qml": "CalendarWidget.qml",
    },
    {
        "id": "media",
        "name": "Media Player",
        "desc": "Now playing audio & controls",
        "icon": "music-notes-duotone",
        "qml": "MediaWidget.qml",
    },
    {
        "id": "sysinfo",
        "name": "System Info",
        "desc": "Processor and memory metrics",
        "icon": "cpu-duotone",
        "qml": "SystemInfo.qml",
    },
    {
        "id": "battery",
        "name": "Battery",
        "desc": "Battery level and power status",
        "icon": "battery-charging-duotone",
        "qml": "BatteryWidget.qml",
    },
    {
        "id": "weather",
        "name": "Weather",
        "desc": "Forecast & real-time conditions",
        "icon": "cloud-sun-duotone",
        "qml": "WeatherWidget.qml",
    },
    {
        "id": "quickcontrols",
        "name": "Quick Controls",
        "desc": "Volume & brightness sliders",
        "icon": "sliders-horizontal-duotone",
        "qml": "VolumeBrightnessWidget.qml",
    },
    {
        "id": "network",
        "name": "Network",
        "desc": "Connection status and IP monitor",
        "icon": "wifi-high-duotone",
        "qml": "NetworkWidget.qml",
    },
    {
        "id": "notes",
        "name": "Quick Notes",
        "desc": "Desktop sticky notes",
        "icon": "note-pencil-duotone",
        "qml": "NotesWidget.qml",
    },
    {
        "id": "todo",
        "name": "Todo List",
        "desc": "Task checklist and todos",
        "icon": "check-square-duotone",
        "qml": "TodoWidget.qml",
    },
    {
        "id": "timer",
        "name": "Focus Timer",
        "desc": "Pomodoro & focus countdown",
        "icon": "timer-duotone",
        "qml": "TimerWidget.qml",
    },
    {
        "id": "thermal",
        "name": "Thermal",
        "desc": "Hardware temperature monitor",
        "icon": "thermometer-duotone",
        "qml": "ThermalWidget.qml",
    },
    {
        "id": "quote",
        "name": "Daily Quotes",
        "desc": "Inspiring daily motivational quotes",
        "icon": "quotes-duotone",
        "qml": "QuoteWidget.qml",
    },
    {
        "id": "clipboard",
        "name": "Clipboard",
        "desc": "Quick clipboard history picker",
        "icon": "clipboard-text-duotone",
        "qml": "ClipboardWidget.qml",
    },
    {
        "id": "crypto",
        "name": "Crypto Tracker",
        "desc": "Cryptocurrency price tracker",
        "icon": "currency-btc-duotone",
        "qml": "CryptoWidget.qml",
    },
    {
        "id": "worldclock",
        "name": "World Clock",
        "desc": "Multi-timezone world clocks",
        "icon": "globe-duotone",
        "qml": "WorldClockWidget.qml",
    },
    {
        "id": "git",
        "name": "Git Dashboard",
        "desc": "Repository stats and activity",
        "icon": "git-branch-duotone",
        "qml": "GitDashboardWidget.qml",
    },
    {
        "id": "visualizer",
        "name": "Visualizer",
        "desc": "Live desktop audio spectrum",
        "icon": "waveform-duotone",
        "qml": "VisualizerWidget.qml",
    },
    {
        "id": "habits",
        "name": "Habits",
        "desc": "Daily streak and habit tracker",
        "icon": "target-duotone",
        "qml": "HabitsWidget.qml",
    },
    {
        "id": "ping",
        "name": "Ping Monitor",
        "desc": "Internet latency monitor",
        "icon": "broadcast-duotone",
        "qml": "PingWidget.qml",
    },
    {
        "id": "storagemap",
        "name": "Storage Map",
        "desc": "Disk drive partition visualization",
        "icon": "hard-drive-duotone",
        "qml": "StorageMapWidget.qml",
    },
    {
        "id": "calc",
        "name": "Calculator",
        "desc": "Desktop interactive calculator",
        "icon": "calculator-duotone",
        "qml": "CalcWidget.qml",
    },
    {
        "id": "poster",
        "name": "Poster / Photo",
        "desc": "Custom desktop image display",
        "icon": "image-duotone",
        "qml": "PosterWidget.qml",
    },
]


class DashWidgetItem(Button):
    def __init__(self, data: dict, on_toggle: callable):
        self.data = data
        self.widget_id = data["id"]
        self._on_toggle = on_toggle

        self._icon = Icon(v_expand=True, v_align="end", icon_name=data["icon"], icon_size=48)
        self._title_label = Label(
            label=data["name"],
            v_expand=False,
            v_align="center",
            h_align="center",
            ellipsization="end",
            max_chars_width=12,
            style="font-size: 13px; font-weight: 600; margin-bottom: 2px;",
        )
        self._status_label = Label(
            label="Active",
            v_expand=False,
            v_align="center",
            h_align="center",
            style="font-size: 10px; opacity: 0.7;",
        )

        self.box = Box(
            orientation="v",
            spacing=6,
            children=[
                self._icon,
                self._title_label,
                self._status_label,
            ],
        )

        super().__init__(
            style_classes=["dash-applet-item"],
            child=self.box,
            h_expand=False,
            h_align="center",
            v_expand=True,
            v_align="center",
            on_clicked=self._on_item_clicked,
        )
        self.refresh_state()

    def _on_item_clicked(self, *_):
        if self._on_toggle:
            self._on_toggle(self.widget_id)

    def refresh_state(self) -> None:
        service = AweService.get_instance()
        is_visible = service.get_visibility(self.widget_id)

        ctx = self.box.get_style_context()
        if is_visible:
            ctx.remove_class("in-bar")
            self._status_label.set_text("Active")
            self._icon.set_opacity(1.0)
            self._title_label.set_opacity(1.0)
            self._status_label.set_opacity(0.85)
        else:
            ctx.add_class("in-bar")
            self._status_label.set_text("Hidden")
            self._icon.set_opacity(0.4)
            self._title_label.set_opacity(0.5)
            self._status_label.set_opacity(0.4)


class DashWidgetThemeChip(Button):
    def __init__(self, data: dict, on_select: callable):
        self.data = data
        self.theme_id = data["id"]
        self._on_select = on_select

        # Phosphor SVG Icon - no emojis
        self._icon = Icon(
            icon_name=data.get("icon", "palette-duotone"),
            icon_size=13,
            v_align="center",
        )

        accent_color = data.get("accent", "#C2E7FF")
        self._accent_dot = Box(
            v_align="center",
            v_expand=False,
            style=f"background-color: {accent_color}; border-radius: 99px; min-width: 6px; min-height: 6px;",
        )

        self._name_lbl = Label(
            label=data["name"],
            v_align="center",
            style="font-size: 11px; font-weight: 500;",
        )

        content = Box(
            orientation="h",
            spacing=5,
            v_align="center",
            h_align="center",
            children=[
                self._icon,
                self._accent_dot,
                self._name_lbl,
            ],
        )

        super().__init__(
            style_classes=["widget-theme-chip"],
            child=content,
            h_expand=False,
            v_expand=False,
            v_align="center",
            tooltip_text=f"{data['name']} — {data.get('desc', '')}",
            on_clicked=self._on_clicked,
        )

    def _on_clicked(self, *_):
        if self._on_select:
            self._on_select(self.theme_id)

    def set_active(self, is_active: bool) -> None:
        if is_active:
            self.add_style_class("active")
            self._name_lbl.set_style("font-size: 11px; font-weight: 700; color: var(--primary);")
        else:
            self.remove_style_class("active")
            self._name_lbl.set_style("font-size: 11px; font-weight: 500; opacity: 0.85;")


class DashWidgetsPage(Box):
    def __init__(self, window=None, bar_manager=None):
        self.window = window
        self._bar_manager = bar_manager
        self._search_entry: Entry | None = None
        self._monitor_obj = None
        self._monitor_id: int | None = None
        self._service = AweService.get_instance()

        # ── Top Control Bar ──────────────────────────────────────────────────
        self._master_switch = SmoothSwitch(
            style_classes=["dash-switch"],
            v_expand=False,
            v_align="center",
            on_user_toggle=self._on_master_toggled,
            width=52,
        )
        self._status_badge = Label(
            label="Stopped",
            style_classes=["dash-header-badge"],
            style="font-size: 11px; font-weight: 600; padding: 4px 10px; border-radius: 12px; opacity: 0.8;",
        )

        top_left_box = Box(
            orientation="v",
            spacing=2,
            h_align="start",
            v_align="center",
            children=[
                Label(
                    label="Desktop Widgets",
                    style="font-size: 16px; font-weight: 700;",
                    h_align="start",
                ),
                Label(
                    label="Click widget cards below to toggle individual desktop widgets",
                    style="font-size: 11px; opacity: 0.6;",
                    h_align="start",
                ),
            ],
        )

        top_right_box = Box(
            orientation="h",
            spacing=12,
            h_align="end",
            v_align="center",
            children=[
                self._status_badge,
                self._master_switch,
            ],
        )

        top_bar = Box(
            orientation="h",
            h_align="fill",
            v_align="center",
            h_expand=True,
            style="padding: 0px 8px 8px 8px;",
            children=[
                top_left_box,
                Box(h_expand=True),
                top_right_box,
            ],
        )

        # ── Theme Selector Bar ───────────────────────────────────────────────
        theme_title = Label(
            label="Theme",
            style="font-size: 11px; font-weight: 700; letter-spacing: 0.5px; opacity: 0.6; margin-right: 4px;",
            v_align="center",
        )

        self._theme_chips: dict[str, DashWidgetThemeChip] = {}
        chips_box = Box(
            orientation="h",
            spacing=6,
            v_align="center",
            h_align="start",
            h_expand=True,
            style="padding: 2px 0px;",
        )
        for t_data in AWE_THEMES:
            chip = DashWidgetThemeChip(t_data, on_select=self._handle_theme_select)
            self._theme_chips[t_data["id"]] = chip
            chips_box.add(chip)

        theme_bar = Box(
            orientation="h",
            spacing=8,
            h_align="fill",
            v_align="center",
            h_expand=True,
            style="padding: 0px 8px 6px 8px;",
            children=[
                theme_title,
                chips_box,
            ],
        )

        # ── Widgets Grid ─────────────────────────────────────────────────────
        self._items: list[DashWidgetItem] = []
        self._item_map: dict[str, DashWidgetItem] = {}
        for data in AWE_WIDGETS_DATA:
            item = DashWidgetItem(data, on_toggle=self._handle_widget_toggle)
            self._items.append(item)
            self._item_map[data["id"]] = item

        self.grid = DashGrid(children=[self._items])

        self.scroll = ClippingScrolledWindow(
            h_expand=False,
            h_align="center",
            style_classes=["dash-grid"],
            child=self.grid,
            max_content_size=(1104, 480),
            fade_distance=56,
            overlay_scroll=True,
            kinetic_scroll=True,
            h_scrollbar_policy="never",
            v_scrollbar_policy="automatic",
        )
        self.scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.scroll.set_size_request(1104, 480)

        main_container = Box(
            orientation="v",
            spacing=8,
            h_align="center",
            v_align="center",
            children=[
                top_bar,
                theme_bar,
                self.scroll,
            ],
        )

        super().__init__(
            orientation="v",
            v_align="center",
            h_align="center",
            spacing=20,
            children=[main_container],
        )

        self._service.connect("status-changed", lambda _, running: self._sync_service_state())
        self._service.connect("visibility-changed", lambda _, w_id, __: self._sync_item_state(w_id))
        self._service.connect("theme-changed", lambda _, t_id: self._sync_theme_state(t_id))
        self._sync_service_state()
        self._sync_theme_state()

    def _handle_theme_select(self, theme_id: str):
        try:
            self._service.set_theme(theme_id)
            play_sound("widget-placed")
        except Exception:
            pass
        self._sync_theme_state(theme_id)

    def _sync_theme_state(self, active_id: str | None = None):
        if active_id is None:
            active_id = self._service.get_theme()
        for t_id, chip in self._theme_chips.items():
            chip.set_active(t_id == active_id)

    def _on_master_toggled(self, is_active: bool):
        try:
            if is_active:
                self._service.start()
            else:
                self._service.stop()
        except Exception as e:
            pass
        self._sync_service_state()

    def _handle_widget_toggle(self, widget_id: str):
        try:
            self._service.toggle_widget_visibility(widget_id)
            play_sound("widget-placed")
        except Exception:
            pass
        self._sync_item_state(widget_id)

    def _sync_service_state(self):
        running = self._service.is_running()
        self._master_switch.set_active(running)
        if running:
            self._status_badge.set_text("Running")
            self._status_badge.set_style("font-size: 11px; font-weight: 600; padding: 4px 10px; border-radius: 12px; color: #73daca; background-color: rgba(115, 218, 202, 0.15);")
        else:
            self._status_badge.set_text("Inactive")
            self._status_badge.set_style("font-size: 11px; font-weight: 600; padding: 4px 10px; border-radius: 12px; color: #9ca8ac; background-color: rgba(156, 168, 172, 0.1);")

    def _sync_item_state(self, widget_id: str):
        item = self._item_map.get(widget_id.lower())
        if item:
            item.refresh_state()

    def set_monitor(self, monitor_obj) -> None:
        if monitor_obj is None or monitor_obj is self._monitor_obj:
            return
        self._monitor_obj = monitor_obj
        display = Gdk.Display.get_default()
        for i in range(display.get_n_monitors()):
            if display.get_monitor(i) == monitor_obj:
                self._monitor_id = i
                break

    def _attach_search_entry(self, entry: Entry):
        if self._search_entry is entry:
            return
        if self._search_entry is not None:
            try:
                self._search_entry.disconnect_by_func(self._search)
                self._search_entry.disconnect_by_func(self._on_entry_key_press)
            except Exception:
                pass
        self._search_entry = entry
        entry.connect("changed", self._search)
        entry.connect("key-press-event", self._on_entry_key_press)

    def _search(self, entry: Entry):
        query = entry.get_text().strip().lower()
        for item in self._items:
            data = item.data
            name = data["name"].lower()
            desc = data["desc"].lower()
            widget_id = data["id"].lower()
            matches = not query or (query in name or query in desc or query in widget_id)
            item.set_visible(matches)

    def _on_entry_key_press(self, widget, event):
        return False
