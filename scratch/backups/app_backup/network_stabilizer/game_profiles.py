"""
Game Profiles & Stutter Diagnosis Guide for Network Stabilizer.
HUD telemetry guides, buffering settings, and personal benchmark notes stored in compact state document.
"""

from typing import Dict, List, Any, Optional
from network_stabilizer.snapshot_manager import SnapshotManager


class GameProfileManager:
    """
    Manages in-game network telemetry activation guides, stutter diagnosis,
    and user-customized game benchmark journals stored in state document.
    """

    GUIDES = {
        "valorant": {
            "title": "Valorant (Riot Games)",
            "telemetry_setup": [
                "Open Valorant Settings -> 'Video' tab -> 'Stats' subtab.",
                "Set 'Network RTT (Avg)' to 'Text Only' or 'Both'.",
                "Set 'Packet Loss' to 'Text Only' or 'Both'.",
                "Set 'Server Tick Rate' to 'Text Only' (should stay steady at 128 Hz).",
                "Set 'Network Jitter' to 'Text Only'."
            ],
            "stutter_diagnosis": [
                "Network Jitter Spikes: If Network RTT fluctuates wildly while Client FPS stays flat, router bufferbloat or Wi-Fi interference is the cause. Configure router SQM.",
                "Server Tick Rate Drops: If Server Tick Rate dips below 128 (e.g. 100-110), the Riot server is lagging, not your PC.",
                "Render Frame Stutter: If Client FPS drops or 'CPU Frame Time' spikes above 7.8ms, enable NVIDIA Reflex (On + Boost) and cap FPS 3 below monitor refresh rate."
            ],
            "buffering_guidance": "Valorant provides a 'Network Buffering' slider in General settings. Use 'Minimum' on stable wired Ethernet/Fiber for lowest input latency. Use 'Moderate' only if persistent packet loss occurs on Wi-Fi.",
            "optimal_settings": [
                {"setting": "RawInputBuffer", "value": "ON", "desc": "Bypasses Windows API message queue to poll mouse packets directly."},
                {"setting": "Network Buffering", "value": "Minimum", "desc": "Lowest packet queue delay on stable wired connections."},
                {"setting": "NVIDIA Reflex", "value": "On + Boost", "desc": "Keeps GPU clock frequencies peaked to eliminate CPU-GPU pipeline latency."}
            ]
        },
        "fortnite": {
            "title": "Fortnite (Epic Games / Unreal Engine 5)",
            "telemetry_setup": [
                "Open Fortnite Settings -> 'Game UI' tab.",
                "Toggle 'Net Debug Stats' to 'ON'.",
                "HUD will display: Ping (ms), Inbound/Outbound Packet Loss (%), and Packets Per Second."
            ],
            "stutter_diagnosis": [
                "Red / Yellow Lines in Net Graph: Red indicates lost UDP packets; yellow indicates packet arrival jitter. Flush DNS and test link stability.",
                "Hitching During Asset Streaming: Sudden frame drops during fast movement are shader compiling or asset streaming, not network issues."
            ],
            "buffering_guidance": "In Epic Games Launcher -> Fortnite Options, check 'Pre-download Streamed Assets' to avoid mid-match background downloads that cause micro-stutters.",
            "optimal_settings": [
                {"setting": "Rendering Mode", "value": "Performance", "desc": "Minimizes heavy DX12 pipeline stalls on mid-range hardware."},
                {"setting": "Pre-download Assets", "value": "Checked (Launcher)", "desc": "Eliminates mid-game disk/network streaming stutters entirely."}
            ]
        },
        "apex_cs2": {
            "title": "Apex Legends & Counter-Strike 2",
            "telemetry_setup": [
                "Apex Legends: Settings -> Gameplay -> Performance Display -> Set to 'ON'.",
                "CS2: Settings -> Game -> Telemetry -> Set 'Show Ping', 'Show Packet Loss', and 'Show Frame Time' to 'Always'."
            ],
            "stutter_diagnosis": [
                "CS2 Sub-Tick Misdelivery: If CS2 displays packet misdelivery icons, router queue backlog is scrambling packet order.",
                "Apex Prediction Errors: Red speedometer / branching icons indicate client-server position desync from packet loss."
            ],
            "buffering_guidance": "In CS2 Game Settings, set 'Buffer to Smooth Packet Loss' to 'None' for minimum hitreg delay on fiber/cable. Use '1 packet' if unavoidable ISP jitter exists.",
            "optimal_settings": [
                {"setting": "CS2 Packet Buffer", "value": "None (or 1 packet)", "desc": "Lowest hitreg delay on wired connections."},
                {"setting": "Apex FPS Cap", "value": "Refresh - 3", "desc": "Keeps GPU usage below 95% to maintain Reflex pipeline."}
            ]
        }
    }

    def __init__(self, snapshot_mgr: Optional[SnapshotManager] = None):
        self.snapshot_mgr = snapshot_mgr or SnapshotManager()

    def get_user_notes(self) -> List[Dict[str, Any]]:
        """Retrieve stored user game performance notes from state file."""
        return self.snapshot_mgr.get_all_profile_notes()

    def save_user_note(self, game: str, server: str, ping_range: str, profile: str, feel: str, notes: str) -> bool:
        """Add or update a game performance observation entry in single state file."""
        return self.snapshot_mgr.save_profile_note(
            game=game,
            server=server,
            ping_range=ping_range,
            profile=profile,
            feel=feel,
            notes=notes
        )

    def delete_user_note(self, note_id: str) -> bool:
        """Delete an existing note by ID."""
        return self.snapshot_mgr.delete_profile_note(note_id)


# Alias
GameProfiles = GameProfileManager
