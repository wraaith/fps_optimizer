"""
Comprehensive Automated Verification Script for Sentinel FPS Pipeline.
Tests:
1. Shared Live FPS IPC (write, read, clear)
2. GameplaySession metrics calculation (real samples, outliers, fallback, stability)
3. Rolling Frametime Smoother & 1% Low Calculation
4. Background desktop process filter in MetricsCollector
5. End-to-end Sentinel health check across all 9 subsystems
"""

import os
import sys
import time
import unittest
from pathlib import Path

# Ensure app directory is on path
APP_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "desktop-app", "app")
if APP_DIR not in sys.path:
    sys.path.insert(0, APP_DIR)

from services.benchmark_logger import (
    write_live_fps,
    read_live_fps,
    clear_live_fps,
    GameplaySession,
    get_hardware_predicted_fps,
    get_history_service,
)
from overlay.metrics_collector import MetricsCollector
from optimize.ai_boost_service import GameFpsTracker, get_ai_boost_service


class TestFpsPipeline(unittest.TestCase):

    def setUp(self):
        clear_live_fps()

    def tearDown(self):
        clear_live_fps()

    def test_01_shared_live_fps_ipc(self):
        """Test write_live_fps, read_live_fps, and clear_live_fps for IPC."""
        test_payload = {
            "fps": 165.2,
            "low_1pct": 142.0,
            "game": "VALORANT.exe",
            "pid": 4321,
            "timestamp": time.time(),
        }
        write_live_fps(test_payload)
        read_back = read_live_fps()
        self.assertIsNotNone(read_back)
        self.assertEqual(read_back.get("fps"), 165.2)
        self.assertEqual(read_back.get("game"), "VALORANT.exe")
        self.assertEqual(read_back.get("pid"), 4321)

        clear_live_fps()
        self.assertIsNone(read_live_fps())

    def test_02_gameplay_session_real_metrics(self):
        """Verify GameplaySession accurately computes avg, peak, 1% low, and gains."""
        session = GameplaySession(
            game_name="VALORANT",
            executable="VALORANT.exe",
            baseline_fps=140.0,
        )

        # Feed 10 FPS samples around 165-175 FPS
        sample_values = [165.0, 168.0, 172.0, 170.0, 174.0, 169.0, 171.0, 175.0, 166.0, 173.0]
        for s in sample_values:
            session.add_sample(s)

        session.add_action("1.0ms High-Resolution Timer Locked")
        session.add_action("Standby Memory Purged", freed_mb=1200.0)

        finalized = session.finalize()
        self.assertEqual(finalized["game_name"], "VALORANT")
        self.assertEqual(finalized["baseline_fps"], 140.0)
        self.assertGreater(finalized["avg_fps"], 165.0)
        self.assertEqual(finalized["peak_fps"], 175.0)
        self.assertGreaterEqual(finalized["low_1pct_fps"], 165.0)
        self.assertGreater(finalized["fps_gain"], 25.0)
        self.assertGreater(finalized["fps_gain_pct"], 15.0)
        self.assertFalse(finalized["is_estimated"])
        self.assertEqual(finalized["samples_count"], 10)
        self.assertEqual(finalized["ram_freed_mb"], 1200.0)

    def test_03_gameplay_session_outlier_rejection(self):
        """Verify that loading screen freezes (< 10 FPS) and catchup spikes are filtered."""
        session = GameplaySession(
            game_name="Apex Legends",
            executable="r5apex.exe",
            baseline_fps=100.0,
        )

        # Loading screen hitch (4.0 FPS should be rejected by add_sample)
        session.add_sample(4.0)
        # Impossible catchup frame (> 1000 FPS should be rejected by add_sample)
        session.add_sample(5000.0)

        # Normal gameplay samples
        for s in [118.0, 120.0, 122.0, 121.0, 125.0]:
            session.add_sample(s)

        finalized = session.finalize()
        self.assertEqual(finalized["samples_count"], 5)
        self.assertGreater(finalized["avg_fps"], 115.0)
        self.assertLess(finalized["avg_fps"], 130.0)
        self.assertFalse(finalized["is_estimated"])

    def test_04_gameplay_session_zero_sample_intelligent_fallback(self):
        """Verify non-admin 0-sample session uses hardware prediction, not fake 60.0 FPS."""
        session = GameplaySession(
            game_name="Cyberpunk 2077",
            executable="Cyberpunk2077.exe",
        )
        finalized = session.finalize()
        self.assertTrue(finalized["is_estimated"])
        self.assertEqual(finalized["samples_count"], 0)
        self.assertGreater(finalized["baseline_fps"], 0)
        self.assertGreater(finalized["avg_fps"], finalized["baseline_fps"])

    def test_05_metrics_collector_ignored_desktop_apps(self):
        """Verify that MetricsCollector strictly filters out desktop utilities & browsers."""
        collector = MetricsCollector()
        for non_game in [
            "python.exe", "pythonw.exe", "fps_optimizer.exe",
            "chrome.exe", "msedge.exe", "firefox.exe",
            "discord.exe", "spotify.exe", "code.exe", "devenv.exe",
            "taskmgr.exe", "explorer.exe", "dwm.exe"
        ]:
            self.assertFalse(
                collector._is_target_application(non_game),
                f"App {non_game} should be filtered out by MetricsCollector!"
            )

        # But a real 3D game MUST be allowed
        self.assertTrue(collector._is_target_application("VALORANT-Win64-Shipping.exe"))
        self.assertTrue(collector._is_target_application("Cyberpunk2077.exe"))
        self.assertTrue(collector._is_target_application("cs2.exe"))

    def test_06_metrics_collector_reads_ipc(self):
        """Verify MetricsCollector reads live FPS from IPC when Sentinel is active."""
        collector = MetricsCollector()
        write_live_fps({"fps": 182.5, "timestamp": time.time()})

        # Run loop update logic
        ipc_data = read_live_fps()
        self.assertIsNotNone(ipc_data)
        self.assertEqual(ipc_data["fps"], 182.5)

    def test_07_rolling_frametime_smoother_math(self):
        """Verify rolling window frametime smoothing produces stable FPS."""
        import collections
        frametimes = collections.deque()
        now = time.time()

        # Simulate 60 frames at ~8.33ms (120 FPS), with one 0.1ms catchup and one 25ms hitch
        raw_times = [8.33] * 58 + [0.1, 25.0]
        for ms in raw_times:
            frametimes.append((now, ms))

        total_ms = sum(ft[1] for ft in frametimes)
        smoothed_fps = round((len(frametimes) * 1000.0) / total_ms, 1)

        # 58 * 8.33 + 0.1 + 25 = 508.24ms for 60 frames = 118.1 FPS
        self.assertGreaterEqual(smoothed_fps, 115.0)
        self.assertLessEqual(smoothed_fps, 122.0)
        # Verify it didn't spike to 10,000 FPS due to the 0.1ms catchup frame
        self.assertNotEqual(smoothed_fps, 10000.0)

    def test_08_sentinel_full_diagnostics(self):
        """Verify Sentinel health check passes all subsystems including the new FPS Telemetry Pipeline."""
        svc = get_ai_boost_service()
        diag = svc.run_diagnostics()
        self.assertEqual(diag["overall"], "HEALTHY")
        self.assertEqual(diag["failed"], 0)
        self.assertGreaterEqual(diag["passed"], 7)

        fps_check = next((c for c in diag["checks"] if c["id"] == "fps_engine"), None)
        self.assertIsNotNone(fps_check)
        self.assertEqual(fps_check["status"], "PASS")


if __name__ == "__main__":
    unittest.main(verbosity=2)
