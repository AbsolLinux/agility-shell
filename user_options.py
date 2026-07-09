import os
import json
from loguru import logger
from fabric.utils import get_relative_path

CONFIG_PATH = os.path.expanduser("~/.config/caffyne-shell/config/config.json")


class UserOptions:
    class User:
        def __init__(self):
            self.avatar = f"/var/lib/AccountsService/icons/{os.getenv('USER')}"

    class Settings:
        def __init__(self):
            self.dnd = False

    class Bars:
        def __init__(self):
            self.configs = [
                {
                    "monitor": 0,
                    "bars": [
                        {
                            "alignment": "bottom",
                            "floating_bar": False,
                            "floating_applets": True,
                            "rounded_edges": True,
                            "min_width": False,
                            "auto_hide": False,
                            "left": [
                                "Dash",
                                {"widget": "Launcher", "variant": "icon"},
                                {"widget": "Processes", "variant": "scale"},
                                "Weather",
                                "Media"
                            ],
                            "center": ["Dock"],
                            "right": [
                                "Tray",
                                "Calendar",
                                {"widget": "Clock", "variant": "icon+label"},
                                {"widget": "Settings", "variant": "single"},
                                "Notifications"
                            ]
                        }
                    ],
                    "alignment": "bottom",
                    "floating_bar": True
                },
                {
                    "monitor": 1,
                    "bars": [
                        {
                            "alignment": "bottom",
                            "floating_bar": False,
                            "floating_applets": True,
                            "rounded_edges": True,
                            "min_width": False,
                            "auto_hide": False,
                            "left": [
                                "Dash",
                                {"widget": "Launcher", "variant": "icon"},
                                {"widget": "Processes", "variant": "scale"},
                                "Weather",
                                "Media"
                            ],
                            "center": ["Dock"],
                            "right": [
                                "Tray",
                                "Calendar",
                                {"widget": "Clock", "variant": "icon+label"},
                                {"widget": "Settings", "variant": "single"},
                                "Notifications"
                            ]
                        }
                    ],
                    "alignment": "bottom",
                    "floating_bar": True
                },
            ]

    class WorldClocks:
        def __init__(self):
            self.clocks = [
                "Europe/London",
                "Europe/Paris"
            ]

    class Dock:
        def __init__(self):
            self.entries = []

    class IdleTimeouts:
        def __init__(self):
            self.list = [
                {"name": "screen-off", "timeout_ac": 10, "timeout_bat": 2, "enabled": True},
                {"name": "lock", "timeout_ac": 15, "timeout_bat": 5, "enabled": True},
                {"name": "suspend", "timeout_ac": 15, "timeout_bat": 10, "enabled": True}
            ]

    class Theme:
        def __init__(self):
            self.light_theme = "catppuccin-latte"
            self.dark_theme = "catppuccin-mocha"
            self.active_accent = "accent4"
            self.is_dark = True
            self.scheme_type = "scheme-tonal-spot"
            self.opacity = 1.0
            self.blur = False
            self.border_style = "medium"
            self.font_monospace_style = "none"

    class Templates:
        def __init__(self):
            self.enabled: list[str] = []

    class Launcher:
        def __init__(self):
            self.grid = False

    class Wallpaper:
        def __init__(self):
            self.path = f"{get_relative_path('wallpapers/wall14.jpg')}"

    class DesktopApplets:
        def __init__(self):
            self.applets: list[dict] = []

        def get_applets(self) -> list[dict]:
            """Return the full placed applet list."""
            return self.applets

        def place(self, key: str, slot: int) -> bool:
            if any(e["key"] == key for e in self.applets):
                return False
            self.applets.append({"key": key, "slot": slot})
            return True

        def remove(self, key: str) -> bool:
            new_applets = [e for e in self.applets if e["key"] != key]
            if len(new_applets) == len(self.applets):
                return False
            self.applets = new_applets
            return True

        def update_slot(self, key: str, slot: int) -> None:
            for e in self.applets:
                if e["key"] == key:
                    e["slot"] = slot
                    break

        def is_placed(self, key: str) -> bool:
            return any(e["key"] == key for e in self.applets)

    class DesktopCanvas:
        def __init__(self):
            self.placements: dict[str, list[dict]] = {}
        
        def get_applets(self, monitor_id: int) -> list[dict]:
            """Return placed applets for *monitor_id* (empty list if none)."""
            return self.placements.get(str(monitor_id), [])
    
        def is_placed(self, monitor_id: int, key: str) -> bool:
            return any(e["key"] == key for e in self.get_applets(monitor_id))
        
        def place(self, monitor_id: int, key: str, grid_x: int, grid_y: int) -> bool:
            mid = str(monitor_id)
            if any(e["key"] == key for e in self.placements.get(mid, [])):
                return False
            self.placements.setdefault(mid, []).append(
                {"key": key, "grid_x": grid_x, "grid_y": grid_y}
            )
            return True
    
        def remove(self, monitor_id: int, key: str) -> bool:
            mid = str(monitor_id)
            before = self.placements.get(mid, [])
            after  = [e for e in before if e["key"] != key]
            if len(after) == len(before):
                return False
            self.placements[mid] = after
            return True
    
        def move(self, monitor_id: int, key: str, grid_x: int, grid_y: int) -> None:
            for e in self.placements.get(str(monitor_id), []):
                if e["key"] == key:
                    e["grid_x"] = grid_x
                    e["grid_y"] = grid_y
                    break
    
        def clear_monitor(self, monitor_id: int) -> None:
            self.placements.pop(str(monitor_id), None)

    def __init__(self):
        self.user = self.User()
        self.settings = self.Settings()
        self.bars = self.Bars()
        self.timeouts = self.IdleTimeouts()
        self.theme = self.Theme()
        self.templates = self.Templates()
        self.launcher = self.Launcher()
        self.dock = self.Dock()
        self.world_clocks = self.WorldClocks()
        self.wallpaper = self.Wallpaper()
        self.desktop_applets = self.DesktopApplets()
        self.desktop_canvas = self.DesktopCanvas()
        self._load()

    def _load(self) -> None:
        if not os.path.isfile(CONFIG_PATH):
            logger.info(f"[UserOptions] no config found at {CONFIG_PATH}, using defaults")
            return

        try:
            with open(CONFIG_PATH) as f:
                data = json.load(f)

            for section, values in data.items():
                obj = getattr(self, section, None)
                if obj is None or not isinstance(values, dict):
                    continue

                for key, value in values.items():
                    if hasattr(obj, key):
                        setattr(obj, key, value)
                    else:
                        logger.warning(f"[UserOptions] unknown key '{section}.{key}', skipping")

            logger.info(f"[UserOptions] loaded config from {CONFIG_PATH}")

        except Exception as e:
            logger.error(f"[UserOptions] failed to load config: {e}")

    def save(self) -> None:
        try:
            os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)

            data = {
                section: vars(getattr(self, section))
                for section in (
                    "user",
                    "settings",
                    "bars",
                    "timeouts",
                    "theme",
                    "launcher",
                    "dock",
                    "world_clocks",
                    "wallpaper",
                    "templates",
                    "desktop_applets",
                    "desktop_canvas"
                )
            }

            tmp = CONFIG_PATH + ".tmp"
            with open(tmp, "w") as f:
                json.dump(data, f, indent=2)

            os.replace(tmp, CONFIG_PATH)

            logger.info(f"[UserOptions] saved config to {CONFIG_PATH}")

        except Exception as e:
            logger.error(f"[UserOptions] failed to save config: {e}")


user_options = UserOptions()