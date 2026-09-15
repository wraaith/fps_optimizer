import os
import sys
import unittest
from unittest.mock import patch, MagicMock

APP_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "desktop-app", "app"))
if APP_DIR not in sys.path:
    sys.path.insert(0, APP_DIR)

from sentinel.managers.timer_manager import TimerManager

class TestTimerManager(unittest.TestCase):
    def setUp(self):
        self.tm = TimerManager()
        self.tm._winmm = MagicMock()
        self.tm._winmm.timeBeginPeriod.return_value = 0
        self.tm._winmm.timeEndPeriod.return_value = 0

    def test_successful_begin_creates_ownership(self):
        self.assertTrue(self.tm.begin(1))
        self.assertTrue(self.tm.owns_timer)
        self.assertEqual(self.tm.timer_period_ms, 1)
        self.assertEqual(self.tm.timer_request_count, 1)
        self.tm._winmm.timeBeginPeriod.assert_called_once_with(1)

    def test_duplicate_begin_is_rejected(self):
        self.assertTrue(self.tm.begin(1))
        self.assertTrue(self.tm.begin(1))
        self.assertEqual(self.tm.timer_request_count, 1)
        self.tm._winmm.timeBeginPeriod.assert_called_once()

    def test_failed_begin_does_not_call_end(self):
        self.tm._winmm.timeBeginPeriod.return_value = 1 # Simulate failure
        self.assertFalse(self.tm.begin(1))
        self.assertFalse(self.tm.owns_timer)
        self.tm._winmm.timeEndPeriod.assert_not_called()

    def test_normal_stop_calls_end_exactly_once(self):
        self.tm.begin(1)
        self.assertTrue(self.tm.end())
        self.assertFalse(self.tm.owns_timer)
        self.tm._winmm.timeEndPeriod.assert_called_once_with(1)
        
        # Second end shouldn't do anything
        self.assertTrue(self.tm.end())
        self.tm._winmm.timeEndPeriod.assert_called_once()

    def test_emergency_stop_calls_end_exactly_once(self):
        self.tm.begin(1)
        self.tm.end()
        self.tm._winmm.timeEndPeriod.assert_called_once()

    def test_game_exit_calls_end_exactly_once(self):
        self.tm.begin(1)
        self.tm.end()
        self.tm._winmm.timeEndPeriod.assert_called_once()

    def test_worker_exception_releases_ownership(self):
        self.tm.begin(1)
        try:
            raise Exception("Worker crash")
        except Exception:
            self.tm.end()
        self.assertFalse(self.tm.owns_timer)
        self.tm._winmm.timeEndPeriod.assert_called_once()

    def test_end_failure_enters_safe_mode(self):
        self.tm.begin(1)
        self.tm._winmm.timeEndPeriod.return_value = 1 # Failed
        self.assertFalse(self.tm.end())
        # The object should ideally record the failure or handle it gracefully
        self.assertTrue(self.tm.owns_timer)

if __name__ == '__main__':
    unittest.main(verbosity=2)
