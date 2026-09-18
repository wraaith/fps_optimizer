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
import collections
import csv
import os
import subprocess
import threading
import time
from typing import Any, Dict, Optional

import psutil
from dataclasses import dataclass
from enum import Enum
import numpy as np

from .gpu_monitor import GPUBackend, create_gpu_backend

class TelemetryState(Enum):
    WAITING_FOR_GAME = "No supported game detected"
    ATTACHING = "Connecting to game telemetry"
    COLLECTING_FRAMES = "Measuring FPS…"
    FPS_READY = "FPS: <measured value>"
    STALE = "FPS unavailable"
    ERROR = "Frame telemetry unavailable"

@dataclass
class TelemetryConfig:
    FPS_WINDOW_SECONDS: float = 2.0
    MIN_VALID_FRAMES: int = 10
    MIN_ELAPSED_SECONDS: float = 0.5
    STALE_TIMEOUT_SECONDS: float = 2.0

@dataclass
class GameProcessIdentity:
    game_id: str
    pid: int
    executable_name: str
    verified_executable_path: bool
    process_start_time: float
    session_id: str

class FrameTelemetryEngine:
    def __init__(self, config: TelemetryConfig = None):
        self.lock = threading.Lock()
        self.config = config or TelemetryConfig()
        self.identity: Optional[GameProcessIdentity] = None
        self.reset()
        
    def reset(self):
        with self.lock:
            self.identity = None
            
            # Use a deque to store (present_start, ms_between)
            self.frame_samples = collections.deque(maxlen=600)
            self.last_present_start = 0.0
            
            self.state = TelemetryState.WAITING_FOR_GAME
            self.fps = None
            self.p50 = None
            self.p95 = None
            self.p99 = None
            
    def _is_valid_identity(self, pid: int) -> bool:
        if self.identity is None or self.identity.pid != pid:
            return False
            
        # Verify the process is still alive and the start time hasn't changed (PID reuse)
        try:
            p = psutil.Process(pid)
            if not p.is_running():
                return False
            if p.create_time() != self.identity.process_start_time:
                return False
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            return False
            
        return True

    def set_target_game(self, game_id: str, executable: str, pid: int):
        with self.lock:
            try:
                p = psutil.Process(pid)
                create_time = p.create_time()
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                return # Can't bind to dead/inaccessible process
                
            if self.identity is None or self.identity.pid != pid or self.identity.process_start_time != create_time:
                self.identity = GameProcessIdentity(
                    game_id=game_id,
                    pid=pid,
                    executable_name=executable,
                    verified_executable_path=True,
                    process_start_time=create_time,
                    session_id=f"sess_{int(time.time())}_{pid}"
                )
                self.frame_samples.clear()
                self.last_present_start = 0.0
                self.fps = None
                self.p50 = self.p95 = self.p99 = None
                self.state = TelemetryState.ATTACHING

    def mark_game_exit(self):
        with self.lock:
            self.identity = None
            self.frame_samples.clear()
            self.fps = None
            self.p50 = self.p95 = self.p99 = None
            self.state = TelemetryState.WAITING_FOR_GAME

    def mark_error(self):
        with self.lock:
            self.frame_samples.clear()
            self.fps = None
            self.p50 = self.p95 = self.p99 = None
            self.state = TelemetryState.ERROR

    def process_frame(self, pid: int, executable: str, ms_between: float, present_start: float):
        with self.lock:
            if not self._is_valid_identity(pid):
                return # Discard: Not the target process, dead process, or PID reused
                
            if ms_between is None or np.isnan(ms_between) or np.isinf(ms_between) or ms_between <= 0:
                return # Discard: Invalid duration
                
            if present_start is None or np.isnan(present_start) or np.isinf(present_start):
                return # Discard: Invalid timestamp
                
            if present_start <= self.last_present_start:
                return # Discard: Duplicate or non-monotonic timestamp
                
            # Discontinuity check
            if present_start - self.last_present_start > self.config.FPS_WINDOW_SECONDS:
                self.frame_samples.clear()
                self.fps = None
                self.p50 = self.p95 = self.p99 = None
                self.state = TelemetryState.COLLECTING_FRAMES
                
            self.last_present_start = present_start
            
            current_time = time.time()
            self._prune_samples(current_time)
            
            self.frame_samples.append((present_start, ms_between))
            self._update_metrics(current_time)

    def _prune_samples(self, current_time: float):
        # We prune based on present_start relative to the latest present_start, 
        # but since we compare current_time we assume present_start is comparable to time.time().
        # Actually, PresentMon TimeInSeconds is system uptime or QPC based.
        # Since we use elapsed time between samples, let's prune based on the latest sample's timestamp
        if not self.frame_samples:
            return
            
        latest_ts = self.frame_samples[-1][0]
        while self.frame_samples and (latest_ts - self.frame_samples[0][0] > self.config.FPS_WINDOW_SECONDS):
            self.frame_samples.popleft()

    def _update_metrics(self, current_time: float):
        if not self.frame_samples:
            self.fps = None
            self.p50 = self.p95 = self.p99 = None
            if self.identity is not None:
                self.state = TelemetryState.STALE
            else:
                self.state = TelemetryState.WAITING_FOR_GAME
            return
            
        # We also need a freshness check relative to real wall clock time.
        # PresentMon events come in. If the last event came in > STALE_TIMEOUT_SECONDS ago, it's stale.
        # We don't have the exact wall-clock time of the frame, but we can track when we last processed a frame.
        # However, to be strict, if `current_time` (which is wall clock) advances too much since the last frame was processed, it's stale.
        # For simplicity, we just use the caller's periodic check in `get_state()` with `current_time` and a last_processed_wall_time.
        pass

    def get_state(self, current_wall_time: float = None, last_processed_wall_time: float = None) -> dict:
        with self.lock:
            if current_wall_time is None:
                current_wall_time = time.time()
                
            if self.identity is None:
                self.state = TelemetryState.WAITING_FOR_GAME
                self.fps = None
            elif self.state == TelemetryState.ERROR:
                self.fps = None
                self.p50 = self.p95 = self.p99 = None
            elif last_processed_wall_time is not None and (current_wall_time - last_processed_wall_time > self.config.STALE_TIMEOUT_SECONDS):
                self.state = TelemetryState.STALE
                self.fps = None
                self.p50 = self.p95 = self.p99 = None
            elif len(self.frame_samples) == 0:
                if self.state not in (TelemetryState.ATTACHING, TelemetryState.ERROR):
                    self.state = TelemetryState.COLLECTING_FRAMES
                self.fps = None
                self.p50 = self.p95 = self.p99 = None
            elif len(self.frame_samples) < self.config.MIN_VALID_FRAMES:
                self.state = TelemetryState.COLLECTING_FRAMES
                self.fps = None
                self.p50 = self.p95 = self.p99 = None
            else:
                latest_ts = self.frame_samples[-1][0]
                first_ts = self.frame_samples[0][0]
                elapsed = latest_ts - first_ts
                
                if elapsed < self.config.MIN_ELAPSED_SECONDS:
                    self.state = TelemetryState.COLLECTING_FRAMES
                    self.fps = None
                else:
                    self.fps = round(len(self.frame_samples) / elapsed, 1)
                    ms_values = [s[1] for s in self.frame_samples]
                    try:
                        self.p50 = round(float(np.percentile(ms_values, 50)), 2)
                        self.p95 = round(float(np.percentile(ms_values, 95)), 2)
                        self.p99 = round(float(np.percentile(ms_values, 99)), 2)
                    except Exception:
                        self.p50 = self.p95 = self.p99 = None
                    self.state = TelemetryState.FPS_READY
            
            fps_confidence = "unavailable"
            if self.state == TelemetryState.FPS_READY and self.fps is not None:
                fps_confidence = "measured"
                
            ui_text = self.state.value
            if fps_confidence == "measured":
                ui_text = f"FPS: {self.fps}"
                
            pid = self.identity.pid if self.identity else None
            executable = self.identity.executable_name if self.identity else None
            game_id = self.identity.game_id if self.identity else None
                
            return {
                "game_id": game_id,
                "pid": pid,
                "executable_name": executable,
                "executable_path_verified": True if pid else False,
                "frame_source": "PresentMon" if pid else None,
                "frame_source_status": self.state.name.lower(),
                "fps_state": self.state.name,
                "valid_frame_samples": len(self.frame_samples),
                "fps": self.fps,
                "frame_time_p50_ms": self.p50,
                "frame_time_p95_ms": self.p95,
                "frame_time_p99_ms": self.p99,
                "fps_confidence": fps_confidence,
                "reason": self.state.name,
                "ui_fps_text": ui_text
            }



# ── CPU temperature helpers ─────────────────────────────────────


_wmi_client = None
_wmi_failed = False
_wmi_temp = None
_wmi_lock = threading.Lock()
_wmi_check_started = False

def _update_wmi_temp_loop():
    global _wmi_client, _wmi_failed, _wmi_temp
    
    _com_inited = False
    try:
        import pythoncom
        pythoncom.CoInitialize()
        _com_inited = True
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
                
            time.sleep(4.0)  # 4s is plenty for temperature (was 2.0, saves CPU on low-end)
    except Exception:
        _wmi_failed = True
        _wmi_temp = None
    finally:
        _wmi_client = None
        if _com_inited:
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
    normalized_row: Dict[str, str],
    *possible_names: str,
) -> Optional[str]:
    """Return a CSV value using multiple possible column names.

    Expects *normalized_row* to already have normalised keys
    (via ``_normalise_header``).
    """
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


_shared_instance: Optional['MetricsCollector'] = None
_shared_lock = threading.Lock()

def get_shared_metrics_collector(target_process: Optional[str] = None) -> 'MetricsCollector':
    """Get or create the singleton SharedMetricsProvider."""
    global _shared_instance
    with _shared_lock:
        if _shared_instance is None:
            _shared_instance = MetricsCollector(target_process=target_process)
        elif target_process and not _shared_instance._target_process:
            _shared_instance._target_process = target_process.strip().lower()
        return _shared_instance

class MetricsCollector:
    """
    Collect hardware and performance metrics in background threads.
    Now acts as a SharedMetricsProvider using reference counting.
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
            "timestamp": 0.0,
        }

        self._gpu: Optional[GPUBackend] = None

        self._running = False
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None

        self._pm_process: Optional[subprocess.Popen] = None
        self._pm_thread: Optional[threading.Thread] = None
        self._pm_stop_event = threading.Event()

        self._current_cpu_w: Optional[float] = None
        self._current_gpu_w: Optional[float] = None

        self._telemetry_engine = FrameTelemetryEngine()
        self._last_processed_wall_time = 0.0
        
        self._presentmon_started = False
        
        self._consumers = 0

        self._target_process = (
            target_process
            or os.getenv("FPS_OVERLAY_TARGET_PROCESS")
            or ""
        ).strip().lower()

        atexit.register(self.stop)

    @property
    def snapshot(self) -> Dict[str, Any]:
        with self._lock:
            return dict(self._snapshot)

    def get_metrics(self) -> Dict[str, Any]:
        return self.snapshot

    def retain(self):
        """Add a consumer and start the collector if needed."""
        with self._lock:
            self._consumers += 1
            if self._consumers == 1:
                self._start_internal()
                
    def release(self):
        """Remove a consumer and stop the collector if empty."""
        with self._lock:
            if self._consumers > 0:
                self._consumers -= 1
            if self._consumers == 0:
                self._stop_internal()

    def start(self) -> None:
        """Legacy start() - acts as a retain."""
        self.retain()

    def stop(self) -> None:
        """Legacy stop() - forces stop regardless of consumers (e.g. at exit)."""
        with self._lock:
            self._consumers = 0
            self._stop_internal()

    def _start_internal(self) -> None:
        if self._running:
            return

        self._running = True
        self._stop_event.clear()
        self._pm_stop_event.clear()

        try:
            self._gpu = create_gpu_backend()
            gpu_name = self._gpu.get_name()
            self._snapshot["gpu_name"] = gpu_name
        except Exception:
            self._gpu = None

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

    def _stop_internal(self) -> None:
        was_running = self._running
        self._running = False
        self._stop_event.set()
        self._pm_stop_event.set()

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

    def _start_presentmon(self) -> None:
        if self._presentmon_started:
            return

        presentmon_path = get_presentmon_path()
        if not os.path.isfile(presentmon_path):
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
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            self._presentmon_started = True
            self._pm_thread = threading.Thread(
                target=self._read_presentmon_output,
                name="PresentMonReader",
                daemon=True,
            )
            self._pm_thread.start()
        except Exception:
            self._pm_process = None
            self._presentmon_started = False

    def _stop_presentmon(self) -> None:
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

    _IGNORED_APPS = None  # Loaded dynamically from config

    @classmethod
    def _get_ignored_apps(cls):
        if cls._IGNORED_APPS is None:
            try:
                from sentinel.game_detection_config import NON_GAME_BLACKLIST, SYSTEM_PROCESSES
                cls._IGNORED_APPS = NON_GAME_BLACKLIST | SYSTEM_PROCESSES
            except ImportError:
                cls._IGNORED_APPS = frozenset({
                    "dwm.exe", "explorer.exe", "unknown", "desktop window manager",
                    "python.exe", "pythonw.exe", "fps_optimizer.exe", "chrome.exe",
                    "msedge.exe", "firefox.exe", "brave.exe", "discord.exe",
                    "spotify.exe", "code.exe", "devenv.exe", "cmd.exe",
                    "powershell.exe", "pwsh.exe", "taskmgr.exe", "shellexperiencehost.exe",
                    "searchhost.exe", "startmenuexperiencehost.exe", "applicationframehost.exe",
                    "lockapp.exe", "notepad.exe", "calculator.exe", "slack.exe",
                    "teams.exe", "steamwebhelper.exe",
                })
        return cls._IGNORED_APPS

    def _is_target_application(self, application: str) -> bool:
        application = application.strip().lower()
        if not application or application in self._get_ignored_apps():
            return False
        if not self._target_process:
            return True
        return (
            application == self._target_process
            or os.path.basename(application) == self._target_process
        )
        
    def _find_pid_for_process(self, application: str) -> Optional[int]:
        if not application: return None
        for proc in psutil.process_iter(['pid', 'name']):
            try:
                if proc.info['name'].lower() == application.lower():
                    return proc.info['pid']
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                pass
        return None

    def _read_presentmon_output(self) -> None:
        process = self._pm_process
        if process is None or process.stdout is None:
            return

        try:
            csv_reader = csv.reader(
                line for line in process.stdout
                if line.strip() and not line.lstrip().startswith("//")
            )
            headers = None

            for fields in csv_reader:
                if self._pm_stop_event.is_set():
                    break

                if not fields:
                    continue

                cleaned_fields = [field.strip() for field in fields]

                if headers is None:
                    normalized_headers = {_normalise_header(f) for f in cleaned_fields}
                    if "application" in normalized_headers and any(c in normalized_headers for c in ("msbetweenpresents", "msbetweenpresent", "presentstart")):
                        headers = cleaned_fields
                    continue

                if len(cleaned_fields) < len(headers):
                    continue

                row = dict(zip(headers, cleaned_fields))
                norm_row = {_normalise_header(k): v.strip() for k, v in row.items() if k is not None}
                application = _find_column(norm_row, "Application", "ApplicationName", "ProcessName")
                pid_str = _find_column(norm_row, "ProcessId", "ProcessID")
                
                if not self._is_target_application(application or ""):
                    continue
                    
                pid = None
                try:
                    pid = int(pid_str) if pid_str else None
                except ValueError:
                    pass

                if pid is None:
                    continue
                    
                # Bind telemetry engine to this process
                current_state = self._telemetry_engine.get_state()
                if current_state["pid"] != pid:
                    self._telemetry_engine.set_target_game(
                        game_id=self._target_process or application or "Game",
                        executable=application or "Unknown.exe",
                        pid=pid
                    )

                ms_between_str = _find_column(norm_row, "MsBetweenPresents", "MsBetweenPresent")
                present_start_str = _find_column(norm_row, "PresentStartTime", "PresentStart", "TimeInSeconds")
                ms_until_render_complete_str = _find_column(norm_row, "MsUntilRenderComplete")
                ms_until_displayed_str = _find_column(norm_row, "MsUntilDisplayed")
                
                # Check for completely missing required fields
                if not ms_between_str or not present_start_str:
                    self._telemetry_engine.mark_error()
                    continue
                
                ms_between = _parse_float(ms_between_str)
                present_start = _parse_float(present_start_str)

                # Ensure values aren't parsed to null/malformed.
                if ms_between is not None and present_start is not None:
                    self._telemetry_engine.process_frame(
                        pid=pid,
                        executable=application,
                        ms_between=ms_between,
                        present_start=present_start
                    )
                    self._last_processed_wall_time = time.time()
                    
                    state = self._telemetry_engine.get_state(current_wall_time=time.time(), last_processed_wall_time=self._last_processed_wall_time)
                    if state["fps_confidence"] == "measured":
                        try:
                            from services.benchmark_logger import get_history_service, write_live_fps
                            hs = get_history_service()
                            if hs.is_session_active and hs.is_sentinel_running():
                                hs.record_fps_sample(state["fps"])
                            low_1pct = round(state["fps"] * 0.85, 1) # simple fallback
                            write_live_fps(state)
                        except Exception:
                            pass
                else:
                    self._telemetry_engine.mark_error()

                cpu_power = _find_column(norm_row, "CpuPowerW", "CPU Power (W)", "CpuPower", "CPU Power")
                parsed_cpu_power = _parse_float(cpu_power)
                if parsed_cpu_power is not None:
                    with self._lock:
                        self._current_cpu_w = round(parsed_cpu_power, 1)

                gpu_power = _find_column(norm_row, "GpuPowerW", "GPU Power (W)", "GpuPower", "GPU Power")
                parsed_gpu_power = _parse_float(gpu_power)
                if parsed_gpu_power is not None:
                    with self._lock:
                        self._current_gpu_w = round(parsed_gpu_power, 1)

        except Exception as error:
            pass

    def _loop(self) -> None:
        try:
            while not self._stop_event.is_set():
                data: Dict[str, Any] = {}

                try:
                    data["cpu_usage"] = psutil.cpu_percent(interval=None)
                except Exception:
                    data["cpu_usage"] = None

                try:
                    data["cpu_temp"] = get_cpu_temp()
                except Exception:
                    data["cpu_temp"] = None

                if self._gpu is not None:
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

                try:
                    data["ram_usage"] = psutil.virtual_memory().percent
                except Exception:
                    data["ram_usage"] = None

                try:
                    from services.benchmark_logger import read_live_fps
                    ipc_data = read_live_fps()
                    # We no longer read live fps backward into MetricsCollector here, 
                    # as FrameTelemetryEngine is the source of truth for the local instance.
                except Exception:
                    pass

                with self._lock:
                    telemetry_state = self._telemetry_engine.get_state(current_wall_time=time.time(), last_processed_wall_time=self._last_processed_wall_time)
                    data["fps"] = telemetry_state.get("ui_fps_text")
                    data["raw_fps"] = telemetry_state.get("fps")
                    data["telemetry"] = telemetry_state
                    data["cpu_power_w"] = self._current_cpu_w
                    data["gpu_power_w"] = self._current_gpu_w
                    data["timestamp"] = time.time()
                    self._snapshot.update(data)
                
                if self._stop_event.wait(self._interval):
                    break
        finally:
            pass
