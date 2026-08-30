from fabric.widgets.label import Label
from snippets import Icon
from .button import QSButton


class ScreenshotButton(QSButton):
    def __init__(self, stack):
        super().__init__(
            icon=Icon(
                icon_name="camera-duotone",
                icon_size=16,
            ),
            label=Label(
                label="Screenshot",
            ),
            menu_name="screenshot",
            stack=stack,
            on_activate=lambda _: stack.set_visible_child_name("screenshot"),
        )
