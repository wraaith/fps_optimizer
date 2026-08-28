# desktop-app/app/services/system_scan.py

"""
System scanner — gathers CPU, RAM, GPU, and OS information.

Every section is wrapped in try/except so that a failure in one area
(e.g. WMI unavailable, nvidia-smi missing) never crashes the whole scan.
"""

import platform
import subprocess
from typing import Any, Dict, Optional

import psutil

# COM initialization — needed when WMI is called from a background thread
try:
    import pythoncom
except ImportError:
    pythoncom = None

# Optional imports — gracefully degrade if missing
try:
    import wmi as _wmi_mod
except ImportError:
    _wmi_mod = None

try:
    import winreg
except ImportError:
    winreg = None

from .hardware_db import lookup_gpu, lookup_cpu

# Keywords that identify integrated GPUs (should be deprioritized)
_INTEGRATED_GPU_KEYWORDS = (
    "Intel(R) UHD", "Intel(R) HD", "Microsoft Basic",
    "Intel(R) Iris", "Vega Graphics",
)


# ── CPU ─────────────────────────────────────────────────────────

def _get_cpu_name() -> str:
    """Get the CPU name via WMI, falling back to platform.processor()."""
    if _wmi_mod is not None:
        try:
            c = _wmi_mod.WMI()
            processors = c.Win32_Processor()
            if processors:
                return processors[0].Name.strip()
        except Exception:
            pass
    return platform.processor() or "Unknown"

def get_live_cpu_power_wmi() -> Optional[float]:
    """Universal real-time CPU power draw via OpenHardwareMonitor WMI namespace."""
    if _wmi_mod is None:
        return None
    try:
        w = _wmi_mod.WMI(namespace="root\\OpenHardwareMonitor")
        sensors = w.Sensor()
        for sensor in sensors:
            if sensor.SensorType == "Power" and "CPU Total" in sensor.Name:
                return round(float(sensor.Value), 1)
    except Exception:
        return None


# ── GPU helpers ─────────────────────────────────────────────────

def _is_integrated_gpu(name: str) -> bool:
    """Return True if the GPU name looks like an integrated / basic adapter."""
    name_upper = name.upper()
    return any(kw.upper() in name_upper for kw in _INTEGRATED_GPU_KEYWORDS)


def _get_nvidia_smi_vram(gpu_name: str) -> Optional[float]:
    """Query nvidia-smi for the total VRAM in MiB, then convert to GB.

    nvidia-smi reports the exact usable VRAM (e.g. 8188 MiB) which is
    more accurate than the registry or WMI values.
    Returns None if nvidia-smi is unavailable or the GPU isn't NVIDIA.
    """
    if "NVIDIA" not in gpu_name.upper():
        return None
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.total",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=5,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        if result.returncode == 0 and result.stdout.strip():
            mib = float(result.stdout.strip().splitlines()[0])
            return round(mib / 1024, 2)
    except Exception:
        pass
    return None

def get_live_gpu_power() -> Optional[float]:
    """Universal real-time GPU power draw via NVML (NVIDIA)."""
    try:
        import pynvml
        pynvml.nvmlInit()
        handle = pynvml.nvmlDeviceGetHandleByIndex(0)
        # Returns power in milliwatts, divide by 1000 for exact live Watts
        power_mw = pynvml.nvmlDeviceGetPowerUsage(handle)
        return round(power_mw / 1000.0, 1)
    except Exception:
        return None # Fallback if non-NVIDIA or driver missing


def _read_vram_from_registry(adapter_string: str) -> Optional[float]:
    """Try reading the VRAM via the registry (64-bit qwMemorySize)."""
    if winreg is None:
        return None
    try:
        reg_path = (
            r"SYSTEM\CurrentControlSet\Control\Class"
            r"\{4d36e968-e325-11ce-bfc1-08002be10318}"
        )
        idx = 0
        while True:
            subkey_path = f"{reg_path}\\{idx:04d}"
            try:
                with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, subkey_path) as sk:
                    desc, _ = winreg.QueryValueEx(sk, "DriverDesc")
                    if adapter_string.upper() in str(desc).upper():
                        mem, _ = winreg.QueryValueEx(
                            sk, "HardwareInformation.qwMemorySize"
                        )
                        if isinstance(mem, int) and mem > 0:
                            return round(mem / (1024 ** 3), 2)
            except FileNotFoundError:
                break
            except OSError:
                pass
            idx += 1
    except Exception:
        pass
    return None


def _get_gpu_info() -> Dict[str, Any]:
    """Detect the primary (dedicated) GPU and its specs."""
    name = "Unknown"
    vram_gb: Optional[float] = None
    cores: Optional[int] = None
    core_type: Optional[str] = None
    series: Optional[str] = None
    bandwidth_gbs: Optional[float] = None
    gpu_tdp_w: Optional[int] = None

    if _wmi_mod is None:
        return {"name": name, "vram_gb": vram_gb,
                "cores": cores, "core_type": core_type,
                "series": series, "bandwidth_gbs": bandwidth_gbs,
                "tdp_w": gpu_tdp_w}

    try:
        c = _wmi_mod.WMI()
        gpus = c.Win32_VideoController()
        if not gpus:
            return {"name": name, "vram_gb": vram_gb,
                    "cores": cores, "core_type": core_type,
                    "series": series, "bandwidth_gbs": bandwidth_gbs,
                    "tdp_w": gpu_tdp_w}

        # Prefer a dedicated GPU over an integrated one
        gpu = gpus[0]
        for candidate in gpus:
            candidate_name = str(getattr(candidate, "Name", "") or "")
            if candidate_name and not _is_integrated_gpu(candidate_name):
                gpu = candidate
                break

        if hasattr(gpu, "Name") and gpu.Name:
            name = str(gpu.Name)

        # --- VRAM detection (most-accurate first) ---
        # 1. nvidia-smi (exact usable MiB, most reliable for NVIDIA GPUs)
        vram_gb = _get_nvidia_smi_vram(name)

        # 2. Registry (64-bit qwMemorySize, works for all vendors)
        if vram_gb is None:
            vram_gb = _read_vram_from_registry(name)

        # 3. WMI AdapterRAM (32-bit, may overflow for >4 GB GPUs)
        if vram_gb is None and hasattr(gpu, "AdapterRAM") and gpu.AdapterRAM:
            try:
                raw = int(gpu.AdapterRAM)
                if raw > 0:
                    vram_gb = round(raw / (1024 ** 3), 2)
            except (ValueError, TypeError):
                pass

        # Look up enriched specs from the hardware database
        gpu_specs = lookup_gpu(name)
        cores = gpu_specs["cores"]
        core_type = gpu_specs["core_type"]
        series = gpu_specs["series"]
        bandwidth_gbs = gpu_specs["bandwidth_gbs"]
        
        # Override database TDP with real-time hardware telemetry if available
        live_power = get_live_gpu_power()
        if live_power is not None:
            gpu_tdp_w = live_power
        else:
            gpu_tdp_w = gpu_specs["tdp_w"]

        # Use DB VRAM as fallback if detection failed
        if vram_gb is None and gpu_specs["vram_gb"] is not None:
            vram_gb = gpu_specs["vram_gb"]

    except Exception:
        pass

    return {
        "name": name,
        "vram_gb": vram_gb,
        "cores": cores,
        "core_type": core_type,
        "series": series,
        "bandwidth_gbs": bandwidth_gbs,
        "tdp_w": gpu_tdp_w,
    }


# ── OS ──────────────────────────────────────────────────────────

def _get_os_info() -> Dict[str, str]:
    """Return correct OS name, release, and version.

    ``platform.release()`` returns ``'10'`` even on Windows 11.
    We detect Win11 by checking whether the build number >= 22000.
    """
    os_name = platform.system()        # "Windows"
    os_version = platform.version()    # e.g. "10.0.22631" or "10.0.26200"
    os_release = platform.release()    # "10" (even on Win11)

    try:
        build = int(os_version.split(".")[-1])
        if build >= 22000:
            os_release = "11"
    except (ValueError, IndexError):
        pass

    return {
        "name": os_name,
        "release": os_release,
        "version": os_version,
    }


# ── Public entry point ──────────────────────────────────────────

def run_system_scan() -> Dict[str, Any]:
    """Run a full system scan. Never raises — returns partial data on error."""

    # Initialize COM for this thread — required for WMI to work
    # when called from a background thread (e.g. scan_view's worker).
    _com_initialized = False
    if pythoncom is not None:
        try:
            pythoncom.CoInitialize()
            _com_initialized = True
        except Exception:
            pass

    # CPU
    try:
        cpu_name = _get_cpu_name()
        cpu_logical = psutil.cpu_count(logical=True)
        cpu_physical = psutil.cpu_count(logical=False) or cpu_logical
        cpu_usage = psutil.cpu_percent(interval=1.0)
    except Exception:
        cpu_name = "Unknown"
        cpu_logical = 0
        cpu_physical = 0
        cpu_usage = 0.0

    # Enrich CPU data from the hardware database
    try:
        cpu_db = lookup_cpu(cpu_name)
        cpu_threads = cpu_db["threads"] or cpu_logical
        
        live_power = get_live_cpu_power_wmi()
        if live_power is not None:
            cpu_tdp_w = live_power
        else:
            cpu_tdp_w = cpu_db["tdp_w"]
    except Exception:
        cpu_threads = cpu_logical
        cpu_tdp_w = None

    # RAM
    try:
        vm = psutil.virtual_memory()
        ram_total_gb = round(vm.total / (1024 ** 3), 1)
        ram_used_gb = round((vm.total - vm.available) / (1024 ** 3), 1)
    except Exception:
        ram_total_gb = 0.0
        ram_used_gb = 0.0

    # GPU
    try:
        gpu_info = _get_gpu_info()
    except Exception:
        gpu_info = {"name": "Unknown", "vram_gb": None,
                    "cores": None, "core_type": None,
                    "series": None, "bandwidth_gbs": None,
                    "tdp_w": None}

    # OS
    try:
        os_info = _get_os_info()
    except Exception:
        os_info = {"name": platform.system(), "release": platform.release(),
                   "version": platform.version()}

    # Calculate total system TDP
    total_tdp_w = None
    if cpu_tdp_w is not None and gpu_info.get("tdp_w") is not None:
        total_tdp_w = cpu_tdp_w + gpu_info["tdp_w"]

    # Calculate bottleneck score (CPU cores / GPU VRAM ratio)
    bottleneck_score = None
    if (cpu_physical and cpu_physical > 0 and
            gpu_info.get("vram_gb") and gpu_info["vram_gb"] > 0):
        bottleneck_score = round(
            gpu_info["vram_gb"] / cpu_physical, 2
        )

    result = {
        "cpu": {
            "name": cpu_name,
            "logical_cores": cpu_logical,
            "physical_cores": cpu_physical,
            "threads": cpu_threads,
            "tdp_w": cpu_tdp_w,
            "usage_percent": cpu_usage,
        },
        "ram": {
            "total_gb": ram_total_gb,
            "used_gb": ram_used_gb,
        },
        "gpu": gpu_info,
        "os": os_info,
        "system": {
            "total_tdp_w": total_tdp_w,
            "bottleneck_score": bottleneck_score,
        },
    }

    # Release COM for this thread
    if _com_initialized:
        try:
            pythoncom.CoUninitialize()
        except Exception:
            pass

    return result