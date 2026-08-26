from fabric.widgets.box import Box
from fabric.widgets.circularprogressbar import CircularProgressBar
from fabric.widgets.label import Label
from fabric.widgets.overlay import Overlay
from snippets import Icon
from services.singletons import sysmon

class DesktopSysMonModule(Box):
    def __init__(self, icon_name: str):
        self.progress_bar = CircularProgressBar(
            style_classes=["progress-bar"],
            start_angle=90,
            end_angle=450,
            size=(48, 48),
            line_width=3,
            min_value=0,
            max_value=100,
            value=0,
        )
        self.progress_overlay = Overlay(
            child=self.progress_bar,
            overlays=Icon(icon_name=icon_name, icon_size=24, h_align="center", v_align="center"),
        )
        self.top_label = Label(style_classes=["desktop-system-module-label", "top"], v_expand=True, v_align="end", h_align="start")
        self.bottom_label = Label(style_classes=["desktop-system-module-label", "bottom"], v_expand=True, v_align="start", h_align="start")
        super().__init__(
            style_classes=["desktop-system-module"],
            spacing=6,
            children=[
                self.progress_overlay,
                Box(
                    orientation="v",
                    children=[self.top_label, self.bottom_label],
                ),
            ]
        )


class DesktopSysMon(Box):
    def __init__(self):
        self.cpu_module = DesktopSysMonModule(icon_name="cpu-duotone")
        self.ram_module = DesktopSysMonModule(icon_name="chart-line-up-duotone")
        super().__init__(
            spacing=18,
            orientation="v",
            style_classes=["desktop-applet"],
            children=[self.cpu_module, self.ram_module]
        )
        sysmon.connect("changed", self._sync)
        self._sync()

    def _sync(self, *_):
        cpu_val = round(sysmon.cpu_usage)
        mem_val = round(sysmon.mem_usage)

        self.cpu_module.progress_bar.value = cpu_val
        self.cpu_module.top_label.set_label(f"{cpu_val}%")
        self.cpu_module.bottom_label.set_label("CPU Load")

        self.ram_module.progress_bar.value = mem_val
        self.ram_module.top_label.set_label(f"{mem_val}%")
        self.ram_module.bottom_label.set_label(f"{sysmon.mem_used_str}/{sysmon.mem_total_str}")
