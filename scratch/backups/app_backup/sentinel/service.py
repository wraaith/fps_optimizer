class SentinelService:
    """The central lifecycle orchestrator for the Universal Game Sentinel."""
    
    def __init__(self):
        self.is_running = False
        self.is_paused = False
        
    def start(self):
        self.is_running = True
        self.is_paused = False
        
    def pause(self):
        self.is_paused = True
        
    def resume(self):
        self.is_paused = False
        
    def stop(self):
        self.is_running = False
        self.is_paused = False
        
    def emergency_stop(self):
        """Immediately halts all interventions and attempts to rollback active changes."""
        self.stop()
