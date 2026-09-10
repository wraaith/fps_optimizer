import os
import ctypes
import ctypes.wintypes as wintypes
import subprocess
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
    "audiodg.exe", "shellexperiencehost.exe", "searchhost.exe"
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
    Excludes the current python process and critical Windows system processes.
    Format: [{"pid": int, "name": str, "memory_mb": float}]
    """
    current_pid = os.getpid()
    processes = []
    
    for proc in psutil.process_iter(['pid', 'name', 'memory_info']):
        try:
            pid = proc.info['pid']
            name = proc.info['name']
            
            if not name:
                continue
                
            name_lower = name.lower()
            
            # Skip self and critical system processes
            if pid == current_pid or name_lower in SYSTEM_PROCESSES:
                continue
                
            # Filter out things that are part of the python runtime for this app 
            # if they contain "--overlay" etc., though current_pid handles main.py.
            
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

        if not advapi32.AdjustTokenPrivileges(
            hToken, False, ctypes.byref(tp), ctypes.sizeof(tp), None, None
        ):
            return False

        # AdjustTokenPrivileges can "succeed" but still fail
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
    try:
        result = subprocess.run(
            ["sc", "query", "SysMain"],
            capture_output=True, text=True, timeout=5
        )
        running = "RUNNING" in result.stdout.upper()

        # Also check start type
        cfg = subprocess.run(
            ["sc", "qc", "SysMain"],
            capture_output=True, text=True, timeout=5
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
    try:
        if enable:
            subprocess.run(
                ["sc", "config", "SysMain", "start=", "auto"],
                capture_output=True, text=True, timeout=10
            )
            result = subprocess.run(
                ["sc", "start", "SysMain"],
                capture_output=True, text=True, timeout=10
            )
        else:
            subprocess.run(
                ["sc", "stop", "SysMain"],
                capture_output=True, text=True, timeout=10
            )
            result = subprocess.run(
                ["sc", "config", "SysMain", "start=", "disabled"],
                capture_output=True, text=True, timeout=10
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


def check_has_ssd() -> bool:
    """
    Check if the system drive (C:) is an SSD using WMI.
    Returns True if SSD, False if HDD or unknown.
    """
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             "Get-PhysicalDisk | Where-Object { $_.DeviceID -eq '0' } | Select-Object -ExpandProperty MediaType"],
            capture_output=True, text=True, timeout=10
        )
        return "SSD" in result.stdout.upper() or "SOLID" in result.stdout.upper()
    except Exception:
        # Fallback: try alternative WMI query
        try:
            result = subprocess.run(
                ["wmic", "diskdrive", "get", "MediaType"],
                capture_output=True, text=True, timeout=10
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
        return winmm.timeBeginPeriod(resolution_ms) == 0
    except Exception:
        return False


def disable_high_resolution_timer(resolution_ms: int = 1) -> bool:
    """
    Restore standard OS timer resolution when optimizer/sentinel is deactivated.
    """
    try:
        winmm = ctypes.WinDLL("winmm")
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

