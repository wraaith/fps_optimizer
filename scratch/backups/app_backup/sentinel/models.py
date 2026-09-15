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
