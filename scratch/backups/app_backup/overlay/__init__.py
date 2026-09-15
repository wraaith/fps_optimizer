"""Overlay styling kit — fonts, themes, transparency, and widgets."""

from .font_manager import FontManager
from .metrics_collector import MetricsCollector
from .overlay_window import OverlayWindow
from .theme_engine import ThemeEngine, ThemePreset, MINIMALIST_DARK, VIBRANT_GLASS
from .transparency import apply_transparency, remove_transparency, get_available_modes
from .widget_templates import MetricRow, OverlayPanel, ThemeToggleButton
