import os
import sys
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.abspath("desktop-app/app"))

import customtkinter as ctk
from optimize.optimize_view import OptimizeView
from optimize.ai_boost_service import get_ai_boost_service, AIBoostService
from sentinel.service import SentinelService
from sentinel.models import SentinelState, SentinelMode
from ui.sentinel_view import SentinelView


class TestSentinelUnification(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        ctk.set_appearance_mode("dark")
        cls.root = ctk.CTk()
        cls.root.withdraw()

    @classmethod
    def tearDownClass(cls):
        try:
            for after_id in cls.root.tk.eval('after info').split():
                try:
                    cls.root.after_cancel(after_id)
                except Exception:
                    pass
            cls.root.destroy()
        except Exception:
            pass

    def setUp(self):
        self.sentinel_service = SentinelService.get_instance()
        self.ai_service = get_ai_boost_service()
        # Always ensure stopped before each test
        self.sentinel_service.stop()

    def tearDown(self):
        self.sentinel_service.stop()

    def test_01_game_booster_toggle_starts_sentinel_service(self):
        """Starting from Game Booster tab starts SentinelService and updates Universal Sentinel tab."""
        opt_view = OptimizeView(self.root)
        sentinel_view = SentinelView(self.root, service=self.sentinel_service)
        self.root.update()

        self.assertFalse(self.sentinel_service.is_running())
        self.assertEqual(self.sentinel_service.get_state(), SentinelState.IDLE)
        self.assertIn("Start Sentinel", sentinel_view.btn_toggle.cget("text"))

        # Click Game Booster Sentinel toggle
        opt_view._toggle_ai_sentinel_btn()
        self.root.update()

        # Both services should be active
        self.assertTrue(self.sentinel_service.is_running())
        self.assertTrue(self.ai_service.is_running)
        self.assertEqual(self.sentinel_service.get_state(), SentinelState.OBSERVING)

        # Universal Sentinel UI reflects running state
        sentinel_view.refresh()
        self.assertIn("Stop Sentinel", sentinel_view.btn_toggle.cget("text"))
        self.assertIn("RUNNING", sentinel_view.lbl_worker.cget("text"))
        self.assertIn("OBSERVING", sentinel_view.lbl_state.cget("text"))

        # Clean up views
        opt_view.destroy()
        sentinel_view.destroy()

    def test_02_game_booster_toggle_stops_sentinel_service(self):
        """Stopping from Game Booster tab stops SentinelService and resets Universal Sentinel tab."""
        opt_view = OptimizeView(self.root)
        sentinel_view = SentinelView(self.root, service=self.sentinel_service)
        self.root.update()

        # Start service
        self.sentinel_service.start()
        self.root.update()
        self.assertTrue(self.sentinel_service.is_running())

        # Click Game Booster Sentinel toggle to deactivate
        opt_view._toggle_ai_sentinel_btn()
        self.root.update()

        self.assertFalse(self.sentinel_service.is_running())
        self.assertFalse(self.ai_service.is_running)
        self.assertEqual(self.sentinel_service.get_state(), SentinelState.IDLE)

        sentinel_view.refresh()
        self.assertIn("Start Sentinel", sentinel_view.btn_toggle.cget("text"))
        self.assertIn("STOPPED", sentinel_view.lbl_worker.cget("text"))
        self.assertIn("IDLE", sentinel_view.lbl_state.cget("text"))

        opt_view.destroy()
        sentinel_view.destroy()

    def test_03_universal_sentinel_toggle_updates_game_booster(self):
        """Starting and stopping from Universal Sentinel updates Game Booster UI seamlessly."""
        opt_view = OptimizeView(self.root)
        sentinel_view = SentinelView(self.root, service=self.sentinel_service)
        self.root.update()

        # Start from Universal Sentinel view
        sentinel_view._toggle_service()
        self.root.update()

        self.assertTrue(self.sentinel_service.is_running())
        self.assertTrue(self.ai_service.is_running)

        # Notify Game Booster with mock callback update
        opt_view._on_ai_status_update({"state": "MONITORING", "active_game": "Valorant"})
        self.root.update()

        self.assertIn("DEACTIVATE SENTINEL", opt_view.ai_action_btn.cget("text"))
        self.assertIn("●", opt_view.ai_status_badge.cget("text"))

        # Stop from Universal Sentinel view
        sentinel_view._toggle_service()
        self.root.update()

        self.assertFalse(self.sentinel_service.is_running())
        self.assertFalse(self.ai_service.is_running)

        # Game Booster UI receives IDLE state
        opt_view._on_ai_status_update({"state": "IDLE"})
        self.root.update()

        self.assertIn("ACTIVATE SENTINEL", opt_view.ai_action_btn.cget("text"))
        self.assertIn("○ Inactive", opt_view.ai_status_badge.cget("text"))

        opt_view.destroy()
        sentinel_view.destroy()

    def test_04_non_idle_states_always_route_through_sentinel_service_stop(self):
        """
        If _toggle_ai_sentinel_btn() is clicked while SentinelService is in
        INTERVENTION_ACTIVE, VERIFYING, COOLDOWN, or SAFE_MODE, the stop must
        route strictly through SentinelService.stop() — never AIBoostService.stop().
        """
        opt_view = OptimizeView(self.root)
        self.root.update()

        test_states = [
            SentinelState.INTERVENTION_ACTIVE,
            SentinelState.VERIFYING,
            SentinelState.COOLDOWN,
            SentinelState.SAFE_MODE,
        ]

        for state in test_states:
            # Set state machine into target state
            self.sentinel_service.controller.state_machine.transition_to(state)
            self.assertEqual(self.sentinel_service.get_state(), state)

            with patch.object(self.sentinel_service, 'stop', wraps=self.sentinel_service.stop) as spy_sentinel_stop:
                with patch.object(self.ai_service, 'stop', wraps=self.ai_service.stop) as spy_ai_stop:
                    # Click toggle in Game Booster
                    opt_view._toggle_ai_sentinel_btn()
                    self.root.update()

                    # Must have called SentinelService.stop()
                    spy_sentinel_stop.assert_called_once()
                    # State machine must have transitioned back to IDLE
                    self.assertEqual(self.sentinel_service.get_state(), SentinelState.IDLE)
                    self.assertFalse(self.sentinel_service.is_running())

        opt_view.destroy()

    def test_05_single_process_level_instances(self):
        """Confirm there is exactly one process-level instance of SentinelService and AIBoostService."""
        s1 = SentinelService.get_instance()
        s2 = SentinelService.get_instance()
        self.assertIs(s1, s2)

        b1 = get_ai_boost_service()
        b2 = get_ai_boost_service()
        self.assertIs(b1, b2)

        # The internal boost service wrapped by SentinelService must be the exact same singleton
        self.assertIs(s1._get_ai_boost_service(), b1)


if __name__ == "__main__":
    unittest.main()
