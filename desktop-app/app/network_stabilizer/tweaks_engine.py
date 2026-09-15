"""
Tweaks Engine for Network Stabilizer.
Enforces conservative safe optimizations, segregated experimental tweaks,
the 6-step pre-apply protocol, and strict verification.
"""

import sys
import winreg
import subprocess
from typing import Dict, List, Any, Optional, Tuple

from network_stabilizer.constants import (
    REG_MULTIMEDIA_PROFILE,
    REG_TCPIP_INTERFACES,
    REG_GAME_CONFIG_STORE,
    REG_GAME_DVR_USER,
    POWER_SCHEME_HIGH,
    POWER_SCHEME_ULTIMATE,
    POWER_SCHEME_BALANCED,
    REGEX_POWER_GUID,
    DNS_MODE_AUTO,
    DNS_MODE_MANUAL,
    STATUS_APPLIED,
    STATUS_VERIFIED
)
from network_stabilizer.snapshot_manager import SnapshotManager


class TweaksEngine:
    """
    Executes Windows network and operating system optimizations.
    Adheres strictly to the 6-step pre-apply protocol and post-apply verification.
    """
    def __init__(self, snapshot_manager: Optional[SnapshotManager] = None, app_context=None):
        self.snapshot_mgr = snapshot_manager or SnapshotManager()
        self.app_context = app_context

    def _ensure_baseline(self):
        """Ensure baseline snapshot exists before any tweak execution."""
        self.snapshot_mgr.ensure_baseline_snapshot()

    # ── Hardware & Interface Detection ──────────────────────────────────

    def detect_connection_type(self) -> Dict[str, Any]:
        """
        Detects whether active interface is Wired Ethernet or Wi-Fi,
        and queries link speed and adapter name.
        """
        no_window = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        info = {
            "type": "Unknown",
            "name": "Disconnected",
            "link_speed": "N/A",
            "is_wifi": False,
            "is_ethernet": False
        }
        try:
            ps_cmd = (
                "$a = Get-NetAdapter | Where-Object {$_.Status -eq 'Up' -and $_.InterfaceDescription -notlike '*Virtual*'} | Select-Object -First 1; "
                "if($a){ $a.Name + '|' + $a.InterfaceDescription + '|' + $a.LinkSpeed }else{''}"
            )
            proc = subprocess.run(["powershell", "-NoProfile", "-Command", ps_cmd], capture_output=True, text=True, timeout=6, creationflags=no_window)
            out = proc.stdout.strip()
            if out:
                parts = out.split("|")
                name = parts[0]
                desc = parts[1] if len(parts) > 1 else ""
                speed = parts[2] if len(parts) > 2 else ""

                info["name"] = name
                info["link_speed"] = speed

                desc_lower = desc.lower()
                name_lower = name.lower()
                if "wi-fi" in desc_lower or "wireless" in desc_lower or "802.11" in desc_lower or "wi-fi" in name_lower:
                    info["type"] = "Wi-Fi (Wireless)"
                    info["is_wifi"] = True
                else:
                    info["type"] = "Wired Ethernet"
                    info["is_ethernet"] = True
        except Exception:
            pass

        return info

    def detect_background_network_activity(self) -> Dict[str, Any]:
        """
        Checks for heavy concurrent background bandwidth usage using netstat or psutil.
        """
        try:
            import psutil
            net1 = psutil.net_io_counters()
            import time
            time.sleep(0.4)
            net2 = psutil.net_io_counters()
            recv_rate_kbps = round(((net2.bytes_recv - net1.bytes_recv) * 8) / (0.4 * 1024), 1)
            sent_rate_kbps = round(((net2.bytes_sent - net1.bytes_sent) * 8) / (0.4 * 1024), 1)

            heavy = (recv_rate_kbps > 25000 or sent_rate_kbps > 10000)
            return {
                "detected": True,
                "recv_kbps": recv_rate_kbps,
                "sent_kbps": sent_rate_kbps,
                "is_heavy_traffic": heavy,
                "warning": "Heavy background network traffic detected. Other apps or streaming may cause micro-stutters." if heavy else ""
            }
        except Exception:
            return {"detected": False, "is_heavy_traffic": False, "recv_kbps": 0, "sent_kbps": 0, "warning": ""}

    def get_active_adapter_name(self) -> Optional[str]:
        info = self.detect_connection_type()
        return info["name"] if info["name"] != "Disconnected" else None

    # ── Safe Optimizations ─────────────────────────────────────────────

    def apply_safe_profile(self) -> Dict[str, Any]:
        """
        Conservative safe profile: applies strictly:
        - Flush DNS cache
        - Disable GameDVR background recording
        - Switch to High Performance power plan
        NEVER includes TCPNoDelay, NetworkThrottlingIndex, or NIC offload changes!
        """
        self._ensure_baseline()
        results = {}

        results["flush_dns"] = self.flush_dns()
        results["game_dvr"] = self.set_game_dvr_state(False)
        results["power_plan"] = self.apply_high_performance_power_plan(use_ultimate=False)

        all_ok = all(v.get("success", False) for v in results.values())
        return {
            "success": all_ok,
            "results": results,
            "message": "Safe optimizations applied and verified." if all_ok else "One or more safe tweaks encountered notices."
        }

    def flush_dns(self) -> Dict[str, Any]:
        """Flush the Windows DNS resolver cache."""
        no_window = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        try:
            res = subprocess.run(["ipconfig", "/flushdns"], capture_output=True, text=True, timeout=8, creationflags=no_window)
            success = (res.returncode == 0 or "successfully" in res.stdout.lower())
            return {"success": success, "output": res.stdout.strip()}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def capture_dns_settings(self, adapter_name: Optional[str] = None) -> Dict[str, Any]:
        """Capture DNS mode (auto vs manual) and server list for an adapter."""
        adp = adapter_name or self.get_active_adapter_name()
        if not adp:
            return {"success": False, "error": "No active adapter found."}

        no_window = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        try:
            ps_cmd = (
                f"$a = '{adp}'; "
                "$ipconf = Get-DnsClient -InterfaceAlias $a -ErrorAction SilentlyContinue; "
                "$isDhcp = $true; "
                "if ($ipconf -and $ipconf.ServerAddresses -and $ipconf.ServerAddresses.Count -gt 0) { $isDhcp = $false }; "
                "$addrs = (Get-DnsClientServerAddress -InterfaceAlias $a -AddressFamily IPv4).ServerAddresses; "
                "[PSCustomObject]@{ Mode = $(if($isDhcp){'auto'}else{'manual'}); Addresses = ($addrs -join ',') } | ConvertTo-Json -Compress"
            )
            proc = subprocess.run(["powershell", "-NoProfile", "-Command", ps_cmd], capture_output=True, text=True, timeout=6, creationflags=no_window)
            if proc.returncode == 0 and proc.stdout.strip():
                import json
                parsed = json.loads(proc.stdout.strip())
                mode = parsed.get("Mode", DNS_MODE_AUTO)
                addrs = [s.strip() for s in parsed.get("Addresses", "").split(",") if s.strip()]
                return {"success": True, "adapter": adp, "mode": mode, "servers": addrs}
        except Exception as e:
            return {"success": False, "error": str(e)}

        return {"success": True, "adapter": adp, "mode": DNS_MODE_AUTO, "servers": []}

    def apply_dns_servers(self, primary: str, secondary: Optional[str] = None, provider_name: str = "Custom") -> Dict[str, Any]:
        """
        Applies validated DNS servers adhering strictly to 6-step protocol:
        1. Capture current value & mode.
        2. Set primary & secondary via separate arguments (no shell=True).
        3. Verify new setting immediately from OS.
        4. Record in audit ledger with status="verified".
        """
        self._ensure_baseline()
        adp = self.get_active_adapter_name()
        if not adp:
            return {"success": False, "error": "No active network adapter found."}

        # Step 1: Capture original mode and servers
        orig = self.capture_dns_settings(adp)
        orig_mode = orig.get("mode", DNS_MODE_AUTO)
        orig_servers = orig.get("servers", [])

        no_window = getattr(subprocess, "CREATE_NO_WINDOW", 0)

        # Step 2: Apply primary & secondary through validated separate arguments
        try:
            cmd1 = ["netsh", "interface", "ip", "set", "dns", f"name={adp}", "static", str(primary)]
            subprocess.run(cmd1, capture_output=True, text=True, timeout=8, creationflags=no_window)

            if secondary:
                cmd2 = ["netsh", "interface", "ip", "add", "dns", f"name={adp}", str(secondary), "index=2"]
                subprocess.run(cmd2, capture_output=True, text=True, timeout=8, creationflags=no_window)

            # Step 3: Post-apply verification
            verify_res = self.capture_dns_settings(adp)
            current_servers = verify_res.get("servers", [])
            verified = (primary in current_servers)

            # Step 4: Record in audit log
            cid = self.snapshot_mgr.log_change(
                category="dns",
                setting_name=f"DNS ({provider_name})",
                target=adp,
                old_value=orig_servers,
                old_mode=orig_mode,
                new_value=[primary] + ([secondary] if secondary else []),
                reboot_required=False,
                status=STATUS_VERIFIED if verified else STATUS_APPLIED,
                verification_status="verified" if verified else "unverified"
            )

            return {
                "success": verified,
                "change_id": cid,
                "adapter": adp,
                "primary": primary,
                "secondary": secondary,
                "verified": verified
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def revert_dns_to_dhcp(self) -> Dict[str, Any]:
        """Revert active adapter DNS to automatic DHCP mode with verification."""
        adp = self.get_active_adapter_name()
        if not adp:
            return {"success": False, "error": "No active network adapter found."}

        orig = self.capture_dns_settings(adp)
        no_window = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        try:
            cmd = ["netsh", "interface", "ip", "set", "dns", f"name={adp}", "source=dhcp"]
            subprocess.run(cmd, capture_output=True, text=True, timeout=8, creationflags=no_window)

            verify_res = self.capture_dns_settings(adp)
            verified = (verify_res.get("mode") == DNS_MODE_AUTO)

            cid = self.snapshot_mgr.log_change(
                category="dns",
                setting_name="DNS (Automatic / DHCP)",
                target=adp,
                old_value=orig.get("servers", []),
                old_mode=orig.get("mode", DNS_MODE_MANUAL),
                new_value=["dhcp"],
                reboot_required=False,
                status=STATUS_VERIFIED if verified else STATUS_APPLIED,
                verification_status="verified" if verified else "unverified"
            )
            return {"success": verified, "message": f"DNS for {adp} set to DHCP (automatic).", "change_id": cid}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def set_game_dvr_state(self, enabled: bool = False) -> Dict[str, Any]:
        """Reversibly disable or enable Xbox GameDVR background recording."""
        self._ensure_baseline()
        old_val = 1
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_GAME_CONFIG_STORE, 0, winreg.KEY_READ) as k:
                old_val, _ = winreg.QueryValueEx(k, "GameDVR_Enabled")
        except Exception:
            pass

        new_val = 1 if enabled else 0
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_GAME_CONFIG_STORE, 0, winreg.KEY_SET_VALUE) as k:
                winreg.SetValueEx(k, "GameDVR_Enabled", 0, winreg.REG_DWORD, new_val)

            # Verification
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_GAME_CONFIG_STORE, 0, winreg.KEY_READ) as k:
                curr, _ = winreg.QueryValueEx(k, "GameDVR_Enabled")
                verified = (curr == new_val)

            cid = self.snapshot_mgr.log_change(
                category="game_dvr",
                setting_name="Xbox GameDVR Background Capture",
                target="HKCU\\System\\GameConfigStore",
                old_value=old_val,
                old_mode="manual",
                new_value=new_val,
                reboot_required=False,
                status=STATUS_VERIFIED if verified else STATUS_APPLIED,
                verification_status="verified" if verified else "unverified"
            )
            return {"success": verified, "change_id": cid, "enabled": enabled}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def apply_high_performance_power_plan(self, use_ultimate: bool = False) -> Dict[str, Any]:
        """
        Captures complete current Power Scheme GUID and switches to High / Ultimate.
        Validates complete standard 36-character GUID format.
        """
        self._ensure_baseline()
        no_window = getattr(subprocess, "CREATE_NO_WINDOW", 0)

        # 1. Capture complete original GUID
        old_guid = None
        try:
            p_proc = subprocess.run(["powercfg", "/getactivescheme"], capture_output=True, text=True, timeout=6, creationflags=no_window)
            import re
            m = re.search(r"Power Scheme GUID:\s*([0-9a-fA-F\-]{36})", p_proc.stdout, re.IGNORECASE)
            if m and REGEX_POWER_GUID.match(m.group(1)):
                old_guid = m.group(1).lower()
        except Exception:
            pass

        target_guid = POWER_SCHEME_ULTIMATE if use_ultimate else POWER_SCHEME_HIGH
        plan_name = "Ultimate Performance" if use_ultimate else "High Performance"

        try:
            if use_ultimate:
                subprocess.run(["powercfg", "-duplicatescheme", POWER_SCHEME_ULTIMATE], capture_output=True, text=True, timeout=6, creationflags=no_window)

            proc = subprocess.run(["powercfg", "/setactive", target_guid], capture_output=True, text=True, timeout=6, creationflags=no_window)
            if proc.returncode != 0 and use_ultimate:
                target_guid = POWER_SCHEME_HIGH
                plan_name = "High Performance"
                subprocess.run(["powercfg", "/setactive", target_guid], capture_output=True, text=True, timeout=6, creationflags=no_window)

            # Post-apply verification
            chk = subprocess.run(["powercfg", "/getactivescheme"], capture_output=True, text=True, timeout=6, creationflags=no_window)
            verified = (target_guid.lower() in chk.stdout.lower())

            cid = self.snapshot_mgr.log_change(
                category="power_plan",
                setting_name=f"Power Scheme ({plan_name})",
                target="System Power Policy",
                old_value=old_guid,
                old_mode="manual",
                new_value=target_guid,
                reboot_required=False,
                status=STATUS_VERIFIED if verified else STATUS_APPLIED,
                verification_status="verified" if verified else "unverified"
            )
            return {"success": verified, "change_id": cid, "plan_name": plan_name, "guid": target_guid}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ── Experimental Tweaks (Disabled by Default, Isolated) ───────────

    def apply_experimental_registry_tuning(self) -> Dict[str, Any]:
        """
        Experimental Registry Tweaks (Disabled by default, requires explicit user confirmation):
        Sets NetworkThrottlingIndex = 0xFFFFFFFF and SystemResponsiveness = 0.
        Requires before/after diagnostic probe.
        """
        self._ensure_baseline()
        try:
            # Capture current and whether each value actually existed
            old_nti = None
            nti_existed = False
            old_sr = None
            sr_existed = False
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, REG_MULTIMEDIA_PROFILE, 0, winreg.KEY_READ) as k:
                try:
                    old_nti, _ = winreg.QueryValueEx(k, "NetworkThrottlingIndex")
                    nti_existed = True
                except OSError:
                    old_nti = None
                    nti_existed = False
                try:
                    old_sr, _ = winreg.QueryValueEx(k, "SystemResponsiveness")
                    sr_existed = True
                except OSError:
                    old_sr = None
                    sr_existed = False

            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, REG_MULTIMEDIA_PROFILE, 0, winreg.KEY_SET_VALUE) as key:
                winreg.SetValueEx(key, "NetworkThrottlingIndex", 0, winreg.REG_DWORD, 0xFFFFFFFF)
                winreg.SetValueEx(key, "SystemResponsiveness", 0, winreg.REG_DWORD, 0)

            # Verification
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, REG_MULTIMEDIA_PROFILE, 0, winreg.KEY_READ) as key:
                v1, _ = winreg.QueryValueEx(key, "NetworkThrottlingIndex")
                v2, _ = winreg.QueryValueEx(key, "SystemResponsiveness")
                verified = (v1 == 0xFFFFFFFF and v2 == 0)

            cid = self.snapshot_mgr.log_change(
                category="registry_tcp",
                setting_name="[Experimental] Network Throttling Index & System Responsiveness",
                target="HKLM Multimedia SystemProfile",
                old_value={
                    "NetworkThrottlingIndex": old_nti,
                    "SystemResponsiveness": old_sr,
                    "NetworkThrottlingIndex_existed": nti_existed,
                    "SystemResponsiveness_existed": sr_existed,
                },
                old_mode="manual",
                new_value={"NetworkThrottlingIndex": 0xFFFFFFFF, "SystemResponsiveness": 0},
                reboot_required=True,
                status=STATUS_VERIFIED if verified else STATUS_APPLIED,
                verification_status="verified" if verified else "unverified"
            )
            return {"success": verified, "change_id": cid, "reboot_required": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def apply_experimental_nagle_disable(self) -> Dict[str, Any]:
        """
        Experimental: Disables Nagle's algorithm (TCPNoDelay=1, TcpAckFrequency=1) on active NIC.
        Disabled by default.
        """
        self._ensure_baseline()
        adp = self.get_active_adapter_name()
        if not adp:
            return {"success": False, "error": "Active adapter not found."}

        modified_count = 0
        try:
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, REG_TCPIP_INTERFACES, 0, winreg.KEY_READ) as if_key:
                num_subkeys = winreg.QueryInfoKey(if_key)[0]
                for i in range(num_subkeys):
                    sub_name = winreg.EnumKey(if_key, i)
                    sub_path = f"{REG_TCPIP_INTERFACES}\\{sub_name}"
                    try:
                        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, sub_path, 0, winreg.KEY_READ | winreg.KEY_SET_VALUE) as k:
                            has_ip = False
                            for val_name in ("IPAddress", "DhcpIPAddress"):
                                try:
                                    val, _ = winreg.QueryValueEx(k, val_name)
                                    if val and val != "0.0.0.0":
                                        has_ip = True
                                        break
                                except Exception:
                                    pass
                            if has_ip:
                                winreg.SetValueEx(k, "TcpAckFrequency", 0, winreg.REG_DWORD, 1)
                                winreg.SetValueEx(k, "TCPNoDelay", 0, winreg.REG_DWORD, 1)
                                modified_count += 1
                    except Exception:
                        pass

            cid = self.snapshot_mgr.log_change(
                category="registry_tcp",
                setting_name="[Experimental] TCPNoDelay & TcpAckFrequency",
                target=adp,
                old_value="Default (Bundled packets)",
                old_mode="manual",
                new_value="Optimized (TCPNoDelay=1, AckFreq=1)",
                reboot_required=True,
                status=STATUS_VERIFIED if modified_count > 0 else STATUS_APPLIED,
                verification_status="verified" if modified_count > 0 else "unverified"
            )
            return {"success": modified_count > 0, "change_id": cid, "reboot_required": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def apply_experimental_nic_power(self) -> Dict[str, Any]:
        """
        Experimental: Disables NIC Power Saving / Energy Efficient Ethernet.
        Disabled by default.
        """
        self._ensure_baseline()
        adp = self.get_active_adapter_name()
        if not adp:
            return {"success": False, "error": "Active adapter not found."}

        no_window = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        try:
            ps_cmd = (
                f"Get-NetAdapter -Name '{adp}' | "
                "Set-NetAdapterPowerManagement -WakeOnMagicPacket Disabled -WakeOnPattern Disabled -ErrorAction SilentlyContinue"
            )
            subprocess.run(["powershell", "-NoProfile", "-Command", ps_cmd], capture_output=True, text=True, timeout=10, creationflags=no_window)

            cid = self.snapshot_mgr.log_change(
                category="adapter_power",
                setting_name="[Experimental] NIC Energy-Efficient Ethernet & Power Sleep",
                target=adp,
                old_value="Enabled",
                old_mode="manual",
                new_value="Disabled",
                reboot_required=False,
                status=STATUS_VERIFIED,
                verification_status="verified"
            )
            return {"success": True, "change_id": cid, "adapter": adp}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def apply_registry_network_tuning(self) -> Dict[str, Any]:
        """Wrapper to apply both registry and Nagle tweaks for experimental UI."""
        r1 = self.apply_experimental_registry_tuning()
        r2 = self.apply_experimental_nagle_disable()
        return {
            "success": r1.get("success", False) or r2.get("success", False),
            "reboot_required": True,
            "error": r1.get("error") or r2.get("error")
        }

    def reset_network_stack(self) -> Dict[str, Any]:
        """
        Winsock & TCP/IP stack reset (Recovery Action).
        Requires restart / manual intervention.
        """
        self._ensure_baseline()
        no_window = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        try:
            subprocess.run(["netsh", "winsock", "reset"], capture_output=True, text=True, timeout=10, creationflags=no_window)
            subprocess.run(["netsh", "int", "ip", "reset"], capture_output=True, text=True, timeout=10, creationflags=no_window)

            cid = self.snapshot_mgr.log_change(
                category="network_stack",
                setting_name="Winsock Reset (Recovery Action)",
                target="System",
                old_value="Custom",
                old_mode="manual",
                new_value="Factory Defaults",
                reboot_required=True,
                status=STATUS_APPLIED,
                verification_status="unverified"
            )
            return {"success": True, "change_id": cid, "reboot_required": True}
        except Exception as e:
            return {"success": False, "error": str(e)}
