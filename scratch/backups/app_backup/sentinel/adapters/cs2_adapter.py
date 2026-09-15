from typing import Any, Dict, List
from .base_adapter import GameAdapter

class CounterStrike2Adapter(GameAdapter):
    @property
    def game_id(self) -> str:
        return "cs2"
        
    @property
    def executable_names(self) -> List[str]:
        return ["cs2.exe"]
        
    def detect(self) -> bool:
        return False
        
    def telemetry_setup(self) -> List[Dict[str, Any]]:
        return [
            {"step": "Open Settings > Telemetry"},
            {"step": "Show Frame Time and FPS: Set to 'Always' or 'Show if poor'"},
            {"step": "Show Ping: Set to 'Always'"},
            {"step": "Show Packet Loss/Misdelivery: Set to 'Always'"},
            {"step": "Show Network Connection Issues: Set to 'Show if poor'"}
        ]
        
    def classify_stutter(self, metrics: Dict[str, Any]) -> str:
        has_net_spike = metrics.get("packet_misdelivery", 0) > 0 or metrics.get("packet_loss", 0) > 0
        has_frame_spike = metrics.get("frame_time_spike", False)
        
        if has_net_spike:
            return "packet_loss"
        elif has_frame_spike and not has_net_spike:
            return "render_stutter"
        return "game_or_driver_unknown"
        
    def recommendations(self, metrics: Dict[str, Any]) -> List[Dict[str, Any]]:
        recs = []
        if self.classify_stutter(metrics) == "render_stutter":
            recs.append({
                "setting": "fps_max",
                "value": "Calculated safe cap",
                "reason": "Consistent frame-time spikes detected. Capping FPS slightly below average can stabilize the render queue.",
                "note": "Requires manual entry in console or autoexec.cfg."
            })
        return recs
        
    def profile_settings(self) -> Dict[str, Any]:
        return {}
