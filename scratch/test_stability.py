import sys
import os
import unittest
import time

sys.path.insert(0, os.path.abspath("desktop-app/app"))

from services.predictor import predict_fps
from services.system_scan import run_system_scan
from optimize.optimizer_service import (
    get_top_memory_consumers,
    trim_all_working_sets,
    check_has_ssd,
    get_sysmain_status,
)
from optimize.ai_boost_service import get_ai_boost_service
import customtkinter as ctk
from optimize.optimize_view import OptimizeView


class StabilityRegressionTests(unittest.TestCase):
    def test_predictor_unlisted_hardware(self):
        """Verify fuzzy hardware matching never raises NameError or UnboundLocalError."""
        res = predict_fps("AMD Ryzen 7 7800X3D", "NVIDIA GeForce RTX 4070 Ti", 16, "1920x1080", "Ultra")
        self.assertIsNotNone(res)
        self.assertIn("avg_fps", res)
        self.assertIn("confidence", res)
        self.assertTrue(res["avg_fps"] > 0)
        self.assertTrue(res["min_fps"] <= res["avg_fps"] <= res["max_fps"])

    def test_system_scan_com_lifecycle(self):
        """Verify repeated system scans succeed without COM apartment leaks or errors."""
        for _ in range(2):
            data = run_system_scan()
            self.assertIn("cpu", data)
            self.assertIn("gpu", data)
            self.assertIn("ram", data)
            self.assertIn("os", data)

    def test_optimizer_process_protection(self):
        """Verify top memory consumers protects python runtimes and self."""
        current_pid = os.getpid()
        consumers = get_top_memory_consumers(20)
        consumer_pids = {c["pid"] for c in consumers}
        consumer_names = {c["name"].lower() for c in consumers}
        self.assertNotIn(current_pid, consumer_pids)
        self.assertNotIn("python.exe", consumer_names)
        self.assertNotIn("pythonw.exe", consumer_names)
        self.assertNotIn("fps_optimizer.exe", consumer_names)

    def test_ssd_caching_and_sysmain(self):
        """Verify SSD check is cached and sysmain status check succeeds."""
        start = time.perf_counter()
        ssd1 = check_has_ssd()
        first_duration = time.perf_counter() - start

        start = time.perf_counter()
        ssd2 = check_has_ssd()
        cached_duration = time.perf_counter() - start

        self.assertEqual(ssd1, ssd2)
        self.assertLess(cached_duration, 0.05)

        sm = get_sysmain_status()
        self.assertIn("running", sm)
        self.assertIn("start_type", sm)

    def test_ai_sentinel_fast_shutdown(self):
        """Verify AI sentinel stops instantaneously without waiting out cooldowns."""
        svc = get_ai_boost_service()
        svc.start()
        time.sleep(0.3)
        self.assertTrue(svc.is_running)
        stop_start = time.perf_counter()
        svc.stop()
        stop_duration = time.perf_counter() - stop_start
        self.assertFalse(svc.is_running)
        self.assertLess(stop_duration, 2.5)

    def test_optimize_view_clean_destruction(self):
        """Verify OptimizeView can be instantiated and destroyed without thread leaks."""
        root = ctk.CTk()
        root.withdraw()
        try:
            view = OptimizeView(root)
            root.update()
            # View destruction must stop telemetry thread
            view.destroy()
            root.update()
            self.assertTrue(view._telemetry_stop.is_set())
        finally:
            root.destroy()


if __name__ == "__main__":
    unittest.main()
