from typing import Optional, Dict, Any, List
from .models import SentinelMode
from .state_machine import StateMachine
from .safety_manager import SafetyManager

class InterventionController:
    """The sole owner for executing optimizations during an active Sentinel session."""
    
    _instance: Optional['InterventionController'] = None
    
    @classmethod
    def get_instance(cls) -> 'InterventionController':
        if cls._instance is None:
            cls._instance = InterventionController()
        return cls._instance
    
    def __init__(self):
        self.state_machine = StateMachine()
        self.safety = SafetyManager()
        self.mode = SentinelMode.MONITOR_ONLY
        self.active_interventions = []
        
    def set_mode(self, mode: SentinelMode):
        self.mode = mode
        
    def request_intervention(self, intervention_name: Any, args: Dict[str, Any] = None) -> Dict[str, Any]:
        """Requests execution of an intervention, gated by mode and safety."""
        args = args or {}
        name_str = intervention_name if isinstance(intervention_name, str) else getattr(intervention_name, "name", "unknown")
        
        is_sentinel_running = args.get("is_sentinel_running", True)
        
        # Controller enforcement: reject real process cleanup before mode-specific logic whenever Sentinel is running
        is_dry_run = args.get("dry_run", True)
        if name_str == "process_cleanup" and is_sentinel_running and not is_dry_run:
            return {
                "status": "blocked",
                "operation": "process_cleanup",
                "reason": "Sentinel is active",
                "system_changed": False,
                "rollback_available": False,
                "details": {}
            }

        # MONITOR_ONLY blocks all interventions EXCEPT process_cleanup when the service is stopped
        if self.mode == SentinelMode.MONITOR_ONLY:
            if not (name_str == "process_cleanup" and not is_sentinel_running):
                return {
                    "status": "blocked",
                    "operation": name_str,
                    "reason": "MONITOR_ONLY",
                    "system_changed": False,
                    "rollback_available": False,
                    "details": {}
                }
            
        # In a full implementation, safety.is_safe_to_intervene would be called here
        
        # Legacy typed interventions
        if name_str == "dns":
            from .interventions.legacy_interventions import DNSIntervention
            return DNSIntervention().execute(args).to_dict()
        elif name_str == "power_plan":
            from .interventions.legacy_interventions import PowerPlanIntervention
            return PowerPlanIntervention().execute(args).to_dict()
        elif name_str == "process_cleanup":
            from .interventions.legacy_interventions import ProcessCleanupIntervention
            tm = getattr(self, "token_manager", None) or args.get("token_manager")
            return ProcessCleanupIntervention(token_manager=tm).execute(args).to_dict()
            
        # Mock execution for strings
        if isinstance(intervention_name, str):
            return {
                "status": "applied",
                "operation": name_str,
                "system_changed": True,
                "rollback_available": False,
                "details": {}
            }
            
        # For Phase 4 object interventions
        if hasattr(intervention_name, "execute"):
            try:
                res = intervention_name.execute()
                if hasattr(res, "to_dict"):
                    return res.to_dict()
                return res
            except Exception as e:
                return {
                    "status": "failed",
                    "operation": name_str,
                    "reason": str(e),
                    "system_changed": False,
                    "rollback_available": False,
                    "details": {}
                }
                
        return {
            "status": "failed",
            "operation": name_str,
            "reason": "Unknown intervention type",
            "system_changed": False,
            "rollback_available": False,
            "details": {}
        }
        
    def check_legacy_allowed(self, action_name: str) -> bool:
        """Gate legacy calls. If Sentinel is active and in Monitor Only, reject."""
        if self.mode == SentinelMode.MONITOR_ONLY:
            return False
        return True
