import hashlib
import mimetypes
import urllib.parse
import urllib.request
from pathlib import Path
from loguru import logger

import gi
gi.require_version("Playerctl", "2.0")
from gi.repository import Playerctl, GLib

from fabric.core.service import Service, Signal, Property
from fabric import Fabricator

TEMP_DIR = Path.home() / ".cache" / "agility-shell"
TEMP_DIR.mkdir(parents=True, exist_ok=True)

class PlayerService(Service):
    @Signal
    def meta_change(self, metadata: GLib.Variant, player: Playerctl.Player) -> None: ...

    @Signal
    def artwork_change(self, local_path: str) -> None: ...

    @Signal
    def pause(self) -> None: ...

    @Signal
    def play(self) -> None: ...

    @Signal
    def track_position(self, pos: float, dur: float) -> None: ...

    @Property(bool, "readable", default_value=False)
    def can_go_previous(self) -> bool:
        return self._player.get_property("can_go_previous")

    @Property(bool, "readable", default_value=False)
    def can_go_next(self) -> bool:
        return self._player.get_property("can_go_next")

    @Property(bool, "readable", default_value=False)
    def can_pause(self) -> bool:
        return self._player.get_property("can_pause")

    @Property(bool, "readable", default_value=False)
    def can_play(self) -> bool:
        return self._player.get_property("can_play")

    @Property(bool, "readable", default_value=False)
    def can_seek(self) -> bool:
        return self._player.get_property("can_seek")

    @Property(bool, "readable", default_value=False)
    def can_control(self) -> bool:
        return self._player.get_property("can_control")

    def __init__(self, player: Playerctl.Player, **kwargs):
        super().__init__(**kwargs)
        self._player: Playerctl.Player = player
        self._current_artwork_hash = ""
        self._current_artwork_path = ""
        self._is_cleaning_up = False
        self._signal_ids = []

        self._signal_ids.append(
            self._player.connect("playback-status::playing", self.on_play)
        )
        self._signal_ids.append(
            self._player.connect("playback-status::paused", self.on_pause)
        )
        self._signal_ids.append(self._player.connect("metadata", self.on_metadata))
        self._signal_ids.append(self._player.connect("seeked", self.on_seeked))

        self.status = self._player.props.playback_status
        self.pos_fabricator = Fabricator(
            interval=1000,
            poll_from=lambda f, *_: self.get_position(),
            on_changed=lambda f, *_: self.fabricating(),
        )
        self.poll_progress()

        try:
            metadata = self._player.props.metadata
            if metadata:
                self.meta_change(metadata, self._player)
                self._handle_artwork(metadata, metadata.keys())
        except Exception as e:
            logger.warning(f"Failed to initialize metadata: {e}")

    def get_artwork(self) -> str:
        return self._current_artwork_path

    def get_position(self) -> float:
        if self._is_cleaning_up:
            return 0
        try:
            return self._player.get_position()
        except Exception as e:
            logger.warning(f"Could not get position: {e}")
            return 0

    def set_position(self, pos: float):
        if self._is_cleaning_up:
            return
        self.pos_fabricator.stop()
        try:
            self._player.set_position(int(pos * 1_000_000))
        except GLib.Error as e:
            logger.error(f"Failed to seek: {e}")

    def poll_progress(self):
        if self._is_cleaning_up:
            return
        if self.status.value_name == "PLAYERCTL_PLAYBACK_STATUS_PLAYING":
            self.pos_fabricator.start()
        else:
            self.pos_fabricator.stop()

    def fabricating(self):
        if self._is_cleaning_up:
            return
        try:
            pos = self._player.get_position() / 1_000_000
            keys = self._player.props.metadata.keys()
            dur = (
                self._player.props.metadata["mpris:length"] / 1_000_000
                if "mpris:length" in keys
                else 0
            )
            self.track_position(pos, dur)
        except GLib.Error as e:
            logger.warning(f"Failed to get position: {e}")

    def on_seeked(self, player, position):
        if self._is_cleaning_up:
            return
        if self.status.value_name == "PLAYERCTL_PLAYBACK_STATUS_PLAYING":
            self.pos_fabricator.start()

    def on_play(self, player, status):
        if self._is_cleaning_up:
            return
        self.status = player.props.playback_status
        self.poll_progress()
        self.play()

    def on_pause(self, player, status):
        if self._is_cleaning_up:
            return
        self.status = player.props.playback_status
        self.poll_progress()
        self.pause()

    def on_metadata(self, player, metadata):
        if self._is_cleaning_up:
            return
        self.meta_change(metadata, player)
        self._handle_artwork(metadata, metadata.keys())

    def _handle_artwork(self, metadata, keys):
        if self._is_cleaning_up or "mpris:artUrl" not in keys:
            return

        art_url = metadata["mpris:artUrl"]
        artwork_hash = hashlib.md5(art_url.encode()).hexdigest()

        if artwork_hash == self._current_artwork_hash:
            return

        self._current_artwork_hash = artwork_hash
        parsed = urllib.parse.urlparse(art_url)

        if parsed.scheme == "file":
            self._set_artwork(urllib.parse.unquote(parsed.path))
        elif parsed.scheme in ("http", "https"):
            GLib.Thread.new(
                "download-artwork",
                self._download_artwork,
                art_url,
                artwork_hash,
            )

    def _set_artwork(self, path: str):
        self._current_artwork_path = path
        self.artwork_change(path)

    def _download_artwork(self, art_url: str, artwork_hash: str):
        if self._is_cleaning_up:
            return
        try:
            cache_dir = TEMP_DIR / "player-art"
            cache_dir.mkdir(parents=True, exist_ok=True)

            filename_hash = hashlib.md5(art_url.encode()).hexdigest()
            parsed = urllib.parse.urlparse(art_url)

            local_arturl = None
            url_suffix = Path(parsed.path).suffix
            if url_suffix:
                test_path = cache_dir / f"{filename_hash}{url_suffix}"
                if test_path.exists():
                    local_arturl = test_path
            else:
                existing = list(cache_dir.glob(f"{filename_hash}.*"))
                if existing:
                    local_arturl = existing[0]

            if not local_arturl:
                with urllib.request.urlopen(art_url, timeout=5) as response:
                    data = response.read()
                    suffix = mimetypes.guess_extension(
                        response.info().get_content_type()
                    ) or ".png"
                    local_arturl = cache_dir / f"{filename_hash}{suffix}"
                    tmp = local_arturl.with_suffix(".tmp")
                    tmp.write_bytes(data)
                    tmp.replace(local_arturl)

            GLib.idle_add(self._set_artwork, str(local_arturl))

        except Exception as e:
            logger.error(f"Failed to download artwork: {e}")

    def cleanup(self):
        if self._is_cleaning_up:
            return
        self._is_cleaning_up = True

        try:
            if hasattr(self, "pos_fabricator"):
                self.pos_fabricator.stop()
        except Exception as e:
            logger.error(f"Error stopping fabricator: {e}")

        for signal_id in self._signal_ids:
            try:
                self._player.disconnect(signal_id)
            except Exception as e:
                logger.warning(f"Error disconnecting signal: {e}")
        self._signal_ids.clear()
        self._current_artwork_path = ""

class PlayerManager(Service):
    _instance = None

    @Signal
    def new_player(self, player_name: str, service: PlayerService) -> None: ...

    @Signal
    def player_vanish(self, player_name: str) -> None: ...

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._init_singleton()
        return cls._instance

    def _init_singleton(self):
        super().__init__()
        self._manager = Playerctl.PlayerManager()
        self._services: dict[str, PlayerService] = {}
        self._player_objects: dict[str, Playerctl.Player] = {}

        self._manager.connect("name-appeared", self._on_name_appeared, self._manager)
        self._manager.connect("player-vanished", self._on_player_vanished, self._manager)
        self._init_existing_players()

    def _init_existing_players(self):
        for player_obj in self._manager.props.player_names:
            self._create_player(player_obj)

    def _create_player(self, name_obj):
        name_str = name_obj.name
        if name_str in self._services:
            return
        try:
            player = Playerctl.Player.new_from_name(name_obj)
            self._manager.manage_player(player)
            service = PlayerService(player)
            self._services[name_str] = service
            self._player_objects[name_str] = player
            self.new_player(name_str, service)
        except Exception as e:
            logger.error(f"Failed to create player {name_str}: {e}")

    def _on_name_appeared(self, sender, name, manager):
        self._create_player(name)

    def _on_player_vanished(self, sender, player, manager):
        name = player.props.player_name
        if name in self._services:
            self._services[name].cleanup()
            del self._services[name]
        self._player_objects.pop(name, None)
        self.player_vanish(name)

    def get_player_service(self, name: str) -> PlayerService | None:
        return self._services.get(name)

    def get_all_services(self) -> dict[str, PlayerService]:
        return self._services.copy()