from typing import Dict, List, Any

class GameAdapter:
    """Base interface for all game-specific Sentinel adapters."""
    
    @property
    def game_id(self) -> str:
        raise NotImplementedError
        
    @property
    def executable_names(self) -> List[str]:
        raise NotImplementedError
        
    def detect(self) -> bool:
        """Returns True if the game is currently running and (optionally) focused."""
        raise NotImplementedError
        
    def telemetry_setup(self) -> List[Dict[str, Any]]:
        """Returns instructions for setting up in-game telemetry."""
        raise NotImplementedError
        
    def classify_stutter(self, metrics: Dict[str, Any]) -> str:
        """Classifies anomalies based on game-specific telemetry and behavior."""
        raise NotImplementedError
        
    def recommendations(self, metrics: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Returns safe recommendations (e.g. settings changes) based on metrics."""
        raise NotImplementedError
        
    def profile_settings(self) -> Dict[str, Any]:
        """Returns the game profile configurations."""
        raise NotImplementedError
