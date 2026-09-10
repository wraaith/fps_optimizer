import os
import sys
import unittest
import customtkinter as ctk

APP_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "desktop-app", "app")
if APP_DIR not in sys.path:
    sys.path.insert(0, APP_DIR)

from ui.history_view import HistoryView
from services.benchmark_logger import get_history_service
from ui.theme_manager import set_cyber_mode


class TestHistoryViewRender(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        ctk.set_appearance_mode("dark")
        cls.root = ctk.CTk()
        cls.root.geometry("900x600")
        cls.root.withdraw()

    @classmethod
    def tearDownClass(cls):
        try:
            for after_id in cls.root.tk.eval('after info').split():
                cls.root.after_cancel(after_id)
        except Exception:
            pass
        try:
            cls.root.destroy()
        except Exception:
            pass

    def setUp(self):
        self.hs = get_history_service()
        self.hs.clear_history()

    def tearDown(self):
        self.hs.clear_history()

    def test_01_empty_state_rendering(self):
        view = HistoryView(self.root)
        view.pack(fill="both", expand=True)
        self.root.update()

        self.assertEqual(len(self.hs.get_all_sessions()), 0)
        self.assertEqual(view._kpi_cards["sessions"]["val"].cget("text"), "0")
        self.assertEqual(view._kpi_cards["avg_boost"]["val"].cget("text"), "--")
        view.destroy()

    def test_02_populated_state_rendering(self):
        self.hs.create_demo_session(game_name="VALORANT", baseline_fps=144.0, boost_fps=172.0)
        self.hs.create_demo_session(game_name="CS2", baseline_fps=180.0, boost_fps=210.0)

        view = HistoryView(self.root)
        view.pack(fill="both", expand=True)
        self.root.update()

        self.assertEqual(view._kpi_cards["sessions"]["val"].cget("text"), "2")
        self.assertIn("%", view._kpi_cards["avg_boost"]["val"].cget("text"))
        self.assertIn("FPS", view._kpi_cards["low_1pct"]["val"].cget("text"))
        view.destroy()

    def test_03_theme_switching(self):
        self.hs.create_demo_session(game_name="Apex Legends", baseline_fps=110.0, boost_fps=135.0)
        view = HistoryView(self.root)
        view.pack(fill="both", expand=True)
        self.root.update()

        # Switch to Performance mode
        set_cyber_mode(False)
        view.apply_theme(False)
        self.root.update()

        # Switch back to Cyber mode
        set_cyber_mode(True)
        view.apply_theme(True)
        self.root.update()
        view.destroy()

    def test_04_record_demo_action(self):
        view = HistoryView(self.root)
        view.pack(fill="both", expand=True)
        self.root.update()

        self.assertEqual(len(self.hs.get_all_sessions()), 0)
        view._on_record_demo()
        self.root.update()

        self.assertEqual(len(self.hs.get_all_sessions()), 1)
        self.assertEqual(view._kpi_cards["sessions"]["val"].cget("text"), "1")
        view.destroy()


if __name__ == "__main__":
    unittest.main()
