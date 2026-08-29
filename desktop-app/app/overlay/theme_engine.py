"""
Theme Engine — define, register, and live-switch overlay theme presets.

Provides ``ThemePreset`` (a frozen dataclass describing every visual
property of the overlay) and ``ThemeEngine`` (the runtime manager that
holds the active preset and notifies subscribers on change).

Built-in presets:
    - ``minimalist_dark``  — clean, subdued, opaque overlay
    - ``vibrant_glass``    — frosted-glass acrylic with vivid accents

Usage::

    from overlay.font_manager import FontManager
    from overlay.theme_engine import ThemeEngine

    fm = FontManager()
    engine = ThemeEngine(font_manager=fm)
    engine.on_theme_changed(my_callback)

    engine.switch_theme("vibrant_glass")   # fires callback
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Callable, Dict, List, Optional

import customtkinter as ctk

from .font_manager import FontManager


# ── Theme Preset ─────────────────────────────────────────────────────

@dataclass(frozen=True)
class ThemePreset:
    """Immutable snapshot of every visual property for an overlay theme."""

    name: str

    # ── Colors ────────────────────────────────────────────────────
    bg_color: str            # Main background / frame color
    label_color: str         # Metric label text (e.g. "FPS:")
    value_color: str         # Metric value text (e.g. "144")
    accent_color: str        # Separator / highlight accent
    row_bg_color: str        # Per-row background (can match bg_color)

    # ── Typography ────────────────────────────────────────────────
    font_family: str         # e.g. "Rajdhani", "Segoe UI"
    label_size: int          # Point size for labels
    value_size: int          # Point size for values
    font_weight: str = "bold"

    # ── Transparency ──────────────────────────────────────────────
    bg_mode: str = "solid"   # "transparent" | "acrylic" | "mica" | "solid"
    bg_opacity: float = 0.90

    # ── Widget styling ────────────────────────────────────────────
    corner_radius: int = 8
    padding: tuple = (12, 12)
    row_spacing: int = 4
    border_width: int = 0
    border_color: str = "transparent"


# ── Built-in presets ─────────────────────────────────────────────────

MINIMALIST_DARK = ThemePreset(
    name="minimalist_dark",
    # Colors
    bg_color="#0d0d0d",
    label_color="#555555",
    value_color="#cccccc",
    accent_color="#333333",
    row_bg_color="#141414",
    # Typography
    font_family="Segoe UI",
    label_size=12,
    value_size=14,
    font_weight="bold",
    # Transparency
    bg_mode="solid",
    bg_opacity=0.92,
    # Widget styling
    corner_radius=8,
    padding=(10, 10),
    row_spacing=3,
    border_width=0,
    border_color="transparent",
)

VIBRANT_GLASS = ThemePreset(
    name="vibrant_glass",
    # Colors
    bg_color="#1a1a2e",
    label_color="#8888cc",
    value_color="#00ffaa",
    accent_color="#6c63ff",
    row_bg_color="#22223a",
    # Typography
    font_family="Rajdhani",
    label_size=13,
    value_size=15,
    font_weight="bold",
    # Transparency
    bg_mode="acrylic",
    bg_opacity=0.65,
    # Widget styling
    corner_radius=14,
    padding=(14, 14),
    row_spacing=5,
    border_width=1,
    border_color="#6c63ff",
)


# ── Theme Engine ─────────────────────────────────────────────────────

class ThemeEngine:
    """Runtime theme manager.

    Holds the active ``ThemePreset``, allows switching at runtime, and
    notifies all registered callbacks so that widgets can re-style
    themselves without being destroyed and recreated.
    """

    # Class-level preset registry (shared across instances)
    _presets: Dict[str, ThemePreset] = {
        "minimalist_dark": MINIMALIST_DARK,
        "vibrant_glass": VIBRANT_GLASS,
    }

    def __init__(
        self,
        font_manager: FontManager,
        initial_theme: str = "minimalist_dark",
    ) -> None:
        self._font_manager = font_manager
        self._callbacks: List[Callable[[ThemePreset], None]] = []

        name = initial_theme if initial_theme in self._presets else "minimalist_dark"
        self._current = self._presets[name]

        # Sync the font manager's active family to the theme
        self._font_manager.family = self._current.font_family

    # ── Properties ───────────────────────────────────────────────

    @property
    def current(self) -> ThemePreset:
        """Return the active theme preset."""
        return self._current

    @property
    def font_manager(self) -> FontManager:
        return self._font_manager

    @property
    def preset_names(self) -> List[str]:
        """Return a sorted list of available preset names."""
        return sorted(self._presets.keys())

    # ── Preset management ────────────────────────────────────────

    @classmethod
    def register_preset(cls, preset: ThemePreset) -> None:
        """Add (or replace) a named preset in the global registry."""
        cls._presets[preset.name] = preset

    @classmethod
    def get_preset(cls, name: str) -> Optional[ThemePreset]:
        """Retrieve a registered preset by name."""
        return cls._presets.get(name)

    # ── Theme switching ──────────────────────────────────────────

    def switch_theme(self, name: str) -> None:
        """Switch to a registered preset and notify listeners."""
        preset = self._presets.get(name)
        if preset is None:
            return

        self._current = preset
        self._font_manager.family = preset.font_family
        self._fire_callbacks()

    def apply_overrides(self, **overrides) -> None:
        """Create a *transient* preset from the current one with overrides.

        Useful when the user manually adjusts a single slider (e.g. opacity)
        without switching themes entirely.
        """
        data = asdict(self._current)
        data.update(overrides)
        # Build a new frozen preset
        self._current = ThemePreset(**data)
        self._font_manager.family = self._current.font_family
        self._fire_callbacks()

    # ── Callback system ──────────────────────────────────────────

    def on_theme_changed(self, callback: Callable[[ThemePreset], None]) -> None:
        """Register a callback that fires whenever the theme changes."""
        if callback not in self._callbacks:
            self._callbacks.append(callback)

    def remove_callback(self, callback: Callable[[ThemePreset], None]) -> None:
        """Unregister a previously added callback."""
        try:
            self._callbacks.remove(callback)
        except ValueError:
            pass

    def _fire_callbacks(self) -> None:
        for cb in self._callbacks:
            try:
                cb(self._current)
            except Exception:
                pass

    # ── Font helpers (delegates to FontManager) ──────────────────

    def make_label_font(self, size_override: Optional[int] = None) -> ctk.CTkFont:
        """Create a CTkFont for metric labels using the current theme."""
        size = size_override or self._current.label_size
        return ctk.CTkFont(
            family=self._current.font_family,
            size=size,
            weight=self._current.font_weight,
        )

    def make_value_font(self, size_override: Optional[int] = None) -> ctk.CTkFont:
        """Create a CTkFont for metric values using the current theme."""
        size = size_override or self._current.value_size
        return ctk.CTkFont(
            family=self._current.font_family,
            size=size,
            weight=self._current.font_weight,
        )
