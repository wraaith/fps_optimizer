import customtkinter as ctk
from typing import Optional, Dict, Any
from .theme_manager import get_theme, is_cyber_mode, get_font

class SentinelView(ctk.CTkFrame):
    """Unified UI view for the Universal AI Game Sentinel."""
    
    def __init__(self, master: Any, service: Any, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        self.service = service
        theme = get_theme()
        
        # Header
        title = ctk.CTkLabel(self, text="UNIVERSAL AI GAME SENTINEL" if is_cyber_mode() else "Universal AI Game Sentinel", 
                             font=get_font(24, "bold"), text_color=theme["text_primary"])
        title.pack(anchor="w", pady=(0, 10))
        
        subtitle = ctk.CTkLabel(self, text="Autonomous monitoring, classification, and safe optimization.",
                                font=get_font(14, "normal"), text_color=theme["text_secondary"])
        subtitle.pack(anchor="w", pady=(0, 20))
        
        # Grid Layout for main content
        self.grid_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.grid_frame.pack(fill="both", expand=True)
        self.grid_frame.grid_columnconfigure((0, 1), weight=1)
        
        # 1. State & Modes Card
        self.state_card = ctk.CTkFrame(self.grid_frame, fg_color=theme["card_bg"], corner_radius=8)
        self.state_card.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        ctk.CTkLabel(self.state_card, text="Sentinel State", font=get_font(16, "bold"), text_color=theme["text_primary"]).pack(anchor="w", padx=15, pady=10)
        self.lbl_active_game = ctk.CTkLabel(self.state_card, text="Active Game: None", font=get_font(13), text_color=theme["text_secondary"])
        self.lbl_active_game.pack(anchor="w", padx=15)
        self.lbl_state = ctk.CTkLabel(self.state_card, text="Status: IDLE", font=get_font(13), text_color=theme["text_secondary"])
        self.lbl_state.pack(anchor="w", padx=15)
        
        # 2. Live Diagnostics
        self.diag_card = ctk.CTkFrame(self.grid_frame, fg_color=theme["card_bg"], corner_radius=8)
        self.diag_card.grid(row=0, column=1, sticky="nsew", padx=10, pady=10)
        ctk.CTkLabel(self.diag_card, text="Live Diagnostics", font=get_font(16, "bold"), text_color=theme["text_primary"]).pack(anchor="w", padx=15, pady=10)
        self.lbl_diag = ctk.CTkLabel(self.diag_card, text="Awaiting data...", font=get_font(13), text_color=theme["text_secondary"])
        self.lbl_diag.pack(anchor="w", padx=15)
        
        # 3. Interventions & Stutters
        self.interv_card = ctk.CTkFrame(self.grid_frame, fg_color=theme["card_bg"], corner_radius=8)
        self.interv_card.grid(row=1, column=0, sticky="nsew", padx=10, pady=10)
        ctk.CTkLabel(self.interv_card, text="Interventions", font=get_font(16, "bold"), text_color=theme["text_primary"]).pack(anchor="w", padx=15, pady=10)
        self.lbl_stutter = ctk.CTkLabel(self.interv_card, text="Detected: None", font=get_font(13), text_color=theme["text_secondary"])
        self.lbl_stutter.pack(anchor="w", padx=15)
        self.lbl_last_action = ctk.CTkLabel(self.interv_card, text="Last Action: None", font=get_font(13), text_color=theme["text_secondary"])
        self.lbl_last_action.pack(anchor="w", padx=15)
        
        # 4. Snapshots & Rollback
        self.snap_card = ctk.CTkFrame(self.grid_frame, fg_color=theme["card_bg"], corner_radius=8)
        self.snap_card.grid(row=1, column=1, sticky="nsew", padx=10, pady=10)
        ctk.CTkLabel(self.snap_card, text="Rollback Engine", font=get_font(16, "bold"), text_color=theme["text_primary"]).pack(anchor="w", padx=15, pady=10)
        self.btn_snapshot = ctk.CTkButton(self.snap_card, text="Create Snapshot", command=self._create_snapshot, 
                                          fg_color=theme["btn_bg"], hover_color=theme["btn_hover"])
        self.btn_snapshot.pack(pady=10)
        
    def _create_snapshot(self):
        # Stub
        pass
        
    def refresh(self):
        # Stub for live updates
        pass
