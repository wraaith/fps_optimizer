import os
import sys
import unittest
from unittest.mock import patch, MagicMock

# Add the app directory to sys.path so we can import modules properly
APP_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "desktop-app", "app"))
if APP_DIR not in sys.path:
    sys.path.insert(0, APP_DIR)

from sentinel.service import SentinelService
from sentinel.models import SentinelMode
from optimize.ai_boost_service import get_ai_boost_service
from overlay.metrics_collector import get_shared_metrics_collector
import time

class TestSentinelLifecycle(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Mock ALL potentially destructive APIs before running tests
        cls.patches = [
            patch('subprocess.run'),
            patch('subprocess.Popen'),
            patch('psutil.Process'),
            patch('psutil.cpu_percent', return_value=15.0),
            patch('psutil.virtual_memory', return_value=MagicMock(percent=40.0, available=8000000000)),
            patch('optimize.ai_boost_service.enable_high_resolution_timer', return_value=True),
            patch('optimize.ai_boost_service.disable_high_resolution_timer'),
            patch('optimize.ai_boost_service.activate_high_performance_power'),
            patch('optimize.ai_boost_service.restore_power_scheme'),
            patch('optimize.ai_boost_service.disable_game_bar_notifications'),
            patch('optimize.ai_boost_service.disable_nagle_algorithm'),
            patch('optimize.ai_boost_service.disable_network_throttling'),
            patch('overlay.metrics_collector.get_cpu_temp', return_value=45.0),
        ]
        for p in cls.patches:
            p.start()

    @classmethod
    def tearDownClass(cls):
        for p in cls.patches:
            p.stop()

    def setUp(self):
        self.service = SentinelService.get_instance()
        self.service.set_mode(SentinelMode.MONITOR_ONLY)
        self.service.stop() # ensure clean state
        self.ai_service = get_ai_boost_service()
        self.metrics = get_shared_metrics_collector()
        
        # Reset consumer counts for tests
        self.metrics._consumers = 0
        self.metrics.stop()

    def tearDown(self):
        self.service.stop()
        self.metrics.stop()

    def test_start_stop_idempotency(self):
        # Start twice
        self.service.start()
        self.assertTrue(self.service.is_running())
        self.assertTrue(self.service.has_active_worker())
        
        thread_before = self.ai_service._worker.thread
        self.service.start()
        thread_after = self.ai_service._worker.thread
        
        # Ensure no duplicate thread was created
        self.assertEqual(thread_before, thread_after)
        
        # Stop twice
        self.service.stop()
        self.assertFalse(self.service.is_running())
        self.assertFalse(self.service.has_active_worker())
        
        self.service.stop()
        self.assertFalse(self.service.is_running())

    def test_pause_resume(self):
        self.service.start()
        self.assertTrue(self.service.is_running())
        
        self.service.pause()
        self.assertTrue(self.service._is_paused)
        self.assertTrue(self.ai_service._worker.pause_event.is_set())
        
        self.service.resume()
        self.assertFalse(self.service._is_paused)
        self.assertFalse(self.ai_service._worker.pause_event.is_set())
        
        self.service.stop()

    def test_emergency_stop(self):
        self.service.start()
        self.service.emergency_stop()
        
        self.assertFalse(self.service.is_running())
        self.assertEqual(self.service.controller.mode, SentinelMode.MONITOR_ONLY)

    def test_shared_metrics_provider(self):
        self.assertEqual(self.metrics._consumers, 0)
        
        self.metrics.retain()
        self.assertEqual(self.metrics._consumers, 1)
        self.assertTrue(self.metrics._running)
        
        self.metrics.retain()
        self.assertEqual(self.metrics._consumers, 2)
        
        self.metrics.release()
        self.assertEqual(self.metrics._consumers, 1)
        self.assertTrue(self.metrics._running)
        
        self.metrics.release()
        self.assertEqual(self.metrics._consumers, 0)
        self.assertFalse(self.metrics._running)

    def test_no_time_sleep_in_workers(self):
        # Check source for time.sleep in managed workers
        import inspect
        from sentinel.worker import ManagedWorker
        
        worker_src = inspect.getsource(ManagedWorker._run_wrapper)
        self.assertNotIn("time.sleep(", worker_src, "ManagedWorker must use bounded event wait, not time.sleep")
        
        from optimize.ai_boost_service import AIBoostService, GameFpsTracker
        ai_src = inspect.getsource(AIBoostService._work_fn)
        self.assertNotIn("time.sleep(", ai_src, "AIBoostService._work_fn must not use time.sleep")
        
        tracker_src = inspect.getsource(GameFpsTracker._work_fn)
        self.assertNotIn("time.sleep(", tracker_src, "GameFpsTracker._work_fn must not use time.sleep")

    def test_monitor_only_blocks_interventions(self):
        self.service.set_mode(SentinelMode.MONITOR_ONLY)
        # MONITOR_ONLY blocks active interventions
        result = self.service.request_intervention("timeBeginPeriod")
        self.assertIsInstance(result, dict)
        self.assertEqual(result.get("status"), "blocked", "MONITOR_ONLY must block interventions")
        
        self.service.stop()

    def test_worker_exception_cleanup(self):
        # Simulate worker crash using a dummy worker
        def faulty_work():
            raise Exception("Test Crash")
            
        from sentinel.worker import ManagedWorker
        dummy = ManagedWorker(name="CrashTest", interval=0.1, work_fn=faulty_work)
        dummy.start()
        time.sleep(0.5) # Wait for it to hit the exception
        
        self.assertEqual(dummy.status, "ERROR")
        self.assertIsNotNone(dummy.last_error)
        dummy.stop()

if __name__ == '__main__':
    unittest.main(verbosity=2)
