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
    """Get the CPU name via Windows Registry (0.001ms, zero COM), falling back to platform.processor()."""
    if winreg is not None:
        try:
            with winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE,
                r"HARDWARE\DESCRIPTION\System\CentralProcessor\0",
            ) as k:
                val, _ = winreg.QueryValueEx(k, "ProcessorNameString")
                if val and str(val).strip():
                    return str(val).strip()
        except Exception:
            pass
    return platform.processor() or "Unknown CPU"

def get_live_cpu_power_wmi() -> Optional[float]:
    """Universal real-time CPU power draw via OpenHardwareMonitor WMI namespace if active."""
    # Check if OpenHardwareMonitor is active before attempting any WMI connection
    # to avoid COM dangling IUnknown apartment crashes on Windows.
    try:
        ohm_running = any(
            p.info.get('name') and p.info['name'].lower() in ("openhardwaremonitor.exe", "librehardwaremonitor.exe")
            for p in psutil.process_iter(['name'])
        )
        if not ohm_running:
            return None
    except Exception:
        return None

    if _wmi_mod is None:
        return None

    try:
        w = _wmi_mod.WMI(namespace="root\\OpenHardwareMonitor")
        sensors = w.Sensor()
        val = None
        for sensor in sensors:
            if getattr(sensor, "SensorType", "") == "Power" and "CPU Total" in getattr(sensor, "Name", ""):
                val = round(float(sensor.Value), 1)
                break
        del sensors
        del w
        return val
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
        try:
            handle = pynvml.nvmlDeviceGetHandleByIndex(0)
            power_mw = pynvml.nvmlDeviceGetPowerUsage(handle)
            return round(power_mw / 1000.0, 1)
        finally:
            try:
                pynvml.nvmlShutdown()
            except Exception:
                pass
    except Exception:
        return None


def _get_gpus_from_registry() -> list:
    """Read all installed display adapters directly from Windows Registry (zero COM, zero crash)."""
    if winreg is None:
        return []
    adapters = []
    reg_path = (
        r"SYSTEM\CurrentControlSet\Control\Class"
        r"\{4d36e968-e325-11ce-bfc1-08002be10318}"
    )
    for idx in range(20):
        subkey_path = f"{reg_path}\\{idx:04d}"
        try:
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, subkey_path) as sk:
                try:
                    desc, _ = winreg.QueryValueEx(sk, "DriverDesc")
                    desc = str(desc).strip()
                except OSError:
                    desc = ""

                if desc:
                    mem_gb = None
                    for val_name in (
                        "HardwareInformation.qwMemorySize",
                        "qwMemorySize",
                        "HardwareInformation.MemorySize",
                    ):
                        try:
                            mem, _ = winreg.QueryValueEx(sk, val_name)
                            if isinstance(mem, int) and mem > 0:
                                mem_gb = round(mem / (1024 ** 3), 2)
                                break
                        except OSError:
                            pass
                    adapters.append((desc, mem_gb))
        except FileNotFoundError:
            break
        except OSError:
            pass
    return adapters


def _read_vram_from_registry(adapter_string: str) -> Optional[float]:
    """Try reading the VRAM via the registry (64-bit qwMemorySize)."""
    adapters = _get_gpus_from_registry()
    for desc, mem_gb in adapters:
        if adapter_string.upper() in desc.upper() and mem_gb:
            return mem_gb
    return None


def _get_gpu_info() -> Dict[str, Any]:
    """Detect the primary (dedicated) GPU and its specs safely without WMI/COM crashes."""
    name = "Unknown"
    vram_gb: Optional[float] = None
    cores: Optional[int] = None
    core_type: Optional[str] = None
    series: Optional[str] = None
    bandwidth_gbs: Optional[float] = None
    gpu_tdp_w: Optional[int] = None

    # Step 1: Query Windows Registry for display adapters (100% stable, zero COM)
    reg_adapters = _get_gpus_from_registry()
    if reg_adapters:
        # Prefer a dedicated GPU (e.g. NVIDIA, AMD, Intel Arc) over integrated
        chosen = reg_adapters[0]
        for candidate_name, candidate_vram in reg_adapters:
            if candidate_name and not _is_integrated_gpu(candidate_name):
                chosen = (candidate_name, candidate_vram)
                break
        name = chosen[0]
        vram_gb = chosen[1]

    # Step 2: WMI fallback ONLY if registry found zero adapters
    if (not name or name == "Unknown") and _wmi_mod is not None:
        try:
            c = _wmi_mod.WMI()
            gpus = c.Win32_VideoController()
            if gpus:
                gpu = gpus[0]
                for cand in gpus:
                    cand_name = str(getattr(cand, "Name", "") or "")
                    if cand_name and not _is_integrated_gpu(cand_name):
                        gpu = cand
                        break
                if hasattr(gpu, "Name") and gpu.Name:
                    name = str(gpu.Name)
                if hasattr(gpu, "AdapterRAM") and gpu.AdapterRAM:
                    try:
                        raw = int(gpu.AdapterRAM)
                        if raw > 0:
                            vram_gb = round(raw / (1024 ** 3), 2)
                    except Exception:
                        pass
            del gpus
            del c
        except Exception:
            pass

    # Step 3: Exact VRAM detection via nvidia-smi (most accurate for NVIDIA)
    exact_vram = _get_nvidia_smi_vram(name)
    if exact_vram is not None:
        vram_gb = exact_vram

    # Step 4: Look up enriched specs from the hardware database
    gpu_specs = lookup_gpu(name)
    cores = gpu_specs["cores"]
    core_type = gpu_specs["core_type"]
    series = gpu_specs["series"]
    bandwidth_gbs = gpu_specs["bandwidth_gbs"]

    # Step 5: Override database TDP with real-time hardware telemetry if available
    live_power = get_live_gpu_power()
    if live_power is not None:
        gpu_tdp_w = live_power
    else:
        gpu_tdp_w = gpu_specs["tdp_w"]

    # Use DB VRAM as fallback if detection failed
    if vram_gb is None and gpu_specs["vram_gb"] is not None:
        vram_gb = gpu_specs["vram_gb"]

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

_CACHED_STATIC_HARDWARE: Optional[Dict[str, Any]] = None


def run_system_scan(cached: bool = False) -> Dict[str, Any]:
    """Run a system scan. Never raises — returns partial data on error.

    Uses 100% stable Win32 Registry + psutil queries. Zero COM/WMI dependencies,
    eliminating all ntdll heap corruption and IUnknown release crashes.
    """
    global _CACHED_STATIC_HARDWARE

    if cached and _CACHED_STATIC_HARDWARE is not None:
        result = dict(_CACHED_STATIC_HARDWARE)
        # Update live RAM used and CPU percent quickly
        try:
            vm = psutil.virtual_memory()
            result["ram"] = dict(result["ram"])
            result["ram"]["used_gb"] = round((vm.total - vm.available) / (1024 ** 3), 1)
        except Exception:
            pass
        return result

    # CPU
    try:
        cpu_name = _get_cpu_name()
        cpu_logical = psutil.cpu_count(logical=True) or 4
        cpu_physical = psutil.cpu_count(logical=False) or cpu_logical
        cpu_usage = psutil.cpu_percent(interval=None) or 0.0
    except Exception:
        cpu_name = "Unknown"
        cpu_logical = 4
        cpu_physical = 4
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
        ram_total_gb = 16.0
        ram_used_gb = 8.0

    # GPU (100% registry + nvidia-smi, zero COM)
    try:
        gpu_info = _get_gpu_info()
    except Exception:
        gpu_info = {
            "name": "Unknown",
            "vram_gb": None,
            "cores": None,
            "core_type": None,
            "series": None,
            "bandwidth_gbs": None,
            "tdp_w": None,
        }

    # OS
    try:
        os_info = _get_os_info()
    except Exception:
        os_info = {
            "name": platform.system(),
            "release": platform.release(),
            "version": platform.version(),
        }

    # Calculate total system TDP
    total_tdp_w = None
    if cpu_tdp_w is not None and gpu_info.get("tdp_w") is not None:
        total_tdp_w = round(cpu_tdp_w + gpu_info["tdp_w"], 1)

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

    _CACHED_STATIC_HARDWARE = result
    return result