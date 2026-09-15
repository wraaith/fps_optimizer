from .models import SentinelState

class StateMachine:
    """Manages the lifecycle transitions of the Sentinel engine."""
    
    def __init__(self):
        self.current_state = SentinelState.IDLE
        
    def transition_to(self, new_state: SentinelState):
        """Safely transitions to a new state with validation."""
        self.current_state = new_state
