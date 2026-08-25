from fabric.audio.service import Audio
from fabric.notifications import Notifications
from fabric.bluetooth.service import BluetoothClient
from fabric.power_profiles import PowerProfiles

from .wm import get_wm_service
from .battery import Battery
from .brightness import Brightness
from .edit_mode import EditMode
from .player import PlayerManager
from .network import NetworkClient
from .weather import Weather
from .idle import SwayidleService
from .timer import TimerService
from .processes import ProcessMonitorService
from .themes import ThemeService
from .night_mode import NightModeService
from .recorder import RecorderService
from .bluetooth import BluetoothClient
from .system_tray import SystemTray
from .clipboard import ClipboardService
from .caffeine import CaffeineService
from .sysmon import SysMonService
from user_options import user_options

bar_manager = None
style_service = None
toggleable_windows: dict[str, object] = {}
audio = Audio()
notifications = Notifications()
bluetooth = BluetoothClient()
player_manager = PlayerManager()
power_profiles = PowerProfiles()
theme_service = ThemeService()
wm = get_wm_service()
battery = Battery()
brightness = Brightness()
edit_mode = EditMode()
network = NetworkClient()
weather = Weather()
idle = SwayidleService(rules=user_options.timeouts.list)
timer = TimerService()
process_monitor = ProcessMonitorService()
night_mode = NightModeService()
recorder = RecorderService()
watcher = SystemTray()
clipboard = ClipboardService()
caffeine = CaffeineService()
sysmon = SysMonService()
idle.start()