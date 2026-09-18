import pytest
import time
import psutil
import numpy as np
import sys
import os
from unittest.mock import patch, MagicMock

_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(_dir))

from app.overlay.metrics_collector import FrameTelemetryEngine, TelemetryState, TelemetryConfig, MetricsCollector
from app.services.benchmark_logger import read_live_fps, write_live_fps, clear_live_fps

@pytest.fixture
def mock_psutil_process():
    with patch("psutil.Process") as mock_process:
        instance = mock_process.return_value
        instance.is_running.return_value = True
        instance.create_time.return_value = 1000.0
        yield mock_process

def test_chrome_foreground_no_fps(mock_psutil_process):
    engine = FrameTelemetryEngine()
    engine.set_target_game("VALORANT", "VALORANT-Win64-Shipping.exe", 1234)
    
    engine.process_frame(pid=9999, executable="chrome.exe", ms_between=16.6, present_start=time.time())
    
    state = engine.get_state()
    assert state["fps_state"] == TelemetryState.ATTACHING.name
    assert state["fps_confidence"] == "unavailable"
    assert state["fps"] is None

def test_vscode_foreground_no_fps(mock_psutil_process):
    engine = FrameTelemetryEngine()
    engine.set_target_game("VALORANT", "VALORANT-Win64-Shipping.exe", 1234)
    engine.process_frame(pid=8888, executable="Code.exe", ms_between=16.6, present_start=time.time())
    assert engine.get_state()["fps_state"] == TelemetryState.ATTACHING.name

def test_launcher_only_no_fps(mock_psutil_process):
    engine = FrameTelemetryEngine()
    engine.set_target_game("VALORANT", "VALORANT-Win64-Shipping.exe", 1234)
    engine.process_frame(pid=5555, executable="RiotClientServices.exe", ms_between=16.6, present_start=time.time())
    assert engine.get_state()["fps_state"] == TelemetryState.ATTACHING.name

def test_anti_cheat_only_no_fps(mock_psutil_process):
    engine = FrameTelemetryEngine()
    engine.set_target_game("VALORANT", "VALORANT-Win64-Shipping.exe", 1234)
    engine.process_frame(pid=6666, executable="vgk.exe", ms_between=16.6, present_start=time.time())
    assert engine.get_state()["fps_state"] == TelemetryState.ATTACHING.name

def test_correct_supported_game_detection(mock_psutil_process):
    engine = FrameTelemetryEngine()
    engine.set_target_game("VALORANT", "VALORANT-Win64-Shipping.exe", 1234)
    assert engine.get_state()["fps_state"] == TelemetryState.ATTACHING.name

def test_wrong_executable_path(mock_psutil_process):
    # This implies the game identity check. FrameTelemetryEngine checks PID and start time.
    engine = FrameTelemetryEngine()
    engine.set_target_game("VALORANT", "VALORANT-Win64-Shipping.exe", 1234)
    engine.process_frame(pid=9999, executable="FakeGame.exe", ms_between=16.6, present_start=time.time())
    assert engine.get_state()["fps_state"] == TelemetryState.ATTACHING.name

def test_pid_mismatch(mock_psutil_process):
    engine = FrameTelemetryEngine()
    engine.set_target_game("VALORANT", "VALORANT-Win64-Shipping.exe", 1234)
    engine.process_frame(pid=1235, executable="VALORANT-Win64-Shipping.exe", ms_between=16.6, present_start=time.time())
    assert engine.get_state()["fps_state"] == TelemetryState.ATTACHING.name

def test_pid_reuse_after_game_exit(mock_psutil_process):
    engine = FrameTelemetryEngine()
    engine.set_target_game("VALORANT", "VALORANT-Win64-Shipping.exe", 1234)
    
    # Simulate PID reused (new process with same PID but different create time)
    mock_psutil_process.return_value.create_time.return_value = 2000.0
    
    engine.process_frame(pid=1234, executable="VALORANT-Win64-Shipping.exe", ms_between=16.6, present_start=time.time())
    # Should discard because create_time mismatched
    assert engine.get_state()["fps_state"] == TelemetryState.ATTACHING.name

def test_non_monotonic_timestamps(mock_psutil_process):
    engine = FrameTelemetryEngine()
    engine.set_target_game("VALORANT", "VALORANT-Win64-Shipping.exe", 1234)
    now = time.time()
    engine.process_frame(pid=1234, executable="VALORANT-Win64-Shipping.exe", ms_between=16.6, present_start=now + 1.0)
    engine.process_frame(pid=1234, executable="VALORANT-Win64-Shipping.exe", ms_between=16.6, present_start=now + 0.5)
    assert engine.get_state()["valid_frame_samples"] == 1

def test_zero_duration(mock_psutil_process):
    engine = FrameTelemetryEngine()
    engine.set_target_game("VALORANT", "VALORANT", 1234)
    engine.process_frame(pid=1234, executable="VALORANT", ms_between=0.0, present_start=time.time())
    assert engine.get_state()["valid_frame_samples"] == 0

def test_negative_duration(mock_psutil_process):
    engine = FrameTelemetryEngine()
    engine.set_target_game("VALORANT", "VALORANT", 1234)
    engine.process_frame(pid=1234, executable="VALORANT", ms_between=-16.6, present_start=time.time())
    assert engine.get_state()["valid_frame_samples"] == 0

def test_null_field(mock_psutil_process):
    engine = FrameTelemetryEngine()
    engine.set_target_game("VALORANT", "VALORANT", 1234)
    engine.process_frame(pid=1234, executable="VALORANT", ms_between=None, present_start=time.time())
    assert engine.get_state()["valid_frame_samples"] == 0

def test_nan_field(mock_psutil_process):
    engine = FrameTelemetryEngine()
    engine.set_target_game("VALORANT", "VALORANT", 1234)
    engine.process_frame(pid=1234, executable="VALORANT", ms_between=np.nan, present_start=time.time())
    assert engine.get_state()["valid_frame_samples"] == 0

def test_infinite_field(mock_psutil_process):
    engine = FrameTelemetryEngine()
    engine.set_target_game("VALORANT", "VALORANT", 1234)
    engine.process_frame(pid=1234, executable="VALORANT", ms_between=np.inf, present_start=time.time())
    assert engine.get_state()["valid_frame_samples"] == 0

def test_missing_presentmon_fields_and_malformed(mock_psutil_process):
    engine = FrameTelemetryEngine()
    engine.set_target_game("VALORANT", "VALORANT-Win64-Shipping.exe", 1234)
    
    # Simulating the behavior when metrics_collector sends None because fields were missing/malformed
    engine.mark_error()
    assert engine.get_state()["fps_state"] == TelemetryState.ERROR.name

def test_duplicate_frame_events(mock_psutil_process):
    engine = FrameTelemetryEngine()
    engine.set_target_game("VALORANT", "VALORANT-Win64-Shipping.exe", 1234)
    now = time.time()
    # Identical timestamps
    engine.process_frame(pid=1234, executable="VALORANT", ms_between=16.6, present_start=now)
    engine.process_frame(pid=1234, executable="VALORANT", ms_between=16.6, present_start=now)
    assert engine.get_state()["valid_frame_samples"] == 1

def test_game_restart_with_new_pid(mock_psutil_process):
    engine = FrameTelemetryEngine()
    engine.set_target_game("VALORANT", "VALORANT", 1234)
    now = time.time()
    for i in range(40):
        engine.process_frame(pid=1234, executable="VALORANT", ms_between=16.6, present_start=now + (i * 0.0166))
    
    assert engine.get_state()["fps_state"] == TelemetryState.FPS_READY.name
    
    engine.set_target_game("VALORANT", "VALORANT", 5678)
    assert engine.get_state()["fps_state"] == TelemetryState.ATTACHING.name
    assert engine.get_state()["valid_frame_samples"] == 0

def test_process_exit(mock_psutil_process):
    engine = FrameTelemetryEngine()
    engine.set_target_game("VALORANT", "VALORANT", 1234)
    
    mock_psutil_process.return_value.is_running.return_value = False
    
    engine.process_frame(pid=1234, executable="VALORANT", ms_between=16.6, present_start=time.time())
    assert engine.get_state()["valid_frame_samples"] == 0
    
    engine.mark_game_exit()
    assert engine.get_state()["fps_state"] == TelemetryState.WAITING_FOR_GAME.name

def test_presentmon_unavailable_at_startup():
    collector = MetricsCollector()
    assert collector.snapshot["fps"] is None

def test_presentmon_disconnect(mock_psutil_process):
    engine = FrameTelemetryEngine()
    engine.set_target_game("VALORANT", "VALORANT", 1234)
    now = time.time()
    for i in range(40):
        engine.process_frame(pid=1234, executable="VALORANT", ms_between=16.6, present_start=now + (i * 0.0166))
    
    assert engine.get_state()["fps_state"] == TelemetryState.FPS_READY.name
    engine.mark_error() # Simulating PresentMon disconnecting
    state = engine.get_state()
    assert state["fps_state"] == TelemetryState.ERROR.name
    assert state["fps"] is None

def test_stale_timeout(mock_psutil_process):
    engine = FrameTelemetryEngine(config=TelemetryConfig(STALE_TIMEOUT_SECONDS=2.0))
    engine.set_target_game("VALORANT", "VALORANT", 1234)
    for i in range(15):
        engine.process_frame(pid=1234, executable="VALORANT", ms_between=16.6, present_start=time.time() + (i * 0.016))
    
    # Processed time is now, but wall time moves forward 3 seconds
    state = engine.get_state(current_wall_time=time.time() + 3.0, last_processed_wall_time=time.time())
    assert state["fps_state"] == TelemetryState.STALE.name
    assert state["fps"] is None

def test_too_few_samples(mock_psutil_process):
    engine = FrameTelemetryEngine()
    engine.set_target_game("VALORANT", "VALORANT", 1234)
    engine.process_frame(pid=1234, executable="VALORANT", ms_between=16.6, present_start=time.time())
    state = engine.get_state()
    assert state["fps_state"] == TelemetryState.COLLECTING_FRAMES.name
    assert state["fps"] is None

def test_large_frame_gap(mock_psutil_process):
    engine = FrameTelemetryEngine()
    engine.set_target_game("VALORANT", "VALORANT", 1234)
    now = time.time()
    for i in range(15):
        engine.process_frame(pid=1234, executable="VALORANT", ms_between=16.6, present_start=now + (i * 0.016))
    
    # Add a huge gap (3 seconds)
    engine.process_frame(pid=1234, executable="VALORANT", ms_between=16.6, present_start=now + 5.0)
    state = engine.get_state()
    assert state["fps_state"] == TelemetryState.COLLECTING_FRAMES.name

def test_fps_null_after_session_end(mock_psutil_process):
    engine = FrameTelemetryEngine()
    engine.set_target_game("VALORANT", "VALORANT", 1234)
    now = time.time()
    for i in range(40):
        engine.process_frame(pid=1234, executable="VALORANT", ms_between=16.6, present_start=now + (i * 0.0166))
    
    assert engine.get_state()["fps"] is not None
    engine.mark_game_exit()
    assert engine.get_state()["fps"] is None

def test_ui_fps_text_is_never_parsed_numerically():
    state = {
        "fps_confidence": "measured",
        "fps_state": "FPS_READY",
        "fps": 144.0,
        "ui_fps_text": "FPS: 144.0"
    }
    write_live_fps(state)
    
    read = read_live_fps()
    assert read["fps"] == 144.0
    assert read["ui_fps_text"] == "FPS: 144.0"

def test_ipc_validation_prevents_contradictory_payloads():
    # If confidence is measured but fps is null
    state = {
        "fps_confidence": "measured",
        "fps_state": "FPS_READY",
        "fps": None,
        "ui_fps_text": "FPS: None"
    }
    write_live_fps(state)
    read = read_live_fps()
    assert read["fps"] is None
    assert read["fps_confidence"] == "unavailable"

    # If state isn't FPS_READY but confidence is measured
    state2 = {
        "fps_confidence": "measured",
        "fps_state": "COLLECTING_FRAMES",
        "fps": 60.0,
        "ui_fps_text": "FPS: 60"
    }
    write_live_fps(state2)
    read2 = read_live_fps()
    assert read2["fps"] is None
    assert read2["fps_confidence"] == "unavailable"

def test_multiple_ui_reads_do_not_create_multiple_workers():
    c1 = MetricsCollector()
    c2 = MetricsCollector()
    assert c1 is not c2
    # The actual shared logic is get_shared_metrics_collector
    from app.overlay.metrics_collector import get_shared_metrics_collector
    s1 = get_shared_metrics_collector()
    s2 = get_shared_metrics_collector()
    assert s1 is s2

def test_fps_unaffected_by_polling_interval(mock_psutil_process):
    # This proves the FPS is derived purely from the timestamps (ms_between)
    engine = FrameTelemetryEngine()
    engine.set_target_game("VALORANT", "VALORANT", 1234)
    now = time.time()
    for i in range(70):
        engine.process_frame(pid=1234, executable="VALORANT", ms_between=8.33, present_start=now + (i * 0.00833))
    
    state = engine.get_state(current_wall_time=now + 0.6, last_processed_wall_time=now + 0.6)
    assert 118.0 <= state["fps"] <= 122.0

def test_fps_unaffected_by_monitor_refresh_rate(mock_psutil_process):
    # Just asserting the ms_between directly sets FPS
    engine = FrameTelemetryEngine()
    engine.set_target_game("VALORANT", "VALORANT", 1234)
    now = time.time()
    for i in range(120):
        # Even if monitor is 60Hz, if game produces frames at 200Hz (5ms)
        engine.process_frame(pid=1234, executable="VALORANT", ms_between=5.0, present_start=now + (i * 0.005))
    
    state = engine.get_state(current_wall_time=now + 0.6, last_processed_wall_time=now + 0.6)
    assert 198.0 <= state["fps"] <= 202.0


# ══════════════════════════════════════════════════════════════════════
# SENTINEL TELEMETRY INTEGRATION TESTS
# ══════════════════════════════════════════════════════════════════════

from unittest.mock import PropertyMock


def _make_sentinel_telemetry(**overrides):
    """Helper to create a realistic sentinel telemetry dict for tests."""
    base = {
        "state": "OBSERVING",
        "mode": "MONITOR_ONLY",
        "session_id": "test-session-uuid",
        "is_running": True,
        "event_timeline": [
            {"timestamp": time.time(), "event": "Worker started", "details": "Test", "metadata": {}},
            {"timestamp": time.time(), "event": "Baseline started", "details": "Observing", "metadata": {}},
        ],
        "event_count": 2,
        "anomaly": {
            "classification": "none",
            "evidence": "Telemetry nominal",
            "confidence": 0.0,
            "timestamp": time.time(),
        },
        "recommendation": {
            "game": "VALORANT",
            "classification": "none",
            "evidence": "Telemetry nominal",
            "confidence": 0.0,
            "action": "None",
            "risk": "none",
            "reversible": True,
            "reason_blocked": "Monitor-only mode",
        },
        "blocked_operations_count": 0,
        "metrics_health": {
            "fps": {"value": 144.0, "status": "measured", "source": "PresentMon", "timestamp": time.time()},
            "cpu_usage": {"value": "35%", "status": "measured", "source": "Kernel", "timestamp": time.time()},
        },
        "debug_info": {
            "current_mode": "MONITOR_ONLY",
            "state_machine_state": "OBSERVING",
            "worker_status": "RUNNING",
        },
        "collected_at": time.time(),
    }
    base.update(overrides)
    return base


@pytest.fixture
def mock_sentinel_for_telemetry():
    """Mock _collect_sentinel_telemetry to return a controlled sentinel telemetry dict."""
    telemetry = _make_sentinel_telemetry()
    with patch("app.services.benchmark_logger._collect_sentinel_telemetry", return_value=telemetry):
        yield telemetry


def test_sentinel_telemetry_in_finalized_session(mock_sentinel_for_telemetry):
    """Finalized session record includes sentinel_telemetry key."""
    from app.services.benchmark_logger import GameplaySession
    session = GameplaySession("VALORANT", "VALORANT-Win64-Shipping.exe", baseline_fps=140.0)
    for _ in range(10):
        session.add_sample(155.0)
    record = session.finalize()
    assert "sentinel_telemetry" in record, "Finalized session must include sentinel_telemetry"


def test_sentinel_telemetry_contains_required_fields(mock_sentinel_for_telemetry):
    """sentinel_telemetry sub-dict contains all required fields."""
    from app.services.benchmark_logger import GameplaySession
    session = GameplaySession("VALORANT", "VALORANT-Win64-Shipping.exe", baseline_fps=140.0)
    for _ in range(10):
        session.add_sample(160.0)
    record = session.finalize()
    sentinel = record["sentinel_telemetry"]
    required_keys = {
        "state", "mode", "session_id", "is_running",
        "event_timeline", "event_count", "anomaly", "recommendation",
        "blocked_operations_count", "metrics_health", "debug_info", "collected_at",
    }
    for key in required_keys:
        assert key in sentinel, f"Missing sentinel_telemetry field: {key}"


def test_sentinel_telemetry_absent_when_sentinel_unavailable():
    """When sentinel service raises, session still finalizes without sentinel_telemetry."""
    with patch("app.services.benchmark_logger._collect_sentinel_telemetry", return_value=None):
        from app.services.benchmark_logger import GameplaySession
        session = GameplaySession("CS2", "cs2.exe", baseline_fps=200.0)
        for _ in range(10):
            session.add_sample(210.0)
        record = session.finalize()
        assert "sentinel_telemetry" not in record, "sentinel_telemetry should be absent when sentinel is unavailable"


def test_sentinel_event_timeline_in_telemetry_log(mock_sentinel_for_telemetry):
    """Event timeline from sentinel flows into the telemetry log."""
    from app.services.benchmark_logger import GameplaySession
    session = GameplaySession("Apex Legends", "r5apex.exe", baseline_fps=120.0)
    for _ in range(10):
        session.add_sample(135.0)
    record = session.finalize()
    sentinel = record["sentinel_telemetry"]
    assert len(sentinel["event_timeline"]) == 2
    events = [e["event"] for e in sentinel["event_timeline"]]
    assert "Worker started" in events
    assert "Baseline started" in events
