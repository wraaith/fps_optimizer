import os
import sys
import time
import threading
import unittest
from unittest.mock import patch, MagicMock
import psutil

# Ensure app directory is on sys.path
APP_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "desktop-app", "app"))
if APP_DIR not in sys.path:
    sys.path.insert(0, APP_DIR)

from sentinel.service import SentinelService
from sentinel.models import SentinelMode
from sentinel.managers.process_token_manager import TokenValidationResult

class MockProcess:
    """Mock process object for testing termination without touching OS processes."""
    def __init__(self, pid: int, name: str, exe: str, create_time: float):
        self._pid = pid
        self._name = name
        self._exe = exe
        self._create_time = create_time
        self.terminate_call_count = 0

    @property
    def pid(self) -> int:
        return self._pid

    def name(self) -> str:
        return self._name

    def exe(self) -> str:
        return self._exe

    def create_time(self) -> float:
        return self._create_time

    def terminate(self):
        self.terminate_call_count += 1
        
    @property
    def terminated(self) -> bool:
        return self.terminate_call_count > 0

    @property
    def info(self) -> dict:
        return {
            'pid': self._pid,
            'name': self._name,
            'exe': self._exe,
            'create_time': self._create_time
        }

class TestProcessCleanupHardened(unittest.TestCase):
    def setUp(self):
        self.service = SentinelService.get_instance()
        self.service.stop()  # Generates fresh session_id and clears tokens
        self.service.set_mode(SentinelMode.MONITOR_ONLY)
        self.session_id = self.service.session_id

        # Setup standard mock target
        self.target_mock = MockProcess(
            1001,
            "fps_optimizer_overlay.exe",
            "c:/test/fps_optimizer_overlay.exe",
            1000.0
        )

    def _get_token_from_dry_run(self, mock_piter) -> str:
        mock_piter.return_value = [self.target_mock]
        res = self.service.request_intervention("process_cleanup", {
            "legacy_mode": True,
            "dry_run": True
        })
        candidates = res.get("details", {}).get("candidates", [])
        return candidates[0]["token"] if candidates else None

    def _run_real_termination(self, token: str, pid: int = 1001, **kwargs) -> dict:
        args = {
            "legacy_mode": True,
            "dry_run": False,
            "foreground_confirmed": True,
            "targets": [{"pid": pid, "token": token}]
        }
        args.update(kwargs)
        return self.service.request_intervention("process_cleanup", args)

    def test_01_missing_legacy_mode(self):
        res = self.service.request_intervention("process_cleanup", {
            "dry_run": False,
            "legacy_mode": False,
            "foreground_confirmed": True,
            "targets": [{"pid": 1001, "token": "dummy"}]
        })
        self.assertIn(res["status"], ["blocked", "failed"])
        self.assertFalse(res["system_changed"])
        self.assertEqual(self.target_mock.terminate_call_count, 0)

    @patch('psutil.process_iter')
    def test_02_missing_token(self, mock_piter):
        res = self._run_real_termination(None)
        self.assertIn(res["status"], ["blocked", "failed"])
        self.assertEqual(res["reason"], "Missing token")
        self.assertFalse(res["system_changed"])
        self.assertEqual(self.target_mock.terminate_call_count, 0)

    @patch('psutil.process_iter')
    @patch('psutil.Process')
    def test_03_invalid_token(self, mock_process, mock_piter):
        mock_process.return_value = self.target_mock
        res = self._run_real_termination("bad-token")
        self.assertIn(res["status"], ["blocked", "failed"])
        self.assertIn("already_consumed", res["reason"])
        self.assertFalse(res["system_changed"])
        self.assertEqual(self.target_mock.terminate_call_count, 0)

    @patch('psutil.process_iter')
    @patch('psutil.Process')
    def test_04_expired_token(self, mock_process, mock_piter):
        token = self._get_token_from_dry_run(mock_piter)
        self.assertIsNotNone(token)
        
        # Expire the token in memory
        self.service.token_manager._tokens[token]["expires_at"] = time.monotonic() - 10.0
        
        mock_process.return_value = self.target_mock
        res = self._run_real_termination(token)
        self.assertIn(res["status"], ["blocked", "failed"])
        self.assertIn("expired", res["reason"])
        self.assertFalse(res["system_changed"])
        self.assertEqual(self.target_mock.terminate_call_count, 0)

    @patch('psutil.process_iter')
    @patch('psutil.Process')
    def test_05_reused_token(self, mock_process, mock_piter):
        token = self._get_token_from_dry_run(mock_piter)
        self.assertIsNotNone(token)
        mock_process.return_value = self.target_mock
        
        # First use: must succeed
        res1 = self._run_real_termination(token)
        self.assertEqual(res1["status"], "applied")
        self.assertTrue(res1["system_changed"])
        self.assertEqual(self.target_mock.terminate_call_count, 1)
        
        # Second use: must be rejected as already consumed
        res2 = self._run_real_termination(token)
        self.assertIn(res2["status"], ["blocked", "failed"])
        self.assertIn("already_consumed", res2["reason"])
        self.assertFalse(res2["system_changed"])
        self.assertEqual(self.target_mock.terminate_call_count, 1)

    @patch('psutil.process_iter')
    @patch('psutil.Process')
    def test_06_pid_reuse(self, mock_process, mock_piter):
        token = self._get_token_from_dry_run(mock_piter)
        self.assertIsNotNone(token)
        reused_mock = MockProcess(1001, "different.exe", "c:/test/different.exe", 2000.0)
        mock_process.return_value = reused_mock
        
        res = self._run_real_termination(token)
        self.assertIn(res["status"], ["blocked", "identity_changed", "failed"])
        self.assertFalse(res["system_changed"])
        self.assertEqual(reused_mock.terminate_call_count, 0)

    @patch('psutil.process_iter')
    @patch('psutil.Process')
    def test_07_executable_path_change(self, mock_process, mock_piter):
        token = self._get_token_from_dry_run(mock_piter)
        self.assertIsNotNone(token)
        changed_mock = MockProcess(1001, "fps_optimizer_overlay.exe", "c:/evil/overlay.exe", 1000.0)
        mock_process.return_value = changed_mock
        
        res = self._run_real_termination(token)
        self.assertIn(res["status"], ["blocked", "identity_changed", "failed"])
        self.assertIn("identity_mismatch", res["reason"])
        self.assertFalse(res["system_changed"])
        self.assertEqual(changed_mock.terminate_call_count, 0)

    @patch('psutil.process_iter')
    @patch('psutil.Process')
    def test_08_creation_time_change(self, mock_process, mock_piter):
        token = self._get_token_from_dry_run(mock_piter)
        self.assertIsNotNone(token)
        changed_mock = MockProcess(1001, "fps_optimizer_overlay.exe", "c:/test/fps_optimizer_overlay.exe", 5000.0)
        mock_process.return_value = changed_mock
        
        res = self._run_real_termination(token)
        self.assertIn(res["status"], ["blocked", "identity_changed", "failed"])
        self.assertIn("identity_mismatch", res["reason"])
        self.assertFalse(res["system_changed"])
        self.assertEqual(changed_mock.terminate_call_count, 0)

    @patch('psutil.process_iter')
    @patch('psutil.Process')
    def test_09_protected_process(self, mock_process, mock_piter):
        token = self.service.token_manager.generate_token(
            1001, "c:/sys/svchost.exe", 100.0, "process_cleanup", self.service.session_id
        )
        protected_mock = MockProcess(1001, "svchost.exe", "c:/sys/svchost.exe", 100.0)
        mock_process.return_value = protected_mock
        
        res = self._run_real_termination(token)
        self.assertIn(res["status"], ["blocked", "failed"])
        self.assertFalse(res["system_changed"])
        self.assertEqual(protected_mock.terminate_call_count, 0)

    @patch('psutil.process_iter')
    @patch('psutil.Process')
    def test_10_active_game(self, mock_process, mock_piter):
        token = self.service.token_manager.generate_token(
            1001, "c:/game/game.exe", 100.0, "process_cleanup", self.service.session_id
        )
        game_mock = MockProcess(1001, "game.exe", "c:/game/game.exe", 100.0)
        mock_process.return_value = game_mock
        
        res = self._run_real_termination(token)
        self.assertIn(res["status"], ["blocked", "failed"])
        self.assertFalse(res["system_changed"])
        self.assertEqual(game_mock.terminate_call_count, 0)

    def test_11_sentinel_running_in_every_mode(self):
        modes = [
            SentinelMode.MONITOR_ONLY,
            SentinelMode.CONSERVATIVE,
            SentinelMode.BALANCED,
            SentinelMode.ADVANCED
        ]
        for mode in modes:
            with self.subTest(mode=mode):
                self.service._is_running = True
                self.service.set_mode(mode)
                res = self.service.request_intervention("process_cleanup", {
                    "legacy_mode": True,
                    "dry_run": False,
                    "foreground_confirmed": True,
                    "targets": [{"pid": 1001, "token": "dummy"}]
                })
                self.assertEqual(res["status"], "blocked")
                self.assertEqual(res["reason"], "Sentinel is active")
                self.assertFalse(res["system_changed"])
                self.assertEqual(self.target_mock.terminate_call_count, 0)
                self.service._is_running = False

    def test_12_monitor_only(self):
        self.service._is_running = True
        self.service.set_mode(SentinelMode.MONITOR_ONLY)
        res = self.service.request_intervention("process_cleanup", {
            "legacy_mode": True,
            "dry_run": False
        })
        self.assertEqual(res["status"], "blocked")
        self.assertFalse(res["system_changed"])
        self.service._is_running = False

    @patch('psutil.process_iter')
    def test_13_dry_run(self, mock_piter):
        mock_piter.return_value = [self.target_mock]
        res = self.service.request_intervention("process_cleanup", {
            "legacy_mode": True,
            "dry_run": True
        })
        self.assertEqual(res["status"], "dry_run")
        self.assertFalse(res["system_changed"])
        self.assertEqual(self.target_mock.terminate_call_count, 0)
        
        candidates = res.get("details", {}).get("candidates", [])
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0]["pid"], 1001)
        self.assertIsNotNone(candidates[0]["token"])
        self.assertIn("Allowlisted", candidates[0]["reason"])

    @patch('psutil.process_iter')
    @patch('psutil.Process')
    def test_14_process_disappearance(self, mock_process, mock_piter):
        token = self._get_token_from_dry_run(mock_piter)
        self.assertIsNotNone(token)
        mock_process.side_effect = psutil.NoSuchProcess(1001)
        
        res = self._run_real_termination(token)
        self.assertEqual(res["status"], "already_exited")
        self.assertFalse(res["system_changed"])
        self.assertEqual(self.target_mock.terminate_call_count, 0)

    @patch('psutil.process_iter')
    @patch('psutil.Process')
    def test_15_access_denied(self, mock_process, mock_piter):
        token = self._get_token_from_dry_run(mock_piter)
        self.assertIsNotNone(token)
        mock_process.side_effect = psutil.AccessDenied(1001)
        
        res = self._run_real_termination(token)
        self.assertEqual(res["status"], "failed")
        self.assertFalse(res["system_changed"])
        self.assertEqual(self.target_mock.terminate_call_count, 0)

    @patch('psutil.process_iter')
    @patch('psutil.Process')
    def test_16_wrong_operation(self, mock_process, mock_piter):
        token = self.service.token_manager.generate_token(
            1001, "c:/test/fps_optimizer_overlay.exe", 1000.0, "wrong_op", self.service.session_id
        )
        mock_process.return_value = self.target_mock
        
        res = self._run_real_termination(token)
        self.assertIn(res["status"], ["blocked", "failed"])
        self.assertIn("operation_mismatch", res["reason"])
        self.assertFalse(res["system_changed"])
        self.assertEqual(self.target_mock.terminate_call_count, 0)

    @patch('psutil.process_iter')
    @patch('psutil.Process')
    def test_17_wrong_session(self, mock_process, mock_piter):
        token = self._get_token_from_dry_run(mock_piter)
        self.assertIsNotNone(token)
        mock_process.return_value = self.target_mock
        
        self.service.session_id = "completely-different-session-uuid"
        res = self._run_real_termination(token)
        self.assertIn(res["status"], ["blocked", "failed"])
        self.assertIn("session_mismatch", res["reason"])
        self.assertFalse(res["system_changed"])
        self.assertEqual(self.target_mock.terminate_call_count, 0)

    @patch('psutil.process_iter')
    @patch('psutil.Process')
    def test_18_successful_termination(self, mock_process, mock_piter):
        token = self._get_token_from_dry_run(mock_piter)
        self.assertIsNotNone(token)
        mock_process.return_value = self.target_mock
        
        res = self._run_real_termination(token)
        self.assertEqual(res["status"], "applied")
        self.assertTrue(res["system_changed"])
        self.assertEqual(self.target_mock.terminate_call_count, 1)

    @patch('psutil.process_iter')
    def test_19_token_invalidation_on_service_stop(self, mock_piter):
        token = self._get_token_from_dry_run(mock_piter)
        self.assertIsNotNone(token)
        self.assertIn(token, self.service.token_manager._tokens)
        
        old_session = self.service.session_id
        self.service.stop()
        
        self.assertNotEqual(self.service.session_id, old_session)
        self.assertNotIn(token, self.service.token_manager._tokens)
        self.assertEqual(len(self.service.token_manager._tokens), 0)

    @patch('psutil.process_iter')
    def test_20_token_invalidation_on_emergency_stop(self, mock_piter):
        token = self._get_token_from_dry_run(mock_piter)
        self.assertIsNotNone(token)
        self.assertIn(token, self.service.token_manager._tokens)
        
        old_session = self.service.session_id
        self.service.emergency_stop()
        
        self.assertNotEqual(self.service.session_id, old_session)
        self.assertNotIn(token, self.service.token_manager._tokens)
        self.assertEqual(len(self.service.token_manager._tokens), 0)

    @patch('psutil.process_iter')
    def test_21_concurrent_token_consumption(self, mock_piter):
        token = self._get_token_from_dry_run(mock_piter)
        self.assertIsNotNone(token)
        
        results = []
        def consumer():
            r = self.service.token_manager.consume_token(
                token=token,
                pid=1001,
                exe_path="c:/test/fps_optimizer_overlay.exe",
                create_time=1000.0,
                operation="process_cleanup",
                session_id=self.service.session_id
            )
            results.append(str(r))

        threads = [threading.Thread(target=consumer) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(results.count("valid"), 1)
        self.assertEqual(results.count("already_consumed"), 9)

    @patch('psutil.process_iter')
    @patch('psutil.Process')
    def test_22_missing_foreground_confirmation(self, mock_process, mock_piter):
        token = self._get_token_from_dry_run(mock_piter)
        self.assertIsNotNone(token)
        mock_process.return_value = self.target_mock
        
        res = self.service.request_intervention("process_cleanup", {
            "legacy_mode": True,
            "dry_run": False,
            "foreground_confirmed": False,
            "targets": [{"pid": 1001, "token": token}]
        })
        self.assertEqual(res["status"], "blocked")
        self.assertIn("Foreground confirmation required", res["reason"])
        self.assertFalse(res["system_changed"])
        self.assertEqual(self.target_mock.terminate_call_count, 0)

if __name__ == '__main__':
    unittest.main()
