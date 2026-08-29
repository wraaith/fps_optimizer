"""
Widget Templates — reusable, theme-aware CustomTkinter overlay widgets.

Provides:
    - ``MetricRow``    — a single label + value row with rounded background
    - ``OverlayPanel`` — container for multiple ``MetricRow`` instances
    - ``ThemeToggleButton`` — small button to cycle themes

Every widget exposes an ``apply_theme(preset)`` method for live re-styling
without destroying and recreating the widget tree.
"""

from __future__ import annotations

from typing import Callable, Dict, List, Optional, Tuple

import customtkinter as ctk

from .theme_engine import ThemePreset


# ── Font cache ───────────────────────────────────────────────────────
# CTkFont objects hold Tk resources.  Creating identical fonts repeatedly
# wastes memory and triggers unnecessary Tk internal work.  This module-
# level cache ensures at most one CTkFont per (family, size, weight).

_font_cache: Dict[Tuple[str, int, str], ctk.CTkFont] = {}


def _get_font(family: str, size: int, weight: str) -> ctk.CTkFont:
    """Return a cached CTkFont, creating one only if needed."""
    key = (family, size, weight)
    font = _font_cache.get(key)
    if font is None:
        font = ctk.CTkFont(family=family, size=size, weight=weight)
        _font_cache[key] = font
    return font


# ── MetricRow ────────────────────────────────────────────────────────

class MetricRow(ctk.CTkFrame):
    """A single overlay metric row: ``[label:  value]``.

    The row is drawn inside a rounded ``CTkFrame`` whose visual properties
    (colours, radius, font) are fully driven by a ``ThemePreset``.
    """

    def __init__(
        self,
        parent,
        key: str,
        label_text: str,
        preset: ThemePreset,
        initial_value: str = "--",
        **kwargs,
    ) -> None:
        # CTkFrame does not accept the string "transparent" for border_color;
        # only pass border_color when border_width > 0.
        frame_kw = dict(
            corner_radius=preset.corner_radius,
            fg_color=preset.row_bg_color,
            border_width=preset.border_width,
        )
        if preset.border_width:
            frame_kw["border_color"] = preset.border_color
        frame_kw.update(kwargs)
        super().__init__(parent, **frame_kw)

        self.key = key
        self.grid_columnconfigure(1, weight=1)

        # Cache current text values for dirty-checking
        self._cur_label_text = f"{label_text}:"
        self._cur_value_text = initial_value
        self._cur_value_color: Optional[str] = None

        self._label = ctk.CTkLabel(
            self,
            text=self._cur_label_text,
            font=_get_font(preset.font_family, preset.label_size, preset.font_weight),
            text_color=preset.label_color,
            anchor="w",
        )
        self._label.grid(row=0, column=0, padx=(10, 6), pady=4, sticky="w")

        self._value = ctk.CTkLabel(
            self,
            text=initial_value,
            font=_get_font(preset.font_family, preset.value_size, preset.font_weight),
            text_color=preset.value_color,
            anchor="e",
        )
        self._value.grid(row=0, column=1, padx=(0, 10), pady=4, sticky="e")

    # ── Public API ───────────────────────────────────────────────

    def set_value(self, text: str, color: Optional[str] = None) -> None:
        """Update the displayed value only if it actually changed."""
        if text == self._cur_value_text and color == self._cur_value_color:
            return  # Nothing changed — skip the Tk configure() call

        if text != self._cur_value_text and color and color != self._cur_value_color:
            self._value.configure(text=text, text_color=color)
        elif text != self._cur_value_text:
            self._value.configure(text=text)
        elif color and color != self._cur_value_color:
            self._value.configure(text_color=color)

        self._cur_value_text = text
        self._cur_value_color = color

    def set_label(self, text: str) -> None:
        """Change the label text only if it actually changed."""
        if text == self._cur_label_text:
            return
        self._cur_label_text = text
        self._label.configure(text=text)

    def apply_theme(self, preset: ThemePreset) -> None:
        """Re-style this row to match *preset* — no widget recreation."""
        cfg = dict(
            corner_radius=preset.corner_radius,
            fg_color=preset.row_bg_color,
            border_width=preset.border_width,
        )
        if preset.border_width:
            cfg["border_color"] = preset.border_color
        self.configure(**cfg)
        # Use cached fonts — no new allocations if same params
        label_font = _get_font(preset.font_family, preset.label_size, preset.font_weight)
        value_font = _get_font(preset.font_family, preset.value_size, preset.font_weight)
        self._label.configure(font=label_font, text_color=preset.label_color)
        self._value.configure(font=value_font, text_color=preset.value_color)


# ── OverlayPanel ─────────────────────────────────────────────────────

class OverlayPanel(ctk.CTkFrame):
    """Container that manages a stack of ``MetricRow`` widgets.

    Handles visibility toggles and propagates theme changes to all rows.
    """

    # Default metric definitions: (key, label_text)
    DEFAULT_METRICS = [
        ("fps", "FPS"),
        ("gpu", "GPU"),
        ("gpu_temp", "GPU Temp"),
        ("gpu_pwr", "GPU Pwr"),
        ("cpu", "CPU"),
        ("cpu_temp", "CPU Temp"),
        ("cpu_pwr", "CPU Pwr"),
        ("ram", "RAM"),
    ]

    def __init__(
        self,
        parent,
        preset: ThemePreset,
        layout_mode: str = "vertical",
        metrics: Optional[List[tuple]] = None,
        **kwargs,
    ) -> None:
        super().__init__(
            parent,
            corner_radius=preset.corner_radius,
            fg_color=preset.bg_color,
            border_width=0,
            **kwargs,
        )

        self._preset = preset
        self._layout_mode = layout_mode
        self._rows: Dict[str, MetricRow] = {}
        self._visibility: Dict[str, bool] = {}
        self._layout_hash: Optional[tuple] = None  # Track current layout state

        metric_defs = metrics or self.DEFAULT_METRICS

        for key, label_text in metric_defs:
            row = MetricRow(
                self,
                key=key,
                label_text=label_text,
                preset=preset,
            )
            self._rows[key] = row
            self._visibility[key] = True

        self._relayout()

    # ── Public API ───────────────────────────────────────────────

    @property
    def rows(self) -> Dict[str, MetricRow]:
        """Return the internal ``{key: MetricRow}`` mapping."""
        return self._rows

    def set_value(self, key: str, text: str, color: Optional[str] = None) -> None:
        """Update a metric value by key."""
        row = self._rows.get(key)
        if row:
            row.set_value(text, color)

    def set_visibility(self, key: str, visible: bool) -> None:
        """Show or hide a metric row."""
        if key in self._visibility and self._visibility[key] != visible:
            self._visibility[key] = visible
            self._relayout()

    def bulk_set_visibility(self, visibility: Dict[str, bool]) -> None:
        """Set visibility for multiple keys at once."""
        changed = False
        for key, vis in visibility.items():
            if key in self._visibility and self._visibility[key] != vis:
                self._visibility[key] = vis
                changed = True
        if changed:
            self._relayout()

    def apply_theme(self, preset: ThemePreset) -> None:
        """Re-style the panel and all child rows."""
        self._preset = preset
        self.configure(
            corner_radius=preset.corner_radius,
            fg_color=preset.bg_color,
        )
        for row in self._rows.values():
            row.apply_theme(preset)
        # Force relayout since padding/spacing may have changed
        self._layout_hash = None
        self._relayout()

    # ── Internal ─────────────────────────────────────────────────

    def _relayout(self) -> None:
        """Re-grid visible rows and hide invisible ones.

        Skips the actual Tk grid calls if the layout hasn't changed.
        """
        # Build a hashable snapshot of the current visibility state + layout mode
        new_hash = (
            self._layout_mode,
            tuple((key, self._visibility.get(key, True)) for key in self._rows)
        )
        if new_hash == self._layout_hash:
            return  # Layout unchanged — skip all grid operations
        self._layout_hash = new_hash

        # Unmap everything first
        for row in self._rows.values():
            row.grid_forget()

        # Clear existing column weights from previous layouts
        for i in range(len(self._rows) + 1):
            self.grid_columnconfigure(i, weight=0)

        visible_keys = [k for k in self._rows if self._visibility.get(k, True)]
        
        if not visible_keys:
            # If nothing is visible, show a placeholder
            if "fps" in self._rows:
                self._rows["fps"].set_label("INFO:")
                self._rows["fps"].set_value("No metrics selected")
                self._rows["fps"].grid(
                    row=0,
                    column=0,
                    padx=self._preset.padding[0],
                    pady=(self._preset.row_spacing, 0),
                    sticky="ew",
                )
            self.grid_columnconfigure(0, weight=1)
            return

        # Restore FPS label if it was a placeholder
        if "fps" in self._rows:
            self._rows["fps"].set_label("FPS:")

        if self._layout_mode == "horizontal":
            for i, key in enumerate(visible_keys):
                # Only add left padding to the first item, only right padding to the last item.
                # Between items, use row_spacing.
                padx_left = self._preset.padding[0] if i == 0 else self._preset.row_spacing
                padx_right = self._preset.padding[0] if i == len(visible_keys) - 1 else 0
                
                self._rows[key].grid(
                    row=0,
                    column=i,
                    padx=(padx_left, padx_right),
                    pady=self._preset.padding[1],
                    sticky="ns",
                )
            self.grid_rowconfigure(0, weight=1)
        else:
            for i, key in enumerate(visible_keys):
                self._rows[key].grid(
                    row=i,
                    column=0,
                    padx=self._preset.padding[0],
                    pady=(self._preset.padding[1] if i == 0 else self._preset.row_spacing, 
                          self._preset.padding[1] if i == len(visible_keys) - 1 else 0),
                    sticky="ew",
                )
            self.grid_columnconfigure(0, weight=1)


# ── ThemeToggleButton ────────────────────────────────────────────────

class ThemeToggleButton(ctk.CTkButton):
    """Small floating button that cycles through available themes.

    Typically placed in the overlay when click-through is disabled.
    """

    def __init__(
        self,
        parent,
        theme_names: List[str],
        on_toggle: Callable[[str], None],
        preset: ThemePreset,
        **kwargs,
    ) -> None:
        self._theme_names = list(theme_names)
        self._current_index = 0
        self._on_toggle = on_toggle

        # Find current theme index
        for i, name in enumerate(self._theme_names):
            if name == preset.name:
                self._current_index = i
                break

        super().__init__(
            parent,
            text="🎨",
            width=32,
            height=32,
            corner_radius=16,
            font=_get_font("Segoe UI", 14, "normal"),
            fg_color=preset.accent_color,
            hover_color=preset.label_color,
            command=self._cycle,
            **kwargs,
        )

    def _cycle(self) -> None:
        self._current_index = (self._current_index + 1) % len(self._theme_names)
        next_theme = self._theme_names[self._current_index]
        self._on_toggle(next_theme)

    def apply_theme(self, preset: ThemePreset) -> None:
        """Re-style the button to match the current theme."""
        self.configure(
            fg_color=preset.accent_color,
            hover_color=preset.label_color,
        )
        # Update current index
        for i, name in enumerate(self._theme_names):
            if name == preset.name:
                self._current_index = i
                break
