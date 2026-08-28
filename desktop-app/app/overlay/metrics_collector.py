"""
Background metrics collector.

Runs background workers that collect:

- CPU usage
- CPU temperature
- GPU name
- GPU usage
- GPU temperature
- RAM usage
- FPS through PresentMon
- CPU power through PresentMon, when available
- GPU power through PresentMon, when available

The latest values are available through ``snapshot`` or ``get_metrics()``.
"""

import atexit
import csv
import os
import subprocess
import threading
import time
from typing import Any, Dict, Optional

import psutil

from .gpu_monitor import GPUBackend, create_gpu_backend


# ── CPU temperature helpers ─────────────────────────────────────


_wmi_client = None
_wmi_failed = False
_wmi_temp = None
_wmi_lock = threading.Lock()
_wmi_check_started = False

def _update_wmi_temp_loop():
    global _wmi_client, _wmi_failed, _wmi_temp
    
    try:
        import pythoncom
        pythoncom.CoInitialize()
    except Exception:
        pass
        
    try:
        import wmi
        if _wmi_client is None:
            _wmi_client = wmi.WMI(namespace=r"root\wmi")
            
        while not _wmi_failed:
            sensors = _wmi_client.MSAcpi_ThermalZoneTemperature()
            if not sensors:
                _wmi_failed = True
                break
                
            kelvin_tenths = sensors[0].CurrentTemperature
            celsius = kelvin_tenths / 10.0 - 273.15
            
            if 0 < celsius < 150:
                _wmi_temp = round(celsius, 1)
            else:
                _wmi_temp = None
                
            time.sleep(2.0)
    except Exception:
        _wmi_failed = True
        _wmi_temp = None
        
    try:
        import pythoncom
        pythoncom.CoUninitialize()
    except Exception:
        pass

def _try_wmi_cpu_temp() -> Optional[float]:
    """Try reading CPU temperature through WMI (non-blocking)."""
    global _wmi_check_started, _wmi_failed, _wmi_temp

    if _wmi_failed:
        return None

    with _wmi_lock:
        if not _wmi_check_started:
            _wmi_check_started = True
            t = threading.Thread(
                target=_update_wmi_temp_loop,
                name="WMICpuTemp",
                daemon=True,
            )
            t.start()

    return _wmi_temp


def _try_psutil_cpu_temp() -> Optional[float]:
    """Try reading CPU temperature through psutil."""

    try:
        temperatures = psutil.sensors_temperatures()

        if temperatures:
            for entries in temperatures.values():
                if entries:
                    return round(entries[0].current, 1)

    except Exception:
        pass

    return None


def get_cpu_temp() -> Optional[float]:
    """Return the best available CPU temperature."""

    temperature = _try_psutil_cpu_temp()

    if temperature is not None:
        return temperature

    return _try_wmi_cpu_temp()


# ── PresentMon helpers ──────────────────────────────────────────


def get_presentmon_path() -> str:
    """Return the path to the bundled PresentMon executable."""

    app_dir = os.path.dirname(
        os.path.dirname(
            os.path.abspath(__file__)
        )
    )

    return os.path.join(
        app_dir,
        "bin",
        "PresentMon-2.5.1-x64.exe",
    )


def _normalise_header(value: str) -> str:
    """Normalize a PresentMon CSV header for reliable lookup."""

    return "".join(
        character.lower()
        for character in value.strip().lstrip("\ufeff")
        if character.isalnum()
    )


def _find_column(
    row: Dict[str, str],
    *possible_names: str,
) -> Optional[str]:
    """Return a CSV value using multiple possible column names."""

    normalized_row = {
        _normalise_header(key): value.strip()
        for key, value in row.items()
        if key is not None
    }

    for name in possible_names:
        value = normalized_row.get(_normalise_header(name))

        if value is not None and value != "":
            return value

    return None


def _parse_float(value: Optional[str]) -> Optional[float]:
    """Convert a CSV value to float safely."""

    if value is None:
        return None

    cleaned = (
        value.strip()
        .replace(",", "")
        .replace(" ms", "")
        .replace(" W", "")
        .replace("%", "")
    )

    if not cleaned or cleaned.lower() in {
        "na",
        "n/a",
        "null",
        "none",
        "-",
    }:
        return None

    try:
        return float(cleaned)
    except (TypeError, ValueError):
        return None


# ── Metrics collector ────────────────────────────────────────────


class MetricsCollector:
    """
    Collect hardware and performance metrics in background threads.

    Access the latest values with:

        collector.snapshot

    or:

        collector.get_metrics()
    """

    def __init__(
        self,
        interval: float = 1.0,
        target_process: Optional[str] = None,
    ):
        self._interval = max(0.1, float(interval))

        self._lock = threading.Lock()

        self._snapshot: Dict[str, Any] = {
            "cpu_usage": None,
            "cpu_temp": None,
            "gpu_name": None,
            "gpu_temp": None,
            "gpu_usage": None,
            "ram_usage": None,
            "fps": None,
            "cpu_power_w": None,
            "gpu_power_w": None,
        }

        self._gpu: Optional[GPUBackend] = None

        self._running = False
        self._thread: Optional[threading.Thread] = None

        self._pm_process: Optional[subprocess.Popen] = None
        self._pm_thread: Optional[threading.Thread] = None

        self._current_fps: Optional[float] = None
        self._current_cpu_w: Optional[float] = None
        self._current_gpu_w: Optional[float] = None

        self._presentmon_started = False

        # Optional process filter.
        #
        # Example:
        #   MetricsCollector(target_process="Cyberpunk2077.exe")
        #
        # It can also be set through:
        #   FPS_OVERLAY_TARGET_PROCESS=Cyberpunk2077.exe
        self._target_process = (
            target_process
            or os.getenv("FPS_OVERLAY_TARGET_PROCESS")
            or ""
        ).strip().lower()

        atexit.register(self.stop)

    # ── Public API ───────────────────────────────────────────────

    @property
    def snapshot(self) -> Dict[str, Any]:
        """Return a thread-safe copy of the latest metrics."""

        with self._lock:
            return dict(self._snapshot)

    def get_metrics(self) -> Dict[str, Any]:
        """Compatibility alias for ``snapshot``."""

        return self.snapshot

    def start(self) -> None:
        """Start hardware and PresentMon collection."""

        with self._lock:
            if self._running:
                return

            self._running = True

        # Initialize the GPU backend once.
        try:
            self._gpu = create_gpu_backend()

            gpu_name = self._gpu.get_name()

            with self._lock:
                self._snapshot["gpu_name"] = gpu_name

        except Exception:
            self._gpu = None

        # Prime psutil's non-blocking CPU usage measurement.
        try:
            psutil.cpu_percent(interval=None)
        except Exception:
            pass

        self._thread = threading.Thread(
            target=self._loop,
            name="MetricsCollector",
            daemon=True,
        )
        self._thread.start()

        self._start_presentmon()

    def stop(self) -> None:
        """Stop all collection workers and release resources."""

        with self._lock:
            was_running = self._running
            self._running = False

        if not was_running and self._pm_process is None:
            return

        self._stop_presentmon()

        if self._gpu is not None:
            try:
                self._gpu.shutdown()
            except Exception:
                pass

        if (
            self._thread is not None
            and self._thread.is_alive()
            and self._thread is not threading.current_thread()
        ):
            self._thread.join(timeout=2.0)

        self._thread = None

    # ── PresentMon process ──────────────────────────────────────

    def _start_presentmon(self) -> None:
        """Start PresentMon and begin reading its CSV output."""

        if self._presentmon_started:
            return

        presentmon_path = get_presentmon_path()

        if not os.path.isfile(presentmon_path):
            print(
                f"[Metrics] PresentMon not found at: "
                f"{presentmon_path}"
            )
            return

        try:
            self._pm_process = subprocess.Popen(
                [
                    presentmon_path,
                    "--output_stdout",
                    "--no_console_stats",
                    "--stop_existing_session",
                    "--v1_metrics",
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                stdin=subprocess.DEVNULL,
                text=True,
                universal_newlines=True,
                bufsize=1,
                creationflags=getattr(
                    subprocess,
                    "CREATE_NO_WINDOW",
                    0,
                ),
            )

            self._presentmon_started = True

            self._pm_thread = threading.Thread(
                target=self._read_presentmon_output,
                name="PresentMonReader",
                daemon=True,
            )
            self._pm_thread.start()

        except Exception as error:
            self._pm_process = None
            self._presentmon_started = False
            print(f"[Metrics] Failed to start PresentMon: {error}")

    def _stop_presentmon(self) -> None:
        """Stop PresentMon without killing unrelated instances."""

        process = self._pm_process
        self._pm_process = None
        self._presentmon_started = False

        if process is not None:
            try:
                if process.poll() is None:
                    process.terminate()
                    process.wait(timeout=1.5)
            except subprocess.TimeoutExpired:
                try:
                    process.kill()
                    process.wait(timeout=1.0)
                except Exception:
                    pass
            except Exception:
                pass

        reader = self._pm_thread

        if (
            reader is not None
            and reader.is_alive()
            and reader is not threading.current_thread()
        ):
            reader.join(timeout=2.0)

        self._pm_thread = None

    def _is_target_application(self, application: str) -> bool:
        """Return whether a PresentMon row belongs to the target app."""

        application = application.strip().lower()

        if not application:
            return False

        ignored_applications = {
            "dwm.exe",
            "explorer.exe",
            "unknown",
            "desktop window manager",
        }

        if application in ignored_applications:
            return False

        if not self._target_process:
            return True

        return (
            application == self._target_process
            or os.path.basename(application)
            == self._target_process
        )

    def _read_presentmon_output(self) -> None:
        """Read and parse PresentMon CSV output continuously."""

        process = self._pm_process

        if process is None or process.stdout is None:
            return

        try:
            csv_reader = csv.reader(
                line
                for line in process.stdout
                if line.strip()
                and not line.lstrip().startswith("//")
            )

            headers = None

            for fields in csv_reader:
                if not self._running:
                    break

                if not fields:
                    continue

                cleaned_fields = [
                    field.strip()
                    for field in fields
                ]

                # Ignore metadata or informational lines until the
                # actual CSV header appears.
                if headers is None:
                    normalized_headers = {
                        _normalise_header(field)
                        for field in cleaned_fields
                    }

                    has_application = (
                        "application" in normalized_headers
                    )

                    has_timing_column = any(
                        column in normalized_headers
                        for column in (
                            "msbetweenpresents",
                            "msbetweenpresent",
                            "presentstart",
                        )
                    )

                    if has_application and has_timing_column:
                        headers = cleaned_fields

                    continue

                if len(cleaned_fields) < len(headers):
                    continue

                row = dict(
                    zip(headers, cleaned_fields)
                )

                application = _find_column(
                    row,
                    "Application",
                    "ApplicationName",
                    "ProcessName",
                )

                if not self._is_target_application(
                    application or ""
                ):
                    continue

                # ── FPS ─────────────────────────────────────

                ms_between = _find_column(
                    row,
                    "MsBetweenPresents",
                    "MsBetweenPresent",
                )

                milliseconds = _parse_float(ms_between)

                if (
                    milliseconds is not None
                    and milliseconds > 0
                ):
                    fps = 1000.0 / milliseconds

                    with self._lock:
                        self._current_fps = round(fps, 1)

                # ── CPU power ───────────────────────────────

                cpu_power = _find_column(
                    row,
                    "CpuPowerW",
                    "CPU Power (W)",
                    "CpuPower",
                    "CPU Power",
                )

                parsed_cpu_power = _parse_float(cpu_power)

                if parsed_cpu_power is not None:
                    with self._lock:
                        self._current_cpu_w = round(
                            parsed_cpu_power,
                            1,
                        )

                # ── GPU power ───────────────────────────────

                gpu_power = _find_column(
                    row,
                    "GpuPowerW",
                    "GPU Power (W)",
                    "GpuPower",
                    "GPU Power",
                )

                parsed_gpu_power = _parse_float(gpu_power)

                if parsed_gpu_power is not None:
                    with self._lock:
                        self._current_gpu_w = round(
                            parsed_gpu_power,
                            1,
                        )

        except Exception as error:
            if self._running:
                print(
                    f"[Metrics] PresentMon read error: {error}"
                )

    # ── Hardware polling loop ──────────────────────────────────

    def _loop(self) -> None:
        """Poll hardware metrics until stopped."""

        while True:
            with self._lock:
                if not self._running:
                    break

            data: Dict[str, Any] = {}

            # CPU usage
            try:
                data["cpu_usage"] = psutil.cpu_percent(
                    interval=None
                )
            except Exception:
                data["cpu_usage"] = None

            # CPU temperature
            try:
                data["cpu_temp"] = get_cpu_temp()
            except Exception:
                data["cpu_temp"] = None

            # GPU metrics
            if self._gpu is not None:
                try:
                    data["gpu_name"] = self._gpu.get_name()
                except Exception:
                    data["gpu_name"] = None

                try:
                    data["gpu_temp"] = (
                        self._gpu.get_temperature()
                    )
                except Exception:
                    data["gpu_temp"] = None

                try:
                    data["gpu_usage"] = (
                        self._gpu.get_usage_percent()
                    )
                except Exception:
                    data["gpu_usage"] = None

            else:
                data["gpu_name"] = None
                data["gpu_temp"] = None
                data["gpu_usage"] = None

            # RAM usage
            try:
                data["ram_usage"] = (
                    psutil.virtual_memory().percent
                )
            except Exception:
                data["ram_usage"] = None

            # PresentMon values
            with self._lock:
                data["fps"] = self._current_fps
                data["cpu_power_w"] = self._current_cpu_w
                data["gpu_power_w"] = self._current_gpu_w

                self._snapshot.update(data)

                running = self._running

            if not running:
                break

            time.sleep(self._interval)
