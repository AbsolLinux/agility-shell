from .base import BaseButton, VARIANT_ICON, VARIANT_ICON_LABEL, VARIANT_LABEL
from snippets import Icon
from services.singletons import sysmon

class SysMonButton(BaseButton):
    VARIANTS = [VARIANT_ICON, VARIANT_ICON_LABEL, VARIANT_LABEL]

    def __init__(self, monitor_id, vertical, variant=None, **kwargs):
        self._icon_widget = Icon(icon_name="chart-line-up-duotone", icon_size=16)
        super().__init__(
            icon=self._icon_widget,
            label="0%",
            variant=variant or VARIANT_ICON_LABEL,
            **kwargs,
        )
        sysmon.connect("changed", self._sync)
        self._sync()

    def _sync(self, *_):
        cpu = round(sysmon.cpu_usage)
        mem = round(sysmon.mem_usage)
        self._update_label(f"CPU {cpu}% | RAM {mem}%")
