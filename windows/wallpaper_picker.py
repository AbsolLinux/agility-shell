import os
from fabric.widgets.wayland import WaylandWindow as Window
from fabric.widgets.box import Box
from fabric.widgets.label import Label
from fabric.widgets.button import Button
from fabric.widgets.image import Image
from fabric.widgets.eventbox import EventBox
from fabric.widgets.scrolledwindow import ScrolledWindow
from gi.repository import Gtk, Gdk, GdkPixbuf, GLib, GtkLayerShell
from snippets import Icon
from services.wallpaper import WallpaperService
from loguru import logger

class WallpaperThumbnail(EventBox):
    def __init__(self, path: str, on_select, is_active: bool = False):
        self.path = path
        self.on_select = on_select

        self._image = Image(style_classes=["wallpaper-picker-thumb-img"])
        self._load_thumbnail()

        self.box = Box(
            style_classes=["wallpaper-picker-thumb"] + (["active"] if is_active else []),
            children=[self._image],
        )

        super().__init__(
            child=self.box,
            style_classes=["wallpaper-picker-thumb-wrapper"],
        )
        self.connect("button-release-event", self._on_click)

    def _load_thumbnail(self):
        try:
            pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_scale(self.path, 120, 75, False)
            self._image.set_from_pixbuf(pixbuf)
        except Exception as e:
            logger.debug(f"[WallpaperPicker] thumb load error {self.path}: {e}")

    def _on_click(self, widget, event):
        if event.button == 1:
            self.on_select(self.path)
            return True
        return False

    def set_active(self, active: bool):
        if active:
            self.box.add_style_class("active")
        else:
            self.box.remove_style_class("active")


class WallpaperPicker(Window):
    def __init__(self, **kwargs):
        self._service = WallpaperService.get_instance()
        self._wallpapers: list[str] = []
        self._current_index: int = 0
        self._thumb_widgets: dict[str, WallpaperThumbnail] = {}

        # Dismiss background
        self._backdrop = EventBox(
            style_classes=["wallpaper-picker-backdrop"],
            h_expand=True,
            v_expand=True,
        )
        self._backdrop.connect("button-release-event", lambda w, e: self.close() if e.button == 1 else False)

        # Header
        self._title_label = Label(
            label="Wallpaper Gallery",
            style="font-size: 20px; font-weight: 700;",
            h_align="start",
        )
        self._count_label = Label(
            label="0 of 0",
            style="font-size: 13px; opacity: 0.6;",
            h_align="start",
        )
        header_text = Box(
            orientation="v",
            spacing=2,
            children=[self._title_label, self._count_label],
        )

        self._random_btn = Button(
            child=Box(
                orientation="h",
                spacing=6,
                children=[
                    Icon(icon_name="shuffle-duotone", icon_size=16),
                    Label(label="Random (Alt+X)"),
                ],
            ),
            style_classes=["wallpaper-picker-btn"],
            on_clicked=lambda *_: self._shuffle_random(),
        )

        self._apply_btn = Button(
            child=Box(
                orientation="h",
                spacing=6,
                children=[
                    Icon(icon_name="check-duotone", icon_size=16),
                    Label(label="Apply (Enter)"),
                ],
            ),
            style_classes=["wallpaper-picker-btn", "apply-btn"],
            on_clicked=lambda *_: self._apply_and_close(),
        )

        self._close_btn = Button(
            child=Icon(icon_name="x", icon_size=18),
            style_classes=["wallpaper-picker-btn", "close-btn"],
            on_clicked=lambda *_: self.close(),
        )

        header_bar = Box(
            orientation="h",
            spacing=12,
            children=[
                header_text,
                Box(h_expand=True),
                self._random_btn,
                self._apply_btn,
                self._close_btn,
            ],
        )

        # Main Large Preview
        self._preview_image = Image(style_classes=["wallpaper-picker-preview-img"])
        self._preview_name_label = Label(
            label="",
            style="font-size: 14px; font-weight: 600;",
            h_align="center",
        )

        self._prev_btn = Button(
            child=Icon(icon_name="caret-left-duotone", icon_size=28),
            style_classes=["wallpaper-picker-nav-btn"],
            on_clicked=lambda *_: self._prev_wallpaper(),
        )

        self._next_btn = Button(
            child=Icon(icon_name="caret-right-duotone", icon_size=28),
            style_classes=["wallpaper-picker-nav-btn"],
            on_clicked=lambda *_: self._next_wallpaper(),
        )

        preview_card = Box(
            orientation="v",
            spacing=8,
            h_align="center",
            v_align="center",
            children=[
                self._preview_image,
                self._preview_name_label,
            ],
        )

        center_preview_row = Box(
            orientation="h",
            spacing=16,
            h_align="center",
            v_align="center",
            children=[
                self._prev_btn,
                preview_card,
                self._next_btn,
            ],
        )

        # Bottom Thumbnails Strip
        self._thumbs_box = Box(
            orientation="h",
            spacing=10,
            h_align="center",
        )

        self._thumbs_scroll = ScrolledWindow(
            min_content_height=90,
            max_content_height=100,
            h_expand=True,
            child=self._thumbs_box,
            style_classes=["wallpaper-picker-thumbs-scroll"],
        )

        # Modal Dialog Container
        modal_content = Box(
            orientation="v",
            spacing=20,
            style_classes=["wallpaper-picker-modal"],
            children=[
                header_bar,
                center_preview_row,
                self._thumbs_scroll,
            ],
        )

        main_overlay = Box(
            orientation="v",
            h_expand=True,
            v_expand=True,
            h_align="center",
            v_align="center",
            children=[modal_content],
        )

        container = Box(
            orientation="v",
            h_expand=True,
            v_expand=True,
            children=[main_overlay],
        )

        super().__init__(
            layer="top",
            anchor="top bottom left right",
            keyboard_mode="exclusive",
            title="agility-shell-wallpaper-picker",
            style_classes=["wallpaper-picker-window"],
            visible=False,
            child=container,
            **kwargs,
        )
        GtkLayerShell.set_exclusive_zone(self, -1)

        self.connect("key-press-event", self._on_key_press)
        self.connect("realize", self._on_realize)

    def _on_realize(self, *_):
        self._reload_wallpapers()

    def _reload_wallpapers(self):
        self._wallpapers = self._service.get_all_wallpapers()
        current_path = self._service.wallpaper_path

        # Find current index
        if current_path in self._wallpapers:
            self._current_index = self._wallpapers.index(current_path)
        elif self._wallpapers:
            self._current_index = 0

        # Build thumbnails
        for child in self._thumbs_box.get_children():
            self._thumbs_box.remove(child)
        self._thumb_widgets.clear()

        for path in self._wallpapers:
            thumb = WallpaperThumbnail(path, on_select=self._select_path, is_active=(path == current_path))
            self._thumb_widgets[path] = thumb
            self._thumbs_box.add(thumb)

        self._thumbs_box.show_all()
        self._update_preview()

    def _update_preview(self):
        if not self._wallpapers or self._current_index >= len(self._wallpapers):
            return

        active_path = self._wallpapers[self._current_index]
        self._count_label.set_label(f"{self._current_index + 1} of {len(self._wallpapers)}")
        self._preview_name_label.set_label(os.path.basename(active_path))

        try:
            # Scaled preview for fast crisp rendering
            pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_scale(active_path, 640, 360, True)
            self._preview_image.set_from_pixbuf(pixbuf)
        except Exception as e:
            logger.error(f"[WallpaperPicker] failed to preview image {active_path}: {e}")

        # Update thumbnail active borders
        for path, thumb in self._thumb_widgets.items():
            thumb.set_active(path == active_path)

    def _select_path(self, path: str):
        if path in self._wallpapers:
            self._current_index = self._wallpapers.index(path)
            self._update_preview()

    def _prev_wallpaper(self):
        if not self._wallpapers:
            return
        self._current_index = (self._current_index - 1) % len(self._wallpapers)
        self._update_preview()

    def _next_wallpaper(self):
        if not self._wallpapers:
            return
        self._current_index = (self._current_index + 1) % len(self._wallpapers)
        self._update_preview()

    def _shuffle_random(self):
        chosen = self._service.random_wallpaper()
        if chosen and chosen in self._wallpapers:
            self._current_index = self._wallpapers.index(chosen)
            self._update_preview()

    def _apply_and_close(self):
        if self._wallpapers and self._current_index < len(self._wallpapers):
            active_path = self._wallpapers[self._current_index]
            self._service.set_wallpaper(active_path)
        self.close()

    def _on_key_press(self, widget, event: Gdk.EventKey):
        keyval = event.keyval
        if keyval in (Gdk.KEY_Left, Gdk.KEY_h, Gdk.KEY_k):
            self._prev_wallpaper()
            return True
        elif keyval in (Gdk.KEY_Right, Gdk.KEY_l, Gdk.KEY_j):
            self._next_wallpaper()
            return True
        elif keyval in (Gdk.KEY_Return, Gdk.KEY_KP_Enter, Gdk.KEY_space):
            self._apply_and_close()
            return True
        elif keyval in (Gdk.KEY_r, Gdk.KEY_R):
            self._shuffle_random()
            return True
        elif keyval == Gdk.KEY_Escape:
            self.close()
            return True
        return False

    def toggle(self, active_monitor=None):
        if self.is_visible():
            self.close()
        else:
            self.open(active_monitor)

    def open(self, active_monitor=None):
        self._reload_wallpapers()
        self.show_all()

    def close(self):
        self.hide()
