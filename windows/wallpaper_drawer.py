import os
import gc
import math
import cairo
import hashlib
import weakref
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, Future

import gi
gi.require_version("PangoCairo", "1.0")
from gi.repository import Gtk, Gdk, GdkPixbuf, GLib, Pango, PangoCairo, GtkLayerShell
from PIL import Image as PilImage
from loguru import logger

from fabric.widgets.wayland import WaylandWindow as Window
from fabric.widgets.box import Box
from fabric.widgets.label import Label
from fabric.widgets.image import Image
from fabric.widgets.button import Button
from fabric.widgets.eventbox import EventBox
from fabric.widgets.scrolledwindow import ScrolledWindow

from snippets import ClippingBox, AppletReveal, Animator, Icon, enable_blur, disable_blur
from services.wallpaper import WallpaperService
from utils.sounds import play_sound
from user_options import user_options

THUMB_CACHE_DIR = Path.home() / ".cache" / "agility-shell" / "thumbnails"
THUMB_MAX_WIDTH = 540
THUMB_MAX_HEIGHT = 304

CARD_WIDTH = 168
CARD_HEIGHT = 95
ACTIVE_WIDTH = 200
ACTIVE_HEIGHT = 112
SPACING = 16
SLOT_WIDTH = CARD_WIDTH + SPACING  # 184px
NUM_SLOTS = 7
CENTER_SLOT = 3  # Slot 3 is the dead center slot (0..6)
BASE_OFFSET = SLOT_WIDTH  # ScrolledWindow scroll offset so Slot 1..5 are in view


def _render_shape(cr: cairo.Context, x: float, y: float, w: float, h: float, radius: float) -> None:
    radius = max(0.0, min(radius, min(w / 2.0, h / 2.0)))
    cr.new_sub_path()
    cr.arc(x + w - radius, y + radius, radius, -math.pi / 2.0, 0.0)
    cr.arc(x + w - radius, y + h - radius, radius, 0.0, math.pi / 2.0)
    cr.arc(x + radius, y + h - radius, radius, math.pi / 2.0, math.pi)
    cr.arc(x + radius, y + radius, radius, math.pi, 3.0 * math.pi / 2.0)
    cr.close_path()


def _fast_cache_key(path: str) -> str:
    try:
        stat = os.stat(path)
        raw = f"{path}:{stat.st_mtime}:{stat.st_size}:agility_v3"
    except Exception:
        raw = f"{path}:agility_v3"
    return hashlib.sha256(raw.encode()).hexdigest()


def _get_thumb_cache_path(file_path: str) -> Path:
    return THUMB_CACHE_DIR / f"{_fast_cache_key(file_path)}.jpg"


def _generate_thumb_to_cache(file_path: str) -> Path | None:
    try:
        THUMB_CACHE_DIR.mkdir(parents=True, exist_ok=True)
        cache_path = _get_thumb_cache_path(file_path)
        if not cache_path.exists():
            with PilImage.open(file_path) as img:
                if hasattr(img, "draft"):
                    img.draft("RGB", (THUMB_MAX_WIDTH, THUMB_MAX_HEIGHT))
                if img.mode != "RGB":
                    img = img.convert("RGB")
                w, h = img.size
                target_ratio = 16.0 / 9.0
                current_ratio = w / float(h)
                if current_ratio > target_ratio:
                    new_w = int(h * target_ratio)
                    left = (w - new_w) // 2
                    img = img.crop((left, 0, left + new_w, h))
                else:
                    new_h = int(w / target_ratio)
                    top = (h - new_h) // 2
                    img = img.crop((0, top, w, top + new_h))

                thumb = img.resize((THUMB_MAX_WIDTH, THUMB_MAX_HEIGHT), PilImage.Resampling.LANCZOS)
                thumb.save(cache_path, "JPEG", quality=85, optimize=True)
                del thumb
            gc.collect()
        return cache_path
    except Exception as e:
        logger.debug(f"[WallpaperDrawer] Failed to generate thumb for {file_path}: {e}")
        return None


# =============================================================================
# Slot Card for Dock and Stairs
# =============================================================================

class WallpaperSlotCard(EventBox):
    def __init__(
        self,
        slot_index: int,
        on_slot_clicked,
        card_width: int = CARD_WIDTH,
        card_height: int = CARD_HEIGHT,
        active_width: int = ACTIVE_WIDTH,
        active_height: int = ACTIVE_HEIGHT,
    ):
        self.slot_index = slot_index
        self.on_slot_clicked = on_slot_clicked
        self.card_width = card_width
        self.card_height = card_height
        self.active_width = active_width
        self.active_height = active_height

        self.path: str = ""
        self._is_active: bool = (slot_index == CENTER_SLOT)
        self._load_generation = 0
        self._future: Future | None = None
        self._pixbuf_cache: dict[str, GdkPixbuf.Pixbuf] = {}

        self._image = Image(style_classes=["wallpaper-card-img"])
        self._clip_box = ClippingBox(
            style_classes=["wallpaper-card-clip"],
            children=[self._image],
        )

        w = self.active_width if self._is_active else self.card_width
        h = self.active_height if self._is_active else self.card_height
        self._clip_box.set_size_request(w, h)

        self._label = Label(
            label="",
            style_classes=["wallpaper-card-label"] + (["active"] if self._is_active else []),
            ellipsize="end",
            max_chars_width=20,
            h_align="center",
        )

        self.box = Box(
            orientation="v",
            spacing=6,
            h_align="center",
            v_align="center",
            style_classes=["wallpaper-card"] + (["active"] if self._is_active else ["inactive"]),
            children=[self._clip_box, self._label],
        )

        super().__init__(
            child=self.box,
            style_classes=["wallpaper-card-eventbox"],
        )
        self.set_size_request(max(w, self.card_width) + 16, self.active_height + 38)
        self.connect("button-press-event", self._on_button_press)

    def bind_wallpaper(self, path: str, is_active: bool, executor: ThreadPoolExecutor):
        self.path = path
        self._is_active = is_active

        raw_name = os.path.splitext(os.path.basename(path))[0]
        clean_name = raw_name.replace("-", " ").replace("_", " ").lower()
        self._label.set_label(clean_name)

        if is_active:
            self.box.remove_style_class("inactive")
            self.box.add_style_class("active")
            self._label.add_style_class("active")
            w, h = self.active_width, self.active_height
        else:
            self.box.remove_style_class("active")
            self.box.add_style_class("inactive")
            self._label.remove_style_class("active")
            w, h = self.card_width, self.card_height

        self._clip_box.set_size_request(w, h)

        if path in self._pixbuf_cache:
            pix = self._pixbuf_cache[path]
            scaled = pix if is_active else pix.scale_simple(self.card_width, self.card_height, GdkPixbuf.InterpType.BILINEAR)
            self._image.set_from_pixbuf(scaled)
            return

        self._load_async(path, is_active, executor)

    def _load_async(self, path: str, is_active: bool, executor: ThreadPoolExecutor):
        self._load_generation += 1
        gen = self._load_generation
        ref = weakref.ref(self)

        def work():
            cache_path = _generate_thumb_to_cache(path)
            if cache_path is None:
                return
            try:
                pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_scale(str(cache_path), self.active_width, self.active_height, False)
            except Exception:
                return

            def apply():
                widget = ref()
                if widget is None or gen != widget._load_generation:
                    return GLib.SOURCE_REMOVE
                widget._pixbuf_cache[path] = pixbuf
                scaled = pixbuf if widget._is_active else pixbuf.scale_simple(widget.card_width, widget.card_height, GdkPixbuf.InterpType.BILINEAR)
                widget._image.set_from_pixbuf(scaled)
                return GLib.SOURCE_REMOVE

            GLib.idle_add(apply)

        self._future = executor.submit(work)

    def _on_button_press(self, widget, event: Gdk.EventButton):
        if event.button == 1:
            self.on_slot_clicked(self.slot_index, self.path)
            return True
        return False


# =============================================================================
# 1. Dock Window (Classic Caelestia 1:1 Floating Dock Switcher)
# =============================================================================

class WallpaperDockWindow(Window):
    def __init__(self, **kwargs):
        self._service = WallpaperService.get_instance()
        self._wallpapers: list[str] = []
        self._current_index: int = 0
        self._original_wallpaper: str = ""
        self._previewed_wallpaper: str = ""
        self._executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="DockPool")
        self._preview_timer_id: int | None = None
        self._animator: Animator | None = None
        self._active_monitor = None

        self._carousel_box = Box(
            orientation="h",
            spacing=0,
            h_align="start",
            v_align="center",
            style_classes=["wallpaper-drawer-carousel"],
        )

        self._slot_cards: list[WallpaperSlotCard] = []
        for i in range(NUM_SLOTS):
            card = WallpaperSlotCard(
                slot_index=i,
                on_slot_clicked=self._on_slot_clicked,
                card_width=CARD_WIDTH,
                card_height=CARD_HEIGHT,
                active_width=ACTIVE_WIDTH,
                active_height=ACTIVE_HEIGHT,
            )
            self._slot_cards.append(card)
            self._carousel_box.add(card)

        viewport_width = 5 * SLOT_WIDTH
        viewport_height = ACTIVE_HEIGHT + 44

        self._scroller = ScrolledWindow(
            h_expand=False,
            v_expand=False,
            min_content_width=viewport_width,
            max_content_width=viewport_width,
            min_content_height=viewport_height,
            max_content_height=viewport_height,
            h_scrollbar_policy=Gtk.PolicyType.NEVER,
            v_scrollbar_policy=Gtk.PolicyType.NEVER,
            child=self._carousel_box,
            style_classes=["wallpaper-drawer-scroller"],
        )
        self._scroller.connect("scroll-event", self._on_mouse_scroll)

        self._dock_container = Box(
            orientation="h",
            h_align="center",
            v_align="center",
            style_classes=["wallpaper-drawer-dock"],
            children=[self._scroller],
        )

        self._revealer = AppletReveal(
            direction="up",
            child=self._dock_container,
            open_duration=0.20,
            close_duration=0.16,
            h_align="center",
            v_align="end",
        )

        super().__init__(
            layer="top",
            anchor="bottom",
            keyboard_mode="none",
            title="agility-shell-wallpaper-drawer",
            style_classes=["wallpaper-drawer-window"],
            visible=False,
            child=self._revealer,
            **kwargs,
        )
        self.set_margin_bottom(28)
        GtkLayerShell.set_exclusive_zone(self, -1)

        self.connect("key-press-event", self._on_key_press)
        self.connect("focus-out-event", self._on_focus_out)

    def _on_focus_out(self, widget, event):
        if self.is_visible():
            self._cancel_and_close()
        return False

    def _on_key_press(self, widget, event: Gdk.EventKey):
        keyval = event.keyval
        if keyval in (Gdk.KEY_Left, Gdk.KEY_h, Gdk.KEY_H):
            self._navigate_step(-1)
            return True
        elif keyval in (Gdk.KEY_Right, Gdk.KEY_l, Gdk.KEY_L):
            self._navigate_step(+1)
            return True
        elif keyval in (Gdk.KEY_Return, Gdk.KEY_KP_Enter, Gdk.KEY_space):
            self._commit_and_close()
            return True
        elif keyval in (Gdk.KEY_r, Gdk.KEY_R):
            self._shuffle_random()
            return True
        elif keyval == Gdk.KEY_Escape:
            self._cancel_and_close()
            return True
        return False

    def _on_mouse_scroll(self, widget, event: Gdk.EventScroll):
        if event.direction == Gdk.ScrollDirection.UP or event.delta_y < 0:
            self._navigate_step(-1)
            return True
        elif event.direction == Gdk.ScrollDirection.DOWN or event.delta_y > 0:
            self._navigate_step(+1)
            return True
        elif event.direction == Gdk.ScrollDirection.SMOOTH:
            if event.delta_y < 0 or event.delta_x < 0:
                self._navigate_step(-1)
                return True
            elif event.delta_y > 0 or event.delta_x > 0:
                self._navigate_step(+1)
                return True
        return False

    def _on_slot_clicked(self, slot_idx: int, path: str):
        delta = slot_idx - CENTER_SLOT
        if delta == 0:
            self._commit_and_close()
        else:
            self._navigate_step(delta)

    def _reload_wallpapers(self):
        self._wallpapers = self._service.get_all_wallpapers()
        current_path = self._service.wallpaper_path
        self._original_wallpaper = current_path
        self._previewed_wallpaper = current_path

        if current_path in self._wallpapers:
            self._current_index = self._wallpapers.index(current_path)
        elif self._wallpapers:
            self._current_index = 0

        self._scroller.get_hadjustment().set_value(BASE_OFFSET)
        self._render_slots(trigger_preview=False)

    def _render_slots(self, trigger_preview: bool = True):
        if not self._wallpapers:
            return

        N = len(self._wallpapers)
        for i in range(NUM_SLOTS):
            rel = i - CENTER_SLOT
            idx = (self._current_index + rel) % N
            path = self._wallpapers[idx]
            is_active = (i == CENTER_SLOT)
            self._slot_cards[i].bind_wallpaper(path, is_active, self._executor)

        if trigger_preview:
            self._schedule_live_preview()

    def _navigate_step(self, delta: int):
        if not self._wallpapers:
            return

        if self._animator:
            self._animator.pause()
            self._animator = None
            self._scroller.get_hadjustment().set_value(BASE_OFFSET)

        N = len(self._wallpapers)
        target_index = (self._current_index + delta) % N

        start_val = BASE_OFFSET
        end_val = BASE_OFFSET + (delta * SLOT_WIDTH)
        adj = self._scroller.get_hadjustment()

        def on_update(anim, _):
            adj.set_value(anim.value)

        def on_finished(_):
            self._current_index = target_index
            adj.set_value(BASE_OFFSET)
            self._render_slots(trigger_preview=True)
            self._animator = None

        try:
            self._animator = (
                Animator(
                    bezier_curve=(0.16, 1.0, 0.3, 1.0),
                    duration=0.16,
                    min_value=float(start_val),
                    max_value=float(end_val),
                    tick_widget=self._scroller,
                )
                .build()
                .unwrap()
            )
            self._animator.connect("notify::value", on_update)
            self._animator.connect("finished", on_finished)
            self._animator.play()
        except Exception:
            self._current_index = target_index
            adj.set_value(BASE_OFFSET)
            self._render_slots(trigger_preview=True)

    def _shuffle_random(self):
        if not self._wallpapers:
            return
        import random
        candidates = [i for i in range(len(self._wallpapers)) if i != self._current_index]
        self._current_index = random.choice(candidates) if candidates else 0
        self._scroller.get_hadjustment().set_value(BASE_OFFSET)
        self._render_slots(trigger_preview=True)

    def _schedule_live_preview(self):
        if self._preview_timer_id is not None:
            GLib.source_remove(self._preview_timer_id)
            self._preview_timer_id = None

        def _do_preview():
            self._preview_timer_id = None
            if 0 <= self._current_index < len(self._wallpapers):
                active_path = self._wallpapers[self._current_index]
                self._previewed_wallpaper = active_path
                anim_duration = 0.5 if getattr(user_options.wallpaper, "hotkey_animations", True) else 0.0
                self._service.preview_wallpaper(active_path, pos=(0.5, 0.92), duration=anim_duration)
            return GLib.SOURCE_REMOVE

        self._preview_timer_id = GLib.timeout_add(60, _do_preview)

    def _commit_and_close(self):
        if self._preview_timer_id is not None:
            GLib.source_remove(self._preview_timer_id)
            self._preview_timer_id = None

        if self._wallpapers and 0 <= self._current_index < len(self._wallpapers):
            active_path = self._wallpapers[self._current_index]
            self._service.set_wallpaper(active_path, pos=(0.5, 0.92), is_hotkey=True)
            play_sound("confirm")

        self.close()

    def _cancel_and_close(self):
        if self._preview_timer_id is not None:
            GLib.source_remove(self._preview_timer_id)
            self._preview_timer_id = None

        if self._original_wallpaper and self._previewed_wallpaper != self._original_wallpaper:
            self._service.preview_wallpaper(self._original_wallpaper, pos=(0.5, 0.92), duration=0.3)

        self.close()

    def toggle(self, active_monitor=None):
        if self.is_visible():
            self._cancel_and_close()
        else:
            self.open(active_monitor)

    def open(self, active_monitor=None):
        self._active_monitor = active_monitor
        if active_monitor is not None:
            try:
                display = Gdk.Display.get_default()
                for i in range(display.get_n_monitors()):
                    if display.get_monitor(i) == active_monitor:
                        self.set_monitor(i)
                        break
            except Exception as e:
                logger.debug(f"[WallpaperDock] Failed to set monitor: {e}")

        self._reload_wallpapers()
        self.show_all()
        self._scroller.get_hadjustment().set_value(BASE_OFFSET)
        GtkLayerShell.set_keyboard_interactivity(self, True)
        self._revealer.open()

    def close(self):
        def on_done():
            self.hide()
            GtkLayerShell.set_keyboard_interactivity(self, False)

        if self._revealer:
            self._revealer.close(on_done=on_done)
        else:
            on_done()


# =============================================================================
# 2. Stairs Window (Upscaled Diagonal Stepped Switcher - "Lite Big")
# =============================================================================

STAIRS_CARD_WIDTH = 220
STAIRS_CARD_HEIGHT = 124
STAIRS_ACTIVE_WIDTH = 280
STAIRS_ACTIVE_HEIGHT = 158

class WallpaperStairsWindow(Window):
    def __init__(self, **kwargs):
        self._service = WallpaperService.get_instance()
        self._wallpapers: list[str] = []
        self._current_index: int = 0
        self._original_wallpaper: str = ""
        self._previewed_wallpaper: str = ""
        self._executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="StairsPool")
        self._preview_timer_id: int | None = None
        self._active_monitor = None
        self._blur_ctx = None

        # Upscaled diagonal coordinates from top-left to bottom-right
        self._step_coords = [
            (30, 20),
            (150, 110),
            (270, 200),
            (400, 290),  # Slot 3: Center active card (280x158)
            (560, 400),
            (680, 490),
            (800, 580),
        ]

        self._fixed = Gtk.Fixed()
        self._fixed.set_size_request(1100, 760)
        self._slot_cards: list[WallpaperSlotCard] = []

        for i in range(NUM_SLOTS):
            card = WallpaperSlotCard(
                slot_index=i,
                on_slot_clicked=self._on_slot_clicked,
                card_width=STAIRS_CARD_WIDTH,
                card_height=STAIRS_CARD_HEIGHT,
                active_width=STAIRS_ACTIVE_WIDTH,
                active_height=STAIRS_ACTIVE_HEIGHT,
            )
            card.box.add_style_class("wallpaper-stairs-card")
            self._slot_cards.append(card)
            x, y = self._step_coords[i]
            self._fixed.put(card, x, y)

        stairs_wrapper = Box(
            orientation="v",
            h_align="center",
            v_align="center",
            style_classes=["wallpaper-stairs-container"],
            children=[self._fixed],
        )

        self._backdrop = EventBox(
            style_classes=["wallpaper-stairs-backdrop"],
            h_expand=True,
            v_expand=True,
            child=stairs_wrapper,
        )
        self._backdrop.connect("button-press-event", self._on_backdrop_clicked)
        self._backdrop.connect("scroll-event", self._on_mouse_scroll)

        super().__init__(
            layer="top",
            anchor="top bottom left right",
            keyboard_mode="none",
            title="agility-shell-wallpaper-stairs",
            style_classes=["wallpaper-stairs-window"],
            visible=False,
            child=self._backdrop,
            **kwargs,
        )
        GtkLayerShell.set_exclusive_zone(self, -1)
        self.connect("key-press-event", self._on_key_press)
        self.connect("focus-out-event", self._on_focus_out)

    def _on_focus_out(self, widget, event):
        if self.is_visible():
            self._cancel_and_close()
        return False

    def _on_backdrop_clicked(self, widget, event: Gdk.EventButton):
        if event.button == 1:
            alloc = self._fixed.get_allocation()
            coords = self._fixed.translate_coordinates(self, 0, 0)
            if coords:
                wx, wy = coords
                if not (wx <= event.x <= wx + alloc.width and wy <= event.y <= wy + alloc.height):
                    self._cancel_and_close()
                    return True
            else:
                self._cancel_and_close()
                return True
        return False

    def _on_key_press(self, widget, event: Gdk.EventKey):
        keyval = event.keyval
        if keyval in (Gdk.KEY_Left, Gdk.KEY_Up, Gdk.KEY_h, Gdk.KEY_H, Gdk.KEY_k, Gdk.KEY_K):
            self._navigate_step(-1)
            return True
        elif keyval in (Gdk.KEY_Right, Gdk.KEY_Down, Gdk.KEY_l, Gdk.KEY_L, Gdk.KEY_j, Gdk.KEY_J):
            self._navigate_step(+1)
            return True
        elif keyval in (Gdk.KEY_Return, Gdk.KEY_KP_Enter, Gdk.KEY_space):
            self._commit_and_close()
            return True
        elif keyval in (Gdk.KEY_r, Gdk.KEY_R):
            self._shuffle_random()
            return True
        elif keyval == Gdk.KEY_Escape:
            self._cancel_and_close()
            return True
        return False

    def _on_mouse_scroll(self, widget, event: Gdk.EventScroll):
        if event.direction == Gdk.ScrollDirection.UP or event.delta_y < 0:
            self._navigate_step(-1)
            return True
        elif event.direction == Gdk.ScrollDirection.DOWN or event.delta_y > 0:
            self._navigate_step(+1)
            return True
        elif event.direction == Gdk.ScrollDirection.SMOOTH:
            if event.delta_y < 0 or event.delta_x < 0:
                self._navigate_step(-1)
                return True
            elif event.delta_y > 0 or event.delta_x > 0:
                self._navigate_step(+1)
                return True
        return False

    def _on_slot_clicked(self, slot_idx: int, path: str):
        delta = slot_idx - CENTER_SLOT
        if delta == 0:
            self._commit_and_close()
        else:
            self._navigate_step(delta)

    def _reload_wallpapers(self):
        self._wallpapers = self._service.get_all_wallpapers()
        current_path = self._service.wallpaper_path
        self._original_wallpaper = current_path
        self._previewed_wallpaper = current_path

        if current_path in self._wallpapers:
            self._current_index = self._wallpapers.index(current_path)
        elif self._wallpapers:
            self._current_index = 0

        self._render_slots(trigger_preview=False)

    def _render_slots(self, trigger_preview: bool = True):
        if not self._wallpapers:
            return

        N = len(self._wallpapers)
        for i in range(NUM_SLOTS):
            rel = i - CENTER_SLOT
            idx = (self._current_index + rel) % N
            path = self._wallpapers[idx]
            is_active = (i == CENTER_SLOT)
            self._slot_cards[i].bind_wallpaper(path, is_active, self._executor)

        if trigger_preview:
            self._schedule_live_preview()

    def _navigate_step(self, delta: int):
        if not self._wallpapers:
            return
        N = len(self._wallpapers)
        self._current_index = (self._current_index + delta) % N
        self._render_slots(trigger_preview=True)

    def _shuffle_random(self):
        if not self._wallpapers:
            return
        import random
        candidates = [i for i in range(len(self._wallpapers)) if i != self._current_index]
        self._current_index = random.choice(candidates) if candidates else 0
        self._render_slots(trigger_preview=True)

    def _schedule_live_preview(self):
        if self._preview_timer_id is not None:
            GLib.source_remove(self._preview_timer_id)
            self._preview_timer_id = None

        def _do_preview():
            self._preview_timer_id = None
            if 0 <= self._current_index < len(self._wallpapers):
                active_path = self._wallpapers[self._current_index]
                self._previewed_wallpaper = active_path
                anim_duration = 0.4 if getattr(user_options.wallpaper, "hotkey_animations", True) else 0.0
                self._service.preview_wallpaper(active_path, pos=(0.5, 0.5), duration=anim_duration)
            return GLib.SOURCE_REMOVE

        self._preview_timer_id = GLib.timeout_add(60, _do_preview)

    def _commit_and_close(self):
        if self._preview_timer_id is not None:
            GLib.source_remove(self._preview_timer_id)
            self._preview_timer_id = None

        if self._wallpapers and 0 <= self._current_index < len(self._wallpapers):
            active_path = self._wallpapers[self._current_index]
            self._service.set_wallpaper(active_path, pos=(0.5, 0.5), is_hotkey=True)
            play_sound("confirm")

        self.close()

    def _cancel_and_close(self):
        if self._preview_timer_id is not None:
            GLib.source_remove(self._preview_timer_id)
            self._preview_timer_id = None

        if self._original_wallpaper and self._previewed_wallpaper != self._original_wallpaper:
            self._service.preview_wallpaper(self._original_wallpaper, pos=(0.5, 0.5), duration=0.3)

        self.close()

    def toggle(self, active_monitor=None):
        if self.is_visible():
            self._cancel_and_close()
        else:
            self.open(active_monitor)

    def open(self, active_monitor=None):
        self._active_monitor = active_monitor
        if active_monitor is not None:
            try:
                display = Gdk.Display.get_default()
                for i in range(display.get_n_monitors()):
                    if display.get_monitor(i) == active_monitor:
                        self.set_monitor(i)
                        break
            except Exception as e:
                logger.debug(f"[WallpaperStairs] Failed to set monitor: {e}")

        self._reload_wallpapers()
        self.show_all()
        GtkLayerShell.set_keyboard_interactivity(self, True)
        if self._blur_ctx is None:
            self._blur_ctx = enable_blur(self)

    def close(self):
        if self._blur_ctx is not None:
            try:
                disable_blur(self)
            except Exception:
                pass
            self._blur_ctx = None
        self.hide()
        GtkLayerShell.set_keyboard_interactivity(self, False)


# =============================================================================
# 3. Mesh Window (Organic Cluster / Force-Directed Canvas with Cursor Zoom & Pan)
# =============================================================================

class WallpaperMeshWindow(Window):
    def __init__(self, **kwargs):
        self._service = WallpaperService.get_instance()
        self._wallpapers: list[str] = []
        self._executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="MeshPool")
        self._blur_ctx = None
        self._active_monitor = None
        self._pixbufs: dict[str, GdkPixbuf.Pixbuf] = {}
        self._nodes: list[dict] = []

        self._zoom: float = 1.0
        self._pan_x: float = 0.0
        self._pan_y: float = 0.0
        self._drag_start: tuple[float, float] | None = None
        self._pan_start: tuple[float, float] = (0.0, 0.0)
        self._drag_moved: bool = False
        self._hovered_idx: int | None = None
        self._selected_idx: int | None = None

        self._da = Gtk.DrawingArea()
        self._da.set_hexpand(True)
        self._da.set_vexpand(True)
        self._da.add_events(
            Gdk.EventMask.BUTTON_PRESS_MASK
            | Gdk.EventMask.BUTTON_RELEASE_MASK
            | Gdk.EventMask.POINTER_MOTION_MASK
            | Gdk.EventMask.SCROLL_MASK
            | Gdk.EventMask.SMOOTH_SCROLL_MASK
            | Gdk.EventMask.LEAVE_NOTIFY_MASK
        )

        self._da.connect("draw", self._on_draw)
        self._da.connect("button-press-event", self._on_button_press)
        self._da.connect("button-release-event", self._on_button_release)
        self._da.connect("motion-notify-event", self._on_motion_notify)
        self._da.connect("scroll-event", self._on_scroll)
        self._da.connect("leave-notify-event", self._on_leave)

        super().__init__(
            layer="top",
            anchor="top bottom left right",
            keyboard_mode="none",
            title="agility-shell-wallpaper-mesh",
            style_classes=["wallpaper-mesh-window"],
            visible=False,
            child=self._da,
            **kwargs,
        )
        GtkLayerShell.set_exclusive_zone(self, -1)
        self.connect("key-press-event", self._on_key_press)
        self.connect("focus-out-event", self._on_focus_out)

    def _on_focus_out(self, widget, event):
        if self.is_visible():
            self.close()
        return False

    def _on_key_press(self, widget, event: Gdk.EventKey):
        keyval = event.keyval
        if keyval in (Gdk.KEY_Escape,):
            self.close()
            return True
        elif keyval in (Gdk.KEY_r, Gdk.KEY_R):
            self.close()
            self._service.random_wallpaper(is_hotkey=True)
            return True
        elif keyval in (Gdk.KEY_plus, Gdk.KEY_equal, Gdk.KEY_KP_Add):
            self._zoom_step(1.2)
            return True
        elif keyval in (Gdk.KEY_minus, Gdk.KEY_underscore, Gdk.KEY_KP_Subtract):
            self._zoom_step(1.0 / 1.2)
            return True
        elif keyval in (Gdk.KEY_0, Gdk.KEY_KP_0):
            self._zoom = 1.0
            self._pan_x = 0.0
            self._pan_y = 0.0
            self._da.queue_draw()
            return True
        elif keyval in (Gdk.KEY_Left, Gdk.KEY_h):
            self._pan_x += 60
            self._da.queue_draw()
            return True
        elif keyval in (Gdk.KEY_Right, Gdk.KEY_l):
            self._pan_x -= 60
            self._da.queue_draw()
            return True
        elif keyval in (Gdk.KEY_Up, Gdk.KEY_k):
            self._pan_y += 60
            self._da.queue_draw()
            return True
        elif keyval in (Gdk.KEY_Down, Gdk.KEY_j):
            self._pan_y -= 60
            self._da.queue_draw()
            return True
        return False

    def _zoom_step(self, factor: float):
        self._zoom = max(0.35, min(3.5, self._zoom * factor))
        self._da.queue_draw()

    def _on_scroll(self, widget, event: Gdk.EventScroll):
        if event.direction == Gdk.ScrollDirection.UP:
            factor = 1.15
        elif event.direction == Gdk.ScrollDirection.DOWN:
            factor = 1.0 / 1.15
        elif event.direction == Gdk.ScrollDirection.SMOOTH:
            delta = event.delta_y
            if abs(delta) < 0.001:
                delta = event.delta_x
            factor = 1.0 - (delta * 0.12)
        else:
            return False

        alloc = widget.get_allocation()
        cx = alloc.width / 2.0
        cy = alloc.height / 2.0

        wx = (event.x - (cx + self._pan_x)) / self._zoom
        wy = (event.y - (cy + self._pan_y)) / self._zoom

        new_zoom = max(0.35, min(3.5, self._zoom * factor))
        self._pan_x = event.x - cx - (wx * new_zoom)
        self._pan_y = event.y - cy - (wy * new_zoom)
        self._zoom = new_zoom

        self._update_hover(event.x, event.y)
        widget.queue_draw()
        return True

    def _on_button_press(self, widget, event: Gdk.EventButton):
        if event.button == 1:
            self._drag_start = (event.x, event.y)
            self._pan_start = (self._pan_x, self._pan_y)
            self._drag_moved = False
            return True
        return False

    def _on_motion_notify(self, widget, event: Gdk.EventMotion):
        if self._drag_start is not None and (event.state & Gdk.ModifierType.BUTTON1_MASK):
            dx = event.x - self._drag_start[0]
            dy = event.y - self._drag_start[1]
            if abs(dx) > 4 or abs(dy) > 4:
                self._drag_moved = True
                self._pan_x = self._pan_start[0] + dx
                self._pan_y = self._pan_start[1] + dy
                widget.queue_draw()
                return True
        self._update_hover(event.x, event.y)
        return False

    def _on_button_release(self, widget, event: Gdk.EventButton):
        if event.button == 1:
            if not self._drag_moved:
                hit = self._get_card_at(event.x, event.y)
                if hit:
                    self._trigger_card_selection(hit[0], hit[1])
                else:
                    self.close()
            self._drag_start = None
            self._drag_moved = False
            return True
        return False

    def _on_leave(self, widget, event: Gdk.EventCrossing):
        if self._hovered_idx is not None:
            self._hovered_idx = None
            win = self._da.get_window()
            if win:
                win.set_cursor(Gdk.Cursor.new_from_name(self._da.get_display(), "default"))
            self._da.queue_draw()
        return False

    def _get_card_at(self, sx: float, sy: float) -> tuple[int, dict] | None:
        alloc = self._da.get_allocation()
        cx = alloc.width / 2.0
        cy = alloc.height / 2.0

        for idx in reversed(range(len(self._nodes))):
            node = self._nodes[idx]
            nx = cx + self._pan_x + node["x"] * self._zoom - (node["w"] * self._zoom) / 2.0
            ny = cy + self._pan_y + node["y"] * self._zoom - (node["h"] * self._zoom) / 2.0
            nw = node["w"] * self._zoom
            nh = node["h"] * self._zoom
            if nx <= sx <= nx + nw and ny <= sy <= ny + nh:
                return (idx, node)
        return None

    def _update_hover(self, sx: float, sy: float):
        hit = self._get_card_at(sx, sy)
        new_hover = hit[0] if hit else None
        if new_hover != self._hovered_idx:
            self._hovered_idx = new_hover
            win = self._da.get_window()
            if win:
                cursor_name = "pointer" if hit else "default"
                win.set_cursor(Gdk.Cursor.new_from_name(self._da.get_display(), cursor_name))
            self._da.queue_draw()

    def _compute_mesh_layout(self, active_path: str):
        self._nodes.clear()
        if not self._wallpapers:
            return

        active_idx = 0
        if active_path in self._wallpapers:
            active_idx = self._wallpapers.index(active_path)

        ordered_paths = [self._wallpapers[active_idx]] + [
            p for i, p in enumerate(self._wallpapers) if i != active_idx
        ]

        N = len(ordered_paths)
        for i, path in enumerate(ordered_paths):
            raw_name = os.path.splitext(os.path.basename(path))[0]
            clean_name = raw_name.replace("-", " ").replace("_", " ").lower()

            if i == 0:
                w, h = 280.0, 158.0  # Hero
            elif i <= 5:
                w, h = 210.0, 118.0  # Medium / Lite small
            elif i <= 14:
                w, h = 160.0, 90.0   # Small
            else:
                w, h = 124.0, 70.0   # Compact

            self._nodes.append({
                "path": path,
                "title": clean_name,
                "w": w,
                "h": h,
                "x": 0.0,
                "y": 0.0,
                "is_active": (i == 0),
            })

        for k in range(1, N):
            angle = k * 2.399963
            dist = 190.0 + math.sqrt(k) * 125.0 + ((k * 37) % 30 - 15)
            self._nodes[k]["x"] = dist * math.cos(angle)
            self._nodes[k]["y"] = dist * math.sin(angle) * 0.72

        for _ in range(25):
            for k in range(1, N):
                self._nodes[k]["x"] -= self._nodes[k]["x"] * 0.03
                self._nodes[k]["y"] -= self._nodes[k]["y"] * 0.03

            for i in range(N):
                for j in range(i + 1, N):
                    rx = self._nodes[i]["x"] - self._nodes[j]["x"]
                    ry = self._nodes[i]["y"] - self._nodes[j]["y"]
                    d = math.hypot(rx, ry) + 0.001
                    min_d = math.hypot((self._nodes[i]["w"] + self._nodes[j]["w"]) / 2.0,
                                       (self._nodes[i]["h"] + self._nodes[j]["h"]) / 2.0) + 24.0
                    if d < min_d:
                        push = 0.4 * (min_d - d) / d
                        dx = rx * push
                        dy = ry * push
                        if i != 0:
                            self._nodes[i]["x"] += dx
                            self._nodes[i]["y"] += dy
                        if j != 0:
                            self._nodes[j]["x"] -= dx
                            self._nodes[j]["y"] -= dy

    def _reload_wallpapers(self):
        self._wallpapers = self._service.get_all_wallpapers()
        current_path = self._service.wallpaper_path
        self._compute_mesh_layout(current_path)

        for path in self._wallpapers:
            if path not in self._pixbufs:
                self._load_async_thumb(path)

    def _load_async_thumb(self, path: str):
        ref = weakref.ref(self)
        def work():
            cache_path = _generate_thumb_to_cache(path)
            if not cache_path:
                return
            try:
                pix = GdkPixbuf.Pixbuf.new_from_file_at_scale(str(cache_path), 480, 270, False)
                def apply():
                    win = ref()
                    if win is not None and win.is_visible():
                        win._pixbufs[path] = pix
                        win._da.queue_draw()
                    return GLib.SOURCE_REMOVE
                GLib.idle_add(apply)
            except Exception:
                pass
        self._executor.submit(work)

    def _trigger_card_selection(self, idx: int, node: dict):
        self._selected_idx = idx
        self._da.queue_draw()
        play_sound("confirm")
        self._service.set_wallpaper(node["path"], is_hotkey=True)
        GLib.timeout_add(160, self._finish_select)

    def _finish_select(self):
        self.close()
        return GLib.SOURCE_REMOVE

    def _on_draw(self, widget, cr: cairo.Context):
        alloc = widget.get_allocation()
        cx = alloc.width / 2.0
        cy = alloc.height / 2.0

        ctx = widget.get_style_context()
        found, col = ctx.lookup_color("primary")
        if found:
            accent_r, accent_g, accent_b = col.red, col.green, col.blue
        else:
            accent_r, accent_g, accent_b = 0.45, 0.65, 0.95

        p_ctx = PangoCairo.create_context(cr)

        for idx, node in enumerate(self._nodes):
            sw = node["w"] * self._zoom
            sh = node["h"] * self._zoom
            sx = cx + self._pan_x + (node["x"] * self._zoom) - (sw / 2.0)
            sy = cy + self._pan_y + (node["y"] * self._zoom) - (sh / 2.0)

            # Viewport culling
            if sx + sw < -20 or sx > alloc.width + 20 or sy + sh < -20 or sy > alloc.height + 20:
                continue

            radius = 14.0 * min(1.5, max(0.5, self._zoom))
            is_hovered = (idx == self._hovered_idx)
            is_selected = (idx == self._selected_idx)
            is_active = node["is_active"]

            # Drop shadow
            _render_shape(cr, sx, sy + 6.0 * self._zoom, sw, sh, radius)
            cr.set_source_rgba(0.0, 0.0, 0.0, 0.45)
            cr.fill()

            # Background base
            _render_shape(cr, sx, sy, sw, sh, radius)
            cr.set_source_rgba(0.12, 0.12, 0.16, 0.92)
            cr.fill()

            # Pixbuf thumbnail
            pix = self._pixbufs.get(node["path"])
            if pix is not None:
                cr.save()
                _render_shape(cr, sx, sy, sw, sh, radius)
                cr.clip()
                cr.translate(sx, sy)
                cr.scale(sw / pix.get_width(), sh / pix.get_height())
                Gdk.cairo_set_source_pixbuf(cr, pix, 0, 0)
                cr.paint()
                cr.restore()

            # Highlights & Borders
            if is_selected:
                _render_shape(cr, sx, sy, sw, sh, radius)
                cr.set_source_rgba(accent_r, accent_g, accent_b, 0.95)
                cr.set_line_width(5.0 * min(1.5, self._zoom))
                cr.stroke()
            elif is_active:
                _render_shape(cr, sx, sy, sw, sh, radius)
                cr.set_source_rgba(accent_r, accent_g, accent_b, 0.95)
                cr.set_line_width(3.5 * min(1.5, self._zoom))
                cr.stroke()
            elif is_hovered:
                _render_shape(cr, sx, sy, sw, sh, radius)
                cr.set_source_rgba(1.0, 1.0, 1.0, 0.85)
                cr.set_line_width(2.5 * min(1.5, self._zoom))
                cr.stroke()
            else:
                _render_shape(cr, sx, sy, sw, sh, radius)
                cr.set_source_rgba(1.0, 1.0, 1.0, 0.12)
                cr.set_line_width(1.0)
                cr.stroke()

            # Title label pill
            if sh > 55.0:
                pill_h = min(26.0, 22.0 * self._zoom)
                pill_margin = 6.0 * self._zoom
                _render_shape(cr, sx + pill_margin, sy + sh - pill_h - pill_margin, sw - (2.0 * pill_margin), pill_h, 6.0 * self._zoom)
                cr.set_source_rgba(0.05, 0.05, 0.08, 0.78)
                cr.fill()

                layout = Pango.Layout(p_ctx)
                layout.set_text(node["title"], -1)
                font_size = max(7, int(9 * min(1.4, self._zoom)))
                font_desc = Pango.FontDescription.from_string(f"Sans Bold {font_size}")
                layout.set_font_description(font_desc)
                layout.set_width(int((sw - 4.0 * pill_margin) * Pango.SCALE))
                layout.set_ellipsize(Pango.EllipsizeMode.END)
                layout.set_alignment(Pango.Alignment.CENTER)

                tw, th = layout.get_pixel_size()
                cr.move_to(sx + (sw - tw) / 2.0, sy + sh - pill_h - pill_margin + (pill_h - th) / 2.0)
                cr.set_source_rgba(0.95, 0.95, 0.98, 0.92)
                PangoCairo.show_layout(cr, layout)

        return False

    def toggle(self, active_monitor=None):
        if self.is_visible():
            self.close()
        else:
            self.open(active_monitor)

    def open(self, active_monitor=None):
        self._active_monitor = active_monitor
        if active_monitor is not None:
            try:
                display = Gdk.Display.get_default()
                for i in range(display.get_n_monitors()):
                    if display.get_monitor(i) == active_monitor:
                        self.set_monitor(i)
                        break
            except Exception as e:
                logger.debug(f"[WallpaperMesh] Failed to set monitor: {e}")

        self._zoom = 1.0
        self._pan_x = 0.0
        self._pan_y = 0.0
        self._drag_start = None
        self._drag_moved = False
        self._hovered_idx = None
        self._selected_idx = None

        self._reload_wallpapers()
        self.show_all()
        GtkLayerShell.set_keyboard_interactivity(self, True)
        if self._blur_ctx is None:
            self._blur_ctx = enable_blur(self)

    def close(self):
        if self._blur_ctx is not None:
            try:
                disable_blur(self)
            except Exception:
                pass
            self._blur_ctx = None
        self.hide()
        GtkLayerShell.set_keyboard_interactivity(self, False)


# =============================================================================
# 4. Wheel Window (Radial Orbit Switcher)
# =============================================================================

WHEEL_CENTER_W = 340
WHEEL_CENTER_H = 191
WHEEL_SAT_W = 136
WHEEL_SAT_H = 76
WHEEL_RADIUS = 310

class WallpaperWheelWindow(Window):
    def __init__(self, **kwargs):
        self._service = WallpaperService.get_instance()
        self._wallpapers: list[str] = []
        self._current_index: int = 0
        self._original_wallpaper: str = ""
        self._previewed_wallpaper: str = ""
        self._executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="WheelPool")
        self._preview_timer_id: int | None = None
        self._blur_ctx = None
        self._active_monitor = None

        self._fixed = Gtk.Fixed()
        self._fixed.set_size_request(880, 760)

        self._center_img = Image(style_classes=["wallpaper-card-img"])
        self._center_clip = ClippingBox(
            style_classes=["wallpaper-card-clip"],
            children=[self._center_img],
        )
        self._center_clip.set_size_request(WHEEL_CENTER_W, WHEEL_CENTER_H)

        self._center_title = Label(
            label="",
            style="font-size: 15px; font-weight: 700; color: var(--primary); margin-top: 6px;",
            ellipsize="end",
            max_chars_width=24,
            h_align="center",
        )
        self._center_hint = Label(
            label="Click or Enter to Apply  •  Scroll or Arrows to Rotate",
            style="font-size: 11px; opacity: 0.6; margin-top: 2px;",
            h_align="center",
        )

        center_vbox = Box(
            orientation="v",
            spacing=4,
            h_align="center",
            v_align="center",
            style_classes=["wallpaper-wheel-center"],
            children=[self._center_clip, self._center_title, self._center_hint],
        )
        self._center_event = EventBox(child=center_vbox)
        self._center_event.connect("button-press-event", lambda *_: self._commit_and_close())

        cx = (880 - WHEEL_CENTER_W - 32) / 2.0
        cy = (760 - WHEEL_CENTER_H - 60) / 2.0
        self._fixed.put(self._center_event, int(cx), int(cy))

        self._sat_cards: list[EventBox] = []
        self._sat_images: list[Image] = []
        self._sat_offsets = [-4, -3, -2, -1, 1, 2, 3, 4]

        center_point_x = 440.0
        center_point_y = 380.0

        for i, offset in enumerate(self._sat_offsets):
            angle = (i / 8.0) * (2.0 * math.pi) - (math.pi / 2.0)
            sx = center_point_x + (WHEEL_RADIUS * math.cos(angle)) - (WHEEL_SAT_W / 2.0)
            sy = center_point_y + (WHEEL_RADIUS * math.sin(angle)) - (WHEEL_SAT_H / 2.0)

            img = Image(style_classes=["wallpaper-card-img"])
            clip = ClippingBox(
                style_classes=["wallpaper-card-clip"],
                children=[img],
            )
            clip.set_size_request(WHEEL_SAT_W, WHEEL_SAT_H)

            box = Box(
                orientation="v",
                style_classes=["wallpaper-wheel-satellite"],
                children=[clip],
            )
            ev = EventBox(child=box)
            ev.connect("button-press-event", lambda _, off=offset: self._navigate_step(off))

            self._sat_cards.append(ev)
            self._sat_images.append(img)
            self._fixed.put(ev, int(sx), int(sy))

        wheel_wrapper = Box(
            orientation="v",
            h_align="center",
            v_align="center",
            children=[self._fixed],
        )

        self._backdrop = EventBox(
            style_classes=["wallpaper-wheel-backdrop"],
            h_expand=True,
            v_expand=True,
            child=wheel_wrapper,
        )
        self._backdrop.connect("button-press-event", self._on_backdrop_clicked)
        self._backdrop.connect("scroll-event", self._on_mouse_scroll)

        super().__init__(
            layer="top",
            anchor="top bottom left right",
            keyboard_mode="none",
            title="agility-shell-wallpaper-wheel",
            style_classes=["wallpaper-wheel-window"],
            visible=False,
            child=self._backdrop,
            **kwargs,
        )
        GtkLayerShell.set_exclusive_zone(self, -1)
        self.connect("key-press-event", self._on_key_press)
        self.connect("focus-out-event", self._on_focus_out)

    def _on_focus_out(self, widget, event):
        if self.is_visible():
            self._cancel_and_close()
        return False

    def _on_backdrop_clicked(self, widget, event: Gdk.EventButton):
        if event.button == 1:
            alloc = self._fixed.get_allocation()
            coords = self._fixed.translate_coordinates(self, 0, 0)
            if coords:
                wx, wy = coords
                if not (wx <= event.x <= wx + alloc.width and wy <= event.y <= wy + alloc.height):
                    self._cancel_and_close()
                    return True
            else:
                self._cancel_and_close()
                return True
        return False

    def _on_key_press(self, widget, event: Gdk.EventKey):
        keyval = event.keyval
        if keyval in (Gdk.KEY_Left, Gdk.KEY_Up, Gdk.KEY_h, Gdk.KEY_H, Gdk.KEY_k, Gdk.KEY_K):
            self._navigate_step(-1)
            return True
        elif keyval in (Gdk.KEY_Right, Gdk.KEY_Down, Gdk.KEY_l, Gdk.KEY_L, Gdk.KEY_j, Gdk.KEY_J):
            self._navigate_step(+1)
            return True
        elif keyval in (Gdk.KEY_Return, Gdk.KEY_KP_Enter, Gdk.KEY_space):
            self._commit_and_close()
            return True
        elif keyval in (Gdk.KEY_r, Gdk.KEY_R):
            self._shuffle_random()
            return True
        elif keyval == Gdk.KEY_Escape:
            self._cancel_and_close()
            return True
        return False

    def _on_mouse_scroll(self, widget, event: Gdk.EventScroll):
        if event.direction == Gdk.ScrollDirection.UP or event.delta_y < 0:
            self._navigate_step(-1)
            return True
        elif event.direction == Gdk.ScrollDirection.DOWN or event.delta_y > 0:
            self._navigate_step(+1)
            return True
        elif event.direction == Gdk.ScrollDirection.SMOOTH:
            if event.delta_y < 0 or event.delta_x < 0:
                self._navigate_step(-1)
                return True
            elif event.delta_y > 0 or event.delta_x > 0:
                self._navigate_step(+1)
                return True
        return False

    def _reload_wallpapers(self):
        self._wallpapers = self._service.get_all_wallpapers()
        current_path = self._service.wallpaper_path
        self._original_wallpaper = current_path
        self._previewed_wallpaper = current_path

        if current_path in self._wallpapers:
            self._current_index = self._wallpapers.index(current_path)
        elif self._wallpapers:
            self._current_index = 0

        self._render_wheel(trigger_preview=False)

    def _render_wheel(self, trigger_preview: bool = True):
        if not self._wallpapers:
            return

        N = len(self._wallpapers)
        active_path = self._wallpapers[self._current_index]

        raw_name = os.path.splitext(os.path.basename(active_path))[0]
        self._center_title.set_label(raw_name.replace("-", " ").replace("_", " ").lower())
        self._load_image_async(active_path, WHEEL_CENTER_W, WHEEL_CENTER_H, self._center_img)

        for i, offset in enumerate(self._sat_offsets):
            idx = (self._current_index + offset) % N
            sat_path = self._wallpapers[idx]
            self._load_image_async(sat_path, WHEEL_SAT_W, WHEEL_SAT_H, self._sat_images[i])

        if trigger_preview:
            self._schedule_live_preview()

    def _load_image_async(self, path: str, target_w: int, target_h: int, target_img: Image):
        ref_img = weakref.ref(target_img)
        def work():
            cache_path = _generate_thumb_to_cache(path)
            if not cache_path:
                return
            try:
                pix = GdkPixbuf.Pixbuf.new_from_file_at_scale(str(cache_path), target_w, target_h, False)
                def apply():
                    img = ref_img()
                    if img is not None:
                        img.set_from_pixbuf(pix)
                    return GLib.SOURCE_REMOVE
                GLib.idle_add(apply)
            except Exception:
                pass
        self._executor.submit(work)

    def _navigate_step(self, delta: int):
        if not self._wallpapers:
            return
        N = len(self._wallpapers)
        self._current_index = (self._current_index + delta) % N
        self._render_wheel(trigger_preview=True)

    def _shuffle_random(self):
        if not self._wallpapers:
            return
        import random
        candidates = [i for i in range(len(self._wallpapers)) if i != self._current_index]
        self._current_index = random.choice(candidates) if candidates else 0
        self._render_wheel(trigger_preview=True)

    def _schedule_live_preview(self):
        if self._preview_timer_id is not None:
            GLib.source_remove(self._preview_timer_id)
            self._preview_timer_id = None

        def _do_preview():
            self._preview_timer_id = None
            if 0 <= self._current_index < len(self._wallpapers):
                active_path = self._wallpapers[self._current_index]
                self._previewed_wallpaper = active_path
                anim_duration = 0.4 if getattr(user_options.wallpaper, "hotkey_animations", True) else 0.0
                self._service.preview_wallpaper(active_path, pos=(0.5, 0.5), duration=anim_duration)
            return GLib.SOURCE_REMOVE

        self._preview_timer_id = GLib.timeout_add(60, _do_preview)

    def _commit_and_close(self):
        if self._preview_timer_id is not None:
            GLib.source_remove(self._preview_timer_id)
            self._preview_timer_id = None

        if self._wallpapers and 0 <= self._current_index < len(self._wallpapers):
            active_path = self._wallpapers[self._current_index]
            self._service.set_wallpaper(active_path, pos=(0.5, 0.5), is_hotkey=True)
            play_sound("confirm")

        self.close()

    def _cancel_and_close(self):
        if self._preview_timer_id is not None:
            GLib.source_remove(self._preview_timer_id)
            self._preview_timer_id = None

        if self._original_wallpaper and self._previewed_wallpaper != self._original_wallpaper:
            self._service.preview_wallpaper(self._original_wallpaper, pos=(0.5, 0.5), duration=0.3)

        self.close()

    def toggle(self, active_monitor=None):
        if self.is_visible():
            self._cancel_and_close()
        else:
            self.open(active_monitor)

    def open(self, active_monitor=None):
        self._active_monitor = active_monitor
        if active_monitor is not None:
            try:
                display = Gdk.Display.get_default()
                for i in range(display.get_n_monitors()):
                    if display.get_monitor(i) == active_monitor:
                        self.set_monitor(i)
                        break
            except Exception as e:
                logger.debug(f"[WallpaperWheel] Failed to set monitor: {e}")

        self._reload_wallpapers()
        self.show_all()
        GtkLayerShell.set_keyboard_interactivity(self, True)
        if self._blur_ctx is None:
            self._blur_ctx = enable_blur(self)

    def close(self):
        if self._blur_ctx is not None:
            try:
                disable_blur(self)
            except Exception:
                pass
            self._blur_ctx = None
        self.hide()
        GtkLayerShell.set_keyboard_interactivity(self, False)


# =============================================================================
# 5. Coverflow Window (3D Horizontal Deck Switcher)
# =============================================================================

class WallpaperCoverflowWindow(Window):
    def __init__(self, **kwargs):
        self._service = WallpaperService.get_instance()
        self._wallpapers: list[str] = []
        self._current_index: int = 0
        self._original_wallpaper: str = ""
        self._previewed_wallpaper: str = ""
        self._executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="CoverflowPool")
        self._preview_timer_id: int | None = None
        self._blur_ctx = None
        self._active_monitor = None

        self._deck_fixed = Gtk.Fixed()
        self._deck_fixed.set_size_request(1140, 320)

        self._slot_offsets = [-3, -2, -1, 0, 1, 2, 3]
        self._slot_specs = [
            {"w": 140, "h": 79,  "x": 15,  "y": 120, "opacity": 0.35},
            {"w": 190, "h": 107, "x": 115, "y": 105, "opacity": 0.55},
            {"w": 250, "h": 140, "x": 235, "y": 88,  "opacity": 0.82},
            {"w": 340, "h": 191, "x": 400, "y": 62,  "opacity": 1.00},  # Center
            {"w": 250, "h": 140, "x": 655, "y": 88,  "opacity": 0.82},
            {"w": 190, "h": 107, "x": 835, "y": 105, "opacity": 0.55},
            {"w": 140, "h": 79,  "x": 985, "y": 120, "opacity": 0.35},
        ]

        self._card_events: list[EventBox] = [None] * 7
        self._card_images: list[Image] = [None] * 7

        z_order = [0, 6, 1, 5, 2, 4, 3]
        for slot_idx in z_order:
            spec = self._slot_specs[slot_idx]
            offset = self._slot_offsets[slot_idx]

            img = Image(style_classes=["wallpaper-card-img"])
            clip = ClippingBox(
                style_classes=["wallpaper-card-clip"],
                children=[img],
            )
            clip.set_size_request(spec["w"], spec["h"])

            card_box = Box(
                orientation="v",
                style_classes=["wallpaper-coverflow-center-card"] if offset == 0 else ["wallpaper-coverflow-side-card"],
                children=[clip],
            )
            card_box.set_opacity(spec["opacity"])

            ev = EventBox(child=card_box)
            if offset == 0:
                ev.connect("button-press-event", lambda *_: self._commit_and_close())
            else:
                ev.connect("button-press-event", lambda _, off=offset: self._navigate_step(off))

            self._card_events[slot_idx] = ev
            self._card_images[slot_idx] = img
            self._deck_fixed.put(ev, spec["x"], spec["y"])

        self._title_label = Label(
            label="",
            style="font-size: 16px; font-weight: 700; color: var(--primary);",
            ellipsize="end",
            max_chars_width=26,
            h_align="center",
        )
        self._hint_label = Label(
            label="Click Center or Enter to Apply  •  Scroll or Arrows to Slide  •  Esc to Close",
            style="font-size: 11px; opacity: 0.6; margin-top: 3px;",
            h_align="center",
        )

        info_pill = Box(
            orientation="v",
            spacing=2,
            h_align="center",
            v_align="center",
            style_classes=["wallpaper-coverflow-info-pill"],
            children=[self._title_label, self._hint_label],
        )

        deck_wrapper = Box(
            orientation="v",
            spacing=20,
            h_align="center",
            v_align="center",
            children=[self._deck_fixed, info_pill],
        )

        self._backdrop = EventBox(
            style_classes=["wallpaper-coverflow-backdrop"],
            h_expand=True,
            v_expand=True,
            child=deck_wrapper,
        )
        self._backdrop.connect("button-press-event", self._on_backdrop_clicked)
        self._backdrop.connect("scroll-event", self._on_mouse_scroll)

        super().__init__(
            layer="top",
            anchor="top bottom left right",
            keyboard_mode="none",
            title="agility-shell-wallpaper-coverflow",
            style_classes=["wallpaper-coverflow-window"],
            visible=False,
            child=self._backdrop,
            **kwargs,
        )
        GtkLayerShell.set_exclusive_zone(self, -1)
        self.connect("key-press-event", self._on_key_press)
        self.connect("focus-out-event", self._on_focus_out)

    def _on_focus_out(self, widget, event):
        if self.is_visible():
            self._cancel_and_close()
        return False

    def _on_backdrop_clicked(self, widget, event: Gdk.EventButton):
        if event.button == 1:
            alloc = self._deck_fixed.get_allocation()
            coords = self._deck_fixed.translate_coordinates(self, 0, 0)
            if coords:
                wx, wy = coords
                if not (wx <= event.x <= wx + alloc.width and wy <= event.y <= wy + alloc.height + 80):
                    self._cancel_and_close()
                    return True
            else:
                self._cancel_and_close()
                return True
        return False

    def _on_key_press(self, widget, event: Gdk.EventKey):
        keyval = event.keyval
        if keyval in (Gdk.KEY_Left, Gdk.KEY_Up, Gdk.KEY_h, Gdk.KEY_H, Gdk.KEY_k, Gdk.KEY_K):
            self._navigate_step(-1)
            return True
        elif keyval in (Gdk.KEY_Right, Gdk.KEY_Down, Gdk.KEY_l, Gdk.KEY_L, Gdk.KEY_j, Gdk.KEY_J):
            self._navigate_step(+1)
            return True
        elif keyval in (Gdk.KEY_Return, Gdk.KEY_KP_Enter, Gdk.KEY_space):
            self._commit_and_close()
            return True
        elif keyval in (Gdk.KEY_r, Gdk.KEY_R):
            self._shuffle_random()
            return True
        elif keyval == Gdk.KEY_Escape:
            self._cancel_and_close()
            return True
        return False

    def _on_mouse_scroll(self, widget, event: Gdk.EventScroll):
        if event.direction == Gdk.ScrollDirection.UP or event.delta_y < 0:
            self._navigate_step(-1)
            return True
        elif event.direction == Gdk.ScrollDirection.DOWN or event.delta_y > 0:
            self._navigate_step(+1)
            return True
        elif event.direction == Gdk.ScrollDirection.SMOOTH:
            if event.delta_y < 0 or event.delta_x < 0:
                self._navigate_step(-1)
                return True
            elif event.delta_y > 0 or event.delta_x > 0:
                self._navigate_step(+1)
                return True
        return False

    def _reload_wallpapers(self):
        self._wallpapers = self._service.get_all_wallpapers()
        current_path = self._service.wallpaper_path
        self._original_wallpaper = current_path
        self._previewed_wallpaper = current_path

        if current_path in self._wallpapers:
            self._current_index = self._wallpapers.index(current_path)
        elif self._wallpapers:
            self._current_index = 0

        self._render_deck(trigger_preview=False)

    def _render_deck(self, trigger_preview: bool = True):
        if not self._wallpapers:
            return

        N = len(self._wallpapers)
        active_path = self._wallpapers[self._current_index]

        raw_name = os.path.splitext(os.path.basename(active_path))[0]
        self._title_label.set_label(raw_name.replace("-", " ").replace("_", " ").lower())

        for slot_idx in range(7):
            offset = self._slot_offsets[slot_idx]
            spec = self._slot_specs[slot_idx]
            idx = (self._current_index + offset) % N
            path = self._wallpapers[idx]
            self._load_image_async(path, spec["w"], spec["h"], self._card_images[slot_idx])

        if trigger_preview:
            self._schedule_live_preview()

    def _load_image_async(self, path: str, target_w: int, target_h: int, target_img: Image):
        ref_img = weakref.ref(target_img)
        def work():
            cache_path = _generate_thumb_to_cache(path)
            if not cache_path:
                return
            try:
                pix = GdkPixbuf.Pixbuf.new_from_file_at_scale(str(cache_path), target_w, target_h, False)
                def apply():
                    img = ref_img()
                    if img is not None:
                        img.set_from_pixbuf(pix)
                    return GLib.SOURCE_REMOVE
                GLib.idle_add(apply)
            except Exception:
                pass
        self._executor.submit(work)

    def _navigate_step(self, delta: int):
        if not self._wallpapers:
            return
        N = len(self._wallpapers)
        self._current_index = (self._current_index + delta) % N
        self._render_deck(trigger_preview=True)

    def _shuffle_random(self):
        if not self._wallpapers:
            return
        import random
        candidates = [i for i in range(len(self._wallpapers)) if i != self._current_index]
        self._current_index = random.choice(candidates) if candidates else 0
        self._render_deck(trigger_preview=True)

    def _schedule_live_preview(self):
        if self._preview_timer_id is not None:
            GLib.source_remove(self._preview_timer_id)
            self._preview_timer_id = None

        def _do_preview():
            self._preview_timer_id = None
            if 0 <= self._current_index < len(self._wallpapers):
                active_path = self._wallpapers[self._current_index]
                self._previewed_wallpaper = active_path
                anim_duration = 0.4 if getattr(user_options.wallpaper, "hotkey_animations", True) else 0.0
                self._service.preview_wallpaper(active_path, pos=(0.5, 0.5), duration=anim_duration)
            return GLib.SOURCE_REMOVE

        self._preview_timer_id = GLib.timeout_add(60, _do_preview)

    def _commit_and_close(self):
        if self._preview_timer_id is not None:
            GLib.source_remove(self._preview_timer_id)
            self._preview_timer_id = None

        if self._wallpapers and 0 <= self._current_index < len(self._wallpapers):
            active_path = self._wallpapers[self._current_index]
            self._service.set_wallpaper(active_path, pos=(0.5, 0.5), is_hotkey=True)
            play_sound("confirm")

        self.close()

    def _cancel_and_close(self):
        if self._preview_timer_id is not None:
            GLib.source_remove(self._preview_timer_id)
            self._preview_timer_id = None

        if self._original_wallpaper and self._previewed_wallpaper != self._original_wallpaper:
            self._service.preview_wallpaper(self._original_wallpaper, pos=(0.5, 0.5), duration=0.3)

        self.close()

    def toggle(self, active_monitor=None):
        if self.is_visible():
            self._cancel_and_close()
        else:
            self.open(active_monitor)

    def open(self, active_monitor=None):
        self._active_monitor = active_monitor
        if active_monitor is not None:
            try:
                display = Gdk.Display.get_default()
                for i in range(display.get_n_monitors()):
                    if display.get_monitor(i) == active_monitor:
                        self.set_monitor(i)
                        break
            except Exception as e:
                logger.debug(f"[WallpaperCoverflow] Failed to set monitor: {e}")

        self._reload_wallpapers()
        self.show_all()
        GtkLayerShell.set_keyboard_interactivity(self, True)
        if self._blur_ctx is None:
            self._blur_ctx = enable_blur(self)

    def close(self):
        if self._blur_ctx is not None:
            try:
                disable_blur(self)
            except Exception:
                pass
            self._blur_ctx = None
        self.hide()
        GtkLayerShell.set_keyboard_interactivity(self, False)


# =============================================================================
# Unified WallpaperDrawer Facade Controller
# =============================================================================

class WallpaperDrawer:
    def __init__(self, **kwargs):
        self._kwargs = kwargs
        self._windows: dict[str, Window] = {}

    def _get_window(self, style: str) -> Window:
        if style not in self._windows:
            if style == "stairs":
                self._windows[style] = WallpaperStairsWindow(**self._kwargs)
            elif style == "mesh":
                self._windows[style] = WallpaperMeshWindow(**self._kwargs)
            elif style == "wheel":
                self._windows[style] = WallpaperWheelWindow(**self._kwargs)
            elif style == "coverflow":
                self._windows[style] = WallpaperCoverflowWindow(**self._kwargs)
            else:
                self._windows[style] = WallpaperDockWindow(**self._kwargs)
        return self._windows[style]

    def _get_active_subwindow(self) -> Window:
        style = getattr(user_options.wallpaper, "switcher_style", "dock")
        return self._get_window(style)

    def is_visible(self) -> bool:
        return any(win.is_visible() for win in self._windows.values())

    def toggle(self, active_monitor=None):
        if self.is_visible():
            self.close()
        else:
            self.open(active_monitor)

    def open(self, active_monitor=None):
        self.close()
        win = self._get_active_subwindow()
        win.open(active_monitor)

    def close(self):
        for win in list(self._windows.values()):
            if win.is_visible():
                win.close()
