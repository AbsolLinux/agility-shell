from .base import BaseButton, VARIANT_ICON, VARIANT_ICON_LABEL, VARIANT_LABEL
from snippets import Icon
from services.singletons import night_mode

class NightLightButton(BaseButton):
    VARIANTS = [VARIANT_ICON, VARIANT_ICON_LABEL, VARIANT_LABEL]

    def __init__(self, monitor_id, vertical, variant=None, **kwargs):
        self._icon_widget = Icon(icon_name="moon-stars-duotone", icon_size=16)
        super().__init__(
            icon=self._icon_widget,
            label="Night Light",
            variant=variant or VARIANT_ICON,
            **kwargs,
        )
        self.connect("button-release-event", self._on_click)
        night_mode.connect("notify::enabled", self._sync)
        self._sync()

    def _on_click(self, widget, event):
        if event.button == 1:
            night_mode.toggle()
            return True
        return False

    def _sync(self, *_):
        is_active = night_mode.enabled
        for cls in ("nightlight-on", "active"):
            self.remove_style_class(cls)
            child = self.get_child()
            if child:
                child.remove_style_class(cls)

        if is_active:
            self.add_style_class("nightlight-on")
            self.add_style_class("active")
            child = self.get_child()
            if child:
                child.add_style_class("nightlight-on")
                child.add_style_class("active")
            self._update_label("Night Mode")
        else:
            self._update_label("Normal")
