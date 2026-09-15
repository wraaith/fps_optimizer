import psutil
from datetime import datetime
from typing import Dict, List, Optional
import sys

class PriorityRollbackManager:
    """
    Manages process priority tracking and targeted rollback.
    """
    def __init__(self):
        self.records: List[Dict] = []
        
        # Windows priority constants map
        self.priority_map = {
            "IDLE": psutil.IDLE_PRIORITY_CLASS if sys.platform == "win32" else 19,
            "BELOW_NORMAL": getattr(psutil, 'BELOW_NORMAL_PRIORITY_CLASS', 10),
            "NORMAL": getattr(psutil, 'NORMAL_PRIORITY_CLASS', 0),
            "ABOVE_NORMAL": getattr(psutil, 'ABOVE_NORMAL_PRIORITY_CLASS', -5),
            "HIGH": getattr(psutil, 'HIGH_PRIORITY_CLASS', -10),
            "REALTIME": getattr(psutil, 'REALTIME_PRIORITY_CLASS', -20)
        }

    def _class_to_name(self, class_val: int) -> str:
        for name, val in self.priority_map.items():
            if val == class_val:
                return name
        return "UNKNOWN"

    def record_and_change(self, pid: int, new_priority_name: str, intervention_id: str = "temp") -> bool:
        """Records the original priority and attempts to change it."""
        if new_priority_name == "REALTIME":
            return False # Security constraint: never use REALTIME
            
        try:
            proc = psutil.Process(pid)
            exe_path = proc.exe()
            
            # Skip protected / system processes (rudimentary check, real app would check signing/paths)
            if "system32" in exe_path.lower() or "anticheat" in exe_path.lower():
                return False
                
            old_class = proc.nice()
            old_name = self._class_to_name(old_class)
            
            # Apply new
            new_class = self.priority_map.get(new_priority_name, self.priority_map["NORMAL"])
            proc.nice(new_class)
            
            record = {
                "pid": pid,
                "executable": exe_path,
                "original_priority": old_name,
                "new_priority": new_priority_name,
                "timestamp": datetime.now().isoformat(),
                "intervention_id": intervention_id,
                "restored": False
            }
            self.records.append(record)
            return True
            
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return False

    def rollback_all(self):
        """Restores all modified priorities back to original_priority."""
        for rec in reversed(self.records):
            if rec["restored"]:
                continue
                
            try:
                proc = psutil.Process(rec["pid"])
                # Only restore if it's the exact same executable path
                if proc.exe() == rec["executable"]:
                    old_class = self.priority_map.get(rec["original_priority"], self.priority_map["NORMAL"])
                    proc.nice(old_class)
                    rec["restored"] = True
                else:
                    # PID reuse detected
                    rec["restored"] = "not_required"
            except psutil.NoSuchProcess:
                rec["restored"] = "not_required"
            except psutil.AccessDenied:
                pass
                
    def get_records(self) -> List[Dict]:
        return self.records
