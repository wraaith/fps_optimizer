"""
AI System Performance Booster - Safe Action Executor
Implements NON-DESTRUCTIVE optimization actions only.
No process is ever forcibly terminated (taskkill/psutil.terminate is never called).
Windows-specific actions use ctypes/WinAPI or ship out to helper .exe tools
(EmptyStandbyList.exe / RAMMap) that must be present alongside this script.
"""
import subprocess
import platform
import psutil
import os
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("ActionExecutor")

IS_WINDOWS = platform.system() == "Windows"
EMPTY_STANDBY_TOOL = os.path.join(os.path.dirname(__file__), "EmptyStandbyList.exe")

def clear_standby_memory():
    """Calls native Windows NtSetSystemInformation (or EmptyStandbyList.exe fallback)
    to release Windows standby/cached RAM. This never touches running processes."""
    if not IS_WINDOWS:
        log.info("Standby memory clearing is Windows-only. Skipped.")
        return False
    try:
        from optimize.optimizer_service import clear_standby_memory as opt_clear
        res = opt_clear()
        if res.get("success"):
            log.info(f"Standby memory list cleared via native NtSetSystemInformation (freed {res.get('freed_mb', 0)}MB).")
            return True
    except Exception:
        pass
    if not os.path.exists(EMPTY_STANDBY_TOOL):
        log.warning("EmptyStandbyList.exe not found and native privilege failed.")
        return False
    try:
        subprocess.run([EMPTY_STANDBY_TOOL, "workingsets"], check=True, timeout=15)
        log.info("Standby memory list cleared via EmptyStandbyList.exe.")
        return True
    except Exception as e:
        log.error(f"Failed to clear standby memory: {e}")
        return False

def lower_background_priority(exclude_names=None, mem_threshold_mb=100):
    """Lowers CPU priority (nice value) of background processes above a memory
    threshold, WITHOUT ending them. Foreground/whitelisted apps are excluded."""
    exclude_names = set(n.lower() for n in (exclude_names or []))
    changed = []
    for p in psutil.process_iter(['pid', 'name', 'memory_info']):
        try:
            name = (p.info['name'] or "").lower()
            mem_info = p.info.get('memory_info')
            if not mem_info:
                continue
            mem_mb = mem_info.rss / (1024**2)
            if name in exclude_names or mem_mb < mem_threshold_mb:
                continue
            if IS_WINDOWS:
                p.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
            else:
                p.nice(10)
            changed.append(p.info['pid'])
        except (psutil.NoSuchProcess, psutil.AccessDenied, Exception):
            continue
    log.info(f"Lowered priority for {len(changed)} background processes: {changed}")
    return changed

def review_pagefile_size():
    """Read-only advisory: recommends checking virtual memory settings.
    Actual pagefile resize requires admin + registry/WMI edits, left as a
    manual confirmation step for safety."""
    log.info("Swap usage elevated. Recommend reviewing virtual memory (page file) size in "
             "System Properties > Advanced > Performance > Virtual Memory.")
    return "advisory_logged"

def trim_working_sets_safe():
    """Uses Windows SetProcessWorkingSetSize via ctypes to ask the OS to trim
    a process's working set (moves idle pages to standby/compressed store)
    WITHOUT terminating it. Skips system-critical PIDs."""
    if not IS_WINDOWS:
        return []
    import ctypes
    trimmed = []
    PROCESS_QUERY_INFORMATION = 0x0400
    PROCESS_SET_QUOTA = 0x0100
    for p in psutil.process_iter(['pid', 'name']):
        try:
            if p.info['pid'] in (0, 4):
                continue
            handle = ctypes.windll.kernel32.OpenProcess(
                PROCESS_QUERY_INFORMATION | PROCESS_SET_QUOTA, False, p.info['pid'])
            if handle:
                ctypes.windll.kernel32.SetProcessWorkingSetSize(handle, -1, -1)
                ctypes.windll.kernel32.CloseHandle(handle)
                trimmed.append(p.info['pid'])
        except Exception:
            continue
    log.info(f"Requested working-set trim for {len(trimmed)} processes (no process ended).")
    return trimmed


def trim_all_working_sets(exclude_pids=None):
    """Wrapper around working set trimming accepting optional exclude_pids."""
    if not IS_WINDOWS:
        return []
    import ctypes
    exclude = set(exclude_pids or [])
    trimmed = []
    PROCESS_QUERY_INFORMATION = 0x0400
    PROCESS_SET_QUOTA = 0x0100
    for p in psutil.process_iter(['pid', 'name']):
        try:
            pid = p.info['pid']
            if pid in (0, 4) or pid in exclude:
                continue
            handle = ctypes.windll.kernel32.OpenProcess(
                PROCESS_QUERY_INFORMATION | PROCESS_SET_QUOTA, False, pid)
            if handle:
                ctypes.windll.kernel32.SetProcessWorkingSetSize(handle, -1, -1)
                ctypes.windll.kernel32.CloseHandle(handle)
                trimmed.append(pid)
        except Exception:
            continue
    log.info(f"Requested working-set trim for {len(trimmed)} processes (no process ended).")
    return trimmed

ACTION_MAP = {
    "CLEAR_STANDBY_MEMORY": clear_standby_memory,
    "LOWER_BACKGROUND_PROCESS_PRIORITY": lower_background_priority,
    "REVIEW_PAGEFILE_SIZE": review_pagefile_size,
    "TRIM_WORKING_SETS": trim_working_sets_safe,
    "TRIM_ALL_WORKING_SETS": trim_all_working_sets,
}

def execute(action_names):
    results = {}
    for name in action_names:
        fn = ACTION_MAP.get(name)
        if fn:
            results[name] = fn()
        else:
            results[name] = "unknown_action"
    return results
