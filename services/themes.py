import json
import os
import subprocess

from fabric.core.service import Service, Signal, Property
from gi.repository import GLib
from loguru import logger

from user_options import user_options
from .wallpaper import WallpaperService
from .templates import template_service, MATUGEN_CONFIG_CACHE

THEMES_DIR       = os.path.expanduser("~/.config/agility-shell/themes")
LIGHT_THEMES_DIR = os.path.join(THEMES_DIR, "light")
DARK_THEMES_DIR  = os.path.join(THEMES_DIR, "dark")
CACHE_THEME_PATH = os.path.expanduser("~/.cache/agility-shell/theme.json")

WALLPAPER_THEME = "Matugen"

wallpaper = WallpaperService().get_instance()

def opacity_to_hex(opacity: float) -> str:
    if not 0 <= opacity <= 1:
        raise ValueError("Opacity must be between 0 and 1")

    alpha = round(opacity * 255)
    return f"{alpha:02X}"

class ThemeService(Service):
    """
    Theming service for Fabric shell using matugen.

    Two modes per light/dark slot:
      • Theme file  → builds a colour JSON, writes to CACHE_THEME_PATH, runs:
                        matugen json <path> -m light|dark
      • Wallpaper   → theme name == WALLPAPER_THEME, runs:
                        matugen image <wallpaper> -m light|dark -t <scheme>

    Listens to the WallpaperService singleton so that wallpaper-mode themes
    re-apply automatically whenever the wallpaper changes.

    Usage:
        from services.theme_service import theme_service
        theme_service.toggle_dark()
        theme_service.set_dark_theme("forest")
        theme_service.set_accent("teal")
    """

    _instance: "ThemeService | None" = None

    @staticmethod
    def get_instance() -> "ThemeService":
        if ThemeService._instance is None:
            ThemeService._instance = ThemeService()
        return ThemeService._instance

    @Signal
    def theme_changed(self) -> None: ...

    @Signal
    def accent_changed(self) -> None: ...

    @Signal
    def mode_changed(self) -> None: ...

    @Property(bool, "read-write", default_value=True)
    def is_dark(self) -> bool:
        return self._is_dark

    @Property(str, "read-write", default_value="")
    def light_theme(self) -> str:
        return self._light_theme

    @Property(str, "read-write", default_value="")
    def dark_theme(self) -> str:
        return self._dark_theme

    @Property(str, "read-write", default_value="")
    def active_accent(self) -> str:
        return self._active_accent

    @Property(str, "read-write", default_value="")
    def scheme_type(self) -> str:
        return self._scheme_type

    @Property(object, "read-write")
    def available_accents(self) -> list[str]:
        return self._available_accents

    @Property(object, "read-write")
    def current_theme_data(self) -> dict | None:
        return self._current_theme_data

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self._is_dark: bool         = user_options.theme.is_dark
        self._light_theme: str      = user_options.theme.light_theme
        self._dark_theme: str       = user_options.theme.dark_theme
        self._active_accent: str    = user_options.theme.active_accent
        self._scheme_type: str      = user_options.theme.scheme_type
        self._current_theme_data: dict | None = None
        self._available_accents: list[str]    = []

        self._connect_wallpaper_service()

        self._load_current_theme()
        logger.info("[ThemeService] initialised")

    def _connect_wallpaper_service(self) -> None:
        try:
            wallpaper.connect("wallpaper-changed", self._on_wallpaper_changed)
            self._wallpaper_service = wallpaper
            logger.info("[ThemeService] connected to WallpaperService")
        except Exception as e:
            logger.warning(f"[ThemeService] could not connect to WallpaperService: {e}")
            self._wallpaper_service = None

    def toggle_dark_mode(self) -> None:
        self.apply_dark(not self._is_dark)

    def apply_dark(self, value: bool) -> None:
        logger.info(f"[ThemeService] set_dark: {value}")
        self._is_dark = value
        user_options.theme.is_dark = value
        self.notify("is-dark")
        self.mode_changed()
        self._load_current_theme()
        self.apply()

    def apply_light_theme(self, name: str) -> None:
        logger.info(f"[ThemeService] set_light_theme: {name}")
        self._light_theme = name
        user_options.theme.light_theme = name
        self.notify("light-theme")
        self._load_current_theme()
        self.apply()
        self.theme_changed()

    def apply_dark_theme(self, name: str) -> None:
        print(f"SET DARK THEME CALLED: {name}", flush=True)
        logger.info(f"[ThemeService] set_dark_theme: {name}")
        self._dark_theme = name
        user_options.theme.dark_theme = name
        self.notify("dark-theme")
        self._load_current_theme()
        self.apply()
        self.theme_changed()

    def apply_accent(self, accent_name: str) -> None:
        logger.info(f"[ThemeService] set_accent: {accent_name}")
        if self._current_theme_data is None:
            logger.warning("[ThemeService] wallpaper mode active — accent not applicable")
            return
        available = self._current_theme_data.get("accents", {}).get("available", {})
        if accent_name not in available:
            logger.warning(f"[ThemeService] accent '{accent_name}' not in {list(available.keys())}")
            return
        self._active_accent = accent_name
        user_options.theme.active_accent = accent_name
        self.notify("active-accent")
        self.accent_changed()
        self.apply()

    def set_scheme_type(self, scheme_type: str) -> None:
        logger.info(f"[ThemeService] set_scheme_type: {scheme_type}")
        self._scheme_type = scheme_type
        user_options.theme.scheme_type = scheme_type
        self.notify("scheme-type")
        self.apply()

    def list_themes(self, dark: bool = False) -> list[str]:
        folder = DARK_THEMES_DIR if dark else LIGHT_THEMES_DIR
        if not os.path.isdir(folder):
            return []
        return [
            os.path.splitext(f)[0]
            for f in sorted(os.listdir(folder))
            if f.endswith(".json")
        ]

    def load_theme_data(self, name: str, dark: bool) -> dict | None:
        """Load and return raw theme JSON for any theme by name, without changing state."""
        if name == WALLPAPER_THEME:
            return None
        folder = DARK_THEMES_DIR if dark else LIGHT_THEMES_DIR
        path = os.path.join(folder, f"{name}.json")
        if not os.path.isfile(path):
            return None
        try:
            with open(path) as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"[ThemeService] failed to read {path}: {e}")
            return None

    def apply(self) -> None:
        GLib.idle_add(self._apply)

    @property
    def active_is_wallpaper(self) -> bool:
        return (self._dark_theme if self._is_dark else self._light_theme) == WALLPAPER_THEME

    @property
    def active_theme_name(self) -> str:
        return self._dark_theme if self._is_dark else self._light_theme

    def _on_wallpaper_changed(self, _service, _path: str) -> None:
        if self.active_is_wallpaper:
            logger.info("[ThemeService] wallpaper changed, re-applying wallpaper theme")
            self.apply()

    def _load_current_theme(self) -> None:
        active_name = self._dark_theme if self._is_dark else self._light_theme

        if active_name == WALLPAPER_THEME:
            self._current_theme_data = None
            self._available_accents  = []
            self.notify("current-theme-data")
            self.notify("available-accents")
            return

        folder = DARK_THEMES_DIR if self._is_dark else LIGHT_THEMES_DIR
        path   = os.path.join(folder, f"{active_name}.json")
        logger.info(f"[ThemeService] loading theme: {path}")

        if not os.path.isfile(path):
            logger.warning(f"[ThemeService] theme file not found: {path}")
            self._current_theme_data = None
            self._available_accents  = []
            self.notify("current-theme-data")
            self.notify("available-accents")
            return

        try:
            with open(path) as f:
                self._current_theme_data = json.load(f)

            accents = self._current_theme_data.get("accents", {}).get("available", {})
            self._available_accents = list(accents.keys())

            if self._active_accent not in accents:
                default  = self._current_theme_data.get("accents", {}).get("default", "")
                fallback = default if default in accents else (next(iter(accents), ""))
                if fallback:
                    logger.info(f"[ThemeService] accent fallback: '{self._active_accent}' → '{fallback}'")
                    self._active_accent = fallback
                    user_options.theme.active_accent = fallback

            self.notify("current-theme-data")
            self.notify("available-accents")
            logger.info(f"[ThemeService] loaded '{active_name}', accents: {self._available_accents}")

        except Exception as e:
            logger.error(f"[ThemeService] failed to load '{active_name}': {e}")
            self._current_theme_data = None
            self._available_accents  = []

    def _build_matugen_json(self) -> dict:
        
        if self._current_theme_data is None:
            return {}

        raw_colors   = self._current_theme_data.get("colors", {})
        accents      = self._current_theme_data.get("accents", {})
        default_acc  = accents.get("default", "")
        accent_name  = self._active_accent if self._active_accent in accents.get("available", {}) else default_acc
        accent_color = accents.get("available", {}).get(accent_name)
        alpha = opacity_to_hex(user_options.theme.opacity)

        colors: dict = {}
        for key, variants in raw_colors.items():
            if not isinstance(variants, dict):
                continue
            light_color = variants.get("light", {}).get("color")
            dark_color  = variants.get("dark",  {}).get("color")
            if not light_color or not dark_color:
                continue
            colors[key] = {
                "light":   {"color": light_color + alpha},
                "default": {"color": dark_color + alpha},
                "dark":    {"color": dark_color + alpha},
            }

        if accent_color:
            colors["primary"] = {
                "light":   {"color": accent_color + alpha},
                "default": {"color": accent_color + alpha},
                "dark":    {"color": accent_color + alpha},
            }
            colors["source_color"] = {
                "light":   {"color": accent_color},
                "default": {"color": accent_color},
                "dark":    {"color": accent_color},
            }
        print(f"building json with accent: {accent_name} = {accent_color}", flush=True)

        return {"colors": colors}


    def _apply(self) -> bool:
        mode        = "dark" if self._is_dark else "light"
        active_name = self._dark_theme if self._is_dark else self._light_theme
        try:
            if active_name == WALLPAPER_THEME:
                wp_path = (
                    self._wallpaper_service.wallpaper_path
                    if self._wallpaper_service
                    else ""
                )
                if not wp_path or not os.path.isfile(wp_path):
                    logger.warning("[ThemeService] no wallpaper set, cannot apply Matugen mode")
                    return GLib.SOURCE_REMOVE
                cmd = [
                    "matugen", "image", wp_path,
                    "-m", mode,
                    "-t", self._scheme_type,
                    "--source-color-index", "0",
                    "--opacity", str(user_options.theme.opacity),
                ]
            else:
                if self._current_theme_data is None:
                    logger.warning("[ThemeService] no theme data, skipping apply")
                    return GLib.SOURCE_REMOVE

                matugen_json = self._build_matugen_json()
                if not matugen_json:
                    logger.warning("[ThemeService] empty JSON, skipping apply")
                    return GLib.SOURCE_REMOVE

                os.makedirs(os.path.dirname(CACHE_THEME_PATH), exist_ok=True)
                with open(CACHE_THEME_PATH, "w") as f:
                    json.dump(matugen_json, f, indent=2)

                cmd = ["matugen", "json", CACHE_THEME_PATH, "-m", mode, "--opacity", str(user_options.theme.opacity)]

            # ensure config exists, generate if not
            if not os.path.isfile(MATUGEN_CONFIG_CACHE):
                logger.info("[ThemeService] no matugen config found, generating...")
                template_service.build_matugen_config()

            cmd += ["-c", MATUGEN_CONFIG_CACHE]

            logger.info(f"[ThemeService] running: {' '.join(cmd)}")
            subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            logger.info(f"[ThemeService] launched matugen: mode={mode}, theme={active_name}")

        except FileNotFoundError:
            logger.error("[ThemeService] matugen not found — is it installed?")
        except Exception as e:
            logger.error(f"[ThemeService] unexpected error: {e}")

        return GLib.SOURCE_REMOVE