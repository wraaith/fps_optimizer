import pytest
from unittest.mock import patch, MagicMock
import tkinter as tk
import customtkinter as ctk

# Import modules to test
from optimize.ai_boost_service import AIBoostService
from ui.theme_manager import PERFORMANCE_THEME, CYBER_THEME
from ui.main_window import MainWindow
from ui.sentinel_view import SentinelView
from sentinel.service import SentinelService
from sentinel.models import SentinelMode

class TestAIBoostService:
    @pytest.fixture
    def mock_sentinel(self):
        with patch('sentinel.service.SentinelService.get_instance') as mock_get:
            mock_inst = MagicMock()
            mock_get.return_value = mock_inst
            yield mock_inst

    @pytest.fixture
    def mock_history(self):
        with patch('services.benchmark_logger.get_history_service') as mock_get:
            mock_inst = MagicMock()
            mock_get.return_value = mock_inst
            yield mock_inst
            
    @pytest.fixture
    def mock_controller(self):
        with patch('sentinel.intervention_controller.InterventionController.get_instance') as mock_get:
            mock_inst = MagicMock()
            mock_get.return_value = mock_inst
            # by default, pretend legacy is allowed
            mock_inst.check_legacy_allowed.return_value = True
            yield mock_inst

    @pytest.fixture(autouse=True)
    def fast_cooldown(self):
        with patch('optimize.ai_boost_service.COOLDOWN_SEC', 0):
            yield

    def test_successful_priority_lowering(self, mock_sentinel, mock_history, mock_controller):
        mock_sentinel.request_intervention.return_value = {
            "status": "applied",
            "details": {"lowered": 5}
        }
        service = AIBoostService()
        service._execute_actions(["LOWER_BACKGROUND_PROCESS_PRIORITY"], [])
        
        mock_sentinel.request_intervention.assert_called_once_with("lower_background_priority", {"exclude_pids": []})
        mock_history.record_optimization.assert_called_once_with("Deprioritized 5 Background Apps")

    def test_failed_priority_lowering(self, mock_sentinel, mock_history, mock_controller):
        mock_sentinel.request_intervention.return_value = {
            "status": "failed",
            "reason": "access denied"
        }
        service = AIBoostService()
        with patch('optimize.ai_boost_service.log') as mock_log:
            service._execute_actions(["LOWER_BACKGROUND_PROCESS_PRIORITY"], [])
            
            mock_sentinel.request_intervention.assert_called_once()
            mock_history.record_optimization.assert_not_called()
            mock_log.info.assert_called_with("AI intervention lower_background_priority was failed: access denied")

    def test_missing_lowered_field(self, mock_sentinel, mock_history, mock_controller):
        mock_sentinel.request_intervention.return_value = {
            "status": "applied",
            # missing details/lowered
        }
        service = AIBoostService()
        service._execute_actions(["LOWER_BACKGROUND_PROCESS_PRIORITY"], [])
        
        mock_history.record_optimization.assert_called_once_with("Deprioritized 0 Background Apps")

    def test_successful_standby_memory_clear(self, mock_sentinel, mock_history, mock_controller):
        mock_sentinel.request_intervention.return_value = {
            "status": "applied",
            "details": {"freed_mb": 1024}
        }
        service = AIBoostService()
        service._execute_actions(["CLEAR_STANDBY_MEMORY"], [])
        
        mock_sentinel.request_intervention.assert_called_once_with("clear_standby_memory", {"exclude_pids": []})
        mock_history.record_optimization.assert_called_once_with("Standby Cache & Working Sets Purged", freed_mb=1024)

    def test_failed_standby_memory_clear(self, mock_sentinel, mock_history, mock_controller):
        mock_sentinel.request_intervention.return_value = {
            "status": "blocked",
            "reason": "dry run"
        }
        service = AIBoostService()
        with patch('optimize.ai_boost_service.log') as mock_log:
            service._execute_actions(["CLEAR_STANDBY_MEMORY"], [])
            
            mock_history.record_optimization.assert_not_called()
            mock_log.info.assert_called_with("AI intervention clear_standby_memory was blocked: dry run")
            
    def test_missing_freed_mb_field(self, mock_sentinel, mock_history, mock_controller):
        mock_sentinel.request_intervention.return_value = {
            "status": "applied"
        }
        service = AIBoostService()
        service._execute_actions(["CLEAR_STANDBY_MEMORY"], [])
        
        mock_history.record_optimization.assert_called_once_with("Standby Cache & Working Sets Purged", freed_mb=0)

    def test_request_intervention_exception(self, mock_sentinel, mock_history, mock_controller):
        mock_sentinel.request_intervention.side_effect = RuntimeError("Service crash")
        service = AIBoostService()
        with patch('optimize.ai_boost_service.log') as mock_log:
            service._execute_actions(["CLEAR_STANDBY_MEMORY"], [])
            mock_history.record_optimization.assert_not_called()
            mock_log.exception.assert_called_once()
            
    def test_monitor_only_blocking(self):
        # Using real SentinelService for this test
        SentinelService._instance = None
        service = SentinelService.get_instance()
        service.set_mode(SentinelMode.MONITOR_ONLY)
        service.start()
        
        res = service.request_intervention("lower_background_priority")
        assert res["status"] == "blocked"
        assert res["reason"] == "MONITOR_ONLY"
        
        service.stop()
        
    def test_dry_run_blocking(self):
        SentinelService._instance = None
        service = SentinelService.get_instance()
        service.set_mode(SentinelMode.ADVANCED)
        service.start()
        
        res = service.request_intervention("process_cleanup", {"dry_run": False})
        assert res["status"] == "blocked"
        assert res["reason"] == "Sentinel is active"
        
        service.stop()

class TestUIThemeAndVisuals:
    def test_theme_keys_completeness(self):
        import re, glob
        keys = set()
        for f in glob.glob('app/ui/**/*.py', recursive=True) + glob.glob('app/overlay/**/*.py', recursive=True):
            content = open(f, encoding='utf-8').read()
            keys.update(re.findall(r'theme\["([^"]+)"\]', content))
            keys.update(re.findall(r"theme\['([^']+)'\]", content))

        missing_perf = keys - set(PERFORMANCE_THEME.keys())
        missing_cyber = keys - set(CYBER_THEME.keys())

        assert len(missing_perf) == 0, f"Missing in Performance: {missing_perf}"
        assert len(missing_cyber) == 0, f"Missing in Cyber: {missing_cyber}"

    def test_unchanged_and_changed_textbox_content(self):
        root = ctk.CTk()
        # Mock the SentinelService
        with patch('sentinel.service.SentinelService.get_instance') as mock_get:
            mock_inst = MagicMock()
            mock_inst.get_event_timeline.return_value = [{"event": "test", "details": "detail", "timestamp": 0}]
            mock_inst.get_metrics_health.return_value = {}
            mock_inst.get_advanced_debug_info.return_value = {}
            mock_get.return_value = mock_inst
            
            view = SentinelView(root)
            view.timeline_textbox.delete = MagicMock()
            
            # Initial call
            view._prev_timeline_content = None
            view.refresh()
            assert view.timeline_textbox.delete.call_count == 1
            
            # Unchanged
            view.refresh()
            assert view.timeline_textbox.delete.call_count == 1
            
            # Changed
            mock_inst.get_event_timeline.return_value = [{"event": "test", "details": "detail", "timestamp": 1}]
            view.refresh()
            assert view.timeline_textbox.delete.call_count == 2
            
            root.destroy()
            
    def test_exception_safe_window_restoration(self):
        app = MainWindow()
        app.withdraw()
        assert app.state() == "withdrawn"
        
        # Test 1: Exception during theme apply doesn't deiconify withdrawn window
        with patch('ui.main_window.get_theme', side_effect=Exception("Theme crash")):
            try:
                app._apply_theme_to_ui(False)
            except Exception:
                pass
            assert app.state() == "withdrawn"
            
        app.deiconify()
        app.state("zoomed")
        
        # Test 2: Zoomed remains zoomed
        app._apply_theme_to_ui(False)
        assert app.state() == "zoomed"
        
        # Test 3: Exception restores to zoomed
        with patch('ui.main_window.get_theme', side_effect=Exception("Theme crash")):
            try:
                app._apply_theme_to_ui(False)
            except Exception:
                pass
            assert app.state() == "zoomed"
            
        app.destroy()

    def test_dpi_initialization_guard(self):
        # verify set DPI aware is only in main.py, and executed early.
        # we check the file directly
        import os
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        main_path = os.path.join(base_dir, 'app', 'main.py')
        content = open(main_path, encoding='utf-8').read()
        assert 'ctypes.windll.shcore.SetProcessDpiAwareness(2)' in content
        assert 'ctypes.windll.user32.SetProcessDPIAware()' in content
        
        import re
        tk_init = content.find('ctk.CTk()')
        dpi_init = content.find('SetProcessDpiAwareness')
        if tk_init != -1 and dpi_init != -1:
            assert dpi_init < tk_init, "DPI initialization must happen before tkinter window creation"
