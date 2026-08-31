import os
import json
import shutil
import subprocess
from loguru import logger
from fabric.core.service import Service, Signal
from user_options import user_options

AWE_DIR = os.path.expanduser("~/.config/quickshell/Awe")
SETTINGS_FILE = os.path.expanduser("~/.config/quickshell/widget_settings.json")
ALT_SETTINGS_FILE = os.path.expanduser("~/.config/quickshell/Awe/widget_settings.json")


class AweService(Service):
    """
    Service to manage Quickshell Awe desktop widgets process and configuration.
    """

    @Signal
    def status_changed(self, is_running: bool) -> None: ...

    @Signal
    def visibility_changed(self, widget_id: str, is_visible: bool) -> None: ...

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
        self._load_visibility()

    def is_running(self) -> bool:
        if self._proc is not None:
            if self._proc.poll() is None:
                return True
            self._proc = None

        # Check via pgrep if already running outside this process
        try:
            res = subprocess.run(
                ["pgrep", "-f", "quickshell.*Awe|qs.*Awe"],
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
                logger.info("[awe] Auto-starting Quickshell Awe widgets on startup...")
                self.start()
        except Exception as e:
            logger.warning(f"[awe] Failed to start on startup (safely ignored): {e}")

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
            logger.warning("[awe] quickshell executable ('qs' or 'quickshell') not found in PATH.")
            self.status_changed(False)
            return False

        if not os.path.exists(AWE_DIR):
            logger.warning(f"[awe] Awe directory not found at {AWE_DIR}")
            self.status_changed(False)
            return False

        try:
            cmd = [qs_bin, "-p", AWE_DIR]
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
            logger.info(f"[awe] Quickshell Awe launched with PID {self._proc.pid}")
            self.status_changed(True)
            return True
        except Exception as e:
            logger.error(f"[awe] Failed to spawn quickshell process: {e}")
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
            subprocess.run(["pkill", "-f", "quickshell.*Awe|qs.*Awe"], check=False)
        except Exception:
            pass

        logger.info("[awe] Quickshell Awe stopped.")
        self.status_changed(False)

    def toggle(self) -> bool:
        if self.is_running():
            self.stop()
            return False
        else:
            return self.start()

    # ── Visibility Settings Management ──────────────────────────────────────

    def _load_visibility(self) -> None:
        target_file = SETTINGS_FILE if os.path.exists(SETTINGS_FILE) else ALT_SETTINGS_FILE
        if os.path.exists(target_file):
            try:
                with open(target_file, "r") as f:
                    data = json.load(f)
                vis = data.get("manager", {}).get("visibility", {})
                if isinstance(vis, dict):
                    self._widgets_visibility = {str(k).lower(): bool(v) for k, v in vis.items()}
            except Exception as e:
                logger.warning(f"[awe] Error reading widget settings: {e}")

    def get_visibility(self, widget_id: str) -> bool:
        w_id = widget_id.lower()
        if w_id in self._widgets_visibility:
            return self._widgets_visibility[w_id]
        return True

    def set_visibility(self, widget_id: str, visible: bool) -> None:
        w_id = widget_id.lower()
        self._widgets_visibility[w_id] = bool(visible)

        # Persist to JSON files
        for target_path in [SETTINGS_FILE, ALT_SETTINGS_FILE]:
            try:
                data = {}
                if os.path.exists(target_path):
                    with open(target_path, "r") as f:
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
                logger.warning(f"[awe] Failed to write settings to {target_path}: {e}")

        self.visibility_changed(w_id, visible)

    def toggle_widget_visibility(self, widget_id: str) -> bool:
        new_state = not self.get_visibility(widget_id)
        self.set_visibility(widget_id, new_state)
        return new_state
