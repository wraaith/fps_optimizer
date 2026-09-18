# desktop-app/app/sentinel/game_detection.py

"""
Universal Game Detection Protocol — 3-Tier Cascading Pipeline.

Tier 1: Exclusion blacklist (near-zero cost, O(1) frozenset lookup)
Tier 2: Fullscreen / borderless geometry check (cheap ctypes, multi-monitor)
Tier 3: PresentMon frame-activity confirmation (read-only, no new sessions)

Usage:
    from sentinel.game_detection import detect_active_game, ActiveGameInfo

    result = detect_active_game()
    if result:
        print(f"Game detected: {result.exe_name} (confidence={result.confidence})")
"""

import ctypes
import ctypes.wintypes as wintypes
import logging
import os
import time
from dataclasses import dataclass
from enum import Enum
from typing import Optional, Tuple

import psutil

from sentinel.game_detection_config import (
    NON_GAME_BLACKLIST,
    SYSTEM_PROCESSES,
    FRAME_ACTIVITY_WINDOW_SEC,
    MIN_FRAME_ACTIVITY_FPS,
)

log = logging.getLogger("GameDetection")


# ── Enums ─────────────────────────────────────────────────────────────


class WindowMode(Enum):
    EXCLUSIVE_FULLSCREEN = "EXCLUSIVE_FULLSCREEN"
    BORDERLESS_FULLSCREEN = "BORDERLESS_FULLSCREEN"
    WINDOWED = "WINDOWED"


class DetectionConfidence(Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


# ── Data Model ────────────────────────────────────────────────────────


@dataclass
class ActiveGameInfo:
    """Result of the game detection pipeline."""
    pid: int
    exe_name: str
    window_mode: str        # WindowMode.value
    confidence: str         # DetectionConfidence.value
    detection_method: str   # e.g. "TIER1+TIER2+TIER3"
    detected_at: float      # time.time()


# ── Win32 Constants ───────────────────────────────────────────────────

GWL_STYLE = -16
WS_OVERLAPPEDWINDOW = 0x00CF0000  # WS_OVERLAPPED | WS_CAPTION | WS_SYSMENU | WS_THICKFRAME | WS_MINIMIZEBOX | WS_MAXIMIZEBOX
WS_POPUP = 0x80000000
WS_CAPTION = 0x00C00000
WS_THICKFRAME = 0x00040000
MONITOR_DEFAULTTONEAREST = 2


class MONITORINFO(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("rcMonitor", wintypes.RECT),
        ("rcWork", wintypes.RECT),
        ("dwFlags", wintypes.DWORD),
    ]


# ── Tier 1: Foreground Process + Blacklist ────────────────────────────


def _get_foreground_process() -> Optional[Tuple[int, int, str, str]]:
    """Get the foreground window's (hwnd, pid, exe_name, title).

    Returns None if no valid foreground window is found.
    Pure ctypes + psutil — no COM, no WMI, no subprocess.
    """
    try:
        user32 = ctypes.windll.user32

        hwnd = user32.GetForegroundWindow()
        if not hwnd:
            return None

        if not user32.IsWindowVisible(hwnd):
            return None

        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        pid_val = pid.value

        if not pid_val or pid_val <= 4 or pid_val == os.getpid():
            return None

        # Get window title
        length = user32.GetWindowTextLengthW(hwnd)
        title = ""
        if length > 0:
            buff = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, buff, length + 1)
            title = buff.value.strip()

        # Get process name via psutil (fast, cached)
        proc = psutil.Process(pid_val)
        exe_name = proc.name() or ""

        return (hwnd, pid_val, exe_name, title)
    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
        return None
    except Exception:
        return None


def _is_blacklisted(exe_name: str) -> bool:
    """Check if a process name is in the combined blacklist.

    O(1) frozenset lookup, case-insensitive.
    """
    name_lower = exe_name.lower()
    return name_lower in NON_GAME_BLACKLIST or name_lower in SYSTEM_PROCESSES


# ── Tier 2: Fullscreen / Borderless Geometry ──────────────────────────


def _classify_window_mode(hwnd: int) -> WindowMode:
    """Classify the window as fullscreen, borderless, or windowed.

    Multi-monitor safe: uses MonitorFromWindow to get the correct monitor,
    then compares the window rect against that specific monitor's rect.
    """
    try:
        user32 = ctypes.windll.user32

        # Get window style flags
        style = user32.GetWindowLongW(hwnd, GWL_STYLE)

        # Get the window rect
        win_rect = wintypes.RECT()
        user32.GetWindowRect(hwnd, ctypes.byref(win_rect))

        # Get the monitor this window is on (not necessarily primary)
        hMonitor = user32.MonitorFromWindow(hwnd, MONITOR_DEFAULTTONEAREST)
        if not hMonitor:
            return WindowMode.WINDOWED

        # Get monitor info
        mi = MONITORINFO()
        mi.cbSize = ctypes.sizeof(MONITORINFO)
        if not user32.GetMonitorInfoW(hMonitor, ctypes.byref(mi)):
            return WindowMode.WINDOWED

        mon_rect = mi.rcMonitor

        # Check if the window covers the full monitor
        covers_monitor = (
            win_rect.left <= mon_rect.left
            and win_rect.top <= mon_rect.top
            and win_rect.right >= mon_rect.right
            and win_rect.bottom >= mon_rect.bottom
        )

        if not covers_monitor:
            return WindowMode.WINDOWED

        # Window covers the full monitor — determine if exclusive or borderless
        has_caption = bool(style & WS_CAPTION)
        has_thickframe = bool(style & WS_THICKFRAME)
        is_popup = bool(style & WS_POPUP)

        # Exclusive fullscreen: no decorations, typically WS_POPUP style
        # Borderless fullscreen: WS_POPUP without caption/thickframe, covers monitor
        # Both are valid "fullscreen" for gaming purposes

        if is_popup and not has_caption and not has_thickframe:
            # Could be either exclusive or borderless — hard to distinguish
            # without checking DirectX swap chain. Default to borderless.
            return WindowMode.BORDERLESS_FULLSCREEN

        if not has_caption and not has_thickframe:
            return WindowMode.EXCLUSIVE_FULLSCREEN

        # Has decorations but still covers monitor (maximized with auto-hide taskbar)
        return WindowMode.BORDERLESS_FULLSCREEN

    except Exception:
        return WindowMode.WINDOWED


# ── Tier 3: PresentMon Frame-Activity Confirmation ───────────────────


def _check_presentmon_frame_activity(pid: int) -> Optional[bool]:
    """Check if the given PID is actively producing frames via PresentMon.

    Reads from the existing FrameTelemetryEngine — does NOT start new
    PresentMon capture sessions. Uses non-blocking lock acquisition.

    Returns:
        True  — PID is actively producing frames
        False — PID is not producing frames (telemetry running but no match)
        None  — Telemetry unavailable (module missing, not started, lock contention)
    """
    try:
        from overlay.metrics_collector import get_shared_metrics_collector
        collector = get_shared_metrics_collector()
        engine = collector._telemetry_engine

        # Non-blocking lock acquisition to avoid stalling the detection poll
        acquired = engine.lock.acquire(timeout=0.05)
        if not acquired:
            return None

        try:
            # Check if the engine is tracking this PID
            if engine.identity is None:
                return None  # No game bound to telemetry yet

            if engine.identity.pid != pid:
                return False  # Telemetry is tracking a different process

            # Check if frames are actively being received
            from overlay.metrics_collector import TelemetryState
            if engine.state in (TelemetryState.FPS_READY, TelemetryState.COLLECTING_FRAMES):
                # Verify there are recent frame samples
                if engine.fps is not None and engine.fps >= MIN_FRAME_ACTIVITY_FPS:
                    return True
                # Even without computed FPS, having frame samples means activity
                if len(engine.frame_samples) > 0:
                    return True

            return False
        finally:
            engine.lock.release()

    except ImportError:
        # MetricsCollector module not available
        return None
    except Exception:
        return None


def get_active_frame_pid() -> Optional[int]:
    """Return the PID currently producing frames in the telemetry engine, or None.

    Convenience function for Tier 3 queries from external modules.
    """
    try:
        from overlay.metrics_collector import get_shared_metrics_collector, TelemetryState
        collector = get_shared_metrics_collector()
        engine = collector._telemetry_engine

        acquired = engine.lock.acquire(timeout=0.05)
        if not acquired:
            return None

        try:
            if (engine.identity is not None
                    and engine.state in (TelemetryState.FPS_READY, TelemetryState.COLLECTING_FRAMES)):
                return engine.identity.pid
            return None
        finally:
            engine.lock.release()
    except Exception:
        return None


# ── Main Detection Pipeline ──────────────────────────────────────────


def detect_active_game(require_fullscreen: bool = True) -> Optional[ActiveGameInfo]:
    """Detect the active game using a 3-tier cascading pipeline.

    Tier 1: Exclusion blacklist — near-zero cost, rejects known non-games.
    Tier 2: Fullscreen geometry — cheap ctypes check, multi-monitor aware.
    Tier 3: PresentMon frame confirmation — read-only from existing telemetry.

    Args:
        require_fullscreen: If True, windowed processes must pass Tier 3
            (frame activity) to be classified as games. If False, any
            non-blacklisted fullscreen OR windowed process with frame
            activity is accepted.

    Returns:
        ActiveGameInfo with confidence level, or None if no game detected.
        Never raises — returns None on any detection failure.
    """
    now = time.time()

    # ── Tier 1: Get foreground process and check blacklist ────────
    fg = _get_foreground_process()
    if fg is None:
        return None

    hwnd, pid, exe_name, title = fg

    if _is_blacklisted(exe_name):
        return None

    # ── Tier 2: Fullscreen / borderless geometry check ───────────
    window_mode = _classify_window_mode(hwnd)
    is_fullscreen = window_mode in (
        WindowMode.EXCLUSIVE_FULLSCREEN,
        WindowMode.BORDERLESS_FULLSCREEN,
    )

    # ── Tier 3: PresentMon frame-activity confirmation ───────────
    frame_active = _check_presentmon_frame_activity(pid)

    # ── Decision Logic ───────────────────────────────────────────

    if is_fullscreen:
        if frame_active is True:
            # All 3 tiers passed → HIGH confidence
            return ActiveGameInfo(
                pid=pid,
                exe_name=exe_name,
                window_mode=window_mode.value,
                confidence=DetectionConfidence.HIGH.value,
                detection_method="TIER1+TIER2+TIER3",
                detected_at=now,
            )
        elif frame_active is None:
            # Fullscreen but PresentMon unavailable → MEDIUM confidence
            log.warning(
                "PresentMon telemetry unavailable for PID %d (%s); "
                "degrading to MEDIUM confidence (Tier 1+2 only)",
                pid, exe_name,
            )
            return ActiveGameInfo(
                pid=pid,
                exe_name=exe_name,
                window_mode=window_mode.value,
                confidence=DetectionConfidence.MEDIUM.value,
                detection_method="TIER1+TIER2",
                detected_at=now,
            )
        else:
            # Fullscreen but no frame activity — might be a fullscreen media app,
            # or a freshly launched game in its loading screen before the first frame.
            # We intentionally collapse "no frames" and "unavailable" both into MEDIUM
            # confidence to avoid unjustly demoting games during loading screens.
            return ActiveGameInfo(
                pid=pid,
                exe_name=exe_name,
                window_mode=window_mode.value,
                confidence=DetectionConfidence.MEDIUM.value,
                detection_method="TIER1+TIER2",
                detected_at=now,
            )

    # Windowed mode
    if frame_active is True:
        # Windowed but actively producing frames → LOW confidence (game in windowed mode)
        return ActiveGameInfo(
            pid=pid,
            exe_name=exe_name,
            window_mode=window_mode.value,
            confidence=DetectionConfidence.LOW.value,
            detection_method="TIER1+TIER3_FALLBACK",
            detected_at=now,
        )

    # Windowed with no frame activity → not a game
    return None


# ── Backward Compatibility Wrapper ────────────────────────────────────


def get_foreground_game_process() -> Optional[dict]:
    """Drop-in replacement for optimizer_service.get_foreground_game_process().

    Returns the same ``{"pid": int, "name": str, "title": str}`` dict for
    full backward compatibility with all existing callers.
    """
    try:
        result = detect_active_game()
        if result is None:
            return None

        # Recover the window title from the foreground window
        fg = _get_foreground_process()
        title = fg[3] if fg else ""

        return {
            "pid": result.pid,
            "name": result.exe_name,
            "title": title,
        }
    except Exception:
        return None
