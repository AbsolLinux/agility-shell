import os
import json
import shutil
import subprocess
from loguru import logger
from fabric.core.service import Service, Signal
from user_options import user_options

REPO_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AGILITY_QS_DIR = os.path.join(REPO_DIR, "quickshell", "agility")
USER_QS_DIR = os.path.expanduser("~/.config/agility-shell/quickshell/agility")
QS_DIR = AGILITY_QS_DIR if os.path.exists(AGILITY_QS_DIR) else USER_QS_DIR

PRIMARY_SETTINGS_FILE = os.path.expanduser("~/.config/agility-shell/widget_settings.json")
LEGACY_SETTINGS_FILE = os.path.expanduser("~/.config/quickshell/widget_settings.json")

AWE_THEMES: list[dict] = [
    {
        "id": "liquid_glass",
        "name": "Liquid Glass",
        "icon": "drop-duotone",
        "desc": "Water droplet translucent glass with curved meniscus sheen",
        "accent": "#7DD3FC",
        "tile_bg": "#38141F2E",
    },
    {
        "id": "transparent",
        "name": "Transparent",
        "icon": "frame-corners-duotone",
        "desc": "Minimal see-through floating aesthetic",
        "accent": "#38BDF8",
        "tile_bg": "#260B0E14",
    },
    {
        "id": "material",
        "name": "Material 3",
        "icon": "paint-brush-duotone",
        "desc": "Original dark slate with Pixel cyan",
        "accent": "#C2E7FF",
        "tile_bg": "#232D33",
    },
    {
        "id": "cyberpunk",
        "name": "Cyberpunk",
        "icon": "lightning-duotone",
        "desc": "High-contrast neon glow on obsidian",
        "accent": "#00FFE0",
        "tile_bg": "#0A0B10",
    },
    {
        "id": "nordic",
        "name": "Nordic Frost",
        "icon": "snowflake-duotone",
        "desc": "Arctic cold blue & snow storm palette",
        "accent": "#88C0D0",
        "tile_bg": "#2E3440",
    },
    {
        "id": "oled",
        "name": "OLED Black",
        "icon": "moon-stars-duotone",
        "desc": "100% pitch-black with crisp white typography",
        "accent": "#FFFFFF",
        "tile_bg": "#000000",
    },
    {
        "id": "warm_latte",
        "name": "Warm Latte",
        "icon": "coffee-duotone",
        "desc": "Cozy espresso & caramel with warm amber",
        "accent": "#F59E0B",
        "tile_bg": "#1E1A16",
    },
    {
        "id": "tokyo_night",
        "name": "Tokyo Night",
        "icon": "sparkle-duotone",
        "desc": "Midnight indigo-violet with lavender & cyan",
        "accent": "#7AA2F7",
        "tile_bg": "#1A1B26",
    },
    {
        "id": "evergreen_moss",
        "name": "Evergreen",
        "icon": "tree-evergreen-duotone",
        "desc": "Translucent forest green with phosphor telemetry",
        "accent": "#22C55E",
        "tile_bg": "#0C1A12",
    },
    {
        "id": "aurora_prism",
        "name": "Aurora Prism",
        "icon": "diamond-duotone",
        "desc": "Crystal glass with iridescent aurora reflections",
        "accent": "#E879F9",
        "tile_bg": "#161826",
    },
]


class AweService(Service):
    """
    Service to manage native Quickshell desktop widgets process and configuration directly within Agility Shell.
    """

    @Signal
    def status_changed(self, is_running: bool) -> None: ...

    @Signal
    def visibility_changed(self, widget_id: str, is_visible: bool) -> None: ...

    @Signal
    def theme_changed(self, theme_id: str) -> None: ...

    _instance = None

    @classmethod
    def get_instance(cls) -> "AweService":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._proc: subprocess.Popen | None = None
        self._widgets_visibility: dict[str, bool] = {}
        self._current_theme: str = "liquid_glass"
        self._load_visibility()
        self._load_theme()

    def is_running(self) -> bool:
        if self._proc is not None:
            if self._proc.poll() is None:
                return True
            self._proc = None

        # Check via pgrep if running
        try:
            res = subprocess.run(
                ["pgrep", "-f", "quickshell.*(agility|Awe)|qs.*(agility|Awe)"],
                capture_output=True,
                text=True,
                check=False,
            )
            return res.returncode == 0
        except Exception:
            return False

    def is_enabled(self) -> bool:
        return bool(getattr(user_options.settings, "awe_widgets_enabled", False))

    def init_startup(self) -> None:
        """Start on shell startup only if user explicitly enabled it."""
        try:
            if self.is_enabled():
                logger.info("[desktop-widgets] Auto-starting desktop widgets on startup...")
                self.start()
        except Exception as e:
            logger.warning(f"[desktop-widgets] Failed to start on startup (safely ignored): {e}")

    def start(self) -> bool:
        if self.is_running():
            setattr(user_options.settings, "awe_widgets_enabled", True)
            try:
                user_options.save()
            except Exception:
                pass
            self.status_changed(True)
            return True

        qs_bin = shutil.which("qs") or shutil.which("quickshell")
        if not qs_bin:
            logger.warning("[desktop-widgets] quickshell executable ('qs' or 'quickshell') not found in PATH.")
            self.status_changed(False)
            return False

        if not os.path.exists(QS_DIR):
            logger.warning(f"[desktop-widgets] Quickshell directory not found at {QS_DIR}")
            self.status_changed(False)
            return False

        try:
            cmd = [qs_bin, "-p", QS_DIR]
            self._proc = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
            setattr(user_options.settings, "awe_widgets_enabled", True)
            try:
                user_options.save()
            except Exception:
                pass
            logger.info(f"[desktop-widgets] Quickshell desktop widgets launched with PID {self._proc.pid} from {QS_DIR}")
            self.status_changed(True)
            return True
        except Exception as e:
            logger.error(f"[desktop-widgets] Failed to spawn quickshell process: {e}")
            self._proc = None
            self.status_changed(False)
            return False

    def stop(self) -> None:
        setattr(user_options.settings, "awe_widgets_enabled", False)
        try:
            user_options.save()
        except Exception:
            pass

        if self._proc is not None:
            try:
                self._proc.terminate()
                self._proc.wait(timeout=1.0)
            except Exception:
                try:
                    self._proc.kill()
                except Exception:
                    pass
            self._proc = None

        try:
            subprocess.run(["pkill", "-f", "quickshell.*(agility|Awe)|qs.*(agility|Awe)"], check=False)
        except Exception:
            pass

        logger.info("[desktop-widgets] Quickshell desktop widgets stopped.")
        self.status_changed(False)

    def toggle(self) -> bool:
        if self.is_running():
            self.stop()
            return False
        else:
            return self.start()

    # ── Visibility Settings Management ──────────────────────────────────────

    def _get_read_settings_file(self) -> str | None:
        for p in [PRIMARY_SETTINGS_FILE, LEGACY_SETTINGS_FILE]:
            if os.path.exists(p):
                return p
        return None

    def _load_visibility(self) -> None:
        target_file = self._get_read_settings_file()
        if target_file and os.path.exists(target_file):
            try:
                with open(target_file, "r") as f:
                    data = json.load(f)
                vis = data.get("manager", {}).get("visibility", {})
                if isinstance(vis, dict):
                    self._widgets_visibility = {str(k).lower(): bool(v) for k, v in vis.items()}
            except Exception as e:
                logger.warning(f"[desktop-widgets] Error reading widget settings: {e}")

    def get_visibility(self, widget_id: str) -> bool:
        w_id = widget_id.lower()
        if w_id in self._widgets_visibility:
            return self._widgets_visibility[w_id]
        return True

    def set_visibility(self, widget_id: str, visible: bool) -> None:
        w_id = widget_id.lower()
        self._widgets_visibility[w_id] = bool(visible)

        # Persist to both primary and legacy settings files
        for target_path in [PRIMARY_SETTINGS_FILE, LEGACY_SETTINGS_FILE]:
            try:
                data = {}
                if os.path.exists(target_path):
                    with open(target_path, "r") as f:
                        data = json.load(f)
                elif os.path.exists(LEGACY_SETTINGS_FILE):
                    with open(LEGACY_SETTINGS_FILE, "r") as f:
                        data = json.load(f)

                if "manager" not in data:
                    data["manager"] = {}
                if "visibility" not in data["manager"]:
                    data["manager"]["visibility"] = {}

                data["manager"]["visibility"][w_id] = bool(visible)

                os.makedirs(os.path.dirname(target_path), exist_ok=True)
                with open(target_path, "w") as f:
                    json.dump(data, f, indent=2)
            except Exception as e:
                logger.warning(f"[desktop-widgets] Failed to write settings to {target_path}: {e}")

        self.visibility_changed(w_id, visible)

    def toggle_widget_visibility(self, widget_id: str) -> bool:
        new_state = not self.get_visibility(widget_id)
        self.set_visibility(widget_id, new_state)
        return new_state

    # ── Theme Settings Management ───────────────────────────────────────────

    def _load_theme(self) -> None:
        target_file = self._get_read_settings_file()
        if target_file and os.path.exists(target_file):
            try:
                with open(target_file, "r") as f:
                    data = json.load(f)
                theme = data.get("manager", {}).get("theme", "liquid_glass")
                if theme:
                    self._current_theme = str(theme)
            except Exception as e:
                logger.warning(f"[desktop-widgets] Error reading widget theme: {e}")

    def get_theme(self) -> str:
        return self._current_theme

    def set_theme(self, theme_id: str) -> None:
        self._current_theme = str(theme_id)

        # Persist to both primary and legacy JSON files
        for target_path in [PRIMARY_SETTINGS_FILE, LEGACY_SETTINGS_FILE]:
            try:
                data = {}
                if os.path.exists(target_path):
                    with open(target_path, "r") as f:
                        data = json.load(f)
                elif os.path.exists(LEGACY_SETTINGS_FILE):
                    with open(LEGACY_SETTINGS_FILE, "r") as f:
                        data = json.load(f)

                if "manager" not in data:
                    data["manager"] = {}

                data["manager"]["theme"] = str(theme_id)

                os.makedirs(os.path.dirname(target_path), exist_ok=True)
                with open(target_path, "w") as f:
                    json.dump(data, f, indent=2)
            except Exception as e:
                logger.warning(f"[desktop-widgets] Failed to write theme to {target_path}: {e}")

        self.theme_changed(self._current_theme)


# Alias for clean naming
DesktopWidgetsService = AweService
