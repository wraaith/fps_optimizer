"""
Network Stabilizer Feature Package
Lightweight embedded network diagnosis and safe, audited optimization suite.
"""

from .constants import FEATURE_NAME, FEATURE_VERSION, SCHEMA_VERSION
from .diagnostics_engine import DiagnosticsEngine
from .game_profiles import GameProfileManager, GameProfiles
from .router_advisor import RouterAdvisor
from .snapshot_manager import SnapshotManager
from .tweaks_engine import TweaksEngine


class NetworkStabilizerFeature:
    """
    Compact integration facade connecting diagnostics, safe tweaks,
    router guidance, game profiles, and targeted rollback.
    """
    def __init__(self, app_context=None):
        self.app_context = app_context
        self.diagnostics = DiagnosticsEngine()
        self.snapshots = SnapshotManager()
        self.profiles = GameProfileManager(snapshot_mgr=self.snapshots)
        self.router = RouterAdvisor()
        self.tweaks = TweaksEngine(
            snapshot_manager=self.snapshots,
            app_context=app_context,
        )

    def run_diagnostics(self, target=None, probe_count=20, cancel_event=None):
        """Run bounded on-demand probe across targets."""
        return self.diagnostics.run_full_diagnostic(
            custom_game_host=target,
            probe_count=probe_count,
            cancel_event=cancel_event
        )

    def cancel_active_diagnostics(self):
        """Immediately request cancellation of in-flight diagnostic work."""
        self.diagnostics.request_cancellation()

    def apply_safe_optimization(self):
        """Ensure baseline snapshot exists, then apply safe optimizations."""
        snapshot = self.snapshots.ensure_baseline_snapshot()
        if not snapshot.get("success", False):
            return {
                "success": False,
                "message": "Optimization cancelled because baseline snapshot could not be verified."
            }

        return self.tweaks.apply_safe_profile()

    def restore_previous_state(self, progress_callback=None):
        """Restore feature-managed settings in reverse chronological order with verification."""
        self.cancel_active_diagnostics()
        return self.snapshots.restore_previous_state(progress_callback=progress_callback)


__all__ = [
    "FEATURE_NAME",
    "FEATURE_VERSION",
    "SCHEMA_VERSION",
    "NetworkStabilizerFeature",
    "DiagnosticsEngine",
    "GameProfileManager",
    "GameProfiles",
    "RouterAdvisor",
    "SnapshotManager",
    "TweaksEngine",
]
