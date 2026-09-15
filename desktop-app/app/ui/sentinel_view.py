import os
import json
import csv
import time
from typing import Optional, Dict, Any, List

import customtkinter as ctk
from .theme_manager import get_theme, is_cyber_mode, get_font
from sentinel.models import SentinelMode, SentinelState

class SentinelView(ctk.CTkFrame):
    """
    Unified UI view for the Universal AI Game Sentinel.
    Provides complete observability, live diagnostics, metrics health,
    game profiles, recommendation details, event timeline, and advanced debug.
    Strictly enforces MONITOR_ONLY mode without enabling automatic interventions.
    """
    
    def __init__(self, master: Any, service: Any = None, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        if service is None:
            from sentinel.service import SentinelService
            self.service = SentinelService.get_instance()
        else:
            self.service = service
            
        self.theme = get_theme()
        self.card_bg = self.theme.get("bg_card", self.theme.get("card_bg", "#090e23"))
        self._after_id = None
        self._export_status_text = ""
        
        self._build_ui()
        self.refresh()
        
        # Start periodic UI refresh loop (1s interval)
        self._after_id = self.after(1000, self._periodic_refresh)

    def _build_ui(self):
        # ── 1. Header & Title ──────────────────────────────────────
        header_frame = ctk.CTkFrame(self, fg_color="transparent")
        header_frame.pack(fill="x", pady=(0, 10))
        
        title = ctk.CTkLabel(
            header_frame,
            text="⚡ UNIVERSAL AI GAME SENTINEL" if is_cyber_mode() else "Universal AI Game Sentinel",
            font=get_font(22, "bold"),
            text_color=self.theme.get("text_primary", "#ffffff")
        )
        title.pack(side="left", anchor="w")
        
        # Lifecycle buttons on the top right
        btn_frame = ctk.CTkFrame(header_frame, fg_color="transparent")
        btn_frame.pack(side="right", anchor="e")
        
        self.btn_toggle = ctk.CTkButton(
            btn_frame,
            text="Start Sentinel",
            width=110,
            command=self._toggle_service,
            fg_color="#1f538d",
            hover_color="#14375e"
        )
        self.btn_toggle.pack(side="left", padx=6)
        
        self.btn_emergency_stop = ctk.CTkButton(
            btn_frame,
            text="🛑 Emergency Stop",
            width=130,
            command=self._emergency_stop,
            fg_color="#8b0000",
            hover_color="#5a0000",
            text_color="white",
            font=get_font(12, "bold")
        )
        self.btn_emergency_stop.pack(side="left", padx=6)

        # ── 2. Enforced Monitor-Only Safety Banner ──────────────────
        self.banner_frame = ctk.CTkFrame(
            self,
            fg_color="#2b1b04" if not is_cyber_mode() else "#1a1202",
            border_width=1,
            border_color="#d97706",
            corner_radius=6
        )
        self.banner_frame.pack(fill="x", pady=(0, 12))
        
        self.banner_label = ctk.CTkLabel(
            self.banner_frame,
            text="🛡️ Monitor-only: no system changes are currently allowed. Real interventions and automatic tuning are blocked.",
            font=get_font(12, "bold"),
            text_color="#fbbf24"
        )
        self.banner_label.pack(side="left", padx=14, pady=8)

        # ── 3. Tabview for Observability Sections ──────────────────
        self.tabview = ctk.CTkTabview(
            self,
            fg_color=self.card_bg,
            segmented_button_selected_color="#1f538d",
            segmented_button_selected_hover_color="#14375e"
        )
        self.tabview.pack(fill="both", expand=True)
        
        self.tab_overview = self.tabview.add("Overview & Health")
        self.tab_profiles = self.tabview.add("Game Profiles")
        self.tab_recommendations = self.tabview.add("Recommendations & Timeline")
        self.tab_rollback = self.tabview.add("Snapshots & Ledger")
        self.tab_debug = self.tabview.add("Advanced Debug")
        
        self._build_overview_tab()
        self._build_profiles_tab()
        self._build_recommendations_tab()
        self._build_rollback_tab()
        self._build_debug_tab()

    # ── Tab 1: Overview & Live Diagnostics ────────────────────────
    def _build_overview_tab(self):
        container = ctk.CTkScrollableFrame(self.tab_overview, fg_color="transparent")
        container.pack(fill="both", expand=True, padx=4, pady=4)
        
        # Summary Grid
        self.overview_card = ctk.CTkFrame(container, fg_color=self.card_bg, border_width=1, border_color="#333333")
        self.overview_card.pack(fill="x", pady=(0, 10), padx=4)
        
        ctk.CTkLabel(self.overview_card, text="Sentinel Operational Summary", font=get_font(15, "bold"), text_color=self.theme["text_primary"]).pack(anchor="w", padx=14, pady=(10, 6))
        
        grid = ctk.CTkFrame(self.overview_card, fg_color="transparent")
        grid.pack(fill="x", padx=14, pady=(0, 10))
        grid.grid_columnconfigure((0, 1, 2, 3), weight=1)
        
        self.lbl_mode = ctk.CTkLabel(grid, text="Mode: MONITOR_ONLY", font=get_font(12, "bold"), text_color="#38bdf8")
        self.lbl_mode.grid(row=0, column=0, sticky="w", pady=2)
        
        self.lbl_state = ctk.CTkLabel(grid, text="State: IDLE", font=get_font(12), text_color=self.theme["text_secondary"])
        self.lbl_state.grid(row=0, column=1, sticky="w", pady=2)
        
        self.lbl_active_game = ctk.CTkLabel(grid, text="Active Game: None", font=get_font(12), text_color=self.theme["text_secondary"])
        self.lbl_active_game.grid(row=0, column=2, sticky="w", pady=2)
        
        self.lbl_worker = ctk.CTkLabel(grid, text="Worker: STOPPED", font=get_font(12), text_color=self.theme["text_secondary"])
        self.lbl_worker.grid(row=0, column=3, sticky="w", pady=2)
        
        self.lbl_consumers = ctk.CTkLabel(grid, text="Metrics Consumers: 0", font=get_font(12), text_color=self.theme["text_secondary"])
        self.lbl_consumers.grid(row=1, column=0, sticky="w", pady=2)
        
        self.lbl_pm_status = ctk.CTkLabel(grid, text="PresentMon: STOPPED", font=get_font(12), text_color=self.theme["text_secondary"])
        self.lbl_pm_status.grid(row=1, column=1, sticky="w", pady=2)
        
        self.lbl_last_class = ctk.CTkLabel(grid, text="Last Anomaly: None", font=get_font(12), text_color=self.theme["text_secondary"])
        self.lbl_last_class.grid(row=1, column=2, sticky="w", pady=2)
        
        self.lbl_confidence = ctk.CTkLabel(grid, text="Confidence: 0%", font=get_font(12), text_color=self.theme["text_secondary"])
        self.lbl_confidence.grid(row=1, column=3, sticky="w", pady=2)

        self.lbl_interv_active = ctk.CTkLabel(grid, text="Interventions Active: None (BLOCKED)", font=get_font(12), text_color="#10b981")
        self.lbl_interv_active.grid(row=2, column=0, columnspan=2, sticky="w", pady=2)
        
        self.lbl_rollback_avail = ctk.CTkLabel(grid, text="Rollback Available: Yes", font=get_font(12), text_color=self.theme["text_secondary"])
        self.lbl_rollback_avail.grid(row=2, column=2, columnspan=2, sticky="w", pady=2)

        # Export Session Summary Controls
        export_bar = ctk.CTkFrame(self.overview_card, fg_color="transparent")
        export_bar.pack(fill="x", padx=14, pady=(6, 12))
        
        btn_json = ctk.CTkButton(export_bar, text="📥 Export Summary (JSON)", width=170, command=self._export_json, fg_color="#1e3a8a", hover_color="#172554")
        btn_json.pack(side="left", padx=(0, 8))
        
        btn_csv = ctk.CTkButton(export_bar, text="📥 Export Summary (CSV)", width=170, command=self._export_csv, fg_color="#1e3a8a", hover_color="#172554")
        btn_csv.pack(side="left", padx=(0, 8))
        
        self.lbl_export_status = ctk.CTkLabel(export_bar, text="", font=get_font(11), text_color="#10b981")
        self.lbl_export_status.pack(side="left", padx=6)

        # Metrics Health Table
        health_card = ctk.CTkFrame(container, fg_color=self.card_bg, border_width=1, border_color="#333333")
        health_card.pack(fill="x", pady=(0, 10), padx=4)
        
        ctk.CTkLabel(health_card, text="Live Telemetry & Metrics Health", font=get_font(15, "bold"), text_color=self.theme.get("text_primary", "#ffffff")).pack(anchor="w", padx=14, pady=(10, 4))
        ctk.CTkLabel(health_card, text="Status indicators: [measured] verified live data, [stale] delayed >3s, [unavailable] sensor inactive, [error] reading failed.", font=get_font(11), text_color=self.theme.get("text_secondary", "#888888")).pack(anchor="w", padx=14, pady=(0, 8))

        self.table_frame = ctk.CTkFrame(health_card, fg_color="transparent")
        self.table_frame.pack(fill="x", padx=14, pady=(0, 12))
        self.table_frame.grid_columnconfigure((0, 1, 2, 3), weight=1)
        
        headers = ["Metric", "Observed Value", "Data Source", "Health Status"]
        for col_idx, h in enumerate(headers):
            lbl = ctk.CTkLabel(self.table_frame, text=h, font=get_font(12, "bold"), text_color=self.theme.get("text_primary", "#ffffff"))
            lbl.grid(row=0, column=col_idx, sticky="w", pady=(0, 4))

        self.metric_rows: Dict[str, Dict[str, Any]] = {}
        row_keys = [
            ("fps", "Average FPS"),
            ("frame_time_p50_ms", "Frame Time Median (p50)"),
            ("frame_time_p95_ms", "Frame Time 95th Percentile (p95)"),
            ("frame_time_p99_ms", "Frame Time 99th Percentile (p99)"),
            ("one_percent_low_fps", "1% Low FPS"),
            ("cpu_usage", "Total CPU Usage"),
            ("cpu_cores_usage", "Per-Core CPU Usage"),
            ("gpu_usage", "GPU Utilization"),
            ("ram_pressure", "RAM Pressure"),
            ("hard_faults", "Hard Page Faults"),
            ("disk_latency_ms", "Disk Latency"),
            ("network_rtt_ms", "Network RTT (Ping)"),
            ("network_jitter_ms", "Network Jitter"),
            ("packet_loss_percent", "Packet Loss")
        ]
        
        for r_idx, (key, label) in enumerate(row_keys, start=1):
            lbl_name = ctk.CTkLabel(self.table_frame, text=label, font=get_font(12), text_color=self.theme.get("text_secondary", "#888888"))
            lbl_name.grid(row=r_idx, column=0, sticky="w", pady=2)
            
            lbl_val = ctk.CTkLabel(self.table_frame, text="--", font=get_font(12, "bold"), text_color=self.theme.get("text_primary", "#ffffff"))
            lbl_val.grid(row=r_idx, column=1, sticky="w", pady=2)
            
            lbl_src = ctk.CTkLabel(self.table_frame, text="--", font=get_font(11), text_color=self.theme.get("text_secondary", "#888888"))
            lbl_src.grid(row=r_idx, column=2, sticky="w", pady=2)
            
            lbl_st = ctk.CTkLabel(self.table_frame, text="unavailable", font=get_font(11, "bold"), text_color="#94a3b8")
            lbl_st.grid(row=r_idx, column=3, sticky="w", pady=2)
            
            self.metric_rows[key] = {"val": lbl_val, "src": lbl_src, "status": lbl_st}

    # ── Tab 2: Game Profiles ─────────────────────────────────────
    def _build_profiles_tab(self):
        container = ctk.CTkScrollableFrame(self.tab_profiles, fg_color="transparent")
        container.pack(fill="both", expand=True, padx=4, pady=4)
        
        notice = ctk.CTkLabel(
            container,
            text="Game adapters operate strictly in recommendation-only mode. No game files, memory, or settings are altered.",
            font=get_font(11, "bold"),
            text_color="#38bdf8"
        )
        notice.pack(anchor="w", padx=8, pady=(0, 10))

        profiles_data = [
            {
                "id": "valorant",
                "title": "Valorant (Riot Games)",
                "exe": "VALORANT-Win64-Shipping.exe",
                "telemetry": [
                    "Open Settings > Video > Stats",
                    "Enable 'Client FPS' (Text Only)",
                    "Enable 'Network RTT' (Text Only)",
                    "Enable 'Network RTT Jitter' (Text Only)",
                    "Enable 'Packet Loss' (Text Only)"
                ],
                "classification_rule": "Separates network stutter (RTT jitter >5ms / packet loss >0) from render spikes (>5ms variance).",
                "recommendation": "Network Buffering adjustment (Minimum for clean connection, Moderate if jitter/loss detected).",
                "profile": "Buffer Mode: Minimum | Anticheat Vanguard: Protected"
            },
            {
                "id": "fortnite",
                "title": "Fortnite (Epic Games)",
                "exe": "FortniteClient-Win64-Shipping.exe",
                "telemetry": [
                    "Open Settings > Game UI",
                    "Set 'Net Debug Stats' to ON",
                    "Open Settings > Video > Enable 'Show FPS'"
                ],
                "classification_rule": "Detects DX12 shader compilation stutter and frame-time variance exceeding 8ms.",
                "recommendation": "Performance Mode rendering advice for low-VRAM GPUs with severe frame-time spikes.",
                "profile": "Rendering: DX12 / Performance Mode advisory"
            },
            {
                "id": "cs2",
                "title": "Counter-Strike 2 (Valve)",
                "exe": "cs2.exe",
                "telemetry": [
                    "Open Settings > Telemetry",
                    "Show Frame Time and FPS: Always",
                    "Show Ping: Always",
                    "Show Packet Loss / Misdelivery: Always"
                ],
                "classification_rule": "Evaluates packet misdelivery vs sub-tick render queue congestion.",
                "recommendation": "Calculated safe fps_max cap slightly below 99% refresh rate to stabilize render pacing.",
                "profile": "Frame Pacing: Sub-tick telemetry advisory"
            },
            {
                "id": "apex",
                "title": "Apex Legends (Respawn / EA)",
                "exe": "r5apex.exe",
                "telemetry": [
                    "Open Settings > Gameplay",
                    "Set 'Performance Display' to ON",
                    "Check connected data center on title screen"
                ],
                "classification_rule": "Detects route routing instability (>20ms jitter) vs GPU render queue overflow.",
                "recommendation": "Alternative data center selection if packet loss persists; launch options fps cap (+fps_max 144).",
                "profile": "Launch Option: +fps_max 144 (User manual)"
            }
        ]

        self.game_cards: Dict[str, Dict[str, Any]] = {}
        for p in profiles_data:
            card = ctk.CTkFrame(container, fg_color=self.card_bg, border_width=1, border_color="#333333")
            card.pack(fill="x", pady=(0, 10), padx=4)
            
            top_row = ctk.CTkFrame(card, fg_color="transparent")
            top_row.pack(fill="x", padx=12, pady=(8, 2))
            
            lbl_title = ctk.CTkLabel(top_row, text=p["title"], font=get_font(14, "bold"), text_color=self.theme.get("text_primary", "#ffffff"))
            lbl_title.pack(side="left")
            
            lbl_status = ctk.CTkLabel(top_row, text="Status: IDLE (Not Detected)", font=get_font(11, "bold"), text_color="#94a3b8")
            lbl_status.pack(side="right")
            
            ctk.CTkLabel(card, text=f"Executable: {p['exe']}", font=get_font(11), text_color=self.theme.get("text_secondary", "#888888")).pack(anchor="w", padx=12, pady=1)
            
            steps_text = " • " + "\n • ".join(p["telemetry"])
            ctk.CTkLabel(card, text=f"Telemetry Setup:\n{steps_text}", font=get_font(11), text_color=self.theme.get("text_secondary", "#888888"), justify="left").pack(anchor="w", padx=12, pady=3)
            
            ctk.CTkLabel(card, text=f"Classification: {p['classification_rule']}", font=get_font(11), text_color=self.theme.get("text_secondary", "#888888")).pack(anchor="w", padx=12, pady=1)
            ctk.CTkLabel(card, text=f"Advisory: {p['recommendation']}", font=get_font(11), text_color="#38bdf8").pack(anchor="w", padx=12, pady=1)
            ctk.CTkLabel(card, text=f"Profile Info: {p['profile']}", font=get_font(11), text_color=self.theme.get("text_secondary", "#888888")).pack(anchor="w", padx=12, pady=(1, 8))
            
            self.game_cards[p["id"]] = {"status": lbl_status, "exe": p["exe"]}

    # ── Tab 3: Recommendations & Event Timeline ──────────────────
    def _build_recommendations_tab(self):
        container = ctk.CTkScrollableFrame(self.tab_recommendations, fg_color="transparent")
        container.pack(fill="both", expand=True, padx=4, pady=4)
        
        # Recommendation Card
        rec_card = ctk.CTkFrame(container, fg_color=self.card_bg, border_width=1, border_color="#333333")
        rec_card.pack(fill="x", pady=(0, 10), padx=4)
        
        ctk.CTkLabel(rec_card, text="Detailed Recommendation & Stutter Diagnostic", font=get_font(15, "bold"), text_color=self.theme.get("text_primary", "#ffffff")).pack(anchor="w", padx=14, pady=(10, 4))
        
        self.lbl_rec_game = ctk.CTkLabel(rec_card, text="Target Game: None", font=get_font(12), text_color=self.theme.get("text_secondary", "#888888"))
        self.lbl_rec_game.pack(anchor="w", padx=14, pady=1)
        
        self.lbl_rec_class = ctk.CTkLabel(rec_card, text="Classification: None", font=get_font(12, "bold"), text_color="#38bdf8")
        self.lbl_rec_class.pack(anchor="w", padx=14, pady=1)
        
        self.lbl_rec_evidence = ctk.CTkLabel(rec_card, text="Evidence: Baseline nominal", font=get_font(12), text_color=self.theme.get("text_secondary", "#888888"))
        self.lbl_rec_evidence.pack(anchor="w", padx=14, pady=1)
        
        self.lbl_rec_confidence = ctk.CTkLabel(rec_card, text="Confidence: 0.0", font=get_font(12), text_color=self.theme.get("text_secondary", "#888888"))
        self.lbl_rec_confidence.pack(anchor="w", padx=14, pady=1)
        
        self.lbl_rec_action = ctk.CTkLabel(rec_card, text="Suggested Action: None", font=get_font(12), text_color=self.theme.get("text_secondary", "#888888"))
        self.lbl_rec_action.pack(anchor="w", padx=14, pady=1)
        
        self.lbl_rec_risk = ctk.CTkLabel(rec_card, text="Risk Assessment: None", font=get_font(12), text_color=self.theme.get("text_secondary", "#888888"))
        self.lbl_rec_risk.pack(anchor="w", padx=14, pady=1)
        
        self.lbl_rec_rev = ctk.CTkLabel(rec_card, text="Reversibility: Fully Reversible (Manual user adjustment)", font=get_font(12), text_color=self.theme.get("text_secondary", "#888888"))
        self.lbl_rec_rev.pack(anchor="w", padx=14, pady=1)
        
        self.lbl_rec_blocked = ctk.CTkLabel(rec_card, text="Execution Status: Blocked (Monitor-only mode enforced)", font=get_font(12, "bold"), text_color="#f59e0b")
        self.lbl_rec_blocked.pack(anchor="w", padx=14, pady=(1, 10))

        # Event Timeline Card
        tl_card = ctk.CTkFrame(container, fg_color=self.card_bg, border_width=1, border_color="#333333")
        tl_card.pack(fill="both", expand=True, pady=(0, 4), padx=4)
        
        ctk.CTkLabel(tl_card, text="Bounded Event Timeline (Audit Log)", font=get_font(15, "bold"), text_color=self.theme.get("text_primary", "#ffffff")).pack(anchor="w", padx=14, pady=(10, 4))
        ctk.CTkLabel(tl_card, text="Displays recent lifecycle and anomaly events. Bounded to 200 items in-memory without persistent raw sample bloat.", font=get_font(11), text_color=self.theme.get("text_secondary", "#888888")).pack(anchor="w", padx=14, pady=(0, 6))

        self.timeline_textbox = ctk.CTkTextbox(tl_card, height=220, font=("Consolas", 11), fg_color="#111827", text_color="#e5e7eb")
        self.timeline_textbox.pack(fill="both", expand=True, padx=14, pady=(0, 12))
        self.timeline_textbox.configure(state="disabled")

    # ── Tab 4: Snapshots & Ledger ────────────────────────────────
    def _build_rollback_tab(self):
        container = ctk.CTkScrollableFrame(self.tab_rollback, fg_color="transparent")
        container.pack(fill="both", expand=True, padx=4, pady=4)
        
        card = ctk.CTkFrame(container, fg_color=self.card_bg, border_width=1, border_color="#333333")
        card.pack(fill="x", pady=(0, 10), padx=4)
        
        ctk.CTkLabel(card, text="State Ledger & Rollback Integrity", font=get_font(15, "bold"), text_color=self.theme.get("text_primary", "#ffffff")).pack(anchor="w", padx=14, pady=(10, 4))
        
        self.lbl_ledger_version = ctk.CTkLabel(card, text="Ledger Schema Version: 2", font=get_font(12), text_color=self.theme.get("text_secondary", "#888888"))
        self.lbl_ledger_version.pack(anchor="w", padx=14, pady=1)
        
        self.lbl_ledger_status = ctk.CTkLabel(card, text="Ledger Integrity: Clean", font=get_font(12), text_color="#10b981")
        self.lbl_ledger_status.pack(anchor="w", padx=14, pady=1)
        
        self.lbl_safe_mode_warn = ctk.CTkLabel(card, text="", font=get_font(12, "bold"), text_color="#ef4444")
        self.lbl_safe_mode_warn.pack(anchor="w", padx=14, pady=1)

        ctk.CTkLabel(card, text="Policy Notice: Automatic modifications to DNS, registry, power plan, and background processes are completely disabled.", font=get_font(11), text_color=self.theme.get("text_secondary", "#888888")).pack(anchor="w", padx=14, pady=(6, 10))

    # ── Tab 5: Advanced Debug ────────────────────────────────────
    def _build_debug_tab(self):
        container = ctk.CTkScrollableFrame(self.tab_debug, fg_color="transparent")
        container.pack(fill="both", expand=True, padx=4, pady=4)
        
        card = ctk.CTkFrame(container, fg_color=self.card_bg, border_width=1, border_color="#333333")
        card.pack(fill="x", pady=(0, 10), padx=4)
        
        ctk.CTkLabel(card, text="Sentinel Internal State Machine & Telemetry Debug", font=get_font(15, "bold"), text_color=self.theme.get("text_primary", "#ffffff")).pack(anchor="w", padx=14, pady=(10, 6))

        self.debug_textbox = ctk.CTkTextbox(card, height=320, font=("Consolas", 11), fg_color="#0f172a", text_color="#38bdf8")
        self.debug_textbox.pack(fill="both", expand=True, padx=14, pady=(0, 12))
        self.debug_textbox.configure(state="disabled")

    # ── Actions & Handlers ───────────────────────────────────────
    def _toggle_service(self):
        if self.service.is_running():
            self.service.stop()
        else:
            self.service.start()
        self.refresh()

    def _emergency_stop(self):
        self.service.emergency_stop()
        self.refresh()

    def _export_json(self):
        try:
            summary = self.service.export_session_summary()
            os.makedirs("desktop-app/app/data/session_exports", exist_ok=True)
            path = f"desktop-app/app/data/session_exports/session_summary_{int(time.time())}.json"
            with open(path, "w", encoding="utf-8") as f:
                json.dump(summary, f, indent=2)
            self.lbl_export_status.configure(text=f"Exported JSON: {os.path.basename(path)}", text_color="#10b981")
        except Exception as e:
            self.lbl_export_status.configure(text=f"Export Failed: {e}", text_color="#ef4444")

    def _export_csv(self):
        try:
            summary = self.service.export_session_summary()
            os.makedirs("desktop-app/app/data/session_exports", exist_ok=True)
            path = f"desktop-app/app/data/session_exports/session_summary_{int(time.time())}.csv"
            
            # Flatten dictionary fields
            flat_rows = []
            for k, v in summary.items():
                if isinstance(v, dict) and "value" in v and "status" in v:
                    flat_rows.append({"metric": k, "value": v["value"], "status": v["status"]})
                else:
                    flat_rows.append({"metric": k, "value": str(v), "status": "measured"})
                    
            with open(path, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=["metric", "value", "status"])
                writer.writeheader()
                writer.writerows(flat_rows)
            self.lbl_export_status.configure(text=f"Exported CSV: {os.path.basename(path)}", text_color="#10b981")
        except Exception as e:
            self.lbl_export_status.configure(text=f"Export Failed: {e}", text_color="#ef4444")

    # ── Refresh & Update Loop ────────────────────────────────────
    def _periodic_refresh(self):
        try:
            if not self.winfo_exists():
                return
            self.refresh()
        except Exception:
            pass
        finally:
            self._after_id = self.after(1000, self._periodic_refresh)

    def refresh(self):
        """Updates all UI elements from SentinelService telemetry."""
        if not self.service:
            return
            
        is_running = self.service.is_running()
        self.btn_toggle.configure(
            text="Stop Sentinel" if is_running else "Start Sentinel",
            fg_color="#8b0000" if is_running else "#1f538d",
            hover_color="#5a0000" if is_running else "#14375e"
        )
        
        # 1. Operational Summary
        state_name = getattr(self.service.controller.state_machine, "current_state", SentinelState.IDLE).name
        self.lbl_state.configure(text=f"State: {state_name}")
        
        game_info = self.service.get_active_game_info()
        self.lbl_active_game.configure(text=f"Active Game: {game_info.get('name', 'None')}")
        
        has_worker = self.service.has_active_worker()
        self.lbl_worker.configure(text=f"Worker: {'RUNNING' if has_worker else 'STOPPED'}", text_color="#10b981" if has_worker else self.theme["text_secondary"])
        
        # Debug / telemetry info
        debug_info = self.service.get_advanced_debug_info()
        self.lbl_consumers.configure(text=f"Metrics Consumers: {debug_info.get('metrics_consumer_count', 0)}")
        self.lbl_pm_status.configure(text=f"PresentMon: {debug_info.get('presentmon_process_status', 'STOPPED')}")
        
        last_anom = getattr(self.service, "_last_anomaly", {})
        self.lbl_last_class.configure(text=f"Last Anomaly: {last_anom.get('classification', 'None')}")
        self.lbl_confidence.configure(text=f"Confidence: {int(last_anom.get('confidence', 0.0) * 100)}%")

        # 2. Metrics Health Table
        health = self.service.get_metrics_health()
        for key, widgets in self.metric_rows.items():
            data = health.get(key, {})
            val = data.get("value")
            src = data.get("source", "--")
            st = data.get("status", "unavailable")
            
            if isinstance(val, list):
                disp_val = ", ".join(str(v) for v in val[:4]) + ("..." if len(val) > 4 else "")
            elif val is not None:
                disp_val = str(val)
            else:
                disp_val = "--"
                
            widgets["val"].configure(text=disp_val)
            widgets["src"].configure(text=src)
            
            # Color code status
            color_map = {
                "measured": "#10b981",
                "stale": "#f59e0b",
                "unavailable": "#94a3b8",
                "error": "#ef4444"
            }
            widgets["status"].configure(text=st, text_color=color_map.get(st, "#94a3b8"))

        # 3. Game Profile Cards
        active_exe = (game_info.get("exe") or "").lower()
        for g_id, card_widgets in self.game_cards.items():
            target_exe = card_widgets["exe"].lower()
            if game_info.get("detected") and target_exe in active_exe:
                card_widgets["status"].configure(text="Status: ACTIVE (Detected)", text_color="#10b981")
            else:
                card_widgets["status"].configure(text="Status: IDLE (Not Detected)", text_color="#94a3b8")

        # 4. Recommendation Card
        last_rec = getattr(self.service, "_last_recommendation", {})
        self.lbl_rec_game.configure(text=f"Target Game: {last_rec.get('game', 'None')}")
        self.lbl_rec_class.configure(text=f"Classification: {last_rec.get('classification', 'None')}")
        self.lbl_rec_evidence.configure(text=f"Evidence: {last_rec.get('evidence', 'Telemetry nominal')}")
        self.lbl_rec_confidence.configure(text=f"Confidence: {last_rec.get('confidence', 0.0)}")
        self.lbl_rec_action.configure(text=f"Suggested Action: {last_rec.get('action', 'None')}")
        self.lbl_rec_risk.configure(text=f"Risk Assessment: {last_rec.get('risk', 'none')}")
        self.lbl_rec_blocked.configure(text=f"Reason Blocked: {last_rec.get('reason_blocked', 'Monitor-only mode')}")

        # 5. Timeline Textbox
        events = self.service.get_event_timeline()
        self.timeline_textbox.configure(state="normal")
        self.timeline_textbox.delete("1.0", "end")
        for ev in reversed(events[-50:]):  # Display last 50 in reverse chronological order
            t_str = time.strftime("%H:%M:%S", time.localtime(ev.get("timestamp", 0)))
            self.timeline_textbox.insert("end", f"[{t_str}] {ev.get('event', '').upper()}: {ev.get('details', '')}\n")
        self.timeline_textbox.configure(state="disabled")

        # 6. Snapshots / Ledger Tab
        if debug_info.get("safe_mode"):
            self.lbl_ledger_status.configure(text="Ledger Integrity: SAFE MODE (Corrupt Ledger Protected)", text_color="#ef4444")
            self.lbl_safe_mode_warn.configure(text="⚠️ Safe mode engaged: Automatic interventions disabled due to ledger protection.")
        else:
            self.lbl_ledger_status.configure(text="Ledger Integrity: Clean & Verified", text_color="#10b981")
            self.lbl_safe_mode_warn.configure(text="")
        self.lbl_ledger_version.configure(text=f"Ledger Schema Version: {debug_info.get('ledger_schema_version', 2)}")

        # 7. Advanced Debug Textbox
        self.debug_textbox.configure(state="normal")
        self.debug_textbox.delete("1.0", "end")
        debug_str = json.dumps(debug_info, indent=2)
        self.debug_textbox.insert("end", debug_str)
        self.debug_textbox.configure(state="disabled")

    def destroy(self):
        """Cancels periodic refresh timer cleanly when window/view closes."""
        if self._after_id:
            try:
                self.after_cancel(self._after_id)
            except Exception:
                pass
            self._after_id = None
        super().destroy()
