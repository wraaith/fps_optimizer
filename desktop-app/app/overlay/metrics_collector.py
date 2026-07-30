"""
Background metrics collector.
Runs a daemon thread that polls CPU / GPU / FPS data every ~1 s and
stores the latest values in a thread-safe dict.
"""

import ctypes
import ctypes.wintypes as wt
import platform
import threading
import time
from typing import Any, Dict, Optional

import psutil

from .gpu_monitor import GPUBackend, create_gpu_backend


# ── CPU temperature helpers (Windows) ───────────────────────────

def _try_wmi_cpu_temp() -> Optional[float]:
    """Try reading CPU temp via WMI (needs admin on most systems)."""
    try:
        import wmi
        w = wmi.WMI(namespace=r"root\wmi")
        sensors = w.MSAcpi_ThermalZoneTemperature()
        if sensors:
            # Value is in tenths of Kelvin
            kelvin_tenths = sensors[0].CurrentTemperature
            celsius = kelvin_tenths / 10.0 - 273.15
            if 0 < celsius < 150:  # sanity check
                return round(celsius, 1)
    except Exception:
        pass
    return None


def _try_psutil_cpu_temp() -> Optional[float]:
    """Try psutil (works on Linux/macOS, not Windows usually)."""
    try:
        temps = psutil.sensors_temperatures()
        if temps:
            for name, entries in temps.items():
                if entries:
                    return round(entries[0].current, 1)
    except Exception:
        pass
    return None


def get_cpu_temp() -> Optional[float]:
    """Best-effort CPU temperature."""
    temp = _try_psutil_cpu_temp()
    if temp is not None:
        return temp
    return _try_wmi_cpu_temp()


# ── DWM-based display FPS ──────────────────────────────────────

class _DWM_TIMING_INFO(ctypes.Structure):
    """Partial DWM_TIMING_INFO — we only need the first few fields."""
    _fields_ = [
        ("cbSize", ctypes.c_uint32),
        ("rateRefreshNumerator", ctypes.c_uint32),
        ("rateRefreshDenominator", ctypes.c_uint32),
        ("qpcRefreshPeriod", ctypes.c_uint64),
        ("rateComposeNumerator", ctypes.c_uint32),
        ("rateComposeDenominator", ctypes.c_uint32),
        ("qpcVBlank", ctypes.c_uint64),
        ("cRefresh", ctypes.c_uint64),
        ("cDXRefresh", ctypes.c_uint32),
        ("qpcCompose", ctypes.c_uint64),
        ("cFrame", ctypes.c_uint64),
        ("cDXPresent", ctypes.c_uint32),
        ("cRefreshFrame", ctypes.c_uint64),
        ("cFrameSubmitted", ctypes.c_uint64),
        ("cDXPresentSubmitted", ctypes.c_uint32),
        ("cFrameConfirmed", ctypes.c_uint64),
        ("cDXPresentConfirmed", ctypes.c_uint32),
        ("cRefreshConfirmed", ctypes.c_uint64),
        ("cDXRefreshConfirmed", ctypes.c_uint32),
        ("cFramesLate", ctypes.c_uint64),
        ("cFramesOutstanding", ctypes.c_uint32),
        ("cFrameDisplayed", ctypes.c_uint64),
    ]


def _get_dwm_fps() -> Optional[float]:
    """
    Read the DWM composition rate.
    On VRR / G-Sync / FreeSync monitors this tracks the actual display
    output rate.  On fixed-rate monitors it returns the monitor Hz.
    """
    try:
        dwmapi = ctypes.windll.dwmapi
        info = _DWM_TIMING_INFO()
        info.cbSize = ctypes.sizeof(info)
        hr = dwmapi.DwmGetCompositionTimingInfo(None, ctypes.byref(info))
        if hr == 0 and info.rateComposeNumerator and info.rateComposeDenominator:
            return round(info.rateComposeNumerator / info.rateComposeDenominator, 1)
    except Exception:
        pass
    return None


# ── Collector thread ────────────────────────────────────────────

class MetricsCollector:
    """
    Polls hardware metrics in a background daemon thread.

    Access latest snapshot via ``collector.snapshot`` (dict).
    """

    def __init__(self, interval: float = 1.0):
        self._interval = interval
        self._lock = threading.Lock()
        self._snapshot: Dict[str, Any] = {
            "cpu_usage": None,
            "cpu_temp": None,
            "gpu_name": None,
            "gpu_temp": None,
            "gpu_usage": None,
            "fps": None,
        }
        self._gpu: Optional[GPUBackend] = None
        self._running = False
        self._thread: Optional[threading.Thread] = None

    # ── public API ──────────────────────────────────────────────

    @property
    def snapshot(self) -> Dict[str, Any]:
        with self._lock:
            return dict(self._snapshot)

    def start(self) -> None:
        if self._running:
            return
        self._running = True

        # Init GPU backend (once, on main thread to surface errors early)
        try:
            self._gpu = create_gpu_backend()
            self._snapshot["gpu_name"] = self._gpu.get_name()
        except Exception:
            self._gpu = None

        # Kick off a non-blocking cpu_percent baseline measurement
        try:
            psutil.cpu_percent(interval=None)
        except Exception:
            pass

        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._running = False
        if self._gpu:
            try:
                self._gpu.shutdown()
            except Exception:
                pass

    # ── internal loop ───────────────────────────────────────────

    def _loop(self) -> None:
        while self._running:
            data: Dict[str, Any] = {}

            # CPU
            try:
                data["cpu_usage"] = psutil.cpu_percent(interval=None)
            except Exception:
                data["cpu_usage"] = None

            try:
                data["cpu_temp"] = get_cpu_temp()
            except Exception:
                data["cpu_temp"] = None

            # GPU
            if self._gpu:
                try:
                    data["gpu_name"] = self._gpu.get_name()
                except Exception:
                    data["gpu_name"] = None
                try:
                    data["gpu_temp"] = self._gpu.get_temperature()
                except Exception:
                    data["gpu_temp"] = None
                try:
                    data["gpu_usage"] = self._gpu.get_usage_percent()
                except Exception:
                    data["gpu_usage"] = None
            else:
                data["gpu_name"] = None
                data["gpu_temp"] = None
                data["gpu_usage"] = None

            # FPS (DWM display rate)
            try:
                data["fps"] = _get_dwm_fps()
            except Exception:
                data["fps"] = None

            with self._lock:
                self._snapshot.update(data)

            time.sleep(self._interval)
