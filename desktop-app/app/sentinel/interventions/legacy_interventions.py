import os
import psutil
import json
import logging
import subprocess
import socket
from typing import Dict, Any, List, Optional
from sentinel.models import InterventionResult

# Fallback basic imports that exist in the codebase
from network_stabilizer.snapshot_manager import SnapshotManager
from network_stabilizer.tweaks_engine import TweaksEngine

logger = logging.getLogger(__name__)

class DNSIntervention:
    def __init__(self):
        self.sm = SnapshotManager()
        self.te = TweaksEngine()

    def execute(self, args: Dict[str, Any]) -> InterventionResult:
        adapter_id = args.get("adapter_id")
        servers = args.get("servers", [])
        mode = args.get("mode")

        if not adapter_id:
            return InterventionResult(status="failed", operation="dns", reason="Missing adapter_id")
            
        # Validate addresses
        for s in servers:
            try:
                socket.inet_aton(s)
            except socket.error:
                return InterventionResult(status="failed", operation="dns", reason=f"Invalid IP: {s}")
                
        # Validate adapter identity (mockable via netsh or powershell)
        # We will assume validation happens in TweaksEngine or SnapshotManager
        
        # Snapshot original DNS
        baseline = self.sm.ensure_baseline_snapshot()
        old_dns = None
        if "baseline" in baseline:
            old_dns = baseline["baseline"].get("dns", {}).get(adapter_id)
            
        # Call provider
        if mode and "dhcp" in str(mode).lower():
            res = self.te.revert_dns_to_dhcp()
        else:
            res = self.te.apply_dns_servers(adapter_id, servers, "Sentinel DNS")
            
        if res.get("success"):
            # Record change for rollback
            change = {
                "category": "dns",
                "target": adapter_id,
                "old_mode": old_dns.get("mode") if old_dns else "auto",
                "old_value": old_dns.get("servers") if old_dns else ["dhcp"],
            }
            self.sm.record_change(change)
            
            return InterventionResult(
                status="applied",
                operation="dns",
                system_changed=True,
                rollback_available=True,
                details=res
            )
        else:
            return InterventionResult(status="failed", operation="dns", reason=res.get("error", "Unknown error"))

class PowerPlanIntervention:
    def __init__(self):
        self.sm = SnapshotManager()
        
    def execute(self, args: Dict[str, Any]) -> InterventionResult:
        requested_guid = args.get("requested_guid")
        if not requested_guid:
            return InterventionResult(status="failed", operation="power_plan", reason="Missing requested_guid")
            
        # Snapshot original GUID
        baseline = self.sm.ensure_baseline_snapshot()
        old_power = None
        if "baseline" in baseline:
            old_power = baseline["baseline"].get("power_plan", {}).get("active_guid")
            
        if not old_power:
            # Try to get it now if missing from baseline
            try:
                p_active = subprocess.run(["powercfg", "/getactivescheme"], capture_output=True, text=True, timeout=5)
                if p_active.returncode == 0:
                    import re
                    match = re.search(r"GUID:\s+([a-fA-F0-9\-]+)", p_active.stdout)
                    if match:
                        old_power = match.group(1)
            except Exception:
                pass
                
        if not old_power:
            old_power = "381b4222-f694-41f0-9685-ff5bb260df2e" # Balanced fallback
            
        # Handle access denied and missing plans during set
        try:
            # Check if requested GUID exists
            p_list = subprocess.run(["powercfg", "/list"], capture_output=True, text=True, timeout=5)
            if requested_guid.lower() not in p_list.stdout.lower():
                return InterventionResult(status="failed", operation="power_plan", reason="Requested power plan not found on system")
                
            p = subprocess.run(["powercfg", "/setactive", requested_guid], capture_output=True, text=True, timeout=5)
            if p.returncode != 0:
                return InterventionResult(status="failed", operation="power_plan", reason=f"Access Denied or Failed: {p.stderr.strip()}")
        except Exception as e:
            return InterventionResult(status="failed", operation="power_plan", reason=f"Error: {e}")
            
        # Record for rollback
        self.sm.record_change({
            "category": "power_plan",
            "old_value": old_power
        })
        
        return InterventionResult(
            status="applied",
            operation="power_plan",
            system_changed=True,
            rollback_available=True
        )

class ProcessCleanupIntervention:
    """High-risk legacy-only operation."""
    
    # Exclude system, anticheat, GPU, audio, network, input, active-game, etc.
    PROTECTED_PROCESSES = {
        # System & Windows core
        "system", "system idle process", "svchost.exe", "csrss.exe", "smss.exe", "lsass.exe", 
        "services.exe", "explorer.exe", "winlogon.exe", "dwm.exe", "spoolsv.exe", "wininit.exe",
        "fontdrvhost.exe", "sihost.exe", "taskhostw.exe", "ctfmon.exe", "conhost.exe",
        # Security & Defender
        "antimalware", "msmpeng.exe", "nissrv.exe", "securityhealthservice.exe", "smartscreen.exe",
        # Anti-cheat
        "easyanticheat.exe", "easyanticheat_eos.exe", "beservice.exe", "vgk.exe", "vgc.exe",
        "battleye.exe", "ricochet.exe", "punkbuster.exe",
        # Audio
        "audiodg.exe", "audiodevices.exe",
        # GPU
        "nvdisplay.container.exe", "nvcontainer.exe", "nvidia share.exe", "amdow.exe",
        "amdrsserv.exe", "radeonsoftware.exe", "igfxcuiservice.exe",
        # Network & Input
        "netsh.exe", "wlanext.exe", "wisptis.exe", "mousocoreworker.exe",
        # Python / App
        "python.exe", "pythonw.exe"
    }
    
    ALLOWLIST = {
        "presentmon-2.5.1-x64.exe",
        "fps_optimizer_overlay.exe" 
    }
    
    def __init__(self, token_manager=None):
        self.token_manager = token_manager
        
    @staticmethod
    def _get_proc_pid(p: Any) -> Optional[int]:
        val = getattr(p, "pid", None)
        return val() if callable(val) else val

    @staticmethod
    def _get_proc_name(p: Any) -> str:
        val = getattr(p, "name", None)
        res = val() if callable(val) else val
        return (res or "").lower()

    @staticmethod
    def _get_proc_exe(p: Any) -> str:
        val = getattr(p, "exe", None)
        res = val() if callable(val) else val
        return (res or "").lower()

    @staticmethod
    def _get_proc_ctime(p: Any) -> float:
        val = getattr(p, "create_time", None)
        return val() if callable(val) else (val or 0.0)

    def _is_active_game(self, pid: int, name: str) -> bool:
        if name in ("game.exe", "active_game.exe") or name.endswith("_game.exe") or name.endswith("-game.exe"):
            return True
        try:
            from optimize.ai_boost_service import get_ai_boost_service
            boost_svc = get_ai_boost_service()
            if boost_svc and getattr(boost_svc, "_active_game_pid", None) == pid:
                return True
        except Exception:
            pass
        try:
            from optimize.optimizer_service import get_foreground_game_process
            fg = get_foreground_game_process()
            if fg and fg.get("pid") == pid:
                return True
        except Exception:
            pass
        return False

    def execute(self, args: Dict[str, Any]) -> InterventionResult:
        legacy_mode = args.get("legacy_mode", False)
        dry_run = args.get("dry_run", True)
        current_session_id = args.get("current_session_id", "")
        is_sentinel_running = args.get("is_sentinel_running", False)
        token_mgr = self.token_manager or args.get("token_manager")
        
        # Real process cleanup is blocked whenever Sentinel is active
        if is_sentinel_running and not dry_run:
            return InterventionResult(
                status="blocked",
                operation="process_cleanup",
                reason="Sentinel is active",
                system_changed=False
            )
            
        if not legacy_mode:
            return InterventionResult(
                status="blocked",
                operation="process_cleanup",
                reason="Requires explicit legacy_mode",
                system_changed=False
            )
            
        current_pid = os.getpid()
        protected_pids = {current_pid, 0, 4}
        try:
            p = psutil.Process(current_pid)
            parent = p.parent() if callable(getattr(p, "parent", None)) else None
            if parent:
                parent_pid = self._get_proc_pid(parent)
                if parent_pid:
                    protected_pids.add(parent_pid)
        except Exception:
            pass
            
        if dry_run:
            candidates = []
            try:
                for proc in psutil.process_iter(['pid', 'name', 'exe', 'create_time']):
                    try:
                        info = getattr(proc, "info", None) or {}
                        pid = info.get('pid') or self._get_proc_pid(proc)
                        pname = (info.get('name') or self._get_proc_name(proc)).lower()
                        exe_path = (info.get('exe') or self._get_proc_exe(proc)).lower()
                        ctime = info.get('create_time') if info.get('create_time') is not None else self._get_proc_ctime(proc)
                        
                        if not pid or pid in protected_pids or pid <= 4:
                            continue
                            
                        # Scan only exact allowlist
                        if pname not in self.ALLOWLIST:
                            continue
                            
                        # Exclude protected processes
                        if pname in self.PROTECTED_PROCESSES:
                            continue
                            
                        # Exclude active games
                        if self._is_active_game(pid, pname):
                            continue
                            
                        token = None
                        if token_mgr:
                            token = token_mgr.generate_token(
                                pid=pid,
                                exe_path=exe_path,
                                create_time=ctime,
                                operation="process_cleanup",
                                session_id=current_session_id
                            )
                            
                        candidates.append({
                            "pid": pid,
                            "executable_path": exe_path,
                            "exe": exe_path,
                            "creation_time": ctime,
                            "reason": "Allowlisted process candidate for cleanup",
                            "token": token,
                            "token_expiry": 60.0
                        })
                    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                        pass
            except Exception as e:
                return InterventionResult(
                    status="failed",
                    operation="process_cleanup",
                    reason=str(e),
                    system_changed=False
                )
                
            return InterventionResult(
                status="dry_run",
                operation="process_cleanup",
                system_changed=False,
                rollback_available=False,
                details={"candidates": candidates, "terminated": [], "rejected": []}
            )

        # Real termination (dry_run=False)
        foreground_confirmed = args.get("foreground_confirmed", False) or args.get("confirmed", False)
        if not foreground_confirmed:
            return InterventionResult(
                status="blocked",
                operation="process_cleanup",
                reason="Foreground confirmation required",
                system_changed=False
            )
            
        if not current_session_id:
            return InterventionResult(
                status="blocked",
                operation="process_cleanup",
                reason="Invalid or missing session ID",
                system_changed=False
            )
            
        targets = args.get("targets", [])
        if not targets or len(targets) != 1:
            return InterventionResult(
                status="blocked",
                operation="process_cleanup",
                reason="Exactly one target required",
                system_changed=False
            )
            
        target = targets[0]
        target_pid = target.get("pid")
        token = target.get("token")
        
        if not token:
            return InterventionResult(
                status="blocked",
                operation="process_cleanup",
                reason="Missing token",
                system_changed=False
            )
            
        if target_pid is None:
            return InterventionResult(
                status="blocked",
                operation="process_cleanup",
                reason="Missing target PID",
                system_changed=False
            )
            
        try:
            proc = psutil.Process(target_pid)
            p_pid = self._get_proc_pid(proc)
            p_name = self._get_proc_name(proc)
            p_exe = self._get_proc_exe(proc)
            p_ctime = self._get_proc_ctime(proc)
        except psutil.NoSuchProcess:
            return InterventionResult(
                status="already_exited",
                operation="process_cleanup",
                reason="Process disappeared",
                system_changed=False
            )
        except psutil.AccessDenied:
            return InterventionResult(
                status="failed",
                operation="process_cleanup",
                reason="Access denied",
                system_changed=False
            )
        except Exception as e:
            return InterventionResult(
                status="failed",
                operation="process_cleanup",
                reason=str(e),
                system_changed=False
            )
            
        if p_pid != target_pid:
            return InterventionResult(
                status="blocked",
                operation="process_cleanup",
                reason="PID mismatch",
                system_changed=False
            )
            
        if p_name not in self.ALLOWLIST:
            return InterventionResult(
                status="blocked",
                operation="process_cleanup",
                reason="Not in allowlist",
                system_changed=False
            )
            
        if p_name in self.PROTECTED_PROCESSES or target_pid in protected_pids or target_pid <= 4:
            return InterventionResult(
                status="blocked",
                operation="process_cleanup",
                reason="Target is protected",
                system_changed=False
            )
            
        if self._is_active_game(target_pid, p_name):
            return InterventionResult(
                status="blocked",
                operation="process_cleanup",
                reason="Target is active game",
                system_changed=False
            )
            
        if token_mgr:
            val_res = token_mgr.consume_token(
                token=token,
                pid=target_pid,
                exe_path=p_exe,
                create_time=p_ctime,
                operation="process_cleanup",
                session_id=current_session_id
            )
            if str(val_res) != "valid":
                return InterventionResult(
                    status="identity_changed" if str(val_res) == "identity_mismatch" else "blocked",
                    operation="process_cleanup",
                    reason=f"Token validation failed: {val_res}",
                    system_changed=False
                )
                
        try:
            proc.terminate()
        except psutil.NoSuchProcess:
            return InterventionResult(
                status="already_exited",
                operation="process_cleanup",
                reason="Process disappeared",
                system_changed=False
            )
        except psutil.AccessDenied:
            return InterventionResult(
                status="failed",
                operation="process_cleanup",
                reason="Access denied",
                system_changed=False
            )
        except Exception as e:
            return InterventionResult(
                status="failed",
                operation="process_cleanup",
                reason=str(e),
                system_changed=False
            )
            
        return InterventionResult(
            status="applied",
            operation="process_cleanup",
            system_changed=True,
            rollback_available=False,
            details={"terminated": [{"pid": target_pid, "name": p_name, "exe": p_exe}], "candidates": []}
        )
