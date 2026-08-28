# desktop-app/app/services/predictor.py

"""
FPS predictor — lightweight CSV-lookup engine.

Uses the benchmark dataset (``data/benchmark_data.csv``) to predict
Min / Avg / Max FPS for a given CPU + GPU + RAM + resolution + settings
combination.

Prediction strategy (in priority order):
1. **Exact match** — same CPU, GPU, RAM, resolution, settings.
2. **Fuzzy match** — same GPU + resolution + settings, best-matching CPU.
3. **Interpolated** — weighted average of nearest neighbours in the dataset,
   scored on name similarity *and* hardware specs (VRAM, bandwidth, TDP).

No ML dependencies required — pure Python with the ``csv`` module.
"""

import csv
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

_DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "benchmark_data.csv"

# Module-level cache
_benchmark_cache: Optional[List[Dict[str, Any]]] = None


def _load_benchmarks() -> List[Dict[str, Any]]:
    """Load and cache the benchmark dataset.

    Malformed rows are skipped individually and logged — a single bad
    row (empty field, stray text, etc.) no longer discards the entire
    dataset.
    """
    global _benchmark_cache
    if _benchmark_cache is None:
        rows: List[Dict[str, Any]] = []
        try:
            with open(_DATA_PATH, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for i, row in enumerate(reader):
                    try:
                        rows.append({
                            "cpu": row["CPU"].strip(),
                            "cpu_cores": int(row["CPU Cores"]),
                            "cpu_threads": int(row["CPU Threads"]),
                            "cpu_tdp": int(row["CPU TDP (W)"]),
                            "gpu": row["GPU"].strip(),
                            "gpu_series": row["GPU Series"].strip(),
                            "gpu_vram": int(row["GPU VRAM (GB)"]),
                            "gpu_bandwidth": float(row["GPU Bandwidth (GB/s)"]),
                            "gpu_tdp": int(row["GPU TDP (W)"]),
                            "total_tdp": int(row["Total System TDP (W)"]),
                            "bottleneck": float(row["Bottleneck Score"]),
                            "ram": int(row["RAM (GB)"]),
                            "resolution": row["Resolution"].strip(),
                            "settings": row["Graphics Settings"].strip(),
                            "min_fps": int(row["Min FPS"]),
                            "avg_fps": int(row["Avg FPS"]),
                            "max_fps": int(row["Max FPS"]),
                        })
                    except (KeyError, ValueError) as e:
                        logger.warning("Skipping malformed benchmark row %d: %s", i, e)
        except OSError as e:
            logger.error("Could not open benchmark dataset at %s: %s", _DATA_PATH, e)
        _benchmark_cache = rows
        logger.info("Loaded %d benchmark rows from %s", len(rows), _DATA_PATH)
    return _benchmark_cache


def _normalize(name: str) -> str:
    """Normalize hardware names for comparison."""
    return name.upper().strip()


def _string_similarity(a: str, b: str) -> float:
    """Score how similar two hardware name strings are (0.0-1.0).

    Used for both CPU and GPU name comparison — the logic is identical,
    so there is no need for two separate functions.
    """
    a_norm, b_norm = _normalize(a), _normalize(b)
    if a_norm == b_norm:
        return 1.0

    if a_norm in b_norm or b_norm in a_norm:
        return 0.8

    tokens_a = set(a_norm.split())
    tokens_b = set(b_norm.split())
    if not tokens_a or not tokens_b:
        return 0.0
    overlap = len(tokens_a & tokens_b)
    return overlap / max(len(tokens_a), len(tokens_b))


def _resolution_pixels(res: str) -> int:
    """Convert a resolution string like '1920x1080' to total pixel count."""
    try:
        w, h = res.lower().split("x")
        return int(w) * int(h)
    except (ValueError, AttributeError):
        return 0


_SETTINGS_RANK = {"low": 1, "medium": 2, "high": 3, "ultra": 4}


def _settings_distance(a: str, b: str) -> float:
    """Distance between two graphics settings (0.0-3.0)."""
    rank_a = _SETTINGS_RANK.get(a.lower().strip(), 2)
    rank_b = _SETTINGS_RANK.get(b.lower().strip(), 2)
    return abs(rank_a - rank_b)


def _spec_similarity(
    target_vram: Optional[float],
    target_bandwidth: Optional[float],
    target_tdp: Optional[float],
    row: Dict[str, Any],
) -> float:
    """Score similarity based on numeric GPU specs (0.0-1.0).

    Complements name-string matching: two GPUs that don't share a
    model name (e.g. an unlisted variant) but have near-identical
    VRAM/bandwidth/TDP are still a decent fuzzy match. Returns a
    neutral 0.5 when the caller has no target specs to compare against.
    """
    if target_vram is None and target_bandwidth is None and target_tdp is None:
        return 0.5

    scores = []
    if target_vram is not None and row.get("gpu_vram") is not None:
        scores.append(max(0.0, 1.0 - abs(target_vram - row["gpu_vram"]) / 24.0))
    if target_bandwidth is not None and row.get("gpu_bandwidth") is not None:
        scores.append(max(0.0, 1.0 - abs(target_bandwidth - row["gpu_bandwidth"]) / 1000.0))
    if target_tdp is not None and row.get("gpu_tdp") is not None:
        scores.append(max(0.0, 1.0 - abs(target_tdp - row["gpu_tdp"]) / 400.0))

    return sum(scores) / len(scores) if scores else 0.5


def _confidence_from_score(score: float) -> str:
    """Map a fuzzy-match score to a human-readable confidence tier."""
    if score >= 0.85:
        return "high"
    if score >= 0.6:
        return "medium"
    if score >= 0.35:
        return "low"
    return "very_low"


def predict_fps(
    cpu: str,
    gpu: str,
    ram_gb: int = 16,
    resolution: str = "1920x1080",
    settings: str = "High",
    gpu_vram: Optional[float] = None,
    gpu_bandwidth: Optional[float] = None,
    gpu_tdp: Optional[float] = None,
) -> Dict[str, Any]:
    """Predict FPS for the given hardware + display configuration.

    ``gpu_vram``/``gpu_bandwidth``/``gpu_tdp`` are optional enriched specs
    (typically pulled from ``hardware_db.lookup_gpu()``) used to improve
    the fuzzy-matching pass when no exact/near name match exists.

    Returns a dict with keys:
        min_fps, avg_fps, max_fps  — predicted values (int)
        confidence                 — 'exact', 'high', 'medium', 'low', 'very_low', 'none'
        matches                    — number of dataset rows used
    """
    benchmarks = _load_benchmarks()
    if not benchmarks:
        return {
            "min_fps": None, "avg_fps": None, "max_fps": None,
            "confidence": "none", "matches": 0,
        }

    target_res = _normalize(resolution)
    target_settings = settings.strip().lower()

    # ── Pass 1: exact match ─────────────────────────────────────
    exact_matches = [
        row for row in benchmarks
        if (_normalize(row["gpu"]) == _normalize(gpu)
            and _normalize(row["cpu"]) == _normalize(cpu)
            and _normalize(row["resolution"]) == target_res
            and row["settings"].lower() == target_settings
            and row["ram"] == ram_gb)
    ]
    if exact_matches:
        return _aggregate(exact_matches, "exact")

    # ── Pass 2: same GPU + resolution + settings ────────────────
    gpu_res_matches = [
        row for row in benchmarks
        if (_normalize(row["gpu"]) == _normalize(gpu)
            and _normalize(row["resolution"]) == target_res
            and row["settings"].lower() == target_settings)
    ]
    if gpu_res_matches:
        return _aggregate(gpu_res_matches, "high")

    # ── Pass 3: same GPU + resolution (any settings) ────────────
    gpu_matches = [
        row for row in benchmarks
        if _normalize(row["gpu"]) == _normalize(gpu)
           and _normalize(row["resolution"]) == target_res
    ]
    if gpu_matches:
        # Weight by settings proximity
        return _weighted_aggregate(gpu_matches, target_settings, "medium")

    # ── Pass 4: fuzzy — score all rows on name + specs ──────────
    scored: List[Tuple[float, Dict[str, Any]]] = []
    target_pixels = _resolution_pixels(resolution)

    for row in benchmarks:
        gpu_sim = _string_similarity(gpu, row["gpu"])
        if gpu_sim < 0.3:
            continue  # skip very dissimilar GPUs

        cpu_sim = _string_similarity(cpu, row["cpu"])
        spec_sim = _spec_similarity(gpu_vram, gpu_bandwidth, gpu_tdp, row)
        row_pixels = _resolution_pixels(row["resolution"])

        # Resolution distance (normalised by 4K pixels)
        res_dist = abs(target_pixels - row_pixels) / (3840 * 2160) if target_pixels else 1.0
        settings_dist = _settings_distance(settings, row["settings"])
        ram_dist = abs(ram_gb - row["ram"]) / 32.0

        # Combined score (higher = better match)
        score = (
            gpu_sim * 0.30
            + cpu_sim * 0.20
            + spec_sim * 0.20
            + max(0, 1.0 - res_dist) * 0.20
            + max(0, 1.0 - settings_dist / 3.0) * 0.05
            + max(0, 1.0 - ram_dist) * 0.05
        )
        scored.append((score, row))

    if not scored:
        return {
            "min_fps": None, "avg_fps": None, "max_fps": None,
            "confidence": "none", "matches": 0,
        }

    # Take top 5 matches weighted by score
    scored.sort(key=lambda x: x[0], reverse=True)
    top = scored[:5]
    total_weight = sum(s for s, _ in top)
    if total_weight == 0:
        return {
            "min_fps": None, "avg_fps": None, "max_fps": None,
            "confidence": "none", "matches": 0,
        }

    min_fps = sum(s * r["min_fps"] for s, r in top) / total_weight
    avg_fps = sum(s * r["avg_fps"] for s, r in top) / total_weight
    max_fps = sum(s * r["max_fps"] for s, r in top) / total_weight

    return {
        "min_fps": round(min_fps),
        "avg_fps": round(avg_fps),
        "max_fps": round(max_fps),
        "confidence": _confidence_from_score(top[0][0]),
        "matches": len(top),
    }


def _aggregate(rows: List[Dict[str, Any]], confidence: str) -> Dict[str, Any]:
    """Simple average across matched rows."""
    n = len(rows)
    return {
        "min_fps": round(sum(r["min_fps"] for r in rows) / n),
        "avg_fps": round(sum(r["avg_fps"] for r in rows) / n),
        "max_fps": round(sum(r["max_fps"] for r in rows) / n),
        "confidence": confidence,
        "matches": n,
    }


def _weighted_aggregate(
    rows: List[Dict[str, Any]],
    target_settings: str,
    confidence: str,
) -> Dict[str, Any]:
    """Average weighted by settings proximity."""
    weights = []
    for row in rows:
        dist = _settings_distance(target_settings, row["settings"])
        weights.append(max(0.1, 1.0 - dist / 3.0))

    total = sum(weights)
    return {
        "min_fps": round(sum(w * r["min_fps"] for w, r in zip(weights, rows)) / total),
        "avg_fps": round(sum(w * r["avg_fps"] for w, r in zip(weights, rows)) / total),
        "max_fps": round(sum(w * r["max_fps"] for w, r in zip(weights, rows)) / total),
        "confidence": confidence,
        "matches": len(rows),
    }


def get_available_options() -> Dict[str, List[str]]:
    """Return the available CPUs, GPUs, resolutions, and settings from the dataset."""
    benchmarks = _load_benchmarks()
    cpus = sorted(set(r["cpu"] for r in benchmarks))
    gpus = sorted(set(r["gpu"] for r in benchmarks))
    resolutions = sorted(set(r["resolution"] for r in benchmarks),
                         key=_resolution_pixels)
    settings = ["Low", "Medium", "High", "Ultra"]
    ram_options = sorted(set(r["ram"] for r in benchmarks))
    return {
        "cpus": cpus,
        "gpus": gpus,
        "resolutions": resolutions,
        "settings": settings,
        "ram_options": ram_options,
    }