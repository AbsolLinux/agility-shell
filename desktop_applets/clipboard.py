from gi.repository import Gtk, GLib
from fabric.widgets.box import Box
from fabric.widgets.label import Label
from fabric.widgets.button import Button
from snippets import Icon
from services.singletons import clipboard

class DesktopClipboard(Box):
    def __init__(self, **kwargs):
        self.icon = Icon(icon_name="clipboard-text-duotone", icon_size=20)
        self.title_label = Label(
            label="Clipboard",
            style="font-size: 13px; font-weight: 700;",
            h_align="start",
        )
        self.count_label = Label(
            label="0 items",
            style="font-size: 11px; opacity: 0.6;",
            h_align="end",
        )

        header = Box(
            orientation="h",
            spacing=8,
            h_align="fill",
            children=[
                self.icon,
                self.title_label,
                Box(h_expand=True),
                self.count_label,
            ],
        )

        self.items_box = Box(
            orientation="v",
            spacing=4,
            h_expand=True,
            v_expand=True,
        )

        super().__init__(
            orientation="v",
            spacing=8,
            style_classes=["desktop-applet"],
            h_expand=True,
            v_expand=True,
            children=[header, self.items_box],
            **kwargs,
        )

        clipboard.connect("changed", self._sync)
        self._sync()

    def _sync(self, *_):
        for child in self.items_box.get_children():
            self.items_box.remove(child)

        items = getattr(clipboard, "history", [])
        self.count_label.set_label(f"{len(items)} items")

        if not items:
            empty_lbl = Label(label="Clipboard is empty", style="font-size: 11px; opacity: 0.5;", v_align="center", v_expand=True)
            self.items_box.add(empty_lbl)
            self.items_box.show_all()
            return

        for item in items[:3]:
            text = item.get("text", "").strip()
            if not text:
                continue
            one_liner = text.replace("\n", " ")
            if len(one_liner) > 28:
                one_liner = one_liner[:26] + "…"

            btn = Button(
                child=Label(label=one_liner, style="font-size: 11px; font-weight: 500;", h_align="start", ellipsization="end"),
                style_classes=["option-selection-button"],
                h_expand=True,
                h_align="fill",
                on_clicked=lambda _, t=text: self._copy_item(t),
            )
            self.items_box.add(btn)

        self.items_box.show_all()

    def _copy_item(self, text: str):
        if hasattr(clipboard, "copy"):
            clipboard.copy(text)
        elif hasattr(clipboard, "set_text"):
            clipboard.set_text(text)
