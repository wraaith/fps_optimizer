import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../app")))

import pytest
from unittest.mock import patch, MagicMock
import subprocess
import threading
import tkinter as tk
import customtkinter as ctk

from ui.theme_manager import (
    on_theme_changed,
    remove_theme_listener,
    set_cyber_mode,
    is_cyber_mode,
    _notify_listeners,
    _listeners,
)
from network_stabilizer.snapshot_manager import SnapshotManager
from sentinel.service import SentinelService
from sentinel.providers import LegacyActionProvider
import ai_perf_booster.actions as legacy_actions
from network_stabilizer.diagnostics_engine import DiagnosticsEngine
from services.system_scan import _init_com, _uninit_com


class TestNetworkViewStability:
    @pytest.fixture(autouse=True)
    def setup_tk(self):
        # Create hidden root
        root = ctk.CTk()
        root.withdraw()
        yield root
        try:
            root.destroy()
        except Exception:
            pass

    def test_switch_tab_no_transparency_value_error_in_both_modes(self, setup_tk):
        """Verify that switch_tab never raises ValueError('transparency is not allowed')
        in either Performance Mode or Cyber Mode.
        """
        from ui.network_view import NetworkView

        # Test in Performance Mode (where border_color used to be "transparent")
        set_cyber_mode(False)
        view_perf = NetworkView(setup_tk)
        for tab in view_perf.tab_keys:
            # Should not raise ValueError
            view_perf.switch_tab(tab)
        view_perf.destroy()

        # Test in Cyber Mode
        set_cyber_mode(True)
        view_cyber = NetworkView(setup_tk)
        for tab in view_cyber.tab_keys:
            view_cyber.switch_tab(tab)
        view_cyber.destroy()

    def test_stat_card_update_val_on_destroyed_widget_is_safe(self, setup_tk):
        """Verify StatCard.update_val does not throw _tkinter.TclError when widget is destroyed."""
        from ui.network_view import StatCard

        card = StatCard(setup_tk, title="Ping", value="15ms", subtext="Normal", icon="📡")
        card.update_val("20ms", "Good", "#00ff9f")

        # Destroy widget
        card.destroy()

        # Calling update_val on destroyed card must be a safe no-op
        card.update_val("999ms", "Timeout", "#f43f5e")

    def test_network_view_destroy_unregisters_theme_listener_and_cleans_up(self, setup_tk):
        """Verify NetworkView.destroy cleans up resources and unregisters its theme listener."""
        from ui.network_view import NetworkView

        initial_listener_count = len(_listeners)
        view = NetworkView(setup_tk)
        assert len(_listeners) == initial_listener_count + 1

        # Destroying view should unregister the listener and mark destroyed
        view.destroy()
        assert view._is_destroyed is True
        assert len(_listeners) == initial_listener_count

    def test_network_view_apply_theme_safe_when_destroyed(self, setup_tk):
        """Verify calling apply_theme on a destroyed NetworkView does not crash."""
        from ui.network_view import NetworkView

        view = NetworkView(setup_tk)
        view.destroy()

        # Calling apply_theme directly after destruction must be a safe no-op
        view.apply_theme(True)
        view.apply_theme(False)


class TestThemeManagerStability:
    def test_add_and_remove_theme_listener(self):
        called = []
        listener = lambda mode: called.append(mode)

        on_theme_changed(listener)
        assert listener in _listeners

        remove_theme_listener(listener)
        assert listener not in _listeners

    def test_dead_listener_pruning(self):
        """Verify that dead or failing listeners are safely pruned from _listeners."""
        # Create a mock listener that raises an error simulating a dead widget
        def failing_listener(is_cyber):
            raise RuntimeError("Widget destroyed")

        on_theme_changed(failing_listener)
        assert failing_listener in _listeners

        # Trigger notification – failing listener should be caught and pruned
        _notify_listeners()
        assert failing_listener not in _listeners


class TestSnapshotManagerStability:
    def test_record_change_dictionary_support(self, tmp_path):
        """Verify record_change accepts dictionary input from legacy interventions."""
        state_file = str(tmp_path / "test_state.json")
        sm = SnapshotManager(state_file_path=state_file)

        dns_change = {
            "category": "dns",
            "target": "Ethernet",
            "old_mode": "auto",
            "old_value": ["dhcp"],
            "new_value": ["1.1.1.1", "1.0.0.1"],
        }
        change_id = sm.record_change(dns_change)
        assert change_id is not None
        assert "dns" in change_id

        # Verify change was logged in persistent changes
        changes = sm.get_change_log()
        assert len(changes) == 1
        assert changes[0]["category"] == "dns"
        assert changes[0]["target"] == "Ethernet"
        assert changes[0]["old_mode"] == "auto"

        # Verify power plan record
        power_change = {
            "category": "power_plan",
            "old_value": "381b4222-f694-41f0-9685-ff5bb260df2e",
            "new_value": "8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c",
        }
        p_id = sm.record_change(power_change)
        assert p_id is not None
        assert len(sm.get_change_log()) == 2


class TestSentinelTimerReporting:
    def test_timer_ownership_state_active_and_inactive(self):
        """Verify get_advanced_debug_info accurately reflects timer ownership."""
        svc = SentinelService.get_instance()

        # When timer manager does not own timer
        svc.timer_manager.owns_timer = False
        debug_inactive = svc.get_advanced_debug_info()
        assert debug_inactive["timer_ownership_state"] == "INACTIVE"

        # When timer manager owns timer
        svc.timer_manager.owns_timer = True
        debug_active = svc.get_advanced_debug_info()
        assert debug_active["timer_ownership_state"] == "ACTIVE (1.0ms)"

        # Reset back
        svc.timer_manager.owns_timer = False


class TestLegacyActionProviderAndActions:
    def test_legacy_action_provider_trim_all_working_sets(self):
        """Verify LegacyActionProvider.trim_all_working_sets executes without AttributeError."""
        res = LegacyActionProvider.trim_all_working_sets(exclude_pids=[])
        assert isinstance(res, dict)
        assert "success" in res
        assert "trimmed_count" in res

    def test_legacy_action_provider_clear_standby_memory(self):
        """Verify LegacyActionProvider.clear_standby_memory executes without AttributeError."""
        res = LegacyActionProvider.clear_standby_memory()
        assert isinstance(res, dict)
        assert "success" in res
        assert "freed_mb" in res

    def test_ai_perf_booster_actions_trim_all_working_sets(self):
        """Verify ai_perf_booster.actions has trim_all_working_sets function."""
        assert hasattr(legacy_actions, "trim_all_working_sets")
        res = legacy_actions.trim_all_working_sets(exclude_pids=[])
        assert isinstance(res, list)

    def test_ai_perf_booster_actions_action_map(self):
        """Verify ACTION_MAP contains TRIM_ALL_WORKING_SETS."""
        assert "TRIM_ALL_WORKING_SETS" in legacy_actions.ACTION_MAP


class TestDiagnosticsEngineStability:
    def test_active_proc_cleared_on_timeout(self):
        """Verify self._active_proc is cleared even when subprocess times out."""
        engine = DiagnosticsEngine()

        with patch("subprocess.Popen") as mock_popen:
            mock_proc = MagicMock()
            mock_proc.communicate.side_effect = subprocess.TimeoutExpired(cmd="ping", timeout=1.0)
            mock_popen.return_value = mock_proc

            res = engine.ping_target_bounded("1.1.1.1", probe_count=1, timeout_sec=0.1)
            # Process must be killed and _active_proc must be None
            mock_proc.kill.assert_called()
            assert engine._active_proc is None
            assert res["timeout_count"] == 1


class TestSystemScanComSafety:
    def test_init_and_uninit_com_execution(self):
        """Verify COM apartment initialization helper functions run safely."""
        inited = _init_com()
        # Even if pythoncom is missing or present, _uninit_com must execute safely
        _uninit_com(inited)
