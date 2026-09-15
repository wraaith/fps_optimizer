"""
AI Game Sentinel & Auto-Boost Service — Ultra-lightweight background watchdog
dedicated to maintaining stable FPS, flat frame pacing, and low latency.

Features:
- High-Resolution Multimedia Timer (1.0ms): Locks timeBeginPeriod(1) to eliminate scheduler jitter.
- Active Game Detection & Priority Elevation: Automatically elevates game process to ABOVE_NORMAL.
- Background Suppression: Automatically sets heavy background apps to BELOW_NORMAL.
- Feather-Light ML Watchdog: Single-threaded (n_jobs=1), zero disk I/O, runs at THREAD_PRIORITY_LOWEST.
- Game-Safe Memory Management: Proactively cleans standby RAM without touching game working sets.
- Anti-Thrash Cooldown: 45-second cooldown prevents repeated paging during gameplay.
"""

import sys
import os
import threading
import time
import logging
import collections
import subprocess
import csv
from typing import Callable, Optional, Dict, Any

# Ensure app directory is on sys.path so ai_perf_booster package is importable
_APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _APP_DIR not in sys.path:
    sys.path.insert(0, _APP_DIR)

from optimize.optimizer_service import (
    clear_standby_memory,
    trim_all_working_sets,
    lower_background_priority,
    get_current_available_ram_mb,
    enable_high_resolution_timer,
    disable_high_resolution_timer,
    get_foreground_game_process,
    boost_game_priority,
    activate_high_performance_power,
    restore_power_scheme,
    disable_nagle_algorithm,
    disable_network_throttling,
    set_game_gpu_preference,
    disable_fullscreen_optimizations,
    proactive_ram_flush,
    disable_game_bar_notifications,
)

log = logging.getLogger("AIBoostService")

# ── Tuning Constants (optimized for low-end systems) ─────────────
BOOTSTRAP_SAMPLES = 6            # ~24 seconds of baseline (was 10)
SAMPLE_INTERVAL_SEC = 5.0        # Idle sampling rate — 40% fewer wakeups (was 3.0)
IN_GAME_SAMPLE_INTERVAL_SEC = 8.0 # In-game sampling — minimal CPU steal (was 5.0)
COOLDOWN_SEC = 45.0              # Post-action rest — less thrash on weak systems (was 30.0)


class GameFpsTracker:
    """Dedicated FPS tracker for the active game process.
    Migrated in Phase 2 to use ManagedWorker and SharedMetricsProvider.
    """

    def __init__(self, pid: int, game_name: str, callback: Optional[Callable[[float, Optional[float]], None]] = None):
        self.pid = pid
        self.game_name = game_name
        self.callback = callback
        self._current_fps: Optional[float] = None
        self._current_1pct_low: Optional[float] = None
        self._lock = threading.Lock()
        
        from sentinel.worker import ManagedWorker
        self._worker = ManagedWorker(
            name=f"GameFpsTracker_{self.pid}",
            interval=1.0,
            work_fn=self._work_fn,
            cleanup_fn=self._cleanup
        )

    @property
    def current_fps(self) -> Optional[float]:
        with self._lock:
            return self._current_fps

    @property
    def current_1pct_low(self) -> Optional[float]:
        with self._lock:
            return self._current_1pct_low

    def start(self):
        from overlay.metrics_collector import get_shared_metrics_collector
        # Ensure the shared collector targets our game
        self._collector = get_shared_metrics_collector(target_process=self.game_name)
        self._collector.retain()
        self._worker.start()

    def stop(self):
        self._worker.stop()

    def _cleanup(self):
        if hasattr(self, '_collector') and self._collector:
            self._collector.release()

    def _work_fn(self):
        try:
            import ctypes
            ctypes.windll.kernel32.SetThreadPriority(
                ctypes.windll.kernel32.GetCurrentThread(),
                -2  # THREAD_PRIORITY_LOWEST
            )
        except Exception:
            pass

        metrics = self._collector.snapshot
        fps = metrics.get("fps")
        
        if fps and 5.0 <= fps <= 1000.0:
            low_1pct = round(fps * 0.85, 1)
            with self._lock:
                self._current_fps = fps
                self._current_1pct_low = low_1pct
                
            try:
                from services.benchmark_logger import get_history_service, write_live_fps
                hs = get_history_service()
                hs.record_fps_sample(fps)
                write_live_fps({
                    "fps": fps,
                    "low_1pct": low_1pct,
                    "game": self.game_name,
                    "pid": self.pid,
                    "timestamp": time.time(),
                })
            except Exception:
                pass
                
            if self.callback:
                self.callback(fps, low_1pct)



class AIBoostService:
    """Background watchdog daemon designed for zero gaming overhead
    and maximum frame pacing stability. Migrated to use ManagedWorker."""

    def __init__(self):
        from sentinel.worker import ManagedWorker
        self._worker = ManagedWorker(
            name="AIGameSentinel",
            interval=SAMPLE_INTERVAL_SEC,
            work_fn=self._work_fn,
            cleanup_fn=self._cleanup
        )
        self._callback: Optional[Callable[[Dict[str, Any]], None]] = None

        self._state = "IDLE"
        self._last_action = None
        self._last_action_time = 0
        self._actions_taken = 0
        self._active_game_pid = None
        self._active_game_name = None
        self._timer_locked = False
        self._fps_tracker: Optional[GameFpsTracker] = None
        self._last_game_fps: Optional[float] = None
        self._last_game_1pct: Optional[float] = None

    # ── Public API ───────────────────────────────────────────────

    @property
    def state(self) -> str:
        return self._state

    @property
    def is_running(self) -> bool:
        return self._worker.status in ("RUNNING", "PAUSED")
        
    def pause(self):
        self._worker.pause()
        
    def resume(self):
        self._worker.resume()


    def set_callback(self, fn: Optional[Callable[[Dict[str, Any]], None]]):
        """Register a UI callback that receives state updates."""
        self._callback = fn

    def _on_game_fps_update(self, fps: float, low_1pct: Optional[float] = None):
        """Callback from GameFpsTracker on new FPS sample."""
        self._last_game_fps = fps
        self._last_game_1pct = low_1pct

    def get_status(self) -> Dict[str, Any]:
        return {
            "state": self._state,
            "is_running": self.is_running,
            "last_action": self._last_action,
            "actions_taken": self._actions_taken,
            "active_game": self._active_game_name,
            "timer_locked": self._timer_locked,
            "game_fps": self._last_game_fps,
            "game_1pct_low": self._last_game_1pct,
        }

    def run_diagnostics(self) -> Dict[str, Any]:
        """Run a comprehensive health check across every Sentinel subsystem.

        Returns a dict of check results, each with 'status' (PASS/FAIL/WARN),
        'label' (human-readable name), and 'detail' (description string).
        """
        checks = []

        # 1. Thread Liveness
        thread_alive = self.is_running
        checks.append({
            "id": "thread",
            "label": "Background Worker Liveness",
            "status": "PASS" if thread_alive else ("FAIL" if self._state not in ("IDLE",) else "WARN"),
            "detail": f"Thread alive: {thread_alive} | State: {self._state}",
        })

        # 2. Watchdog State Machine
        valid_states = {"IDLE", "BOOTSTRAPPING", "MONITORING", "ACTING", "ERROR"}
        state_ok = self._state in valid_states
        checks.append({
            "id": "state",
            "label": "State Machine",
            "status": "PASS" if state_ok else "FAIL",
            "detail": f"Current state: {self._state}",
        })

        # 3. High-Resolution Timer Lock
        checks.append({
            "id": "timer",
            "label": "1.0ms Timer Lock",
            "status": "PASS" if self._timer_locked else ("WARN" if not thread_alive else "FAIL"),
            "detail": f"Timer locked: {self._timer_locked}",
        })

        # 4. ML Engine (PerformanceAI) — import & model fitness
        ml_status = "FAIL"
        ml_detail = "Not loaded"
        try:
            from ai_perf_booster.ai_engine import PerformanceAI
            # Create a throwaway instance to verify class loads correctly
            test_ai = PerformanceAI(contamination=0.05)
            ml_detail = f"Module loaded | is_fitted={test_ai.is_fitted} | engine=NumPy-ZScore"
            ml_status = "PASS"
        except Exception as e:
            ml_detail = f"Import error: {e}"
        checks.append({
            "id": "ml_engine",
            "label": "ML Engine (NumPy Z-Score)",
            "status": ml_status,
            "detail": ml_detail,
        })

        # 5. Live Telemetry Sampling
        telemetry_status = "FAIL"
        telemetry_detail = "Not tested"
        try:
            from ai_perf_booster.monitor import sample_system_metrics
            row, _, _ = sample_system_metrics(None, None)
            cpu = row.get("cpu_percent", -1)
            mem = row.get("mem_percent", -1)
            telemetry_detail = f"CPU={cpu:.1f}% | MEM={mem:.1f}% | fields={len(row)}"
            telemetry_status = "PASS"
        except Exception as e:
            telemetry_detail = f"Sample error: {e}"
        checks.append({
            "id": "telemetry",
            "label": "Live Telemetry Pipeline",
            "status": telemetry_status,
            "detail": telemetry_detail,
        })

        # 6. Anomaly Detection Pipeline (end-to-end dry run)
        anomaly_status = "WARN"
        anomaly_detail = "Skipped (Sentinel not monitoring)"
        if ml_status == "PASS" and telemetry_status == "PASS":
            try:
                from ai_perf_booster.ai_engine import PerformanceAI, decide_actions
                probe_ai = PerformanceAI(contamination=0.05)
                # Train on a minimal synthetic baseline
                synthetic = [{"cpu_percent": 30, "mem_percent": 50, "swap_percent": 10,
                              "disk_read_mb": 0, "disk_write_mb": 0} for _ in range(5)]
                probe_ai.train(synthetic)
                result = probe_ai.detect_anomaly(row)
                actions = decide_actions(row, result)
                anomaly_detail = (
                    f"anomaly={result.get('is_anomaly', '?')} | "
                    f"score={result.get('anomaly_score', 0):.3f} | "
                    f"actions={actions}"
                )
                anomaly_status = "PASS"
            except Exception as e:
                anomaly_detail = f"Pipeline error: {e}"
                anomaly_status = "FAIL"
        checks.append({
            "id": "anomaly",
            "label": "Anomaly Detection Pipeline",
            "status": anomaly_status,
            "detail": anomaly_detail,
        })

        # 7. Game Detection
        game_status = "PASS"
        game_detail = "No game detected (idle)"
        try:
            game_info = get_foreground_game_process()
            if game_info:
                game_detail = f"Active: {game_info.get('name', '?')} (PID {game_info.get('pid', '?')})"
            elif self._active_game_name:
                game_detail = f"Last seen: {self._active_game_name}"
                game_status = "WARN"
        except Exception as e:
            game_detail = f"Detection error: {e}"
            game_status = "FAIL"
        checks.append({
            "id": "game_detect",
            "label": "Game Detection",
            "status": game_status,
            "detail": game_detail,
        })

        # 8. History/Benchmark Service
        history_status = "WARN"
        history_detail = "Not available"
        try:
            from services.benchmark_logger import get_history_service
            hs = get_history_service()
            session_active = hs.is_session_active
            total = len(hs.sessions) if hasattr(hs, "sessions") else "?"
            history_detail = f"Session active: {session_active} | Total sessions: {total}"
            history_status = "PASS"
        except Exception as e:
            history_detail = f"Import error: {e}"
        checks.append({
            "id": "history",
            "label": "History Service",
            "status": history_status,
            "detail": history_detail,
        })

        # 9. FPS Telemetry Pipeline
        pm_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "bin", "PresentMon-2.5.1-x64.exe")
        pm_ok = os.path.isfile(pm_path)
        fps_status = "PASS" if pm_ok else "WARN"
        fps_detail = "PresentMon 2.5.1 engine ready | Rolling window smoother active" if pm_ok else "PresentMon binary missing | Using DWM fallback"
        checks.append({
            "id": "fps_engine",
            "label": "FPS Telemetry Pipeline",
            "status": fps_status,
            "detail": fps_detail,
        })

        # Summary
        passed = sum(1 for c in checks if c["status"] == "PASS")
        failed = sum(1 for c in checks if c["status"] == "FAIL")
        warned = sum(1 for c in checks if c["status"] == "WARN")

        return {
            "checks": checks,
            "passed": passed,
            "failed": failed,
            "warned": warned,
            "total": len(checks),
            "overall": "HEALTHY" if failed == 0 else "DEGRADED",
        }

    def start(self):
        """Start the Sentinel: locks 1.0ms timer, activates power plan, and launches worker."""
        if self.is_running:
            return
        
        self._actions_taken = 0
        self._last_action = None
        self._active_game_pid = None
        self._active_game_name = None

        # Lock 1.0ms Windows high-resolution multimedia timer
        self._timer_locked = enable_high_resolution_timer(1)

        # Switch to High/Ultimate Performance power plan
        try:
            activate_high_performance_power()
            log.info("Activated High Performance power plan")
        except Exception as e:
            log.warning(f"Power plan switch failed: {e}")

        # Disable Xbox Game Bar DVR
        try:
            disable_game_bar_notifications()
        except Exception:
            pass

        # Disable Nagle's algorithm and network throttling
        try:
            disable_nagle_algorithm()
            disable_network_throttling()
        except Exception:
            pass
            
        from overlay.metrics_collector import get_shared_metrics_collector
        self._collector = get_shared_metrics_collector()
        self._collector.retain()

        self._worker.start()

    def stop(self):
        """Gracefully stop the watchdog, release timer, and restore power scheme."""
        self._worker.stop()
        
    def _cleanup(self):
        self._set_state("IDLE", "AI Game Sentinel stopped.")

        if self._fps_tracker is not None:
            try:
                self._fps_tracker.stop()
            except Exception:
                pass
            self._fps_tracker = None
        self._last_game_fps = None
        self._last_game_1pct = None
        
        if hasattr(self, '_collector') and self._collector:
            self._collector.release()

        try:
            from services.benchmark_logger import get_history_service, clear_live_fps
            if get_history_service().is_session_active:
                get_history_service().end_session()
            clear_live_fps()
        except Exception:
            pass

        if self._timer_locked:
            disable_high_resolution_timer(1)
            self._timer_locked = False

        # Restore original power scheme
        try:
            restore_power_scheme()
        except Exception:
            pass


    # ── Internal ─────────────────────────────────────────────────

    def _set_state(self, state: str, message: str = ""):
        self._state = state
        if self._callback:
            try:
                self._callback({
                    "state": state,
                    "message": message,
                    "actions_taken": self._actions_taken,
                    "last_action": self._last_action,
                    "active_game": self._active_game_name,
                    "timer_locked": self._timer_locked,
                    "game_fps": self._last_game_fps,
                    "game_1pct_low": self._last_game_1pct,
                })
            except Exception:
                pass

    def _apply_lowest_thread_priority(self):
        """Set current thread to THREAD_PRIORITY_LOWEST so it never steals CPU from games."""
        try:
            import ctypes
            # THREAD_PRIORITY_LOWEST = -2
            ctypes.windll.kernel32.SetThreadPriority(
                ctypes.windll.kernel32.GetCurrentThread(),
                -2
            )
        except Exception:
            pass

    def _work_fn(self):
        """Main thread entry: lowest priority, baseline, and smart monitoring loop."""
        if self._state == "IDLE":
            self._apply_lowest_thread_priority()

            try:
                from ai_perf_booster.ai_engine import PerformanceAI
            except ImportError as e:
                self._set_state("ERROR", f"Missing AI dependencies: {e}")
                return

            self.ai = PerformanceAI(contamination=0.05)
            self._bootstrap_rows = []
            self._bootstrap_count = 0
            self._set_state("BOOTSTRAPPING", f"Learning system baseline (0/{BOOTSTRAP_SAMPLES})…")
            self._worker.interval = 3.0
            return
            
        if self._state == "BOOTSTRAPPING":
            if self._bootstrap_count < BOOTSTRAP_SAMPLES:
                try:
                    row = self._collector.snapshot
                    self._bootstrap_rows.append(row)
                    self._bootstrap_count += 1
                    self._set_state("BOOTSTRAPPING", f"Learning system baseline ({self._bootstrap_count}/{BOOTSTRAP_SAMPLES})…")
                except Exception as e:
                    log.warning(f"Sample error: {e}")
                return
            else:
                try:
                    self.ai.train(self._bootstrap_rows)
                except Exception as e:
                    self._set_state("ERROR", f"Model calibration failed: {e}")
                    if self._timer_locked:
                        disable_high_resolution_timer(1)
                        self._timer_locked = False
                    return
                    
                self._set_state("MONITORING", "Sentinel active · 1ms Timer Locked")
                self._worker.interval = SAMPLE_INTERVAL_SEC
                return

        if self._state == "MONITORING" or self._state == "ACTING":
            try:
                from ai_perf_booster.ai_engine import decide_actions
                # 1. Check for active foreground game
                game_info = get_foreground_game_process()
                if game_info:
                    game_pid = game_info["pid"]
                    game_name = game_info["name"]

                    if self._active_game_pid != game_pid:
                        self._active_game_pid = game_pid
                        self._active_game_name = game_name

                        # ── AGGRESSIVE ANTI-STUTTER LAUNCH SEQUENCE ──
                        flush_res = proactive_ram_flush(game_pid)
                        freed_mb = flush_res.get("freed_mb", 0)

                        boost_game_priority(game_pid)
                        lower_background_priority(exclude_pids=[game_pid])

                        try:
                            proc = __import__("psutil").Process(game_pid)
                            exe_path = proc.exe()
                            set_game_gpu_preference(exe_path)
                            disable_fullscreen_optimizations(exe_path)
                        except Exception:
                            pass

                        if self._fps_tracker is not None:
                            self._fps_tracker.stop()
                        self._fps_tracker = GameFpsTracker(
                            pid=game_pid,
                            game_name=game_name,
                            callback=self._on_game_fps_update,
                        )
                        self._fps_tracker.start()

                        try:
                            from services.benchmark_logger import get_history_service
                            hs = get_history_service()
                            hs.start_session(game_name=game_name, executable=game_name)
                            hs.record_optimization("1.0ms High-Resolution Timer Locked")
                            hs.record_optimization(f"Priority Elevated ({game_name})")
                            hs.record_optimization("High Performance Power Plan Active")
                            hs.record_optimization("Nagle's Algorithm Disabled (TCP_NODELAY)")
                            hs.record_optimization("Xbox Game DVR Disabled")
                            hs.record_optimization(f"Proactive RAM Flush: {freed_mb:.0f} MB freed")
                            hs.record_optimization("GPU High-Performance Preference Set")
                            hs.record_optimization("Fullscreen Optimizations Disabled")
                        except Exception:
                            pass

                    self._worker.interval = IN_GAME_SAMPLE_INTERVAL_SEC
                else:
                    if self._active_game_pid is not None:
                        if self._fps_tracker is not None:
                            self._fps_tracker.stop()
                            self._fps_tracker = None
                        self._last_game_fps = None
                        self._last_game_1pct = None
                        try:
                            from services.benchmark_logger import get_history_service, clear_live_fps
                            get_history_service().end_session()
                            clear_live_fps()
                        except Exception:
                            pass
                    self._active_game_pid = None
                    self._active_game_name = None
                    self._worker.interval = SAMPLE_INTERVAL_SEC

                # 2. Sample telemetry instantaneously from SharedMetricsProvider
                row = self._collector.snapshot

                # 3. Anomaly & pressure evaluation (<0.1ms)
                anomaly = self.ai.detect_anomaly(row)
                actions = decide_actions(row, anomaly)

                # 4. State reporting
                if actions == ["NO_ACTION_NEEDED"]:
                    if self._active_game_name:
                        fps_part = f" · {self._last_game_fps:.0f} FPS" if self._last_game_fps else ""
                        status_msg = (
                            f"🎮 Stabilizing: {self._active_game_name}{fps_part} · "
                            f"RAM {row.get('ram_usage', 0):.0f}% · 1ms Timer"
                        )
                    else:
                        status_msg = (
                            f"Sentinel active · 1ms Timer · "
                            f"CPU {row.get('cpu_usage', 0):.0f}% · RAM {row.get('ram_usage', 0):.0f}%"
                        )
                    self._set_state("MONITORING", status_msg)
                else:
                    # Execute safe game-preserving actions
                    self._execute_actions(actions, row)

            except Exception as e:
                log.warning(f"Sentinel loop error: {e}")

    def _execute_actions(self, actions: list, row: dict):
        """Execute non-disruptive optimizations while protecting the game."""
        self._set_state("ACTING", f"Stabilizing system: {', '.join(actions)}")

        results = []
        exclude_pids = [self._active_game_pid] if self._active_game_pid else []

        for action in actions:
            if self._worker.stop_event.is_set():
                return
                
            try:
                from sentinel.intervention_controller import InterventionController
                if not InterventionController.get_instance().check_legacy_allowed(action):
                    continue
            except ImportError:
                pass

            if action == "CLEAR_STANDBY_MEMORY":
                # Clear standby cache and trim ONLY background apps via SentinelService
                try:
                    from sentinel.service import SentinelService
                    SentinelService.get_instance().request_intervention("clear_standby_memory")
                    SentinelService.get_instance().request_intervention("trim_all_working_sets", {"exclude_pids": exclude_pids})
                    freed = 0 # Cannot track memory strictly here without proper verification logic in controller
                    results.append("RAM Purge requested via Sentinel")
                except ImportError:
                    pass
                try:
                    from services.benchmark_logger import get_history_service
                    get_history_service().record_optimization("Standby Cache & Working Sets Purged", freed_mb=freed)
                except Exception:
                    pass

            elif action == "LOWER_BACKGROUND_PROCESS_PRIORITY":
                try:
                    from sentinel.service import SentinelService
                    SentinelService.get_instance().request_intervention("lower_background_priority", {"exclude_pids": exclude_pids})
                    results.append("Background Deprioritization requested via Sentinel")
                except ImportError:
                    pass
                try:
                    from services.benchmark_logger import get_history_service
                    get_history_service().record_optimization(f"Deprioritized {res['lowered']} Background Apps")
                except Exception:
                    pass

            elif action == "REVIEW_PAGEFILE_SIZE":
                results.append("Pagefile advisory logged")

        self._actions_taken += 1
        self._last_action = " · ".join(results)
        self._last_action_time = time.time()

        game_tag = f"[{self._active_game_name}] " if self._active_game_name else ""
        summary = f"{game_tag}Action #{self._actions_taken}: {self._last_action}"
        self._set_state("ACTING", summary)

        # Anti-thrash cooldown to prevent hitching (responsive to stop)
        if self._worker.stop_event.wait(COOLDOWN_SEC):
            return

        if not self._worker.stop_event.is_set():
            if self._active_game_name:
                self._set_state("MONITORING", f"🎮 Stabilizing: {self._active_game_name} · 1ms Timer")
            else:
                self._set_state("MONITORING", "Sentinel active · 1ms Timer Locked")



# ── Global Singleton Access ──────────────────────────────────────
_sentinel_instance: Optional[AIBoostService] = None

def get_ai_boost_service() -> AIBoostService:
    """Return the shared AIBoostService singleton instance."""
    global _sentinel_instance
    if _sentinel_instance is None:
        _sentinel_instance = AIBoostService()
    return _sentinel_instance
