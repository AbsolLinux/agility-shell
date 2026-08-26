import re
from gi.repository import Gtk
from fabric.widgets.box import Box
from fabric.widgets.label import Label
from fabric.widgets.button import Button
from snippets import Icon

class DesktopCalculator(Box):
    def __init__(self, **kwargs):
        self.expression = "0"
        self.showing_result = False

        self.expression_label = Label(
            label="0",
            v_expand=True,
            v_align="end",
            h_expand=True,
            h_align="end",
            style="font-size: 20px; font-weight: 700; font-family: apply(mixed-mono);",
        )
        self.preview_label = Label(
            label="",
            v_expand=True,
            v_align="start",
            h_expand=True,
            h_align="end",
            style="font-size: 11px; opacity: 0.6; font-family: apply(mixed-mono);",
        )

        display_box = Box(
            orientation="v",
            spacing=2,
            style_classes=["desktop-system-module"],
            children=[self.preview_label, self.expression_label],
        )

        buttons = [
            [("C", "C"), ("%", "%"), ("÷", "/"), ("⌫", "back")],
            [("7", "7"), ("8", "8"), ("9", "9"), ("×", "*")],
            [("4", "4"), ("5", "5"), ("6", "6"), ("-", "-")],
            [("1", "1"), ("2", "2"), ("3", "3"), ("+", "+")],
            [("0", "0"), (".", "."), ("=", "=")],
        ]

        grid_box = Box(orientation="v", spacing=4, h_expand=True)
        for row in buttons:
            row_box = Box(orientation="h", spacing=4, h_expand=True)
            for label_text, val in row:
                btn = Button(
                    child=Label(label=label_text, style="font-size: 12px; font-weight: 600;"),
                    style_classes=["option-selection-button"] + (["active"] if val == "=" else []),
                    h_expand=True,
                    on_clicked=lambda _, v=val: self._on_btn(v),
                )
                row_box.add(btn)
            grid_box.add(row_box)

        super().__init__(
            orientation="v",
            spacing=8,
            style_classes=["desktop-applet"],
            h_expand=True,
            v_expand=True,
            children=[display_box, grid_box],
            **kwargs,
        )

    def _on_btn(self, val: str):
        if val == "C":
            self.expression = "0"
            self.showing_result = False
        elif val == "back":
            if self.showing_result or len(self.expression) <= 1:
                self.expression = "0"
                self.showing_result = False
            else:
                self.expression = self.expression[:-1]
        elif val == "=":
            self._calculate()
        elif val in ("+", "-", "*", "/"):
            self.showing_result = False
            if self.expression[-1:] in ("+", "-", "*", "/"):
                self.expression = self.expression[:-1] + val
            else:
                self.expression += val
        else:
            if self.expression == "0" or self.showing_result:
                self.expression = val
                self.showing_result = False
            else:
                self.expression += val
        self._update_ui()

    def _calculate(self):
        try:
            expr = self.expression.replace("×", "*").replace("÷", "/")
            # Safe eval with restricted characters
            clean_expr = re.sub(r"[^0-9\+\-\*\/\.\%\(\)]", "", expr)
            res = eval(clean_expr, {"__builtins__": None}, {})
            if isinstance(res, float) and res.is_integer():
                res = int(res)
            self.preview_label.set_label(self.expression + " =")
            self.expression = str(res)
            self.showing_result = True
        except Exception:
            self.expression = "Error"
            self.showing_result = True

    def _update_ui(self):
        disp = self.expression.replace("*", "×").replace("/", "÷")
        self.expression_label.set_label(disp)
        if not self.showing_result:
            try:
                expr = self.expression.replace("×", "*").replace("÷", "/")
                clean_expr = re.sub(r"[^0-9\+\-\*\/\.\%\(\)]", "", expr)
                res = eval(clean_expr, {"__builtins__": None}, {})
                if isinstance(res, float) and res.is_integer():
                    res = int(res)
                self.preview_label.set_label(f"= {res}")
            except Exception:
                self.preview_label.set_label("")
