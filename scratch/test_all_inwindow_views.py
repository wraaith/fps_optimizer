import sys
import os
import unittest

sys.path.insert(0, os.path.abspath("desktop-app/app"))

import customtkinter as ctk
from ui.main_window import MainWindow
from optimize.optimize_view import OptimizeView


class TestAllInWindowViews(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.window = MainWindow()
        cls.window.withdraw()

    @classmethod
    def tearDownClass(cls):
        try:
            for after_id in cls.window.tk.eval('after info').split():
                try:
                    cls.window.after_cancel(after_id)
                except Exception:
                    pass
            cls.window.destroy()
        except Exception:
            pass

    def test_full_inwindow_navigation_and_zero_popups(self):
        """Verify seamless in-window transitions for all 4 sub-panels with 0 popups."""
        win = self.window
        win.show_optimize()
        win.update()

        opt_view = win.current_view
        self.assertIsInstance(opt_view, OptimizeView)

        # Helper to check zero popups
        def assert_zero_popups():
            toplevels = [c for c in win.winfo_children() if isinstance(c, ctk.CTkToplevel)]
            self.assertEqual(len(toplevels), 0, f"Found unexpected CTkToplevel popup: {toplevels}")

        # 1. Dashboard active
        self.assertTrue(bool(opt_view.basic_frame.grid_info()))
        assert_zero_popups()

        # 2. Process Terminator
        opt_view._open_process_killer()
        win.update()
        assert_zero_popups()
        self.assertTrue(bool(opt_view.process_killer_frame.grid_info()))
        self.assertFalse(bool(opt_view.basic_frame.grid_info()))

        # Back to Dashboard
        opt_view.show_dashboard()
        win.update()
        self.assertTrue(bool(opt_view.basic_frame.grid_info()))
        self.assertFalse(bool(opt_view.process_killer_frame.grid_info()))

        # 3. Sentinel Diagnostics
        opt_view._open_sentinel_diagnostics()
        win.update()
        assert_zero_popups()
        self.assertTrue(bool(opt_view.diagnostics_frame.grid_info()))
        self.assertFalse(bool(opt_view.basic_frame.grid_info()))

        # Back to Dashboard
        opt_view.show_dashboard()
        win.update()
        self.assertTrue(bool(opt_view.basic_frame.grid_info()))
        self.assertFalse(bool(opt_view.diagnostics_frame.grid_info()))

        # 4. Network Stabilizer (Normal window shift to NetworkView)
        opt_view._open_network_dialog()
        win.update()
        assert_zero_popups()
        self.assertEqual(type(win.current_view).__name__, "NetworkView")
        self.assertEqual(win._active_nav_btn, win.network_button)

        # Back to Game Booster Dashboard via back button
        win.current_view.back_btn.invoke()
        win.update()
        self.assertEqual(type(win.current_view).__name__, "OptimizeView")
        self.assertEqual(win._active_nav_btn, win.optimize_button)
        opt_view = win.current_view

        # 5. SysMain Storage Tweaker
        opt_view._open_sysmain_dialog()
        win.update()
        assert_zero_popups()
        self.assertTrue(bool(opt_view.sysmain_frame.grid_info()))
        self.assertFalse(bool(opt_view.basic_frame.grid_info()))

        # Back to Dashboard
        opt_view.show_dashboard()
        win.update()
        self.assertTrue(bool(opt_view.basic_frame.grid_info()))
        self.assertFalse(bool(opt_view.sysmain_frame.grid_info()))

        # 6. Test theme toggles while sub-panel is open
        opt_view.show_diagnostics()
        win.update()
        opt_view.apply_theme(is_cyber=True)
        win.update()
        opt_view.apply_theme(is_cyber=False)
        win.update()
        self.assertTrue(bool(opt_view.diagnostics_frame.grid_info()))
        opt_view.show_dashboard()
        win.update()
        self.assertTrue(bool(opt_view.basic_frame.grid_info()))


if __name__ == "__main__":
    unittest.main()
