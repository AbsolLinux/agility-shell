import os
import gc
import hashlib
import weakref
import threading

from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, Future

from fabric.utils import monitor_file
from fabric.widgets.box import Box
from fabric.widgets.button import Button
from fabric.widgets.image import Image
from fabric.widgets.label import Label
from fabric.widgets.centerbox import CenterBox
from gi.repository import GdkPixbuf, GLib, Gio
from snippets import Icon, ClippingScrolledWindow, ClippingBox
from services.themes import wallpaper
from user_options import user_options
from PIL import Image as PilImage

THUMBNAIL_SIZE = 174
SUPPORTED_EXTS = (".jpg", ".jpeg", ".png", ".webp", ".bmp")

PREVIEW_WIDTH  = 918
PREVIEW_HEIGHT = 546

WALLPAPER_TRANSITIONS: list[tuple[str, str, str]] = [
    ("grow",   "Grow",   "corners-out-duotone"),
    ("fade",   "Fade",   "sparkle-duotone"),
    ("wipe",   "Wipe",   "line-segment-duotone"),
    ("wave",   "Wave",   "waves-duotone"),
    ("left",   "Left",   "arrow-left-duotone"),
    ("right",  "Right",  "arrow-right-duotone"),
    ("top",    "Up",     "arrow-up-duotone"),
    ("bottom", "Down",   "arrow-down-duotone"),
    ("outer",  "Shrink", "corners-in-duotone"),
    ("random", "Random", "shuffle-duotone"),
]

THUMB_CACHE_DIR   = Path.home() / ".cache" / "agility-shell" / "thumbnails"
PREVIEW_CACHE_DIR = Path.home() / ".cache" / "agility-shell" / "previews"

def _fast_cache_key(path: str) -> str:
    stat = os.stat(path)
    raw  = f"{path}:{stat.st_mtime}:{stat.st_size}"
    return hashlib.sha256(raw.encode()).hexdigest()

def _get_thumb_cache_path(file_path: str) -> Path:
    return THUMB_CACHE_DIR / f"{_fast_cache_key(file_path)}.jpg"

def _get_preview_cache_path(file_path: str) -> Path:
    return PREVIEW_CACHE_DIR / f"{_fast_cache_key(file_path)}.jpg"

def _generate_thumb_to_cache(file_path: str, size: int) -> Path | None:
    try:
        THUMB_CACHE_DIR.mkdir(parents=True, exist_ok=True)
        cache_path = _get_thumb_cache_path(file_path)
        if not cache_path.exists():
            with PilImage.open(file_path) as img:

                if hasattr(img, "draft"):
                    img.draft("RGB", (size * 2, size * 2))
                if img.mode != "RGB":
                    img = img.convert("RGB")
                w, h  = img.size
                side  = min(w, h)
                left  = (w - side) // 2
                top   = (h - side) // 2
                thumb = img.crop((left, top, left + side, top + side)).resize(
                    (size, size), PilImage.Resampling.LANCZOS
                )
                thumb.save(cache_path, "JPEG", quality=85, optimize=True)
                del thumb
            gc.collect()
        return cache_path
    except Exception:
        return None

def _generate_preview_to_cache(file_path: str) -> Path | None:
    try:
        PREVIEW_CACHE_DIR.mkdir(parents=True, exist_ok=True)
        cache_path = _get_preview_cache_path(file_path)
        if not cache_path.exists():
            with PilImage.open(file_path) as img:
                img.draft("RGB", (PREVIEW_WIDTH, PREVIEW_HEIGHT))
                if img.mode != "RGB":
                    img = img.convert("RGB")
                img = img.resize((PREVIEW_WIDTH, PREVIEW_HEIGHT), PilImage.Resampling.LANCZOS)
                img.save(cache_path, "JPEG", quality=88, optimize=True)
            gc.collect()
        return cache_path
    except Exception:
        return None
    
def _load_pixbuf_from_path(cache_path: Path):
    try:
        return GdkPixbuf.Pixbuf.new_from_file(str(cache_path))
    except Exception:
        return None

class SelectorHeader(CenterBox):
    def __init__(self, h_stack, v_stack, left_icon_name, right_icon_name, h_target, v_target):
        super().__init__(
            h_expand=False,
            halign="center",
            start_children=Button(
                style_classes=["applet-misc-button"],
                child=Icon(icon_name=left_icon_name),
                on_pressed=lambda _: v_stack.set_visible_child_name(v_target),
            ),
            end_children=Button(
                style_classes=["applet-misc-button"],
                child=Icon(icon_name=right_icon_name),
                on_pressed=lambda _: h_stack.set_visible_child_name(h_target),
            ),
        )

class WallpaperThumb(Button):
    """
    Memory contract:
    - The executor work() closure captures only: path (str), size (int),
      generation (int), and a weakref to self.
    - self is never captured directly — if the widget is destroyed or unloaded
      before the job finishes, the weakref returns None and the result is dropped.
    - _future is tracked so unload() can cancel() before PIL even starts,
      avoiding wasted decode work on off-screen thumbs.
    """

    def __init__(self, path: str, on_select):
        self._path            = path
        self._loaded          = False
        self._load_generation = 0
        self._future: Future | None = None

        self.image = Image()
        self.box = ClippingBox(
            style_classes=["dash-grid-selector-preview"],
            children=self.image,
        )
        super().__init__(
            style_classes=["wallpaper-thumb"],
            child=self.box,
            on_clicked=lambda _: on_select(self),
        )
        self.set_size_request(THUMBNAIL_SIZE, THUMBNAIL_SIZE)

    def load(self, executor: ThreadPoolExecutor) -> None:
        if self._loaded:
            return
        self._loaded = True
        self._load_generation += 1

        path = self._path
        gen  = self._load_generation
        ref  = weakref.ref(self)

        def work():
            cache_path = _generate_thumb_to_cache(path, THUMBNAIL_SIZE)
            if cache_path is None:
                return
            pixbuf = _load_pixbuf_from_path(cache_path)
            if pixbuf is None:
                return

            def apply():
                thumb = ref()
                if thumb is None:
                    return GLib.SOURCE_REMOVE
                if gen != thumb._load_generation:
                    return GLib.SOURCE_REMOVE
                thumb.image.set_from_pixbuf(pixbuf)
                return GLib.SOURCE_REMOVE

            GLib.idle_add(apply)

        self._future = executor.submit(work)

    def unload(self) -> None:
        self._loaded          = False
        self._load_generation += 1

        if self._future is not None:
            self._future.cancel()
            self._future = None

        self.image.set_from_pixbuf(None)

    @property
    def path(self) -> str:
        return self._path

    def set_active(self, active: bool) -> None:
        if active:
            self.add_style_class("active")
        else:
            self.remove_style_class("active")

class DashSelectorPage(Box):
    def __init__(self):
        self._preview_box = ClippingBox(
            style_classes=["dash-grid-selector-preview"],
            orientation="v",
            h_align="center",
            v_align="start",
            h_expand=False,
        )
        self._thumb_strip = Box(
            orientation="v",
            spacing=12,
            style_classes=["wallpaper-thumb-strip"],
        )
        self._scroll = ClippingScrolledWindow(
            v_expand=True,
            style_classes=["grid-selector-thumb-scroll"],
            max_content_size=(174, 630),
            fade_distance=60,
            child=self._thumb_strip,
            overlay_scroll=True,
            kinetic_scroll=True,
        )
        self._preview_column = Box(
            orientation="v",
            spacing=10,
            h_align="center",
            v_align="start",
            children=[self._preview_box],
        )
        super().__init__(
            orientation="v",
            v_align="start",
            h_align="center",
            h_expand=True,
            v_expand=True,
            spacing=12,
            children=[
                Box(
                    orientation="h",
                    spacing=12,
                    h_expand=True,
                    v_expand=True,
                    children=[self._preview_column, self._scroll],
                ),
            ],
        )

class DashWallpaperPage(DashSelectorPage):
    """
    Memory contract
    - All preview and thumb loads use weakrefs + generation counters.
    - No closure ever captures self directly.
    - In-flight futures are cancelled on hide/unload so no stale pixbufs
    - can land on the main thread after the page is hidden.
    """

    def __init__(self):
        super().__init__()

        self._executor                    = ThreadPoolExecutor(max_workers=1)
        self._active_thumb: WallpaperThumb | None = None
        self._preview_generation          = 0
        self._preview_future: Future | None = None

        self._preview_image = Image()
        self._preview_box.add(self._preview_image)

        # Transition Selector Bar
        self._transition_buttons: dict[str, Button] = {}
        self._trans_row = Box(
            orientation="h",
            spacing=4,
            style_classes=["option-selection-container"],
            h_align="center",
        )

        self._add_trans_btn = Button(
            child=Box(
                orientation="h",
                spacing=2,
                children=[
                    Icon(icon_name="plus-duotone", icon_size=13),
                    Label(label="Add", style="font-size: 11px; font-weight: 500;"),
                ],
            ),
            style_classes=["option-selection-button"],
            on_clicked=lambda *_: self._toggle_custom_creator(),
        )

        self._controls_box = Box(
            orientation="h",
            spacing=10,
            h_align="center",
            v_align="center",
            children=[
                Label(label="Transition:", style="font-size: 12px; opacity: 0.7; font-weight: 600;"),
                self._trans_row,
                self._add_trans_btn,
            ],
        )

        # Custom Animation Creator Card
        self._creator_card = self._build_custom_creator()
        self._creator_card.set_no_show_all(True)
        self._creator_card.hide()

        self._preview_column.add(self._controls_box)
        self._preview_column.add(self._creator_card)

        self._rebuild_transition_buttons()

        self.connect("realize", self._on_realize)
        self._load_wallpapers()

        if wallpaper.wallpaper_path:
            self._restore_active(wallpaper.wallpaper_path)

        wallpaper.connect("wallpaper-changed", self._on_wallpaper_changed)

    def _build_custom_creator(self) -> Box:
        from fabric.widgets.entry import Entry
        from snippets import FlatScale

        self._custom_name_entry = Entry(
            placeholder="e.g. 90-Deg-Wipe",
            style_classes=["dash-search-entry"],
            style="min-width: 140px; font-size: 11px; padding: 4px 8px;",
        )

        self._custom_base_type = "wipe"
        self._custom_angle = "90"
        self._custom_duration = 1.5

        types = ["wipe", "wave", "fade", "grow", "outer", "left", "right", "top", "bottom"]
        self._type_btns = {}
        types_box = Box(orientation="h", spacing=2, style_classes=["option-selection-container"])
        for t in types:
            btn = Button(
                child=Label(label=t.capitalize(), style="font-size: 10px; font-weight: 500;"),
                style_classes=["option-selection-button"] + (["active"] if t == self._custom_base_type else []),
                on_clicked=lambda _, k=t: self._set_creator_base_type(k),
            )
            self._type_btns[t] = btn
            types_box.add(btn)

        angles = [("45°", "45"), ("90°", "90"), ("135°", "135"), ("180°", "180")]
        self._angle_btns = {}
        angles_box = Box(orientation="h", spacing=2, style_classes=["option-selection-container"])
        for a_label, a_val in angles:
            btn = Button(
                child=Label(label=a_label, style="font-size: 10px; font-weight: 500;"),
                style_classes=["option-selection-button"] + (["active"] if a_val == self._custom_angle else []),
                on_clicked=lambda _, k=a_val: self._set_creator_angle(k),
            )
            self._angle_btns[a_val] = btn
            angles_box.add(btn)

        save_btn = Button(
            child=Label(label="Save Animation", style="font-size: 11px; font-weight: 600;"),
            style_classes=["option-selection-button", "active"],
            on_clicked=lambda *_: self._save_custom_animation(),
        )
        cancel_btn = Button(
            child=Label(label="Cancel", style="font-size: 11px; font-weight: 500;"),
            style_classes=["option-selection-button"],
            on_clicked=lambda *_: self._toggle_custom_creator(force_close=True),
        )

        row1 = Box(
            orientation="h",
            spacing=8,
            h_align="center",
            children=[
                Label(label="Name:", style="font-size: 11px; font-weight: 600; opacity: 0.8;"),
                self._custom_name_entry,
                Label(label="Effect:", style="font-size: 11px; font-weight: 600; opacity: 0.8;"),
                types_box,
            ],
        )

        row2 = Box(
            orientation="h",
            spacing=8,
            h_align="center",
            children=[
                Label(label="Angle:", style="font-size: 11px; font-weight: 600; opacity: 0.8;"),
                angles_box,
                save_btn,
                cancel_btn,
            ],
        )

        card = Box(
            orientation="v",
            spacing=8,
            style_classes=["desktop-system-module"],
            style="padding: 8px 12px; border-radius: 12px;",
            h_align="center",
            children=[row1, row2],
        )
        return card

    def _set_creator_base_type(self, t: str):
        self._custom_base_type = t
        for k, btn in self._type_btns.items():
            if k == t:
                btn.add_style_class("active")
            else:
                btn.remove_style_class("active")

    def _set_creator_angle(self, a: str):
        self._custom_angle = a
        for k, btn in self._angle_btns.items():
            if k == a:
                btn.add_style_class("active")
            else:
                btn.remove_style_class("active")

    def _toggle_custom_creator(self, force_close: bool = False):
        if force_close or self._creator_card.get_visible():
            self._creator_card.hide()
        else:
            self._creator_card.show_all()

    def _save_custom_animation(self):
        name = self._custom_name_entry.get_text().strip()
        if not name:
            name = f"Custom {self._custom_base_type.capitalize()}"

        cust = {
            "name": name,
            "type": self._custom_base_type,
            "angle": self._custom_angle,
            "duration": 1.5,
            "bezier": ".43,1.19,1,.4",
        }

        custom_list = list(getattr(user_options.wallpaper, "custom_transitions", []))
        custom_list = [c for c in custom_list if c.get("name") != name]
        custom_list.append(cust)
        user_options.wallpaper.custom_transitions = custom_list

        pool = list(getattr(user_options.wallpaper, "enabled_transitions", []))
        if name not in pool:
            pool.append(name)
        user_options.wallpaper.enabled_transitions = pool
        user_options.wallpaper.transition_type = name
        user_options.save()

        self._toggle_custom_creator(force_close=True)
        self._rebuild_transition_buttons()
        self._on_transition_selected(name)

    def _rebuild_transition_buttons(self):
        for child in self._trans_row.get_children():
            self._trans_row.remove(child)
        self._transition_buttons.clear()

        current_trans = getattr(user_options.wallpaper, "transition_type", "grow")
        enabled_pool = set(getattr(user_options.wallpaper, "enabled_transitions", []))
        customs = getattr(user_options.wallpaper, "custom_transitions", [])

        all_items = list(WALLPAPER_TRANSITIONS)
        for c in customs:
            cname = c.get("name", "Custom")
            all_items.append((cname, cname, "magic-wand-duotone"))

        for t_key, t_label, t_icon in all_items:
            in_pool = t_key in enabled_pool or t_key == "random"
            btn = Button(
                style_classes=["option-selection-button"]
                + (["active"] if t_key == current_trans else [])
                + ([] if in_pool else ["dimmed"]),
                child=Box(
                    orientation="h",
                    spacing=4,
                    children=[
                        Icon(icon_name=t_icon, icon_size=13),
                        Label(label=t_label, style="font-size: 11px; font-weight: 500;"),
                    ],
                ),
            )
            btn.connect("clicked", lambda _, k=t_key: self._on_transition_selected(k))
            btn.connect("button-press-event", lambda _, ev, k=t_key, l=t_label: self._on_trans_btn_press(ev, k, l))
            self._transition_buttons[t_key] = btn
            self._trans_row.add(btn)
        self._trans_row.show_all()

    def _on_trans_btn_press(self, event, t_key: str, t_label: str):
        if event.button == 3:  # Right Click -> Context Menu for inclusion/exclusion
            menu = Gtk.Menu()

            enabled_pool = list(getattr(user_options.wallpaper, "enabled_transitions", []))
            is_enabled = t_key in enabled_pool

            if t_key != "random":
                toggle_lbl = f"✓ Included in Random Pool" if is_enabled else f"✗ Excluded from Random Pool"
                toggle_item = Gtk.MenuItem(label=toggle_lbl)
                toggle_item.connect("activate", lambda *_: self._toggle_trans_in_pool(t_key))
                menu.append(toggle_item)

            select_item = Gtk.MenuItem(label=f"Use '{t_label}' Now")
            select_item.connect("activate", lambda *_: self._on_transition_selected(t_key))
            menu.append(select_item)

            custom_names = [c.get("name") for c in getattr(user_options.wallpaper, "custom_transitions", [])]
            if t_key in custom_names:
                menu.append(Gtk.SeparatorMenuItem())
                del_item = Gtk.MenuItem(label="Delete Custom Animation")
                del_item.connect("activate", lambda *_: self._delete_custom_transition(t_key))
                menu.append(del_item)

            menu.show_all()
            menu.popup_at_pointer(event)
            return True
        return False

    def _toggle_trans_in_pool(self, t_key: str):
        pool = list(getattr(user_options.wallpaper, "enabled_transitions", []))
        if t_key in pool:
            pool.remove(t_key)
        else:
            pool.append(t_key)
        if not pool:
            pool = ["grow"]
        user_options.wallpaper.enabled_transitions = pool
        user_options.save()
        self._rebuild_transition_buttons()

    def _delete_custom_transition(self, t_key: str):
        customs = [c for c in getattr(user_options.wallpaper, "custom_transitions", []) if c.get("name") != t_key]
        user_options.wallpaper.custom_transitions = customs
        pool = [k for k in getattr(user_options.wallpaper, "enabled_transitions", []) if k != t_key]
        user_options.wallpaper.enabled_transitions = pool
        if user_options.wallpaper.transition_type == t_key:
            user_options.wallpaper.transition_type = "random"
        user_options.save()
        self._rebuild_transition_buttons()

    def _on_transition_selected(self, transition_type: str) -> None:
        user_options.wallpaper.transition_type = transition_type
        user_options.save()
        for k, btn in self._transition_buttons.items():
            if k == transition_type:
                btn.add_style_class("active")
            else:
                btn.remove_style_class("active")
        if self._active_thumb:
            wallpaper.set_wallpaper(self._active_thumb.path, transition_type=transition_type)
        elif wallpaper.wallpaper_path:
            wallpaper.set_wallpaper(wallpaper.wallpaper_path, transition_type=transition_type)

    def _on_wallpaper_changed(self, service, path: str) -> None:
        GLib.idle_add(self._refresh_and_select, path)

    def _refresh_and_select(self, path: str) -> None:
        if self.is_visible():
            self._restore_active(path)
            self._update_preview(path)

    def _on_realize(self, *_) -> None:
        h_stack = self.get_parent()
        v_stack = h_stack.get_parent() if h_stack else None

        if v_stack:
            v_stack.connect("notify::visible-child", self._on_v_stack_switch)
        if h_stack:
            h_stack.connect("notify::visible-child", self._on_h_stack_switch)

        toplevel = self.get_toplevel()
        if toplevel:
            toplevel.connect("destroy", lambda *_: self._cleanup())

    def _on_v_stack_switch(self, stack, *_) -> None:
        if stack.get_visible_child() == self.get_parent():
            self._on_became_visible()
        else:
            self._on_became_hidden()

    def _on_h_stack_switch(self, stack, *_) -> None:
        if stack.get_visible_child() == self:
            self._on_became_visible()
        else:
            self._on_became_hidden()

    def _on_became_visible(self) -> None:
        if not self._thumb_strip.get_children():
            self._load_wallpapers()
            if wallpaper.wallpaper_path:
                self._restore_active(wallpaper.wallpaper_path)
        else:
            GLib.idle_add(self._on_scroll_changed, self._scroll.get_vadjustment())
            if self._active_thumb:
                self._update_preview(self._active_thumb.path)
            elif wallpaper.wallpaper_path:
                self._update_preview(wallpaper.wallpaper_path)

    def _on_became_hidden(self) -> None:
        self._unload_all_thumbs()

    def _cleanup(self) -> None:
        self._cancel_preview()
        self._unload_all_thumbs()
        self._preview_image.set_from_pixbuf(None)
        self._executor.shutdown(wait=False)
        if hasattr(self, "_walls_monitor"):
            self._walls_monitor.cancel()

    def _cancel_preview(self) -> None:
        if self._preview_future is not None:
            self._preview_future.cancel()
            self._preview_future = None

    def _unload_all_thumbs(self) -> None:
        self._cancel_preview()
        for thumb in self._thumb_strip.get_children():
            if isinstance(thumb, WallpaperThumb):
                thumb.unload()
        self._active_thumb = None
        self._preview_image.set_from_pixbuf(None)

    def _load_wallpapers(self) -> None:
        walls_dir = os.path.expanduser("~/.config/agility-shell/wallpapers")
        if not os.path.isdir(walls_dir):
            return

        def load():
            paths = sorted(
                os.path.join(walls_dir, f)
                for f in os.listdir(walls_dir)
                if f.lower().endswith(SUPPORTED_EXTS)
            )
            def apply():
                for path in paths:
                    thumb = WallpaperThumb(path, self._on_thumb_clicked)
                    self._thumb_strip.add(thumb)
                self._thumb_strip.show_all()
                adj = self._scroll.get_vadjustment()
                adj.connect("value-changed", self._on_scroll_changed)
                GLib.idle_add(self._on_scroll_changed, adj)
                self._walls_monitor = monitor_file(walls_dir)
                self._walls_monitor.connect("changed", self._on_dir_changed)
            GLib.idle_add(apply)

        threading.Thread(target=load, daemon=True).start()

    def _on_dir_changed(self, monitor, file, other_file, event_type) -> None:
        path = file.get_path()
        if not path.lower().endswith(SUPPORTED_EXTS):
            return
        if event_type == Gio.FileMonitorEvent.CREATED:
            GLib.idle_add(self._add_thumb, path)
        elif event_type == Gio.FileMonitorEvent.DELETED:
            GLib.idle_add(self._remove_thumb, path)

    def _on_scroll_changed(self, adj) -> None:
        visible_start = adj.get_value()
        visible_end   = visible_start + adj.get_page_size()
        buffer        = THUMBNAIL_SIZE * 2

        y = 0
        for thumb in self._thumb_strip.get_children():
            if not isinstance(thumb, WallpaperThumb):
                continue
            in_view = (
                y + THUMBNAIL_SIZE >= visible_start - buffer and
                y                  <= visible_end   + buffer
            )
            if in_view:
                thumb.load(self._executor)
            else:
                thumb.unload()
            y += THUMBNAIL_SIZE + 8

    def _on_thumb_clicked(self, thumb: WallpaperThumb) -> None:
        self._set_active(thumb)
        wallpaper.set_wallpaper(thumb.path, transition_type=user_options.wallpaper.transition_type)

    def _set_active(self, thumb: WallpaperThumb) -> None:
        if self._active_thumb:
            self._active_thumb.set_active(False)
        self._active_thumb = thumb
        thumb.set_active(True)
        self._update_preview(thumb.path)

    def _restore_active(self, path: str) -> None:
        self._update_preview(path)
        for thumb in self._thumb_strip.get_children():
            if isinstance(thumb, WallpaperThumb) and thumb.path == path:
                if self._active_thumb:
                    self._active_thumb.set_active(False)
                self._active_thumb = thumb
                thumb.set_active(True)
                return

    def _update_preview(self, path: str | None) -> None:
        self._cancel_preview()
        self._preview_generation += 1

        if path is None:
            return

        gen = self._preview_generation
        ref = weakref.ref(self)

        def load():
            cache_path = _generate_preview_to_cache(path)
            if cache_path is None:
                return
            pixbuf = _load_pixbuf_from_path(cache_path)
            if pixbuf is None:
                return

            def apply():
                page = ref()
                if page is None or gen != page._preview_generation:

                    return GLib.SOURCE_REMOVE
                page._preview_image.set_from_pixbuf(pixbuf)

                return GLib.SOURCE_REMOVE

            GLib.idle_add(apply)

        self._preview_future = self._executor.submit(load)

    def _add_thumb(self, path: str) -> None:
        existing = [
            t.path for t in self._thumb_strip.get_children()
            if isinstance(t, WallpaperThumb)
        ]
        if path in existing:
            return
        thumb     = WallpaperThumb(path, self._on_thumb_clicked)
        all_paths = sorted(existing + [path])
        index     = all_paths.index(path)
        self._thumb_strip.pack_start(thumb, False, False, 0)
        self._thumb_strip.reorder_child(thumb, index)
        thumb.show_all()
        thumb.load(self._executor)

    def _remove_thumb(self, path: str) -> None:
        for thumb in self._thumb_strip.get_children():
            if isinstance(thumb, WallpaperThumb) and thumb.path == path:
                if self._active_thumb == thumb:
                    self._active_thumb = None
                    self._preview_area.set_style("background-image: none;")
                thumb.destroy()
                break