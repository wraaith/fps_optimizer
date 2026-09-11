import os
import sys
import time
import unittest

APP_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "desktop-app", "app")
if APP_DIR not in sys.path:
    sys.path.insert(0, APP_DIR)

from ui.main_window import MainWindow
from ui.theme_manager import set_cyber_mode


class TestGuiResilience(unittest.TestCase):

    def test_rapid_tab_switching_and_theme_toggling(self):
        """Simulate rapid tab switching, theme flipping, and graceful shutdown."""
        app = MainWindow()
        app.withdraw()  # Offscreen

        try:
            # Rapidly cycle through all views
            for _ in range(3):
                app.show_scan()
                app.update()
                app.show_optimize()
                app.update()
                app.show_history()
                app.update()
                app.show_overlay_settings()
                app.update()
                app.show_network()
                app.update()

            # Rapidly toggle Cyber Mode on and off
            for _ in range(4):
                set_cyber_mode(True)
                app.update()
                set_cyber_mode(False)
                app.update()

            # Ensure current_view is healthy
            self.assertIsNotNone(app.current_view)

            # Test History refresh
            app.show_history()
            app.update()
            app.current_view.refresh()
            app.update()

            # Test Game Booster
            app.show_optimize()
            app.update()
            app.current_view._update_ram_label()
            app.update()

        finally:
            app._close_app()


if __name__ == "__main__":
    unittest.main()
