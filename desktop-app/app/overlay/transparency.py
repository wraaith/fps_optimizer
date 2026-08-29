"""
Transparency — cross-platform window transparency via *pywinstyles*.

Wraps ``pywinstyles.apply_style()`` with graceful degradation so the
overlay works on every Windows version (and does nothing harmful on
Linux/macOS).

Supported modes:
    - ``"transparent"`` — colour-key transparency (any OS with Tk)
    - ``"acrylic"``     — frosted glass blur (Windows 10 1809+)
    - ``"mica"``        — wallpaper-tinted material (Windows 11 only)
    - ``"solid"``       — opaque background with alpha

Usage::

    from overlay.transparency import apply_transparency

    apply_transparency(my_window, mode="acrylic", opacity=0.65)
"""

from __future__ import annotations

import platform
from typing import Optional


# ── Lazy pywinstyles import ──────────────────────────────────────────

_pywinstyles = None
_pywinstyles_checked = False


def _get_pywinstyles():
    """Lazy-import pywinstyles; returns None if unavailable."""
    global _pywinstyles, _pywinstyles_checked
    if _pywinstyles_checked:
        return _pywinstyles
    _pywinstyles_checked = True
    try:
        import pywinstyles as _pw
        _pywinstyles = _pw
    except ImportError:
        _pywinstyles = None
    return _pywinstyles


# ── Transparent colour key ───────────────────────────────────────────

TRANSPARENT_COLOR_KEY = "#010101"


# ── Public API ───────────────────────────────────────────────────────

def apply_transparency(
    window,
    mode: str = "solid",
    opacity: float = 0.90,
    bg_color: str = "#0d0d0d",
) -> str:
    """Apply a transparency effect to *window*.

    Parameters
    ----------
    window : tk.Tk | tk.Toplevel | ctk.CTk | ctk.CTkToplevel
        The target window.
    mode : str
        One of ``"transparent"``, ``"acrylic"``, ``"mica"``, ``"solid"``.
    opacity : float
        Window opacity, 0.0 (invisible) to 1.0 (fully opaque).
    bg_color : str
        Background colour to set on the window when using solid/acrylic.

    Returns
    -------
    str
        The mode that was actually applied (may differ from *mode* if
        the requested mode isn't available on this platform).
    """
    mode = mode.lower().strip()
    opacity = max(0.0, min(1.0, opacity))
    is_windows = platform.system() == "Windows"
    pw = _get_pywinstyles() if is_windows else None

    # ── acrylic ──────────────────────────────────────────────────
    if mode == "acrylic":
        if pw is not None:
            try:
                pw.apply_style(window, "acrylic")
                window.configure(bg=bg_color)
                window.wm_attributes("-alpha", opacity)
                _try_header_color(pw, window, bg_color)
                return "acrylic"
            except Exception:
                pass
        # Fallback
        return _apply_solid(window, opacity, bg_color)

    # ── mica ─────────────────────────────────────────────────────
    if mode == "mica":
        if pw is not None:
            try:
                pw.apply_style(window, "mica")
                window.configure(bg=bg_color)
                window.wm_attributes("-alpha", opacity)
                _try_header_color(pw, window, bg_color)
                return "mica"
            except Exception:
                pass
        return _apply_solid(window, opacity, bg_color)

    # ── transparent (colour-key) ─────────────────────────────────
    if mode == "transparent":
        try:
            window.configure(bg=TRANSPARENT_COLOR_KEY)
            window.wm_attributes("-alpha", 1.0)
            window.wm_attributes("-transparentcolor", TRANSPARENT_COLOR_KEY)
            return "transparent"
        except Exception:
            return _apply_solid(window, opacity, bg_color)

    # ── solid (default) ──────────────────────────────────────────
    return _apply_solid(window, opacity, bg_color)


def remove_transparency(window) -> None:
    """Remove any transparency effect from *window*."""
    try:
        window.wm_attributes("-alpha", 1.0)
    except Exception:
        pass
    try:
        window.wm_attributes("-transparentcolor", "")
    except Exception:
        pass
    pw = _get_pywinstyles()
    if pw is not None:
        try:
            pw.apply_style(window, "normal")
        except Exception:
            pass


def get_available_modes() -> list[str]:
    """Return a list of transparency modes available on this platform."""
    modes = ["solid", "transparent"]
    if platform.system() == "Windows":
        pw = _get_pywinstyles()
        if pw is not None:
            modes.append("acrylic")
            # Mica is Win11+ only (build >= 22000)
            try:
                build = int(platform.version().split(".")[-1])
                if build >= 22000:
                    modes.append("mica")
            except Exception:
                pass
    return modes


# ── Internal helpers ─────────────────────────────────────────────────

def _apply_solid(window, opacity: float, bg_color: str) -> str:
    """Apply a plain opaque background with alpha."""
    try:
        window.configure(bg=bg_color)
        window.wm_attributes("-alpha", max(0.3, opacity))
    except Exception:
        pass
    return "solid"


def _try_header_color(pw, window, color: str) -> None:
    """Attempt to match the title bar colour (Windows 11 only)."""
    try:
        pw.change_header_color(window, color=color)
    except Exception:
        pass
