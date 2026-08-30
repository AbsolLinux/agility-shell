from .standalone_menus import AudioApplet, PowerApplet, KeyboardApplet, ScreenshotApplet, BluetoothApplet, WifiApplet, LogoutApplet
from .calculator import CalculatorApplet
from .calendar import CalendarApplet
from .launcher import LauncherApplet
from .clock import ClockApplet
from .process_monitor import ProcessMonitorApplet
from .notifications import NotificationWindow
from .notificationhistory import NotificationHistoryApplet
from .weather_popup import WeatherApplet
from .media import MediaApplet
from .quick_settings import QuickSettings
from .clipboard import ClipboardApplet
from .wallpaper_picker import WallpaperPicker
from .dash.dash import Dash
from .osd import OSD
__all__ = [
    "CalculatorApplet",
    "CalendarApplet",
    "LauncherApplet",
    "MediaApplet",
    "ClockApplet",
    "WeatherApplet",
    "NotificationWindow",
    "NotificationHistoryApplet",
    "ProcessMonitorApplet",
    "QuickSettings",
    "WifiApplet",
    "LogoutApplet",
    "Dash",
    "OSD",
    "ClipboardApplet",
    "WallpaperPicker",
    "AudioApplet",
    "PowerApplet",
    "KeyboardApplet",
    "ScreenshotApplet",
    "BluetoothApplet"
]
