import platform
from typing import Any, Dict, Optional

import psutil
import wmi

from .gpu_db import lookup_gpu


def _get_cpu_name() -> str:
    try:
        c = wmi.WMI()
        return c.Win32_Processor()[0].Name.strip()
    except Exception:
        return platform.processor() or "Unknown"


def _get_gpu_info() -> Dict[str, Any]:
    name = "Unknown"
    vram_gb: Optional[float] = None

    try:
        c = wmi.WMI()
        gpus = c.Win32_VideoController()
        if not gpus:
            return {"name": name, "vram_gb": vram_gb, "cores": None, "core_type": None}

        gpu = gpus[0]

        if hasattr(gpu, "Name") and gpu.Name:
            name = str(gpu.Name)

        if hasattr(gpu, "AdapterRAM") and gpu.AdapterRAM:
            try:
                vram_gb = round(int(gpu.AdapterRAM) / (1024 ** 3), 1)
            except (ValueError, TypeError):
                vram_gb = None

        cores, core_type = lookup_gpu(name)

    except Exception:
        cores, core_type = None, None

    return {
        "name": name,
        "vram_gb": vram_gb,
        "cores": cores,
        "core_type": core_type,
    }


def run_system_scan() -> Dict[str, Any]:
    cpu_name = _get_cpu_name()
    cpu_logical_cores = psutil.cpu_count(logical=True)
    cpu_physical_cores = psutil.cpu_count(logical=False) or cpu_logical_cores
    cpu_usage_percent = psutil.cpu_percent(interval=1.0)

    vm = psutil.virtual_memory()
    ram_total_gb = round(vm.total / (1024 ** 3), 1)
    ram_used_gb = round((vm.total - vm.available) / (1024 ** 3), 1)

    os_name = platform.system()
    os_release = platform.release()
    os_version = platform.version()

    gpu_info = _get_gpu_info()

    return {
        "cpu": {
            "name": cpu_name,
            "logical_cores": cpu_logical_cores,
            "physical_cores": cpu_physical_cores,
            "usage_percent": cpu_usage_percent,
        },
        "ram": {
            "total_gb": ram_total_gb,
            "used_gb": ram_used_gb,
        },
        "gpu": gpu_info,
        "os": {
            "name": os_name,
            "release": os_release,
            "version": os_version,
        },
    }