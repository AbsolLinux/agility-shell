from .base import BaseButton, VARIANT_ICON, VARIANT_ICON_LABEL, VARIANT_LABEL
from snippets import Icon
from services.singletons import caffeine

class CaffeineButton(BaseButton):
    VARIANTS = [VARIANT_ICON, VARIANT_ICON_LABEL, VARIANT_LABEL]

    def __init__(self, monitor_id, vertical, variant=None, **kwargs):
        self._icon_widget = Icon(icon_name="coffee-duotone", icon_size=16)
        super().__init__(
            icon=self._icon_widget,
            label="Awake",
            variant=variant or VARIANT_ICON,
            **kwargs,
        )
        self.connect("button-release-event", self._on_click)
        caffeine.connect("notify::enabled", self._sync)
        self._sync()

    def _on_click(self, widget, event):
        if event.button == 1:
            caffeine.toggle()
            return True
        return False

    def _sync(self, *_):
        is_active = caffeine.enabled
        for cls in ("caffeine-on", "active"):
            self.remove_style_class(cls)
            child = self.get_child()
            if child:
                child.remove_style_class(cls)

        if is_active:
            self.add_style_class("caffeine-on")
            self.add_style_class("active")
            child = self.get_child()
            if child:
                child.add_style_class("caffeine-on")
                child.add_style_class("active")
            self._update_label("Awake")
        else:
            self._update_label("Normal")
