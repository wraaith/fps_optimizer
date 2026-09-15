import os
import sys
import unittest
from unittest.mock import patch, MagicMock

APP_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "desktop-app", "app"))
if APP_DIR not in sys.path:
    sys.path.insert(0, APP_DIR)

from sentinel.managers.priority_rollback_manager import PriorityRollbackManager
import psutil

class TestPriorityRollbackManager(unittest.TestCase):
    def setUp(self):
        self.pm = PriorityRollbackManager()
        # Mock psutil map
        self.NORMAL = getattr(psutil, 'NORMAL_PRIORITY_CLASS', 0)
        self.HIGH = getattr(psutil, 'HIGH_PRIORITY_CLASS', -10)

    @patch('sentinel.managers.priority_rollback_manager.psutil.Process')
    def test_successful_restoration(self, mock_process):
        mock_proc = MagicMock()
        mock_proc.exe.return_value = "C:\\Games\\Game.exe"
        mock_proc.nice.return_value = self.NORMAL
        mock_process.return_value = mock_proc

        self.assertTrue(self.pm.record_and_change(1234, "HIGH", "t1"))
        
        mock_proc.nice.assert_called_with(self.HIGH)
        
        # Rollback
        self.pm.rollback_all()
        mock_proc.nice.assert_called_with(self.NORMAL)
        
        self.assertTrue(self.pm.records[0]["restored"])

    @patch('sentinel.managers.priority_rollback_manager.psutil.Process')
    def test_real_time_rejection(self, mock_process):
        self.assertFalse(self.pm.record_and_change(1234, "REALTIME", "t1"))
        mock_process.assert_not_called()

    @patch('sentinel.managers.priority_rollback_manager.psutil.Process')
    def test_protected_process_rejection(self, mock_process):
        mock_proc = MagicMock()
        mock_proc.exe.return_value = "C:\\Windows\\System32\\svchost.exe"
        mock_process.return_value = mock_proc

        self.assertFalse(self.pm.record_and_change(1234, "HIGH", "t1"))

    @patch('sentinel.managers.priority_rollback_manager.psutil.Process')
    def test_process_already_exited(self, mock_process):
        mock_proc = MagicMock()
        mock_proc.exe.return_value = "C:\\Games\\Game.exe"
        mock_proc.nice.return_value = self.NORMAL
        mock_process.return_value = mock_proc

        self.assertTrue(self.pm.record_and_change(1234, "HIGH", "t1"))
        
        # Simulate exit during rollback
        mock_process.side_effect = psutil.NoSuchProcess(1234)
        
        self.pm.rollback_all()
        self.assertEqual(self.pm.records[0]["restored"], "not_required")

    @patch('sentinel.managers.priority_rollback_manager.psutil.Process')
    def test_access_denied(self, mock_process):
        mock_proc = MagicMock()
        mock_proc.exe.return_value = "C:\\Games\\Game.exe"
        mock_proc.nice.return_value = self.NORMAL
        mock_process.return_value = mock_proc

        self.assertTrue(self.pm.record_and_change(1234, "HIGH", "t1"))
        
        # Simulate AccessDenied during rollback
        def mock_nice_denied(*args):
            if args:
                raise psutil.AccessDenied(1234)
            return self.NORMAL
        mock_proc.nice.side_effect = mock_nice_denied
        
        self.pm.rollback_all()
        self.assertFalse(self.pm.records[0]["restored"]) # Restoration failed

    @patch('sentinel.managers.priority_rollback_manager.psutil.Process')
    def test_pid_reused(self, mock_process):
        mock_proc = MagicMock()
        mock_proc.exe.return_value = "C:\\Games\\Game.exe"
        mock_proc.nice.return_value = self.NORMAL
        mock_process.return_value = mock_proc

        self.assertTrue(self.pm.record_and_change(1234, "HIGH", "t1"))
        
        # Simulate PID reused
        mock_proc_reused = MagicMock()
        mock_proc_reused.exe.return_value = "C:\\Other\\App.exe"
        mock_process.return_value = mock_proc_reused
        
        self.pm.rollback_all()
        mock_proc_reused.nice.assert_not_called()
        self.assertEqual(self.pm.records[0]["restored"], "not_required")

    @patch('sentinel.managers.priority_rollback_manager.psutil.Process')
    def test_repeated_rollback(self, mock_process):
        mock_proc = MagicMock()
        mock_proc.exe.return_value = "C:\\Games\\Game.exe"
        mock_proc.nice.return_value = self.NORMAL
        mock_process.return_value = mock_proc

        self.assertTrue(self.pm.record_and_change(1234, "HIGH", "t1"))
        
        self.pm.rollback_all()
        self.assertTrue(self.pm.records[0]["restored"])
        
        mock_proc.nice.reset_mock()
        self.pm.rollback_all()
        mock_proc.nice.assert_not_called()

if __name__ == '__main__':
    unittest.main(verbosity=2)
