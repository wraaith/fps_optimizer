import os
import sys
import json
import unittest
from unittest.mock import patch, MagicMock

APP_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "desktop-app", "app"))
if APP_DIR not in sys.path:
    sys.path.insert(0, APP_DIR)

from network_stabilizer.snapshot_manager import SnapshotManager, STATUS_REVERTED, STATUS_ROLLBACK_FAILED

class TestUnifiedRollback(unittest.TestCase):
    def setUp(self):
        self.state_file = "./test_state.json"
        self.sm = SnapshotManager(state_file_path=self.state_file)
        # Start fresh
        self.sm._save_state_atomic(self.sm._get_empty_schema())

    def tearDown(self):
        if os.path.exists(self.state_file):
            os.remove(self.state_file)
        corrupt_files = [f for f in os.listdir('.') if f.startswith("test_state.json.corrupt")]
        for f in corrupt_files:
            os.remove(f)

    def test_empty_ledger(self):
        state = self.sm._load_state()
        self.assertEqual(len(state.get("persistent_changes", [])), 0)

    @patch('network_stabilizer.snapshot_manager.subprocess.run')
    def test_dns_rollback_auto(self, mock_run):
        # Mock netsh interface presence check
        mock_run.return_value = MagicMock(returncode=0, stdout="Ethernet", stderr="")
        
        change = {
            "id": "c1",
            "category": "dns",
            "target": "Ethernet",
            "old_mode": "auto",
            "old_value": ["dhcp"]
        }
        
        res = self.sm.restore_change(change)
        self.assertTrue(res["success"])
        # Should call netsh to set dhcp, then powershell to verify
        self.assertTrue(mock_run.call_count >= 3)

    @patch('network_stabilizer.snapshot_manager.subprocess.run')
    def test_power_plan_rollback(self, mock_run):
        mock_list = MagicMock(returncode=0, stdout="381b4222-f694-41f0-9685-ff5bb260df2e")
        mock_set = MagicMock(returncode=0)
        mock_active = MagicMock(returncode=0, stdout="381b4222-f694-41f0-9685-ff5bb260df2e")
        
        mock_run.side_effect = [mock_list, mock_set, mock_active]
        
        change = {
            "id": "c2",
            "category": "power_plan",
            "old_value": "381b4222-f694-41f0-9685-ff5bb260df2e"
        }
        
        res = self.sm.restore_change(change)
        self.assertTrue(res["success"])

    def test_corrupt_json_enters_safe_mode(self):
        with open(self.state_file, "w") as f:
            f.write("{ invalid json")
            
        state = self.sm._load_state()
        self.assertTrue(state.get("safe_mode"))
        self.assertTrue(self.sm.in_safe_mode)
        
        # Original should be backed up as corrupt
        corrupt_files = [f for f in os.listdir('.') if f.startswith("test_state.json.corrupt")]
        self.assertTrue(len(corrupt_files) > 0)
        self.assertEqual(os.path.basename(state["recovery_path"]), corrupt_files[-1])

    def test_empty_file_enters_safe_mode(self):
        with open(self.state_file, "w") as f:
            f.write("")
            
        state = self.sm._load_state()
        self.assertTrue(state.get("safe_mode"))

    def test_truncated_file_enters_safe_mode(self):
        with open(self.state_file, "w") as f:
            f.write('{"schema_version": 2, "persistent_')
            
        state = self.sm._load_state()
        self.assertTrue(state.get("safe_mode"))

    def test_valid_json_with_unknown_fields(self):
        with open(self.state_file, "w") as f:
            json.dump({"schema_version": 2, "persistent_changes": [], "unknown_field": "test"}, f)
            
        state = self.sm._load_state()
        self.assertFalse(state.get("safe_mode", False))
        self.assertEqual(state.get("unknown_field"), "test")

    @patch('builtins.open', side_effect=PermissionError("Permission denied"))
    def test_permission_denied_ledger(self, mock_open):
        state = self.sm._load_state()
        self.assertTrue(state.get("safe_mode"))

    @patch('os.replace', side_effect=OSError("Replace failed"))
    def test_failed_atomic_replacement(self, mock_replace):
        state = self.sm._get_empty_schema()
        self.sm._save_state_atomic(state)
        # Should catch error and delete tmp_file
        tmp_files = [f for f in os.listdir('.') if f.startswith("test_state.json.tmp")]
        self.assertEqual(len(tmp_files), 0)

    def test_partial_restore_failure(self):
        with patch('network_stabilizer.snapshot_manager.subprocess.run') as mock_run:
            mock_list = MagicMock(returncode=0, stdout="381b4222-f694-41f0-9685-ff5bb260df2e")
            mock_set = MagicMock(returncode=1, stderr="Access Denied")
            mock_run.side_effect = [mock_list, mock_set]
            
            change = {
                "id": "c3",
                "category": "power_plan",
                "old_value": "381b4222-f694-41f0-9685-ff5bb260df2e"
            }
            
            res = self.sm.restore_change(change)
            self.assertFalse(res["success"])
            self.assertEqual(res["reason"], "powercfg /setactive returned exit code 1: Access Denied")
            
            # Check status was updated
            state = self.sm._load_state()
            # We didn't actually add the change to the ledger first, so let's check res
            self.assertIn("Access Denied", res["reason"])

if __name__ == '__main__':
    unittest.main(verbosity=2)
