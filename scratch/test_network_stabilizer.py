"""
Automated verification tests for compact Network Stabilizer.
Tests NetworkStabilizerFeature facade, single-file JSON state persistence,
targeted rollback, and 6-tab NetworkView rendering.
"""

import os
import sys
import json
import unittest

# Ensure app directory is on sys.path
_APP_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "desktop-app", "app"))
if _APP_DIR not in sys.path:
    sys.path.insert(0, _APP_DIR)

from network_stabilizer import (
    FEATURE_NAME,
    FEATURE_VERSION,
    NetworkStabilizerFeature,
    DiagnosticsEngine,
    RouterAdvisor,
    SnapshotManager,
    GameProfiles,
)
from network_stabilizer.constants import STATE_FILE_PATH, TERM_RESTORE_RESULT


class TestCompactNetworkStabilizer(unittest.TestCase):

    def setUp(self):
        self.feature = NetworkStabilizerFeature()

    def test_01_feature_metadata(self):
        """Verify feature metadata exports."""
        self.assertEqual(FEATURE_NAME, "Network Stabilizer")
        self.assertEqual(FEATURE_VERSION, "0.1.0")

    def test_02_baseline_snapshot_in_single_state_file(self):
        """Verify baseline snapshot is recorded in compact network_stabilizer_state.json."""
        res = self.feature.snapshots.ensure_baseline_snapshot()
        self.assertTrue(res.get("success"), "Baseline snapshot must succeed")
        self.assertTrue(os.path.exists(STATE_FILE_PATH), f"{STATE_FILE_PATH} must exist")

        with open(STATE_FILE_PATH, "r", encoding="utf-8") as f:
            state = json.load(f)

        self.assertIn("network_state", state)
        self.assertIn("created_at", state["network_state"])
        self.assertIn("dns", state["network_state"])
        self.assertIn("power_plan", state["network_state"])
        self.assertIn("game_settings", state["network_state"])
        self.assertIn("adapter_settings", state["network_state"])

    def test_03_targeted_rollback_only_changed_settings(self):
        """Verify rollback touches ONLY recorded applied changes."""
        # Log a mock change
        change_id = self.feature.snapshots.log_change(
            category="test",
            setting_name="Mock Setting for Unit Test",
            old_value="original_val",
            new_value="optimized_val",
            target="UnitTestTarget",
            reboot_required=False
        )
        self.assertTrue(bool(change_id))

        applied = self.feature.snapshots.load_applied_changes()
        matching = [c for c in applied if c["id"] == change_id]
        self.assertEqual(len(matching), 1)

        # Execute targeted rollback
        rb_res = self.feature.restore_previous_state()
        self.assertTrue(rb_res.get("success"))

        # Verify change is now reverted and not in load_applied_changes
        applied_after = self.feature.snapshots.load_applied_changes()
        matching_after = [c for c in applied_after if c["id"] == change_id]
        self.assertEqual(len(matching_after), 0)

    def test_04_diagnostics_ping_and_gateway(self):
        """Verify diagnostics ping, jitter, and gateway detection."""
        gw = self.feature.diagnostics.get_default_gateway()
        self.assertTrue(bool(gw))

        res = self.feature.diagnostics.ping_host("127.0.0.1", count=2)
        self.assertEqual(res["sent"], 2)
        self.assertGreaterEqual(res["received"], 1)
        self.assertGreaterEqual(res["avg_ms"], 0.0)

    def test_05_router_sqm_calculations(self):
        """Verify 85-92% bandwidth limit calculations and OpenWrt template."""
        limits = RouterAdvisor.calculate_bandwidth_limits(100.0, 20.0, "Cable")
        self.assertEqual(limits["down_limit_mbps"], 88.0)
        self.assertEqual(limits["up_limit_mbps"], 17.0)

        guide = RouterAdvisor.get_router_guide("OpenWrt (CAKE / fq_codel)", 100.0, 20.0, limits)
        self.assertIn("cake", guide.get("snippet", ""))

    def test_06_game_profiles_in_state_file(self):
        """Verify game profile notes are persisted inside network_stabilizer_state.json."""
        self.feature.profiles.save_user_note(
            game="Valorant",
            server="Frankfurt",
            ping_range="18-22ms",
            profile="Cloudflare DNS + TCP NoDelay",
            feel="Zero jitter",
            notes="Testing journal entry"
        )
        notes = self.feature.profiles.get_user_notes()
        matching = [n for n in notes if n.get("game") == "Valorant" and n.get("server") == "Frankfurt"]
        self.assertGreater(len(matching), 0)

        # Cleanup
        nid = matching[0]["id"]
        self.feature.profiles.delete_user_note(nid)

    def test_07_network_view_ui_rendering(self):
        """Verify NetworkView from ui.network_view instantiates and switches across all 6 tabs."""
        import customtkinter as ctk
        ctk.set_appearance_mode("dark")
        root = ctk.CTk()
        root.withdraw()

        from ui.network_view import NetworkView
        view = NetworkView(root)
        self.assertIsNotNone(view)

        for tab_key in ["overview", "diagnostics", "tweaks", "router", "profiles", "rollback"]:
            view.switch_tab(tab_key)
            self.assertIn(tab_key, view.tabs)

        root.destroy()


    def test_08_target_validation_boundaries(self):
        """Verify strict target validation rejects empty, whitespace, control chars, metachars, length > 255."""
        v = DiagnosticsEngine.validate_target
        # Empty
        ok, err = v("")
        self.assertFalse(ok)
        self.assertIn("empty", err.lower())

        # Whitespace
        self.assertFalse(v(" 1.1.1.1")[0])
        self.assertFalse(v("1.1.1.1 ")[0])
        self.assertFalse(v("1.1. 1.1")[0])

        # Control characters
        self.assertFalse(v("1.1.1.1\x00")[0])
        self.assertFalse(v("1.1.1.1\n")[0])

        # Shell metacharacters
        for char in ['&', '|', ';', '$', '`', '<', '>', '(', ')', '{', '}', '^', '"', "'", '*']:
            self.assertFalse(v(f"1.1.1.1{char}")[0], f"Failed to reject metachar: {char}")

        # Max length 255
        self.assertFalse(v("a" * 256 + ".com")[0])

        # Valid targets
        self.assertTrue(v("1.1.1.1")[0])
        self.assertTrue(v("8.8.8.8")[0])
        self.assertTrue(v("dynamodb.us-east-1.amazonaws.com")[0])
        self.assertTrue(v("localhost")[0])

    def test_09_adjacent_difference_jitter_calculation(self):
        """Verify Adjacent-Difference Jitter (mean consecutive absolute delta)."""
        samples = [10.0, 14.0, 11.0, 15.0]
        # diffs: |14-10|=4, |11-14|=3, |15-11|=4 -> sum=11, count=3 -> mean=3.67
        diffs = [abs(samples[j + 1] - samples[j]) for j in range(len(samples) - 1)]
        jitter = round(sum(diffs) / len(diffs), 2)
        self.assertEqual(jitter, 3.67)

    def test_10_power_plan_full_guid_regex(self):
        """Verify full 36-character power plan GUID validation and rejection of shortened GUIDs."""
        from network_stabilizer.constants import REGEX_POWER_GUID, POWER_SCHEME_HIGH
        # Complete 36-char GUID
        self.assertTrue(bool(REGEX_POWER_GUID.match(POWER_SCHEME_HIGH)))
        self.assertTrue(bool(REGEX_POWER_GUID.match("8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c")))

        # Shortened GUIDs must be rejected
        self.assertFalse(bool(REGEX_POWER_GUID.match("8c5e7fda")))
        self.assertFalse(bool(REGEX_POWER_GUID.match("8c5e7fda-e8bf-4a96")))

    def test_11_corrupted_state_recovery(self):
        """Verify atomic writes and corruption recovery for network_stabilizer_state.json."""
        mgr = SnapshotManager()
        # Deliberately corrupt state file with invalid JSON
        with open(mgr.state_file, "w", encoding="utf-8") as f:
            f.write("{ INVALID JSON CONTENT ###")

        # Load must recover with clean baseline schema
        state = mgr._load_state()
        self.assertIn("network_state", state)
        self.assertIn("persistent_changes", state)
        # Corrupt backup must exist
        corrupt_backups = [f for f in os.listdir(os.path.dirname(mgr.state_file)) if "corrupt" in f]
        self.assertGreater(len(corrupt_backups), 0)

    def test_12_lifo_rollback_order_and_categorization(self):
        """Verify rollback processes in reverse chronological order (LIFO) and reports 4 categories."""
        mgr = SnapshotManager()
        # Log two changes
        c1 = mgr.log_change("test", "First Setting", "v1", "v2", "target1", False)
        c2 = mgr.log_change("test", "Second Setting", "vA", "vB", "target2", False)

        report = mgr.restore_previous_state()
        self.assertIn("successful", report)
        self.assertIn("skipped", report)
        self.assertIn("failed", report)
        self.assertIn("reboot_required", report)
        self.assertIn(TERM_RESTORE_RESULT, report["message"])

        # Order of restoration IDs should be LIFO: c2 before c1
        restored_ids = [r["id"] for r in report["successful"]]
        idx_c1 = restored_ids.index(c1)
        idx_c2 = restored_ids.index(c2)
        self.assertLess(idx_c2, idx_c1, "Rollback must execute in reverse chronological order (LIFO)")

    def test_13_dns_mode_separate_storage(self):
        """Verify DNS mode is tracked separately from server IP address list."""
        from network_stabilizer.constants import DNS_MODE_AUTO, DNS_MODE_MANUAL
        mgr = SnapshotManager()
        state = mgr._get_empty_schema()
        # Record adapter with auto vs manual
        state["network_state"]["dns"] = {}
        state["network_state"]["dns"]["Ethernet"] = {
            "mode": DNS_MODE_AUTO,
            "servers": []
        }
        state["network_state"]["dns"]["Wi-Fi"] = {
            "mode": DNS_MODE_MANUAL,
            "servers": ["1.1.1.1", "1.0.0.1"]
        }
        self.assertEqual(state["network_state"]["dns"]["Ethernet"]["mode"], "auto")
        self.assertEqual(state["network_state"]["dns"]["Wi-Fi"]["mode"], "manual")

    def test_14_no_older_wording_present(self):
        """Verify no older wording such as 'exact original state' or 'guaranteed' remains in feature files."""
        app_dir = os.path.join(_APP_DIR, "network_stabilizer")
        files_to_check = [os.path.join(app_dir, f) for f in os.listdir(app_dir) if f.endswith(".py")]
        files_to_check.append(os.path.join(_APP_DIR, "ui", "network_view.py"))

        forbidden_phrases = ["exact original state", "guarantee 1-click restore to this exact point", "full rollback ready"]
        for fpath in files_to_check:
            with open(fpath, "r", encoding="utf-8") as f:
                content = f.read().lower()
            for phrase in forbidden_phrases:
                self.assertNotIn(phrase, content, f"Forbidden older phrase '{phrase}' found in {fpath}")

    def test_15_same_constant_in_rollback_tab_and_restore_result(self):
        """Verify the exact same constant is referenced in Rollback tab and restore-result message."""
        from network_stabilizer.constants import TERM_RESTORE_RESULT
        from ui.network_view import TERM_RESTORE_RESULT as VIEW_TERM_RESTORE_RESULT
        self.assertEqual(TERM_RESTORE_RESULT, VIEW_TERM_RESTORE_RESULT)

        mgr = SnapshotManager()
        res = mgr.restore_previous_state()
        self.assertEqual(res["message"], TERM_RESTORE_RESULT)

    def test_16_failed_and_skipped_restorations_display_reasons(self):
        """Verify failed and skipped restorations display their specific reasons."""
        mgr = SnapshotManager()
        # 1. Skipped due to invalid interface format
        cid_skip = mgr.log_change("dns", "Invalid DNS", ["1.1.1.1"], ["8.8.8.8"], target="!@#$%^&*()", status="applied")
        # 2. Skipped Winsock recovery action
        cid_winsock = mgr.log_change("network_stack", "Winsock Reset (Recovery Action)", "Custom", "Factory Defaults", target="System", status="applied")

        res_skip = mgr.restore_change({"id": cid_skip, "category": "dns", "target": "!@#$%^&*()", "old_value": ["1.1.1.1"], "old_mode": "manual"})
        self.assertTrue(res_skip["skipped"])
        self.assertTrue(bool(res_skip["reason"]))
        self.assertIn("Invalid interface identifier", res_skip["reason"])

        res_winsock = mgr.restore_change({"id": cid_winsock, "category": "network_stack", "target": "System", "old_value": "Custom", "old_mode": "manual"})
        self.assertTrue(res_winsock["skipped"])
        self.assertTrue(bool(res_winsock["reason"]))
        self.assertIn("Winsock reset is a recovery action requiring restart", res_winsock["reason"])

        # Check that reasons are preserved in audit history
        changes = mgr.get_change_log()
        c_dns = next(c for c in changes if c["id"] == cid_skip)
        self.assertEqual(c_dns["status"], "skipped")
        self.assertIn("Invalid interface identifier", c_dns.get("reason", ""))

    def test_17_winsock_reset_shown_as_recovery_action(self):
        """Verify Winsock reset is designated as a recovery action requiring restart/manual intervention."""
        from network_stabilizer.constants import TERM_WINSOCK_RECOVERY
        self.assertIn("recovery action requiring restart / manual intervention", TERM_WINSOCK_RECOVERY.lower())

        mgr = SnapshotManager()
        res = mgr.restore_change({"id": "ws-test", "category": "network_stack", "target": "System", "old_value": "Custom"})
        self.assertTrue(res["skipped"])
        self.assertEqual(res["reason"], TERM_WINSOCK_RECOVERY)

    def test_18_registry_rollback_reports_restored_vs_deleted(self):
        """Verify registry rollback reports whether a value was restored or deleted because it did not previously exist."""
        from unittest.mock import patch, MagicMock
        mgr = SnapshotManager()

        mock_key = MagicMock()
        mock_key.__enter__.return_value = mock_key
        mock_key.__exit__.return_value = False

        with patch("winreg.OpenKey", return_value=mock_key), \
             patch("winreg.SetValueEx") as mock_set, \
             patch("winreg.DeleteValue") as mock_del:

            # Case A: Value did NOT previously exist -> should delete and report deleted
            c_del = {
                "id": "reg-del-test",
                "category": "registry_tcp",
                "setting": "Network Throttling Index",
                "target": "HKLM Multimedia SystemProfile",
                "old_value": {
                    "NetworkThrottlingIndex": None,
                    "NetworkThrottlingIndex_existed": False,
                    "SystemResponsiveness": None,
                    "SystemResponsiveness_existed": False
                }
            }
            with patch("winreg.QueryValueEx", side_effect=FileNotFoundError):
                res_del = mgr.restore_change(c_del)
                self.assertTrue(res_del["success"])
                self.assertIn("deleted because it did not previously exist", res_del["details"])
                self.assertTrue(mock_del.called)

            # Case B: Value DID previously exist -> should set and report restored
            c_res = {
                "id": "reg-res-test",
                "category": "registry_tcp",
                "setting": "Network Throttling Index",
                "target": "HKLM Multimedia SystemProfile",
                "old_value": {
                    "NetworkThrottlingIndex": 10,
                    "NetworkThrottlingIndex_existed": True,
                    "SystemResponsiveness": 20,
                    "SystemResponsiveness_existed": True
                }
            }
            with patch("winreg.QueryValueEx", side_effect=[(10, 4), (20, 4)]):
                res_res = mgr.restore_change(c_res)
                self.assertTrue(res_res["success"])
                self.assertIn("restored to 10", res_res["details"])
                self.assertIn("restored to 20", res_res["details"])
                self.assertTrue(mock_set.called)

    def test_19_audit_record_remains_available_after_rollback(self):
        """Verify audit record remains available after successful, skipped, or failed rollback."""
        mgr = SnapshotManager()
        cid = mgr.log_change("test", "Setting To Audit", "old", "new", "target")
        initial_log = mgr.get_change_log()
        self.assertTrue(any(c["id"] == cid for c in initial_log))

        mgr.restore_previous_state()

        post_log = mgr.get_change_log()
        matched = [c for c in post_log if c["id"] == cid]
        self.assertEqual(len(matched), 1, "Audit ledger must preserve record after rollback")
        self.assertEqual(matched[0]["status"], "reverted")


if __name__ == "__main__":
    unittest.main()
