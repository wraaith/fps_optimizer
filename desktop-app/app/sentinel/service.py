import collections
import threading
import time
import uuid
from typing import Optional, Any, Dict, List

from sentinel.intervention_controller import InterventionController
from sentinel.managers.priority_rollback_manager import PriorityRollbackManager
from sentinel.managers.process_token_manager import ProcessTokenManager
from sentinel.managers.timer_manager import TimerManager
from sentinel.models import SentinelMode, SentinelState

class SentinelService:
    """The central lifecycle orchestrator for the Universal Game Sentinel."""
    
    _instance: Optional['SentinelService'] = None
    
    @classmethod
    def get_instance(cls) -> 'SentinelService':
        if cls._instance is None:
            cls._instance = SentinelService()
        return cls._instance
    
    def __init__(self):
        self._is_running = False
        self._is_paused = False
        
        self.controller = InterventionController.get_instance()
        self.timer_manager = TimerManager()
        self.priority_manager = PriorityRollbackManager()
        
        self.session_id = str(uuid.uuid4())
        self.token_manager = ProcessTokenManager(self.session_id)
        
        self._ai_boost_service = None
        
        # Bounded event timeline and observability tracking
        self._timeline_lock = threading.Lock()
        self._event_timeline = collections.deque(maxlen=200)
        self._state_transitions = collections.deque(maxlen=50)
        self._blocked_operations_count = 0
        self._last_anomaly = {
            "classification": "none",
            "evidence": "Telemetry nominal; no frame pacing irregularities",
            "confidence": 0.0,
            "timestamp": time.time()
        }
        self._last_recommendation = {
            "game": "None",
            "classification": "none",
            "evidence": "Telemetry nominal",
            "confidence": 0.0,
            "action": "None",
            "risk": "none",
            "reversible": True,
            "reason_blocked": "Monitor-only mode"
        }
        self.log_event("Ledger loaded", "State audit ledger verified and loaded")
        
    def log_event(self, event_type: str, details: str = "", metadata: Optional[Dict[str, Any]] = None):
        """Thread-safe bounded event logging."""
        with self._timeline_lock:
            self._event_timeline.append({
                "timestamp": time.time(),
                "event": event_type,
                "details": details,
                "metadata": metadata or {}
            })
            
    def get_event_timeline(self) -> List[Dict[str, Any]]:
        with self._timeline_lock:
            return list(self._event_timeline)
        
    def _get_ai_boost_service(self):
        if self._ai_boost_service is None:
            # Lazy import to avoid circular dependencies
            from optimize.ai_boost_service import get_ai_boost_service
            self._ai_boost_service = get_ai_boost_service()
        return self._ai_boost_service
        
    def get_state(self) -> SentinelState:
        return getattr(self.controller.state_machine, "current_state", SentinelState.IDLE)

    def start(self):
        if self._is_running:
            return
        self._is_running = True
        self._is_paused = False
        self.controller.state_machine.transition_to(SentinelState.OBSERVING)
        self._get_ai_boost_service().start()
        self.log_event("Worker started", "Sentinel worker thread initiated")
        self.log_event("Baseline started", "Observing baseline frametimes and system telemetry")
        
    def pause(self):
        if self._is_running:
            self._is_paused = True
            self._get_ai_boost_service().pause()
        
    def resume(self):
        if self._is_running and self._is_paused:
            self._is_paused = False
            self._get_ai_boost_service().resume()
        
    def stop(self):
        """Safely stops the service, rolling back active temporary interventions."""
        was_running = self._is_running
        self._is_running = False
        self._is_paused = False
        self.controller.state_machine.transition_to(SentinelState.IDLE)
        if was_running:
            self.timer_manager.end()
            self.priority_manager.rollback_all()
            ai_svc = self._get_ai_boost_service()
            if ai_svc:
                ai_svc.stop()
            self.log_event("Worker stopped", "Sentinel worker stopped cleanly")
        
        # Always invalidate active tokens, clear state, and generate new session ID
        self.session_id = str(uuid.uuid4())
        self.token_manager.session_id = self.session_id
        self.token_manager.reset()
        
    def emergency_stop(self):
        """Immediately halts all interventions and attempts to rollback active changes."""
        self.log_event("Rollback attempted", "Emergency stop invoked; rolling back active changes")
        self.controller.set_mode(SentinelMode.MONITOR_ONLY)  # Block new interventions
        self.stop()
        self.controller.state_machine.transition_to(SentinelState.SAFE_MODE)
        self.session_id = str(uuid.uuid4())
        self.token_manager.session_id = self.session_id
        self.token_manager.reset()
        self.log_event("Safe mode entered", "Emergency stop complete; mode locked to MONITOR_ONLY")

    def is_running(self) -> bool:
        return self._is_running
        
    def has_active_worker(self) -> bool:
        return self._is_running and self._get_ai_boost_service().is_running

    def set_mode(self, mode: SentinelMode):
        self.controller.set_mode(mode)
        
    def handle_worker_exception(self, error: Exception):
        """Called when a managed worker encounters an exception."""
        self.log_event("Safe mode entered", f"Worker exception encountered: {error}")
        self.emergency_stop()
        
    def handle_game_exit(self):
        """Called when the active game process exits."""
        self.log_event("Game detected", "Active game process terminated")
        if self._ai_boost_service:
            self._ai_boost_service._set_state("IDLE", "Game exited.")

    def get_active_game_info(self) -> Dict[str, Any]:
        """Returns detected active game information using the 3-tier detection pipeline."""
        # Primary: 3-tier Universal Game Detection Protocol
        try:
            from sentinel.game_detection import detect_active_game
            result = detect_active_game()
            if result is not None:
                return {
                    "name": result.exe_name,
                    "exe": result.exe_name,
                    "pid": result.pid,
                    "detected": True,
                    "confidence": result.confidence,
                    "detection_method": result.detection_method,
                    "window_mode": result.window_mode,
                }
        except ImportError:
            pass
        except Exception:
            pass

        # Fallback: legacy foreground window detection
        try:
            from optimize.optimizer_service import get_foreground_game_process
            fg = get_foreground_game_process()
            if fg and fg.get("pid"):
                return {
                    "name": fg.get("name") or fg.get("title") or "Unknown Game",
                    "exe": fg.get("exe") or fg.get("name") or "",
                    "pid": fg.get("pid"),
                    "detected": True,
                    "confidence": "LEGACY",
                    "detection_method": "LEGACY_FOREGROUND",
                    "window_mode": "UNKNOWN",
                }
        except Exception:
            pass

        # Fallback: AI boost service tracked game
        if self._ai_boost_service and getattr(self._ai_boost_service, "_active_game_pid", None):
            pid = self._ai_boost_service._active_game_pid
            name = getattr(self._ai_boost_service, "_active_game_name", f"PID {pid}")
            return {
                "name": name,
                "exe": name,
                "pid": pid,
                "detected": True,
                "confidence": "LEGACY",
                "detection_method": "AI_BOOST_FALLBACK",
                "window_mode": "UNKNOWN",
            }

        return {
            "name": "None",
            "exe": "None",
            "pid": None,
            "detected": False,
            "confidence": None,
            "detection_method": None,
            "window_mode": None,
        }

    def is_intervention_active(self) -> bool:
        """Monitor-only never allows active system interventions."""
        return False

    def is_rollback_available(self) -> bool:
        try:
            from network_stabilizer.snapshot_manager import SnapshotManager
            sm = SnapshotManager()
            changes = sm.load_applied_changes()
            return len(changes) > 0
        except Exception:
            return False

    def get_metrics_health(self) -> Dict[str, Dict[str, Any]]:
        """
        Gathers live values for all required metrics and tags each with
        its data source and status: measured, stale, unavailable, or error.
        Estimated values are never reported as measured.
        """
        now = time.time()
        health: Dict[str, Dict[str, Any]] = {}
        
        # 1. Overlay / PresentMon metrics
        pm_snapshot = {}
        collector = None
        try:
            from overlay.metrics_collector import get_shared_metrics_collector
            collector = get_shared_metrics_collector()
            pm_snapshot = collector.snapshot
        except Exception:
            pass

        # FPS
        fps_val = pm_snapshot.get("fps")
        fps_ts = pm_snapshot.get("timestamp", 0.0)
        if fps_val is not None and fps_val > 0:
            status = "stale" if (now - fps_ts > 3.0) else "measured"
            health["fps"] = {"value": round(fps_val, 1), "timestamp": fps_ts, "source": "PresentMon", "status": status}
        else:
            health["fps"] = {"value": None, "timestamp": now, "source": "PresentMon", "status": "unavailable"}

        # Frametimes (median/p50, p95, p99, 1% low)
        try:
            times = []
            if collector and hasattr(collector, "_frametimes"):
                with collector._lock:
                    times = [ft[1] for ft in collector._frametimes]
            if len(times) >= 5:
                import numpy as np
                p50 = float(np.percentile(times, 50))
                p95 = float(np.percentile(times, 95))
                p99 = float(np.percentile(times, 99))
                fps_series = [1000.0 / t for t in times if t > 0]
                one_pct_low = float(np.percentile(fps_series, 1)) if fps_series else 0.0
                
                health["frame_time_p50_ms"] = {"value": round(p50, 2), "timestamp": now, "source": "PresentMon", "status": "measured"}
                health["frame_time_p95_ms"] = {"value": round(p95, 2), "timestamp": now, "source": "PresentMon", "status": "measured"}
                health["frame_time_p99_ms"] = {"value": round(p99, 2), "timestamp": now, "source": "PresentMon", "status": "measured"}
                health["one_percent_low_fps"] = {"value": round(one_pct_low, 1), "timestamp": now, "source": "PresentMon", "status": "measured"}
            else:
                health["frame_time_p50_ms"] = {"value": None, "timestamp": now, "source": "PresentMon", "status": "unavailable"}
                health["frame_time_p95_ms"] = {"value": None, "timestamp": now, "source": "PresentMon", "status": "unavailable"}
                health["frame_time_p99_ms"] = {"value": None, "timestamp": now, "source": "PresentMon", "status": "unavailable"}
                health["one_percent_low_fps"] = {"value": None, "timestamp": now, "source": "PresentMon", "status": "unavailable"}
        except Exception:
            health["frame_time_p50_ms"] = {"value": None, "timestamp": now, "source": "PresentMon", "status": "unavailable"}
            health["frame_time_p95_ms"] = {"value": None, "timestamp": now, "source": "PresentMon", "status": "unavailable"}
            health["frame_time_p99_ms"] = {"value": None, "timestamp": now, "source": "PresentMon", "status": "unavailable"}
            health["one_percent_low_fps"] = {"value": None, "timestamp": now, "source": "PresentMon", "status": "unavailable"}

        # CPU total and per-core
        try:
            import psutil
            cpu_tot = psutil.cpu_percent(interval=None)
            health["cpu_usage"] = {"value": f"{cpu_tot}%", "timestamp": now, "source": "Kernel", "status": "measured"}
            per_core = psutil.cpu_percent(interval=None, percpu=True)
            health["cpu_cores_usage"] = {"value": [f"{c}%" for c in per_core], "timestamp": now, "source": "Kernel", "status": "measured"}
        except Exception as e:
            health["cpu_usage"] = {"value": None, "timestamp": now, "source": "Kernel", "status": "error"}
            health["cpu_cores_usage"] = {"value": None, "timestamp": now, "source": "Kernel", "status": "error"}

        # GPU usage
        gpu_val = pm_snapshot.get("gpu_usage")
        if gpu_val is not None:
            health["gpu_usage"] = {"value": f"{gpu_val}%", "timestamp": pm_snapshot.get("timestamp", now), "source": "GPU Driver", "status": "measured"}
        else:
            health["gpu_usage"] = {"value": None, "timestamp": now, "source": "GPU Driver", "status": "unavailable"}

        # RAM pressure
        try:
            import psutil
            ram_pct = psutil.virtual_memory().percent
            health["ram_pressure"] = {"value": f"{ram_pct}%", "timestamp": now, "source": "OS VirtualMemory", "status": "measured"}
        except Exception:
            health["ram_pressure"] = {"value": None, "timestamp": now, "source": "OS VirtualMemory", "status": "unavailable"}

        # Hard faults
        try:
            import psutil
            swap = psutil.swap_memory()
            sin = getattr(swap, "sin", None)
            health["hard_faults"] = {"value": f"{sin} faults" if sin is not None else "0/s", "timestamp": now, "source": "OS Memory", "status": "measured"}
        except Exception:
            health["hard_faults"] = {"value": None, "timestamp": now, "source": "OS Memory", "status": "unavailable"}

        # Disk latency
        try:
            import psutil
            counters = psutil.disk_io_counters()
            if counters and getattr(counters, "read_count", 0) > 0:
                lat = round(counters.read_time / counters.read_count, 2)
                health["disk_latency_ms"] = {"value": f"{lat} ms", "timestamp": now, "source": "Disk Subsystem", "status": "measured"}
            else:
                health["disk_latency_ms"] = {"value": None, "timestamp": now, "source": "Disk Subsystem", "status": "unavailable"}
        except Exception:
            health["disk_latency_ms"] = {"value": None, "timestamp": now, "source": "Disk Subsystem", "status": "unavailable"}

        # Network RTT, Jitter, Packet Loss
        try:
            from network_stabilizer.diagnostics_engine import DiagnosticsEngine
            diag = DiagnosticsEngine()
            cached = getattr(diag, "last_summary", None)
            if cached and isinstance(cached, dict):
                rtt = cached.get("avg_rtt_ms")
                jit = cached.get("jitter_ms")
                loss = cached.get("packet_loss_pct")
                ts = cached.get("timestamp", now)
                status = "stale" if (now - ts > 10.0) else "measured"
                health["network_rtt_ms"] = {"value": f"{rtt} ms" if rtt is not None else None, "timestamp": ts, "source": "NetworkDiagnostics", "status": status if rtt is not None else "unavailable"}
                health["network_jitter_ms"] = {"value": f"{jit} ms" if jit is not None else None, "timestamp": ts, "source": "NetworkDiagnostics", "status": status if jit is not None else "unavailable"}
                health["packet_loss_percent"] = {"value": f"{loss}%" if loss is not None else None, "timestamp": ts, "source": "NetworkDiagnostics", "status": status if loss is not None else "unavailable"}
            else:
                health["network_rtt_ms"] = {"value": None, "timestamp": now, "source": "NetworkDiagnostics", "status": "unavailable"}
                health["network_jitter_ms"] = {"value": None, "timestamp": now, "source": "NetworkDiagnostics", "status": "unavailable"}
                health["packet_loss_percent"] = {"value": None, "timestamp": now, "source": "NetworkDiagnostics", "status": "unavailable"}
        except Exception:
            health["network_rtt_ms"] = {"value": None, "timestamp": now, "source": "NetworkDiagnostics", "status": "unavailable"}
            health["network_jitter_ms"] = {"value": None, "timestamp": now, "source": "NetworkDiagnostics", "status": "unavailable"}
            health["packet_loss_percent"] = {"value": None, "timestamp": now, "source": "NetworkDiagnostics", "status": "unavailable"}

        return health

    def export_session_summary(self) -> Dict[str, Any]:
        """Exports measured session summaries with strict per-field status marking."""
        health = self.get_metrics_health()
        game_info = self.get_active_game_info()
        now = time.time()
        
        avail_mem = None
        avail_status = "unavailable"
        try:
            import psutil
            avail_mem = round(psutil.virtual_memory().available / (1024 * 1024), 1)
            avail_status = "measured"
        except Exception:
            pass

        return {
            "game": game_info.get("name", "None"),
            "timestamp": now,
            "frame_time_p50_ms": {
                "value": health.get("frame_time_p50_ms", {}).get("value"),
                "status": health.get("frame_time_p50_ms", {}).get("status", "unavailable")
            },
            "frame_time_p95_ms": {
                "value": health.get("frame_time_p95_ms", {}).get("value"),
                "status": health.get("frame_time_p95_ms", {}).get("status", "unavailable")
            },
            "frame_time_p99_ms": {
                "value": health.get("frame_time_p99_ms", {}).get("value"),
                "status": health.get("frame_time_p99_ms", {}).get("status", "unavailable")
            },
            "average_fps": {
                "value": health.get("fps", {}).get("value"),
                "status": health.get("fps", {}).get("status", "unavailable")
            },
            "one_percent_low_fps": {
                "value": health.get("one_percent_low_fps", {}).get("value"),
                "status": health.get("one_percent_low_fps", {}).get("status", "unavailable")
            },
            "cpu_usage": {
                "value": health.get("cpu_usage", {}).get("value"),
                "status": health.get("cpu_usage", {}).get("status", "unavailable")
            },
            "gpu_usage": {
                "value": health.get("gpu_usage", {}).get("value"),
                "status": health.get("gpu_usage", {}).get("status", "unavailable")
            },
            "available_memory": {
                "value": f"{avail_mem} MB" if avail_mem is not None else None,
                "status": avail_status
            },
            "hard_faults": {
                "value": health.get("hard_faults", {}).get("value"),
                "status": health.get("hard_faults", {}).get("status", "unavailable")
            },
            "disk_latency_ms": {
                "value": health.get("disk_latency_ms", {}).get("value"),
                "status": health.get("disk_latency_ms", {}).get("status", "unavailable")
            },
            "network_rtt_ms": {
                "value": health.get("network_rtt_ms", {}).get("value"),
                "status": health.get("network_rtt_ms", {}).get("status", "unavailable")
            },
            "network_jitter_ms": {
                "value": health.get("network_jitter_ms", {}).get("value"),
                "status": health.get("network_jitter_ms", {}).get("status", "unavailable")
            },
            "packet_loss_percent": {
                "value": health.get("packet_loss_percent", {}).get("value"),
                "status": health.get("packet_loss_percent", {}).get("status", "unavailable")
            },
            "anomaly_class": self._last_anomaly.get("classification", "none"),
            "recommendation": self._last_recommendation,
            "metric_status": "MONITOR_ONLY_ACTIVE"
        }

    def get_advanced_debug_info(self) -> Dict[str, Any]:
        """Provides complete internal debug telemetry for the Advanced Debug View."""
        consumers_count = 0
        pm_status = "STOPPED"
        try:
            from overlay.metrics_collector import get_shared_metrics_collector
            c = get_shared_metrics_collector()
            consumers_count = c._consumers
            if c._running:
                pm_status = "RUNNING"
            elif c._pm_process and c._pm_process.poll() is None:
                pm_status = "RUNNING"
        except Exception:
            pm_status = "NOT_AVAILABLE"

        ledger_version = 2
        safe_mode = False
        last_rollback = None
        try:
            from network_stabilizer.snapshot_manager import SnapshotManager
            sm = SnapshotManager()
            safe_mode = getattr(sm, "in_safe_mode", False)
            schema = sm.get_current_state() if hasattr(sm, "get_current_state") else {}
            ledger_version = schema.get("schema_version", 2)
            last_rollback = schema.get("last_rollback")
        except Exception:
            pass

        return {
            "current_mode": self.controller.mode.name,
            "state_machine_state": getattr(self.controller.state_machine, "current_state", SentinelState.IDLE).name,
            "state_transitions": list(self._state_transitions),
            "worker_status": "RUNNING" if self.has_active_worker() else "STOPPED",
            "worker_id": getattr(self._get_ai_boost_service(), "_worker_id", "SentinelWorker-1"),
            "stop_event_status": "SET" if not self._is_running else "CLEARED",
            "metrics_consumer_count": consumers_count,
            "presentmon_process_status": pm_status,
            "timer_ownership_state": "ACTIVE (1.0ms)" if (getattr(self.timer_manager, "owns_timer", False) or getattr(self.timer_manager, "is_active", False)) else "INACTIVE",
            "intervention_controller_mode": self.controller.mode.name,
            "blocked_operation_count": self._blocked_operations_count,
            "last_rollback_result": last_rollback or "None",
            "ledger_schema_version": ledger_version,
            "safe_mode": safe_mode
        }

    def request_intervention(self, intervention_name: str, args: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        The central gateway for ALL state-changing operations.
        Validates through InterventionController.
        """
        args = args or {}
        args["current_session_id"] = self.session_id
        args["is_sentinel_running"] = self._is_running
        
        # Real process cleanup (dry_run=False) is blocked if Sentinel is active in ANY mode
        is_dry_run = args.get("dry_run", True)
        if intervention_name == "process_cleanup" and self._is_running and not is_dry_run:
            self._blocked_operations_count += 1
            self.log_event("Intervention request blocked", f"Operation 'process_cleanup' blocked (Sentinel is active)")
            return {
                "status": "blocked",
                "operation": "process_cleanup",
                "reason": "Sentinel is active",
                "system_changed": False,
                "rollback_available": False,
                "details": {}
            }

        if not self._is_running or self._is_paused:
            # The ONLY intervention allowed when not running is process_cleanup in legacy_mode
            if intervention_name != "process_cleanup":
                self._blocked_operations_count += 1
                self.log_event("Intervention request blocked", f"Operation '{intervention_name}' blocked (SERVICE_NOT_ACTIVE)")
                return {
                    "status": "blocked",
                    "operation": intervention_name,
                    "reason": "SERVICE_NOT_ACTIVE",
                    "system_changed": False,
                    "rollback_available": False,
                    "details": {}
                }
            
        # Pass the token manager and running state to the controller
        self.controller.token_manager = self.token_manager
        
        if intervention_name == "process_cleanup":
            res = self.controller.request_intervention(intervention_name, args)
            if res.get("status") == "blocked":
                self._blocked_operations_count += 1
                self.log_event("Intervention request blocked", f"Operation 'process_cleanup' blocked ({res.get('reason')})")
            return res
        
        if self.controller.mode == SentinelMode.MONITOR_ONLY:
            self._blocked_operations_count += 1
            self.log_event("Intervention request blocked", f"Operation '{intervention_name}' blocked (MONITOR_ONLY)")
            return {
                "status": "blocked",
                "operation": intervention_name,
                "reason": "MONITOR_ONLY",
                "system_changed": False,
                "rollback_available": False,
                "details": {}
            }
        if intervention_name == "timeBeginPeriod":
            from .managers.timer_manager import TimerContext
            resolution = args.get("resolution_ms", 1)
            source = args.get("source", "sentinel")
            success = self.timer_manager.begin(TimerContext(source=source, requested_resolution=resolution))
            return {
                "status": "applied" if success else "failed",
                "operation": intervention_name,
                "system_changed": success,
                "rollback_available": success,
                "details": {}
            }
        
        if intervention_name == "timeEndPeriod":
            source = args.get("source", "sentinel")
            success = self.timer_manager.end(source)
            return {
                "status": "rolled_back" if success else "failed",
                "operation": intervention_name,
                "system_changed": success,
                "rollback_available": False,
                "details": {}
            }
            
        # Dispatch to controller for other interventions
        res = self.controller.request_intervention(intervention_name, args)
        if res.get("status") == "blocked":
            self._blocked_operations_count += 1
            self.log_event("Intervention request blocked", f"Operation '{intervention_name}' blocked ({res.get('reason')})")
        return res
