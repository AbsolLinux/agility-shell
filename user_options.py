import os
import json
from loguru import logger
from fabric.utils import get_relative_path

CONFIG_PATH = os.path.expanduser("~/.config/agility-shell/config/config.json")


class UserOptions:
    class User:
        def __init__(self):
            self.avatar = f"/var/lib/AccountsService/icons/{os.getenv('USER')}"

    class Settings:
        def __init__(self):
            self.dnd = False
            self.hover_open = True
            self.hover_delay = 180
            self.hover_widgets = [
                "Dash", "Launcher", "SysMon", "Processes", "Clipboard", "Caffeine", "NightLight",
                "Media", "Weather", "Volume", "Brightness", "Energy", "Wifi", "Bluetooth",
                "Clock", "Calendar", "Notifications", "Settings", "Tray", "Calculator", "Keyboard", "Screenshot", "Session"
            ]
            self.bar_theme = "default"
            self.bar_blur = True
            self.bar_opacity = 1.0
            self.widget_opacity = 1.0
            self.desktop_widget_opacity = 1.0
            self.dash_blur = True
            self.dash_dim_opacity = 0.6
            self.dash_card_opacity = 1.0
            self.instant_dash = True
            self.pinned_apps = []

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
                            "horizontal_alignment": "center",
                            "auto_hide": False,
                            "left": [
                                "Dash",
                                {"widget": "Launcher", "variant": "icon"},
                                {"widget": "Processes", "variant": "scale"},
                                "Weather",
                                "Media"
                            ],
                            "center": [],
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
                            "horizontal_alignment": "center",
                            "auto_hide": False,
                            "left": [
                                "Dash",
                                {"widget": "Launcher", "variant": "icon"},
                                {"widget": "Processes", "variant": "scale"},
                                "Weather",
                                "Media"
                            ],
                            "center": [],
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
            self.transition_type = "random"
            self.enabled_transitions = [
                "grow", "fade", "wipe", "wave", "left", "right", "top", "bottom", "outer"
            ]
            self.custom_transitions: list[dict] = []
            self.transition_duration = 1.5
            self.transition_fps = 60

    class DesktopApplets:
        def __init__(self):
            self.applets: list[dict] = []

        def get_applets(self) -> list[dict]:
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
            return self.placements.get(str(monitor_id), [])

        def is_placed(self, monitor_id: int, key: str) -> bool:
            return any(e["key"] == key for e in self.get_applets(monitor_id))

        @staticmethod
        def _compute_anchor(grid_x: int, cc: int, cols: int) -> tuple[str, int]:
            left_boundary  = int(cols * 0.4)
            right_boundary = int(cols * 0.6)
            center_col     = cols // 2

            if grid_x < left_boundary:
                return "left", grid_x
            elif grid_x >= right_boundary:
                return "right", cols - grid_x - cc
            else:
                return "center", grid_x - center_col

        def place(self, monitor_id: int, key: str, grid_x: int, grid_y: int, cols: int, ry: float, span_x: int | None = None, span_y: int | None = None, opacity: float | None = None) -> bool:
            mid = str(monitor_id)
            if any(e["key"] == key for e in self.placements.get(mid, [])):
                return False
            from desktop_applets import DESKTOP_CANVAS_SIZES
            base_cols, base_rows = DESKTOP_CANVAS_SIZES.get(key, (1, 1))
            sx = span_x if span_x is not None else base_cols
            sy = span_y if span_y is not None else base_rows
            cc = sx * 2
            ax, dx = self._compute_anchor(grid_x, cc, cols)
            entry = {"key": key, "grid_x": grid_x, "grid_y": grid_y, "ax": ax, "dx": dx, "ry": ry}
            if span_x is not None:
                entry["span_x"] = span_x
            if span_y is not None:
                entry["span_y"] = span_y
            if opacity is not None:
                entry["opacity"] = opacity
            self.placements.setdefault(mid, []).append(entry)
            return True

        def remove(self, monitor_id: int, key: str) -> bool:
            mid = str(monitor_id)
            before = self.placements.get(mid, [])
            after  = [e for e in before if e["key"] != key]
            if len(after) == len(before):
                return False
            self.placements[mid] = after
            return True

        def move(self, monitor_id: int, key: str, grid_x: int, grid_y: int, cols: int) -> None:
            from desktop_applets import DESKTOP_CANVAS_SIZES
            for e in self.placements.get(str(monitor_id), []):
                if e["key"] == key:
                    base_cols, _ = DESKTOP_CANVAS_SIZES.get(key, (1, 1))
                    sx = e.get("span_x", base_cols)
                    cc = sx * 2
                    ax, dx = self._compute_anchor(grid_x, cc, cols)
                    e["grid_x"] = grid_x
                    e["grid_y"] = grid_y
                    e["ax"]     = ax
                    e["dx"]     = dx
                    break

        def set_opacity(self, monitor_id: int, key: str, opacity: float) -> bool:
            for e in self.placements.get(str(monitor_id), []):
                if e["key"] == key:
                    e["opacity"] = max(0.0, min(1.0, float(opacity)))
                    return True
            return False

        def get_opacity(self, monitor_id: int, key: str) -> float | None:
            for e in self.placements.get(str(monitor_id), []):
                if e["key"] == key:
                    return e.get("opacity")
            return None

        def set_span(self, monitor_id: int, key: str, span_x: int, span_y: int) -> bool:
            for e in self.placements.get(str(monitor_id), []):
                if e["key"] == key:
                    e["span_x"] = max(1, int(span_x))
                    e["span_y"] = max(1, int(span_y))
                    return True
            return False

        def get_span(self, monitor_id: int, key: str) -> tuple[int, int] | None:
            for e in self.placements.get(str(monitor_id), []):
                if e["key"] == key and "span_x" in e and "span_y" in e:
                    return (e["span_x"], e["span_y"])
            return None

        def clear_monitor(self, monitor_id: int) -> None:
            self.placements.pop(str(monitor_id), None)

        def resolve(self, monitor_id: int, cols: int, rows: int) -> None:
            from desktop_applets import DESKTOP_CANVAS_SIZES

            def _applet_cell_size(entry: dict) -> tuple[int, int]:
                key = entry["key"]
                base_cols, base_rows = DESKTOP_CANVAS_SIZES.get(key, (1, 1))
                sx = entry.get("span_x", base_cols)
                sy = entry.get("span_y", base_rows)
                return sx * 2, sy * 2

            def _cells(gx: int, gy: int, cc: int, cr: int) -> set[tuple[int, int]]:
                return {(gx + dx, gy + dy) for dx in range(cc) for dy in range(cr)}

            center_col = cols // 2
            entries    = self.placements.get(str(monitor_id), [])
            occupied: set[tuple[int, int]] = set()

            for entry in entries:
                key = entry["key"]
                ry  = entry.get("ry", 0.0)
                cc, cr = _applet_cell_size(entry)

                ax = entry.get("ax")
                if ax == "left":
                    gx = max(0, min(entry["dx"], cols - cc))
                elif ax == "right":
                    gx = max(0, min(cols - entry["dx"] - cc, cols - cc))
                elif ax == "center":
                    gx = max(0, min(center_col + entry["dx"], cols - cc))
                else:
                    rx = entry.get("rx", 0.0)
                    gx = max(0, min(round(rx * cols), cols - cc))
                    ax, dx = self._compute_anchor(gx, cc, cols)
                    entry["ax"] = ax
                    entry["dx"] = dx
                    entry.pop("rx", None)

                gy = max(0, min(round(ry * rows), rows - cr))

                candidate_gy = gy
                while _cells(gx, candidate_gy, cc, cr) & occupied:
                    candidate_gy += 1
                    if candidate_gy + cr > rows:
                        candidate_gy = gy
                        break

                entry["grid_x"] = gx
                entry["grid_y"] = candidate_gy
                occupied |= _cells(gx, candidate_gy, cc, cr)

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