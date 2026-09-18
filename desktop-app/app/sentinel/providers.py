from typing import Any, Dict, List
import ai_perf_booster.monitor as legacy_monitor
import ai_perf_booster.ai_engine as legacy_ai
import ai_perf_booster.actions as legacy_actions
import network_stabilizer.diagnostics_engine as legacy_diag
import network_stabilizer.snapshot_manager as legacy_snap
import network_stabilizer.tweaks_engine as legacy_tweaks
import overlay.metrics_collector as legacy_overlay
import services.benchmark_logger as legacy_benchmark

from .interventions.base_intervention import MonitorProvider, SnapshotProvider

class LegacyPerformanceProvider(MonitorProvider):
    def get_metrics(self) -> Dict[str, Any]:
        # Wraps the legacy sample_system_metrics which returns (dict, prev_disk, prev_net)
        # For a true implementation, we'd manage the state
        metrics, _, _ = legacy_monitor.sample_system_metrics(None, None)
        return metrics

class LegacyAIProvider:
    def __init__(self):
        self._engine = legacy_ai.PerformanceAI()
        
    def train(self, samples: List[Dict[str, Any]]):
        self._engine.train(samples)
        
    def detect_anomaly(self, row: Dict[str, Any]) -> Dict[str, Any]:
        return self._engine.detect_anomaly(row)

class LegacyActionProvider:
    @staticmethod
    def clear_standby_memory() -> Dict[str, Any]:
        try:
            from optimize.optimizer_service import clear_standby_memory as opt_clear
            return opt_clear()
        except Exception:
            success = legacy_actions.clear_standby_memory()
            return {"success": success, "freed_mb": 0.0}

    @staticmethod
    def trim_all_working_sets(exclude_pids=None) -> Dict[str, Any]:
        try:
            from optimize.optimizer_service import trim_all_working_sets as opt_trim
            res = dict(opt_trim(exclude_pids=exclude_pids))
            if "success" not in res:
                res["success"] = res.get("trimmed", 0) > 0
            res["trimmed_count"] = res.get("trimmed", 0)
            return res
        except Exception:
            fn = getattr(legacy_actions, "trim_all_working_sets", getattr(legacy_actions, "trim_working_sets_safe", None))
            pids = fn(exclude_pids) if fn else []
            return {"success": bool(pids), "trimmed": len(pids) if isinstance(pids, list) else 0, "freed_mb": 0.0}
        
class NetworkDiagnosticsProvider:
    @staticmethod
    def check_bufferbloat() -> Dict[str, Any]:
        return legacy_diag.check_bufferbloat_sync()

class NetworkSnapshotProvider(SnapshotProvider):
    def __init__(self):
        self._mgr = legacy_snap.SnapshotManager()
        
    def create_snapshot(self, context: Dict[str, Any]) -> str:
        # Simplistic wrapping for Phase 2
        return self._mgr.log_change(context.get("name"), context.get("old"), context.get("new"), context.get("reason"))
        
    def load_applied_changes(self) -> List[Dict[str, Any]]:
        return self._mgr.load_applied_changes()
        
class NetworkTweaksProvider:
    @staticmethod
    def apply_tcp_optimization() -> bool:
        # Example wrapping of legacy tweaks
        return legacy_tweaks.apply_game_optimizations()

class OverlayMetricsProvider(MonitorProvider):
    def __init__(self):
        self._collector = legacy_overlay.MetricsCollector()
        
    def get_metrics(self) -> Dict[str, Any]:
        return self._collector.snapshot()

class BenchmarkProvider:
    def __init__(self):
        self._logger = legacy_benchmark.BenchmarkLogger()
        
    def log_fps(self, fps: float):
        self._logger.feed_fps(fps)
