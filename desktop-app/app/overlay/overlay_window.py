"""Always-on-top, configurable FPS and hardware overlay."""

import ctypes
import os
import tkinter as tk
from typing import Optional

from .metrics_collector import MetricsCollector

GWL_EXSTYLE = -20
WS_EX_TRANSPARENT = 0x00000020
WS_EX_TOOLWINDOW = 0x00000080

user32 = ctypes.windll.user32
user32.GetWindowLongW.argtypes = [ctypes.c_void_p, ctypes.c_int]
user32.GetWindowLongW.restype = ctypes.c_long
user32.SetWindowLongW.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_long]
user32.SetWindowLongW.restype = ctypes.c_long

TRANSPARENT_KEY = "#010101"
SOLID_BG_COLOR = "#1a1a2e"
DEFAULT_LABEL_COLOR = "#888888"
DEFAULT_VALUE_COLOR = "#e0e0e0"


def _fmt(value, suffix: str = "", decimals: int = 0) -> str:
    if value is None:
        return "--"
    try:
        number = float(value)
        if decimals == 0:
            return f"{int(number) if number.is_integer() else round(number)}{suffix}"
        return f"{number:.{decimals}f}{suffix}"
    except (TypeError, ValueError):
        return str(value)


class OverlayWindow(tk.Toplevel):
    """Configurable overlay attached to an existing Tk/CustomTkinter root."""

    def __init__(self, master):
        super().__init__(master)

        self._closed = False
        self._label_widgets = {}
        self._value_widgets = {}
        self.settings = self._load_settings()
        self.collector = MetricsCollector(
            target_process=self.settings.get("target_process") or None
        )

        self.withdraw()
        self.title("FPS Overlay")
        self.overrideredirect(True)
        self.attributes("-topmost", True)
        self.wm_attributes("-toolwindow", True)

        self._build_ui()
        self._apply_mode()
        self.deiconify()
        self.lift()

        self.collector.start()
        self.after(150, self._apply_window_styles)
        self.after(300, self._update_metrics)
        self.protocol("WM_DELETE_WINDOW", self.close)

    def _load_settings(self) -> dict:
        def get_bool(name: str, default: bool) -> bool:
            value = os.getenv(name)
            return default if value is None else value.strip().lower() in (
                "1", "true", "yes", "on"
            )

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
            "bg_mode": os.getenv("FPS_OVERLAY_BG_MODE", "transparent").lower(),
            "bg_opacity": get_float("FPS_OVERLAY_BG_OPACITY", 0.85),
            "font_size": get_int("FPS_OVERLAY_FONT_SIZE", 18),
            "scale": get_float("FPS_OVERLAY_SCALE", 1.0),
            "position": os.getenv("FPS_OVERLAY_POSITION", "top-right").lower(),
            "click_through": get_bool("FPS_OVERLAY_CLICK_THROUGH", True),
            "target_process": os.getenv("FPS_OVERLAY_TARGET_PROCESS", "").strip(),
            "show_fps": get_bool("FPS_OVERLAY_SHOW_FPS", True),
            "show_gpu": get_bool("FPS_OVERLAY_SHOW_GPU", True),
            "show_gpu_temp": get_bool("FPS_OVERLAY_SHOW_GPU_TEMP", True),
            "show_gpu_pwr": get_bool("FPS_OVERLAY_SHOW_GPU_PWR", True),
            "show_cpu": get_bool("FPS_OVERLAY_SHOW_CPU", True),
            "show_cpu_temp": get_bool("FPS_OVERLAY_SHOW_CPU_TEMP", True),
            "show_cpu_pwr": get_bool("FPS_OVERLAY_SHOW_CPU_PWR", True),
            "show_ram": get_bool("FPS_OVERLAY_SHOW_RAM", True),
        }

        settings["bg_opacity"] = max(0.0, min(1.0, settings["bg_opacity"]))
        settings["font_size"] = max(10, min(40, settings["font_size"]))
        settings["scale"] = max(0.8, min(2.0, settings["scale"]))
        return settings

    def _build_ui(self):
        self.outer_frame = tk.Frame(
            self, bg=TRANSPARENT_KEY, bd=0, highlightthickness=0
        )
        self.outer_frame.pack(anchor="nw", padx=12, pady=12)

        self.content_frame = tk.Frame(
            self.outer_frame, bg=TRANSPARENT_KEY, bd=0, highlightthickness=0
        )
        self.content_frame.pack(anchor="nw")

        rows = [
            ("fps", "FPS"),
            ("gpu", "GPU"),
            ("gpu_temp", "GPU Temp"),
            ("gpu_pwr", "GPU Pwr"),
            ("cpu", "CPU"),
            ("cpu_temp", "CPU Temp"),
            ("cpu_pwr", "CPU Pwr"),
            ("ram", "RAM"),
        ]

        for row, (key, title) in enumerate(rows):
            label = tk.Label(
                self.content_frame,
                text=f"{title}:",
                font=("Segoe UI", 12, "bold"),
                fg=DEFAULT_LABEL_COLOR,
                bg=TRANSPARENT_KEY,
                anchor="w",
            )
            label.grid(row=row, column=0, sticky="w", padx=(0, 8), pady=2)

            value = tk.Label(
                self.content_frame,
                text="--",
                font=("Segoe UI", 12, "bold"),
                fg=self.settings["text_color"],
                bg=TRANSPARENT_KEY,
                anchor="w",
            )
            value.grid(row=row, column=1, sticky="w", pady=2)

            self._label_widgets[key] = label
            self._value_widgets[key] = value

    def _apply_mode(self):
        size = max(10, int(self.settings["font_size"] * self.settings["scale"]))
        label_font = ("Segoe UI", size, "bold")
        value_font = ("Segoe UI", size, "bold")

        if self.settings["bg_mode"] == "solid":
            bg = SOLID_BG_COLOR
            self.configure(bg=bg)
            self.outer_frame.configure(bg=bg)
            self.content_frame.configure(bg=bg)
            self.wm_attributes("-alpha", max(0.75, self.settings["bg_opacity"]))
            self.wm_attributes("-transparentcolor", TRANSPARENT_KEY)
        else:
            bg = TRANSPARENT_KEY
            self.configure(bg=bg)
            self.outer_frame.configure(bg=bg)
            self.content_frame.configure(bg=bg)
            self.wm_attributes("-alpha", 1.0)
            self.wm_attributes("-transparentcolor", TRANSPARENT_KEY)

        for key in self._label_widgets:
            self._label_widgets[key].configure(font=label_font, bg=bg)
            self._value_widgets[key].configure(
                font=value_font,
                fg=self.settings["text_color"],
                bg=bg,
            )

        self._apply_visibility()
        self.update_idletasks()
        self._update_position()

    def _apply_visibility(self):
        visibility = {
            key: self.settings.get(f"show_{key}", True)
            for key in self._label_widgets
        }

        row = 0
        for key in self._label_widgets:
            label = self._label_widgets[key]
            value = self._value_widgets[key]

            if visibility[key]:
                label.grid(row=row, column=0, sticky="w", padx=(0, 8), pady=2)
                value.grid(row=row, column=1, sticky="w", pady=2)
                row += 1
            else:
                label.grid_remove()
                value.grid_remove()

        if row == 0:
            self._label_widgets["fps"].grid(
                row=0, column=0, sticky="w", padx=(0, 8), pady=2
            )
            self._value_widgets["fps"].grid(row=0, column=1, sticky="w", pady=2)
            self._label_widgets["fps"].configure(text="INFO:")
            self._value_widgets["fps"].configure(text="No metrics selected")
        else:
            self._label_widgets["fps"].configure(text="FPS:")

    def _update_position(self):
        self.update_idletasks()
        width = self.winfo_reqwidth()
        height = self.winfo_reqheight()
        screen_w = self.winfo_screenwidth()
        screen_h = self.winfo_screenheight()
        margin = 20
        taskbar = 60
        position = self.settings.get("position", "top-right")

        if position == "top-left":
            x, y = margin, margin
        elif position == "bottom-left":
            x, y = margin, max(margin, screen_h - height - taskbar)
        elif position == "bottom-right":
            x = max(margin, screen_w - width - margin)
            y = max(margin, screen_h - height - taskbar)
        else:
            x = max(margin, screen_w - width - margin)
            y = margin

        self.geometry(f"+{x}+{y}")

    def _apply_window_styles(self):
        if self._closed or not self.winfo_exists():
            return

        hwnd = self.winfo_id()
        style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
        style |= WS_EX_TOOLWINDOW

        if self.settings.get("click_through", True):
            style |= WS_EX_TRANSPARENT
        else:
            style &= ~WS_EX_TRANSPARENT

        user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style)
        self.attributes("-topmost", True)
        self.lift()

    def _update_metrics(self):
        if self._closed or not self.winfo_exists():
            return

        try:
            data = self.collector.snapshot
        except Exception:
            data = {}

        values = {
            "fps": (_fmt(data.get("fps")), ""),
            "gpu": (_fmt(data.get("gpu_usage"), "%"), ""),
            "gpu_temp": (_fmt(data.get("gpu_temp"), "°C"), ""),
            "gpu_pwr": (_fmt(data.get("gpu_power_w"), "W"), ""),
            "cpu": (_fmt(data.get("cpu_usage"), "%"), ""),
            "cpu_temp": (_fmt(data.get("cpu_temp"), "°C"), ""),
            "cpu_pwr": (_fmt(data.get("cpu_power_w"), "W"), ""),
            "ram": (_fmt(data.get("ram_usage"), "%"), ""),
        }

        for key, (text, _) in values.items():
            self._value_widgets[key].configure(
                text=text,
                fg=self.settings["text_color"],
            )

        self.after(500, self._update_metrics)

    def close(self):
        if self._closed:
            return

        self._closed = True

        try:
            self.collector.stop()
        except Exception:
            pass

        try:
            self.destroy()
        except Exception:
            pass
        os._exit(0)