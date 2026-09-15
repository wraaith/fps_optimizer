"""
Vendor-agnostic GPU monitoring.
Tries multiple backends in order:
  1. pynvml  (NVIDIA, no admin needed)
  2. nvidia-smi subprocess (NVIDIA fallback)
  3. WMI (any vendor, limited — no temp/usage on most systems)
"""

import subprocess
from abc import ABC, abstractmethod
from typing import Optional, Tuple


class GPUBackend(ABC):
    """Abstract base for GPU monitoring backends."""

    @abstractmethod
    def get_name(self) -> str:
        ...

    @abstractmethod
    def get_temperature(self) -> Optional[float]:
        ...

    @abstractmethod
    def get_usage_percent(self) -> Optional[float]:
        ...

    @abstractmethod
    def shutdown(self) -> None:
        ...


# ── NVIDIA: pynvml ──────────────────────────────────────────────

class NvmlBackend(GPUBackend):
    """Uses pynvml (nvidia-ml-py) — lightweight, no admin."""

    def __init__(self):
        import pynvml
        self._nv = pynvml
        self._nv.nvmlInit()
        self._handle = self._nv.nvmlDeviceGetHandleByIndex(0)
        self._name = self._nv.nvmlDeviceGetName(self._handle)
        if isinstance(self._name, bytes):
            self._name = self._name.decode()

    def get_name(self) -> str:
        return self._name

    def get_temperature(self) -> Optional[float]:
        try:
            return float(
                self._nv.nvmlDeviceGetTemperature(
                    self._handle, self._nv.NVML_TEMPERATURE_GPU
                )
            )
        except Exception:
            return None

    def get_usage_percent(self) -> Optional[float]:
        try:
            util = self._nv.nvmlDeviceGetUtilizationRates(self._handle)
            return float(util.gpu)
        except Exception:
            return None

    def shutdown(self) -> None:
        try:
            self._nv.nvmlShutdown()
        except Exception:
            pass


# ── NVIDIA: nvidia-smi subprocess fallback ──────────────────────

class NvidiaSmiBackend(GPUBackend):
    """Falls back to parsing nvidia-smi CLI output."""

    _CMD = [
        "nvidia-smi",
        "--query-gpu=name,temperature.gpu,utilization.gpu",
        "--format=csv,noheader,nounits",
    ]

    def __init__(self):
        import time
        self._time = time
        result = subprocess.run(
            self._CMD, capture_output=True, text=True, timeout=5,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        if result.returncode != 0:
            raise RuntimeError("nvidia-smi failed")
        parts = result.stdout.strip().split(", ")
        if len(parts) < 3:
            raise RuntimeError("unexpected nvidia-smi output")
        self._name = parts[0].strip()
        self._last_query_time = 0.0
        self._last_temp = None
        self._last_usage = None

    def _query(self) -> Tuple[Optional[float], Optional[float]]:
        now = self._time.time()
        if now - self._last_query_time < 0.9:
            return self._last_temp, self._last_usage

        try:
            result = subprocess.run(
                self._CMD, capture_output=True, text=True, timeout=5,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            parts = result.stdout.strip().split(", ")
            self._last_temp = float(parts[1]) if len(parts) > 1 else None
            self._last_usage = float(parts[2]) if len(parts) > 2 else None
            self._last_query_time = now
            return self._last_temp, self._last_usage
        except Exception:
            self._last_query_time = now
            return None, None

    def get_name(self) -> str:
        return self._name

    def get_temperature(self) -> Optional[float]:
        temp, _ = self._query()
        return temp

    def get_usage_percent(self) -> Optional[float]:
        _, usage = self._query()
        return usage

    def shutdown(self) -> None:
        pass


# ── WMI fallback (any vendor, limited) ──────────────────────────

class WmiBackend(GPUBackend):
    """Uses WMI — works with any vendor but usually can't get temp/usage."""

    def __init__(self):
        self._name = "Unknown GPU"
        # 1. Try Windows Registry (zero COM, zero crash, instant)
        try:
            import winreg
            reg_path = r"SYSTEM\CurrentControlSet\Control\Class\{4d36e968-e325-11ce-bfc1-08002be10318}"
            for idx in range(10):
                try:
                    with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, f"{reg_path}\\{idx:04d}") as sk:
                        desc, _ = winreg.QueryValueEx(sk, "DriverDesc")
                        desc_str = str(desc).strip()
                        if desc_str:
                            self._name = desc_str
                            desc_upper = desc_str.upper()
                            if not any(kw in desc_upper for kw in ("INTEL", "MICROSOFT BASIC", "VEGA GRAPHICS")):
                                return
                except Exception:
                    pass
            if self._name != "Unknown GPU":
                return
        except Exception:
            pass

        # 2. Fallback to WMI if registry had no adapters
        _com_inited = False
        try:
            import pythoncom
            pythoncom.CoInitialize()
            _com_inited = True
        except Exception:
            pass

        try:
            import wmi
            c = wmi.WMI()
            gpus = c.Win32_VideoController()
            if gpus:
                for gpu in gpus:
                    name = str(getattr(gpu, "Name", "") or "")
                    if name:
                        self._name = name
                        name_upper = name.upper()
                        if not any(kw in name_upper for kw in ("INTEL", "MICROSOFT BASIC", "VEGA GRAPHICS")):
                            break
            c = None
            gpus = None
        except Exception:
            pass
        finally:
            if _com_inited:
                try:
                    import pythoncom
                    pythoncom.CoUninitialize()
                except Exception:
                    pass

    def get_name(self) -> str:
        return self._name

    def get_temperature(self) -> Optional[float]:
        # Win32_VideoController doesn't expose temperature
        return None

    def get_usage_percent(self) -> Optional[float]:
        # Win32_VideoController doesn't expose utilization
        return None

    def shutdown(self) -> None:
        pass


# ── Dummy fallback (no GPU info at all) ─────────────────────────

class DummyBackend(GPUBackend):
    """Used when no real backend is available — prevents crashes."""

    def get_name(self) -> str:
        return "Unknown GPU"

    def get_temperature(self) -> Optional[float]:
        return None

    def get_usage_percent(self) -> Optional[float]:
        return None

    def shutdown(self) -> None:
        pass


# ── Factory ─────────────────────────────────────────────────────

def create_gpu_backend() -> GPUBackend:
    """Try backends in order; return the first that works.

    Never raises — returns DummyBackend as last resort.
    """
    # 1. pynvml
    try:
        return NvmlBackend()
    except Exception:
        pass

    # 2. nvidia-smi
    try:
        return NvidiaSmiBackend()
    except Exception:
        pass

    # 3. WMI
    try:
        return WmiBackend()
    except Exception:
        pass

    # 4. Dummy (never crashes)
    return DummyBackend()
