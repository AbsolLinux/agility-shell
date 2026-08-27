from fabric.core.service import Service, Property, Signal


class WMWindow(Service):
    """
    Base class for a window across all supported WMs.

    Subclasses may expose extra WM-specific properties (e.g. NiriWindowLayout),
    but widgets should only depend on what's defined here.
    """

    @Signal
    def destroyed(self): ...

    @Property(int, "readable", default_value=-1)
    def id(self) -> int:
        return self._property_helper_id

    @Property(str, "readable", default_value="")
    def title(self) -> str:
        return self._property_helper_title or ""

    @Property(str, "readable", default_value="")
    def app_id(self) -> str:
        return self._property_helper_app_id or ""

    @Property(int, "readable", default_value=-1)
    def pid(self) -> int:
        return self._property_helper_pid

    @Property(int, "readable", default_value=-1)
    def workspace_id(self) -> int:
        return self._property_helper_workspace_id

    @Property(bool, "readable", default_value=False)
    def is_focused(self) -> bool:
        return self._property_helper_is_focused or False

    @Property(bool, "readable", default_value=False)
    def is_floating(self) -> bool:
        return self._property_helper_is_floating or False

    def __init__(self, **kwargs):
        self._property_helper_id = -1
        self._property_helper_title = ""
        self._property_helper_app_id = ""
        self._property_helper_pid = -1
        self._property_helper_workspace_id = -1
        self._property_helper_is_focused = False
        self._property_helper_is_floating = False
        super().__init__(**kwargs)

    def sort_key(self) -> tuple:
        """
        Used for ordering windows within a workspace in widgets.
        Override in subclasses to provide WM-specific ordering
        (e.g. Niri uses pos_in_scrolling_layout).
        """
        return (self.workspace_id, 0, 0)

    @property
    def data(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "app_id": self.app_id,
            "pid": self.pid,
            "workspace_id": self.workspace_id,
            "is_focused": self.is_focused,
            "is_floating": self.is_floating,
        }

    def sync(self, data: dict) -> None:
        mapping = {
            "id": "id",
            "title": "title",
            "app_id": "app-id",
            "pid": "pid",
            "workspace_id": "workspace-id",
            "is_focused": "is-focused",
            "is_floating": "is-floating",
        }
        for key, notify_name in mapping.items():
            if key in data:
                old_val = getattr(self, f"_property_helper_{key}", None)
                new_val = data[key]
                if old_val != new_val:
                    setattr(self, f"_property_helper_{key}", new_val)
                    self.notify(notify_name)

    def close(self) -> None:
        raise NotImplementedError

    def focus(self) -> None:
        raise NotImplementedError

    def toggle_fullscreen(self) -> None:
        raise NotImplementedError

    def toggle_floating(self) -> None:
        raise NotImplementedError
