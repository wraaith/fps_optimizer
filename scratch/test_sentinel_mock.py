import unittest
import sys
import os

APP_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "desktop-app", "app")
if APP_DIR not in sys.path:
    sys.path.insert(0, APP_DIR)

from sentinel.service import SentinelService
from sentinel.models import SentinelMode

class TestMockedInterventions(unittest.TestCase):
    def setUp(self):
        self.service = SentinelService.get_instance()
        self.service.start()
        
    def tearDown(self):
        self.service.stop()

    def test_monitor_only_blocks_interventions(self):
        """Monitor-only mode must block all interventions."""
        self.service.set_mode(SentinelMode.MONITOR_ONLY)
        result = self.service.request_intervention("timeBeginPeriod", {"resolution_ms": 1})
        self.assertFalse(result, "Monitor-only mode should block timeBeginPeriod")

    def test_mock_timer_intervention(self):
        """Timer intervention must succeed when active."""
        self.service.set_mode(SentinelMode.ADVANCED)
        result = self.service.request_intervention("timeBeginPeriod", {"resolution_ms": 1})
        self.assertTrue(result)
        
        # Verify it can be ended
        result_end = self.service.request_intervention("timeEndPeriod")
        self.assertTrue(result_end)

if __name__ == "__main__":
    unittest.main()
