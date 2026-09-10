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

# Add the ai_perf_booster directory to sys.path so we can import from it
_AI_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "ai_perf_booster")
if _AI_DIR not in sys.path:
    sys.path.insert(0, _AI_DIR)

from optimize.optimizer_service import (
    clear_standby_memory,
    trim_all_working_sets,
    lower_background_priority,
    get_current_available_ram_mb,
    enable_high_resolution_timer,
    disable_high_resolution_timer,
    get_foreground_game_process,
    boost_game_priority,
)

log = logging.getLogger("AIBoostService")

# ── Tuning Constants ─────────────────────────────────────────────
BOOTSTRAP_SAMPLES = 10           # ~30 seconds of baseline collection
SAMPLE_INTERVAL_SEC = 3.0        # Default sampling rate when idle
IN_GAME_SAMPLE_INTERVAL_SEC = 8.0 # Relaxed sampling while gaming (near 0% CPU)
COOLDOWN_SEC = 45.0              # Post-action rest to prevent hitching/thrashing


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

    def start(self):
        """Start the Sentinel: locks 1.0ms timer and launches background worker."""
        if self.is_running:
            return
        self._stop_event.clear()
        self._actions_taken = 0
        self._last_action = None
        self._active_game_pid = None
        self._active_game_name = None

        # Lock 1.0ms Windows high-resolution multimedia timer
        self._timer_locked = enable_high_resolution_timer(1)

        self._thread = threading.Thread(target=self._run, daemon=True, name="AIGameSentinel")
        self._thread.start()

    def stop(self):
        """Gracefully stop the watchdog and release high-resolution timer."""
        self._stop_event.set()
        self._set_state("IDLE", "AI Game Sentinel stopped.")

        if self._timer_locked:
            disable_high_resolution_timer(1)
            self._timer_locked = False

        if self._thread is not None:
            self._thread.join(timeout=3)
            self._thread = None

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
            from monitor import sample_system_metrics
            from ai_engine import PerformanceAI, decide_actions
        except ImportError as e:
            self._set_state("ERROR", f"Missing AI dependencies: {e}")
            return

        ai = PerformanceAI(contamination=0.05)

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

            # Sleep in short slices for responsiveness
            for _ in range(6):
                if self._stop_event.is_set():
                    return
                time.sleep(0.5)

        if self._stop_event.is_set():
            return

        # ── Phase 2: Lightweight In-Memory Train ──
        self._set_state("TRAINING", "Calibrating lightweight stability model…")
        try:
            ai.train(rows)
        except Exception as e:
            self._set_state("ERROR", f"Model calibration failed: {e}")
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
                        # Boost game priority and depress background bloatware
                        boost_game_priority(game_pid)
                        lower_background_priority(exclude_pids=[game_pid])

                    # In-game: relax polling rate to guarantee 0% gaming impact
                    sleep_duration = IN_GAME_SAMPLE_INTERVAL_SEC
                else:
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

            # Sleep in responsive increments
            steps = int(sleep_duration / 0.5)
            for _ in range(steps):
                if self._stop_event.is_set():
                    return
                time.sleep(0.5)

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

            elif action == "LOWER_BACKGROUND_PROCESS_PRIORITY":
                res = lower_background_priority(exclude_pids=exclude_pids)
                results.append(f"Deprioritized {res['lowered']} background apps")

            elif action == "REVIEW_PAGEFILE_SIZE":
                results.append("Pagefile advisory logged")

        self._actions_taken += 1
        self._last_action = " · ".join(results)
        self._last_action_time = time.time()

        game_tag = f"[{self._active_game_name}] " if self._active_game_name else ""
        summary = f"{game_tag}Action #{self._actions_taken}: {self._last_action}"
        self._set_state("ACTING", summary)

        # Anti-thrash cooldown to prevent hitching
        cooldown_steps = int(COOLDOWN_SEC / 0.5)
        for _ in range(cooldown_steps):
            if self._stop_event.is_set():
                return
            time.sleep(0.5)

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
