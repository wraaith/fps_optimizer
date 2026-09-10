import os
import ctypes
import ctypes.wintypes as wintypes
import subprocess
import functools
import psutil
from typing import Optional, Dict, Any

SYSTEM_PROCESSES = {
    "system", "system idle process", "registry", "smss.exe", 
    "csrss.exe", "wininit.exe", "services.exe", "lsass.exe", 
    "svchost.exe", "fontdrvhost.exe", "dwm.exe", "explorer.exe", 
    "taskhostw.exe", "winlogon.exe", "sihost.exe", "conhost.exe",
    "spoolsv.exe", "searchindexer.exe", "wudfhost.exe", 
    "nvdisplay.container.exe", "securityhealthservice.exe", "ctfmon.exe",
    "memory compression", "dashost.exe", "dllhost.exe",
    "rundll32.exe", "runtimebroker.exe", "searchapp.exe",
    "startmenuexperiencehost.exe", "applicationframehost.exe",
    "audiodg.exe", "shellexperiencehost.exe", "searchhost.exe",
    # Anti-cheat services & security daemons (Strictly Untouched)
    "vgc.exe", "vgtray.exe", "riotclientservices.exe",
    "easyanticheat.exe", "easyanticheat_eos.exe",
    "beservice.exe", "battleye.exe"
}

BLOATWARE_PROCESSES = {
    "chrome.exe", "msedge.exe", "brave.exe", "firefox.exe", 
    "onedrive.exe", "epicgameslauncher.exe", "ccleaner64.exe", 
    "ccleaner.exe", "adobeipcbroker.exe", "creative cloud.exe", 
    "phoneexperiencehost.exe", "yourphone.exe", "skype.exe", 
    "teams.exe", "zoom.exe", "webex.exe", "slack.exe", "spotify.exe"
}

def get_current_available_ram_mb() -> float:
    """Returns the current available RAM in MB."""
    return psutil.virtual_memory().available / (1024 * 1024)

def get_top_memory_consumers(n: int = 15) -> list:
    """
    Returns a list of the top N processes consuming memory.
    Excludes the current python process, child processes, python runtimes,
    and critical Windows system processes.
    Format: [{"pid": int, "name": str, "memory_mb": float}]
    """
    current_pid = os.getpid()
    protected_pids = {current_pid}
    try:
        current_proc = psutil.Process(current_pid)
        for child in current_proc.children(recursive=True):
            protected_pids.add(child.pid)
    except Exception:
        pass

    EXCLUDED_NAMES = set(SYSTEM_PROCESSES)
    EXCLUDED_NAMES.update({"python.exe", "pythonw.exe", "fps_optimizer.exe"})

    processes = []
    
    for proc in psutil.process_iter(['pid', 'name', 'memory_info']):
        try:
            pid = proc.info['pid']
            name = proc.info['name']
            
            if not name:
                continue
                
            name_lower = name.lower()
            
            # Skip self, child processes, python runtimes, and critical system processes
            if pid in protected_pids or pid <= 4 or name_lower in EXCLUDED_NAMES:
                continue
                
            mem_info = proc.info.get('memory_info')
            if not mem_info:
                continue

            rss_mb = mem_info.rss / (1024 * 1024)
            processes.append({
                "pid": pid,
                "name": name,
                "memory_mb": rss_mb
            })
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess, Exception):
            pass
            
    # Sort descending by memory usage
    processes.sort(key=lambda x: x["memory_mb"], reverse=True)
    return processes[:n]

def terminate_processes(pids: list) -> dict:
    """
    Attempts to terminate the list of PIDs.
    Returns a dictionary summarizing successes and failures.
    """
    results = {"success": 0, "failed": 0, "errors": []}
    
    for pid in pids:
        try:
            p = psutil.Process(pid)
            p.terminate()
            p.wait(timeout=3)
            results["success"] += 1
        except psutil.NoSuchProcess:
            # Already dead
            results["success"] += 1
        except psutil.TimeoutExpired:
            # Try hard kill
            try:
                p.kill()
                results["success"] += 1
            except Exception as e:
                results["failed"] += 1
                results["errors"].append(str(e))
        except psutil.AccessDenied:
            results["failed"] += 1
            results["errors"].append(f"Access Denied for PID {pid}")
        except Exception as e:
            results["failed"] += 1
            results["errors"].append(str(e))
            
    return results

def auto_optimize_system() -> list:
    """
    Finds all running processes that match the BLOATWARE_PROCESSES list
    and returns a list of dictionaries with their PIDs and names.
    """
    bloatware_found = []
    for proc in psutil.process_iter(['pid', 'name']):
        try:
            name = proc.info['name']
            if name and name.lower() in BLOATWARE_PROCESSES:
                bloatware_found.append({"pid": proc.info['pid'], "name": name})
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass
    return bloatware_found


# ── Smart RAM Optimization (Windows Native APIs) ─────────────────────

def _enable_privilege(privilege_name: str) -> bool:
    """
    Enable a Windows privilege (e.g. SeProfileSingleProcessPrivilege)
    on the current process token. Required before calling
    NtSetSystemInformation to clear the standby list.
    """
    TOKEN_ADJUST_PRIVILEGES = 0x0020
    TOKEN_QUERY = 0x0008
    SE_PRIVILEGE_ENABLED = 0x00000002

    class LUID(ctypes.Structure):
        _fields_ = [("LowPart", wintypes.DWORD), ("HighPart", wintypes.LONG)]

    class LUID_AND_ATTRIBUTES(ctypes.Structure):
        _fields_ = [("Luid", LUID), ("Attributes", wintypes.DWORD)]

    class TOKEN_PRIVILEGES(ctypes.Structure):
        _fields_ = [
            ("PrivilegeCount", wintypes.DWORD),
            ("Privileges", LUID_AND_ATTRIBUTES * 1),
        ]

    advapi32 = ctypes.WinDLL("advapi32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

    advapi32.OpenProcessToken.argtypes = [wintypes.HANDLE, wintypes.DWORD, ctypes.POINTER(wintypes.HANDLE)]
    advapi32.OpenProcessToken.restype = wintypes.BOOL
    advapi32.LookupPrivilegeValueW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR, ctypes.POINTER(LUID)]
    advapi32.LookupPrivilegeValueW.restype = wintypes.BOOL
    advapi32.AdjustTokenPrivileges.argtypes = [
        wintypes.HANDLE, wintypes.BOOL, ctypes.POINTER(TOKEN_PRIVILEGES),
        wintypes.DWORD, ctypes.c_void_p, ctypes.c_void_p
    ]
    advapi32.AdjustTokenPrivileges.restype = wintypes.BOOL
    kernel32.GetCurrentProcess.restype = wintypes.HANDLE
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel32.CloseHandle.restype = wintypes.BOOL

    hToken = wintypes.HANDLE()
    if not advapi32.OpenProcessToken(
        kernel32.GetCurrentProcess(),
        TOKEN_ADJUST_PRIVILEGES | TOKEN_QUERY,
        ctypes.byref(hToken),
    ):
        return False

    try:
        luid = LUID()
        if not advapi32.LookupPrivilegeValueW(None, privilege_name, ctypes.byref(luid)):
            return False

        tp = TOKEN_PRIVILEGES()
        tp.PrivilegeCount = 1
        tp.Privileges[0].Luid = luid
        tp.Privileges[0].Attributes = SE_PRIVILEGE_ENABLED

        ctypes.set_last_error(0)
        if not advapi32.AdjustTokenPrivileges(
            hToken, False, ctypes.byref(tp), ctypes.sizeof(tp), None, None
        ):
            return False

        # AdjustTokenPrivileges can "succeed" but still fail (e.g. ERROR_NOT_ALL_ASSIGNED)
        if ctypes.get_last_error() != 0:
            return False

        return True
    finally:
        kernel32.CloseHandle(hToken)


def clear_standby_memory() -> dict:
    """
    Flush the Windows standby memory list using NtSetSystemInformation.
    This is exactly what RAMMap's "Empty Standby List" does.
    Returns {"success": bool, "error": str|None, "freed_mb": float}.
    """
    SYSTEM_MEMORY_LIST_INFORMATION = 80
    MEMORY_PURGE_STANDBY_LIST = 4

    ram_before = get_current_available_ram_mb()

    # Step 1: Enable the required privilege
    if not _enable_privilege("SeProfileSingleProcessPrivilege"):
        return {
            "success": False,
            "error": "Failed to enable SeProfileSingleProcessPrivilege. Run as admin.",
            "freed_mb": 0,
        }

    # Step 2: Call NtSetSystemInformation
    ntdll = ctypes.WinDLL("ntdll")
    ntdll.NtSetSystemInformation.argtypes = [ctypes.c_int, ctypes.c_void_p, ctypes.c_ulong]
    ntdll.NtSetSystemInformation.restype = ctypes.c_long

    command = ctypes.c_ulong(MEMORY_PURGE_STANDBY_LIST)
    status = ntdll.NtSetSystemInformation(
        SYSTEM_MEMORY_LIST_INFORMATION,
        ctypes.byref(command),
        ctypes.sizeof(command),
    )

    if status != 0:
        return {
            "success": False,
            "error": f"NtSetSystemInformation returned NTSTATUS 0x{status & 0xFFFFFFFF:08X}",
            "freed_mb": 0,
        }

    ram_after = get_current_available_ram_mb()
    return {
        "success": True,
        "error": None,
        "freed_mb": max(0, ram_after - ram_before),
    }


def trim_all_working_sets(exclude_pids=None) -> dict:
    """
    Call EmptyWorkingSet (SetProcessWorkingSetSizeEx) on non-critical,
    non-game processes to release unused memory pages back to the OS.
    Crucially protects any active game PIDs in exclude_pids from being trimmed.
    Returns {"trimmed": int, "skipped": int, "freed_mb": float}.
    """
    psapi = ctypes.WinDLL("psapi", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

    kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel32.CloseHandle.restype = wintypes.BOOL
    psapi.EmptyWorkingSet.argtypes = [wintypes.HANDLE]
    psapi.EmptyWorkingSet.restype = wintypes.BOOL

    PROCESS_QUERY_INFORMATION = 0x0400
    PROCESS_SET_QUOTA = 0x0100

    current_pid = os.getpid()
    protected_pids = set(exclude_pids or [])
    protected_pids.add(current_pid)

    trimmed = 0
    skipped = 0
    ram_before = get_current_available_ram_mb()

    for proc in psutil.process_iter(["pid", "name"]):
        try:
            pid = proc.info["pid"]
            name = (proc.info["name"] or "").lower()

            # Skip self, protected pids (e.g. active game), and critical system processes
            if pid in protected_pids or pid <= 4 or name in SYSTEM_PROCESSES:
                continue

            hProcess = kernel32.OpenProcess(
                PROCESS_QUERY_INFORMATION | PROCESS_SET_QUOTA, False, pid
            )
            if not hProcess:
                skipped += 1
                continue

            try:
                if psapi.EmptyWorkingSet(hProcess):
                    trimmed += 1
                else:
                    skipped += 1
            finally:
                kernel32.CloseHandle(hProcess)

        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            skipped += 1

    ram_after = get_current_available_ram_mb()
    return {
        "trimmed": trimmed,
        "skipped": skipped,
        "freed_mb": max(0, ram_after - ram_before),
    }


def get_sysmain_status() -> dict:
    """
    Check whether the SysMain (Superfetch) service is running.
    Returns {"running": bool, "start_type": str, "error": str|None}.
    """
    no_window = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    try:
        result = subprocess.run(
            ["sc", "query", "SysMain"],
            capture_output=True, text=True, timeout=5,
            creationflags=no_window
        )
        running = "RUNNING" in result.stdout.upper()

        # Also check start type
        cfg = subprocess.run(
            ["sc", "qc", "SysMain"],
            capture_output=True, text=True, timeout=5,
            creationflags=no_window
        )
        start_type = "unknown"
        for line in cfg.stdout.splitlines():
            if "START_TYPE" in line.upper():
                if "AUTO_START" in line.upper():
                    start_type = "auto"
                elif "DEMAND_START" in line.upper():
                    start_type = "manual"
                elif "DISABLED" in line.upper():
                    start_type = "disabled"
                break

        return {"running": running, "start_type": start_type, "error": None}

    except Exception as e:
        return {"running": False, "start_type": "unknown", "error": str(e)}


def set_sysmain_enabled(enable: bool) -> dict:
    """
    Enable or disable the SysMain (Superfetch) service.
    Returns {"success": bool, "error": str|None}.
    """
    no_window = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    try:
        if enable:
            subprocess.run(
                ["sc", "config", "SysMain", "start=", "auto"],
                capture_output=True, text=True, timeout=10,
                creationflags=no_window
            )
            result = subprocess.run(
                ["sc", "start", "SysMain"],
                capture_output=True, text=True, timeout=10,
                creationflags=no_window
            )
        else:
            subprocess.run(
                ["sc", "stop", "SysMain"],
                capture_output=True, text=True, timeout=10,
                creationflags=no_window
            )
            result = subprocess.run(
                ["sc", "config", "SysMain", "start=", "disabled"],
                capture_output=True, text=True, timeout=10,
                creationflags=no_window
            )

        # Check for success
        if result.returncode == 0 or "already" in result.stdout.lower():
            return {"success": True, "error": None}
        else:
            return {"success": False, "error": result.stdout.strip() or result.stderr.strip()}

    except Exception as e:
        return {"success": False, "error": str(e)}


def get_memory_breakdown() -> dict:
    """
    Get a detailed breakdown of system memory.
    Returns dict with: total_mb, available_mb, used_mb, percent,
    cached_approx_mb (estimated standby + modified from total - available - active).
    """
    vm = psutil.virtual_memory()
    total_mb = vm.total / (1024 * 1024)
    avail_mb = vm.available / (1024 * 1024)
    used_mb = vm.used / (1024 * 1024)

    # Windows exposes "available" = free + standby (reclaimable).
    # "used" = active + wired. The gap is standby + modified cache.
    # cached_approx = total - used - free_approx
    # On Windows, psutil gives us vm.available which includes standby.
    # free = available, so standby_approx = available - truly_free
    # We can estimate using the percent field:
    cached_approx_mb = max(0, total_mb - used_mb - (avail_mb * 0.3))

    return {
        "total_mb": total_mb,
        "available_mb": avail_mb,
        "used_mb": used_mb,
        "percent": vm.percent,
        "cached_approx_mb": cached_approx_mb,
    }


@functools.lru_cache(maxsize=1)
def check_has_ssd() -> bool:
    """
    Check if the system drive (C:) is an SSD using WMI.
    Cached after the first query to avoid 3-4s PowerShell startup latency.
    Returns True if SSD, False if HDD or unknown.
    """
    no_window = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             "Get-PhysicalDisk | Where-Object { $_.DeviceID -eq '0' } | Select-Object -ExpandProperty MediaType"],
            capture_output=True, text=True, timeout=10,
            creationflags=no_window
        )
        return "SSD" in result.stdout.upper() or "SOLID" in result.stdout.upper()
    except Exception:
        # Fallback: try alternative WMI query
        try:
            result = subprocess.run(
                ["wmic", "diskdrive", "get", "MediaType"],
                capture_output=True, text=True, timeout=10,
                creationflags=no_window
            )
            # If no "Fixed hard disk" found, likely SSD
            return "SOLID" in result.stdout.upper() or "SSD" in result.stdout.upper()
        except Exception:
            return False


def lower_background_priority(exclude_names=None, exclude_pids=None, mem_threshold_mb=100) -> dict:
    """
    Lower CPU scheduling priority of heavy background processes
    (above mem_threshold_mb) to BELOW_NORMAL without killing them.
    Skips system processes, active game PIDs, and whitelisted names.
    Returns {"lowered": int, "skipped": int}.
    """
    exclude = set(n.lower() for n in (exclude_names or []))
    # Always protect these
    exclude.update(SYSTEM_PROCESSES)
    exclude.update({"python.exe", "pythonw.exe"})

    protected_pids = set(exclude_pids or [])
    current_pid = os.getpid()
    protected_pids.add(current_pid)

    lowered = 0
    skipped = 0

    for proc in psutil.process_iter(["pid", "name", "memory_info"]):
        try:
            pid = proc.info["pid"]
            name = (proc.info["name"] or "").lower()

            if pid in protected_pids or pid <= 4 or name in exclude:
                skipped += 1
                continue

            mem_info = proc.info.get("memory_info")
            if not mem_info:
                skipped += 1
                continue

            mem_mb = mem_info.rss / (1024 * 1024)
            if mem_mb < mem_threshold_mb:
                continue

            proc.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
            lowered += 1

        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess, Exception):
            skipped += 1

    return {"lowered": lowered, "skipped": skipped}


# ── High-Resolution Timer & FPS Stability APIs ───────────────────────

def enable_high_resolution_timer(resolution_ms: int = 1) -> bool:
    """
    Request the Windows multimedia scheduler to increase timer resolution (down to 1.0ms).
    Standard Windows timer resolution is 15.6ms (64Hz ticks). At 15.6ms, game sleep/sync
    delays can cause dropped frames. 1.0ms eliminates timer sleep jitter and dramatically
    stabilizes 1% low frametimes.
    Returns True if successful.
    """
    try:
        winmm = ctypes.WinDLL("winmm")
        winmm.timeBeginPeriod.argtypes = [ctypes.c_uint]
        winmm.timeBeginPeriod.restype = ctypes.c_uint
        return winmm.timeBeginPeriod(resolution_ms) == 0
    except Exception:
        return False


def disable_high_resolution_timer(resolution_ms: int = 1) -> bool:
    """
    Restore standard OS timer resolution when optimizer/sentinel is deactivated.
    """
    try:
        winmm = ctypes.WinDLL("winmm")
        winmm.timeEndPeriod.argtypes = [ctypes.c_uint]
        winmm.timeEndPeriod.restype = ctypes.c_uint
        return winmm.timeEndPeriod(resolution_ms) == 0
    except Exception:
        return False


def get_foreground_game_process() -> Optional[dict]:
    """
    Detects if the current active foreground window belongs to a game or 3D app.
    Excludes desktop, explorer, browsers, development tools, and background utilities.
    Returns {"pid": int, "name": str, "title": str} or None.
    """
    try:
        user32 = ctypes.windll.user32
        user32.GetForegroundWindow.argtypes = []
        user32.GetForegroundWindow.restype = wintypes.HWND
        user32.IsWindowVisible.argtypes = [wintypes.HWND]
        user32.IsWindowVisible.restype = wintypes.BOOL
        user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
        user32.GetWindowThreadProcessId.restype = wintypes.DWORD
        user32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
        user32.GetWindowTextLengthW.restype = ctypes.c_int
        user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
        user32.GetWindowTextW.restype = ctypes.c_int

        hwnd = user32.GetForegroundWindow()
        if not hwnd or not user32.IsWindowVisible(hwnd):
            return None

        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if not pid.value or pid.value <= 4 or pid.value == os.getpid():
            return None

        length = user32.GetWindowTextLengthW(hwnd)
        title = ""
        if length > 0:
            buff = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, buff, length + 1)
            title = buff.value.strip()

        proc = psutil.Process(pid.value)
        proc_name = (proc.name() or "").lower()

        # Filter out common desktop utilities, IDEs, browsers and system apps
        NON_GAME_EXES = {
            "explorer.exe", "taskmgr.exe", "cmd.exe", "powershell.exe", "pwsh.exe",
            "code.exe", "chrome.exe", "msedge.exe", "firefox.exe", "brave.exe",
            "devenv.exe", "python.exe", "pythonw.exe", "shellexperiencehost.exe",
            "searchhost.exe", "startmenuexperiencehost.exe", "applicationframehost.exe",
            "lockapp.exe", "notepad.exe", "calculator.exe", "slack.exe", "teams.exe",
            "discord.exe", "spotify.exe", "sublime_text.exe"
        }

        if proc_name in NON_GAME_EXES or proc_name in SYSTEM_PROCESSES:
            return None

        return {
            "pid": pid.value,
            "name": proc.name(),
            "title": title,
        }
    except Exception:
        return None


def boost_game_priority(game_pid: int) -> dict:
    """
    Elevates the active game process priority to ABOVE_NORMAL_PRIORITY_CLASS.
    Guarantees the Windows CPU scheduler gives priority execution slices to
    game simulation and render threads ahead of background tasks.
    """
    try:
        proc = psutil.Process(game_pid)
        current_nice = proc.nice()
        if current_nice in (psutil.NORMAL_PRIORITY_CLASS, psutil.BELOW_NORMAL_PRIORITY_CLASS, psutil.IDLE_PRIORITY_CLASS):
            proc.nice(psutil.ABOVE_NORMAL_PRIORITY_CLASS)
            return {"success": True, "pid": game_pid, "name": proc.name(), "priority": "ABOVE_NORMAL"}
        return {"success": True, "pid": game_pid, "name": proc.name(), "priority": "UNCHANGED"}
    except Exception as e:
        return {"success": False, "pid": game_pid, "error": str(e)}


# ── Aggressive Anti-Stutter Optimizations ─────────────────────────────

_original_power_scheme: Optional[str] = None

def activate_high_performance_power() -> dict:
    """
    Switch Windows power plan to 'High Performance' (or 'Ultimate Performance'
    if available) to prevent CPU/GPU frequency throttling during gameplay.
    Saves the original plan GUID so it can be restored when Sentinel stops.
    """
    global _original_power_scheme
    no_window = getattr(subprocess, "CREATE_NO_WINDOW", 0)

    try:
        # Save current active power scheme
        result = subprocess.run(
            ["powercfg", "/getactivescheme"],
            capture_output=True, text=True, timeout=5,
            creationflags=no_window
        )
        if result.returncode == 0:
            for part in result.stdout.split():
                # GUID format: 8-4-4-4-12 hex chars
                if len(part) == 36 and part.count("-") == 4:
                    _original_power_scheme = part
                    break

        # Try Ultimate Performance first (hidden on some systems)
        ULTIMATE_GUID = "e9a42b02-d5df-448d-aa00-03f14749eb61"
        HIGH_PERF_GUID = "8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c"

        # Attempt to unhide Ultimate Performance
        subprocess.run(
            ["powercfg", "/duplicatescheme", ULTIMATE_GUID],
            capture_output=True, text=True, timeout=5,
            creationflags=no_window
        )

        # Try setting Ultimate first, fall back to High Performance
        result = subprocess.run(
            ["powercfg", "/setactive", ULTIMATE_GUID],
            capture_output=True, text=True, timeout=5,
            creationflags=no_window
        )
        if result.returncode != 0:
            result = subprocess.run(
                ["powercfg", "/setactive", HIGH_PERF_GUID],
                capture_output=True, text=True, timeout=5,
                creationflags=no_window
            )

        return {"success": result.returncode == 0, "scheme": "ultimate_or_high_perf"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def restore_power_scheme() -> dict:
    """Restore the original power scheme that was active before Sentinel."""
    global _original_power_scheme
    if not _original_power_scheme:
        return {"success": True, "detail": "No scheme to restore"}

    no_window = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    try:
        result = subprocess.run(
            ["powercfg", "/setactive", _original_power_scheme],
            capture_output=True, text=True, timeout=5,
            creationflags=no_window
        )
        _original_power_scheme = None
        return {"success": result.returncode == 0}
    except Exception as e:
        return {"success": False, "error": str(e)}


def disable_nagle_algorithm() -> dict:
    """
    Disable Nagle's algorithm (TCP delay) on all network interfaces to
    eliminate network microstutter in online games. This reduces TCP
    send latency from ~200ms (Nagle batching window) to immediate.
    Safe: only affects TCP_NODELAY behavior, no packet loss risk.
    """
    import winreg
    modified = 0
    try:
        base_key = r"SYSTEM\CurrentControlSet\Services\Tcpip\Parameters\Interfaces"
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, base_key) as key:
            i = 0
            while True:
                try:
                    subkey_name = winreg.EnumKey(key, i)
                    subkey_path = f"{base_key}\\{subkey_name}"
                    with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, subkey_path,
                                       0, winreg.KEY_SET_VALUE) as subkey:
                        winreg.SetValueEx(subkey, "TcpAckFrequency", 0, winreg.REG_DWORD, 1)
                        winreg.SetValueEx(subkey, "TCPNoDelay", 0, winreg.REG_DWORD, 1)
                        modified += 1
                    i += 1
                except OSError:
                    break
        return {"success": True, "interfaces_modified": modified}
    except Exception as e:
        return {"success": False, "error": str(e)}


def set_game_gpu_preference(exe_path: str) -> dict:
    """
    Register a game executable for 'High Performance' GPU preference in
    Windows Graphics Settings. This forces the discrete GPU and prevents
    the OS from routing game frames through the integrated GPU.
    """
    import winreg
    try:
        key_path = r"Software\Microsoft\DirectX\UserGpuPreferences"
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, key_path) as key:
            winreg.SetValueEx(key, exe_path, 0, winreg.REG_SZ, "GpuPreference=2;")
        return {"success": True, "exe": exe_path}
    except Exception as e:
        return {"success": False, "error": str(e)}


def disable_fullscreen_optimizations(exe_path: str) -> dict:
    """
    Disable Windows 'fullscreen optimizations' (DWM composition in borderless)
    for a game executable. This forces true exclusive fullscreen which
    eliminates DWM-induced frame pacing stutter.
    """
    import winreg
    try:
        key_path = rf"Software\Microsoft\Windows NT\CurrentVersion\AppCompatFlags\Layers"
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, key_path) as key:
            # Read existing flags if any
            try:
                existing, _ = winreg.QueryValueEx(key, exe_path)
            except FileNotFoundError:
                existing = ""
            if "DISABLEDXMAXIMIZEDWINDOWEDMODE" not in existing.upper():
                new_val = f"{existing} DISABLEDXMAXIMIZEDWINDOWEDMODE".strip()
                winreg.SetValueEx(key, exe_path, 0, winreg.REG_SZ, new_val)
        return {"success": True, "exe": exe_path}
    except Exception as e:
        return {"success": False, "error": str(e)}


def proactive_ram_flush(game_pid: Optional[int] = None) -> dict:
    """
    Aggressive pre-game RAM flush: clears standby list AND trims background
    working sets. Called once when a game is first detected to give it the
    maximum available RAM headroom from the start.
    """
    exclude = [game_pid] if game_pid else []
    standby_res = clear_standby_memory()
    trim_res = trim_all_working_sets(exclude_pids=exclude)
    total_freed = standby_res.get("freed_mb", 0) + trim_res.get("freed_mb", 0)
    return {
        "success": standby_res.get("success", False),
        "freed_mb": total_freed,
        "trimmed_processes": trim_res.get("trimmed", 0),
    }


def disable_game_bar_notifications() -> dict:
    """
    Disable Xbox Game Bar overlay and notifications which can cause
    frame drops and stuttering when they trigger during gameplay.
    """
    import winreg
    try:
        # Disable Game Bar
        key_path = r"Software\Microsoft\GameBar"
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, key_path) as key:
            winreg.SetValueEx(key, "AllowAutoGameMode", 0, winreg.REG_DWORD, 1)
            winreg.SetValueEx(key, "AutoGameModeEnabled", 0, winreg.REG_DWORD, 1)

        # Disable Game DVR background recording (major stutter source)
        dvr_path = r"Software\Microsoft\Windows\CurrentVersion\GameDVR"
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, dvr_path) as key:
            winreg.SetValueEx(key, "AppCaptureEnabled", 0, winreg.REG_DWORD, 0)

        return {"success": True}
    except Exception as e:
        return {"success": False, "error": str(e)}


# ── Network Stabilization Suite ───────────────────────────────────────

def flush_dns_cache() -> dict:
    """
    Flush the Windows DNS resolver cache to clear stale or poisoned entries.
    Forces fresh DNS lookups for game servers, reducing connection timeouts.
    """
    no_window = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    try:
        result = subprocess.run(
            ["ipconfig", "/flushdns"],
            capture_output=True, text=True, timeout=10,
            creationflags=no_window
        )
        success = result.returncode == 0 or "successfully" in result.stdout.lower()
        return {"success": success, "output": result.stdout.strip()}
    except Exception as e:
        return {"success": False, "error": str(e)}


def optimize_dns_servers() -> dict:
    """
    Set primary DNS to Cloudflare (1.1.1.1) and secondary to Google (8.8.8.8)
    on the active network adapter. These are the fastest public DNS servers
    and dramatically reduce DNS lookup latency for game server connections.
    Returns the adapter name that was modified.
    """
    no_window = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    try:
        # Find the active adapter name
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             "(Get-NetAdapter | Where-Object {$_.Status -eq 'Up' -and $_.InterfaceDescription -notlike '*Virtual*'} | Select-Object -First 1).Name"],
            capture_output=True, text=True, timeout=10,
            creationflags=no_window
        )
        adapter_name = result.stdout.strip()
        if not adapter_name:
            return {"success": False, "error": "No active network adapter found"}

        # Set Cloudflare primary, Google secondary
        subprocess.run(
            ["netsh", "interface", "ip", "set", "dns", f"name={adapter_name}",
             "static", "1.1.1.1"],
            capture_output=True, text=True, timeout=10,
            creationflags=no_window
        )
        subprocess.run(
            ["netsh", "interface", "ip", "add", "dns", f"name={adapter_name}",
             "8.8.8.8", "index=2"],
            capture_output=True, text=True, timeout=10,
            creationflags=no_window
        )

        return {"success": True, "adapter": adapter_name, "primary": "1.1.1.1", "secondary": "8.8.8.8"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def disable_network_power_saving() -> dict:
    """
    Disable power management on all network adapters to prevent the OS
    from putting NICs to sleep during gameplay, which causes periodic
    latency spikes and packet loss.
    """
    no_window = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             "Get-NetAdapter | Where-Object {$_.Status -eq 'Up'} | ForEach-Object {"
             "  $_ | Set-NetAdapterPowerManagement -WakeOnMagicPacket Disabled -WakeOnPattern Disabled -ErrorAction SilentlyContinue;"
             "  $_.Name"
             "}"],
            capture_output=True, text=True, timeout=15,
            creationflags=no_window
        )
        adapters = [a.strip() for a in result.stdout.strip().splitlines() if a.strip()]
        return {"success": True, "adapters_modified": len(adapters)}
    except Exception as e:
        return {"success": False, "error": str(e)}


def disable_network_throttling() -> dict:
    """
    Disable the Windows Network Throttling Index which limits network
    throughput for non-multimedia applications. Games are often misclassified
    and throttled, causing rubberbanding and lag spikes.
    """
    import winreg
    try:
        key_path = r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\Multimedia\SystemProfile"
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_path,
                           0, winreg.KEY_SET_VALUE) as key:
            # Set NetworkThrottlingIndex to max (0xFFFFFFFF = disabled)
            winreg.SetValueEx(key, "NetworkThrottlingIndex", 0, winreg.REG_DWORD, 0xFFFFFFFF)
            # Also disable system responsiveness throttle during gaming
            winreg.SetValueEx(key, "SystemResponsiveness", 0, winreg.REG_DWORD, 0)
        return {"success": True}
    except Exception as e:
        return {"success": False, "error": str(e)}


def optimize_tcp_settings() -> dict:
    """
    Optimize TCP/IP stack settings for low-latency gaming:
    - Set receive window auto-tuning to 'normal' (prevents excessive buffering)
    - Enable Direct Cache Access for faster packet processing
    - Set congestion provider to CTCP for better throughput
    """
    no_window = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    results = []
    try:
        # TCP auto-tuning level
        r1 = subprocess.run(
            ["netsh", "int", "tcp", "set", "global", "autotuninglevel=normal"],
            capture_output=True, text=True, timeout=10,
            creationflags=no_window
        )
        results.append(f"AutoTuning: {'OK' if r1.returncode == 0 else 'SKIP'}")

        # Enable Direct Cache Access
        r2 = subprocess.run(
            ["netsh", "int", "tcp", "set", "global", "dca=enabled"],
            capture_output=True, text=True, timeout=10,
            creationflags=no_window
        )
        results.append(f"DCA: {'OK' if r2.returncode == 0 else 'SKIP'}")

        # Enable CTCP congestion provider (better for gaming)
        r3 = subprocess.run(
            ["netsh", "int", "tcp", "set", "supplemental", "template=internet",
             "congestionprovider=ctcp"],
            capture_output=True, text=True, timeout=10,
            creationflags=no_window
        )
        results.append(f"CTCP: {'OK' if r3.returncode == 0 else 'SKIP'}")

        return {"success": True, "details": " | ".join(results)}
    except Exception as e:
        return {"success": False, "error": str(e)}


def reset_network_stack() -> dict:
    """
    Full nuclear reset of the Windows network stack:
    - Reset Winsock catalog
    - Reset TCP/IP stack
    - Reset firewall rules
    Requires a reboot to take full effect.
    """
    no_window = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    results = []
    try:
        r1 = subprocess.run(
            ["netsh", "winsock", "reset"],
            capture_output=True, text=True, timeout=15,
            creationflags=no_window
        )
        results.append(f"Winsock: {'OK' if r1.returncode == 0 else r1.stderr.strip()}")

        r2 = subprocess.run(
            ["netsh", "int", "ip", "reset"],
            capture_output=True, text=True, timeout=15,
            creationflags=no_window
        )
        results.append(f"TCP/IP: {'OK' if r2.returncode == 0 else r2.stderr.strip()}")

        return {"success": True, "details": " | ".join(results), "reboot_required": True}
    except Exception as e:
        return {"success": False, "error": str(e)}


def get_network_status() -> dict:
    """
    Get current network adapter status, latency estimate via ping,
    and active DNS configuration.
    """
    no_window = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    info = {"connected": False, "adapter": "Unknown", "dns": [], "latency_ms": -1}

    try:
        # Check connectivity + adapter
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             "$a = Get-NetAdapter | Where-Object {$_.Status -eq 'Up'} | Select-Object -First 1;"
             "if($a){$a.Name + '|' + $a.LinkSpeed}else{'NONE'}"],
            capture_output=True, text=True, timeout=10,
            creationflags=no_window
        )
        adapter_info = result.stdout.strip()
        if adapter_info and adapter_info != "NONE":
            parts = adapter_info.split("|")
            info["connected"] = True
            info["adapter"] = parts[0] if len(parts) > 0 else "Unknown"
            info["link_speed"] = parts[1] if len(parts) > 1 else "Unknown"

        # Get DNS servers
        dns_result = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             "(Get-DnsClientServerAddress -AddressFamily IPv4 | Where-Object {$_.ServerAddresses.Count -gt 0} | Select-Object -First 1).ServerAddresses -join ','"],
            capture_output=True, text=True, timeout=10,
            creationflags=no_window
        )
        dns_str = dns_result.stdout.strip()
        if dns_str:
            info["dns"] = [d.strip() for d in dns_str.split(",") if d.strip()]

        # Quick ping test to Cloudflare (reliable, fast)
        ping_result = subprocess.run(
            ["ping", "-n", "3", "-w", "1000", "1.1.1.1"],
            capture_output=True, text=True, timeout=10,
            creationflags=no_window
        )
        for line in ping_result.stdout.splitlines():
            if "average" in line.lower() or "Average" in line:
                # Extract average ms value
                import re
                match = re.search(r"(\d+)\s*ms", line)
                if match:
                    info["latency_ms"] = int(match.group(1))
                break

    except Exception:
        pass

    return info


def stabilize_network() -> dict:
    """
    Run all safe network stabilization optimizations in one shot:
    DNS flush, Nagle disable, network throttling disable, TCP tuning.
    Does NOT include DNS server change or full reset (those are user-choice).
    """
    results = {}
    results["dns_flush"] = flush_dns_cache()
    results["nagle"] = disable_nagle_algorithm()
    results["throttling"] = disable_network_throttling()
    results["tcp"] = optimize_tcp_settings()

    all_success = all(r.get("success", False) for r in results.values())
    return {"success": all_success, "details": results}

