from typing import Any, Dict, List
from .base_adapter import GameAdapter

class ValorantAdapter(GameAdapter):
    @property
    def game_id(self) -> str:
        return "valorant"
        
    @property
    def executable_names(self) -> List[str]:
        return ["VALORANT-Win64-Shipping.exe"]
        
    def detect(self) -> bool:
        # Stub for detecting process presence
        return False
        
    def telemetry_setup(self) -> List[Dict[str, Any]]:
        return [
            {"step": "Open Settings > Video > Stats"},
            {"step": "Enable 'Client FPS' (Text Only)"},
            {"step": "Enable 'Network RTT' (Text Only)"},
            {"step": "Enable 'Network RTT Jitter' (Text Only)"},
            {"step": "Enable 'Packet Loss' (Text Only)"},
            {"step": "Enable 'Game to Render Latency' (Text Only)"},
        ]
        
    def classify_stutter(self, metrics: Dict[str, Any]) -> str:
        # Separates network stutter from render stutter based on telemetry
        if metrics.get("packet_loss", 0) > 0 or metrics.get("rtt_jitter", 0) > 5:
            return "network_jitter"
        elif metrics.get("frame_time_variance", 0) > 5:
            return "render_stutter"
        return "game_or_driver_unknown"
        
    def recommendations(self, metrics: Dict[str, Any]) -> List[Dict[str, Any]]:
        recs = []
        has_packet_loss = metrics.get("packet_loss", 0) > 0
        has_jitter = metrics.get("rtt_jitter", 0) > 5
        
        if has_packet_loss or has_jitter:
            recs.append({
                "setting": "Network Buffering",
                "value": "Moderate",
                "reason": "Packet loss or severe jitter detected. Moderate buffering reduces rubber-banding.",
                "note": "Network Buffering does NOT lower ping. It increases processing delay slightly for stability."
            })
        else:
            recs.append({
                "setting": "Network Buffering",
                "value": "Minimum",
                "reason": "Network is stable. Minimum buffering provides the absolute lowest processing delay.",
                "note": "Do not use if you experience character teleporting."
            })
        return recs
        
    def profile_settings(self) -> Dict[str, Any]:
        return {"network_buffering": "Minimum"}
