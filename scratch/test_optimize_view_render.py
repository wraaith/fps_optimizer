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
            for after_id in cls.root.tk.eval('after info').split():
                try:
                    cls.root.after_cancel(after_id)
                except Exception:
                    pass
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

        # Check Network Stabilizer card
        self.assertTrue(hasattr(view, "net_card"))
        self.assertTrue(hasattr(view, "net_quick_btn"))
        self.assertTrue(hasattr(view, "net_advanced_btn"))
        self.assertTrue(hasattr(view, "net_title"))
        self.assertTrue(hasattr(view, "net_status_label"))

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

    def test_04_process_killer_dialog(self):
        """Verify the dedicated Process Terminator renders in the same window (no popup)."""
        view = OptimizeView(self.root)
        self.root.update()

        # Dashboard should be visible initially, process killer hidden
        self.assertTrue(bool(view.basic_frame.grid_info()))
        self.assertFalse(bool(view.process_killer_frame.grid_info()))

        # Open process killer (in same window)
        view._open_process_killer()
        self.root.update()

        # Check that NO popup CTkToplevel was created
        toplevel_count = sum(1 for c in view.winfo_children() if isinstance(c, ctk.CTkToplevel))
        self.assertEqual(toplevel_count, 0)

        # Check that process killer frame is now gridded and basic frame is removed
        self.assertTrue(bool(view.process_killer_frame.grid_info()))
        self.assertFalse(bool(view.basic_frame.grid_info()))

        # Test process list rendering and select all
        procs = [
            {"name": "chrome.exe", "pid": 1234, "memory_mb": 450.0},
            {"name": "discord.exe", "pid": 5678, "memory_mb": 250.0}
        ]
        view._pk_render_procs(procs)
        self.root.update()
        self.assertEqual(len(view._pk_cbs), 2)

        view._pk_toggle_select_all()
        self.root.update()
        self.assertEqual(sum(cb.get() for cb, _, _, _ in view._pk_cbs), 2)
        self.assertIn("2 process(es) selected", view.pk_summary_lbl.cget("text"))

        # Return to dashboard via show_dashboard()
        view.show_dashboard()
        self.root.update()

        # Dashboard should be visible again
        self.assertTrue(bool(view.basic_frame.grid_info()))
        self.assertFalse(bool(view.process_killer_frame.grid_info()))

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

    def test_06_network_stabilizer_card(self):
        """Verify the Network Stabilizer card transitions in-window (no popup)."""
        view = OptimizeView(self.root)
        self.root.update()

        # Check button text
        self.assertIn("STABILIZE", view.net_quick_btn.cget("text").upper())
        self.assertIn("ADVANCED", view.net_advanced_btn.cget("text").upper())

        # Check initial state
        self.assertTrue(bool(view.basic_frame.grid_info()))
        self.assertFalse(bool(view.network_frame.grid_info()))

        # Open network panel (in same window)
        view._open_network_dialog()
        self.root.update()

        # Verify zero CTkToplevel popups created
        toplevel_count = sum(1 for c in view.winfo_children() if isinstance(c, ctk.CTkToplevel))
        self.assertEqual(toplevel_count, 0)

        # Verify network_frame is gridded and dashboard is hidden
        self.assertTrue(bool(view.network_frame.grid_info()))
        self.assertFalse(bool(view.basic_frame.grid_info()))
        self.assertTrue(hasattr(view, "net_back_btn"))
        self.assertTrue(hasattr(view, "net_status_card"))
        self.assertTrue(hasattr(view, "net_scroll"))

        # Render dummy status
        view._net_render_status({
            "connected": True,
            "adapter": "Ethernet",
            "link_speed": "1 Gbps",
            "latency_ms": 15,
            "dns": ["1.1.1.1", "8.8.8.8"]
        })
        self.root.update()
        self.assertIn("Ethernet", view.net_adapter_lbl.cget("text"))
        self.assertIn("15ms", view.net_latency_lbl.cget("text"))

        # Return to dashboard via show_dashboard()
        view.show_dashboard()
        self.root.update()
        self.assertTrue(bool(view.basic_frame.grid_info()))
        self.assertFalse(bool(view.network_frame.grid_info()))

    def test_07_diagnostics_in_window(self):
        """Verify Sentinel Diagnostics renders in-window with zero popup dialogs."""
        view = OptimizeView(self.root)
        self.root.update()

        # Check initial state
        self.assertTrue(bool(view.basic_frame.grid_info()))
        self.assertFalse(bool(view.diagnostics_frame.grid_info()))

        # Open diagnostics (in same window)
        view._open_sentinel_diagnostics()
        self.root.update()

        # Verify zero CTkToplevel popups
        toplevel_count = sum(1 for c in view.winfo_children() if isinstance(c, ctk.CTkToplevel))
        self.assertEqual(toplevel_count, 0)

        # Verify diagnostics frame is visible and basic frame is hidden
        self.assertTrue(bool(view.diagnostics_frame.grid_info()))
        self.assertFalse(bool(view.basic_frame.grid_info()))
        self.assertTrue(hasattr(view, "diag_back_btn"))
        self.assertTrue(hasattr(view, "diag_summary_label"))
        self.assertTrue(hasattr(view, "diag_scroll"))

        # Test diagnostic report rendering
        dummy_report = {
            "overall": "HEALTHY",
            "passed": 3,
            "failed": 0,
            "warned": 0,
            "checks": [
                {"label": "Kernel Timer Lock", "status": "PASS", "detail": "1.0ms high-precision lock active"},
                {"label": "Standby Purge Engine", "status": "PASS", "detail": "Standby memory trim ready"},
                {"label": "Working Set Trimmer", "status": "PASS", "detail": "EmptyWorkingSet callable"}
            ]
        }
        view._diag_render(dummy_report)
        self.root.update()
        self.assertIn("ALL SYSTEMS OPERATIONAL", view.diag_summary_label.cget("text"))
        self.assertIn("3 Passed", view.diag_summary_label.cget("text"))

        # Return to dashboard
        view.show_dashboard()
        self.root.update()
        self.assertTrue(bool(view.basic_frame.grid_info()))
        self.assertFalse(bool(view.diagnostics_frame.grid_info()))

    def test_08_sysmain_in_window(self):
        """Verify SysMain Storage Tweaker renders in-window with zero popup dialogs."""
        view = OptimizeView(self.root)
        self.root.update()

        # Check initial state
        self.assertTrue(bool(view.basic_frame.grid_info()))
        self.assertFalse(bool(view.sysmain_frame.grid_info()))

        # Open SysMain (in same window)
        view._open_sysmain_dialog()
        self.root.update()

        # Verify zero CTkToplevel popups
        toplevel_count = sum(1 for c in view.winfo_children() if isinstance(c, ctk.CTkToplevel))
        self.assertEqual(toplevel_count, 0)

        # Verify sysmain frame is visible and basic frame is hidden
        self.assertTrue(bool(view.sysmain_frame.grid_info()))
        self.assertFalse(bool(view.basic_frame.grid_info()))
        self.assertTrue(hasattr(view, "sm_back_btn"))
        self.assertTrue(hasattr(view, "sm_status_lbl"))
        self.assertTrue(hasattr(view, "sm_toggle_btn"))

        # Test rendering status
        view._sm_render_status({"running": True, "start_type": "auto", "error": None}, has_ssd=True)
        self.root.update()
        self.assertIn("RUNNING", view.sm_status_lbl.cget("text"))
        self.assertIn("SSD detected", view.sm_ssd_lbl.cget("text"))
        self.assertIn("DISABLE SYSMAIN", view.sm_toggle_btn.cget("text").upper())

        # Test rendering stopped status
        view._sm_render_status({"running": False, "start_type": "disabled", "error": None}, has_ssd=True)
        self.root.update()
        self.assertIn("STOPPED", view.sm_status_lbl.cget("text"))
        self.assertIn("ENABLE SYSMAIN", view.sm_toggle_btn.cget("text").upper())

        # Return to dashboard
        view.show_dashboard()
        self.root.update()
        self.assertTrue(bool(view.basic_frame.grid_info()))
        self.assertFalse(bool(view.sysmain_frame.grid_info()))


if __name__ == "__main__":
    unittest.main()


