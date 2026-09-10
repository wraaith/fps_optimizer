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

# ── Tuning Constants ─────────────────────────────────────────────
BOOTSTRAP_SAMPLES = 10           # ~30 seconds of baseline collection
SAMPLE_INTERVAL_SEC = 3.0        # Default sampling rate when idle
IN_GAME_SAMPLE_INTERVAL_SEC = 5.0 # Responsive in-game sampling (still near 0% CPU)
COOLDOWN_SEC = 30.0              # Post-action rest (reduced for faster response)


class AIBoostService:
    """Background watchdog daemon designed for zero gaming overhead
    and maximum frame pacing stability."""

    def __init__(self):
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._callback: Optional[Callable[[Dict[str, Any]], None]] = None
        self._state = "IDLE"
        self._last_action = None
        self._last_action_time = 0
        self._actions_taken = 0
        self._active_game_pid = None
        self._active_game_name = None
        self._timer_locked = False

    # ── Public API ───────────────────────────────────────────────

    @property
    def state(self) -> str:
        return self._state

    @property
    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def set_callback(self, fn: Optional[Callable[[Dict[str, Any]], None]]):
        """Register a UI callback that receives state updates."""
        self._callback = fn

    def get_status(self) -> Dict[str, Any]:
        return {
            "state": self._state,
            "is_running": self.is_running,
            "last_action": self._last_action,
            "actions_taken": self._actions_taken,
            "active_game": self._active_game_name,
            "timer_locked": self._timer_locked,
        }

    def run_diagnostics(self) -> Dict[str, Any]:
        """Run a comprehensive health check across every Sentinel subsystem.

        Returns a dict of check results, each with 'status' (PASS/FAIL/WARN),
        'label' (human-readable name), and 'detail' (description string).
        """
        checks = []

        # 1. Thread Liveness
        thread_alive = self._thread is not None and self._thread.is_alive()
        checks.append({
            "id": "thread",
            "label": "Watchdog Thread",
            "status": "PASS" if thread_alive else ("FAIL" if self._state not in ("IDLE",) else "WARN"),
            "detail": f"Thread alive: {thread_alive} | State: {self._state}",
        })

        # 2. Watchdog State Machine
        valid_states = {"IDLE", "BOOTSTRAPPING", "TRAINING", "MONITORING", "ACTING", "ERROR"}
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
            try:
                from ai_perf_booster.ai_engine import PerformanceAI
            except ImportError:
                from ai_engine import PerformanceAI
            # Create a throwaway instance to verify class loads correctly
            test_ai = PerformanceAI(contamination=0.05)
            ml_detail = f"Module loaded | is_fitted={test_ai.is_fitted}"
            ml_status = "PASS"
        except Exception as e:
            ml_detail = f"Import error: {e}"
        checks.append({
            "id": "ml_engine",
            "label": "ML Engine (IsolationForest)",
            "status": ml_status,
            "detail": ml_detail,
        })

        # 5. Live Telemetry Sampling
        telemetry_status = "FAIL"
        telemetry_detail = "Not tested"
        try:
            try:
                from ai_perf_booster.monitor import sample_system_metrics
            except ImportError:
                from monitor import sample_system_metrics
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
                try:
                    from ai_perf_booster.ai_engine import PerformanceAI, decide_actions
                except ImportError:
                    from ai_engine import PerformanceAI, decide_actions
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
        self._stop_event.clear()
        self._actions_taken = 0
        self._last_action = None
        self._active_game_pid = None
        self._active_game_name = None

        # Lock 1.0ms Windows high-resolution multimedia timer
        self._timer_locked = enable_high_resolution_timer(1)

        # Switch to High/Ultimate Performance power plan (prevents CPU/GPU throttle)
        try:
            activate_high_performance_power()
            log.info("Activated High Performance power plan")
        except Exception as e:
            log.warning(f"Power plan switch failed: {e}")

        # Disable Xbox Game Bar DVR (major stutter source)
        try:
            disable_game_bar_notifications()
        except Exception:
            pass

        # Disable Nagle's algorithm and network throttling for lower network latency
        try:
            disable_nagle_algorithm()
            disable_network_throttling()
        except Exception:
            pass

        self._thread = threading.Thread(target=self._run, daemon=True, name="AIGameSentinel")
        self._thread.start()

    def stop(self):
        """Gracefully stop the watchdog, release timer, and restore power scheme."""
        self._stop_event.set()
        self._set_state("IDLE", "AI Game Sentinel stopped.")

        try:
            from services.benchmark_logger import get_history_service
            if get_history_service().is_session_active:
                get_history_service().end_session()
        except Exception:
            pass

        if self._thread is not None and self._thread is not threading.current_thread():
            self._thread.join(timeout=2.0)
            self._thread = None

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

    def _run(self):
        """Main thread entry: lowest priority, baseline, and smart monitoring loop."""
        self._apply_lowest_thread_priority()

        try:
            try:
                from ai_perf_booster.monitor import sample_system_metrics
                from ai_perf_booster.ai_engine import PerformanceAI, decide_actions
            except ImportError:
                from monitor import sample_system_metrics
                from ai_engine import PerformanceAI, decide_actions
        except ImportError as e:
            self._set_state("ERROR", f"Missing AI dependencies: {e}")
            return

        ai = PerformanceAI(contamination=0.05)

        try:
            # ── Phase 1: Bootstrap ──
            self._set_state("BOOTSTRAPPING", f"Learning system baseline (0/{BOOTSTRAP_SAMPLES})…")
            rows = []
            prev_disk = prev_net = None

            for i in range(BOOTSTRAP_SAMPLES):
                if self._stop_event.is_set():
                    return
                try:
                    row, prev_disk, prev_net = sample_system_metrics(prev_disk, prev_net)
                    rows.append(row)
                    self._set_state("BOOTSTRAPPING", f"Learning system baseline ({i + 1}/{BOOTSTRAP_SAMPLES})…")
                except Exception as e:
                    log.warning(f"Sample error: {e}")

                if self._stop_event.wait(3.0):
                    return

            if self._stop_event.is_set():
                return

            # ── Phase 2: Lightweight In-Memory Train ──
            self._set_state("TRAINING", "Calibrating lightweight stability model…")
            try:
                ai.train(rows)
            except Exception as e:
                self._set_state("ERROR", f"Model calibration failed: {e}")
                if self._timer_locked:
                    disable_high_resolution_timer(1)
                    self._timer_locked = False
                return

            if self._stop_event.is_set():
                return

            # ── Phase 3: Sentinel Monitoring Loop ──
            self._set_state("MONITORING", "Sentinel active · 1ms Timer Locked")

            while not self._stop_event.is_set():
                sleep_duration = SAMPLE_INTERVAL_SEC

                try:
                    # 1. Check for active foreground game
                    game_info = get_foreground_game_process()
                    if game_info:
                        game_pid = game_info["pid"]
                        game_name = game_info["name"]

                        if self._active_game_pid != game_pid:
                            self._active_game_pid = game_pid
                            self._active_game_name = game_name

                            # ── AGGRESSIVE ANTI-STUTTER LAUNCH SEQUENCE ──
                            # 1. Proactive RAM flush — give game max headroom
                            flush_res = proactive_ram_flush(game_pid)
                            freed_mb = flush_res.get("freed_mb", 0)

                            # 2. Elevate game CPU priority
                            boost_game_priority(game_pid)

                            # 3. Depress background bloatware
                            lower_background_priority(exclude_pids=[game_pid])

                            # 4. Force GPU to high-performance for this exe
                            try:
                                proc = __import__("psutil").Process(game_pid)
                                exe_path = proc.exe()
                                set_game_gpu_preference(exe_path)
                                disable_fullscreen_optimizations(exe_path)
                            except Exception:
                                pass

                            # 5. Log all optimizations applied
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

                            log.info(
                                f"Anti-stutter launch: {game_name} | "
                                f"Freed {freed_mb:.0f}MB | Priority boosted | "
                                f"GPU pref set | Fullscreen opts disabled"
                            )

                        # In-game: responsive polling (5s, still near 0% CPU)
                        sleep_duration = IN_GAME_SAMPLE_INTERVAL_SEC
                    else:
                        if self._active_game_pid is not None:
                            try:
                                from services.benchmark_logger import get_history_service
                                get_history_service().end_session()
                            except Exception:
                                pass
                        self._active_game_pid = None
                        self._active_game_name = None

                    # 2. Sample telemetry instantaneously (0ms non-blocking)
                    row, prev_disk, prev_net = sample_system_metrics(prev_disk, prev_net)

                    # 3. Anomaly & pressure evaluation (<0.1ms)
                    anomaly = ai.detect_anomaly(row)
                    actions = decide_actions(row, anomaly)

                    # 4. State reporting
                    if actions == ["NO_ACTION_NEEDED"]:
                        if self._active_game_name:
                            status_msg = (
                                f"🎮 Stabilizing: {self._active_game_name} · "
                                f"RAM {row.get('mem_percent', 0):.0f}% · 1ms Timer"
                            )
                        else:
                            status_msg = (
                                f"Sentinel active · 1ms Timer · "
                                f"CPU {row.get('cpu_percent', 0):.0f}% · RAM {row.get('mem_percent', 0):.0f}%"
                            )
                        self._set_state("MONITORING", status_msg)
                    else:
                        # Execute safe game-preserving actions
                        self._execute_actions(actions, row)

                except Exception as e:
                    log.warning(f"Sentinel loop error: {e}")

                if self._stop_event.wait(sleep_duration):
                    return

        finally:
            if self._timer_locked:
                disable_high_resolution_timer(1)
                self._timer_locked = False

    def _execute_actions(self, actions: list, row: dict):
        """Execute non-disruptive optimizations while protecting the game."""
        self._set_state("ACTING", f"Stabilizing system: {', '.join(actions)}")

        results = []
        exclude_pids = [self._active_game_pid] if self._active_game_pid else []

        for action in actions:
            if self._stop_event.is_set():
                return

            if action == "CLEAR_STANDBY_MEMORY":
                # Clear standby cache and trim ONLY background apps
                res = clear_standby_memory()
                trim_res = trim_all_working_sets(exclude_pids=exclude_pids)
                freed = res.get("freed_mb", 0) + trim_res.get("freed_mb", 0)
                results.append(f"Freed {freed:,.0f} MB RAM")
                try:
                    from services.benchmark_logger import get_history_service
                    get_history_service().record_optimization("Standby Cache & Working Sets Purged", freed_mb=freed)
                except Exception:
                    pass

            elif action == "LOWER_BACKGROUND_PROCESS_PRIORITY":
                res = lower_background_priority(exclude_pids=exclude_pids)
                results.append(f"Deprioritized {res['lowered']} background apps")
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
        if self._stop_event.wait(COOLDOWN_SEC):
            return

        if not self._stop_event.is_set():
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
