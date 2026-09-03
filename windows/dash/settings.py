from __future__ import annotations
import os
from fabric.widgets.box import Box
from fabric.widgets.button import Button
from fabric.widgets.label import Label
from fabric.widgets.stack import Stack
from gi.repository import Gtk, GLib, Gdk
from snippets import Icon, ClippingScrolledWindow, ClippingBox, SmoothSwitch, FlatScale
from user_options import user_options
import services.singletons as singletons
from .themes import Section

WIDGET_ICONS: dict[str, str] = {
    "Dash":          "diamonds-four-duotone",
    "Launcher":      "squares-four-duotone",
    "Processes":     "cpu-duotone",
    "SysMon":        "chart-line-up-duotone",
    "Weather":       "cloud-sun-duotone",
    "Media":         "play-circle-duotone",
    "Dock":          "app-window-duotone",
    "Tray":          "caret-up-duotone",
    "Calendar":      "calendar-blank-duotone",
    "Clock":         "clock-duotone",
    "Settings":      "gear-six-duotone",
    "Notifications": "bell-duotone",
    "Energy":        "battery-charging-duotone",
    "Bluetooth":     "bluetooth-duotone",
    "Volume":        "speaker-high-duotone",
    "Wifi":          "wifi-high-duotone",
    "Session":       "power-duotone",
    "Calculator":    "calculator-duotone",
    "Keyboard":      "keyboard-duotone",
    "Screenshot":    "camera-duotone",
    "Brightness":    "sun-dim-duotone",
    "Clipboard":     "clipboard-text-duotone",
    "Caffeine":      "coffee-duotone",
    "NightLight":    "moon-stars-duotone",
    "Workspaces":    "stack-duotone",
    "Focused":       "text-t-duotone",
}

ALL_AVAILABLE_WIDGETS: list[str] = [
    "Dash", "Launcher", "SysMon", "Processes", "Clipboard", "Caffeine", "NightLight",
    "Media", "Weather", "Volume", "Brightness", "Energy", "Wifi", "Bluetooth",
    "Clock", "Calendar", "Notifications", "Settings", "Tray", "Dock", "Workspaces",
    "Calculator", "Keyboard", "Screenshot", "Session", "Focused"
]


class HoverWidgetChip(Button):
    def __init__(self, widget_name: str, is_active: bool, on_toggle):
        self.widget_name = widget_name
        self._is_active = is_active
        self._on_toggle = on_toggle

        icon_name = WIDGET_ICONS.get(widget_name, "app-window-duotone")
        self._icon = Icon(icon_name=icon_name, icon_size=14)
        self._label = Label(label=widget_name, style="font-size: 11px; font-weight: 500;")

        box = Box(
            orientation="h",
            spacing=6,
            children=[self._icon, self._label],
        )

        classes = ["hover-widget-chip"]
        if is_active:
            classes.append("active")

        super().__init__(
            child=box,
            style_classes=classes,
            on_clicked=self._clicked,
        )

    def _clicked(self, *_):
        self._is_active = not self._is_active
        self.set_active_state(self._is_active)
        self._on_toggle(self.widget_name, self._is_active)

    def set_active_state(self, active: bool):
        self._is_active = active
        if active:
            self.add_style_class("active")
        else:
            self.remove_style_class("active")


class BarWidgetChip(Box):
    def __init__(self, section_name: str, widget_entry: str | dict, on_remove):
        key = widget_entry["widget"] if isinstance(widget_entry, dict) else widget_entry
        variant = widget_entry.get("variant") if isinstance(widget_entry, dict) else None
        icon_name = WIDGET_ICONS.get(key, "app-window-duotone")

        icon = Icon(icon_name=icon_name, icon_size=16)
        label_text = f"{key} ({variant})" if variant else key
        label = Label(label=label_text, style="font-size: 12px; font-weight: 500;")

        remove_btn = Button(
            child=Icon(icon_name="x", icon_size=12),
            style_classes=["bar-chip-remove-btn"],
            on_clicked=lambda *_: on_remove(section_name, widget_entry),
        )

        super().__init__(
            orientation="h",
            spacing=6,
            style_classes=["bar-widget-chip"],
            children=[icon, label, remove_btn],
        )


BAR_THEME_PRESETS = [
    {
        "id": "liquid-glass",
        "name": "Liquid Glass",
        "desc": "Glass reflection highlights with backdrop blur",
        "icon": "drop-duotone",
        "bar_opacity": 0.35,
        "widget_opacity": 0.55,
        "blur": True,
    },
    {
        "id": "blurred",
        "name": "Frosted Blur",
        "desc": "Deep frosted milky blur with soft containers",
        "icon": "cloud-fog-duotone",
        "bar_opacity": 0.65,
        "widget_opacity": 0.75,
        "blur": True,
    },
    {
        "id": "transparent",
        "name": "Pure Clear",
        "desc": "Invisible bar with floating pill widgets",
        "icon": "frame-corners-duotone",
        "bar_opacity": 0.0,
        "widget_opacity": 0.85,
        "blur": False,
    },
    {
        "id": "tinted-glass",
        "name": "Tinted Glass",
        "desc": "Accent-tinted glass with subtle glow",
        "icon": "palette-duotone",
        "bar_opacity": 0.45,
        "widget_opacity": 0.60,
        "blur": True,
    },
    {
        "id": "default",
        "name": "Classic Solid",
        "desc": "Standard solid Material theme styling",
        "icon": "square-duotone",
        "bar_opacity": 1.0,
        "widget_opacity": 1.0,
        "blur": False,
    },
]


class BarThemeCard(Button):
    def __init__(
        self,
        theme_id: str,
        title: str,
        description: str,
        icon_name: str,
        is_active: bool,
        on_select,
        **kwargs,
    ):
        self.theme_id = theme_id
        self._on_select = on_select

        self._icon = Icon(icon_name=icon_name, icon_size=20)
        self._title_label = Label(
            label=title,
            style_classes=["bar-theme-card-title"],
            style="font-size: 13px; font-weight: 600;",
            h_align="start",
        )
        self._desc_label = Label(
            label=description,
            style="font-size: 10.5px; opacity: 0.65;",
            h_align="start",
            line_wrap="word-char",
        )
        self._desc_label.set_lines(2)

        header_box = Box(
            orientation="h",
            spacing=8,
            h_align="fill",
            children=[
                self._icon,
                Box(
                    orientation="v",
                    spacing=2,
                    h_align="start",
                    h_expand=True,
                    children=[self._title_label],
                ),
            ],
        )

        preview_box = Box(
            style_classes=["bar-theme-preview-box", theme_id],
            h_align="fill",
            h_expand=True,
            children=[
                Box(
                    orientation="h",
                    spacing=4,
                    h_align="center",
                    children=[
                        Box(style="min-width: 14px; min-height: 8px; border-radius: 3px; background: rgba(255,255,255,0.3);"),
                        Box(style="min-width: 24px; min-height: 8px; border-radius: 3px; background: rgba(255,255,255,0.3);"),
                        Box(style="min-width: 14px; min-height: 8px; border-radius: 3px; background: rgba(255,255,255,0.3);"),
                    ],
                )
            ],
        )

        card_content = Box(
            orientation="v",
            spacing=6,
            children=[
                header_box,
                self._desc_label,
                preview_box,
            ],
        )

        classes = ["bar-theme-card"]
        if is_active:
            classes.append("active")

        super().__init__(
            style_classes=classes,
            child=card_content,
            on_clicked=self._clicked,
            h_expand=True,
            **kwargs,
        )

    def _clicked(self, *_):
        self._on_select(self.theme_id)

    def set_active_state(self, active: bool):
        if active:
            self.add_style_class("active")
        else:
            self.remove_style_class("active")


class SettingsNavButton(Button):
    def __init__(
        self,
        page_id: str,
        title: str,
        subtitle: str,
        icon_name: str,
        on_clicked_cb,
        is_active: bool = False,
    ):
        self.page_id = page_id
        self._on_clicked_cb = on_clicked_cb

        self._icon = Icon(icon_name=icon_name, icon_size=20)
        self._title_label = Label(
            label=title,
            style="font-size: 13px; font-weight: 600;",
            h_align="start",
            style_classes=["settings-nav-title"],
        )
        self._sub_label = Label(
            label=subtitle,
            style="font-size: 10.5px; opacity: 0.65;",
            h_align="start",
            style_classes=["settings-nav-subtitle"],
        )
        text_box = Box(
            orientation="v",
            spacing=2,
            h_align="start",
            v_align="center",
            h_expand=True,
            children=[self._title_label, self._sub_label],
        )

        content_box = Box(
            orientation="h",
            spacing=12,
            h_align="fill",
            v_align="center",
            children=[self._icon, text_box],
        )

        classes = ["dash-settings-nav-btn"]
        if is_active:
            classes.append("active")

        super().__init__(
            child=content_box,
            style_classes=classes,
            on_clicked=lambda *_: self._on_clicked_cb(self.page_id),
            h_align="fill",
            h_expand=True,
        )

    def set_active_state(self, active: bool):
        if active:
            self.add_style_class("active")
        else:
            self.remove_style_class("active")


def create_settings_card(
    title: str | None = None,
    description: str | None = None,
    rows: list[Gtk.Widget] | None = None,
    header_action: Gtk.Widget | None = None,
    body_widget: Gtk.Widget | None = None,
) -> Box:
    """
    Modern GNOME/macOS-style grouped card container with header and clean dividers.
    """
    card_box = Box(
        orientation="v",
        spacing=0,
        h_align="fill",
        h_expand=True,
        style_classes=["dash-settings-card"],
    )

    if title:
        header_row = Box(
            orientation="h",
            spacing=8,
            h_align="fill",
            style_classes=["dash-settings-card-header"],
        )
        title_col = Box(
            orientation="v",
            spacing=2,
            h_align="start",
            h_expand=True,
            children=[
                Label(label=title, style="font-size: 13.5px; font-weight: 700;", h_align="start"),
            ],
        )
        if description:
            title_col.add(
                Label(label=description, style="font-size: 11px; opacity: 0.65;", h_align="start")
            )
        header_row.add(title_col)
        if header_action:
            header_row.add(header_action)
        card_box.add(header_row)

        if rows or body_widget:
            card_box.add(Box(style_classes=["dash-settings-divider"]))

    if rows:
        for idx, row in enumerate(rows):
            card_box.add(row)
            if idx < len(rows) - 1:
                card_box.add(Box(style_classes=["dash-settings-divider"]))

    if body_widget:
        card_box.add(body_widget)

    return card_box


def create_setting_row(
    title: str,
    subtitle: str,
    control: Gtk.Widget,
    control_min_width: int | None = 224,
) -> Box:
    """
    Individual setting row with title/description on the left and control on the right.
    """
    title_col = Box(
        orientation="v",
        spacing=2,
        h_align="start",
        h_expand=True,
        children=[
            Label(label=title, style_classes=["dim-label"], style="font-size: 12.5px; font-weight: 600;", h_align="start"),
            Label(label=subtitle, style="font-size: 11px; opacity: 0.6;", h_align="start", line_wrap="word-char"),
        ],
    )
    ctl_box = Box(
        h_align="end",
        v_align="center",
        children=[control],
    )
    if control_min_width:
        ctl_box.set_style(f"min-width: {control_min_width}px;")

    return Box(
        orientation="h",
        spacing=12,
        h_align="fill",
        style_classes=["dash-settings-row"],
        children=[title_col, ctl_box],
    )


def create_slider_row(
    title: str,
    subtitle: str,
    slider: FlatScale,
    value_badge: Label,
    control_min_width: int = 240,
) -> Box:
    """
    Pairs a FlatScale with an inline value badge (e.g. '60%', '180ms')
    and sets proper layout constraints so it can be dragged smoothly.
    """
    badge_box = Box(
        orientation="h",
        h_align="center",
        v_align="center",
        style="min-width: 50px; padding: 3px 8px; border-radius: 6px; background-color: var(--surface_container_high);",
        children=[value_badge],
    )
    control_box = Box(
        orientation="h",
        spacing=10,
        h_align="end",
        v_align="center",
        children=[slider, badge_box],
    )
    control_box.set_style(f"min-width: {control_min_width}px;")

    return create_setting_row(
        title=title,
        subtitle=subtitle,
        control=control_box,
        control_min_width=control_min_width,
    )


def create_page_header(title: str, description: str, icon_name: str) -> Box:
    """
    Hero header at the top of each settings view.
    """
    icon = Icon(icon_name=icon_name, icon_size=24)
    title_lbl = Label(
        label=title,
        style="font-size: 17px; font-weight: 700;",
        style_classes=["dash-settings-page-title"],
        h_align="start",
    )
    desc_lbl = Label(
        label=description,
        style="font-size: 11.5px; opacity: 0.7;",
        h_align="start",
    )
    text_box = Box(orientation="v", spacing=2, h_align="start", children=[title_lbl, desc_lbl])
    return Box(
        orientation="h",
        spacing=14,
        h_align="fill",
        style_classes=["dash-settings-page-header"],
        children=[icon, text_box],
    )


class DashSettingsPage(Box):
    """
    Modernized Dash settings page featuring a vertical navigation sidebar
    and grouped setting card pages:
      - Bar Behaviour (Hover-to-Open, Delay, Triggers)
      - Bar Themes & Appearance (Style presets, Blur, Opacity levels)
      - Active Bar Widgets (Bar instances, Left, Center, Right slots)
      - Bar Position & Layout (Screen edge, Alignment, Min-width, Dock, Auto-hide)
      - Dash Appearance & Wallpaper Effects (Backdrop blur, Dim, Tiles, Animations)
    """

    def __init__(self, bar_manager=None, **kwargs):
        self._bar_manager = bar_manager
        self._selected_bar_index = 0
        self._section_boxes: dict[str, Box] = {}
        self._nav_buttons: dict[str, SettingsNavButton] = {}
        self._bar_theme_cards: dict[str, BarThemeCard] = {}
        self._hover_chip_widgets: dict[str, HoverWidgetChip] = {}
        self._setting_trans_buttons: dict[str, Button] = {}
        self._pool_chips: dict[str, Button] = {}

        # Build pages
        page_behavior = self._build_page_behavior()
        page_appearance = self._build_page_appearance()
        page_widgets = self._build_page_widgets()
        page_layout = self._build_page_layout()
        page_dash = self._build_page_dash()

        self._stack = Stack(
            transition_type="crossfade",
            transition_duration=200,
            h_expand=False,
            v_expand=True,
            style_classes=["dash-settings-stack"],
        )
        self._stack.set_size_request(822, 604)
        self._stack.set_homogeneous(False)
        self._stack.add_named(self._wrap_scroll(page_behavior), "bar_behavior")
        self._stack.add_named(self._wrap_scroll(page_appearance), "bar_appearance")
        self._stack.add_named(self._wrap_scroll(page_widgets), "bar_widgets")
        self._stack.add_named(self._wrap_scroll(page_layout), "bar_layout")
        self._stack.add_named(self._wrap_scroll(page_dash), "dash_effects")

        sidebar = self._build_sidebar()

        # Wrap in main layout
        main_box = Box(
            orientation="h",
            spacing=18,
            h_align="fill",
            v_align="fill",
            h_expand=True,
            v_expand=True,
            children=[sidebar, self._stack],
        )

        super().__init__(
            orientation="v",
            v_align="center",
            h_align="center",
            style_classes=["dash-settings-container"],
            children=[main_box],
            **kwargs,
        )
        self.set_size_request(1104, 604)

    def _wrap_scroll(self, content_widget: Gtk.Widget) -> ClippingScrolledWindow:
        scroll = ClippingScrolledWindow(
            h_expand=False,
            v_expand=True,
            child=content_widget,
            max_content_size=(822, 604),
            fade_distance=40,
            overlay_scroll=True,
            kinetic_scroll=False,
            h_scrollbar_policy="never",
            v_scrollbar_policy="automatic",
        )
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroll.set_size_request(822, 604)
        return scroll

    def _build_sidebar(self) -> Box:
        sidebar = Box(
            orientation="v",
            spacing=8,
            h_align="start",
            v_align="fill",
            style_classes=["dash-settings-sidebar"],
        )
        sidebar.set_size_request(264, 604)

        nav_items = [
            ("bar_behavior",   "Bar Behaviour",             "Hover trigger & timing",     "sliders-duotone"),
            ("bar_appearance", "Bar Themes & Appearance",   "Styles, blur & opacities",    "palette-duotone"),
            ("bar_widgets",    "Active Bar Widgets",        "Left, center & right slots", "puzzle-piece-duotone"),
            ("bar_layout",     "Bar Position & Layout",     "Edge, alignment & dock",     "layout-duotone"),
            ("dash_effects",   "Dash & Wallpaper Effects",  "Dim, blur & transitions",    "sparkle-duotone"),
        ]

        for pid, title, subtitle, icon_name in nav_items:
            is_active = (pid == "bar_behavior")
            btn = SettingsNavButton(
                page_id=pid,
                title=title,
                subtitle=subtitle,
                icon_name=icon_name,
                on_clicked_cb=self._switch_page,
                is_active=is_active,
            )
            self._nav_buttons[pid] = btn
            sidebar.add(btn)

        sidebar.add(Box(v_expand=True))
        return sidebar

    def _switch_page(self, page_id: str):
        for pid, btn in self._nav_buttons.items():
            btn.set_active_state(pid == page_id)
        self._stack.set_visible_child_name(page_id)

    def _build_page_behavior(self) -> Box:
        header = create_page_header(
            title="Bar Behaviour",
            description="Configure auto-open interactions, hover debouncing, and interactive widget targets",
            icon_name="sliders-duotone",
        )

        self._hover_switch = SmoothSwitch(
            style_classes=["dash-switch"],
            v_expand=True,
            v_align="center",
            on_user_toggle=self._on_hover_toggled,
            width=48,
        )
        self._hover_switch.set_active(getattr(user_options.settings, "hover_open", True))

        hover_row = create_setting_row(
            title="Hover to Open",
            subtitle="Open Dash and bar applets automatically when hovering over them",
            control=self._hover_switch,
            control_min_width=None,
        )

        current_delay = getattr(user_options.settings, "hover_delay", 180)
        self._delay_badge = Label(label=f"{current_delay}ms", style="font-size: 11px; font-weight: 600;")
        self._delay_slider = FlatScale(
            size=(170, 24),
            style_classes=["scale"],
            min_value=50,
            max_value=500,
            step=10,
            value=current_delay,
            value_formatter=lambda val: f"{int(val)}ms",
            h_expand=True,
        )
        self._delay_slider.connect("value-changed", self._on_delay_changed)

        delay_row = create_slider_row(
            title="Hover Delay",
            subtitle="Debounce duration before opening on hover to prevent accidental triggers",
            slider=self._delay_slider,
            value_badge=self._delay_badge,
            control_min_width=240,
        )

        hover_card = create_settings_card(
            title="Hover Interaction",
            description="Control how agility-shell reacts to mouse cursor hover over the bar",
            rows=[hover_row, delay_row],
        )

        # Multi-select chips for hover widgets
        hover_chips_container = Gtk.FlowBox()
        hover_chips_container.set_valign(Gtk.Align.START)
        hover_chips_container.set_max_children_per_line(5)
        hover_chips_container.set_selection_mode(Gtk.SelectionMode.NONE)
        hover_chips_container.set_column_spacing(6)
        hover_chips_container.set_row_spacing(6)
        hover_chips_container.set_homogeneous(False)

        current_hover_list = getattr(user_options.settings, "hover_widgets", ALL_AVAILABLE_WIDGETS)

        for w_name in ALL_AVAILABLE_WIDGETS:
            is_active = w_name in current_hover_list
            chip = HoverWidgetChip(
                widget_name=w_name,
                is_active=is_active,
                on_toggle=self._on_hover_widget_toggled,
            )
            self._hover_chip_widgets[w_name] = chip
            hover_chips_container.add(chip)

        select_all_btn = Button(
            child=Box(
                orientation="h",
                spacing=4,
                children=[Icon(icon_name="check-circle-duotone", icon_size=12), Label(label="Select All", style="font-size: 11px;")],
            ),
            style_classes=["bar-chip-add-btn"],
            on_clicked=lambda *_: self._set_all_hover_widgets(True),
        )

        deselect_all_btn = Button(
            child=Box(
                orientation="h",
                spacing=4,
                children=[Icon(icon_name="x-circle-duotone", icon_size=12), Label(label="Deselect All", style="font-size: 11px;")],
            ),
            style_classes=["bar-chip-add-btn"],
            on_clicked=lambda *_: self._set_all_hover_widgets(False),
        )

        actions_box = Box(
            orientation="h",
            spacing=6,
            h_align="end",
            children=[select_all_btn, deselect_all_btn],
        )

        chips_wrapper = Box(
            orientation="v",
            spacing=10,
            style="padding: 12px 0 6px 0;",
            children=[hover_chips_container],
        )

        chips_card = create_settings_card(
            title="Hover-Enabled Widgets",
            description="Select which specific widgets automatically open their popup/menu when hovered",
            header_action=actions_box,
            body_widget=chips_wrapper,
        )

        page_box = Box(
            orientation="v",
            spacing=16,
            h_align="fill",
            h_expand=True,
            style="padding: 6px 12px 24px 4px;",
            children=[header, hover_card, chips_card],
        )
        return page_box

    def _build_page_appearance(self) -> Box:
        header = create_page_header(
            title="Bar Themes & Appearance",
            description="Customize styling presets, backdrop blur, and element transparencies",
            icon_name="palette-duotone",
        )

        current_bar_theme = getattr(user_options.settings, "bar_theme", "default")
        theme_cards_box = Box(orientation="h", spacing=8, h_align="fill", h_expand=True)
        for preset in BAR_THEME_PRESETS:
            card = BarThemeCard(
                theme_id=preset["id"],
                title=preset["name"],
                description=preset["desc"],
                icon_name=preset["icon"],
                is_active=(preset["id"] == current_bar_theme),
                on_select=self._on_bar_theme_selected,
            )
            self._bar_theme_cards[preset["id"]] = card
            theme_cards_box.add(card)

        theme_wrapper = Box(
            orientation="v",
            spacing=6,
            style="padding: 10px 0 6px 0;",
            children=[theme_cards_box],
        )

        theme_card = create_settings_card(
            title="Bar Style Preset",
            description="Choose an aesthetic theme preset for the bar (Liquid Glass, Frosted Blur, Pure Clear, Tinted Glass, Classic Solid)",
            body_widget=theme_wrapper,
        )

        self._bar_blur_switch = SmoothSwitch(
            style_classes=["dash-switch"],
            v_expand=True,
            v_align="center",
            on_user_toggle=self._on_bar_blur_toggled,
            width=48,
        )
        self._bar_blur_switch.set_active(getattr(user_options.settings, "bar_blur", True))

        bar_blur_row = create_setting_row(
            title="Bar Background Blur",
            subtitle="Enable hardware-accelerated backdrop blur behind the bar",
            control=self._bar_blur_switch,
            control_min_width=None,
        )

        current_bar_opacity = getattr(user_options.settings, "bar_opacity", 1.0)
        self._bar_opacity_badge = Label(label=f"{round(current_bar_opacity * 100)}%", style="font-size: 11px; font-weight: 600;")
        self._bar_opacity_slider = FlatScale(
            size=(170, 24),
            style_classes=["scale"],
            min_value=0.0,
            max_value=1.0,
            step=0.05,
            value=current_bar_opacity,
            value_formatter=lambda val: f"{round(val * 100)}%",
            h_expand=True,
        )
        self._bar_opacity_slider.connect("value-changed", self._on_bar_opacity_changed)

        bar_opacity_row = create_slider_row(
            title="Bar Background Opacity",
            subtitle="Adjust outer bar background transparency (0% is fully clear)",
            slider=self._bar_opacity_slider,
            value_badge=self._bar_opacity_badge,
            control_min_width=240,
        )

        current_widget_opacity = getattr(user_options.settings, "widget_opacity", 1.0)
        self._widget_opacity_badge = Label(label=f"{round(current_widget_opacity * 100)}%", style="font-size: 11px; font-weight: 600;")
        self._widget_opacity_slider = FlatScale(
            size=(170, 24),
            style_classes=["scale"],
            min_value=0.0,
            max_value=1.0,
            step=0.05,
            value=current_widget_opacity,
            value_formatter=lambda val: f"{round(val * 100)}%",
            h_expand=True,
        )
        self._widget_opacity_slider.connect("value-changed", self._on_widget_opacity_changed)

        widget_opacity_row = create_slider_row(
            title="Bar Widgets Opacity",
            subtitle="Adjust widget pill container opacity (100% solid, 0% transparent)",
            slider=self._widget_opacity_slider,
            value_badge=self._widget_opacity_badge,
            control_min_width=240,
        )

        current_desktop_opacity = getattr(user_options.settings, "desktop_widget_opacity", 1.0)
        self._desktop_opacity_badge = Label(label=f"{round(current_desktop_opacity * 100)}%", style="font-size: 11px; font-weight: 600;")
        self._desktop_opacity_slider = FlatScale(
            size=(170, 24),
            style_classes=["scale"],
            min_value=0.0,
            max_value=1.0,
            step=0.05,
            value=current_desktop_opacity,
            value_formatter=lambda val: f"{round(val * 100)}%",
            h_expand=True,
        )
        self._desktop_opacity_slider.connect("value-changed", self._on_desktop_opacity_changed)

        desktop_opacity_row = create_slider_row(
            title="Desktop Canvas Widgets Opacity",
            subtitle="Adjust card opacity for widgets placed directly on the desktop canvas",
            slider=self._desktop_opacity_slider,
            value_badge=self._desktop_opacity_badge,
            control_min_width=240,
        )

        transparency_card = create_settings_card(
            title="Blur & Transparency Levels",
            description="Fine-tune transparency layers for bar containers and placed desktop widgets",
            rows=[bar_blur_row, bar_opacity_row, widget_opacity_row, desktop_opacity_row],
        )

        page_box = Box(
            orientation="v",
            spacing=16,
            h_align="fill",
            h_expand=True,
            style="padding: 6px 12px 24px 4px;",
            children=[header, theme_card, transparency_card],
        )
        return page_box

    def _build_page_widgets(self) -> Box:
        header = create_page_header(
            title="Active Bar Widgets",
            description="Manage multiple bars and configure widget placements across Left, Center, and Right zones",
            icon_name="puzzle-piece-duotone",
        )

        self._bar_selector_container = Box(orientation="h", spacing=8, h_align="fill")
        self._refresh_bar_selector_ui()

        selector_wrapper = Box(
            orientation="v",
            spacing=6,
            style="padding: 8px 0 4px 0;",
            children=[self._bar_selector_container],
        )

        bar_selector_card = create_settings_card(
            title="Active Bar Configuration",
            description="Select which bar to edit on this monitor or add/remove bars",
            body_widget=selector_wrapper,
        )

        cards = [header, bar_selector_card]

        section_descriptions = {
            "left": "Widgets placed in the left-aligned cluster of the selected bar",
            "center": "Widgets placed in the center cluster of the selected bar",
            "right": "Widgets placed in the right-aligned cluster of the selected bar",
        }

        for sec in ("left", "center", "right"):
            sec_box = Gtk.FlowBox()
            sec_box.set_valign(Gtk.Align.START)
            sec_box.set_max_children_per_line(5)
            sec_box.set_selection_mode(Gtk.SelectionMode.NONE)
            sec_box.set_column_spacing(6)
            sec_box.set_row_spacing(6)
            sec_box.set_homogeneous(False)
            self._section_boxes[sec] = sec_box

            add_btn = Button(
                child=Box(
                    orientation="h",
                    spacing=4,
                    children=[Icon(icon_name="plus-circle-duotone", icon_size=14), Label(label="Add Widget", style="font-size: 11px; font-weight: 500;")],
                ),
                style_classes=["bar-chip-add-btn"],
                on_clicked=lambda _btn, s=sec: self._show_add_widget_menu(_btn, s),
            )

            chips_box = Box(
                orientation="v",
                spacing=6,
                style="padding: 10px 0 6px 0;",
                children=[sec_box],
            )

            sec_card = create_settings_card(
                title=f"{sec.capitalize()} Section Widgets",
                description=section_descriptions.get(sec, ""),
                header_action=add_btn,
                body_widget=chips_box,
            )
            cards.append(sec_card)

        self._refresh_bar_widgets_ui()

        page_box = Box(
            orientation="v",
            spacing=16,
            h_align="fill",
            h_expand=True,
            style="padding: 6px 12px 24px 4px;",
            children=cards,
        )
        return page_box

    def _build_page_layout(self) -> Box:
        header = create_page_header(
            title="Bar Position, Alignment & Layout",
            description="Adjust screen placement, corner alignment, and smart visibility behaviors",
            icon_name="layout-duotone",
        )

        current_pos = self._get_current_bar_alignment()
        self._top_btn = Button(
            child=Box(
                orientation="h",
                spacing=6,
                children=[
                    Icon(icon_name="align-top-duotone", icon_size=16),
                    Label(label="Top"),
                ],
            ),
            style_classes=["option-selection-button"],
            on_clicked=lambda *_: self._set_position("top"),
        )
        self._bottom_btn = Button(
            child=Box(
                orientation="h",
                spacing=6,
                children=[
                    Icon(icon_name="align-bottom-duotone", icon_size=16),
                    Label(label="Bottom"),
                ],
            ),
            style_classes=["option-selection-button"],
            on_clicked=lambda *_: self._set_position("bottom"),
        )
        self._update_position_buttons(current_pos)

        pos_row = create_setting_row(
            title="Screen Edge Position",
            subtitle="Attach the selected bar to the top or bottom screen edge",
            control=Box(
                style_classes=["option-selection-container"],
                orientation="h",
                spacing=6,
                h_align="end",
                children=[self._top_btn, self._bottom_btn],
            ),
            control_min_width=None,
        )

        current_h_align = self._get_current_bar_h_align()
        self._left_align_btn = Button(
            child=Box(
                orientation="h",
                spacing=4,
                children=[
                    Icon(icon_name="align-left-duotone", icon_size=16),
                    Label(label="Left"),
                ],
            ),
            style_classes=["option-selection-button"],
            on_clicked=lambda *_: self._set_horizontal_alignment("left"),
        )
        self._center_align_btn = Button(
            child=Box(
                orientation="h",
                spacing=4,
                children=[
                    Icon(icon_name="text-align-center-duotone", icon_size=16),
                    Label(label="Center"),
                ],
            ),
            style_classes=["option-selection-button"],
            on_clicked=lambda *_: self._set_horizontal_alignment("center"),
        )
        self._right_align_btn = Button(
            child=Box(
                orientation="h",
                spacing=4,
                children=[
                    Icon(icon_name="align-right-duotone", icon_size=16),
                    Label(label="Right"),
                ],
            ),
            style_classes=["option-selection-button"],
            on_clicked=lambda *_: self._set_horizontal_alignment("right"),
        )
        self._update_h_align_buttons(current_h_align)

        h_align_row = create_setting_row(
            title="Bar Alignment & Side",
            subtitle="Move bar to left corner, center, or right corner (active when Compact Min-Width is enabled)",
            control=Box(
                style_classes=["option-selection-container"],
                orientation="h",
                spacing=4,
                h_align="end",
                children=[self._left_align_btn, self._center_align_btn, self._right_align_btn],
            ),
            control_min_width=None,
        )

        placement_card = create_settings_card(
            title="Screen Edge & Alignment",
            description="Configure where the bar sits on the monitor display",
            rows=[pos_row, h_align_row],
        )

        current_minwidth = self._get_current_bar_cfg().get("min_width", False)
        self._bar_minwidth_switch = SmoothSwitch(
            style_classes=["dash-switch"],
            v_expand=True,
            v_align="center",
            on_user_toggle=self._on_bar_minwidth_toggled,
            width=48,
        )
        self._bar_minwidth_switch.set_active(current_minwidth)

        minwidth_row = create_setting_row(
            title="Compact Min-Width Bar",
            subtitle="Shrink bar to only wrap its active widgets instead of spanning full screen width",
            control=self._bar_minwidth_switch,
            control_min_width=None,
        )

        current_floating = self._get_current_bar_cfg().get("floating_bar", False)
        self._bar_floating_switch = SmoothSwitch(
            style_classes=["dash-switch"],
            v_expand=True,
            v_align="center",
            on_user_toggle=self._on_bar_floating_toggled,
            width=48,
        )
        self._bar_floating_switch.set_active(current_floating)

        floating_row = create_setting_row(
            title="Floating Bar",
            subtitle="Detach the bar from screen borders with rounded margins and shadows",
            control=self._bar_floating_switch,
            control_min_width=None,
        )

        current_autohide = self._get_current_bar_cfg().get("auto_hide", False)
        self._bar_autohide_switch = SmoothSwitch(
            style_classes=["dash-switch"],
            v_expand=True,
            v_align="center",
            on_user_toggle=self._on_bar_autohide_toggled,
            width=48,
        )
        self._bar_autohide_switch.set_active(current_autohide)

        autohide_row = create_setting_row(
            title="Smart Auto-Hide (Intellihide)",
            subtitle="Keep the bar visible when screen is empty; auto-hide when active windows overlap",
            control=self._bar_autohide_switch,
            control_min_width=None,
        )

        dock_card = create_settings_card(
            title="Dock Styling & Auto-Hide",
            description="Customize bar geometry, borders, and auto-hide behaviors",
            rows=[minwidth_row, floating_row, autohide_row],
        )

        page_box = Box(
            orientation="v",
            spacing=16,
            h_align="fill",
            h_expand=True,
            style="padding: 6px 12px 24px 4px;",
            children=[header, placement_card, dock_card],
        )
        return page_box

    def _build_page_dash(self) -> Box:
        header = create_page_header(
            title="Dash Appearance & Wallpaper Effects",
            description="Tune Dash overlay visuals, card tile translucency, and wallpaper transition effects",
            icon_name="sparkle-duotone",
        )

        self._blur_switch = SmoothSwitch(
            style_classes=["dash-switch"],
            v_expand=True,
            v_align="center",
            on_user_toggle=self._on_dash_blur_toggled,
            width=48,
        )
        self._blur_switch.set_active(getattr(user_options.settings, "dash_blur", True))

        blur_row = create_setting_row(
            title="Dash Background Blur",
            subtitle="Enable or disable backdrop blur when Dash is open",
            control=self._blur_switch,
            control_min_width=None,
        )

        current_dim = getattr(user_options.settings, "dash_dim_opacity", 0.6)
        self._dim_badge = Label(label=f"{round(current_dim * 100)}%", style="font-size: 11px; font-weight: 600;")
        self._dim_slider = FlatScale(
            size=(170, 24),
            style_classes=["scale"],
            min_value=0.0,
            max_value=1.0,
            step=0.05,
            value=current_dim,
            value_formatter=lambda val: f"{round(val * 100)}%",
            h_expand=True,
        )
        self._dim_slider.connect("value-changed", self._on_dim_changed)

        dim_row = create_slider_row(
            title="Dash Backdrop Dim Opacity",
            subtitle="Adjust background darkness/transparency when Dash is opened",
            slider=self._dim_slider,
            value_badge=self._dim_badge,
            control_min_width=240,
        )

        current_card_opacity = getattr(user_options.settings, "dash_card_opacity", 1.0)
        self._card_opacity_badge = Label(label=f"{round(current_card_opacity * 100)}%", style="font-size: 11px; font-weight: 600;")
        self._card_opacity_slider = FlatScale(
            size=(170, 24),
            style_classes=["scale"],
            min_value=0.0,
            max_value=1.0,
            step=0.05,
            value=current_card_opacity,
            value_formatter=lambda val: f"{round(val * 100)}%",
            h_expand=True,
        )
        self._card_opacity_slider.connect("value-changed", self._on_card_opacity_changed)

        card_opacity_row = create_slider_row(
            title="Dash App Tiles Opacity",
            subtitle="Adjust background tile transparency for application launcher cards",
            slider=self._card_opacity_slider,
            value_badge=self._card_opacity_badge,
            control_min_width=240,
        )

        self._instant_switch = SmoothSwitch(
            style_classes=["dash-switch"],
            v_expand=True,
            v_align="center",
            on_user_toggle=self._on_instant_toggled,
            width=48,
        )
        self._instant_switch.set_active(getattr(user_options.settings, "instant_dash", True))

        instant_row = create_setting_row(
            title="Ultra-Fast Instant Dash Opening",
            subtitle="Zero-latency instant display when pressing Super or clicking Dash button",
            control=self._instant_switch,
            control_min_width=None,
        )

        dash_card = create_settings_card(
            title="Dash Overlay & Performance",
            description="Customize Dash backdrop effect, darkening, and launcher tile translucency",
            rows=[blur_row, dim_row, card_opacity_row, instant_row],
        )

        # Wallpaper Transition row
        trans_options = [
            ("grow", "Grow"),
            ("fade", "Fade"),
            ("wipe", "Wipe"),
            ("wave", "Wave"),
            ("left", "Slide L"),
            ("right", "Slide R"),
            ("top", "Slide Up"),
            ("bottom", "Slide Down"),
            ("outer", "Shrink"),
            ("random", "Random"),
        ]
        cur_trans = getattr(user_options.wallpaper, "transition_type", "grow")

        trans_title_col = Box(
            orientation="v",
            spacing=2,
            h_align="start",
            h_expand=True,
            children=[
                Label(label="Wallpaper Transition Effect", style_classes=["dim-label"], style="font-size: 12.5px; font-weight: 600;", h_align="start"),
                Label(label="Animation effect used when switching desktop wallpapers", style="font-size: 11px; opacity: 0.6;", h_align="start", line_wrap="word-char"),
            ],
        )

        trans_flow = Gtk.FlowBox()
        trans_flow.set_valign(Gtk.Align.START)
        trans_flow.set_max_children_per_line(5)
        trans_flow.set_selection_mode(Gtk.SelectionMode.NONE)
        trans_flow.set_column_spacing(6)
        trans_flow.set_row_spacing(6)
        trans_flow.set_homogeneous(True)

        for t_key, t_name in trans_options:
            b = Button(
                child=Label(label=t_name, style="font-size: 11px; font-weight: 500;"),
                style_classes=["option-selection-button"] + (["active"] if t_key == cur_trans else []),
                on_clicked=lambda _, k=t_key: self._on_wallpaper_transition_changed(k),
            )
            self._setting_trans_buttons[t_key] = b
            trans_flow.add(b)

        wallpaper_trans_row = Box(
            orientation="v",
            spacing=10,
            h_align="fill",
            style_classes=["dash-settings-row"],
            children=[trans_title_col, trans_flow],
        )

        # Random Animation Pool multi-select chips
        pool_options = [
            ("grow", "Grow"),
            ("fade", "Fade"),
            ("wipe", "Wipe"),
            ("wave", "Wave"),
            ("left", "Slide L"),
            ("right", "Slide R"),
            ("top", "Slide Up"),
            ("bottom", "Slide Down"),
            ("outer", "Shrink"),
        ]
        enabled_pool = set(getattr(user_options.wallpaper, "enabled_transitions", ["grow", "fade", "wipe", "wave", "left", "right", "top", "bottom", "outer"]))

        pool_title_col = Box(
            orientation="v",
            spacing=2,
            h_align="start",
            h_expand=True,
            children=[
                Label(label="Random Animation Pool", style_classes=["dim-label"], style="font-size: 12.5px; font-weight: 600;", h_align="start"),
                Label(label="Toggle animations used by the system during random wallpaper switches", style="font-size: 11px; opacity: 0.6;", h_align="start", line_wrap="word-char"),
            ],
        )

        pool_flow = Gtk.FlowBox()
        pool_flow.set_valign(Gtk.Align.START)
        pool_flow.set_max_children_per_line(5)
        pool_flow.set_selection_mode(Gtk.SelectionMode.NONE)
        pool_flow.set_column_spacing(6)
        pool_flow.set_row_spacing(6)
        pool_flow.set_homogeneous(True)

        for p_key, p_name in pool_options:
            is_on = p_key in enabled_pool
            b = Button(
                child=Label(label=f"✓ {p_name}" if is_on else f"✗ {p_name}", style="font-size: 11px; font-weight: 500;"),
                style_classes=["option-selection-button"] + (["active"] if is_on else []),
                on_clicked=lambda _, k=p_key, n=p_name: self._on_wallpaper_pool_toggled(k, n),
            )
            self._pool_chips[p_key] = b
            pool_flow.add(b)

        wallpaper_pool_row = Box(
            orientation="v",
            spacing=10,
            h_align="fill",
            style_classes=["dash-settings-row"],
            children=[pool_title_col, pool_flow],
        )

        wallpaper_card = create_settings_card(
            title="Wallpaper Transitions & Effects",
            description="Configure animations and the random transition pool for desktop wallpapers",
            rows=[wallpaper_trans_row, wallpaper_pool_row],
        )

        page_box = Box(
            orientation="v",
            spacing=16,
            h_align="fill",
            h_expand=True,
            style="padding: 6px 12px 24px 4px;",
            children=[header, dash_card, wallpaper_card],
        )
        return page_box

    def _get_current_bar_cfg(self) -> dict:
        if not user_options.bars.configs or not user_options.bars.configs[0].get("bars"):
            return {}
        bars = user_options.bars.configs[0]["bars"]
        if self._selected_bar_index >= len(bars):
            self._selected_bar_index = max(0, len(bars) - 1)
        return bars[self._selected_bar_index]

    def _refresh_bar_selector_ui(self):
        for child in self._bar_selector_container.get_children():
            self._bar_selector_container.remove(child)

        bars = user_options.bars.configs[0].get("bars", []) if user_options.bars.configs else []
        
        pills_box = Box(orientation="h", spacing=6, h_align="start")

        for idx, b_cfg in enumerate(bars):
            align = b_cfg.get("alignment", "bottom").capitalize()
            h_align = b_cfg.get("horizontal_alignment", "center").capitalize()
            is_active = (idx == self._selected_bar_index)
            btn = Button(
                child=Box(
                    orientation="h",
                    spacing=6,
                    children=[
                        Icon(icon_name="bar-duotone" if is_active else "app-window-duotone", icon_size=14),
                        Label(label=f"Bar {idx + 1} ({align} {h_align})", style="font-size: 12px; font-weight: 500;"),
                    ],
                ),
                style_classes=["option-selection-button"] + (["active"] if is_active else []),
                on_clicked=lambda _b, i=idx: self._select_bar(i),
            )
            pills_box.add(btn)

        self._bar_selector_container.add(pills_box)

        # Action buttons: Add Bar (if < 6) & Delete Bar (if > 1)
        actions_box = Box(orientation="h", spacing=6, h_align="end", h_expand=True)

        if len(bars) < 6:
            add_bar_btn = Button(
                child=Box(
                    orientation="h",
                    spacing=4,
                    children=[Icon(icon_name="plus-circle-duotone", icon_size=14), Label(label="Add Bar", style="font-size: 11px; font-weight: 500;")],
                ),
                style_classes=["bar-chip-add-btn"],
                on_clicked=lambda *_: self._add_new_bar(),
            )
            actions_box.add(add_bar_btn)

        if len(bars) > 1:
            delete_bar_btn = Button(
                child=Box(
                    orientation="h",
                    spacing=4,
                    children=[Icon(icon_name="trash-duotone", icon_size=14), Label(label="Delete Bar", style="font-size: 11px; font-weight: 500;")],
                ),
                style_classes=["bar-chip-remove-btn"],
                on_clicked=lambda *_: self._delete_selected_bar(),
            )
            actions_box.add(delete_bar_btn)

        self._bar_selector_container.add(actions_box)
        self._bar_selector_container.show_all()

    def _select_bar(self, index: int):
        self._selected_bar_index = index
        self._refresh_bar_selector_ui()
        self._refresh_bar_widgets_ui()
        cur_align = self._get_current_bar_alignment()
        self._update_position_buttons(cur_align)
        cur_h_align = self._get_current_bar_h_align()
        self._update_h_align_buttons(cur_h_align)
        cfg = self._get_current_bar_cfg()
        if hasattr(self, "_bar_minwidth_switch"):
            self._bar_minwidth_switch.set_active(cfg.get("min_width", False))
        if hasattr(self, "_bar_floating_switch"):
            self._bar_floating_switch.set_active(cfg.get("floating_bar", False))
        if hasattr(self, "_bar_autohide_switch"):
            self._bar_autohide_switch.set_active(cfg.get("auto_hide", False))

    def _add_new_bar(self):
        bm = self._bar_manager or singletons.bar_manager
        if bm:
            display = Gdk.Display.get_default()
            mon = display.get_monitor(0)
            bm.add_bar_for_monitor(mon)
            bars = user_options.bars.configs[0].get("bars", [])
            self._selected_bar_index = max(0, len(bars) - 1)
            self._refresh_bar_selector_ui()
            self._refresh_bar_widgets_ui()
            self._update_position_buttons(self._get_current_bar_alignment())
            self._update_h_align_buttons(self._get_current_bar_h_align())
            cfg = self._get_current_bar_cfg()
            if hasattr(self, "_bar_minwidth_switch"):
                self._bar_minwidth_switch.set_active(cfg.get("min_width", False))
            if hasattr(self, "_bar_floating_switch"):
                self._bar_floating_switch.set_active(cfg.get("floating_bar", False))
            if hasattr(self, "_bar_autohide_switch"):
                self._bar_autohide_switch.set_active(cfg.get("auto_hide", False))

    def _delete_selected_bar(self):
        if not user_options.bars.configs or not user_options.bars.configs[0].get("bars"):
            return
        bars = user_options.bars.configs[0]["bars"]
        if len(bars) <= 1:
            return
        if self._selected_bar_index < len(bars):
            bars.pop(self._selected_bar_index)
            user_options.save()
            self._selected_bar_index = 0
            bm = self._bar_manager or singletons.bar_manager
            if bm and hasattr(bm, "reload_bars"):
                bm.reload_bars()
            self._refresh_bar_selector_ui()
            self._refresh_bar_widgets_ui()
            self._update_position_buttons(self._get_current_bar_alignment())
            self._update_h_align_buttons(self._get_current_bar_h_align())
            cfg = self._get_current_bar_cfg()
            if hasattr(self, "_bar_minwidth_switch"):
                self._bar_minwidth_switch.set_active(cfg.get("min_width", False))
            if hasattr(self, "_bar_floating_switch"):
                self._bar_floating_switch.set_active(cfg.get("floating_bar", False))
            if hasattr(self, "_bar_autohide_switch"):
                self._bar_autohide_switch.set_active(cfg.get("auto_hide", False))

    def _refresh_bar_widgets_ui(self):
        cfg = self._get_current_bar_cfg()

        for sec in ("left", "center", "right"):
            box = self._section_boxes.get(sec)
            if not box:
                continue
            for child in box.get_children():
                box.remove(child)

            entries = cfg.get(sec, [])
            if not entries:
                box.add(Label(label="No widgets placed", style="font-size: 12px; opacity: 0.5;"))
            else:
                for entry in entries:
                    chip = BarWidgetChip(sec, entry, on_remove=self._remove_widget_from_bar)
                    box.add(chip)
            box.show_all()

    def _remove_widget_from_bar(self, section_name: str, widget_entry: str | dict):
        bar_cfg = self._get_current_bar_cfg()
        if not bar_cfg:
            return

        entries = bar_cfg.get(section_name, [])

        if widget_entry in entries:
            entries.remove(widget_entry)
            user_options.save()

            bm = self._bar_manager or singletons.bar_manager
            if bm and hasattr(bm, "reload_bars"):
                bm.reload_bars()

            self._refresh_bar_widgets_ui()

    def _show_add_widget_menu(self, widget: Gtk.Widget, section_name: str):
        menu = Gtk.Menu()
        menu.set_reserve_toggle_size(False)

        categories = {
            "System & Controls": ["SysMon", "Processes", "Volume", "Brightness", "Energy", "Wifi", "Bluetooth", "NightLight", "Caffeine"],
            "Navigation & Apps": ["Dash", "Launcher", "Workspaces", "Dock", "Focused"],
            "Tools & Utilities": ["Clock", "Calendar", "Weather", "Media", "Notifications", "Clipboard", "Calculator", "Keyboard", "Screenshot", "Settings", "Tray", "Session"],
        }

        for cat_name, w_list in categories.items():
            cat_item = Gtk.MenuItem(label=cat_name)
            sub = Gtk.Menu()
            sub.set_reserve_toggle_size(False)
            for w_name in w_list:
                item = Gtk.MenuItem()
                box = Box(orientation="h", spacing=8)
                icon = Icon(icon_name=WIDGET_ICONS.get(w_name, "app-window-duotone"), icon_size=16)
                lbl = Label(label=w_name)
                box.add(icon)
                box.add(lbl)
                item.add(box)
                item.connect("activate", lambda _, name=w_name, s=section_name: self._add_widget_to_bar(s, name))
                sub.append(item)
            cat_item.set_submenu(sub)
            menu.append(cat_item)

        sep = Gtk.SeparatorMenuItem()
        menu.append(sep)

        # All widgets submenu
        all_item = Gtk.MenuItem(label="All Widgets")
        all_sub = Gtk.Menu()
        all_sub.set_reserve_toggle_size(False)
        for w_name in ALL_AVAILABLE_WIDGETS:
            item = Gtk.MenuItem()
            box = Box(orientation="h", spacing=8)
            icon = Icon(icon_name=WIDGET_ICONS.get(w_name, "app-window-duotone"), icon_size=16)
            lbl = Label(label=w_name)
            box.add(icon)
            box.add(lbl)
            item.add(box)
            item.connect("activate", lambda _, name=w_name, s=section_name: self._add_widget_to_bar(s, name))
            all_sub.append(item)
        all_item.set_submenu(all_sub)
        menu.append(all_item)

        menu.show_all()
        try:
            menu.popup_at_widget(widget, Gdk.Gravity.SOUTH, Gdk.Gravity.NORTH, None)
        except Exception:
            menu.popup(None, None, None, None, 0, Gtk.get_current_event_time())

    def _on_hover_widget_toggled(self, widget_name: str, active: bool):
        current = list(getattr(user_options.settings, "hover_widgets", ALL_AVAILABLE_WIDGETS))
        if active and widget_name not in current:
            current.append(widget_name)
        elif not active and widget_name in current:
            current.remove(widget_name)
        user_options.settings.hover_widgets = current
        user_options.save()

    def _set_all_hover_widgets(self, enable_all: bool):
        if enable_all:
            user_options.settings.hover_widgets = list(ALL_AVAILABLE_WIDGETS)
        else:
            user_options.settings.hover_widgets = []
        user_options.save()

        for w_name, chip in self._hover_chip_widgets.items():
            chip.set_active_state(enable_all)

    def _add_widget_to_bar(self, section_name: str, widget_name: str):
        bar_cfg = self._get_current_bar_cfg()
        if not bar_cfg:
            return

        if section_name not in bar_cfg:
            bar_cfg[section_name] = []

        bar_cfg[section_name].append(widget_name)
        user_options.save()

        bm = self._bar_manager or singletons.bar_manager
        if bm and hasattr(bm, "reload_bars"):
            bm.reload_bars()

        self._refresh_bar_widgets_ui()

    def _get_current_bar_alignment(self) -> str:
        cfg = self._get_current_bar_cfg()
        return cfg.get("alignment", "bottom") if cfg else "bottom"

    def _get_current_bar_h_align(self) -> str:
        cfg = self._get_current_bar_cfg()
        return cfg.get("horizontal_alignment", "center") if cfg else "center"

    def _update_position_buttons(self, alignment: str):
        if not hasattr(self, "_top_btn") or not hasattr(self, "_bottom_btn"):
            return
        if alignment == "top":
            self._top_btn.add_style_class("active")
            self._bottom_btn.remove_style_class("active")
        else:
            self._bottom_btn.add_style_class("active")
            self._top_btn.remove_style_class("active")

    def _update_h_align_buttons(self, h_align: str):
        if not hasattr(self, "_left_align_btn") or not hasattr(self, "_center_align_btn") or not hasattr(self, "_right_align_btn"):
            return
        self._left_align_btn.remove_style_class("active")
        self._center_align_btn.remove_style_class("active")
        self._right_align_btn.remove_style_class("active")
        if h_align == "left":
            self._left_align_btn.add_style_class("active")
        elif h_align == "right":
            self._right_align_btn.add_style_class("active")
        else:
            self._center_align_btn.add_style_class("active")

    def _set_position(self, alignment: str):
        cfg = self._get_current_bar_cfg()
        if not cfg:
            return
        cfg["alignment"] = alignment
        user_options.save()
        self._update_position_buttons(alignment)
        bm = self._bar_manager or singletons.bar_manager
        if bm and hasattr(bm, "reload_bars"):
            bm.reload_bars()
        self._refresh_bar_selector_ui()

    def _set_horizontal_alignment(self, h_align: str):
        cfg = self._get_current_bar_cfg()
        if not cfg:
            return
        cfg["horizontal_alignment"] = h_align
        if h_align in ("left", "right") and not cfg.get("min_width", False):
            cfg["min_width"] = True
            if hasattr(self, "_bar_minwidth_switch"):
                self._bar_minwidth_switch.set_active(True)
        user_options.save()
        self._update_h_align_buttons(h_align)
        bm = self._bar_manager or singletons.bar_manager
        if bm and hasattr(bm, "reload_bars"):
            bm.reload_bars()
        self._refresh_bar_selector_ui()

    def _on_bar_minwidth_toggled(self, state: bool):
        cfg = self._get_current_bar_cfg()
        if not cfg:
            return
        cfg["min_width"] = state
        user_options.save()
        bm = self._bar_manager or singletons.bar_manager
        if bm and hasattr(bm, "reload_bars"):
            bm.reload_bars()

    def _on_bar_floating_toggled(self, state: bool):
        cfg = self._get_current_bar_cfg()
        if not cfg:
            return
        cfg["floating_bar"] = state
        user_options.save()
        bm = self._bar_manager or singletons.bar_manager
        if bm and hasattr(bm, "reload_bars"):
            bm.reload_bars()

    def _on_bar_autohide_toggled(self, state: bool):
        cfg = self._get_current_bar_cfg()
        if not cfg:
            return
        cfg["auto_hide"] = state
        user_options.save()
        bm = self._bar_manager or singletons.bar_manager
        if bm and hasattr(bm, "reload_bars"):
            bm.reload_bars()

    def _on_hover_toggled(self, state: bool):
        user_options.settings.hover_open = state
        user_options.save()

    def _on_delay_changed(self, _scale, val: float):
        int_val = int(val)
        if hasattr(self, "_delay_badge"):
            self._delay_badge.set_label(f"{int_val}ms")
        user_options.settings.hover_delay = int_val
        user_options.save()

    def _on_bar_theme_selected(self, theme_id: str):
        preset = next((p for p in BAR_THEME_PRESETS if p["id"] == theme_id), None)
        if not preset:
            return

        user_options.settings.bar_theme = theme_id
        user_options.settings.bar_opacity = preset["bar_opacity"]
        user_options.settings.widget_opacity = preset["widget_opacity"]
        user_options.settings.bar_blur = preset["blur"]
        user_options.save()

        for tid, card in getattr(self, "_bar_theme_cards", {}).items():
            card.set_active_state(tid == theme_id)

        if hasattr(self, "_bar_opacity_slider"):
            self._bar_opacity_slider.set_value(preset["bar_opacity"])
        if hasattr(self, "_bar_opacity_badge"):
            self._bar_opacity_badge.set_label(f"{round(preset['bar_opacity'] * 100)}%")
        if hasattr(self, "_widget_opacity_slider"):
            self._widget_opacity_slider.set_value(preset["widget_opacity"])
        if hasattr(self, "_widget_opacity_badge"):
            self._widget_opacity_badge.set_label(f"{round(preset['widget_opacity'] * 100)}%")
        if hasattr(self, "_bar_blur_switch"):
            self._bar_blur_switch.set_active(preset["blur"])

        bm = self._bar_manager or singletons.bar_manager
        if bm:
            if hasattr(bm, "apply_bar_theme"):
                bm.apply_bar_theme(theme_id)
            if hasattr(bm, "apply_bar_opacity"):
                bm.apply_bar_opacity(preset["bar_opacity"])
            if hasattr(bm, "apply_widget_opacity"):
                bm.apply_widget_opacity(preset["widget_opacity"])
            if hasattr(bm, "apply_blur"):
                bm.apply_blur(preset["blur"])

    def _on_bar_blur_toggled(self, state: bool):
        user_options.settings.bar_blur = state
        user_options.save()
        bm = self._bar_manager or singletons.bar_manager
        if bm and hasattr(bm, "apply_blur"):
            bm.apply_blur(state)

    def _on_bar_opacity_changed(self, _scale, val: float):
        opacity = max(0.0, min(1.0, float(val)))
        if hasattr(self, "_bar_opacity_badge"):
            self._bar_opacity_badge.set_label(f"{round(opacity * 100)}%")
        user_options.settings.bar_opacity = opacity
        user_options.save()

        bm = self._bar_manager or singletons.bar_manager
        if bm and hasattr(bm, "apply_bar_opacity"):
            bm.apply_bar_opacity(opacity)

    def _on_widget_opacity_changed(self, _scale, val: float):
        opacity = max(0.0, min(1.0, float(val)))
        if hasattr(self, "_widget_opacity_badge"):
            self._widget_opacity_badge.set_label(f"{round(opacity * 100)}%")
        user_options.settings.widget_opacity = opacity
        user_options.save()

        bm = self._bar_manager or singletons.bar_manager
        if bm and hasattr(bm, "apply_widget_opacity"):
            bm.apply_widget_opacity(opacity)

    def _on_desktop_opacity_changed(self, _scale, val: float):
        opacity = max(0.0, min(1.0, float(val)))
        if hasattr(self, "_desktop_opacity_badge"):
            self._desktop_opacity_badge.set_label(f"{round(opacity * 100)}%")
        user_options.settings.desktop_widget_opacity = opacity
        user_options.save()

        from services.desktop_applets import DesktopAppletService
        das = DesktopAppletService.get_instance()
        if hasattr(das, "apply_desktop_widget_opacity"):
            das.apply_desktop_widget_opacity(opacity)

    def _on_dash_blur_toggled(self, state: bool):
        user_options.settings.dash_blur = state
        user_options.save()

    def _on_dim_changed(self, _scale, val: float):
        opacity = max(0.0, min(1.0, float(val)))
        if hasattr(self, "_dim_badge"):
            self._dim_badge.set_label(f"{round(opacity * 100)}%")
        user_options.settings.dash_dim_opacity = opacity
        user_options.save()

        bm = self._bar_manager or singletons.bar_manager
        if bm and getattr(bm, "_dash", None) and hasattr(bm._dash, "dismiss_layer"):
            bm._dash.dismiss_layer.set_dim_opacity(opacity)

    def _on_card_opacity_changed(self, _scale, val: float):
        opacity = max(0.0, min(1.0, float(val)))
        if hasattr(self, "_card_opacity_badge"):
            self._card_opacity_badge.set_label(f"{round(opacity * 100)}%")
        user_options.settings.dash_card_opacity = opacity
        user_options.save()

        bm = self._bar_manager or singletons.bar_manager
        if bm and getattr(bm, "_dash", None) and hasattr(bm._dash, "launcher"):
            bm._dash.launcher.set_card_opacity(opacity)

    def _on_instant_toggled(self, state: bool):
        user_options.settings.instant_dash = state
        user_options.save()

    def _on_wallpaper_transition_changed(self, transition_type: str):
        user_options.wallpaper.transition_type = transition_type
        user_options.save()
        for k, btn in getattr(self, "_setting_trans_buttons", {}).items():
            if k == transition_type:
                btn.add_style_class("active")
            else:
                btn.remove_style_class("active")

    def _on_wallpaper_pool_toggled(self, pool_key: str, pool_name: str):
        pool = list(getattr(user_options.wallpaper, "enabled_transitions", []))
        if pool_key in pool:
            pool.remove(pool_key)
            is_on = False
        else:
            pool.append(pool_key)
            is_on = True
        if not pool:
            pool = ["grow"]
            is_on = True
        user_options.wallpaper.enabled_transitions = pool
        user_options.save()

        btn = getattr(self, "_pool_chips", {}).get(pool_key)
        if btn:
            child = btn.get_child()
            if child and hasattr(child, "set_label"):
                child.set_label(f"✓ {pool_name}" if is_on else f"✗ {pool_name}")
            if is_on:
                btn.add_style_class("active")
            else:
                btn.remove_style_class("active")
