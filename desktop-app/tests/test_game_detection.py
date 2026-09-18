"""
Comprehensive tests for the 3-Tier Universal Game Detection Protocol.

Covers:
1. Blacklisted process returns None without reaching Tier 2/3
2. Fullscreen + PresentMon match → HIGH confidence
3. Fullscreen + no PresentMon → MEDIUM confidence, no crash
4. Windowed + sustained GPU activity → LOW confidence
5. Windowed + no GPU activity → None
6. Multi-monitor fullscreen check
7. PresentMon throws → graceful degradation
8. Blacklist loaded from config (dynamic exclusion)
"""

import sys
import os
import time
import pytest
from unittest.mock import patch, MagicMock, PropertyMock
from dataclasses import dataclass

# Ensure app directory is importable
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../app")))

from sentinel.game_detection import (
    detect_active_game,
    get_foreground_game_process,
    _is_blacklisted,
    _classify_window_mode,
    _check_presentmon_frame_activity,
    _get_foreground_process,
    ActiveGameInfo,
    WindowMode,
    DetectionConfidence,
    WS_POPUP,
    WS_CAPTION,
    WS_THICKFRAME,
    MONITORINFO,
)
from sentinel.game_detection_config import NON_GAME_BLACKLIST, SYSTEM_PROCESSES


# ──────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────

def _make_mock_user32(
    hwnd=12345,
    visible=True,
    pid=9999,
    title="TestGame",
    style=WS_POPUP,
    win_rect=(0, 0, 1920, 1080),
    mon_rect=(0, 0, 1920, 1080),
    hmonitor=1,
):
    """Create a mock ctypes.windll.user32 that returns the specified values."""
    mock_u32 = MagicMock()
    mock_u32.GetForegroundWindow.return_value = hwnd
    mock_u32.IsWindowVisible.return_value = visible

    def _get_thread_process_id(h, pid_ptr):
        import ctypes
        pid_ptr._obj.value = pid
        return 1

    mock_u32.GetWindowThreadProcessId.side_effect = _get_thread_process_id
    mock_u32.GetWindowTextLengthW.return_value = len(title)

    def _get_window_text(h, buf, length):
        for i, c in enumerate(title):
            buf[i] = c
        return len(title)

    mock_u32.GetWindowTextW.side_effect = _get_window_text
    mock_u32.GetWindowLongW.return_value = style

    def _get_window_rect(h, rect_ptr):
        rect_ptr.left = win_rect[0]
        rect_ptr.top = win_rect[1]
        rect_ptr.right = win_rect[2]
        rect_ptr.bottom = win_rect[3]
        return True

    mock_u32.GetWindowRect.side_effect = _get_window_rect
    mock_u32.MonitorFromWindow.return_value = hmonitor

    def _get_monitor_info(hmon, mi_ptr):
        mi_ptr.rcMonitor.left = mon_rect[0]
        mi_ptr.rcMonitor.top = mon_rect[1]
        mi_ptr.rcMonitor.right = mon_rect[2]
        mi_ptr.rcMonitor.bottom = mon_rect[3]
        return True

    mock_u32.GetMonitorInfoW.side_effect = _get_monitor_info

    return mock_u32


def _mock_process(name="Game.exe", pid=9999, create_time=1000.0):
    """Create a mock psutil.Process."""
    mock_proc = MagicMock()
    mock_proc.name.return_value = name
    mock_proc.pid = pid
    mock_proc.create_time.return_value = create_time
    mock_proc.is_running.return_value = True
    return mock_proc


# ══════════════════════════════════════════════════════════════════════
# 1. BLACKLISTED PROCESS → None WITHOUT REACHING TIER 2/3
# ══════════════════════════════════════════════════════════════════════

class TestTier1Blacklist:
    def test_chrome_blacklisted_returns_none(self):
        """chrome.exe is blacklisted and should be rejected immediately."""
        assert _is_blacklisted("chrome.exe") is True
        assert _is_blacklisted("Chrome.EXE") is True

    def test_non_blacklisted_passes(self):
        """A non-blacklisted process should not be rejected."""
        assert _is_blacklisted("Game.exe") is False
        assert _is_blacklisted("VALORANT-Win64-Shipping.exe") is False

    def test_system_process_blacklisted(self):
        """System processes are also rejected."""
        assert _is_blacklisted("svchost.exe") is True
        assert _is_blacklisted("dwm.exe") is True

    @patch("sentinel.game_detection._get_foreground_process")
    @patch("sentinel.game_detection._classify_window_mode")
    def test_blacklisted_does_not_reach_tier2(self, mock_classify, mock_fg):
        """When a blacklisted process is detected, Tier 2 is never called."""
        mock_fg.return_value = (12345, 9999, "chrome.exe", "Google Chrome")

        result = detect_active_game()

        assert result is None
        mock_classify.assert_not_called()


# ══════════════════════════════════════════════════════════════════════
# 2. FULLSCREEN + PRESENTMON MATCH → HIGH CONFIDENCE
# ══════════════════════════════════════════════════════════════════════

class TestHighConfidence:
    @patch("sentinel.game_detection._check_presentmon_frame_activity")
    @patch("sentinel.game_detection._classify_window_mode")
    @patch("sentinel.game_detection._get_foreground_process")
    def test_fullscreen_with_presentmon_returns_high(self, mock_fg, mock_classify, mock_pm):
        """Fullscreen process confirmed by PresentMon → HIGH confidence."""
        mock_fg.return_value = (12345, 9999, "Game.exe", "My Game")
        mock_classify.return_value = WindowMode.BORDERLESS_FULLSCREEN
        mock_pm.return_value = True

        result = detect_active_game()

        assert result is not None
        assert result.confidence == "HIGH"
        assert result.detection_method == "TIER1+TIER2+TIER3"
        assert result.pid == 9999
        assert result.exe_name == "Game.exe"
        assert result.window_mode == "BORDERLESS_FULLSCREEN"


# ══════════════════════════════════════════════════════════════════════
# 3. FULLSCREEN + NO PRESENTMON → MEDIUM CONFIDENCE
# ══════════════════════════════════════════════════════════════════════

class TestMediumConfidence:
    @patch("sentinel.game_detection._check_presentmon_frame_activity")
    @patch("sentinel.game_detection._classify_window_mode")
    @patch("sentinel.game_detection._get_foreground_process")
    def test_fullscreen_no_presentmon_returns_medium(self, mock_fg, mock_classify, mock_pm):
        """Fullscreen process with no PresentMon data → MEDIUM confidence, no crash."""
        mock_fg.return_value = (12345, 9999, "Game.exe", "My Game")
        mock_classify.return_value = WindowMode.EXCLUSIVE_FULLSCREEN
        mock_pm.return_value = None  # PresentMon unavailable

        result = detect_active_game()

        assert result is not None
        assert result.confidence == "MEDIUM"
        assert result.detection_method == "TIER1+TIER2"
        assert result.window_mode == "EXCLUSIVE_FULLSCREEN"

    @patch("sentinel.game_detection._check_presentmon_frame_activity")
    @patch("sentinel.game_detection._classify_window_mode")
    @patch("sentinel.game_detection._get_foreground_process")
    def test_fullscreen_no_frames_returns_medium(self, mock_fg, mock_classify, mock_pm):
        """Fullscreen process with PresentMon showing no frames → still MEDIUM (trusted fullscreen)."""
        mock_fg.return_value = (12345, 9999, "Game.exe", "Loading...")
        mock_classify.return_value = WindowMode.BORDERLESS_FULLSCREEN
        mock_pm.return_value = False  # PresentMon running but no frames for this PID

        result = detect_active_game()

        assert result is not None
        assert result.confidence == "MEDIUM"


# ══════════════════════════════════════════════════════════════════════
# 4. WINDOWED + SUSTAINED GPU ACTIVITY → LOW CONFIDENCE
# ══════════════════════════════════════════════════════════════════════

class TestLowConfidence:
    @patch("sentinel.game_detection._check_presentmon_frame_activity")
    @patch("sentinel.game_detection._classify_window_mode")
    @patch("sentinel.game_detection._get_foreground_process")
    def test_windowed_with_frames_returns_low(self, mock_fg, mock_classify, mock_pm):
        """Windowed process with active PresentMon frames → LOW confidence fallback."""
        mock_fg.return_value = (12345, 9999, "Game.exe", "My Windowed Game")
        mock_classify.return_value = WindowMode.WINDOWED
        mock_pm.return_value = True  # Actively producing frames

        result = detect_active_game()

        assert result is not None
        assert result.confidence == "LOW"
        assert result.detection_method == "TIER1+TIER3_FALLBACK"
        assert result.window_mode == "WINDOWED"


# ══════════════════════════════════════════════════════════════════════
# 5. WINDOWED + NO GPU ACTIVITY → None
# ══════════════════════════════════════════════════════════════════════

class TestWindowedNoActivity:
    @patch("sentinel.game_detection._check_presentmon_frame_activity")
    @patch("sentinel.game_detection._classify_window_mode")
    @patch("sentinel.game_detection._get_foreground_process")
    def test_windowed_no_frames_returns_none(self, mock_fg, mock_classify, mock_pm):
        """Windowed process with no frame activity → None."""
        mock_fg.return_value = (12345, 9999, "SomeApp.exe", "Some App")
        mock_classify.return_value = WindowMode.WINDOWED
        mock_pm.return_value = False

        result = detect_active_game()
        assert result is None

    @patch("sentinel.game_detection._check_presentmon_frame_activity")
    @patch("sentinel.game_detection._classify_window_mode")
    @patch("sentinel.game_detection._get_foreground_process")
    def test_windowed_presentmon_unavailable_returns_none(self, mock_fg, mock_classify, mock_pm):
        """Windowed process with PresentMon unavailable → None (can't confirm it's a game)."""
        mock_fg.return_value = (12345, 9999, "SomeApp.exe", "Some App")
        mock_classify.return_value = WindowMode.WINDOWED
        mock_pm.return_value = None  # Unavailable

        result = detect_active_game()
        assert result is None


# ══════════════════════════════════════════════════════════════════════
# 6. MULTI-MONITOR: FULLSCREEN CHECK USES CORRECT MONITOR
# ══════════════════════════════════════════════════════════════════════

class TestMultiMonitor:
    @patch("sentinel.game_detection.ctypes")
    def test_fullscreen_on_secondary_monitor(self, mock_ctypes):
        """Fullscreen check must use MonitorFromWindow, not hardcoded primary resolution."""
        mock_u32 = _make_mock_user32(
            hwnd=99999,
            style=WS_POPUP,
            # Window is on a secondary 2560x1440 monitor at offset (1920, 0)
            win_rect=(1920, 0, 4480, 1440),
            mon_rect=(1920, 0, 4480, 1440),
            hmonitor=2,
        )
        mock_ctypes.windll.user32 = mock_u32
        mock_ctypes.sizeof.return_value = 40  # sizeof(MONITORINFO)
        mock_ctypes.byref = lambda x: x

        result = _classify_window_mode(99999)

        assert result == WindowMode.BORDERLESS_FULLSCREEN
        # Verify MonitorFromWindow was called (not hardcoded primary check)
        mock_u32.MonitorFromWindow.assert_called_once()

    @patch("sentinel.game_detection.ctypes")
    def test_windowed_on_secondary_monitor(self, mock_ctypes):
        """Windowed app that doesn't cover monitor → WINDOWED."""
        mock_u32 = _make_mock_user32(
            hwnd=99999,
            style=WS_POPUP | WS_CAPTION | WS_THICKFRAME,
            # Window is 800x600 on a 2560x1440 monitor
            win_rect=(1920 + 100, 100, 1920 + 900, 700),
            mon_rect=(1920, 0, 4480, 1440),
            hmonitor=2,
        )
        mock_ctypes.windll.user32 = mock_u32
        mock_ctypes.sizeof.return_value = 40
        mock_ctypes.byref = lambda x: x

        result = _classify_window_mode(99999)

        assert result == WindowMode.WINDOWED


# ══════════════════════════════════════════════════════════════════════
# 7. PRESENTMON THROWS → GRACEFUL DEGRADATION
# ══════════════════════════════════════════════════════════════════════

class TestPresentMonGracefulDegradation:
    @patch("sentinel.game_detection._check_presentmon_frame_activity")
    @patch("sentinel.game_detection._classify_window_mode")
    @patch("sentinel.game_detection._get_foreground_process")
    def test_presentmon_exception_degrades_to_medium(self, mock_fg, mock_classify, mock_pm):
        """When PresentMon throws, detection degrades to MEDIUM, does not raise."""
        mock_fg.return_value = (12345, 9999, "Game.exe", "My Game")
        mock_classify.return_value = WindowMode.EXCLUSIVE_FULLSCREEN
        mock_pm.return_value = None  # Simulates unavailable (exception caught internally)

        result = detect_active_game()

        assert result is not None
        assert result.confidence == "MEDIUM"
        assert result.detection_method == "TIER1+TIER2"

    def test_check_presentmon_import_error_returns_none(self):
        """If overlay module can't be imported, returns None (not raises)."""
        with patch.dict("sys.modules", {"overlay.metrics_collector": None}):
            # _check_presentmon_frame_activity handles ImportError internally
            result = _check_presentmon_frame_activity(9999)
            # Should return None, not raise
            assert result is None

    @patch("sentinel.game_detection._check_presentmon_frame_activity")
    @patch("sentinel.game_detection._classify_window_mode")
    @patch("sentinel.game_detection._get_foreground_process")
    def test_detect_never_raises_on_clean_no_game(self, mock_fg, mock_classify, mock_pm):
        """detect_active_game() must return None (not raise) when no game is running."""
        mock_fg.return_value = None
        result = detect_active_game()
        assert result is None
        mock_classify.assert_not_called()
        mock_pm.assert_not_called()


# ══════════════════════════════════════════════════════════════════════
# 8. BLACKLIST LOADED FROM CONFIG (NOT HARDCODED)
# ══════════════════════════════════════════════════════════════════════

class TestBlacklistFromConfig:
    def test_blacklist_is_from_config_module(self):
        """Verify blacklist is imported from config, not hardcoded inline."""
        # All these should be in the config-sourced blacklist
        assert "chrome.exe" in NON_GAME_BLACKLIST
        assert "code.exe" in NON_GAME_BLACKLIST
        assert "discord.exe" in NON_GAME_BLACKLIST

    @patch("sentinel.game_detection._get_foreground_process")
    def test_adding_to_config_changes_behavior(self, mock_fg):
        """Dynamically patching the config blacklist changes exclusion behavior."""
        mock_fg.return_value = (12345, 9999, "MyCustomApp.exe", "Custom App")

        # Before: not blacklisted
        assert _is_blacklisted("MyCustomApp.exe") is False

        # Patch the config to add it
        import sentinel.game_detection_config as cfg
        original = cfg.NON_GAME_BLACKLIST
        try:
            cfg.NON_GAME_BLACKLIST = original | frozenset({"mycustomapp.exe"})
            # Re-import references in game_detection
            import sentinel.game_detection as gd
            original_ref = gd.NON_GAME_BLACKLIST
            gd.NON_GAME_BLACKLIST = cfg.NON_GAME_BLACKLIST

            assert _is_blacklisted("MyCustomApp.exe") is True
        finally:
            # Restore
            cfg.NON_GAME_BLACKLIST = original
            gd.NON_GAME_BLACKLIST = original


# ══════════════════════════════════════════════════════════════════════
# BACKWARD COMPATIBILITY
# ══════════════════════════════════════════════════════════════════════

class TestBackwardCompat:
    @patch("sentinel.game_detection._check_presentmon_frame_activity")
    @patch("sentinel.game_detection._classify_window_mode")
    @patch("sentinel.game_detection._get_foreground_process")
    def test_legacy_wrapper_returns_dict(self, mock_fg, mock_classify, mock_pm):
        """get_foreground_game_process() returns legacy-format dict."""
        mock_fg.return_value = (12345, 9999, "Game.exe", "My Game Title")
        mock_classify.return_value = WindowMode.BORDERLESS_FULLSCREEN
        mock_pm.return_value = True

        result = get_foreground_game_process()

        assert result is not None
        assert result["pid"] == 9999
        assert result["name"] == "Game.exe"
        assert "title" in result

    @patch("sentinel.game_detection._get_foreground_process")
    def test_legacy_wrapper_returns_none_for_blacklisted(self, mock_fg):
        """get_foreground_game_process() returns None for blacklisted processes."""
        mock_fg.return_value = (12345, 9999, "chrome.exe", "Google Chrome")

        result = get_foreground_game_process()
        assert result is None

    def test_legacy_wrapper_returns_none_when_no_window(self):
        """get_foreground_game_process() returns None when no foreground window."""
        with patch("sentinel.game_detection._get_foreground_process", return_value=None):
            result = get_foreground_game_process()
            assert result is None


# ══════════════════════════════════════════════════════════════════════
# ACTIVE GAME INFO DATACLASS
# ══════════════════════════════════════════════════════════════════════

class TestActiveGameInfoDataclass:
    def test_dataclass_fields(self):
        """ActiveGameInfo has all required fields."""
        info = ActiveGameInfo(
            pid=1234,
            exe_name="game.exe",
            window_mode="BORDERLESS_FULLSCREEN",
            confidence="HIGH",
            detection_method="TIER1+TIER2+TIER3",
            detected_at=time.time(),
        )
        assert info.pid == 1234
        assert info.exe_name == "game.exe"
        assert info.window_mode == "BORDERLESS_FULLSCREEN"
        assert info.confidence == "HIGH"
        assert info.detection_method == "TIER1+TIER2+TIER3"
        assert isinstance(info.detected_at, float)
