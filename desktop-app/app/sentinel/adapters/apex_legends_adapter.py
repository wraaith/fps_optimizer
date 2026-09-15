from typing import Any, Dict, List
from .base_adapter import GameAdapter

class ApexLegendsAdapter(GameAdapter):
    @property
    def game_id(self) -> str:
        return "apex"
        
    @property
    def executable_names(self) -> List[str]:
        return ["r5apex.exe"]
        
    def detect(self) -> bool:
        return False
        
    def telemetry_setup(self) -> List[Dict[str, Any]]:
        return [
            {"step": "Open Settings > Gameplay"},
            {"step": "Set 'Performance Display' to ON"},
            {"step": "Note the Data Center you connected to on the main menu."}
        ]
        
    def classify_stutter(self, metrics: Dict[str, Any]) -> str:
        if metrics.get("packet_loss", 0) > 0:
            return "packet_loss"
        elif metrics.get("latency_spikes", 0) > 20:
            return "network_jitter"
        elif metrics.get("fps", 144) < 60:
            return "render_stutter"
        return "game_or_driver_unknown"
        
    def recommendations(self, metrics: Dict[str, Any]) -> List[Dict[str, Any]]:
        recs = []
        if metrics.get("packet_loss", 0) > 0 or metrics.get("latency_spikes", 0) > 30:
            recs.append({
                "setting": "Data Center Selection",
                "value": "Alternative Data Center",
                "reason": "Packet loss or high latency spikes detected on the current data center. Minimum ping is not always the most stable.",
                "note": "Change data center from the main menu before entering the lobby."
            })
            
        if self.classify_stutter(metrics) == "render_stutter":
            recs.append({
                "setting": "Launch Options",
                "value": "+fps_max 144",
                "reason": "Variable FPS is causing render stutter. A reversible launch-option cap stabilizes frame delivery.",
                "note": "Apply via EA App or Steam launch options. Do not use undocumented commands."
            })
            
        return recs
        
    def profile_settings(self) -> Dict[str, Any]:
        return {"fps_cap_enabled": False, "fps_cap_value": 144}
