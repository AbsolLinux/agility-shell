import json
import os
import re
import threading

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gio, GLib, Gtk
from loguru import logger



CACHE_DIR = os.path.expanduser("~/.cache/agility-shell")

ICON_CACHE_FILE = os.path.join(CACHE_DIR, "icons.json")
os.makedirs(CACHE_DIR, exist_ok=True)

FALLBACK_ICON = "application-x-symbolic"


class IconResolver:
    def __init__(self):
        self._lock = threading.Lock()
        self._mem_cache: dict[str, str] = self._load_disk_cache()
        self._disk_dirty = False
        threading.Thread(target=self._build_gio_cache, daemon=True).start()

    def get_icon(self, app_id: str) -> str:
        """Return a valid icon name for *app_id*, falling back to a generic icon."""
        if not app_id:
            return FALLBACK_ICON

        for key in self._candidate_keys(app_id):
            with self._lock:
                cached = self._mem_cache.get(key)
            if cached:
                logger.debug(f"[ICONS] cache hit: '{app_id}' -> '{cached}'")
                return cached

        # Nothing cached — resolve now and store the result.
        icon = self._resolve(app_id)
        logger.info(f"[ICONS] resolved: '{app_id}' -> '{icon}'")
        self._store(app_id, icon)
        return icon

    def _load_disk_cache(self) -> dict[str, str]:
        if not os.path.exists(ICON_CACHE_FILE):
            return {}
        try:
            with open(ICON_CACHE_FILE) as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            logger.warning("[ICONS] Disk cache missing or corrupt — starting fresh.")
            return {}

    def _flush_disk_cache(self) -> None:
        """Write the in-memory cache to disk (call with lock held)."""
        try:
            with open(ICON_CACHE_FILE, "w") as f:
                json.dump(self._mem_cache, f)
            self._disk_dirty = False
        except OSError as exc:
            logger.warning(f"[ICONS] Failed to write cache: {exc}")

    def _store(self, app_id: str, icon: str) -> None:
        if icon == FALLBACK_ICON:
            return  # Don't persist misses — GIO index may not be ready yet
        with self._lock:
            self._mem_cache[app_id] = icon
            self._disk_dirty = True
            self._flush_disk_cache()
    def _build_gio_cache(self) -> None:
        additions: dict[str, str] = {}

        for app in Gio.AppInfo.get_all():
            gio_icon = app.get_icon()
            if not gio_icon:
                continue

            icon_str = gio_icon.to_string()

            desktop_id = (app.get_id() or "").lower().removesuffix(".desktop")
            app_name = (app.get_name() or "").lower()
            executable = (app.get_executable() or "").split("/")[-1].lower()

            candidates = [desktop_id, app_name, executable]

            if "." in desktop_id:
                candidates.append(desktop_id.split(".")[-1])

            for key in candidates:
                if key and key not in additions:
                    additions[key] = icon_str

        with self._lock:
            changed = False
            for key, icon in additions.items():
                if key not in self._mem_cache:
                    self._mem_cache[key] = icon
                    changed = True
            if changed:
                self._flush_disk_cache()

        logger.debug(f"[ICONS] GIO background index complete ({len(additions)} entries).")

    def _resolve(self, app_id: str) -> str:
        theme = Gtk.IconTheme.get_default()
        for candidate in self._candidate_keys(app_id):
            if theme.has_icon(candidate):
                return candidate
        for suffix in ("-desktop", "-symbolic"):
            if theme.has_icon(app_id + suffix):
                return app_id + suffix

        desktop_path = self._find_desktop_file(app_id)
        if desktop_path:
            icon = self._icon_from_desktop_file(desktop_path)
            if icon and icon != FALLBACK_ICON:
                # Validate the icon actually exists in the current theme
                if theme.has_icon(icon):
                    return icon
                # Could be an absolute path — that's valid too
                if os.path.isabs(icon) and os.path.exists(icon):
                    return icon

        return FALLBACK_ICON

    def _find_desktop_file(self, app_id: str) -> str | None:
        """
        Walk XDG data dirs looking for a .desktop file that matches app_id.
        Strategy (in order):
          - Exact filename match  (<app_id>.desktop)
          - Whole-word substring match
          - Per-word token match (split on - . _ and whitespace)
        """
        for data_dir in GLib.get_system_data_dirs():
            apps_dir = os.path.join(data_dir, "applications")
            if not os.path.isdir(apps_dir):
                continue

            try:
                files = os.listdir(apps_dir)
            except OSError:
                continue

            app_id_lower = "".join(app_id.lower().split())

            # Exact match first
            exact = app_id_lower + ".desktop"
            if exact in files:
                return os.path.join(apps_dir, exact)

            # Whole-word substring
            matching = [f for f in files if app_id_lower in f.lower()]
            if matching:
                return os.path.join(apps_dir, matching[0])

            # Token fallback
            for token in filter(None, re.split(r"[-._\s]", app_id)):
                matching = [f for f in files if token.lower() in f.lower()]
                if matching:
                    return os.path.join(apps_dir, matching[0])

        return None

    def _icon_from_desktop_file(self, path: str) -> str:
        """
        Extract the Icon= value strictly from the [Desktop Entry] section,
        avoiding accidental matches in [Desktop Action *] sections.
        """
        in_desktop_entry = False
        try:
            with open(path) as f:
                for raw_line in f:
                    line = raw_line.strip()
                    if line.startswith("["):
                        in_desktop_entry = line == "[Desktop Entry]"
                        continue
                    if in_desktop_entry and line.startswith("Icon="):
                        return line[5:].strip()
        except OSError:
            pass
        return FALLBACK_ICON

    @staticmethod
    def _candidate_keys(app_id: str) -> list[str]:
        """
        Return all lookup keys to try for a given app_id, from most
        specific to least.
        """
        lower = app_id.lower()
        keys = [lower]

        # Short reverse-DNS: org.gnome.Nautilus -> nautilus
        if "." in lower:
            keys.append(lower.split(".")[-1])

        # Dash-joined reverse-DNS: org.gnome.Nautilus -> org-gnome-nautilus
        keys.append("-".join(lower.split(".")))

        return keys
