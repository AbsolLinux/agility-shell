DESKTOP_APPLET_SIZES: dict[str, int] = {
    "Energy":        1,
    "Clock":         1,
    "Calendar":      1,
    "Media":         2,
    "Processes":     1,
    "Weather":       2,
    "SysMon":        1,
    "Wifi":          1,
    "Volume":        1,
    "Brightness":    1,
    "Caffeine":      1,
    "NightLight":    1,
    "Bluetooth":     1,
    "Clipboard":     1,
    "Calculator":    1,
    "Settings":      1,
}

DESKTOP_CANVAS_SIZES: dict[str, tuple[int, int]] = {
    "Energy":        (1, 1),
    "Clock":         (1, 1),
    "Calendar":      (1, 1),
    "Media":         (2, 1),
    "Processes":     (1, 1),
    "Weather":       (2, 1),
    "SysMon":        (1, 1),
    "Wifi":          (1, 1),
    "Volume":        (1, 1),
    "Brightness":    (1, 1),
    "Caffeine":      (1, 1),
    "NightLight":    (1, 1),
    "Bluetooth":     (1, 1),
    "Clipboard":     (1, 1),
    "Calculator":    (1, 1),
    "Settings":      (1, 1),
}

from .battery import DesktopBattery
from .clock import DesktopClock
from .date import DesktopDate
from .media import DesktopMediaApplet
from .system import DesktopSystem
from .weather import DesktopWeather
from .sysmon import DesktopSysMon
from .network import DesktopNetwork
from .volume import DesktopVolume
from .brightness import DesktopBrightness
from .caffeine import DesktopCaffeine
from .nightlight import DesktopNightLight
from .bluetooth import DesktopBluetooth
from .clipboard import DesktopClipboard
from .calculator import DesktopCalculator
from .quick_settings import DesktopQuickSettings

__all__ = [
    "DesktopBattery",
    "DesktopClock",
    "DesktopDate",
    "DesktopMediaApplet",
    "DesktopSystem",
    "DesktopWeather",
    "DesktopSysMon",
    "DesktopNetwork",
    "DesktopVolume",
    "DesktopBrightness",
    "DesktopCaffeine",
    "DesktopNightLight",
    "DesktopBluetooth",
    "DesktopClipboard",
    "DesktopCalculator",
    "DesktopQuickSettings",
    "DESKTOP_APPLET_WIDGETS",
    "DESKTOP_APPLET_SIZES",
    "DESKTOP_CANVAS_SIZES",
]

DESKTOP_APPLET_WIDGETS: dict[str, type] = {
    "Energy":        DesktopBattery,
    "Clock":         DesktopClock,
    "Calendar":      DesktopDate,
    "Media":         DesktopMediaApplet,
    "Processes":     DesktopSystem,
    "Weather":       DesktopWeather,
    "SysMon":        DesktopSysMon,
    "Wifi":          DesktopNetwork,
    "Volume":        DesktopVolume,
    "Brightness":    DesktopBrightness,
    "Caffeine":      DesktopCaffeine,
    "NightLight":    DesktopNightLight,
    "Bluetooth":     DesktopBluetooth,
    "Clipboard":     DesktopClipboard,
    "Calculator":    DesktopCalculator,
    "Settings":      DesktopQuickSettings,
}