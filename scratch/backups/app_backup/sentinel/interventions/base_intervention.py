from typing import Any, Dict, List, Optional

class MonitorProvider:
    """Interface for polling system and game metrics."""
    def get_metrics(self) -> Dict[str, Any]:
        raise NotImplementedError

class Intervention:
    """Interface for an optimization or fix applied to the system/game."""
    @property
    def name(self) -> str:
        raise NotImplementedError
        
    def execute(self) -> Dict[str, Any]:
        """Applies the intervention and returns a status dict."""
        raise NotImplementedError
        
    def revert(self) -> Dict[str, Any]:
        """Undoes the intervention."""
        raise NotImplementedError

class SnapshotProvider:
    """Interface for taking system state snapshots before making changes."""
    def create_snapshot(self, context: Dict[str, Any]) -> str:
        """Creates a snapshot and returns its ID."""
        raise NotImplementedError

class RollbackProvider:
    """Interface for restoring previously snapshotted states."""
    def restore(self, snapshot_id: str) -> bool:
        """Restores the system state corresponding to the snapshot ID."""
        raise NotImplementedError
