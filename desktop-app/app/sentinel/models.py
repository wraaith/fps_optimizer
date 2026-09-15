from enum import Enum, auto

class SentinelMode(Enum):
    MONITOR_ONLY = auto()
    CONSERVATIVE = auto()
    BALANCED = auto()
    ADVANCED = auto()

class StutterCategory(Enum):
    RENDER_STUTTER = "render_stutter"
    NETWORK_JITTER = "network_jitter"
    PACKET_LOSS = "packet_loss"
    BUFFERBLOAT = "bufferbloat"
    CPU_CONTENTION = "cpu_contention"
    MEMORY_PRESSURE = "memory_pressure"
    STORAGE_CONTENTION = "storage_contention"
    GAME_OR_DRIVER_UNKNOWN = "game_or_driver_unknown"

class SentinelState(Enum):
    IDLE = auto()
    OBSERVING = auto()
    BASELINE_READY = auto()
    ANOMALY_DETECTED = auto()
    INTERVENTION_PENDING = auto()
    INTERVENTION_ACTIVE = auto()
    VERIFYING = auto()
    COOLDOWN = auto()
    SAFE_MODE = auto()

from dataclasses import dataclass, field
from typing import Optional, Dict, Any

@dataclass
class InterventionResult:
    status: str
    operation: str
    reason: Optional[str] = None
    system_changed: bool = False
    rollback_available: bool = False
    details: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self):
        return {
            "status": self.status,
            "operation": self.operation,
            "reason": self.reason,
            "system_changed": self.system_changed,
            "rollback_available": self.rollback_available,
            "details": self.details
        }
