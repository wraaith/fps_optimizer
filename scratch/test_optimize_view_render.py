import sys
import os
import unittest

sys.path.insert(0, os.path.abspath("desktop-app/app"))

import customtkinter as ctk
from optimize.optimize_view import OptimizeView
from optimize.optimizer_service import get_memory_breakdown
from optimize.ai_boost_service import get_ai_boost_service


class TestOptimizeViewRender(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Create a hidden CTk root for testing headless/virtual display
        cls.root = ctk.CTk()
        cls.root.withdraw()

    @classmethod
    def tearDownClass(cls):
        try:
            cls.root.destroy()
        except Exception:
            pass

    def test_01_component_structure(self):
        """Verify all HUD and 4 symmetrical cards are instantiated and configured."""
        view = OptimizeView(self.root)
        self.root.update()

        # Check HUD elements
        self.assertTrue(hasattr(view, "hud_frame"))
        self.assertTrue(hasattr(view, "hud_ram_val"))
        self.assertTrue(hasattr(view, "hud_cache_val"))
        self.assertTrue(hasattr(view, "hud_timer_val"))
        self.assertTrue(hasattr(view, "hud_progress"))

        # Check 4 symmetrical cards
        self.assertTrue(hasattr(view, "boost_card"))
        self.assertTrue(hasattr(view, "boost_btn"))
        self.assertTrue(hasattr(view, "boost_chip_label"))
        self.assertTrue(hasattr(view, "boost_tag"))

        self.assertTrue(hasattr(view, "ai_card"))
        self.assertTrue(hasattr(view, "ai_action_btn"))
        self.assertTrue(hasattr(view, "ai_status_badge"))
        self.assertTrue(hasattr(view, "ai_tag"))

        self.assertTrue(hasattr(view, "killer_card"))
        self.assertTrue(hasattr(view, "process_killer_btn"))
        self.assertTrue(hasattr(view, "killer_chip_label"))
        self.assertTrue(hasattr(view, "killer_tag"))

        self.assertTrue(hasattr(view, "sysmain_card"))
        self.assertTrue(hasattr(view, "sysmain_btn"))
        self.assertTrue(hasattr(view, "sysmain_chip_label"))
        self.assertTrue(hasattr(view, "sysmain_tag"))

        # Check bottom status bar
        self.assertTrue(hasattr(view, "status_bar_frame"))
        self.assertTrue(hasattr(view, "basic_status_label"))

    def test_02_theme_toggle_cyber_and_stealth(self):
        """Verify applying both Cyber mode and Stealth mode completes with zero errors."""
        view = OptimizeView(self.root)
        self.root.update()

        # Cyber mode
        view.apply_theme(is_cyber=True)
        self.root.update()
        self.assertIn("CYBER", view.title_label.cget("text"))

        # Stealth / Performance mode
        view.apply_theme(is_cyber=False)
        self.root.update()
        self.assertIn("Game Booster", view.title_label.cget("text"))

    def test_03_hud_telemetry_display(self):
        """Verify HUD progress bar and labels update accurately from memory breakdown."""
        view = OptimizeView(self.root)
        self.root.update()

        dummy_mb = {
            "total_mb": 16384,
            "available_mb": 8192,
            "used_mb": 8192,
            "percent": 50.0,
            "cached_approx_mb": 3500,
        }
        dummy_ai = {"timer_locked": True}

        view._update_hud_display(dummy_mb, dummy_ai)
        self.root.update()

        self.assertAlmostEqual(view.hud_progress.get(), 0.5, delta=0.05)
        self.assertIn("8.0 GB / 16.0 GB (50%)", view.hud_ram_val.cget("text"))
        self.assertIn("3,500 MB Reclaimable", view.hud_cache_val.cget("text"))
        self.assertIn("1.0ms HIGH-RES (LOCKED)", view.hud_timer_val.cget("text"))

    def test_04_mode_toggle(self):
        """Verify switching between Basic 4-card HUD and Advanced Process list."""
        view = OptimizeView(self.root)
        self.root.update()

        # Switch to Advanced
        view.advanced_mode.set(True)
        view._toggle_mode()
        self.root.update()

        # Switch back to Basic
        view.advanced_mode.set(False)
        view._toggle_mode()
        self.root.update()

    def test_05_ai_sentinel_toggle_button(self):
        """Verify the unified action button toggles AI Sentinel and updates UI."""
        view = OptimizeView(self.root)
        self.root.update()

        # Ensure starting in stopped state
        if view.ai_service.is_running:
            view.ai_service.stop()

        self.assertIn("ACTIVATE SENTINEL", view.ai_action_btn.cget("text"))

        # Toggle ON
        view._toggle_ai_sentinel_btn()
        self.root.update()
        self.assertTrue(view.ai_service.is_running)
        self.assertIn("DEACTIVATE SENTINEL", view.ai_action_btn.cget("text"))
        self.assertIn("1.0ms HIGH-RES (LOCKED)", view.hud_timer_val.cget("text"))

        # Toggle OFF
        view._toggle_ai_sentinel_btn()
        self.root.update()
        self.assertFalse(view.ai_service.is_running)
        self.assertIn("ACTIVATE SENTINEL", view.ai_action_btn.cget("text"))
        self.assertIn("15.6ms (DEFAULT)", view.hud_timer_val.cget("text"))


if __name__ == "__main__":
    unittest.main()
