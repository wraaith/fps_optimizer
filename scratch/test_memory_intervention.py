import os
import sys
import time
import unittest
from unittest.mock import patch, MagicMock

APP_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "desktop-app", "app"))
if APP_DIR not in sys.path:
    sys.path.insert(0, APP_DIR)

from sentinel.managers.memory_manager import MemoryInterventionManager

class TestMemoryIntervention(unittest.TestCase):
    def setUp(self):
        self.mm = MemoryInterventionManager()

    def test_protected_process_exclusion(self):
        self.assertTrue(self.mm.is_protected_process("C:\\Windows\\System32\\svchost.exe"))
        self.assertTrue(self.mm.is_protected_process("C:\\Games\\EasyAntiCheat\\eac.exe"))
        self.assertFalse(self.mm.is_protected_process("C:\\Games\\MyGame.exe"))

    @patch('time.time')
    def test_cooldown_and_max_actions(self, mock_time):
        mock_time.return_value = 100.0
        
        # Action 1: Succeeds
        self.assertTrue(self.mm.can_execute())
        self.mm.execute_trim([], {"frame_time": -1}) # Improved
        
        # Action 2: Fails due to cooldown
        mock_time.return_value = 110.0 # 10s elapsed
        self.assertFalse(self.mm.can_execute())
        
        # Action 3: Succeeds (Cooldown passed)
        mock_time.return_value = 150.0 # 50s elapsed
        self.assertTrue(self.mm.can_execute())
        self.mm.execute_trim([], {"frame_time": -1}) # Improved
        
        # Action 4: Succeeds
        mock_time.return_value = 200.0
        self.assertTrue(self.mm.can_execute())
        self.mm.execute_trim([], {"frame_time": -1}) # Improved
        
        # Action 5: Fails due to max actions per session
        mock_time.return_value = 250.0
        self.assertFalse(self.mm.can_execute())

    @patch('time.time')
    def test_disablement_after_ineffective_actions(self, mock_time):
        mock_time.return_value = 100.0
        
        # Action 1: Ineffective (metrics did not improve)
        self.assertTrue(self.mm.can_execute())
        self.mm.execute_trim([], {"frame_time": 0.0, "hard_faults": 0})
        self.assertEqual(self.mm.ineffective_count, 1)
        self.assertFalse(self.mm.is_disabled)
        
        # Action 2: Ineffective
        mock_time.return_value = 150.0
        self.assertTrue(self.mm.can_execute())
        self.mm.execute_trim([], {"frame_time": 0.0, "hard_faults": 0})
        self.assertEqual(self.mm.ineffective_count, 2)
        
        # Disabled!
        self.assertTrue(self.mm.is_disabled)
        self.assertFalse(self.mm.can_execute())

    def test_evidence_requirements(self):
        pre_snap = self.mm.pre_action_snapshot()
        pre_snap["memory_before"] = 1000
        pre_snap["frame_time_before"] = 10.0
        pre_snap["hard_faults_before"] = 5
        
        # Scenario 1: Only memory freed. NOT an improvement.
        self.assertFalse(self.mm.post_action_verification(
            pre_snap, {"memory": 500, "frame_time": 10.0, "hard_faults": 5}))
            
        # Scenario 2: Frame time improved. SUCCESS.
        self.assertTrue(self.mm.post_action_verification(
            pre_snap, {"memory": 500, "frame_time": 8.0, "hard_faults": 5}))
            
        # Scenario 3: Hard faults decreased. SUCCESS.
        self.assertTrue(self.mm.post_action_verification(
            pre_snap, {"memory": 500, "frame_time": 10.0, "hard_faults": 2}))

if __name__ == '__main__':
    unittest.main(verbosity=2)
