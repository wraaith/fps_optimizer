# desktop-app/app/ui/theme_manager.py

"""
Theme Manager — coordinates switching between 'Performance Mode' (ultra-clean,
minimalist stealth, pitch black) and 'Cyber Mode' (high-tech neon glowing gamer HUD
with custom Rajdhani typography and glowing card borders).
"""

from typing import Callable, Dict, List, Any
import customtkinter as ctk
from overlay.font_manager import FontManager

# Singleton font manager
_font_manager = FontManager()
_font_manager.auto_discover()

_cyber_mode: bool = True
_listeners: List[Callable[[bool], None]] = []


# ── Theme Palettes ───────────────────────────────────────────────────

PERFORMANCE_THEME: Dict[str, Any] = {
    "name": "performance",
    "is_cyber": False,
    # Backgrounds
    "bg_root": "#000000",
    "bg_sidebar": "#0a0a0a",
    "bg_main": "#050505",
    "bg_card": "#0a0a0a",
    "bg_card_inner": "#121212",
    "border_card": "#1e1e1e",
    "border_width": 0,
    "corner_radius": 8,
    # Text
    "text_title": "#ffffff",
    "text_primary": "#ffffff",
    "text_secondary": "#888888",
    "text_muted": "#555555",
    # Accents
    "accent_primary": "#ffffff",
    "accent_hover": "#e0e0e0",
    "accent_text": "#000000",
    "accent_cyan": "#ffffff",
    "accent_purple": "#cccccc",
    "accent_green": "#00ff00",
    "accent_amber": "#ffffff",
    # Buttons
    "nav_btn_fg": "transparent",
    "nav_btn_hover": "#1a1a1a",
    "nav_btn_text": "#ffffff",
    "action_btn_fg": "#ffffff",
    "action_btn_hover": "#e0e0e0",
    "action_btn_text": "#000000",
    # Font Families
    "font_family": "Segoe UI",
    "font_family_stat": "Segoe UI",
}

CYBER_THEME: Dict[str, Any] = {
    "name": "cyber",
    "is_cyber": True,
    # Backgrounds — true deep cyberpunk void layers
    "bg_root": "#04060e",
    "bg_sidebar": "#060919",
    "bg_main": "#050817",
    "bg_card": "#090e23",           # Sleek cyber frosted glass pane
    "bg_card_inner": "#0d1433",     # Inset telemetry chamber
    "bg_glass": "#141d47",          # Highlight layer
    "border_card": "#1a2b5e",       # Subtle frosted tech edge
    "border_glow": "#00f0ff",       # Electric neon cyan glow
    "border_purple": "#a855f7",     # Neon amethyst
    "border_pink": "#f43f5e",       # Cyber crimson
    "border_green": "#00ff9f",      # Radioactive mint
    "border_amber": "#fbbf24",      # Cyber gold
    "border_width": 1,
    "corner_radius": 14,
    # Text — high-contrast futuristic tech typography
    "text_title": "#00f0ff",
    "text_primary": "#f0f4ff",
    "text_secondary": "#8193b8",
    "text_muted": "#47567d",
    # Accents
    "accent_primary": "#00f0ff",
    "accent_hover": "#38bdf8",
    "accent_text": "#020617",
    "accent_cyan": "#00f0ff",
    "accent_purple": "#c084fc",
    "accent_green": "#00ff9f",
    "accent_amber": "#fbbf24",
    "accent_crimson": "#f43f5e",
    # Buttons
    "nav_btn_fg": "transparent",
    "nav_btn_hover": "#0e183a",
    "nav_btn_text": "#8193b8",
    "nav_btn_active_fg": "#0d183d",
    "nav_btn_active_text": "#00f0ff",
    "nav_btn_active_border": "#00f0ff",
    "action_btn_fg": "#00f0ff",
    "action_btn_hover": "#38bdf8",
    "action_btn_text": "#020617",
    # Font Families
    "font_family": "Rajdhani",
    "font_family_stat": "Rajdhani",
}


_font_cache: Dict[tuple, ctk.CTkFont] = {}


def is_cyber_mode() -> bool:
    """Return True if Cyber Mode is active."""
    return _cyber_mode


def set_cyber_mode(enabled: bool) -> None:
    """Toggle between Cyber Mode and Performance Mode."""
    global _cyber_mode
    if _cyber_mode != enabled:
        _cyber_mode = enabled
        _font_cache.clear()  # Font family changes between modes
        _notify_listeners()


def get_theme() -> Dict[str, Any]:
    """Get the active theme dictionary."""
    return CYBER_THEME if _cyber_mode else PERFORMANCE_THEME


def get_font(size: int = 14, weight: str = "bold", is_stat: bool = False) -> ctk.CTkFont:
    """Return a cached CTkFont based on current theme mode."""
    theme = get_theme()
    family = theme["font_family_stat"] if is_stat else theme["font_family"]
    key = (family, size, weight)
    if key not in _font_cache:
        _font_cache[key] = ctk.CTkFont(family=family, size=size, weight=weight)
    return _font_cache[key]


def on_theme_changed(listener: Callable[[bool], None]) -> None:
    """Register a callback that fires whenever the mode changes."""
    if listener not in _listeners:
        _listeners.append(listener)


def _notify_listeners() -> None:
    for listener in _listeners:
        try:
            listener(_cyber_mode)
        except Exception:
            pass
