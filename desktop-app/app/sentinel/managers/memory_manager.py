import time
import psutil
from typing import Dict, List, Optional

class MemoryInterventionManager:
    """
    Manages safety and tracking for RAM/Working Set interventions.
    """
    def __init__(self):
        self.cooldown_sec = 30.0
        self.max_actions_per_session = 3
        
        self.last_action_time = 0.0
        self.action_count = 0
        self.ineffective_count = 0
        self.is_disabled = False
        
        self.protected_keywords = ["system32", "anticheat", "battleye", "easyanticheat"]
        
        self.history: List[Dict] = []

    def can_execute(self) -> bool:
        """Evaluates cooldowns and session limits before allowing a memory action."""
        if self.is_disabled:
            return False
            
        if self.action_count >= self.max_actions_per_session:
            return False
            
        if time.time() - self.last_action_time < self.cooldown_sec:
            return False
            
        return True

    def pre_action_snapshot(self) -> dict:
        """Captures system state before intervention for post-action verification."""
        mem = psutil.virtual_memory()
        return {
            "memory_before": mem.used,
            # Mock values for testing hardware metrics
            "frame_time_before": 0.0,
            "disk_latency_before": 0.0,
            "hard_faults_before": 0
        }
        
    def post_action_verification(self, pre_snapshot: dict, current_metrics: dict) -> bool:
        """Verifies if the action actually helped the system beyond just freeing RAM."""
        # Record the outcome
        outcome = {
            **pre_snapshot,
            "memory_after": current_metrics.get("memory", pre_snapshot["memory_before"]),
            "frame_time_after": current_metrics.get("frame_time", pre_snapshot["frame_time_before"]),
            "disk_latency_after": current_metrics.get("disk_latency", pre_snapshot["disk_latency_before"]),
            "hard_faults_after": current_metrics.get("hard_faults", pre_snapshot["hard_faults_before"])
        }
        self.history.append(outcome)
        
        # Determine effectiveness: 
        # Did frame time improve, or did hard faults decrease?
        # Just freeing memory is NOT proof of success.
        improved = False
        if outcome["frame_time_after"] < outcome["frame_time_before"]:
            improved = True
        elif outcome["hard_faults_after"] < outcome["hard_faults_before"]:
            improved = True
        elif outcome["disk_latency_after"] < outcome["disk_latency_before"]:
            improved = True
            
        if not improved:
            self.ineffective_count += 1
            if self.ineffective_count >= 2:
                self.is_disabled = True # Disable after 2 ineffective actions
                
        return improved

    def execute_trim(self, exclude_pids: List[int], current_metrics: dict) -> bool:
        if not self.can_execute():
            return False
            
        pre_snap = self.pre_action_snapshot()
        
        # Real intervention would happen here (but we keep it disabled in Monitor-Only)
        # We just mock the behavior
        
        self.last_action_time = time.time()
        self.action_count += 1
        
        # Post-action verification
        self.post_action_verification(pre_snap, current_metrics)
        return True

    def is_protected_process(self, exe_path: str) -> bool:
        path_lower = exe_path.lower()
        for kw in self.protected_keywords:
            if kw in path_lower:
                return True
        return False
