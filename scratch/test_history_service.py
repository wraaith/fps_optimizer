import os
import sys
import unittest
from unittest.mock import patch

APP_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "desktop-app", "app")
if APP_DIR not in sys.path:
    sys.path.insert(0, APP_DIR)

from services.benchmark_logger import BenchmarkHistoryService, GameplaySession


class TestBenchmarkHistoryService(unittest.TestCase):
    def setUp(self):
        self.service = BenchmarkHistoryService()
        self.service.clear_history()

    def tearDown(self):
        self.service.clear_history()

    def test_sentinel_gated_session_recording(self):
        # 1. When Sentinel is NOT running, start_session should return None
        with patch.object(self.service, "is_sentinel_running", return_value=False):
            session = self.service.start_session(
                game_name="VALORANT",
                executable="VALORANT-Win64-Shipping.exe",
                force=False,
            )
            self.assertIsNone(session)
            self.assertFalse(self.service.is_session_active)

        # 2. When Sentinel IS running, start_session creates an active session
        with patch.object(self.service, "is_sentinel_running", return_value=True):
            session = self.service.start_session(
                game_name="VALORANT",
                executable="VALORANT-Win64-Shipping.exe",
                baseline_fps=140.0,
            )
            self.assertTrue(self.service.is_session_active)
            self.assertEqual(self.service.active_session.game_name, "VALORANT")

            # Feed FPS samples
            samples = [160.0, 165.0, 170.0, 175.0, 180.0, 155.0]
            for s in samples:
                self.service.record_fps_sample(s)

            self.service.record_optimization("1.0ms Timer Locked", freed_mb=0)
            self.service.record_optimization("Standby Cache Purged", freed_mb=1200.0)

            finalized = self.service.end_session()
            self.assertFalse(self.service.is_session_active)
            self.assertIsNotNone(finalized)
            self.assertEqual(finalized["game_name"], "VALORANT")
            self.assertEqual(finalized["baseline_fps"], 140.0)
            self.assertGreater(finalized["avg_fps"], 160.0)
            self.assertEqual(finalized["peak_fps"], 180.0)
            self.assertGreater(finalized["fps_gain"], 20.0)
            self.assertGreater(finalized["fps_gain_pct"], 15.0)
            self.assertEqual(finalized["ram_freed_mb"], 1200.0)
            self.assertEqual(len(self.service.get_all_sessions()), 1)

    def test_summary_metrics(self):
        # Create two demo sessions
        s1 = self.service.create_demo_session(game_name="VALORANT", baseline_fps=140.0, boost_fps=170.0)
        s2 = self.service.create_demo_session(game_name="Cyberpunk 2077", baseline_fps=65.0, boost_fps=80.0)

        metrics = self.service.get_summary_metrics()
        self.assertEqual(metrics["total_sessions"], 2)
        self.assertGreater(metrics["avg_boost_pct"], 10.0)
        self.assertGreater(metrics["avg_boost_fps"], 15.0)
        self.assertGreater(metrics["total_ram_freed_mb"], 1000.0)

    def test_csv_export(self):
        self.service.create_demo_session(game_name="Apex Legends", baseline_fps=120.0, boost_fps=145.0)
        export_path = os.path.join(os.path.dirname(__file__), "test_export.csv")
        try:
            ok = self.service.export_csv(export_path)
            self.assertTrue(ok)
            self.assertTrue(os.path.isfile(export_path))
            with open(export_path, "r", encoding="utf-8") as f:
                content = f.read()
            self.assertIn("Apex Legends", content)
            self.assertIn("fps_gain", content)
        finally:
            if os.path.exists(export_path):
                os.remove(export_path)


if __name__ == "__main__":
    unittest.main()
