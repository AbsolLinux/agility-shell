from .battery import DesktopBattery
from .clock import DesktopClock
from .date import DesktopDate
from .media import DesktopMediaApplet
from .system import DesktopSystem
from .weather import DesktopWeather

__all__ = [
    "DesktopBattery",
    "DesktopClock",
    "DesktopDate",
    "DesktopMediaApplet",
    "DesktopSystem",
    "DesktopWeather",
    "DESKTOP_APPLET_WIDGETS",
    "DESKTOP_APPLET_SIZES",
]

DESKTOP_APPLET_SIZES: dict[str, int] = {
    "Energy":    1,
    "Clock":     1,
    "Calendar":  1,
    "Media":     2,
    "Processes": 1,
    "Weather":   2,
}
DESKTOP_CANVAS_SIZES: dict[str, tuple[int, int]] = {
    "Energy":    (1, 1),
    "Clock":     (1, 1),
    "Calendar":  (1, 1),
    "Media":     (2, 1),
    "Processes": (1, 1),
    "Weather":   (2, 1),
}
DESKTOP_APPLET_WIDGETS: dict[str, type] = {
    "Energy":    DesktopBattery,
    "Clock":     DesktopClock,
    "Calendar":  DesktopDate,
    "Media":     DesktopMediaApplet,
    "Processes": DesktopSystem,
    "Weather":   DesktopWeather,
}