from fabric.widgets.entry import Entry
import services.singletons as singletons


class StyleAwareEntry(Entry):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if singletons.style_service is not None:
            singletons.style_service.connect(
                "notify::style-changed", self._on_style_service_changed
            )

    def _on_style_service_changed(self, service, pspec):
        self.get_style_context().invalidate()
