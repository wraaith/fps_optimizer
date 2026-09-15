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
        
    def request_intervention(self, intervention: Any, metrics: dict) -> bool:
        """Requests execution of an intervention, gated by mode and safety."""
        if self.mode == SentinelMode.MONITOR_ONLY:
            return False
            
        if hasattr(intervention, "name") and not self.safety.is_safe_to_intervene(metrics, intervention.name):
            return False
            
        # For Phase 4, we allow the intervention to execute if we aren't monitor_only
        if hasattr(intervention, "execute"):
            intervention.execute()
        return True
        
    def check_legacy_allowed(self, action_name: str) -> bool:
        """Gate legacy calls. If Sentinel is active and in Monitor Only, reject."""
        if self.mode == SentinelMode.MONITOR_ONLY:
            return False
        return True
