import os
import sys
import unittest
from unittest.mock import patch

APP_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "desktop-app", "app"))
if APP_DIR not in sys.path:
    sys.path.insert(0, APP_DIR)

from sentinel.service import SentinelService
from sentinel.models import SentinelMode
from sentinel.intervention_controller import InterventionController

class TestBackendEnforcement(unittest.TestCase):
    def setUp(self):
        self.service = SentinelService.get_instance()
        # Ensure we are running for tests
        self.service._is_running = True
        self.service._is_paused = False
        self.service.set_mode(SentinelMode.MONITOR_ONLY)

    @patch('network_stabilizer.tweaks_engine.TweaksEngine.apply_dns_servers')
    def test_dns_blocked_monitor_only(self, mock_apply_dns):
        res = self.service.request_intervention("dns", {
            "adapter_id": "Ethernet",
            "servers": ["1.1.1.1", "1.0.0.1"]
        })
        self.assertEqual(res["status"], "blocked")
        self.assertEqual(res["reason"], "MONITOR_ONLY")
        self.assertFalse(res["system_changed"])
        self.assertEqual(mock_apply_dns.call_count, 0)

    @patch('subprocess.run')
    def test_power_plan_blocked_monitor_only(self, mock_run):
        res = self.service.request_intervention("power_plan", {
            "requested_guid": "8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c"
        })
        self.assertEqual(res["status"], "blocked")
        self.assertEqual(res["reason"], "MONITOR_ONLY")
        self.assertFalse(res["system_changed"])
        self.assertEqual(mock_run.call_count, 0)

    @patch('psutil.process_iter')
    def test_process_cleanup_blocked_monitor_only(self, mock_piter):
        res = self.service.request_intervention("process_cleanup", {
            "legacy_mode": True,
            "dry_run": False
        })
        self.assertEqual(res["status"], "blocked")
        self.assertIn(res["reason"], ["Sentinel is active", "MONITOR_ONLY"])
        self.assertFalse(res["system_changed"])
        self.assertEqual(mock_piter.call_count, 0)

    @patch('psutil.process_iter')
    def test_process_cleanup_dry_run_defaults(self, mock_piter):
        self.service.set_mode(SentinelMode.ADVANCED)
        # Test default legacy process cleanup request (which defaults to dry_run = True in execute)
        res = self.service.request_intervention("process_cleanup", {
            "legacy_mode": True,
            "dry_run": True
        })
        self.assertEqual(res["status"], "dry_run")
        self.assertFalse(res["system_changed"])
        
    def test_process_cleanup_rejects_non_legacy(self):
        self.service.set_mode(SentinelMode.ADVANCED)
        res = self.service.request_intervention("process_cleanup", {
            "legacy_mode": False
        })
        self.assertEqual(res["status"], "blocked")
        self.assertEqual(res["reason"], "Requires explicit legacy_mode")
        self.assertFalse(res["system_changed"])

if __name__ == '__main__':
    unittest.main()
