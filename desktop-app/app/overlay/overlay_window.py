"""
Lightweight always-on-top, click-through overlay window.

Uses raw tkinter (not customtkinter) to minimise memory / CPU.
Works best when games run in Borderless Windowed mode.
"""

import ctypes
import os
import tkinter as tk
from typing import Optional

from .metrics_collector import MetricsCollector


# ── Win32 constants ─────────────────────────────────────────────
GWL_EXSTYLE = -20
WS_EX_LAYERED = 0x00080000
WS_EX_TRANSPARENT = 0x00000020
WS_EX_TOOLWINDOW = 0x00000080

user32 = ctypes.windll.user32
user32.SetWindowLongW.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_long]
user32.SetWindowLongW.restype = ctypes.c_long
user32.GetWindowLongW.argtypes = [ctypes.c_void_p, ctypes.c_int]
user32.GetWindowLongW.restype = ctypes.c_long


# ── Default colours ─────────────────────────────────────────────
TRANSPARENT_KEY = "#010101"
DEFAULT_LABEL_COLOR = "#888888"
DEFAULT_VALUE_COLOR = "#e0e0e0"
ACCENT_GREEN = "#00e676"
ACCENT_YELLOW = "#ffd740"
ACCENT_RED = "#ff5252"


def _temp_color(val: Optional[float]) -> str:
    if val is None:
        return DEFAULT_VALUE_COLOR
    if val >= 85:
        return ACCENT_RED
    if val >= 70:
        return ACCENT_YELLOW
    return ACCENT_GREEN


def _usage_color(val: Optional[float]) -> str:
    if val is None:
        return DEFAULT_VALUE_COLOR
    if val >= 90:
        return ACCENT_RED
    if val >= 70:
        return ACCENT_YELLOW
    return ACCENT_GREEN


def _fps_color(val: Optional[float]) -> str:
    if val is None:
        return DEFAULT_VALUE_COLOR
    if val < 30:
        return ACCENT_RED
    if val < 60:
        return ACCENT_YELLOW
    return ACCENT_GREEN


def _fmt(val, suffix: str = "", decimals: int = 0) -> str:
    if val is None:
        return "--"
    try:
        num = float(val)
        if decimals == 0:
            if num.is_integer():
                return f"{int(num)}{suffix}"
            return f"{round(num)}{suffix}"
        return f"{num:.{decimals}f}{suffix}"
    except (TypeError, ValueError):
        return str(val)


class OverlayWindow(tk.Tk):
    def __init__(self):
        super().__init__()

        self.collector = MetricsCollector()
        self.settings = self._load_settings()

        self.title("FPS Overlay")
        self.overrideredirect(True)
        self.attributes("-topmost", True)
        self.wm_attributes("-toolwindow", True)

        self.configure(bg=TRANSPARENT_KEY)
        self.wm_attributes("-transparentcolor", TRANSPARENT_KEY)

        self._label_widgets = {}
        self._value_widgets = {}

        self._build_ui()
        self.apply_settings(self.settings)

        self.after(150, self._apply_window_styles)
        self.after(300, self._update_metrics)

    # ── Settings ────────────────────────────────────────────────

    def _load_settings(self):
        def get_bool(name: str, default: bool) -> bool:
            value = os.getenv(name)
            if value is None:
                return default
            return value.strip().lower() in ("1", "true", "yes", "on")

        def get_float(name: str, default: float) -> float:
            try:
                return float(os.getenv(name, default))
            except (TypeError, ValueError):
                return default

        def get_int(name: str, default: int) -> int:
            try:
                return int(float(os.getenv(name, default)))
            except (TypeError, ValueError):
                return default

        settings = {
            "text_color": os.getenv("FPS_OVERLAY_TEXT_COLOR", DEFAULT_VALUE_COLOR),
            "bg_mode": os.getenv("FPS_OVERLAY_BG_MODE", "transparent"),
            "bg_opacity": get_float("FPS_OVERLAY_BG_OPACITY", 0.35),
            "font_size": get_int("FPS_OVERLAY_FONT_SIZE", 18),
            "scale": get_float("FPS_OVERLAY_SCALE", 1.0),
            "position": os.getenv("FPS_OVERLAY_POSITION", "top-right"),
            "click_through": get_bool("FPS_OVERLAY_CLICK_THROUGH", True),
            "show_fps": get_bool("FPS_OVERLAY_SHOW_FPS", True),
            "show_gpu": get_bool("FPS_OVERLAY_SHOW_GPU", True),
            "show_cpu": get_bool("FPS_OVERLAY_SHOW_CPU", True),
            "show_ram": get_bool("FPS_OVERLAY_SHOW_RAM", True),
        }

        settings["bg_opacity"] = max(0.0, min(1.0, settings["bg_opacity"]))
        settings["font_size"] = max(10, min(40, settings["font_size"]))
        settings["scale"] = max(0.8, min(2.0, settings["scale"]))

        return settings

    # ── UI ──────────────────────────────────────────────────────

    def _build_ui(self):
        self.outer_frame = tk.Frame(
            self,
            bg=TRANSPARENT_KEY,
            bd=0,
            highlightthickness=0
        )
        self.outer_frame.pack(anchor="nw", padx=12, pady=12)

        self.content_frame = tk.Frame(
            self.outer_frame,
            bg=TRANSPARENT_KEY,
            bd=0,
            highlightthickness=0
        )
        self.content_frame.pack(anchor="nw")

        rows = [
            ("fps", "FPS"),
            ("gpu", "GPU"),
            ("cpu", "CPU"),
            ("ram", "RAM"),
        ]

        for row_index, (key, label_text) in enumerate(rows):
            label = tk.Label(
                self.content_frame,
                text=f"{label_text}:",
                font=("Segoe UI", 12, "bold"),
                fg=DEFAULT_LABEL_COLOR,
                bg=TRANSPARENT_KEY,
                anchor="w"
            )
            label.grid(row=row_index, column=0, sticky="w", padx=(0, 8), pady=2)

            value = tk.Label(
                self.content_frame,
                text="--",
                font=("Segoe UI", 12, "bold"),
                fg=self.settings["text_color"],
                bg=TRANSPARENT_KEY,
                anchor="w"
            )
            value.grid(row=row_index, column=1, sticky="w", pady=2)

            self._label_widgets[key] = label
            self._value_widgets[key] = value

    def apply_settings(self, settings: dict):
        self.settings = dict(settings)

        scaled_size = max(10, int(self.settings["font_size"] * self.settings["scale"]))
        label_font = ("Segoe UI", scaled_size, "bold")
        value_font = ("Segoe UI", scaled_size, "bold")

        if self.settings["bg_mode"] == "solid":
            bg_color = "#101010"
            self.configure(bg=bg_color)
            self.outer_frame.configure(bg=bg_color)
            self.content_frame.configure(bg=bg_color)
            try:
                self.wm_attributes("-transparentcolor", "")
            except Exception:
                pass
            try:
                self.wm_attributes("-alpha", self.settings["bg_opacity"])
            except Exception:
                pass
        else:
            bg_color = TRANSPARENT_KEY
            self.configure(bg=TRANSPARENT_KEY)
            self.outer_frame.configure(bg=TRANSPARENT_KEY)
            self.content_frame.configure(bg=TRANSPARENT_KEY)
            try:
                self.wm_attributes("-alpha", 1.0)
            except Exception:
                pass
            try:
                self.wm_attributes("-transparentcolor", TRANSPARENT_KEY)
            except Exception:
                pass

        for key in self._label_widgets:
            self._label_widgets[key].configure(
                font=label_font,
                bg=bg_color
            )
            self._value_widgets[key].configure(
                font=value_font,
                fg=self.settings["text_color"],
                bg=bg_color
            )

        self._apply_visibility()
        self.update_idletasks()
        self._update_position()
        self._apply_window_styles()

    def _apply_visibility(self):
        visibility = {
            "fps": self.settings.get("show_fps", True),
            "gpu": self.settings.get("show_gpu", True),
            "cpu": self.settings.get("show_cpu", True),
            "ram": self.settings.get("show_ram", True),
        }

        current_row = 0
        for key in ("fps", "gpu", "cpu", "ram"):
            label = self._label_widgets[key]
            value = self._value_widgets[key]

            if visibility.get(key, False):
                label.grid(row=current_row, column=0, sticky="w", padx=(0, 8), pady=2)
                value.grid(row=current_row, column=1, sticky="w", pady=2)
                current_row += 1
            else:
                label.grid_remove()
                value.grid_remove()

        if current_row == 0:
            self._label_widgets["fps"].grid(row=0, column=0, sticky="w", padx=(0, 8), pady=2)
            self._value_widgets["fps"].grid(row=0, column=1, sticky="w", pady=2)
            self._label_widgets["fps"].configure(text="INFO:")
            self._value_widgets["fps"].configure(text="No metrics selected")
        else:
            self._label_widgets["fps"].configure(text="FPS:")

    # ── Window placement / style ────────────────────────────────

    def _update_position(self):
        self.update_idletasks()

        width = self.winfo_reqwidth()
        height = self.winfo_reqheight()
        screen_w = self.winfo_screenwidth()
        screen_h = self.winfo_screenheight()

        margin = 20
        taskbar_adjust = 60
        position = self.settings.get("position", "top-right")

        if position == "top-left":
            x = margin
            y = margin
        elif position == "bottom-left":
            x = margin
            y = max(margin, screen_h - height - taskbar_adjust)
        elif position == "bottom-right":
            x = max(margin, screen_w - width - margin)
            y = max(margin, screen_h - height - taskbar_adjust)
        else:
            x = max(margin, screen_w - width - margin)
            y = margin

        self.geometry(f"+{x}+{y}")

    def _apply_window_styles(self):
        hwnd = self.winfo_id()
        style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)

        style |= WS_EX_TOOLWINDOW

        if self.settings.get("click_through", True):
            style |= WS_EX_TRANSPARENT
        else:
            style &= ~WS_EX_TRANSPARENT

        if self.settings.get("bg_mode") == "solid":
            style |= WS_EX_LAYERED

        user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style)

    # ── Metric refresh ──────────────────────────────────────────

    def _update_metrics(self):
        try:
            data = self.collector.get_metrics()
        except Exception:
            data = {}

        fps = self._pick(data, ["fps", "current_fps"])
        gpu = self._pick(data, ["gpu", "gpu_usage", "gpu_percent"])
        cpu = self._pick(data, ["cpu", "cpu_usage", "cpu_percent"])
        ram = self._pick(data, ["ram", "ram_usage", "ram_percent"])

        if "fps" in self._value_widgets:
            self._value_widgets["fps"].configure(
                text=_fmt(fps),
                fg=_fps_color(self._to_float(fps)) if self.settings.get("show_fps", True) else self.settings["text_color"]
            )

        if "gpu" in self._value_widgets:
            gpu_float = self._to_float(gpu)
            gpu_text = f"{_fmt(gpu_float)}%" if gpu_float is not None else _fmt(gpu)
            self._value_widgets["gpu"].configure(
                text=gpu_text,
                fg=_usage_color(gpu_float)
            )

        if "cpu" in self._value_widgets:
            cpu_float = self._to_float(cpu)
            cpu_text = f"{_fmt(cpu_float)}%" if cpu_float is not None else _fmt(cpu)
            self._value_widgets["cpu"].configure(
                text=cpu_text,
                fg=_usage_color(cpu_float)
            )

        if "ram" in self._value_widgets:
            ram_float = self._to_float(ram)
            ram_text = f"{_fmt(ram_float)}%" if ram_float is not None else _fmt(ram)
            self._value_widgets["ram"].configure(
                text=ram_text,
                fg=_usage_color(ram_float)
            )

        self.after(500, self._update_metrics)

    @staticmethod
    def _pick(data: dict, keys):
        for key in keys:
            if key in data:
                return data[key]
        return None

    @staticmethod
    def _to_float(value):
        try:
            if isinstance(value, str):
                value = value.replace("%", "").strip()
            return float(value)
        except (TypeError, ValueError):
            return None