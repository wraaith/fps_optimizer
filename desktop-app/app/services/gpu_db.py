import json
from pathlib import Path
from typing import Optional, Tuple, Dict, Any

GPU_DB_PATH = Path(__file__).resolve().parent.parent / "data" / "gpu_cores.json"


def load_gpu_db() -> Dict[str, Any]:
    with open(GPU_DB_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def lookup_gpu(gpu_name: str) -> Tuple[Optional[int], Optional[str]]:
    try:
        db = load_gpu_db()
    except OSError:
        return None, None

    name_upper = gpu_name.upper()

    for entry in db.get("gpus", []):
        model = entry.get("model", "")
        core_type = entry.get("core_type")
        core_count = entry.get("core_count")

        if not model or core_count is None:
            continue

        if model.upper() in name_upper:
            return int(core_count), core_type

    return None, None