"""Always-on-top, themeable FPS and hardware overlay.

Uses the overlay styling kit:
    - ``FontManager``       — custom TTF/OTF font registration
    - ``ThemeEngine``       — live theme switching (minimalist_dark / vibrant_glass)
    - ``OverlayPanel``      — rounded-corner metric row widgets
    - ``transparency``      — pywinstyles acrylic / mica / solid modes

The overlay can switch between themes at runtime without rebuilding
the widget tree.
"""

from __future__ import annotations

import ctypes
import ctypes.wintypes
import os
import platform
from typing import Optional

import customtkinter as ctk

from .font_manager import FontManager
from .metrics_collector import MetricsCollector
from .theme_engine import ThemeEngine, ThemePreset
from .transparency import apply_transparency, TRANSPARENT_COLOR_KEY
from .widget_templates import MetricRow, OverlayPanel

# ── DPI awareness ──────────────────────────────────────────────────────
# Must be called BEFORE any Tk window is created so Windows does not
# apply bitmap-scaling (the main cause of blurry overlay text).
try:
    # Per-Monitor DPI Aware (v2) – best quality on mixed-DPI setups
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except Exception:
    try:
        # Fallback: System DPI Aware
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass

# ── Win32 window style constants ─────────────────────────────────────
GWL_EXSTYLE = -20
WS_EX_TRANSPARENT = 0x00000020
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_LAYERED = 0x00080000
SWP_NOMOVE = 0x0002
SWP_NOSIZE = 0x0001
SWP_NOZORDER = 0x0004
SWP_NOACTIVATE = 0x0010
SWP_FRAMECHANGED = 0x0020
GA_ROOT = 2

if platform.system() == "Windows":
    user32 = ctypes.windll.user32
    user32.GetWindowLongW.argtypes = [ctypes.c_void_p, ctypes.c_int]
    user32.GetWindowLongW.restype = ctypes.c_long
    user32.SetWindowLongW.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_long]
    user32.SetWindowLongW.restype = ctypes.c_long
    user32.GetAncestor.argtypes = [ctypes.c_void_p, ctypes.c_uint]
    user32.GetAncestor.restype = ctypes.c_void_p
    user32.GetParent.argtypes = [ctypes.c_void_p]
    user32.GetParent.restype = ctypes.c_void_p
    user32.SetWindowPos.argtypes = [
        ctypes.c_void_p, ctypes.c_void_p,
        ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
        ctypes.c_uint
    ]
    user32.SetWindowPos.restype = ctypes.c_bool
else:
    user32 = None


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


class OverlayWindow(ctk.CTkToplevel):
    """Configurable, themeable overlay attached to an existing CTk root."""

    def __init__(self, master) -> None:
        super().__init__(master)

        self._closed = False
        self._settings = self._load_settings()

        # ── Font manager ─────────────────────────────────────────
        self._font_manager = FontManager()
        discovered = self._font_manager.auto_discover()
        if discovered:
            print(f"[Overlay] Loaded fonts: {', '.join(discovered)}")

        # ── Theme engine ─────────────────────────────────────────
        initial_theme = self._settings.get("theme", "minimalist_dark")
        self._theme_engine = ThemeEngine(
            font_manager=self._font_manager,
            initial_theme=initial_theme,
        )
        self._theme_engine.on_theme_changed(self._on_theme_changed)

        # ── Apply user overrides on top of the theme ─────────────
        self._apply_settings_overrides()

        # ── Metrics collector ────────────────────────────────────
        self.collector = MetricsCollector(
            target_process=self._settings.get("target_process") or None
        )

        # ── Window setup ─────────────────────────────────────────
        self.withdraw()
        self.title("FPS Overlay")
        self.overrideredirect(True)
        self.attributes("-topmost", True)

        try:
            self.wm_attributes("-toolwindow", True)
        except Exception:
            pass

        # ── Build UI ─────────────────────────────────────────────
        self._build_ui()
        self._apply_transparency()
        self._apply_visibility()

        # ── Show ─────────────────────────────────────────────────
        self.deiconify()
        self.lift()

        self.collector.start()
        self.after(150, self._apply_window_styles)
        self.after(300, self._update_metrics)
        self.protocol("WM_DELETE_WINDOW", self.close)

    # ── Settings ─────────────────────────────────────────────────

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
            "theme": os.getenv("FPS_OVERLAY_THEME", "minimalist_dark").lower(),
            "text_color": os.getenv("FPS_OVERLAY_TEXT_COLOR", ""),
            "bg_mode": os.getenv("FPS_OVERLAY_BG_MODE", ""),
            "bg_opacity": get_float("FPS_OVERLAY_BG_OPACITY", -1),
            "font_size": get_int("FPS_OVERLAY_FONT_SIZE", -1),
            "scale": get_float("FPS_OVERLAY_SCALE", 1.0),
            "position": os.getenv("FPS_OVERLAY_POSITION", "top-right").lower(),
            "layout": os.getenv("FPS_OVERLAY_LAYOUT", "vertical").lower(),
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

        settings["scale"] = max(0.8, min(2.0, settings["scale"]))
        return settings

    def _apply_settings_overrides(self) -> None:
        """If the user set explicit env-vars, override the theme defaults."""
        overrides = {}
        s = self._settings

        if s["text_color"]:
            overrides["value_color"] = s["text_color"]
        if s["bg_mode"]:
            overrides["bg_mode"] = s["bg_mode"]
        if s["bg_opacity"] >= 0:
            overrides["bg_opacity"] = max(0.0, min(1.0, s["bg_opacity"]))
        if s["font_size"] > 0:
            size = max(10, min(40, s["font_size"]))
            overrides["label_size"] = size
            overrides["value_size"] = size + 2

        if overrides:
            self._theme_engine.apply_overrides(**overrides)

    # ── UI construction ──────────────────────────────────────────

    def _build_ui(self) -> None:
        """Create the panel and the theme-toggle button."""
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # ── Overlay Panel ────────────────────────────────────────
        self._panel = OverlayPanel(
            self,
            preset=self._theme_engine.current,
            layout_mode=self._settings.get("layout", "vertical"),
        )
        self._panel.grid(row=0, column=0, sticky="nsew")

    def _apply_transparency(self) -> None:
        """Apply the current theme's transparency mode."""
        preset = self._theme_engine.current
        applied = apply_transparency(
            self,
            mode=preset.bg_mode,
            opacity=preset.bg_opacity,
            bg_color=preset.bg_color,
        )
        if applied != preset.bg_mode:
            print(
                f"[Overlay] Transparency '{preset.bg_mode}' unavailable, "
                f"fell back to '{applied}'"
            )

    def _apply_visibility(self) -> None:
        """Sync metric visibility from settings."""
        visibility = {
            key: self._settings.get(f"show_{key}", True)
            for key in self._panel.rows
        }
        self._panel.bulk_set_visibility(visibility)
        self.update_idletasks()
        self._update_position()

    # ── Theme switching ──────────────────────────────────────────

    def switch_theme(self, name: str) -> None:
        """Public method to switch the overlay theme at runtime."""
        self._theme_engine.switch_theme(name)

    def _on_theme_changed(self, preset: ThemePreset) -> None:
        """Callback fired by ThemeEngine — re-style everything in place."""
        # Re-theme the panel and all rows
        self._panel.apply_theme(preset)

        # Re-apply transparency for the new mode
        self._apply_transparency()

        # Update layout
        self.update_idletasks()
        self._update_position()
        self._apply_window_styles()

    # ── Position ─────────────────────────────────────────────────

    def _update_position(self) -> None:
        self.update_idletasks()
        width = self.winfo_reqwidth()
        height = self.winfo_reqheight()
        screen_w = self.winfo_screenwidth()
        screen_h = self.winfo_screenheight()
        margin = 20
        right_margin = 45  # Nudge further left for cleaner look
        taskbar = 60
        position = self._settings.get("position", "top-right")

        if position == "top-left":
            x, y = margin, margin
        elif position == "bottom-left":
            x, y = margin, max(margin, screen_h - height - taskbar)
        elif position == "bottom-right":
            x = max(margin, screen_w - width - right_margin)
            y = max(margin, screen_h - height - taskbar)
        else:
            x = max(margin, screen_w - width - right_margin)
            y = margin

        self.geometry(f"+{x}+{y}")

    # ── Window styles ────────────────────────────────────────────

    def _get_target_hwnds(self) -> list[int]:
        """Return HWNDs for both Tk's internal child window and the root OS window."""
        hwnds = []
        if not self.winfo_exists():
            return hwnds
        child = self.winfo_id()
        if child:
            hwnds.append(child)
            if user32 is not None:
                try:
                    root = user32.GetAncestor(child, GA_ROOT)
                    if root and root not in hwnds:
                        hwnds.append(root)
                except Exception:
                    pass
                try:
                    parent = user32.GetParent(child)
                    if parent and parent not in hwnds:
                        hwnds.append(parent)
                except Exception:
                    pass
        return hwnds

    def _apply_window_styles(self) -> None:
        if self._closed or not self.winfo_exists():
            return

        if user32 is None:
            return

        is_click_through = self._settings.get("click_through", True)
        hwnds = self._get_target_hwnds()

        for hwnd in hwnds:
            try:
                style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
                style |= WS_EX_TOOLWINDOW

                if is_click_through:
                    # Windows requires both WS_EX_LAYERED and WS_EX_TRANSPARENT for mouse click-through
                    style |= (WS_EX_LAYERED | WS_EX_TRANSPARENT)
                else:
                    style &= ~WS_EX_TRANSPARENT

                user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style)
                user32.SetWindowPos(
                    hwnd, 0, 0, 0, 0, 0,
                    SWP_NOMOVE | SWP_NOSIZE | SWP_NOZORDER | SWP_NOACTIVATE | SWP_FRAMECHANGED
                )
            except Exception:
                pass

        self.attributes("-topmost", True)
        self.lift()

    # ── Metrics update loop ──────────────────────────────────────

    # Pre-built mapping: metric_key → (snapshot_key, suffix)
    # Avoids rebuilding a dict and calling _fmt() with suffix arg every tick.
    _METRIC_MAP = (
        ("fps",      "fps",         ""),
        ("gpu",      "gpu_usage",   "%"),
        ("gpu_temp", "gpu_temp",    "°C"),
        ("gpu_pwr",  "gpu_power_w", "W"),
        ("cpu",      "cpu_usage",   "%"),
        ("cpu_temp", "cpu_temp",    "°C"),
        ("cpu_pwr",  "cpu_power_w", "W"),
        ("ram",      "ram_usage",   "%"),
    )

    def _update_metrics(self) -> None:
        if self._closed or not self.winfo_exists():
            return

        try:
            data = self.collector.snapshot
            preset = self._theme_engine.current
            panel = self._panel
            for widget_key, data_key, suffix in self._METRIC_MAP:
                panel.set_value(widget_key, _fmt(data.get(data_key), suffix), color=preset.value_color)

            # Re-position if the text expansion caused the window to grow (prevents spilling off-screen in horizontal mode)
            current_req_width = self.winfo_reqwidth()
            current_req_height = self.winfo_reqheight()
            if getattr(self, "_last_req_width", 0) != current_req_width or getattr(self, "_last_req_height", 0) != current_req_height:
                self._last_req_width = current_req_width
                self._last_req_height = current_req_height
                self._update_position()
        except Exception:
            pass
        finally:
            if not self._closed and self.winfo_exists():
                self.after(500, self._update_metrics)

    # ── Cleanup ──────────────────────────────────────────────────

    def close(self) -> None:
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