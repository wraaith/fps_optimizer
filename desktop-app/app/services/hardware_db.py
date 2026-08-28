# desktop-app/app/services/hardware_db.py

"""
Unified hardware database — CPU and GPU specs.

Loads ``data/gpu_cores.json`` and ``data/cpu_specs.json`` once and caches
them in memory.  Provides fuzzy ``lookup_gpu()`` and ``lookup_cpu()``
helpers that find the most-specific match for a detected hardware name.
"""

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

_DATA_DIR = Path(__file__).resolve().parent.parent / "data"
_GPU_DB_PATH = _DATA_DIR / "gpu_cores.json"
_CPU_DB_PATH = _DATA_DIR / "cpu_specs.json"

# Module-level caches — loaded once, reused for every lookup
_gpu_cache: Optional[List[Dict[str, Any]]] = None
_cpu_cache: Optional[List[Dict[str, Any]]] = None


def _contains_model(model_upper: str, name_upper: str) -> bool:
    """Check whether *model_upper* appears inside *name_upper* as a whole
    token — not just as a raw substring (prevents "580" matching inside
    "5800", "5600" matching inside "5600X", etc.)."""
    pattern = r'(?<![A-Z0-9])' + re.escape(model_upper) + r'(?![A-Z0-9])'
    return re.search(pattern, name_upper) is not None


# ── GPU database ────────────────────────────────────────────────


def _get_gpu_list() -> List[Dict[str, Any]]:
    """Return the GPU list, loading from disk only on first call."""
    global _gpu_cache
    if _gpu_cache is None:
        try:
            with open(_GPU_DB_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            _gpu_cache = data.get("gpus", [])
        except (OSError, json.JSONDecodeError, KeyError):
            _gpu_cache = []
    return _gpu_cache


def lookup_gpu(gpu_name: str) -> Dict[str, Any]:
    """Look up full specs for *gpu_name*.

    When multiple entries match (e.g. "RTX 4070" and "RTX 4070 Laptop GPU"
    both appear inside "NVIDIA GeForce RTX 4070 Laptop GPU"), the entry
    with the **longest** model string wins — giving the most specific match.
    Matching requires a word boundary around the model string so "580"
    cannot match inside "5800" etc.

    Returns a dict with keys: cores, core_type, series, vram_gb,
    bandwidth_gbs, tdp_w.  Missing values are None.
    Never raises — returns all-None dict on any error.
    """
    result = {
        "cores": None,
        "core_type": None,
        "series": None,
        "vram_gb": None,
        "bandwidth_gbs": None,
        "tdp_w": None,
    }
    try:
        gpus = _get_gpu_list()
        name_upper = gpu_name.upper()

        best_model_len = 0
        best_entry: Optional[Dict[str, Any]] = None

        for entry in gpus:
            model = entry.get("model", "")
            if not model:
                continue
            model_upper = model.upper()
            if _contains_model(model_upper, name_upper) and len(model) > best_model_len:
                best_model_len = len(model)
                best_entry = entry

        if best_entry is not None:
            result["cores"] = (
                int(best_entry["core_count"])
                if best_entry.get("core_count") is not None
                else None
            )
            result["core_type"] = best_entry.get("core_type")
            result["series"] = best_entry.get("series")
            result["vram_gb"] = best_entry.get("vram_gb")
            result["bandwidth_gbs"] = best_entry.get("bandwidth_gbs")
            result["tdp_w"] = best_entry.get("tdp_w")

        # Fallback to heuristic estimation if TDP is missing
        if result["tdp_w"] is None:
            result["tdp_w"] = _estimate_gpu_tdp(gpu_name)
    except Exception:
        pass

    return result


def _estimate_gpu_tdp(name: str) -> Optional[int]:
    """Fallback heuristic to estimate GPU TDP based on model name."""
    name_upper = name.upper()
    is_laptop = "LAPTOP" in name_upper or "MOBILE" in name_upper

    if "ARC" in name_upper:
        if "A7" in name_upper:
            return 120 if is_laptop else 225
        if "A5" in name_upper:
            return 80 if is_laptop else 175
        if "A3" in name_upper:
            return 35 if is_laptop else 75
        return 75

    if "RTX" in name_upper or "GTX" in name_upper:
        if "90" in name_upper:
            return 150 if is_laptop else 350
        if "80" in name_upper:
            return 130 if is_laptop else 250
        if "70" in name_upper:
            return 115 if is_laptop else 200
        if "60" in name_upper:
            return 90 if is_laptop else 150
        if "50" in name_upper:
            return 60 if is_laptop else 100

    if "RX " in name_upper:
        if "900" in name_upper:
            return 150 if is_laptop else 300
        if "800" in name_upper:
            return 130 if is_laptop else 250
        if "700" in name_upper:
            return 100 if is_laptop else 200
        if "600" in name_upper:
            return 80 if is_laptop else 150
        if "500" in name_upper:
            return 60 if is_laptop else 100

    return 75  # Safe baseline generic fallback for unknowns


# Legacy compatibility — returns (cores, core_type) tuple
def lookup_gpu_cores(gpu_name: str) -> Tuple[Optional[int], Optional[str]]:
    """Legacy helper — returns (core_count, core_type) for *gpu_name*."""
    info = lookup_gpu(gpu_name)
    return info["cores"], info["core_type"]


# ── CPU database ────────────────────────────────────────────────


def _get_cpu_list() -> List[Dict[str, Any]]:
    """Return the CPU list, loading from disk only on first call."""
    global _cpu_cache
    if _cpu_cache is None:
        try:
            with open(_CPU_DB_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            _cpu_cache = data.get("cpus", [])
        except (OSError, json.JSONDecodeError, KeyError):
            _cpu_cache = []
    return _cpu_cache


def _extract_cpu_model_id(cpu_name: str) -> str:
    """Extract the CPU model identifier from a full WMI-style name.

    Examples:
        '13th Gen Intel(R) Core(TM) i7-13700K' → 'i7-13700K'
        'AMD Ryzen 7 7800X3D 8-Core Processor'  → '7800X3D'
        'Intel i5-12600K'                        → 'i5-12600K'
    """
    # Look for Intel-style identifiers: i3-XXXXX, i5-XXXXX, etc.
    m = re.search(r'(i[3579]-\d{4,5}\w*)', cpu_name, re.IGNORECASE)
    if m:
        return m.group(1)

    # Look for AMD-style model numbers: 5600X, 7800X3D, 4100, etc.
    m = re.search(r'(\d{4}X?\d*[A-Z]*\d*D?)\b', cpu_name)
    if m:
        return m.group(1)

    return cpu_name


def lookup_cpu(cpu_name: str) -> Dict[str, Any]:
    """Look up full specs for *cpu_name*.

    Uses word-boundary-aware substring matching with longest-match
    priority, same as the GPU lookup.  Falls back to model-identifier
    matching for WMI names like "13th Gen Intel(R) Core(TM) i7-13700K".
    Returns a dict with keys: cores, threads, tdp_w.
    Never raises — returns all-None dict on any error.
    """
    result = {
        "cores": None,
        "threads": None,
        "tdp_w": None,
    }
    try:
        cpus = _get_cpu_list()
        name_upper = cpu_name.upper()

        best_name_len = 0
        best_entry: Optional[Dict[str, Any]] = None

        # Pass 1: word-boundary substring match (DB name in detected name)
        for entry in cpus:
            name = entry.get("name", "")
            if not name:
                continue
            name_upper_entry = name.upper()
            if _contains_model(name_upper_entry, name_upper) and len(name) > best_name_len:
                best_name_len = len(name)
                best_entry = entry

        # Pass 2: model-identifier match as fallback
        if best_entry is None:
            detected_id = _extract_cpu_model_id(cpu_name).upper()
            for entry in cpus:
                entry_id = _extract_cpu_model_id(entry.get("name", "")).upper()
                if not entry_id:
                    continue
                if entry_id == detected_id:
                    best_entry = entry
                    break

        if best_entry is not None:
            result["cores"] = best_entry.get("cores")
            result["threads"] = best_entry.get("threads")
            result["tdp_w"] = best_entry.get("tdp_w")

        # Fallback to heuristic estimation if TDP is missing
        if result["tdp_w"] is None:
            result["tdp_w"] = _estimate_cpu_tdp(cpu_name)
    except Exception:
        pass

    return result


def _estimate_cpu_tdp(cpu_name: str) -> Optional[float]:
    """Fallback heuristic to estimate CPU TDP based on model suffix using regex.

    Matches against the extracted model identifier (e.g. "I7-13700K",
    "7800X3D") rather than the raw WMI string, so boilerplate words like
    "CPU", "Processor", or "Pentium" cannot falsely trigger a suffix match
    (they all contain the letters "P" and/or "U").
    """
    model_id = _extract_cpu_model_id(cpu_name).upper()

    # 1. High-Performance Laptops (HX, HK) -> ~55W base
    if re.search(r'\d{4,5}H[XK]\b', model_id):
        return 55.0

    # 2. Standard Laptops (H, HS) -> ~45W base
    if re.search(r'\d{4,5}HS?\b', model_id):
        return 45.0

    # 3. Thin & Light Mobile (U-series, P-series, G7) -> ~15-28W
    if re.search(r'\d{3,5}[UP]\b', model_id) or re.search(r'G7\b', model_id):
        return 15.0

    # 4. High-End Enthusiast Desktop (K, KS, KF, X, X3D) -> ~125W
    if re.search(r'\d{4,5}(KS|KF|X3D|K|X)\b', model_id):
        return 125.0

    # Default generic desktop processor baseline
    return 65.0