"""
Comprehensive functional tests for the AI Sentinel Service.

Covers:
- Lifecycle (start, stop, pause, resume, idempotency)
- Emergency stop and safe mode
- Event timeline (bounded deque, thread safety, metadata)
- State machine transitions
- Intervention gateway (mode gating, blocked ops counter)
- Metrics health structure and status values
- Session summary export structure
- Advanced debug info
- Worker exception handling
- Session ID management across stop/emergency cycles
"""

import sys
import os
import time
import threading
import uuid
import pytest
from unittest.mock import patch, MagicMock, PropertyMock

# Ensure app directory is importable
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../app")))

from sentinel.service import SentinelService
from sentinel.models import SentinelMode, SentinelState
from sentinel.intervention_controller import InterventionController
from sentinel.state_machine import StateMachine


# ──────────────────────────────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def reset_singletons():
    """Reset singleton state before every test to guarantee isolation."""
    SentinelService._instance = None
    InterventionController._instance = None
    yield
    SentinelService._instance = None
    InterventionController._instance = None


@pytest.fixture
def mock_ai_boost():
    """Mock the AI boost service so we never touch real game processes."""
    with patch("sentinel.service.SentinelService._get_ai_boost_service") as mock_get:
        mock_svc = MagicMock()
        mock_svc.is_running = False
        mock_svc.state = "IDLE"
        mock_svc._worker_id = "SentinelWorker-Test"
        mock_get.return_value = mock_svc
        yield mock_svc


@pytest.fixture
def service(mock_ai_boost):
    """Provide a fresh SentinelService instance with mocked AI boost."""
    svc = SentinelService.get_instance()
    return svc


# ══════════════════════════════════════════════════════════════════════
# 1. LIFECYCLE TESTS
# ══════════════════════════════════════════════════════════════════════

class TestLifecycle:
    def test_start_transitions_to_observing(self, service, mock_ai_boost):
        """Starting the sentinel transitions state to OBSERVING."""
        assert service.get_state() == SentinelState.IDLE
        service.start()
        assert service.is_running()
        assert service.get_state() == SentinelState.OBSERVING
        mock_ai_boost.start.assert_called_once()
        service.stop()

    def test_stop_returns_to_idle(self, service, mock_ai_boost):
        """Stopping transitions back to IDLE."""
        service.start()
        service.stop()
        assert not service.is_running()
        assert service.get_state() == SentinelState.IDLE

    def test_stop_rolls_back_active(self, service, mock_ai_boost):
        """Stop calls priority_manager.rollback_all and timer_manager.end."""
        service.start()
        service.priority_manager = MagicMock()
        service.timer_manager = MagicMock()
        service.stop()
        service.priority_manager.rollback_all.assert_called_once()
        service.timer_manager.end.assert_called_once()

    def test_pause_resume_lifecycle(self, service, mock_ai_boost):
        """Pausing and resuming delegates to the AI boost service."""
        service.start()
        service.pause()
        assert service._is_paused is True
        mock_ai_boost.pause.assert_called_once()

        service.resume()
        assert service._is_paused is False
        mock_ai_boost.resume.assert_called_once()
        service.stop()

    def test_double_start_is_idempotent(self, service, mock_ai_boost):
        """Calling start() twice doesn't re-initialize or double-start."""
        service.start()
        service.start()  # Should be a no-op
        assert mock_ai_boost.start.call_count == 1
        service.stop()

    def test_double_stop_is_safe(self, service, mock_ai_boost):
        """Calling stop() when already stopped is a safe no-op."""
        service.start()
        service.stop()
        # Second stop should not raise
        service.stop()
        assert not service.is_running()

    def test_pause_when_not_running_is_noop(self, service, mock_ai_boost):
        """Pausing when not running does nothing."""
        service.pause()
        mock_ai_boost.pause.assert_not_called()

    def test_resume_when_not_paused_is_noop(self, service, mock_ai_boost):
        """Resuming when not paused does nothing."""
        service.start()
        service.resume()
        mock_ai_boost.resume.assert_not_called()
        service.stop()


# ══════════════════════════════════════════════════════════════════════
# 2. EMERGENCY STOP TESTS
# ══════════════════════════════════════════════════════════════════════

class TestEmergencyStop:
    def test_emergency_stop_enters_safe_mode(self, service, mock_ai_boost):
        """Emergency stop transitions to SAFE_MODE."""
        service.start()
        service.emergency_stop()
        assert service.get_state() == SentinelState.SAFE_MODE
        assert not service.is_running()

    def test_emergency_stop_resets_session_id(self, service, mock_ai_boost):
        """Emergency stop generates a new session ID."""
        service.start()
        old_session = service.session_id
        service.emergency_stop()
        assert service.session_id != old_session

    def test_emergency_stop_locks_monitor_only(self, service, mock_ai_boost):
        """Emergency stop forces mode to MONITOR_ONLY."""
        service.set_mode(SentinelMode.ADVANCED)
        service.start()
        service.emergency_stop()
        assert service.controller.mode == SentinelMode.MONITOR_ONLY

    def test_emergency_stop_logs_rollback_event(self, service, mock_ai_boost):
        """Emergency stop logs both rollback and safe mode events."""
        service.start()
        service.emergency_stop()
        timeline = service.get_event_timeline()
        event_types = [e["event"] for e in timeline]
        assert "Rollback attempted" in event_types
        assert "Safe mode entered" in event_types


# ══════════════════════════════════════════════════════════════════════
# 3. EVENT TIMELINE TESTS
# ══════════════════════════════════════════════════════════════════════

class TestEventTimeline:
    def test_log_event_appends_to_timeline(self, service):
        """Logged events appear in the timeline."""
        service.log_event("Test event", "Some details")
        timeline = service.get_event_timeline()
        assert any(e["event"] == "Test event" for e in timeline)
        assert any(e["details"] == "Some details" for e in timeline)

    def test_event_timeline_bounded_at_200(self, service):
        """Timeline deque never grows beyond 200 entries."""
        for i in range(250):
            service.log_event(f"Event_{i}", f"Detail_{i}")
        timeline = service.get_event_timeline()
        assert len(timeline) == 200
        # Oldest events should have been evicted (Event_0 through Event_49)
        event_names = [e["event"] for e in timeline]
        assert "Event_0" not in event_names
        assert "Event_249" in event_names

    def test_event_timeline_thread_safety(self, service):
        """Concurrent writes to the timeline don't corrupt it."""
        errors = []

        def writer(start):
            try:
                for i in range(50):
                    service.log_event(f"Thread_{start}_Event_{i}")
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=writer, args=(t,)) for t in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5.0)

        assert len(errors) == 0
        timeline = service.get_event_timeline()
        # 200 max, but we wrote 250 + the initial "Ledger loaded" event
        assert len(timeline) <= 200

    def test_event_includes_metadata(self, service):
        """Events can carry arbitrary metadata dicts."""
        service.log_event("MetaTest", "details", metadata={"key": "value", "count": 42})
        timeline = service.get_event_timeline()
        meta_event = [e for e in timeline if e["event"] == "MetaTest"]
        assert len(meta_event) == 1
        assert meta_event[0]["metadata"]["key"] == "value"
        assert meta_event[0]["metadata"]["count"] == 42

    def test_event_has_timestamp(self, service):
        """Each event gets a timestamp."""
        before = time.time()
        service.log_event("TimestampTest")
        after = time.time()
        timeline = service.get_event_timeline()
        ts_event = [e for e in timeline if e["event"] == "TimestampTest"][0]
        assert before <= ts_event["timestamp"] <= after

    def test_empty_metadata_defaults_to_dict(self, service):
        """Events without metadata default to an empty dict, not None."""
        service.log_event("NoMeta", "detail")
        timeline = service.get_event_timeline()
        no_meta = [e for e in timeline if e["event"] == "NoMeta"][0]
        assert no_meta["metadata"] == {}


# ══════════════════════════════════════════════════════════════════════
# 4. STATE MACHINE TESTS
# ══════════════════════════════════════════════════════════════════════

class TestStateMachine:
    def test_initial_state_is_idle(self, service):
        """Fresh service starts in IDLE state."""
        assert service.get_state() == SentinelState.IDLE

    def test_state_transitions_tracked(self, service, mock_ai_boost):
        """State transitions are recorded via the state machine."""
        service.start()
        assert service.get_state() == SentinelState.OBSERVING

        service.controller.state_machine.transition_to(SentinelState.ANOMALY_DETECTED)
        assert service.get_state() == SentinelState.ANOMALY_DETECTED

        service.stop()
        assert service.get_state() == SentinelState.IDLE

    def test_get_state_returns_enum(self, service):
        """get_state always returns a SentinelState enum member."""
        state = service.get_state()
        assert isinstance(state, SentinelState)


# ══════════════════════════════════════════════════════════════════════
# 5. INTERVENTION GATEWAY TESTS
# ══════════════════════════════════════════════════════════════════════

class TestInterventionGateway:
    def test_monitor_only_blocks_non_cleanup(self, service, mock_ai_boost):
        """MONITOR_ONLY blocks all interventions except process_cleanup."""
        service.set_mode(SentinelMode.MONITOR_ONLY)
        service.start()
        result = service.request_intervention("lower_background_priority")
        assert result["status"] == "blocked"
        assert result["reason"] == "MONITOR_ONLY"
        service.stop()

    def test_service_not_running_blocks_interventions(self, service, mock_ai_boost):
        """When the service is not running, non-cleanup interventions are blocked."""
        result = service.request_intervention("timer_resolution")
        assert result["status"] == "blocked"
        assert result["reason"] == "SERVICE_NOT_ACTIVE"

    def test_process_cleanup_dry_run_blocked_when_active(self, service, mock_ai_boost):
        """Real (non-dry_run) process_cleanup is blocked while sentinel is active."""
        service.set_mode(SentinelMode.ADVANCED)
        service.start()
        result = service.request_intervention("process_cleanup", {"dry_run": False})
        assert result["status"] == "blocked"
        assert result["reason"] == "Sentinel is active"
        service.stop()

    def test_process_cleanup_dry_run_allowed_when_active(self, service, mock_ai_boost):
        """Dry-run process_cleanup goes through even while active (defaults dry_run=True)."""
        service.set_mode(SentinelMode.ADVANCED)
        service.start()
        # Default dry_run is True, so it should be dispatched (not blocked by sentinel active check)
        result = service.request_intervention("process_cleanup", {"dry_run": True})
        # It will be dispatched to the controller, result depends on controller behavior
        assert result["status"] != "blocked" or result.get("reason") != "Sentinel is active"
        service.stop()

    def test_advanced_mode_allows_interventions(self, service, mock_ai_boost):
        """ADVANCED mode allows interventions to pass through."""
        service.set_mode(SentinelMode.ADVANCED)
        service.start()
        result = service.request_intervention("lower_background_priority")
        assert result["status"] == "applied"
        service.stop()

    def test_blocked_operations_counter_increments(self, service, mock_ai_boost):
        """Each blocked intervention increments the blocked ops counter."""
        service.set_mode(SentinelMode.MONITOR_ONLY)
        service.start()
        initial = service._blocked_operations_count
        service.request_intervention("some_intervention")
        service.request_intervention("another_intervention")
        assert service._blocked_operations_count == initial + 2
        service.stop()

    def test_intervention_result_structure(self, service, mock_ai_boost):
        """All intervention results contain required keys."""
        service.set_mode(SentinelMode.MONITOR_ONLY)
        service.start()
        result = service.request_intervention("test_op")
        required_keys = {"status", "operation", "system_changed", "rollback_available"}
        assert required_keys.issubset(set(result.keys()))
        service.stop()

    def test_intervention_logs_blocked_event(self, service, mock_ai_boost):
        """Blocked interventions are logged to the event timeline."""
        service.set_mode(SentinelMode.MONITOR_ONLY)
        service.start()
        service.request_intervention("test_blocked")
        timeline = service.get_event_timeline()
        blocked_events = [e for e in timeline if "blocked" in e["event"].lower()]
        assert len(blocked_events) >= 1
        service.stop()


# ══════════════════════════════════════════════════════════════════════
# 6. METRICS HEALTH TESTS
# ══════════════════════════════════════════════════════════════════════

class TestMetricsHealth:
    @patch("psutil.disk_io_counters")
    @patch("psutil.swap_memory")
    @patch("psutil.virtual_memory")
    @patch("psutil.cpu_percent")
    def test_metrics_health_returns_all_required_keys(self, mock_cpu, mock_vmem, mock_swap, mock_disk, service):
        """get_metrics_health returns all expected telemetry metric keys."""
        mock_cpu.return_value = 45.0
        mock_vmem.return_value = MagicMock(percent=60.0)
        mock_swap.return_value = MagicMock(sin=0)
        mock_disk.return_value = MagicMock(read_time=100, read_count=50)

        health = service.get_metrics_health()
        required_keys = {
            "fps", "cpu_usage", "gpu_usage", "ram_pressure",
            "hard_faults", "disk_latency_ms",
        }
        for key in required_keys:
            assert key in health, f"Missing key: {key}"

    @patch("psutil.disk_io_counters")
    @patch("psutil.swap_memory")
    @patch("psutil.virtual_memory")
    @patch("psutil.cpu_percent")
    def test_metrics_health_status_values(self, mock_cpu, mock_vmem, mock_swap, mock_disk, service):
        """Metric status is one of: measured, stale, unavailable, error."""
        mock_cpu.return_value = 50.0
        mock_vmem.return_value = MagicMock(percent=50.0)
        mock_swap.return_value = MagicMock(sin=0)
        mock_disk.return_value = MagicMock(read_time=100, read_count=50)

        health = service.get_metrics_health()
        valid_statuses = {"measured", "stale", "unavailable", "error"}
        for key, val in health.items():
            if isinstance(val, dict) and "status" in val:
                assert val["status"] in valid_statuses, f"{key} has invalid status: {val['status']}"

    @patch("psutil.disk_io_counters")
    @patch("psutil.swap_memory")
    @patch("psutil.virtual_memory")
    @patch("psutil.cpu_percent")
    def test_metrics_health_cpu_measured(self, mock_cpu, mock_vmem, mock_swap, mock_disk, service):
        """CPU usage reports as measured when psutil is available."""
        # cpu_percent is called twice: once for total, once with percpu=True
        mock_cpu.side_effect = lambda interval=None, percpu=False: [30.0, 40.0] if percpu else 35.5
        mock_vmem.return_value = MagicMock(percent=40.0)
        mock_swap.return_value = MagicMock(sin=0)
        mock_disk.return_value = MagicMock(read_time=100, read_count=50)

        health = service.get_metrics_health()
        assert health["cpu_usage"]["status"] == "measured"
        assert "35.5%" == health["cpu_usage"]["value"]

    def test_metrics_health_fps_unavailable_without_presentmon(self, service):
        """FPS is unavailable when PresentMon isn't running."""
        health = service.get_metrics_health()
        assert health["fps"]["status"] == "unavailable"
        assert health["fps"]["value"] is None

    def test_metrics_health_each_entry_has_source(self, service):
        """Every metric entry includes a data source identifier."""
        health = service.get_metrics_health()
        for key, val in health.items():
            if isinstance(val, dict):
                assert "source" in val, f"Metric '{key}' missing 'source' field"


# ══════════════════════════════════════════════════════════════════════
# 7. SESSION SUMMARY TESTS
# ══════════════════════════════════════════════════════════════════════

class TestSessionSummary:
    def test_export_session_summary_structure(self, service):
        """export_session_summary returns all required top-level keys."""
        summary = service.export_session_summary()
        required_keys = {
            "game", "timestamp", "frame_time_p50_ms", "frame_time_p95_ms",
            "frame_time_p99_ms", "average_fps", "one_percent_low_fps",
            "cpu_usage", "gpu_usage", "available_memory",
            "hard_faults", "disk_latency_ms",
            "network_rtt_ms", "network_jitter_ms", "packet_loss_percent",
            "anomaly_class", "recommendation", "metric_status",
        }
        for key in required_keys:
            assert key in summary, f"Missing summary key: {key}"

    def test_session_summary_anomaly_classification(self, service):
        """Session summary reflects the last anomaly classification."""
        service._last_anomaly = {
            "classification": "cpu_contention",
            "evidence": "Core 3 at 98%",
            "confidence": 0.87,
            "timestamp": time.time(),
        }
        summary = service.export_session_summary()
        assert summary["anomaly_class"] == "cpu_contention"

    def test_session_summary_recommendation_present(self, service):
        """Session summary includes the full recommendation dict."""
        summary = service.export_session_summary()
        rec = summary["recommendation"]
        assert isinstance(rec, dict)
        assert "game" in rec
        assert "action" in rec
        assert "risk" in rec

    def test_session_summary_metric_values_have_status(self, service):
        """Each metric value in the summary carries a status field."""
        summary = service.export_session_summary()
        metric_keys = [
            "frame_time_p50_ms", "frame_time_p95_ms", "frame_time_p99_ms",
            "average_fps", "one_percent_low_fps", "cpu_usage", "gpu_usage",
            "available_memory", "hard_faults", "disk_latency_ms",
            "network_rtt_ms", "network_jitter_ms", "packet_loss_percent",
        ]
        for key in metric_keys:
            assert "status" in summary[key], f"{key} missing 'status'"
            assert "value" in summary[key], f"{key} missing 'value'"

    def test_session_summary_metric_status_active(self, service, mock_ai_boost):
        """metric_status reflects MONITOR_ONLY_ACTIVE."""
        summary = service.export_session_summary()
        assert summary["metric_status"] == "MONITOR_ONLY_ACTIVE"


# ══════════════════════════════════════════════════════════════════════
# 8. ADVANCED DEBUG INFO TESTS
# ══════════════════════════════════════════════════════════════════════

class TestAdvancedDebugInfo:
    def test_debug_info_returns_all_fields(self, service, mock_ai_boost):
        """get_advanced_debug_info contains all expected diagnostic fields."""
        debug = service.get_advanced_debug_info()
        required_keys = {
            "current_mode", "state_machine_state", "state_transitions",
            "worker_status", "worker_id", "stop_event_status",
            "metrics_consumer_count", "presentmon_process_status",
            "timer_ownership_state", "intervention_controller_mode",
            "blocked_operation_count", "last_rollback_result",
            "ledger_schema_version", "safe_mode",
        }
        for key in required_keys:
            assert key in debug, f"Missing debug key: {key}"

    def test_debug_info_mode_and_state(self, service, mock_ai_boost):
        """Debug info accurately reflects mode and state."""
        service.set_mode(SentinelMode.ADVANCED)
        service.start()
        debug = service.get_advanced_debug_info()
        assert debug["current_mode"] == "ADVANCED"
        assert debug["state_machine_state"] == "OBSERVING"
        service.stop()

    def test_debug_info_worker_stopped(self, service, mock_ai_boost):
        """When service is not running, worker_status is STOPPED."""
        mock_ai_boost.is_running = False
        debug = service.get_advanced_debug_info()
        assert debug["worker_status"] == "STOPPED"

    def test_debug_info_blocked_count(self, service, mock_ai_boost):
        """blocked_operation_count reflects actual blocked count."""
        service._blocked_operations_count = 7
        debug = service.get_advanced_debug_info()
        assert debug["blocked_operation_count"] == 7


# ══════════════════════════════════════════════════════════════════════
# 9. WORKER EXCEPTION / GAME EXIT HANDLING
# ══════════════════════════════════════════════════════════════════════

class TestExceptionAndGameExit:
    def test_handle_worker_exception_triggers_emergency(self, service, mock_ai_boost):
        """Worker exception triggers a full emergency stop."""
        service.start()
        service.handle_worker_exception(RuntimeError("GPU driver crash"))
        assert service.get_state() == SentinelState.SAFE_MODE
        assert not service.is_running()
        timeline = service.get_event_timeline()
        safe_events = [e for e in timeline if "Safe mode" in e["event"]]
        assert len(safe_events) >= 1

    def test_handle_game_exit_logs_event(self, service, mock_ai_boost):
        """Game exit is logged to the event timeline."""
        service.start()
        service.handle_game_exit()
        timeline = service.get_event_timeline()
        game_events = [e for e in timeline if "Game detected" in e["event"]]
        assert len(game_events) == 1
        assert "terminated" in game_events[0]["details"]
        service.stop()

    def test_handle_game_exit_sets_ai_idle(self, service, mock_ai_boost):
        """Game exit signals the AI boost service to go idle."""
        service.start()
        # handle_game_exit checks self._ai_boost_service (not _get_ai_boost_service)
        service._ai_boost_service = mock_ai_boost
        service.handle_game_exit()
        mock_ai_boost._set_state.assert_called_once_with("IDLE", "Game exited.")
        service.stop()


# ══════════════════════════════════════════════════════════════════════
# 10. SESSION ID MANAGEMENT
# ══════════════════════════════════════════════════════════════════════

class TestSessionIdManagement:
    def test_session_id_changes_on_stop(self, service, mock_ai_boost):
        """Stopping the service generates a fresh session ID."""
        service.start()
        old_id = service.session_id
        service.stop()
        assert service.session_id != old_id

    def test_session_id_changes_on_emergency_stop(self, service, mock_ai_boost):
        """Emergency stop generates a new session ID."""
        service.start()
        old_id = service.session_id
        service.emergency_stop()
        assert service.session_id != old_id

    def test_session_id_is_valid_uuid(self, service):
        """Session ID is a valid UUID4 string."""
        try:
            uuid.UUID(service.session_id, version=4)
        except ValueError:
            pytest.fail(f"session_id is not a valid UUID4: {service.session_id}")

    def test_token_manager_synced_with_session_id(self, service, mock_ai_boost):
        """Token manager session_id stays in sync after stop."""
        service.start()
        service.stop()
        assert service.token_manager.session_id == service.session_id

    def test_token_manager_reset_on_stop(self, service, mock_ai_boost):
        """Token manager reset is called on stop."""
        service.token_manager = MagicMock()
        service.token_manager.session_id = service.session_id
        service.start()
        service.stop()
        service.token_manager.reset.assert_called()


# ══════════════════════════════════════════════════════════════════════
# 11. ACTIVE GAME INFO
# ══════════════════════════════════════════════════════════════════════

class TestActiveGameInfo:
    def test_no_game_detected(self, service, mock_ai_boost):
        """When no game is running, returns detected=False."""
        info = service.get_active_game_info()
        assert info["detected"] is False
        assert info["pid"] is None

    def test_game_detected_via_ai_boost(self, service, mock_ai_boost):
        """Game detected through AI boost service fallback."""
        mock_ai_boost._active_game_pid = 12345
        mock_ai_boost._active_game_name = "VALORANT"
        service._ai_boost_service = mock_ai_boost

        info = service.get_active_game_info()
        assert info["detected"] is True
        assert info["pid"] == 12345
        assert info["name"] == "VALORANT"

    def test_no_intervention_active_in_monitor_only(self, service):
        """is_intervention_active always returns False (monitor-only mode)."""
        assert service.is_intervention_active() is False


# ══════════════════════════════════════════════════════════════════════
# 12. SINGLETON PATTERN
# ══════════════════════════════════════════════════════════════════════

class TestSingleton:
    def test_get_instance_returns_same_object(self, mock_ai_boost):
        """get_instance always returns the same SentinelService."""
        s1 = SentinelService.get_instance()
        s2 = SentinelService.get_instance()
        assert s1 is s2

    def test_fresh_instance_after_reset(self, mock_ai_boost):
        """After resetting _instance, a new object is created."""
        s1 = SentinelService.get_instance()
        SentinelService._instance = None
        s2 = SentinelService.get_instance()
        assert s1 is not s2
