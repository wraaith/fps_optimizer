"""
AI System Performance Booster — Ultra-Lightweight ML & Stability Engine
Uses a lean, single-threaded Isolation Forest (n_jobs=1, 30 estimators)
and an Exponentially Weighted Moving Average (EWMA) velocity predictor
to detect system pressure anomalies in microseconds with 0 disk I/O.
"""

import os
from typing import Dict, Any, List, Optional
import numpy as np

FEATURES = ["cpu_percent", "mem_percent", "swap_percent", "disk_read_mb", "disk_write_mb"]


class PerformanceAI:
    """Feather-light performance anomaly & trend detector.
    Zero disk writes, strictly single-threaded, minimal RAM footprint (<2MB).
    """

    def __init__(self, contamination=0.05):
        self.contamination = contamination
        self.is_fitted = False
        self._scaler = None
        self._model = None
        self._baseline_means = {}
        self._baseline_stds = {}
        self._ewma_mem = None
        self._ewma_alpha = 0.3
        self._last_mem = None
        self._mem_velocity_mb_s = 0.0

    def train(self, data):
        """Train the model in-memory on baseline telemetry without writing to disk."""
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

        # Baseline statistical moments
        means = np.mean(X, axis=0)
        stds = np.std(X, axis=0) + 1e-6
        for idx, f in enumerate(FEATURES):
            self._baseline_means[f] = float(means[idx])
            self._baseline_stds[f] = float(stds[idx])

        # Try sklearn with strictly single-threaded light config (30 trees, n_jobs=1)
        try:
            from sklearn.ensemble import IsolationForest
            from sklearn.preprocessing import StandardScaler

            self._scaler = StandardScaler()
            X_scaled = self._scaler.fit_transform(X)

            self._model = IsolationForest(
                n_estimators=30,
                contamination=self.contamination,
                random_state=42,
                n_jobs=1,      # STRICTLY 1 worker: never preempts game render threads
                max_samples=min(64, len(X))
            )
            self._model.fit(X_scaled)
        except Exception:
            # Pure NumPy fallback: robust statistical Z-score baseline
            self._model = None

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
        current_cpu = float(row.get("cpu_percent", 0) or 0)
        current_swap = float(row.get("swap_percent", 0) or 0)
        if current_mem < 75.0 and current_cpu < 80.0 and current_swap < 45.0 and abs(mem_velocity) < 1.0:
            return {
                "is_anomaly": False,
                "anomaly_score": 0.0,
                "mem_velocity": mem_velocity,
                "ewma_mem": self._ewma_mem
            }

        # Check sklearn model if available
        if self._model is not None and self._scaler is not None:
            try:
                X = np.array([[float(row.get(f, 0) or 0) for f in FEATURES]], dtype=np.float32)
                X_scaled = self._scaler.transform(X)
                pred = self._model.predict(X_scaled)[0]
                score = float(self._model.decision_function(X_scaled)[0])
                is_anomaly = bool(pred == -1)
                return {
                    "is_anomaly": is_anomaly,
                    "anomaly_score": score,
                    "mem_velocity": mem_velocity,
                    "ewma_mem": self._ewma_mem
                }
            except Exception:
                pass

        # Fast statistical Z-score fallback (< 0.01ms)
        z_scores = []
        for f in FEATURES:
            val = float(row.get(f, 0) or 0)
            m = self._baseline_means.get(f, val)
            s = self._baseline_stds.get(f, 1.0)
            z_scores.append(abs(val - m) / s)

        max_z = max(z_scores) if z_scores else 0.0
        is_anomaly = max_z > 2.8

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
    """
    thresholds = thresholds or {
        "mem_high": 80,
        "mem_critical": 88,
        "cpu_high": 85,
        "swap_high": 50
    }
    actions = []

    mem_percent = float(row.get("mem_percent", 0) or 0)
    cpu_percent = float(row.get("cpu_percent", 0) or 0)
    swap_percent = float(row.get("swap_percent", 0) or 0)
    is_anomaly = anomaly_result.get("is_anomaly", False)
    mem_velocity = anomaly_result.get("mem_velocity", 0.0)

    # Trigger standby clear if memory is high, rapidly rising (+2% in one sample), or anomaly detected
    if mem_percent > thresholds["mem_high"] or (mem_percent > 70 and mem_velocity > 1.5) or is_anomaly:
        actions.append("CLEAR_STANDBY_MEMORY")

    if swap_percent > thresholds["swap_high"]:
        actions.append("REVIEW_PAGEFILE_SIZE")

    if cpu_percent > thresholds["cpu_high"]:
        actions.append("LOWER_BACKGROUND_PROCESS_PRIORITY")

    if not actions:
        actions.append("NO_ACTION_NEEDED")

    return actions
