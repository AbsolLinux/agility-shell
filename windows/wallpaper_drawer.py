import os
import gc
import hashlib
import weakref
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, Future

from fabric.widgets.wayland import WaylandWindow as Window
from fabric.widgets.box import Box
from fabric.widgets.label import Label
from fabric.widgets.image import Image
from fabric.widgets.eventbox import EventBox
from fabric.widgets.scrolledwindow import ScrolledWindow
from gi.repository import Gtk, Gdk, GdkPixbuf, GLib, GtkLayerShell
from PIL import Image as PilImage
from loguru import logger

from snippets import ClippingBox, AppletReveal, Animator
from services.wallpaper import WallpaperService
from utils.sounds import play_sound

THUMB_CACHE_DIR = Path.home() / ".cache" / "agility-shell" / "thumbnails"
CARD_WIDTH = 168
CARD_HEIGHT = 95
ACTIVE_WIDTH = 200
ACTIVE_HEIGHT = 112
SPACING = 16
SLOT_WIDTH = CARD_WIDTH + SPACING  # 184px
NUM_SLOTS = 7
CENTER_SLOT = 3  # Slot 3 is the dead center slot (0..6)
BASE_OFFSET = SLOT_WIDTH  # ScrolledWindow scroll offset so Slot 1..5 are in view


def _fast_cache_key(path: str) -> str:
    try:
        stat = os.stat(path)
        raw = f"{path}:{stat.st_mtime}:{stat.st_size}:caelestia_v2"
    except Exception:
        raw = f"{path}:caelestia_v2"
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
                    img.draft("RGB", (ACTIVE_WIDTH * 2, ACTIVE_HEIGHT * 2))
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

                thumb = img.resize((ACTIVE_WIDTH * 2, ACTIVE_HEIGHT * 2), PilImage.Resampling.LANCZOS)
                thumb.save(cache_path, "JPEG", quality=85, optimize=True)
                del thumb
            gc.collect()
        return cache_path
    except Exception as e:
        logger.debug(f"[WallpaperDrawer] Failed to generate thumb for {file_path}: {e}")
        return None


class WallpaperSlotCard(EventBox):
    def __init__(self, slot_index: int, on_slot_clicked):
        self.slot_index = slot_index
        self.on_slot_clicked = on_slot_clicked
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

        w = ACTIVE_WIDTH if self._is_active else CARD_WIDTH
        h = ACTIVE_HEIGHT if self._is_active else CARD_HEIGHT
        self._clip_box.set_size_request(w, h)

        self._label = Label(
            label="",
            style_classes=["wallpaper-card-label"] + (["active"] if self._is_active else []),
            ellipsize="end",
            max_chars_width=18,
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
        self.set_size_request(SLOT_WIDTH, ACTIVE_HEIGHT + 36)
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
            w, h = ACTIVE_WIDTH, ACTIVE_HEIGHT
        else:
            self.box.remove_style_class("active")
            self.box.add_style_class("inactive")
            self._label.remove_style_class("active")
            w, h = CARD_WIDTH, CARD_HEIGHT

        self._clip_box.set_size_request(w, h)

        # Check local pixbuf cache
        if path in self._pixbuf_cache:
            pix = self._pixbuf_cache[path]
            scaled = pix if is_active else pix.scale_simple(CARD_WIDTH, CARD_HEIGHT, GdkPixbuf.InterpType.BILINEAR)
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
                pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_scale(str(cache_path), ACTIVE_WIDTH, ACTIVE_HEIGHT, False)
            except Exception:
                return

            def apply():
                widget = ref()
                if widget is None or gen != widget._load_generation:
                    return GLib.SOURCE_REMOVE
                widget._pixbuf_cache[path] = pixbuf
                scaled = pixbuf if widget._is_active else pixbuf.scale_simple(CARD_WIDTH, CARD_HEIGHT, GdkPixbuf.InterpType.BILINEAR)
                widget._image.set_from_pixbuf(scaled)
                return GLib.SOURCE_REMOVE

            GLib.idle_add(apply)

        self._future = executor.submit(work)

    def _on_button_press(self, widget, event: Gdk.EventButton):
        if event.button == 1:
            self.on_slot_clicked(self.slot_index, self.path)
            return True
        return False


class WallpaperDrawer(Window):
    def __init__(self, **kwargs):
        self._service = WallpaperService.get_instance()
        self._wallpapers: list[str] = []
        self._current_index: int = 0
        self._original_wallpaper: str = ""
        self._previewed_wallpaper: str = ""
        self._executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="CaelestiaPool")
        self._preview_timer_id: int | None = None
        self._animator: Animator | None = None
        self._is_animating: bool = False
        self._active_monitor = None

        # Carousel box holding 7 slots
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
            )
            self._slot_cards.append(card)
            self._carousel_box.add(card)

        # Viewport displays exactly 5 visible slots
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

        # Caelestia dock container
        self._dock_container = Box(
            orientation="h",
            h_align="center",
            v_align="center",
            style_classes=["wallpaper-drawer-dock"],
            children=[self._scroller],
        )

        # Upward reveal
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
            keyboard_mode="exclusive",
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
        cfg_wallpapers = os.path.expanduser("~/.config/agility-shell/wallpapers")
        repo_wallpapers = os.path.join(os.path.dirname(__file__), "../wallpapers")
        wallpapers_dir = cfg_wallpapers if os.path.isdir(cfg_wallpapers) else repo_wallpapers

        valid_exts = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
        files = []
        if os.path.isdir(wallpapers_dir):
            for f in sorted(os.listdir(wallpapers_dir)):
                ext = os.path.splitext(f)[1].lower()
                if ext in valid_exts:
                    files.append(os.path.join(wallpapers_dir, f))

        self._wallpapers = files
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
            rel = i - CENTER_SLOT  # -3, -2, -1, 0, 1, 2, 3
            idx = (self._current_index + rel) % N
            path = self._wallpapers[idx]
            is_active = (i == CENTER_SLOT)
            self._slot_cards[i].bind_wallpaper(path, is_active, self._executor)

        if trigger_preview:
            self._schedule_live_preview()

    def _navigate_step(self, delta: int):
        if not self._wallpapers:
            return

        # If already animating, complete previous step immediately
        if self._animator:
            self._animator.pause()
            self._animator = None
            self._scroller.get_hadjustment().set_value(BASE_OFFSET)

        N = len(self._wallpapers)
        target_index = (self._current_index + delta) % N

        # Calculate smooth slide offset
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
                self._service.preview_wallpaper(active_path, pos=(0.5, 0.92), duration=0.5)
            return GLib.SOURCE_REMOVE

        self._preview_timer_id = GLib.timeout_add(60, _do_preview)

    def _commit_and_close(self):
        if self._preview_timer_id is not None:
            GLib.source_remove(self._preview_timer_id)
            self._preview_timer_id = None

        if self._wallpapers and 0 <= self._current_index < len(self._wallpapers):
            active_path = self._wallpapers[self._current_index]
            self._service.set_wallpaper(active_path, pos=(0.5, 0.92))
            play_sound("confirm")

        self.close()

    def _cancel_and_close(self):
        if self._preview_timer_id is not None:
            GLib.source_remove(self._preview_timer_id)
            self._preview_timer_id = None

        if self._original_wallpaper and self._previewed_wallpaper != self._original_wallpaper:
            self._service.preview_wallpaper(self._original_wallpaper, pos=(0.5, 0.92), duration=0.4)

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
                logger.debug(f"[WallpaperDrawer] Failed to set monitor: {e}")

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
