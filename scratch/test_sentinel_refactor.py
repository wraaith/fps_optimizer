import unittest
from unittest.mock import patch, MagicMock

import sys
import os
APP_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "desktop-app", "app")
if APP_DIR not in sys.path:
    sys.path.insert(0, APP_DIR)

from sentinel.adapters.valorant_adapter import ValorantAdapter
from sentinel.adapters.fortnite_adapter import FortniteAdapter
from sentinel.adapters.cs2_adapter import CounterStrike2Adapter
from sentinel.adapters.apex_legends_adapter import ApexLegendsAdapter
from sentinel.state_machine import StateMachine
from sentinel.models import SentinelState, SentinelMode
from sentinel.intervention_controller import InterventionController

class TestUniversalSentinel(unittest.TestCase):
    
    def test_01_valorant_adapter(self):
        """Verify Valorant adapter logic for network vs render stutter."""
        adapter = ValorantAdapter()
        self.assertEqual(adapter.game_id, "valorant")
        self.assertIn("VALORANT-Win64-Shipping.exe", adapter.executable_names)
        
        stutter = adapter.classify_stutter({"packet_loss": 1, "frame_time_variance": 1})
        self.assertEqual(stutter, "network_jitter")
        
        stutter = adapter.classify_stutter({"packet_loss": 0, "frame_time_variance": 10})
        self.assertEqual(stutter, "render_stutter")
        
    def test_02_fortnite_adapter(self):
        """Verify Fortnite adapter recommendations."""
        adapter = FortniteAdapter()
        recs = adapter.recommendations({"frame_time_variance": 10, "rendering_mode": "DX12"})
        self.assertTrue(any(r["setting"] == "Rendering Mode" for r in recs))
        
    def test_03_cs2_adapter(self):
        """Verify CS2 adapter telemetry classification."""
        adapter = CounterStrike2Adapter()
        stutter = adapter.classify_stutter({"packet_misdelivery": 1, "frame_time_spike": True})
        self.assertEqual(stutter, "packet_loss")
        
        stutter = adapter.classify_stutter({"packet_misdelivery": 0, "frame_time_spike": True})
        self.assertEqual(stutter, "render_stutter")
        
    def test_04_apex_adapter(self):
        """Verify Apex adapter data center recommendations."""
        adapter = ApexLegendsAdapter()
        recs = adapter.recommendations({"latency_spikes": 35})
        self.assertTrue(any(r["setting"] == "Data Center Selection" for r in recs))

    def test_05_state_machine_transitions(self):
        """Verify the state machine changes state correctly."""
        sm = StateMachine()
        self.assertEqual(sm.current_state, SentinelState.IDLE)
        sm.transition_to(SentinelState.OBSERVING)
        self.assertEqual(sm.current_state, SentinelState.OBSERVING)
        sm.transition_to(SentinelState.SAFE_MODE)
        self.assertEqual(sm.current_state, SentinelState.SAFE_MODE)
        
    def test_06_intervention_controller_gating(self):
        """Verify the controller prevents legacy actions when in MONITOR_ONLY mode."""
        controller = InterventionController.get_instance()
        controller.set_mode(SentinelMode.MONITOR_ONLY)
        
        # Legacy check should return false in monitor only mode
        self.assertFalse(controller.check_legacy_allowed("CLEAR_STANDBY_MEMORY"))
        
        controller.set_mode(SentinelMode.BALANCED)
        self.assertTrue(controller.check_legacy_allowed("CLEAR_STANDBY_MEMORY"))
        
if __name__ == "__main__":
    unittest.main()
