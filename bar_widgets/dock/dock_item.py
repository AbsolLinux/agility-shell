from __future__ import annotations
from typing import Callable

import cairo
from loguru import logger
from gi.repository import Gtk, Gdk, Gio, GLib

from fabric.widgets.eventbox import EventBox
from fabric.widgets.box import Box
from fabric.widgets.image import Image

from services.singletons import edit_mode
from user_options import user_options
from utils.helpers import get_app_icon_name, popup_with_blur

DOCK_DRAG_TARGET = "dock-item"
DOCK_DRAG_INFO = 0


def create_surface_from_widget(widget: Gtk.Widget) -> cairo.ImageSurface:
    alloc = widget.get_allocation()
    surface = cairo.ImageSurface(cairo.Format.ARGB32, alloc.width, alloc.height)
    cr = cairo.Context(surface)
    cr.set_source_rgba(0, 0, 0, 0)
    cr.rectangle(0, 0, alloc.width, alloc.height)
    cr.fill()
    widget.draw(cr)
    return surface


class DockItem(EventBox):

    def __init__(
        self,
        app_id: str,
        pinned: bool,
        running: bool,
        window,
        workspace_id: int,
        wm_service,          # renamed from niri_service
        dock_state,
        on_reorder: Callable[[str, str, bool], None],
        on_workspace_move: Callable[[str, int], None],
        on_pin_toggle: Callable[[str, int], None],
        **kwargs,
    ):
        self.app_id = app_id
        self.pinned = pinned
        self.running = running
        self.window = window
        self.workspace_id = workspace_id
        self._wm = wm_service
        self._dock_state = dock_state
        self._on_reorder = on_reorder
        self._on_workspace_move = on_workspace_move
        self._on_pin_toggle = on_pin_toggle
        self._launching = False
        self._drag_started = False

        style = ["dock-item"]
        if pinned and not running:
            style.append("inactive")
        if running:
            style.append("running")
        if running and window is not None and window.is_focused:
            style.append("focused")

        self._icon = Image(
            css_classes=["icon"],
            icon_name=self._resolve_icon(),
            icon_size=24,
        )
        self._icon_container = Box(style_classes=style, children=[self._icon])
        super().__init__(
            child=self._icon_container,
            **kwargs,
        )

        self.connect("button-release-event", self._on_button_release)
        self.connect("enter-notify-event", lambda w, _: self._icon_container.add_style_class("hovered"))
        self.connect("leave-notify-event", self._on_leave)
        self.connect("button-press-event", lambda w, e: self._icon_container.add_style_class("active") if e.button == 1 and not edit_mode.edit_mode else None)

    def _on_leave(self, w, event):
        if event.detail != Gdk.NotifyType.INFERIOR:
            self._icon_container.remove_style_class("hovered")

    def _resolve_icon(self) -> str:
        return (
            get_app_icon_name(self.app_id)
            or get_app_icon_name(self.app_id.lower())
            or "application-x-executable-symbolic"
        )

    def _do_focus(self) -> bool:
        if self.window is not None:
            self.window.focus()
        return False

    def _on_button_release(self, _, event: Gdk.EventButton):
        self._icon_container.remove_style_class("active")
        if self._drag_started:
            self._drag_started = False
            return True
        if event.button == 1:
            if self.running and self.window is not None:
                self._wm.switch_to_workspace_by_id(self.window.workspace_id)
                GLib.timeout_add(50, self._do_focus)
            else:
                self._launch_fresh()
            return True
        if event.button == 3:
            self._show_context_menu(event)
            return True
        return False

    def _launch_fresh(self) -> None:
        if self._launching:
            return
        app_info = self._find_app_info()
        if not app_info:
            logger.warning(f"[DockItem] No app info found for {self.app_id!r}")
            return
        self._launching = True
        GLib.timeout_add(100, self._do_launch, app_info)

    def _launch_on_workspace(self, workspace_id: int) -> None:
        if self._launching:
            return
        app_info = self._find_app_info()
        if not app_info:
            logger.warning(f"[DockItem] No app info found for {self.app_id!r}")
            return
        self._launching = True
        self._wm.switch_to_workspace_by_id(workspace_id)
        GLib.timeout_add(100, self._do_launch, app_info)

    def _do_launch(self, app_info: Gio.AppInfo) -> bool:
        try:
            app_info.launch([], None)
        except Exception as e:
            logger.error(f"[DockItem] Launch failed for {self.app_id!r}: {e}")
        self._launching = False
        return False

    def _find_app_info(self) -> Gio.AppInfo | None:
        needle = self.app_id.lower()
        all_apps = Gio.AppInfo.get_all()

        for app in all_apps:
            aid = (app.get_id() or "").lower().removesuffix(".desktop")
            if aid == needle:
                return app
        for app in all_apps:
            if hasattr(app, "get_string"):
                wm_class = (app.get_string("StartupWMClass") or "").lower()
                if wm_class == needle:
                    return app
        for app in all_apps:
            aid = (app.get_id() or "").lower()
            if needle in aid:
                return app
        return None

    def _show_context_menu(self, event: Gdk.EventButton) -> None:
        menu = Gtk.Menu()

        app_info = self._find_app_info()
        if app_info and hasattr(app_info, "list_actions"):
            actions = app_info.list_actions()
            for action in actions:
                label = app_info.get_action_name(action)
                item = Gtk.MenuItem(label=label)
                item.connect("activate", lambda _, a=action: app_info.launch_action(a, None))
                menu.append(item)
            if actions:
                menu.append(Gtk.SeparatorMenuItem())

        is_pinned = self._dock_state.is_pinned(self.app_id) if self._dock_state else self.pinned
        pin_label = "Unpin from dock" if is_pinned else "Pin to dock"
        pin_item = Gtk.MenuItem(label=pin_label)
        pin_item.connect("activate", lambda *_: self._do_pin_toggle())
        menu.append(pin_item)

        if user_options.theme.blur:
            popup_with_blur(menu, event)
        else:
            menu.show_all()
            menu.popup_at_pointer(event)

    def _do_pin_toggle(self) -> None:
        self._on_pin_toggle(self.app_id)

    def _setup_drag(self) -> None:
        target_entry = Gtk.TargetEntry.new(DOCK_DRAG_TARGET, Gtk.TargetFlags.SAME_APP, DOCK_DRAG_INFO)
        self.drag_source_set(Gdk.ModifierType.BUTTON1_MASK, [target_entry], Gdk.DragAction.MOVE)
        self.connect("drag-begin", self._on_drag_begin)
        self.connect("drag-data-get", self._on_drag_data_get)
        self.connect("drag-end", self._on_drag_end)

    def _on_drag_begin(self, widget: Gtk.Widget, context: Gdk.DragContext) -> None:
        self._drag_started = True
        surface = create_surface_from_widget(widget)
        Gtk.drag_set_icon_surface(context, surface)

    def _on_drag_end(self, *_) -> None:
        self._drag_started = False

    def _on_drag_data_get(self, _, __, data: Gtk.SelectionData, *___) -> None:
        data.set_text(self.app_id, -1)