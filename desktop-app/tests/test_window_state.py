import pytest
import tkinter as tk
import sys
import os
from unittest.mock import MagicMock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../app")))
from ui.main_window import MainWindow

def test_window_state_minimization():
    sys.argv.append("--debug")
    app = MainWindow()
    app.update()
    
    assert getattr(app, "_ui_suspended", None) is False
    app.debug_counters["periodic_ui_refreshes"] = 0
    
    # Simulate minimize
    app.state("iconic")
    event = MagicMock()
    event.widget = app
    app._on_window_state_event(event)
    
    assert app._ui_suspended is True
    assert app.debug_counters["periodic_ui_refreshes"] == 0
    
    # Simulate restore
    app.state("normal")
    app._on_window_state_event(event)
    
    assert app._ui_suspended is False
    
    # Should schedule exactly one refresh
    assert app._pending_restore_refresh is not None
    app.update_idletasks() # Let after_idle fire
    app.update()
    
    assert app._pending_restore_refresh is None
    assert app.debug_counters["periodic_ui_refreshes"] == 1
    
    app.destroy()

def test_configure_debouncing():
    app = MainWindow()
    app._debug_mode = True
    app.update()
    
    app.debug_counters["configure_events"] = 0
    
    event = MagicMock()
    event.widget = app
    app._on_root_configure(event)
    app._on_root_configure(event)
    
    assert app.debug_counters["configure_events"] == 2
    app.destroy()
