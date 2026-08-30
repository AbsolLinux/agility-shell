import os
import time
import json
import shutil
import subprocess
import threading
from datetime import datetime
from pathlib import Path
from typing import Optional

from fabric.core.service import Property, Service, Signal
from loguru import logger

from utils.sounds import play_sound


def _get_active_window_geometry() -> Optional[str]:
    """Attempt to detect active window geometry across supported Wayland compositors."""
    # 1. Hyprland
    if shutil.which("hyprctl"):
        try:
            res = subprocess.run(
                ["hyprctl", "activewindow", "-j"],
                capture_output=True,
                text=True,
                timeout=2,
            )
            if res.returncode == 0 and res.stdout.strip():
                data = json.loads(res.stdout)
                at = data.get("at", [])
                size = data.get("size", [])
                if len(at) == 2 and len(size) == 2 and size[0] > 0 and size[1] > 0:
                    return f"{at[0]},{at[1]} {size[0]}x{size[1]}"
        except Exception as e:
            logger.debug(f"[ScreenshotService] hyprctl activewindow error: {e}")

    # 2. Niri
    if shutil.which("niri"):
        try:
            res = subprocess.run(
                ["niri", "msg", "-j", "focused-window"],
                capture_output=True,
                text=True,
                timeout=2,
            )
            if res.returncode == 0 and res.stdout.strip():
                data = json.loads(res.stdout)
                if "x" in data and "y" in data and "width" in data and "height" in data:
                    return f"{data['x']},{data['y']} {data['width']}x{data['height']}"
        except Exception as e:
            logger.debug(f"[ScreenshotService] niri focused-window error: {e}")

    return None


class ScreenshotService(Service):
    @Signal
    def screenshot_taken(self, filepath: str) -> None: ...

    @Property(str, "readable", default_value="")
    def last_screenshot(self) -> str:
        return self._last_screenshot

    def __init__(
        self,
        output_dir: str = "~/Pictures/Screenshots",
        **kwargs,
    ):
        super().__init__(**kwargs)
        self._output_dir = Path(output_dir).expanduser()
        self._last_screenshot = ""
        self._output_dir.mkdir(parents=True, exist_ok=True)

    def capture(self, mode: str = "fullscreen", delay: int = 0):
        """
        Capture screenshot in background thread.
        mode: 'fullscreen' | 'region' | 'window'
        delay: delay in seconds (0, 3, 5, etc.)
        """
        thread = threading.Thread(
            target=self._capture_worker,
            args=(mode, delay),
            daemon=True,
        )
        thread.start()

    def capture_fullscreen(self, delay: int = 0):
        self.capture("fullscreen", delay)

    def capture_region(self, delay: int = 0):
        self.capture("region", delay)

    def capture_window(self, delay: int = 0):
        self.capture("window", delay)

    def _close_open_applets(self):
        """Close open applet popups so they aren't captured in the screenshot."""
        try:
            import bar
            bar.set_open_applet(None)
        except Exception as e:
            logger.debug(f"[ScreenshotService] Unable to close open applet: {e}")

    def _capture_worker(self, mode: str, delay: int):
        # If no delay, close applet immediately
        if delay == 0:
            self._close_open_applets()
            time.sleep(0.2)  # brief pause for compositor unmap animation
        else:
            time.sleep(delay)
            self._close_open_applets()
            time.sleep(0.15)

        filepath = self._output_dir / (
            f"screenshot_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.png"
        )

        geometry: Optional[str] = None

        if mode == "region":
            if not shutil.which("slurp"):
                logger.error("[ScreenshotService] slurp not found for region capture")
                return
            try:
                slurp_proc = subprocess.run(
                    ["slurp"],
                    capture_output=True,
                    text=True,
                )
                if slurp_proc.returncode != 0 or not slurp_proc.stdout.strip():
                    logger.info("[ScreenshotService] Region capture cancelled")
                    return
                geometry = slurp_proc.stdout.strip()
            except Exception as e:
                logger.error(f"[ScreenshotService] Failed to execute slurp: {e}")
                return

        elif mode == "window":
            geometry = _get_active_window_geometry()
            if not geometry:
                # Fallback to slurp if available
                if shutil.which("slurp"):
                    logger.info("[ScreenshotService] Active window geometry not auto-detected; falling back to slurp")
                    try:
                        slurp_proc = subprocess.run(
                            ["slurp"],
                            capture_output=True,
                            text=True,
                        )
                        if slurp_proc.returncode != 0 or not slurp_proc.stdout.strip():
                            logger.info("[ScreenshotService] Window capture cancelled")
                            return
                        geometry = slurp_proc.stdout.strip()
                    except Exception as e:
                        logger.error(f"[ScreenshotService] Failed to execute slurp: {e}")
                        return

        # Execute grim
        if not shutil.which("grim"):
            logger.error("[ScreenshotService] grim not found — is grim installed?")
            return

        grim_cmd = ["grim"]
        if geometry:
            grim_cmd.extend(["-g", geometry])
        grim_cmd.append(str(filepath))

        try:
            res = subprocess.run(grim_cmd, capture_output=True, text=True)
            if res.returncode != 0 or not filepath.exists() or filepath.stat().st_size == 0:
                logger.error(f"[ScreenshotService] grim failed: {res.stderr}")
                return
        except Exception as e:
            logger.error(f"[ScreenshotService] Error running grim: {e}")
            return

        # Update service state
        self._last_screenshot = str(filepath)
        self.notify("last-screenshot")
        self.emit("screenshot-taken", str(filepath))
        logger.info(f"[ScreenshotService] Screenshot captured: {filepath}")

        # Copy to clipboard
        if shutil.which("wl-copy"):
            try:
                subprocess.run(
                    ["wl-copy", "--type", "image/png"],
                    input=filepath.read_bytes(),
                    check=False,
                )
                logger.info("[ScreenshotService] Screenshot copied to clipboard")
            except Exception as e:
                logger.warning(f"[ScreenshotService] Failed to copy to clipboard: {e}")

        # Play sound
        try:
            play_sound("confirm")
        except Exception:
            pass

        # Send notification with action buttons
        self._send_notification(filepath)

    def _send_notification(self, filepath: Path):
        if not shutil.which("notify-send"):
            return

        cmd = [
            "notify-send",
            "-a", "Agility Shell",
            "-i", str(filepath),
            "Screenshot Captured",
            f"Saved to {filepath.name}\nCopied to clipboard",
            "-A", "open=Open",
            "-A", "folder=Show in Folder",
        ]

        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=20)
            action = proc.stdout.strip()
            if action == "open":
                subprocess.Popen(["xdg-open", str(filepath)])
            elif action == "folder":
                subprocess.Popen(["xdg-open", str(filepath.parent)])
        except Exception as e:
            logger.debug(f"[ScreenshotService] Notification result handling: {e}")
