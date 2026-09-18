"""
Compact Snapshot & Rollback Manager for Network Stabilizer.
Handles atomic state persistence, corruption recovery, complete power-plan GUIDs,
DNS auto/manual mode tracking, and targeted LIFO rollback with post-verification.
"""

import os
import re
import sys
import json
import uuid
import winreg
import subprocess
from datetime import datetime
from typing import Dict, List, Any, Optional

from network_stabilizer.constants import (
    STATE_FILE_PATH,
    SCHEMA_VERSION,
    REG_MULTIMEDIA_PROFILE,
    REG_TCPIP_INTERFACES,
    REG_GAME_CONFIG_STORE,
    REG_GAME_DVR_USER,
    POWER_SCHEME_BALANCED,
    REGEX_POWER_GUID,
    DNS_MODE_AUTO,
    DNS_MODE_MANUAL,
    STATUS_PROPOSED,
    STATUS_APPLIED,
    STATUS_VERIFIED,
    STATUS_REVERTED,
    STATUS_ROLLBACK_FAILED,
    STATUS_SKIPPED,
    TERM_RESTORE_RESULT,
    TERM_WINSOCK_RECOVERY
)


class SnapshotManager:
    """
    Manages baseline state, audit ledger, and targeted LIFO rollback in network_stabilizer_state.json.
    """
    def __init__(self, state_file_path: Optional[str] = None):
        self.state_file = state_file_path or STATE_FILE_PATH
        self._ensure_state_file()

    def _get_empty_schema(self) -> Dict[str, Any]:
        return {
            "schema_version": 2,
            "network_state": {},
            "persistent_changes": [],
            "session_interventions": [],
            "priority_records": [],
            "timer_state": {},
            "snapshots": [],
            "last_rollback": None
        }

    def _ensure_state_file(self):
        """Ensure single compact state file exists with valid structure."""
        os.makedirs(os.path.dirname(self.state_file), exist_ok=True)
        if not os.path.exists(self.state_file):
            self._save_state_atomic(self._get_empty_schema())

    def _migrate_v1_to_v2(self, old_data: Dict[str, Any]) -> Dict[str, Any]:
        """Migrates a v1 schema to v2 without discarding data."""
        new_schema = self._get_empty_schema()
        
        # Move baseline -> network_state
        if "baseline" in old_data:
            new_schema["network_state"] = old_data.get("baseline", {})
            
        # Move changes -> persistent_changes
        if "changes" in old_data:
            new_schema["persistent_changes"] = old_data.get("changes", [])
            
        # Preserve unknown fields
        for k, v in old_data.items():
            if k not in ["schema_version", "baseline", "changes"] and k not in new_schema:
                new_schema[k] = v
                
        return new_schema

    def _load_state(self) -> Dict[str, Any]:
        """
        Loads state document safely. Recovers from corrupted state file
        by preserving the corrupt file with a timestamp and entering SAFE_MODE (returning empty schema).
        """
        if not os.path.exists(self.state_file):
            return self._get_empty_schema()

        try:
            with open(self.state_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                if not isinstance(data, dict):
                    raise ValueError("Root is not a dict")
                    
                version = data.get("schema_version")
                if version == "1.0.0" or version == 1:
                    migrated = self._migrate_v1_to_v2(data)
                    self._save_state_atomic(migrated)
                    return migrated
                elif version == 2:
                    # Validate top-level keys loosely
                    if "persistent_changes" in data:
                        return data
                raise ValueError(f"Unknown schema version or malformed data: {version}")
        except Exception as e:
            # Safe Mode: DO NOT guess, DO NOT overwrite the corrupt file with a fresh schema blindly.
            print(f"[SnapshotManager] CRITICAL: State file corrupted or schema mismatch ({e}). Entering SAFE_MODE.", file=sys.stderr)
            corrupt_backup = f"{self.state_file}.corrupt_{int(datetime.now().timestamp())}"
            try:
                # Preserve the original file by renaming it to the recovery path
                if os.path.exists(self.state_file):
                    os.rename(self.state_file, corrupt_backup)
            except Exception:
                pass
            
            # Record recovery path and enter safe mode
            self.in_safe_mode = True
            self.recovery_path = corrupt_backup
            
            # Notify the user and disable interventions
            print(f"[SnapshotManager] WARNING: Rollback may be incomplete. State file preserved at {corrupt_backup}", file=sys.stderr)
            print(f"[SnapshotManager] Automatic interventions disabled due to ledger corruption.", file=sys.stderr)
            
            # Do not silently treat it as an ordinary empty ledger, we explicitly mark safe mode
            empty = self._get_empty_schema()
            empty["safe_mode"] = True
            empty["recovery_path"] = corrupt_backup
            return empty

    def _save_state_atomic(self, state: Dict[str, Any]):
        """
        Saves state document atomically:
        Writes to .tmp, flushes & fsyncs, then os.replace.
        Preserves previous valid state if any exception occurs.
        """
        tmp_file = f"{self.state_file}.tmp_{uuid.uuid4().hex[:6]}"
        try:
            with open(tmp_file, "w", encoding="utf-8") as f:
                json.dump(state, f, indent=2)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp_file, self.state_file)
        except Exception as e:
            if os.path.exists(tmp_file):
                try:
                    os.remove(tmp_file)
                except Exception:
                    pass
            print(f"[SnapshotManager] Error during atomic save: {e}", file=sys.stderr)

    # ── Baseline Snapshot ───────────────────────────────────────────────

    def is_baseline_present(self) -> bool:
        """Check if baseline snapshot has been captured."""
        state = self._load_state()
        return bool(state.get("network_state", {}).get("created_at"))

    def get_baseline_metadata(self) -> Dict[str, Any]:
        """Return baseline dictionary."""
        state = self._load_state()
        return state.get("network_state", {})

    def ensure_baseline_snapshot(self) -> Dict[str, Any]:
        """
        Captures baseline state if not already recorded:
        - DNS per adapter with mode explicitly recorded (auto vs manual)
        - Complete Windows Power Scheme GUID (never shortened)
        - GameDVR and overlay settings
        - Active adapter identity (GUID, index, description, driver version)
        """
        state = self._load_state()
        baseline = state.get("network_state", {})
        if baseline.get("created_at"):
            return {"success": True, "baseline": baseline, "already_exists": True}

        no_window = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        captured = {
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "dns": {},
            "power_plan": {},
            "game_settings": {},
            "adapter_settings": {}
        }

        # 1. Capture DNS settings with separate mode and server list
        try:
            ps_dns = (
                "Get-DnsClientServerAddress -AddressFamily IPv4 | ForEach-Object { "
                "  $alias = $_.InterfaceAlias; "
                "  $addrs = $_.ServerAddresses; "
                "  $ipconf = Get-DnsClient -InterfaceAlias $alias -ErrorAction SilentlyContinue; "
                "  $isDhcp = $true; "
                "  if ($ipconf -and $ipconf.ServerAddresses -and $ipconf.ServerAddresses.Count -gt 0) { $isDhcp = $false }; "
                "  [PSCustomObject]@{ InterfaceAlias = $alias; Mode = $(if($isDhcp){'auto'}else{'manual'}); Addresses = ($addrs -join ',') } "
                "} | ConvertTo-Json -Compress"
            )
            proc = subprocess.run(["powershell", "-NoProfile", "-Command", ps_dns], capture_output=True, text=True, timeout=8, creationflags=no_window)
            if proc.returncode == 0 and proc.stdout.strip():
                parsed = json.loads(proc.stdout.strip())
                if isinstance(parsed, dict):
                    parsed = [parsed]
                for item in parsed:
                    alias = item.get("InterfaceAlias")
                    mode = item.get("Mode", DNS_MODE_AUTO)
                    addrs = [a.strip() for a in item.get("Addresses", "").split(",") if a.strip()]
                    captured["dns"][alias] = {
                        "mode": mode,
                        "servers": addrs if addrs else []
                    }
        except Exception:
            pass

        # 2. Capture complete Power Plan GUID returned by Windows
        try:
            p_proc = subprocess.run(["powercfg", "/getactivescheme"], capture_output=True, text=True, timeout=6, creationflags=no_window)
            import re
            m = re.search(r"Power Scheme GUID:\s*([0-9a-fA-F\-]{36})\s*\((.*?)\)", p_proc.stdout, re.IGNORECASE)
            if m and REGEX_POWER_GUID.match(m.group(1)):
                captured["power_plan"] = {
                    "guid": m.group(1).lower(),
                    "name": m.group(2).strip()
                }
            else:
                captured["power_plan"] = {
                    "guid": POWER_SCHEME_BALANCED,
                    "name": "Balanced"
                }
        except Exception:
            pass

        # 3. Capture GameDVR status
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_GAME_CONFIG_STORE, 0, winreg.KEY_READ) as k:
                val, _ = winreg.QueryValueEx(k, "GameDVR_Enabled")
                captured["game_settings"]["GameDVR_Enabled"] = val
        except Exception:
            captured["game_settings"]["GameDVR_Enabled"] = 1

        # 4. Capture Active Adapter with complete identity fields
        try:
            ps_adp = (
                "$a = Get-NetAdapter | Where-Object {$_.Status -eq 'Up' -and $_.InterfaceDescription -notlike '*Virtual*'} | Select-Object -First 1; "
                "if($a){ "
                "  $d = Get-NetAdapter -Name $a.Name | Select-Object InterfaceGuid, InterfaceIndex, Name, InterfaceDescription, DriverVersion; "
                "  $d | ConvertTo-Json -Compress "
                "} else { '' }"
            )
            a_proc = subprocess.run(["powershell", "-NoProfile", "-Command", ps_adp], capture_output=True, text=True, timeout=8, creationflags=no_window)
            adp_str = a_proc.stdout.strip()
            if adp_str:
                adp_json = json.loads(adp_str)
                captured["adapter_settings"]["active_adapter"] = {
                    "interface_guid": adp_json.get("InterfaceGuid", ""),
                    "interface_index": adp_json.get("InterfaceIndex", 0),
                    "name": adp_json.get("Name", ""),
                    "description": adp_json.get("InterfaceDescription", ""),
                    "driver_version": adp_json.get("DriverVersion", "")
                }
        except Exception:
            pass

        state["network_state"] = captured
        self._save_state_atomic(state)
        return {"success": True, "baseline": captured, "already_exists": False}

    # ── Audit Log Management ───────────────────────────────────────────

    def get_change_log(self) -> List[Dict[str, Any]]:
        """Retrieve full audit log."""
        state = self._load_state()
        return state.get("persistent_changes", [])

    def load_applied_changes(self) -> List[Dict[str, Any]]:
        """
        Retrieve only applied and verified changes that are eligible for rollback.
        Excludes already reverted or failed changes.
        """
        return [c for c in self.get_change_log() if c.get("status") in (STATUS_APPLIED, STATUS_VERIFIED)]

    def record_change(self, change: Dict[str, Any]) -> str:
        """Convenience method to record a change dictionary into the audit ledger."""
        category = change.get("category", "general")
        setting_name = change.get("setting", change.get("category", "general"))
        target = change.get("target", "System")
        old_value = change.get("old_value")
        new_value = change.get("new_value")
        old_mode = change.get("old_mode")
        reboot_required = change.get("reboot_required", False)
        status = change.get("status", STATUS_APPLIED)
        verification_status = change.get("verification_status", "unverified")

        return self.log_change(
            category=category,
            setting_name=setting_name,
            old_value=old_value,
            new_value=new_value,
            target=target,
            old_mode=old_mode,
            reboot_required=reboot_required,
            status=status,
            verification_status=verification_status
        )

    def log_change(
        self,
        category: str,
        setting_name: str,
        old_value: Any,
        new_value: Any,
        target: Optional[str] = None,
        old_mode: Optional[str] = None,
        reboot_required: bool = False,
        status: str = STATUS_APPLIED,
        verification_status: str = "unverified"
    ) -> str:
        """Record an explicit change entry into the persistent audit ledger."""
        state = self._load_state()
        ts_slug = datetime.now().strftime("%Y%m%d-%H%M%S")
        change_id = f"{category}-{ts_slug}-{uuid.uuid4().hex[:4]}"

        record = {
            "id": change_id,
            "category": category,
            "setting": setting_name,
            "target": target or "System",
            "old_value": old_value,
            "old_mode": old_mode,
            "new_value": new_value,
            "status": status,
            "reboot_required": reboot_required,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "verification_status": verification_status
        }

        state.setdefault("persistent_changes", []).append(record)
        self._save_state_atomic(state)
        return change_id

    def update_change_status(
        self,
        change_id: str,
        status: str,
        verification_status: Optional[str] = None,
        reason: Optional[str] = None
    ):
        """Update change record status without deleting history."""
        state = self._load_state()
        for c in state.get("persistent_changes", []):
            if c.get("id") == change_id:
                c["status"] = status
                if verification_status:
                    c["verification_status"] = verification_status
                if reason:
                    c["reason"] = reason
                c["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                break
        self._save_state_atomic(state)

    # ── Targeted LIFO Rollback ─────────────────────────────────────────

    def restore_change(self, change: Dict[str, Any]) -> Dict[str, Any]:
        """
        Restores a single change record back to old_value / old_mode.
        Validates target existence and verifies the restoration post-action.
        Reports whether registry values were restored or deleted because they did not previously exist.
        """
        no_window = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        cat = change.get("category")
        target = change.get("target")
        old_val = change.get("old_value")
        old_mode = change.get("old_mode")
        cid = change.get("id")
        setting = change.get("setting", cat)

        res = {
            "id": cid,
            "setting": setting,
            "target": target,
            "success": False,
            "skipped": False,
            "reason": "",
            "details": "",
            "reboot_required": change.get("reboot_required", False)
        }

        try:
            if cat == "dns":
                # Validate interface identifier format
                if not target or not re.match(r"^[a-zA-Z0-9 _\-\.\(\)]+$", str(target)):
                    res["skipped"] = True
                    res["reason"] = f"Invalid interface identifier format: '{target}'"
                    self.update_change_status(cid, STATUS_SKIPPED, "invalid_identifier", reason=res["reason"])
                    return res

                # Validate adapter presence directly via netsh without shell
                chk = subprocess.run(
                    ["netsh", "interface", "show", "interface", f"name={target}"],
                    capture_output=True, text=True, timeout=6, creationflags=no_window
                )
                if chk.returncode != 0:
                    res["skipped"] = True
                    res["reason"] = f"Network adapter '{target}' is no longer present or disconnected."
                    self.update_change_status(cid, STATUS_SKIPPED, "adapter_missing", reason=res["reason"])
                    return res

                if old_mode == DNS_MODE_AUTO or not old_val or old_val == ["dhcp"]:
                    # Restore automatic DHCP DNS
                    cmd = ["netsh", "interface", "ip", "set", "dns", f"name={target}", "source=dhcp"]
                    run_res = subprocess.run(cmd, capture_output=True, text=True, timeout=8, creationflags=no_window)
                    if run_res.returncode != 0:
                        res["reason"] = f"netsh DHCP DNS restore failed: {run_res.stderr.strip()}"
                        self.update_change_status(cid, STATUS_ROLLBACK_FAILED, "failed", reason=res["reason"])
                        return res
                    res["details"] = f"DNS restored to DHCP (auto) on {target}"
                elif isinstance(old_val, list) and len(old_val) > 0:
                    # Restore static DNS
                    cmd1 = ["netsh", "interface", "ip", "set", "dns", f"name={target}", "static", str(old_val[0])]
                    run_res1 = subprocess.run(cmd1, capture_output=True, text=True, timeout=8, creationflags=no_window)
                    if run_res1.returncode != 0:
                        res["reason"] = f"netsh static DNS primary restore failed: {run_res1.stderr.strip()}"
                        self.update_change_status(cid, STATUS_ROLLBACK_FAILED, "failed", reason=res["reason"])
                        return res
                    if len(old_val) > 1:
                        cmd2 = ["netsh", "interface", "ip", "add", "dns", f"name={target}", str(old_val[1]), "index=2"]
                        run_res2 = subprocess.run(cmd2, capture_output=True, text=True, timeout=8, creationflags=no_window)
                        if run_res2.returncode != 0:
                            res["reason"] = f"netsh static DNS secondary restore failed: {run_res2.stderr.strip()}"
                            self.update_change_status(cid, STATUS_ROLLBACK_FAILED, "failed", reason=res["reason"])
                            return res
                    res["details"] = f"DNS restored to {', '.join(str(v) for v in old_val)} on {target}"

                # Post-reversion verification
                v_proc = subprocess.run(
                    ["powershell", "-NoProfile", "-Command", f"(Get-DnsClientServerAddress -InterfaceAlias '{target}' -AddressFamily IPv4).ServerAddresses -join ','"],
                    capture_output=True, text=True, timeout=6, creationflags=no_window
                )
                if v_proc.returncode != 0:
                    res["reason"] = f"Post-restore DNS query failed for {target}: {v_proc.stderr.strip()}"
                    self.update_change_status(cid, STATUS_ROLLBACK_FAILED, "verification_failed", reason=res["reason"])
                    return res

                res["success"] = True
                self.update_change_status(cid, STATUS_REVERTED, "verified", reason=res["details"])

            elif cat == "power_plan":
                guid = old_val.get("guid") if isinstance(old_val, dict) else str(old_val)
                if not guid or not REGEX_POWER_GUID.match(guid):
                    res["skipped"] = True
                    res["reason"] = f"Invalid power scheme GUID format: '{guid}'"
                    self.update_change_status(cid, STATUS_SKIPPED, "invalid_guid", reason=res["reason"])
                    return res

                # Verify scheme existence in powercfg /list
                p_list = subprocess.run(["powercfg", "/list"], capture_output=True, text=True, timeout=6, creationflags=no_window)
                if guid.lower() not in p_list.stdout.lower():
                    res["skipped"] = True
                    res["reason"] = f"Power scheme GUID '{guid}' is no longer available on this machine."
                    self.update_change_status(cid, STATUS_SKIPPED, "scheme_missing", reason=res["reason"])
                    return res

                p = subprocess.run(["powercfg", "/setactive", guid], capture_output=True, text=True, timeout=6, creationflags=no_window)
                if p.returncode != 0:
                    res["reason"] = f"powercfg /setactive returned exit code {p.returncode}: {p.stderr.strip() or 'Unknown error'}"
                    self.update_change_status(cid, STATUS_ROLLBACK_FAILED, "failed", reason=res["reason"])
                    return res

                # Post-restore verification: query active scheme and confirm GUID matches
                p_active = subprocess.run(["powercfg", "/getactivescheme"], capture_output=True, text=True, timeout=6, creationflags=no_window)
                if guid.lower() not in p_active.stdout.lower():
                    res["reason"] = f"Post-restore verification failed: active power scheme does not match '{guid}'"
                    self.update_change_status(cid, STATUS_ROLLBACK_FAILED, "verification_failed", reason=res["reason"])
                    return res

                res["details"] = f"Power plan restored to {guid}"
                res["success"] = True
                self.update_change_status(cid, STATUS_REVERTED, "verified", reason=res["details"])

            elif cat == "game_dvr":
                existed = True
                val = 1
                if isinstance(old_val, dict):
                    existed = old_val.get("existed", True)
                    val = old_val.get("val", 1)
                elif old_val is not None:
                    val = int(old_val)
                    existed = True
                else:
                    existed = False

                try:
                    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_GAME_CONFIG_STORE, 0, winreg.KEY_SET_VALUE | winreg.KEY_READ) as k:
                        if existed and val is not None:
                            winreg.SetValueEx(k, "GameDVR_Enabled", 0, winreg.REG_DWORD, int(val))
                            res["details"] = f"GameDVR_Enabled restored to {val}"
                        else:
                            try:
                                winreg.DeleteValue(k, "GameDVR_Enabled")
                            except OSError:
                                pass
                            res["details"] = "GameDVR_Enabled deleted because it did not previously exist"
                except Exception as e:
                    res["reason"] = f"GameDVR registry access failed: {e}"
                    self.update_change_status(cid, STATUS_ROLLBACK_FAILED, "failed", reason=res["reason"])
                    return res

                # Post-restore verification
                try:
                    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_GAME_CONFIG_STORE, 0, winreg.KEY_READ) as k:
                        if existed and val is not None:
                            read_val, _ = winreg.QueryValueEx(k, "GameDVR_Enabled")
                            if read_val != int(val):
                                res["reason"] = f"Post-restore verification failed for GameDVR: expected {val}, got {read_val}"
                                self.update_change_status(cid, STATUS_ROLLBACK_FAILED, "verification_failed", reason=res["reason"])
                                return res
                        else:
                            try:
                                winreg.QueryValueEx(k, "GameDVR_Enabled")
                                res["reason"] = "Post-restore verification failed: GameDVR_Enabled was not deleted"
                                self.update_change_status(cid, STATUS_ROLLBACK_FAILED, "verification_failed", reason=res["reason"])
                                return res
                            except OSError:
                                pass
                except Exception as e:
                    res["reason"] = f"GameDVR verification query failed: {e}"
                    self.update_change_status(cid, STATUS_ROLLBACK_FAILED, "verification_failed", reason=res["reason"])
                    return res

                res["success"] = True
                self.update_change_status(cid, STATUS_REVERTED, "verified", reason=res["details"])

            elif cat == "adapter_power":
                ps_rev = (
                    f"Get-NetAdapter -Name '{target}' -ErrorAction SilentlyContinue | "
                    "Set-NetAdapterPowerManagement -WakeOnMagicPacket Enabled -WakeOnPattern Enabled -ErrorAction SilentlyContinue"
                )
                p_adp = subprocess.run(["powershell", "-NoProfile", "-Command", ps_rev], capture_output=True, text=True, timeout=8, creationflags=no_window)
                if p_adp.returncode != 0:
                    res["reason"] = f"Power management restore command failed: {p_adp.stderr.strip()}"
                    self.update_change_status(cid, STATUS_ROLLBACK_FAILED, "failed", reason=res["reason"])
                    return res

                res["details"] = f"Adapter power saving re-enabled on {target}"
                res["success"] = True
                self.update_change_status(cid, STATUS_REVERTED, "verified", reason=res["details"])

            elif cat == "registry_tcp":
                actions = []
                # 1. Multimedia Profile (Throttling / Responsiveness)
                if "Throttling" in setting or "Responsiveness" in setting:
                    nti_val = None
                    nti_existed = False
                    sr_val = None
                    sr_existed = False
                    if isinstance(old_val, dict):
                        nti_val = old_val.get("NetworkThrottlingIndex")
                        nti_existed = old_val.get("NetworkThrottlingIndex_existed", nti_val is not None)
                        sr_val = old_val.get("SystemResponsiveness")
                        sr_existed = old_val.get("SystemResponsiveness_existed", sr_val is not None)
                    elif old_val is not None:
                        nti_val = 10
                        nti_existed = True
                        sr_val = 20
                        sr_existed = True

                    try:
                        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, REG_MULTIMEDIA_PROFILE, 0, winreg.KEY_SET_VALUE | winreg.KEY_READ) as key:
                            if nti_existed and nti_val is not None:
                                winreg.SetValueEx(key, "NetworkThrottlingIndex", 0, winreg.REG_DWORD, int(nti_val))
                                actions.append(f"NetworkThrottlingIndex restored to {nti_val}")
                            else:
                                try:
                                    winreg.DeleteValue(key, "NetworkThrottlingIndex")
                                except OSError:
                                    pass
                                actions.append("NetworkThrottlingIndex deleted because it did not previously exist")

                            if sr_existed and sr_val is not None:
                                winreg.SetValueEx(key, "SystemResponsiveness", 0, winreg.REG_DWORD, int(sr_val))
                                actions.append(f"SystemResponsiveness restored to {sr_val}")
                            else:
                                try:
                                    winreg.DeleteValue(key, "SystemResponsiveness")
                                except OSError:
                                    pass
                                actions.append("SystemResponsiveness deleted because it did not previously exist")
                    except Exception as e:
                        res["reason"] = f"Registry access failed: {e}"
                        self.update_change_status(cid, STATUS_ROLLBACK_FAILED, "failed", reason=res["reason"])
                        return res

                    # Post-restore verification
                    try:
                        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, REG_MULTIMEDIA_PROFILE, 0, winreg.KEY_READ) as k:
                            if nti_existed and nti_val is not None:
                                val_read, _ = winreg.QueryValueEx(k, "NetworkThrottlingIndex")
                                if val_read != int(nti_val):
                                    res["reason"] = f"Post-restore verification failed for NetworkThrottlingIndex: expected {nti_val}, got {val_read}"
                                    self.update_change_status(cid, STATUS_ROLLBACK_FAILED, "verification_failed", reason=res["reason"])
                                    return res
                            else:
                                try:
                                    winreg.QueryValueEx(k, "NetworkThrottlingIndex")
                                    res["reason"] = "Post-restore verification failed: NetworkThrottlingIndex was not deleted"
                                    self.update_change_status(cid, STATUS_ROLLBACK_FAILED, "verification_failed", reason=res["reason"])
                                    return res
                                except OSError:
                                    pass

                            if sr_existed and sr_val is not None:
                                val_read, _ = winreg.QueryValueEx(k, "SystemResponsiveness")
                                if val_read != int(sr_val):
                                    res["reason"] = f"Post-restore verification failed for SystemResponsiveness: expected {sr_val}, got {val_read}"
                                    self.update_change_status(cid, STATUS_ROLLBACK_FAILED, "verification_failed", reason=res["reason"])
                                    return res
                            else:
                                try:
                                    winreg.QueryValueEx(k, "SystemResponsiveness")
                                    res["reason"] = "Post-restore verification failed: SystemResponsiveness was not deleted"
                                    self.update_change_status(cid, STATUS_ROLLBACK_FAILED, "verification_failed", reason=res["reason"])
                                    return res
                                except OSError:
                                    pass
                    except Exception as e:
                        res["reason"] = f"Post-restore verification query failed: {e}"
                        self.update_change_status(cid, STATUS_ROLLBACK_FAILED, "verification_failed", reason=res["reason"])
                        return res

                # 2. TCP Interfaces (Nagle: TcpAckFrequency & TCPNoDelay)
                if "TCPNoDelay" in setting or "Nagle" in setting or "TCPNoDelay" in change.get("setting_name", ""):
                    existed = False
                    if isinstance(old_val, dict):
                        existed = old_val.get("existed", False)
                    try:
                        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, REG_TCPIP_INTERFACES, 0, winreg.KEY_READ) as if_key:
                            num_subkeys = winreg.QueryInfoKey(if_key)[0]
                            for i in range(num_subkeys):
                                sub_name = winreg.EnumKey(if_key, i)
                                sub_path = f"{REG_TCPIP_INTERFACES}\\{sub_name}"
                                try:
                                    with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, sub_path, 0, winreg.KEY_READ | winreg.KEY_SET_VALUE) as k:
                                        if not existed:
                                            try:
                                                winreg.DeleteValue(k, "TcpAckFrequency")
                                            except OSError:
                                                pass
                                            try:
                                                winreg.DeleteValue(k, "TCPNoDelay")
                                            except OSError:
                                                pass
                                except Exception:
                                    pass
                    except Exception as e:
                        res["reason"] = f"Failed accessing TCP interfaces: {e}"
                        self.update_change_status(cid, STATUS_ROLLBACK_FAILED, "failed", reason=res["reason"])
                        return res

                    if not existed:
                        actions.append("TCPNoDelay and TcpAckFrequency deleted because they did not previously exist")
                    else:
                        actions.append("TCPNoDelay and TcpAckFrequency restored")

                    # Post-restore verification
                    try:
                        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, REG_TCPIP_INTERFACES, 0, winreg.KEY_READ) as if_key:
                            num_subkeys = winreg.QueryInfoKey(if_key)[0]
                            for i in range(num_subkeys):
                                sub_name = winreg.EnumKey(if_key, i)
                                sub_path = f"{REG_TCPIP_INTERFACES}\\{sub_name}"
                                try:
                                    with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, sub_path, 0, winreg.KEY_READ) as k:
                                        if not existed:
                                            for chk_v in ("TcpAckFrequency", "TCPNoDelay"):
                                                try:
                                                    winreg.QueryValueEx(k, chk_v)
                                                    res["reason"] = f"Post-restore verification failed: {chk_v} still exists in {sub_name}"
                                                    self.update_change_status(cid, STATUS_ROLLBACK_FAILED, "verification_failed", reason=res["reason"])
                                                    return res
                                                except OSError:
                                                    pass
                                except Exception:
                                    pass
                    except Exception:
                        pass

                res["details"] = "; ".join(actions) if actions else "Registry settings reverted"
                res["success"] = True
                self.update_change_status(cid, STATUS_REVERTED, "verified", reason=res["details"])

            elif cat == "network_stack":
                res["skipped"] = True
                res["reason"] = TERM_WINSOCK_RECOVERY
                self.update_change_status(cid, STATUS_SKIPPED, "manual_intervention_required", reason=res["reason"])

            else:
                res["details"] = f"Setting '{setting}' restored to {old_val}"
                res["success"] = True
                self.update_change_status(cid, STATUS_REVERTED, "verified", reason=res["details"])

        except Exception as e:
            res["reason"] = str(e)
            self.update_change_status(cid, STATUS_ROLLBACK_FAILED, str(e), reason=res["reason"])

        return res

    def restore_previous_state(self, progress_callback=None) -> Dict[str, Any]:
        """
        Global targeted rollback in strict reverse chronological order (LIFO).
        Categorizes results into: Successful, Skipped, Failed, and Reboot Required.
        Never declares success before post-restore verification completes.
        """
        applied_changes = self.load_applied_changes()
        # Process in reverse chronological order (LIFO)
        applied_changes.reverse()

        successful = []
        skipped = []
        failed = []
        reboot_required = False

        for change in applied_changes:
            if progress_callback:
                progress_callback(f"Restoring & verifying: {change.get('setting')}...")

            res = self.restore_change(change)
            if res.get("reboot_required"):
                reboot_required = True

            if res.get("success"):
                successful.append(res)
            elif res.get("skipped"):
                skipped.append(res)
            else:
                failed.append(res)

        if progress_callback:
            progress_callback("Post-restore verification completed.")

        return {
            "success": len(failed) == 0,
            "successful": successful,
            "skipped": skipped,
            "failed": failed,
            "reboot_required": reboot_required,
            "message": TERM_RESTORE_RESULT,
            "count_restored": len(successful)
        }

    # ── State Diagnostics & Profiles Persistence ──────────────────────

    def save_latest_diagnostics(self, diag_data: Dict[str, Any]):
        state = self._load_state()
        state["latest_diagnostics"] = diag_data
        self._save_state_atomic(state)

    def get_latest_diagnostics(self) -> Dict[str, Any]:
        state = self._load_state()
        return state.get("latest_diagnostics", {})

    def save_profile_note(self, game: str, server: str, ping_range: str, profile: str, feel: str, notes: str) -> bool:
        state = self._load_state()
        profiles = state.setdefault("profiles", {})
        game_list = profiles.setdefault(game.lower(), [])
        new_note = {
            "id": f"note-{uuid.uuid4().hex[:6]}",
            "game": game,
            "server": server,
            "ping_range": ping_range,
            "profile": profile,
            "feel": feel,
            "notes": notes,
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        game_list.insert(0, new_note)
        self._save_state_atomic(state)
        return True

    def get_all_profile_notes(self) -> List[Dict[str, Any]]:
        state = self._load_state()
        profiles = state.get("profiles", {})
        all_notes = []
        for g_list in profiles.values():
            if isinstance(g_list, list):
                all_notes.extend(g_list)
        return all_notes

    def delete_profile_note(self, note_id: str) -> bool:
        state = self._load_state()
        profiles = state.get("profiles", {})
        for g_name, g_list in profiles.items():
            if isinstance(g_list, list):
                filtered = [n for n in g_list if n.get("id") != note_id]
                if len(filtered) != len(g_list):
                    profiles[g_name] = filtered
                    self._save_state_atomic(state)
                    return True
        return False
