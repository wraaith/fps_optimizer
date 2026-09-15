"""
AI System Performance Booster — Ultra-Lightweight ML & Stability Engine
Pure-NumPy statistical anomaly detector optimized for low-end hardware.
Uses Z-score baseline deviation + Exponentially Weighted Moving Average (EWMA)
velocity predictor to detect system pressure anomalies in microseconds
with zero disk I/O and zero heavy dependencies.

Designed to consume <2MB RAM with instant (<1ms) training.
"""

import os
from typing import Dict, Any, List, Optional
import numpy as np

FEATURES = ["cpu_percent", "mem_percent", "swap_percent", "disk_read_mb", "disk_write_mb"]


class PerformanceAI:
    """Feather-light performance anomaly & trend detector.
    Zero disk writes, zero sklearn, minimal RAM footprint (<2MB).
    Trains in <1ms using pure-NumPy statistical baselines.
    """

    def __init__(self, contamination=0.05):
        self.contamination = contamination
        self.is_fitted = False
        self._baseline_means = {}
        self._baseline_stds = {}
        # Z-score threshold derived from contamination (default 0.05 → ~2.0σ)
        self._z_threshold = max(1.8, 3.0 - (contamination * 20.0))
        self._ewma_mem = None
        self._ewma_alpha = 0.3
        self._last_mem = None
        self._mem_velocity_mb_s = 0.0

    def train(self, data):
        """Train the model in-memory on baseline telemetry without writing to disk.
        Instant (<1ms) — just computes means and standard deviations."""
        if hasattr(data, "to_dict"):
            rows = data.to_dict(orient="records")
        else:
            rows = list(data)

        if not rows:
            return

        # Extract feature matrix
        matrix = []
        for r in rows:
            matrix.append([float(r.get(f, 0) or 0) for f in FEATURES])
        X = np.array(matrix, dtype=np.float32)

        # Baseline statistical moments — the only thing we need
        means = np.mean(X, axis=0)
        stds = np.std(X, axis=0) + 1e-6
        for idx, f in enumerate(FEATURES):
            self._baseline_means[f] = float(means[idx])
            self._baseline_stds[f] = float(stds[idx])

        self.is_fitted = True

    def detect_anomaly(self, row: Dict[str, Any]) -> Dict[str, Any]:
        """Detect anomalies in microseconds without disk I/O."""
        if not self.is_fitted:
            return {"is_anomaly": False, "anomaly_score": 0.0, "mem_velocity": 0.0}

        current_mem = float(row.get("mem_percent", 0) or 0)
        
        # Track EWMA and rate of change (velocity)
        if self._ewma_mem is None:
            self._ewma_mem = current_mem
        else:
            self._ewma_mem = (self._ewma_alpha * current_mem) + ((1.0 - self._ewma_alpha) * self._ewma_mem)

        mem_velocity = 0.0
        if self._last_mem is not None:
            mem_velocity = current_mem - self._last_mem
        self._last_mem = current_mem

        # Fast tranquil screen: if system metrics are comfortably normal and not spiking,
        # return immediate normal in < 0.01ms to preserve maximum CPU cycles for gaming
        # Thresholds lowered for low-end systems (4-8GB RAM, budget CPUs)
        current_cpu = float(row.get("cpu_percent", 0) or 0)
        current_swap = float(row.get("swap_percent", 0) or 0)
        if current_mem < 60.0 and current_cpu < 70.0 and current_swap < 30.0 and abs(mem_velocity) < 1.0:
            return {
                "is_anomaly": False,
                "anomaly_score": 0.0,
                "mem_velocity": mem_velocity,
                "ewma_mem": self._ewma_mem
            }

        # Pure-NumPy Z-score detection (< 0.01ms)
        z_scores = []
        for f in FEATURES:
            val = float(row.get(f, 0) or 0)
            m = self._baseline_means.get(f, val)
            s = self._baseline_stds.get(f, 1.0)
            z_scores.append(abs(val - m) / s)

        max_z = max(z_scores) if z_scores else 0.0
        is_anomaly = max_z > self._z_threshold

        return {
            "is_anomaly": is_anomaly,
            "anomaly_score": float(-max_z),
            "mem_velocity": mem_velocity,
            "ewma_mem": self._ewma_mem
        }

    def forecast_mem_trend(self, steps_ahead=5) -> float:
        """Forecast memory trend using EWMA trajectory."""
        if self._ewma_mem is None:
            return 0.0
        velocity = (self._last_mem - self._ewma_mem) if self._last_mem else 0.0
        return float(self._ewma_mem + (velocity * steps_ahead))


def decide_actions(row: dict, anomaly_result: dict, thresholds=None):
    """
    Rule-layer that turns AI signals into SAFE, non-destructive actions.
    Never recommends killing a process; only cache/priority/background tweaks.

    Thresholds lowered for low-end systems where resources are scarce.
    """
    thresholds = thresholds or {
        "mem_high": 65,       # Was 70 — on 4-8GB PCs, 65% is already tight
        "mem_critical": 75,   # Was 82 — start aggressive cleanup sooner
        "cpu_high": 70,       # Was 75 — budget CPUs throttle earlier
        "swap_high": 30       # Was 40 — any swap on low-end = major stutter
    }
    actions = []

    mem_percent = float(row.get("mem_percent", 0) or 0)
    cpu_percent = float(row.get("cpu_percent", 0) or 0)
    swap_percent = float(row.get("swap_percent", 0) or 0)
    is_anomaly = anomaly_result.get("is_anomaly", False)
    mem_velocity = anomaly_result.get("mem_velocity", 0.0)

    # Trigger standby clear if memory is high, rapidly rising (+2% in one sample), or anomaly detected
    if mem_percent > thresholds["mem_high"] or (mem_percent > 60 and mem_velocity > 1.5) or is_anomaly:
        actions.append("CLEAR_STANDBY_MEMORY")

    if swap_percent > thresholds["swap_high"]:
        actions.append("REVIEW_PAGEFILE_SIZE")

    if cpu_percent > thresholds["cpu_high"]:
        actions.append("LOWER_BACKGROUND_PROCESS_PRIORITY")

    if not actions:
        actions.append("NO_ACTION_NEEDED")

    return actions

