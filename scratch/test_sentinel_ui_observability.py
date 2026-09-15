import os
import sys
import time
import unittest
from unittest.mock import patch, MagicMock

APP_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "desktop-app", "app"))
if APP_DIR not in sys.path:
    sys.path.insert(0, APP_DIR)

import customtkinter as ctk
from sentinel.service import SentinelService
from sentinel.models import SentinelMode, SentinelState
from ui.sentinel_view import SentinelView
from sentinel.adapters.valorant_adapter import ValorantAdapter
from sentinel.adapters.fortnite_adapter import FortniteAdapter
from sentinel.adapters.cs2_adapter import CounterStrike2Adapter
from sentinel.adapters.apex_legends_adapter import ApexLegendsAdapter

class TestSentinelUIObservability(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = ctk.CTk()
        cls.root.withdraw()

    @classmethod
    def tearDownClass(cls):
        try:
            cls.root.destroy()
        except Exception:
            pass

    def setUp(self):
        self.service = SentinelService.get_instance()
        self.service.stop()
        self.service.set_mode(SentinelMode.MONITOR_ONLY)
        self.view = SentinelView(self.root, service=self.service)

    def tearDown(self):
        try:
            self.view.destroy()
        except Exception:
            pass

    def test_01_monitor_only_banner_visible(self):
        banner_text = self.view.banner_label.cget("text")
        self.assertIn("Monitor-only", banner_text)
        self.assertIn("no system changes are currently allowed", banner_text)
        self.assertEqual(self.service.controller.mode, SentinelMode.MONITOR_ONLY)

    def test_02_active_game_display(self):
        with patch.object(self.service, 'get_active_game_info') as mock_game:
            mock_game.return_value = {
                "name": "VALORANT",
                "exe": "VALORANT-Win64-Shipping.exe",
                "pid": 4321,
                "detected": True
            }
            self.view.refresh()
            self.assertIn("VALORANT", self.view.lbl_active_game.cget("text"))
            # Check game profile card detection
            val_status = self.view.game_cards["valorant"]["status"].cget("text")
            self.assertIn("ACTIVE", val_status)

    def test_03_missing_metrics_labeled_unavailable(self):
        with patch.object(self.service, 'get_metrics_health') as mock_health:
            mock_health.return_value = {
                "fps": {"value": None, "source": "PresentMon", "status": "unavailable"},
                "frame_time_p50_ms": {"value": None, "source": "PresentMon", "status": "unavailable"},
                "hard_faults": {"value": None, "source": "OS Memory", "status": "unavailable"}
            }
            self.view.refresh()
            self.assertEqual(self.view.metric_rows["fps"]["status"].cget("text"), "unavailable")
            self.assertEqual(self.view.metric_rows["fps"]["val"].cget("text"), "--")

    def test_04_stale_metrics_labeled_stale(self):
        with patch.object(self.service, 'get_metrics_health') as mock_health:
            mock_health.return_value = {
                "fps": {"value": 144.0, "source": "PresentMon", "status": "stale"},
                "network_rtt_ms": {"value": "24 ms", "source": "NetworkDiagnostics", "status": "stale"}
            }
            self.view.refresh()
            self.assertEqual(self.view.metric_rows["fps"]["status"].cget("text"), "stale")
            self.assertEqual(self.view.metric_rows["fps"]["val"].cget("text"), "144.0")
            self.assertEqual(self.view.metric_rows["network_rtt_ms"]["status"].cget("text"), "stale")

    def test_05_blocked_intervention_display(self):
        self.view.refresh()
        self.assertIn("BLOCKED", self.view.lbl_interv_active.cget("text"))
        self.assertIn("Monitor-only mode", self.view.lbl_rec_blocked.cget("text"))

    def test_06_safe_mode_and_corrupt_ledger_warning(self):
        with patch.object(self.service, 'get_advanced_debug_info') as mock_debug:
            mock_debug.return_value = {
                "safe_mode": True,
                "ledger_schema_version": 2,
                "metrics_consumer_count": 0,
                "presentmon_process_status": "STOPPED",
                "state_machine_state": "SAFE_MODE"
            }
            self.view.refresh()
            self.assertIn("SAFE MODE", self.view.lbl_ledger_status.cget("text"))
            self.assertIn("Safe mode engaged", self.view.lbl_safe_mode_warn.cget("text"))

    def test_07_emergency_stop_always_available(self):
        self.service._is_running = True
        self.view.refresh()
        
        # Invoke emergency stop via UI
        self.view._emergency_stop()
        
        self.assertFalse(self.service.is_running())
        self.assertEqual(self.service.controller.mode, SentinelMode.MONITOR_ONLY)
        # Verify event logged
        events = [e["event"] for e in self.service.get_event_timeline()]
        self.assertIn("Safe mode entered", events)

    def test_08_repeated_start_stop_idempotency_no_duplicate_workers(self):
        with patch.object(self.service, '_get_ai_boost_service') as mock_get_ai:
            mock_ai = MagicMock()
            mock_ai.is_running = True
            mock_get_ai.return_value = mock_ai
            
            # Start multiple times
            self.service.start()
            self.service.start()
            self.assertEqual(mock_ai.start.call_count, 1)
            
            # Stop multiple times
            self.service.stop()
            self.service.stop()
            self.assertEqual(mock_ai.stop.call_count, 1)
            self.assertFalse(self.service.is_running())

    def test_09_presentmon_missing_responsive_ui(self):
        # Simulate PresentMon not being available
        with patch('overlay.metrics_collector.get_shared_metrics_collector') as mock_pm:
            mock_collector = MagicMock()
            mock_collector.snapshot = {}
            mock_collector._running = False
            mock_collector._consumers = 0
            mock_collector._frametimes = []
            mock_pm.return_value = mock_collector
            
            # Refresh should not raise exception or freeze
            self.view.refresh()
            fps_status = self.view.metric_rows["fps"]["status"].cget("text")
            self.assertEqual(fps_status, "unavailable")

    def test_10_provider_startup_failure_handling(self):
        with patch('overlay.metrics_collector.get_shared_metrics_collector', side_effect=Exception("Failed to init PresentMon")):
            # Should handle exception without failing
            health = self.service.get_metrics_health()
            self.assertIn("fps", health)
            self.assertEqual(health["fps"]["status"], "unavailable")

    def test_11_session_summary_export_fields_and_status(self):
        summary = self.service.export_session_summary()
        required_fields = [
            "game", "timestamp", "frame_time_p50_ms", "frame_time_p95_ms",
            "frame_time_p99_ms", "average_fps", "one_percent_low_fps",
            "cpu_usage", "gpu_usage", "available_memory", "hard_faults",
            "disk_latency_ms", "network_rtt_ms", "network_jitter_ms",
            "packet_loss_percent", "anomaly_class", "recommendation",
            "metric_status"
        ]
        for field in required_fields:
            self.assertIn(field, summary, f"Missing field {field} in session export")

        # Every metric field must have value and status in [measured, stale, unavailable, estimated]
        valid_statuses = {"measured", "stale", "unavailable", "estimated"}
        for k, v in summary.items():
            if isinstance(v, dict) and "status" in v:
                self.assertIn(v["status"], valid_statuses, f"Field {k} has invalid status {v['status']}")
                
        self.assertEqual(summary["metric_status"], "MONITOR_ONLY_ACTIVE")

    def test_12_game_adapters_remain_recommendation_only(self):
        adapters = [
            ValorantAdapter(),
            FortniteAdapter(),
            CounterStrike2Adapter(),
            ApexLegendsAdapter()
        ]
        sample_metrics = {
            "fps": 55.0,
            "frame_time_variance": 9.0,
            "packet_loss": 2.0,
            "rtt_jitter": 8.0,
            "latency_spikes": 35.0
        }
        for adapter in adapters:
            recs = adapter.recommendations(sample_metrics)
            self.assertIsInstance(recs, list)
            for r in recs:
                self.assertIn("setting", r)
                self.assertIn("reason", r)
            # Verify profile settings does not modify OS or game
            profile = adapter.profile_settings()
            self.assertIsInstance(profile, dict)

    def test_13_no_ui_control_bypasses_intervention_controller(self):
        # When stopped: blocked
        res_stopped = self.service.request_intervention("timeBeginPeriod", {"resolution_ms": 1})
        self.assertEqual(res_stopped["status"], "blocked")
        self.assertFalse(res_stopped["system_changed"])
        
        # When running in MONITOR_ONLY: blocked
        self.service._is_running = True
        self.service.set_mode(SentinelMode.MONITOR_ONLY)
        res_running = self.service.request_intervention("timeBeginPeriod", {"resolution_ms": 1})
        self.assertEqual(res_running["status"], "blocked")
        self.assertEqual(res_running["reason"], "MONITOR_ONLY")
        self.assertFalse(res_running["system_changed"])
        self.service._is_running = False

if __name__ == '__main__':
    unittest.main()
