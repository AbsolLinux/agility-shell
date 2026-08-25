from fabric.widgets.box import Box
from fabric.widgets.label import Label
from fabric.widgets.button import Button
from fabric.widgets.entry import Entry
from fabric.widgets.scrolledwindow import ScrolledWindow
from snippets import Icon, Applet, AppletPage
from services.singletons import clipboard
from gi.repository import Gtk, Gdk, GLib

class ClipboardItem(Button):
    def __init__(self, item: dict, on_copy):
        self._item = item
        self._on_copy = on_copy

        text_label = Label(
            label=item["preview"],
            h_align="start",
            ellipsize=True,
            max_chars_width=28,
            style="font-size: 13px;",
        )

        time_label = Label(
            label=item["timestamp"],
            h_align="end",
            style="font-size: 11px; opacity: 0.6;",
        )

        copy_icon = Icon(icon_name="clipboard-text-duotone", icon_size=16)

        inner = Box(
            orientation="h",
            spacing=8,
            children=[
                copy_icon,
                text_label,
                Box(h_expand=True),
                time_label,
            ],
        )

        super().__init__(
            style_classes=["menu-device-item", "clipboard-item"],
            child=inner,
            on_clicked=lambda *_: self._copy(),
        )

    def _copy(self):
        clipboard.copy_text(self._item["text"])
        self._on_copy(self)


class ClipboardApplet(Applet):
    def __init__(self, parent, **kwargs):
        self._search_entry = Entry(
            placeholder="Search clipboard...",
            style_classes=["dash-search-entry", "clipboard-search"],
            h_expand=True,
        )
        self._search_entry.connect("notify::text", self._on_search_changed)

        self._clear_btn = Button(
            style_classes=["applet-misc-button"],
            child=Icon(icon_name="trash-duotone", icon_size=16),
            on_clicked=lambda *_: clipboard.clear(),
        )

        search_row = Box(
            orientation="h",
            spacing=8,
            children=[self._search_entry, self._clear_btn],
        )

        self._list_box = Box(
            orientation="v",
            spacing=6,
            h_expand=True,
        )

        self._placeholder = Box(
            style_classes=["menu-list-placeholder"],
            h_expand=True,
            v_expand=True,
            children=[
                Label(
                    label="Clipboard is empty",
                    style="font-size: 13px; opacity: 0.7; padding: 24px 0;",
                    h_align="center",
                    v_align="center",
                )
            ],
        )

        self._scroll = ScrolledWindow(
            min_content_height=260,
            max_content_height=320,
            h_expand=True,
            v_expand=True,
            child=self._list_box,
        )

        content = Box(
            orientation="v",
            spacing=10,
            children=[
                search_row,
                self._scroll,
                self._placeholder,
            ],
        )

        super().__init__(
            main_menu=AppletPage(first=True, title="Clipboard", child=content),
            **kwargs,
        )

        clipboard.connect("changed", self._refresh)
        clipboard.connect("notify::history", self._refresh)
        self._refresh()

    def _on_search_changed(self, *_):
        self._refresh()

    def _refresh(self, *_):
        query = (self._search_entry.get_text() or "").strip().lower()
        items = clipboard.history

        if query:
            items = [it for it in items if query in it["text"].lower()]

        for child in self._list_box.get_children():
            self._list_box.remove(child)

        if items:
            self._placeholder.set_visible(False)
            self._scroll.set_visible(True)
            for it in items:
                self._list_box.add(ClipboardItem(it, on_copy=self._on_item_copied))
            self._list_box.show_all()
        else:
            self._scroll.set_visible(False)
            self._placeholder.set_visible(True)

    def _on_item_copied(self, item_widget):
        item_widget.add_style_class("active")
        GLib.timeout_add(300, lambda: item_widget.remove_style_class("active") if item_widget else False)
