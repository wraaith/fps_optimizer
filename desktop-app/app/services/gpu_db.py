# desktop-app/app/services/gpu_db.py

"""
GPU core-count database.

Loads ``data/gpu_cores.json`` once and caches the list in memory.
Provides a fuzzy ``lookup_gpu()`` that finds the most-specific match.
"""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

GPU_DB_PATH = Path(__file__).resolve().parent.parent / "data" / "gpu_cores.json"

# Module-level cache — loaded once, reused for every lookup
_gpu_cache: Optional[List[Dict[str, Any]]] = None


def _get_gpu_list() -> List[Dict[str, Any]]:
    """Return the GPU list, loading from disk only on first call."""
    global _gpu_cache
    if _gpu_cache is None:
        try:
            with open(GPU_DB_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            _gpu_cache = data.get("gpus", [])
        except (OSError, json.JSONDecodeError, KeyError):
            _gpu_cache = []
    return _gpu_cache


def lookup_gpu(gpu_name: str) -> Tuple[Optional[int], Optional[str]]:
    """Look up core count and type for *gpu_name*.

    When multiple entries match (e.g. "RTX 4070" and "RTX 4070 Laptop GPU"
    both appear inside "NVIDIA GeForce RTX 4070 Laptop GPU"), the entry
    with the **longest** model string wins — giving the most specific match.

    Never raises — returns (None, None) on any error.
    """
    try:
        gpus = _get_gpu_list()
        name_upper = gpu_name.upper()

        best_model_len = 0
        best_cores: Optional[int] = None
        best_core_type: Optional[str] = None

        for entry in gpus:
            model = entry.get("model", "")
            core_type = entry.get("core_type")
            core_count = entry.get("core_count")

            if not model or core_count is None:
                continue

            if model.upper() in name_upper and len(model) > best_model_len:
                best_model_len = len(model)
                best_cores = int(core_count)
                best_core_type = core_type

        return best_cores, best_core_type
    except Exception:
        return None, None