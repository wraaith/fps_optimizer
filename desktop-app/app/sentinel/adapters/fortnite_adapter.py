from typing import Any, Dict, List
from .base_adapter import GameAdapter

class FortniteAdapter(GameAdapter):
    @property
    def game_id(self) -> str:
        return "fortnite"
        
    @property
    def executable_names(self) -> List[str]:
        return ["FortniteClient-Win64-Shipping.exe"]
        
    def detect(self) -> bool:
        return False
        
    def telemetry_setup(self) -> List[Dict[str, Any]]:
        return [
            {"step": "Open Settings > Game UI"},
            {"step": "Set 'Net Debug Stats' to ON"},
            {"step": "Open Settings > Video"},
            {"step": "Enable 'Show FPS'"}
        ]
        
    def classify_stutter(self, metrics: Dict[str, Any]) -> str:
        if metrics.get("packet_loss", 0) > 0:
            return "packet_loss"
        elif metrics.get("frame_time_variance", 0) > 5:
            return "render_stutter"
        return "game_or_driver_unknown"
        
    def recommendations(self, metrics: Dict[str, Any]) -> List[Dict[str, Any]]:
        recs = []
        if metrics.get("frame_time_variance", 0) > 8 and metrics.get("rendering_mode", "DX12") != "PerformanceMode":
            recs.append({
                "setting": "Rendering Mode",
                "value": "Performance Mode",
                "reason": "High frame-time variance detected in DX12. Performance Mode may drastically reduce stuttering on older GPUs.",
                "note": "Requires game restart. Applies lowered fidelity."
            })
        return recs
        
    def profile_settings(self) -> Dict[str, Any]:
        return {"rendering_mode": "DX12"}
