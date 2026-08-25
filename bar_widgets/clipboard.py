from .base import BaseButton, VARIANT_ICON, VARIANT_ICON_LABEL, VARIANT_LABEL
from snippets import Icon
from services.singletons import clipboard

class ClipboardButton(BaseButton):
    VARIANTS = [VARIANT_ICON, VARIANT_ICON_LABEL, VARIANT_LABEL]

    def __init__(self, monitor_id, vertical, variant=None, **kwargs):
        self._icon_widget = Icon(icon_name="clipboard-text-duotone", icon_size=16)
        super().__init__(
            icon=self._icon_widget,
            label="Clipboard",
            variant=variant or VARIANT_ICON,
            **kwargs,
        )
        clipboard.connect("changed", self._sync)
        self._sync()

    def _sync(self, *_):
        items = clipboard.history
        if items and items[0].get("text"):
            preview = items[0]["text"].replace("\n", " ").strip()
            if len(preview) > 12:
                preview = preview[:10] + "…"
            self._update_label(preview)
        else:
            self._update_label("Empty")
