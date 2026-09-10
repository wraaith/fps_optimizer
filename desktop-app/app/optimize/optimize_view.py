import customtkinter as ctk
import threading
import time

from optimize.optimizer_service import (
    get_current_available_ram_mb,
    get_top_memory_consumers,
    terminate_processes,
    auto_optimize_system,
    clear_standby_memory,
    trim_all_working_sets,
    get_sysmain_status,
    set_sysmain_enabled,
    get_memory_breakdown,
    check_has_ssd,
    get_foreground_game_process,
)
from optimize.ai_boost_service import get_ai_boost_service
from ui.theme_manager import is_cyber_mode, get_theme, get_font, PERFORMANCE_THEME, CYBER_THEME



class OptimizeView(ctk.CTkFrame):
    def __init__(self, parent, **kwargs):
        theme = get_theme()
        super().__init__(parent, fg_color=theme["bg_main"], **kwargs)
        
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)  # The main content area

        # ── Header ─────────────────────────────────────────────
        self.header_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.header_frame.grid(row=0, column=0, padx=20, pady=(15, 6), sticky="ew")
        self.header_frame.grid_columnconfigure(0, weight=1)
        self.header_frame.grid_columnconfigure(1, weight=0)

        is_cyber = is_cyber_mode()

        self.title_label = ctk.CTkLabel(
            self.header_frame,
            text="⚡ CYBER MATRIX // GAME BOOSTER" if is_cyber else "Game Booster",
            font=get_font(22, "bold"),
            text_color=theme["text_title"]
        )
        self.title_label.grid(row=0, column=0, sticky="w")
        
        self.subtitle_label = ctk.CTkLabel(
            self.header_frame,
            text="● 1.0ms HARDWARE TIMER · AUTONOMOUS FPS SENTINEL · ZERO-HITCH CACHE CONTROL" if is_cyber else "Intelligent Gaming Performance & Frame Pacing Sentinel",
            font=get_font(12, "normal"),
            text_color=theme["accent_cyan"] if is_cyber else theme["text_secondary"]
        )
        self.subtitle_label.grid(row=1, column=0, sticky="w", pady=(2, 0))

        # Backward compatibility for any external reference
        self.ram_label = self.subtitle_label

        # Toggle for Advanced Mode
        self.advanced_mode = ctk.BooleanVar(value=False)
        self.mode_switch = ctk.CTkSwitch(
            self.header_frame,
            text="[ ADVANCED PURGE OPS ]" if is_cyber else "Advanced Process Cleaner",
            variable=self.advanced_mode,
            command=self._toggle_mode,
            progress_color=theme["accent_cyan"],
            button_color="#ffffff",
            font=get_font(12, "bold")
        )
        self.mode_switch.grid(row=0, column=1, rowspan=2, sticky="e")

        # ── 1-Click Boost UI (Default) ─────────────────────────
        self.basic_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.basic_frame.grid(row=1, column=0, sticky="nsew")
        self.basic_frame.grid_columnconfigure(0, weight=1)
        self.basic_frame.grid_rowconfigure(0, weight=0)  # HUD banner
        self.basic_frame.grid_rowconfigure(1, weight=1)  # 2x2 grid
        self.basic_frame.grid_rowconfigure(2, weight=0)  # Bottom status pill

        # AI Sentinel Background Service
        self.ai_service = get_ai_boost_service()
        self.ai_service.set_callback(self._on_ai_status_update)

        # ── Real-Time Memory Health & Gaming Readiness HUD Banner ──
        self.hud_frame = ctk.CTkFrame(
            self.basic_frame,
            fg_color=theme["bg_card"],
            corner_radius=12,
            border_width=1,
            border_color=theme["border_glow"] if is_cyber else "#1e1e1e"
        )
        self.hud_frame.grid(row=0, column=0, padx=15, pady=(4, 6), sticky="ew")
        self.hud_frame.grid_columnconfigure((0, 1, 2), weight=1)

        # Stat 1: Active RAM
        self.hud_ram_col = ctk.CTkFrame(self.hud_frame, fg_color="transparent")
        self.hud_ram_col.grid(row=0, column=0, padx=14, pady=(8, 2), sticky="w")
        self.hud_ram_title = ctk.CTkLabel(
            self.hud_ram_col,
            text="// ACTIVE MEMORY" if is_cyber else "ACTIVE MEMORY IN USE",
            font=get_font(10, "bold"),
            text_color=theme["text_secondary"]
        )
        self.hud_ram_title.pack(anchor="w")
        self.hud_ram_val = ctk.CTkLabel(
            self.hud_ram_col,
            text="-- GB / -- GB (--%)",
            font=get_font(14, "bold", is_stat=True),
            text_color=theme["text_primary"]
        )
        self.hud_ram_val.pack(anchor="w")

        # Stat 2: Purgeable Standby Cache
        self.hud_cache_col = ctk.CTkFrame(self.hud_frame, fg_color="transparent")
        self.hud_cache_col.grid(row=0, column=1, padx=14, pady=(8, 2), sticky="w")
        self.hud_cache_title = ctk.CTkLabel(
            self.hud_cache_col,
            text="// PURGEABLE STANDBY CACHE" if is_cyber else "PURGEABLE STANDBY CACHE",
            font=get_font(10, "bold"),
            text_color=theme["text_secondary"]
        )
        self.hud_cache_title.pack(anchor="w")
        self.hud_cache_val = ctk.CTkLabel(
            self.hud_cache_col,
            text="-- MB Reclaimable",
            font=get_font(14, "bold", is_stat=True),
            text_color=theme["accent_cyan"] if is_cyber else "#00dd88"
        )
        self.hud_cache_val.pack(anchor="w")

        # Stat 3: Scheduler Timer
        self.hud_timer_col = ctk.CTkFrame(self.hud_frame, fg_color="transparent")
        self.hud_timer_col.grid(row=0, column=2, padx=14, pady=(8, 2), sticky="e")
        self.hud_timer_title = ctk.CTkLabel(
            self.hud_timer_col,
            text="// SCHEDULER RESOLUTION" if is_cyber else "FPS SCHEDULER RESOLUTION",
            font=get_font(10, "bold"),
            text_color=theme["text_secondary"]
        )
        self.hud_timer_title.pack(anchor="e")
        self.hud_timer_val = ctk.CTkLabel(
            self.hud_timer_col,
            text="● 1.0ms HIGH-RES [LOCKED]" if self.ai_service.is_running else "○ 15.6ms [DEFAULT]",
            font=get_font(13, "bold"),
            text_color=theme["accent_green"] if self.ai_service.is_running else theme["text_muted"]
        )
        self.hud_timer_val.pack(anchor="e")

        # Visual progress bar
        self.hud_progress = ctk.CTkProgressBar(
            self.hud_frame,
            height=6,
            corner_radius=3,
            fg_color=theme["bg_card_inner"],
            progress_color=theme["accent_cyan"] if is_cyber else theme["accent_primary"]
        )
        self.hud_progress.grid(row=1, column=0, columnspan=3, padx=14, pady=(2, 8), sticky="ew")
        self.hud_progress.set(0.5)

        # ── 2x2 Grid Card Container ──
        self.btn_container = ctk.CTkFrame(self.basic_frame, fg_color="transparent")
        self.btn_container.grid(row=1, column=0, sticky="nsew", padx=12, pady=2)
        self.btn_container.grid_columnconfigure(0, weight=1)
        self.btn_container.grid_columnconfigure(1, weight=1)
        self.btn_container.grid_rowconfigure(0, weight=1)
        self.btn_container.grid_rowconfigure(1, weight=1)

        # ── Card 1: 1-Click Boost (standby clear + trim) ──
        self.boost_card = ctk.CTkFrame(
            self.btn_container,
            fg_color=theme["bg_card"],
            corner_radius=14,
            border_width=1,
            border_color=theme["border_glow"] if is_cyber else "#1e1e1e"
        )
        self.boost_card.grid(row=0, column=0, padx=6, pady=5, sticky="nsew")
        self.boost_card.grid_columnconfigure(0, weight=1)

        self.boost_header = ctk.CTkFrame(self.boost_card, fg_color="transparent")
        self.boost_header.grid(row=0, column=0, padx=14, pady=(12, 3), sticky="ew")
        self.boost_header.grid_columnconfigure(0, weight=1)
        self.boost_header.grid_columnconfigure(1, weight=0)

        self.boost_title = ctk.CTkLabel(
            self.boost_header,
            text="⚡ QUANTUM RAM FLUSH" if is_cyber else "⚡ Quick RAM Flush",
            font=get_font(15, "bold"),
            text_color=theme["text_title"]
        )
        self.boost_title.grid(row=0, column=0, sticky="w")

        self.boost_tag = ctk.CTkLabel(
            self.boost_header,
            text="[ 1-CLICK ]" if is_cyber else "1-CLICK",
            font=get_font(10, "bold"),
            fg_color=theme["bg_card_inner"],
            text_color=theme["accent_cyan"] if is_cyber else "#ffffff",
            corner_radius=6,
            padx=7,
            pady=2
        )
        self.boost_tag.grid(row=0, column=1, sticky="e")

        self.boost_desc = ctk.CTkLabel(
            self.boost_card,
            text="Purge standby cache & trim working sets without closing running games.",
            font=get_font(11, "normal"),
            text_color=theme["text_secondary"],
            justify="left",
            wraplength=290
        )
        self.boost_desc.grid(row=1, column=0, padx=14, pady=(0, 6), sticky="w")

        self.boost_chip_frame = ctk.CTkFrame(self.boost_card, fg_color=theme["bg_card_inner"], corner_radius=8)
        self.boost_chip_frame.grid(row=2, column=0, padx=14, pady=(0, 8), sticky="ew")
        self.boost_chip_label = ctk.CTkLabel(
            self.boost_chip_frame,
            text="💾 STANDBY CACHE: Checking..." if is_cyber else "💾 Purgeable Cache: Checking...",
            font=get_font(11, "bold"),
            text_color=theme["accent_cyan"] if is_cyber else theme["text_primary"]
        )
        self.boost_chip_label.pack(padx=10, pady=4, anchor="w")

        self.boost_btn = ctk.CTkButton(
            self.boost_card,
            text="⚡ PURGE STANDBY RAM NOW" if is_cyber else "Flush RAM Now",
            font=get_font(13, "bold"),
            fg_color=theme["action_btn_fg"],
            hover_color=theme["action_btn_hover"],
            text_color=theme["action_btn_text"],
            height=38,
            corner_radius=19 if is_cyber else 8,
            command=self._run_auto_boost
        )
        self.boost_btn.grid(row=3, column=0, padx=14, pady=(0, 12), sticky="ew")

        # ── Card 2: AI Game Sentinel ──
        self.ai_card = ctk.CTkFrame(
            self.btn_container,
            fg_color=theme["bg_card"],
            corner_radius=14,
            border_width=1,
            border_color=theme["border_purple"] if is_cyber else "#1e1e1e"
        )
        self.ai_card.grid(row=0, column=1, padx=6, pady=5, sticky="nsew")
        self.ai_card.grid_columnconfigure(0, weight=1)

        self.ai_header = ctk.CTkFrame(self.ai_card, fg_color="transparent")
        self.ai_header.grid(row=0, column=0, padx=14, pady=(12, 3), sticky="ew")
        self.ai_header.grid_columnconfigure(0, weight=1)
        self.ai_header.grid_columnconfigure(1, weight=0)

        self.ai_card_title = ctk.CTkLabel(
            self.ai_header,
            text="🤖 AI FPS SENTINEL" if is_cyber else "🤖 AI Game Sentinel",
            font=get_font(15, "bold"),
            text_color=theme["accent_purple"] if is_cyber else theme["text_title"]
        )
        self.ai_card_title.grid(row=0, column=0, sticky="w")

        self.ai_tag = ctk.CTkLabel(
            self.ai_header,
            text="[ AUTO-PILOT ]" if is_cyber else "AUTO-PILOT",
            font=get_font(10, "bold"),
            fg_color=theme["bg_card_inner"],
            text_color=theme["accent_purple"] if is_cyber else "#ffffff",
            corner_radius=6,
            padx=7,
            pady=2
        )
        self.ai_tag.grid(row=0, column=1, sticky="e")

        self.ai_desc = ctk.CTkLabel(
            self.ai_card,
            text="Locks 1.0ms timer, elevates game CPU priority & stabilizes frame pacing.",
            font=get_font(11, "normal"),
            text_color=theme["text_secondary"],
            justify="left",
            wraplength=290
        )
        self.ai_desc.grid(row=1, column=0, padx=14, pady=(0, 6), sticky="w")

        self.ai_chip_frame = ctk.CTkFrame(self.ai_card, fg_color=theme["bg_card_inner"], corner_radius=8)
        self.ai_chip_frame.grid(row=2, column=0, padx=14, pady=(0, 8), sticky="ew")
        self.ai_status_badge = ctk.CTkLabel(
            self.ai_chip_frame,
            text="○ SENTINEL STANDBY · 15.6ms CLOCK" if is_cyber else ("○ Inactive · Click to activate 1.0ms lock" if not self.ai_service.is_running else "● Sentinel Active · 1.0ms Timer Locked"),
            font=get_font(11, "bold"),
            text_color=theme["accent_green"] if self.ai_service.is_running else theme["text_secondary"]
        )
        self.ai_status_badge.pack(padx=10, pady=4, anchor="w")

        self.ai_action_btn = ctk.CTkButton(
            self.ai_card,
            text="⚡ ENGAGE AI SENTINEL" if not self.ai_service.is_running else "⏹ DISENGAGE SENTINEL",
            font=get_font(13, "bold"),
            fg_color=theme["accent_purple"] if (is_cyber and not self.ai_service.is_running) else ("#00ff9f" if is_cyber else ("#00aa00" if self.ai_service.is_running else "#262626")),
            hover_color="#9333ea" if (is_cyber and not self.ai_service.is_running) else ("#34d399" if is_cyber else ("#008800" if self.ai_service.is_running else "#333333")),
            text_color="#ffffff" if (not is_cyber or not self.ai_service.is_running) else "#020617",
            height=38,
            corner_radius=19 if is_cyber else 8,
            command=self._toggle_ai_sentinel_btn
        )
        self.ai_action_btn.grid(row=3, column=0, padx=14, pady=(0, 12), sticky="ew")

        # ── Card 3: Process Terminator ──
        self.killer_card = ctk.CTkFrame(
            self.btn_container,
            fg_color=theme["bg_card"],
            corner_radius=14,
            border_width=1,
            border_color=theme["border_pink"] if is_cyber else "#1e1e1e"
        )
        self.killer_card.grid(row=1, column=0, padx=6, pady=5, sticky="nsew")
        self.killer_card.grid_columnconfigure(0, weight=1)

        self.killer_header = ctk.CTkFrame(self.killer_card, fg_color="transparent")
        self.killer_header.grid(row=0, column=0, padx=14, pady=(12, 3), sticky="ew")
        self.killer_header.grid_columnconfigure(0, weight=1)
        self.killer_header.grid_columnconfigure(1, weight=0)

        self.killer_title = ctk.CTkLabel(
            self.killer_header,
            text="🎯 PROCESS TERMINATOR" if is_cyber else "🎯 Process Terminator",
            font=get_font(15, "bold"),
            text_color=theme["accent_crimson"] if is_cyber else theme["text_title"]
        )
        self.killer_title.grid(row=0, column=0, sticky="w")

        self.killer_tag = ctk.CTkLabel(
            self.killer_header,
            text="[ PURGE_OPS ]" if is_cyber else "CLEANER",
            font=get_font(10, "bold"),
            fg_color=theme["bg_card_inner"],
            text_color=theme["accent_crimson"] if is_cyber else "#ffffff",
            corner_radius=6,
            padx=7,
            pady=2
        )
        self.killer_tag.grid(row=0, column=1, sticky="e")

        self.killer_desc = ctk.CTkLabel(
            self.killer_card,
            text="Inspect running apps, identify heavy memory hogs, and terminate bloatware.",
            font=get_font(11, "normal"),
            text_color=theme["text_secondary"],
            justify="left",
            wraplength=290
        )
        self.killer_desc.grid(row=1, column=0, padx=14, pady=(0, 6), sticky="w")

        self.killer_chip_frame = ctk.CTkFrame(self.killer_card, fg_color=theme["bg_card_inner"], corner_radius=8)
        self.killer_chip_frame.grid(row=2, column=0, padx=14, pady=(0, 8), sticky="ew")
        self.killer_chip_label = ctk.CTkLabel(
            self.killer_chip_frame,
            text="🔍 SELECTIVE PROCESS HUNTER" if is_cyber else "🔍 Selective Background App Terminator",
            font=get_font(11, "bold"),
            text_color=theme["text_primary"]
        )
        self.killer_chip_label.pack(padx=10, pady=4, anchor="w")

        self.process_killer_btn = ctk.CTkButton(
            self.killer_card,
            text="🎯 BROWSE RUNNING PROCESSES" if is_cyber else "Browse Processes",
            font=get_font(13, "bold"),
            fg_color="#e11d48" if is_cyber else "#8b1515",
            hover_color="#f43f5e" if is_cyber else "#aa1818",
            text_color="#ffffff",
            height=38,
            corner_radius=19 if is_cyber else 8,
            command=self._open_process_killer
        )
        self.process_killer_btn.grid(row=3, column=0, padx=14, pady=(0, 12), sticky="ew")

        # ── Card 4: SysMain Control ──
        self.sysmain_card = ctk.CTkFrame(
            self.btn_container,
            fg_color=theme["bg_card"],
            corner_radius=14,
            border_width=1,
            border_color=theme["border_amber"] if is_cyber else "#1e1e1e"
        )
        self.sysmain_card.grid(row=1, column=1, padx=6, pady=5, sticky="nsew")
        self.sysmain_card.grid_columnconfigure(0, weight=1)

        self.sysmain_header = ctk.CTkFrame(self.sysmain_card, fg_color="transparent")
        self.sysmain_header.grid(row=0, column=0, padx=14, pady=(12, 3), sticky="ew")
        self.sysmain_header.grid_columnconfigure(0, weight=1)
        self.sysmain_header.grid_columnconfigure(1, weight=0)

        self.sysmain_title = ctk.CTkLabel(
            self.sysmain_header,
            text="💾 SYSMAIN STORAGE TWEAKER" if is_cyber else "💾 SysMain SSD Tweaker",
            font=get_font(15, "bold"),
            text_color=theme["accent_amber"] if is_cyber else theme["text_title"]
        )
        self.sysmain_title.grid(row=0, column=0, sticky="w")

        self.sysmain_tag = ctk.CTkLabel(
            self.sysmain_header,
            text="[ NVMe / SATA ]" if is_cyber else "STORAGE",
            font=get_font(10, "bold"),
            fg_color=theme["bg_card_inner"],
            text_color=theme["accent_amber"] if is_cyber else "#ffffff",
            corner_radius=6,
            padx=7,
            pady=2
        )
        self.sysmain_tag.grid(row=0, column=1, sticky="e")

        self.sysmain_desc = ctk.CTkLabel(
            self.sysmain_card,
            text="Disable Windows Superfetch to prevent redundant SSD disk-to-RAM caching.",
            font=get_font(11, "normal"),
            text_color=theme["text_secondary"],
            justify="left",
            wraplength=290
        )
        self.sysmain_desc.grid(row=1, column=0, padx=14, pady=(0, 6), sticky="w")

        self.sysmain_chip_frame = ctk.CTkFrame(self.sysmain_card, fg_color=theme["bg_card_inner"], corner_radius=8)
        self.sysmain_chip_frame.grid(row=2, column=0, padx=14, pady=(0, 8), sticky="ew")
        self.sysmain_chip_label = ctk.CTkLabel(
            self.sysmain_chip_frame,
            text="🛡️ STATUS: Checking SSD & SysMain..." if is_cyber else "🛡️ Status: Checking SSD & SysMain...",
            font=get_font(11, "bold"),
            text_color=theme["text_secondary"]
        )
        self.sysmain_chip_label.pack(padx=10, pady=4, anchor="w")

        self.sysmain_btn = ctk.CTkButton(
            self.sysmain_card,
            text="⚙️ CONFIGURE SYSMAIN SERVICE" if is_cyber else "Configure SysMain",
            font=get_font(13, "bold"),
            fg_color="#0f172a" if is_cyber else "#262626",
            hover_color="#1e293b" if is_cyber else "#333333",
            text_color=theme["accent_cyan"] if is_cyber else "#ffffff",
            border_width=1 if is_cyber else 0,
            border_color="#00f0ff" if is_cyber else "#333333",
            height=38,
            corner_radius=19 if is_cyber else 8,
            command=self._open_sysmain_dialog
        )
        self.sysmain_btn.grid(row=3, column=0, padx=14, pady=(0, 12), sticky="ew")

        # ── Bottom Status Pill Bar ──
        self.status_bar_frame = ctk.CTkFrame(
            self.basic_frame,
            fg_color=theme["bg_card"],
            corner_radius=10,
            border_width=1,
            border_color="#1a2b5e" if is_cyber else "#1e1e1e"
        )
        self.status_bar_frame.grid(row=2, column=0, padx=15, pady=(2, 10), sticky="ew")

        self.basic_status_label = ctk.CTkLabel(
            self.status_bar_frame,
            text="> SYSTEM_STATUS // ⚡ Ready · Select an optimization operation or engage AI Sentinel for autonomous frame pacing." if is_cyber else "⚡ Ready · Select an action above or activate AI Sentinel for auto-pilot frame pacing.",
            font=get_font(12, "bold"),
            text_color=theme["text_secondary"]
        )
        self.basic_status_label.pack(padx=14, pady=6, anchor="w")

        # ── Advanced UI (Hidden by default) ────────────────────
        self.advanced_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.advanced_frame.grid_columnconfigure(0, weight=1)
        self.advanced_frame.grid_rowconfigure(0, weight=0)
        self.advanced_frame.grid_rowconfigure(1, weight=1)
        self.advanced_frame.grid_rowconfigure(2, weight=0)

        # Advanced subheader
        self.adv_subheader = ctk.CTkFrame(self.advanced_frame, fg_color="transparent")
        self.adv_subheader.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        self.adv_subheader.grid_columnconfigure(0, weight=1)
        
        self.adv_result_label = ctk.CTkLabel(
            self.adv_subheader, text="", font=get_font(14, "bold"), text_color=theme["accent_green"]
        )
        self.adv_result_label.grid(row=0, column=0, sticky="w")
        
        self.rescan_btn = ctk.CTkButton(
            self.adv_subheader, text="Rescan Processes", width=140,
            fg_color=theme["nav_btn_fg"] if is_cyber_mode() else "#333333",
            hover_color=theme["nav_btn_hover"] if is_cyber_mode() else "#444444",
            text_color=theme["nav_btn_text"],
            font=get_font(13, "bold"),
            command=self._load_advanced_processes
        )
        self.rescan_btn.grid(row=0, column=1, sticky="e")

        self.list_frame = ctk.CTkScrollableFrame(self.advanced_frame, fg_color=theme["bg_card"])
        self.list_frame.grid(row=1, column=0, padx=0, pady=0, sticky="nsew")
        self.list_frame.grid_columnconfigure(0, weight=1)

        self.checkboxes = []
        
        self.terminate_btn = ctk.CTkButton(
            self.advanced_frame,
            text="⚡ TERMINATE SELECTED" if is_cyber_mode() else "Terminate Selected",
            font=get_font(15, "bold"),
            fg_color=theme["action_btn_fg"],
            hover_color=theme["action_btn_hover"],
            text_color=theme["action_btn_text"],
            height=40,
            corner_radius=20 if is_cyber_mode() else 8,
            command=self._confirm_termination
        )
        self.terminate_btn.grid(row=2, column=0, pady=(20, 0), sticky="ew")

        # Initial Setup & Telemetry Daemon
        self._update_ram_label()
        self._init_sysmain_status()
        self._start_telemetry_loop()

    def apply_theme(self, is_cyber: bool):
        """Update optimize view styling when theme mode toggles."""
        theme = CYBER_THEME if is_cyber else PERFORMANCE_THEME
        self.configure(fg_color=theme["bg_main"])
        self.list_frame.configure(fg_color=theme["bg_card"])

        # Header
        self.title_label.configure(
            text="⚡ CYBER MATRIX // GAME BOOSTER" if is_cyber else "Game Booster",
            font=get_font(22, "bold"),
            text_color=theme["text_title"]
        )
        self.subtitle_label.configure(
            text="⚡ HARDWARE TIMER LOCKED · HIGH-PRECISION OS PACING ENGAGED" if is_cyber else "Hardware timer optimization, standby memory flush, and game stability",
            font=get_font(12, "normal"),
            text_color=theme["text_secondary"]
        )
        self.mode_switch.configure(
            text="[ ADVANCED PURGE OPS ]" if is_cyber else "Advanced Process Mode",
            progress_color=theme["accent_cyan"],
            font=get_font(12, "bold")
        )

        # HUD Banner
        border_col = theme.get("border_glow", "#00f0ff") if is_cyber else "#1e1e1e"
        self.hud_frame.configure(fg_color=theme["bg_card"], border_color=border_col)
        self.hud_ram_title.configure(
            text="// ACTIVE MEMORY" if is_cyber else "Active Memory",
            font=get_font(10, "bold"),
            text_color=theme["text_secondary"]
        )
        self.hud_ram_val.configure(font=get_font(14, "bold", is_stat=True), text_color=theme["text_primary"])
        self.hud_cache_title.configure(
            text="// PURGEABLE STANDBY CACHE" if is_cyber else "Standby Cache",
            font=get_font(10, "bold"),
            text_color=theme["text_secondary"]
        )
        self.hud_cache_val.configure(
            font=get_font(14, "bold", is_stat=True),
            text_color=theme["accent_cyan"] if is_cyber else "#00dd88"
        )
        self.hud_timer_title.configure(
            text="// SCHEDULER RESOLUTION" if is_cyber else "Timer Resolution",
            font=get_font(10, "bold"),
            text_color=theme["text_secondary"]
        )
        self.hud_timer_val.configure(
            font=get_font(13, "bold"),
            text_color=theme["accent_green"] if self.ai_service.is_running else theme["text_muted"]
        )
        self.hud_progress.configure(
            fg_color=theme["bg_card_inner"],
            progress_color=theme["accent_cyan"] if is_cyber else theme["accent_primary"]
        )

        # 4 Cards Container & Glowing Neon Borders
        self.boost_card.configure(
            fg_color=theme["bg_card"],
            border_color=theme.get("border_glow", "#00f0ff") if is_cyber else "#1e1e1e",
            corner_radius=14
        )
        self.ai_card.configure(
            fg_color=theme["bg_card"],
            border_color=theme.get("border_purple", "#a855f7") if is_cyber else "#1e1e1e",
            corner_radius=14
        )
        self.killer_card.configure(
            fg_color=theme["bg_card"],
            border_color=theme.get("border_pink", "#f43f5e") if is_cyber else "#1e1e1e",
            corner_radius=14
        )
        self.sysmain_card.configure(
            fg_color=theme["bg_card"],
            border_color=theme.get("border_amber", "#fbbf24") if is_cyber else "#1e1e1e",
            corner_radius=14
        )

        # Card 1: Quantum Flush
        self.boost_title.configure(
            text="⚡ QUANTUM RAM FLUSH" if is_cyber else "Memory Standby Flush",
            font=get_font(15, "bold"),
            text_color=theme["accent_cyan"] if is_cyber else theme["text_title"]
        )
        self.boost_tag.configure(
            text="[ 1-CLICK ]" if is_cyber else "RAM",
            font=get_font(10, "bold"),
            fg_color=theme["bg_card_inner"],
            text_color=theme["accent_cyan"] if is_cyber else "#ffffff"
        )
        self.boost_desc.configure(font=get_font(11, "normal"), text_color=theme["text_secondary"])
        self.boost_chip_frame.configure(fg_color=theme["bg_card_inner"])
        self.boost_chip_label.configure(
            font=get_font(11, "bold"),
            text_color=theme["accent_cyan"] if is_cyber else theme["text_primary"]
        )
        self.boost_btn.configure(
            text="⚡ PURGE STANDBY RAM NOW" if is_cyber else "Flush RAM Now",
            font=get_font(13, "bold"),
            fg_color=theme["action_btn_fg"],
            hover_color=theme["action_btn_hover"],
            text_color=theme["action_btn_text"],
            corner_radius=19 if is_cyber else 8
        )

        # Card 2: AI Sentinel
        self.ai_card_title.configure(
            text="🤖 AI FPS SENTINEL" if is_cyber else "AI Game Sentinel",
            font=get_font(15, "bold"),
            text_color=theme["accent_purple"] if is_cyber else theme["text_title"]
        )
        self.ai_tag.configure(
            text="[ AUTO-PILOT ]" if is_cyber else "AUTO",
            font=get_font(10, "bold"),
            fg_color=theme["bg_card_inner"],
            text_color=theme["accent_purple"] if is_cyber else "#ffffff"
        )
        self.ai_desc.configure(font=get_font(11, "normal"), text_color=theme["text_secondary"])
        self.ai_chip_frame.configure(fg_color=theme["bg_card_inner"])
        self.ai_status_badge.configure(
            font=get_font(11, "bold"),
            text_color=theme["accent_green"] if self.ai_service.is_running else theme["text_secondary"]
        )
        if not self.ai_service.is_running:
            self.ai_action_btn.configure(
                text="⚡ ENGAGE AI SENTINEL" if is_cyber else "Activate Sentinel",
                font=get_font(13, "bold"),
                fg_color=theme["accent_purple"] if is_cyber else "#262626",
                hover_color="#9333ea" if is_cyber else "#333333",
                text_color="#ffffff",
                corner_radius=19 if is_cyber else 8
            )
        else:
            self.ai_action_btn.configure(
                text="⏹ DISENGAGE SENTINEL" if is_cyber else "Deactivate Sentinel",
                font=get_font(13, "bold"),
                fg_color="#00ff9f" if is_cyber else "#00aa00",
                hover_color="#00d685" if is_cyber else "#008800",
                text_color="#05060f" if is_cyber else "#ffffff",
                corner_radius=19 if is_cyber else 8
            )

        # Card 3: Killer
        self.killer_title.configure(
            text="🎯 PROCESS TERMINATOR" if is_cyber else "Background Process Killer",
            font=get_font(15, "bold"),
            text_color="#f43f5e" if is_cyber else theme["text_title"]
        )
        self.killer_tag.configure(
            text="[ PURGE_OPS ]" if is_cyber else "MANUAL",
            font=get_font(10, "bold"),
            fg_color=theme["bg_card_inner"],
            text_color="#f43f5e" if is_cyber else "#ffffff"
        )
        self.killer_desc.configure(font=get_font(11, "normal"), text_color=theme["text_secondary"])
        self.killer_chip_frame.configure(fg_color=theme["bg_card_inner"])
        self.killer_chip_label.configure(font=get_font(11, "bold"), text_color=theme["text_primary"])
        self.process_killer_btn.configure(
            text="🎯 BROWSE RUNNING PROCESSES" if is_cyber else "Browse Processes",
            font=get_font(13, "bold"),
            fg_color="#e11d48" if is_cyber else "#8b1515",
            hover_color="#f43f5e" if is_cyber else "#aa1818",
            text_color="#ffffff",
            corner_radius=19 if is_cyber else 8
        )

        # Card 4: SysMain
        self.sysmain_title.configure(
            text="💾 SYSMAIN STORAGE TWEAKER" if is_cyber else "SysMain (Superfetch) Tweaker",
            font=get_font(15, "bold"),
            text_color=theme["accent_amber"] if is_cyber else theme["text_title"]
        )
        self.sysmain_tag.configure(
            text="[ NVMe / SATA ]" if is_cyber else "DISK",
            font=get_font(10, "bold"),
            fg_color=theme["bg_card_inner"],
            text_color=theme["accent_amber"] if is_cyber else "#ffffff"
        )
        self.sysmain_desc.configure(font=get_font(11, "normal"), text_color=theme["text_secondary"])
        self.sysmain_chip_frame.configure(fg_color=theme["bg_card_inner"])
        self.sysmain_chip_label.configure(font=get_font(11, "bold"))
        self.sysmain_btn.configure(
            text="⚙️ CONFIGURE SYSMAIN SERVICE" if is_cyber else "Configure SysMain",
            font=get_font(13, "bold"),
            fg_color="#0f172a" if is_cyber else "#262626",
            hover_color="#1e293b" if is_cyber else "#333333",
            text_color=theme["accent_cyan"] if is_cyber else "#ffffff",
            border_width=1 if is_cyber else 0,
            border_color="#00f0ff" if is_cyber else "#333333",
            corner_radius=19 if is_cyber else 8
        )

        # Status Bar Frame
        self.status_bar_frame.configure(
            fg_color=theme["bg_card"],
            border_color="#1a2b5e" if is_cyber else "#1e1e1e"
        )
        self.basic_status_label.configure(
            text="> SYSTEM_STATUS // ⚡ Ready · Select an optimization operation or engage AI Sentinel for autonomous frame pacing." if is_cyber else "⚡ Ready · Select an action above or activate AI Sentinel for auto-pilot frame pacing.",
            font=get_font(12, "bold"),
            text_color=theme["text_secondary"]
        )

        # Advanced View
        self.rescan_btn.configure(
            fg_color=theme["nav_btn_fg"] if is_cyber else "#333333",
            hover_color=theme["nav_btn_hover"] if is_cyber else "#444444",
            text_color=theme["nav_btn_text"],
            font=get_font(13, "bold")
        )
        self.terminate_btn.configure(
            text="⚡ TERMINATE SELECTED" if is_cyber else "Terminate Selected",
            font=get_font(15, "bold"),
            fg_color=theme["action_btn_fg"],
            hover_color=theme["action_btn_hover"],
            text_color=theme["action_btn_text"],
            corner_radius=20 if is_cyber else 8
        )
        self._update_ram_label()

    # ── Live Telemetry & Real-Time Refresher Daemon ────────────

    def _start_telemetry_loop(self):
        """Background thread updating the HUD memory telemetry every 3s."""
        def _worker():
            while True:
                try:
                    if not self.winfo_exists():
                        break
                except Exception:
                    break

                try:
                    mb = get_memory_breakdown()
                    ai_stat = self.ai_service.get_status()
                    self.after(0, self._update_hud_display, mb, ai_stat)
                except Exception:
                    pass
                time.sleep(3.0)

        t = threading.Thread(target=_worker, daemon=True)
        t.start()

    def _update_hud_display(self, mb: dict, ai_stat: dict):
        """Render live memory breakdown and scheduler status on the main thread."""
        try:
            if not self.winfo_exists():
                return
        except Exception:
            return

        theme = get_theme()
        is_cyber = is_cyber_mode()

        pct = mb.get("percent", 0.0) / 100.0
        self.hud_progress.set(min(max(pct, 0.0), 1.0))

        used_gb = mb.get("used_mb", 0.0) / 1024.0
        total_gb = mb.get("total_mb", 0.0) / 1024.0
        self.hud_ram_val.configure(text=f"{used_gb:.1f} GB / {total_gb:.1f} GB ({mb.get('percent', 0):.0f}%)")

        cache_mb = mb.get("cached_approx_mb", 0.0)
        self.hud_cache_val.configure(text=f"{cache_mb:,.0f} MB Reclaimable")
        self.boost_chip_label.configure(text=f"💾 Purgeable Cache: {cache_mb:,.0f} MB")

        if ai_stat.get("timer_locked"):
            self.hud_timer_val.configure(
                text="● 1.0ms HIGH-RES (LOCKED)",
                text_color=theme["accent_green"] if is_cyber else "#00ff00"
            )
        else:
            self.hud_timer_val.configure(
                text="○ 15.6ms (DEFAULT)",
                text_color=theme["text_muted"]
            )

    def _init_sysmain_status(self):
        """Asynchronously inspect SysMain and drive type to populate Card 4 status chip."""
        def _worker():
            try:
                sm_status = get_sysmain_status()
                has_ssd = check_has_ssd()
                self.after(0, self._render_sysmain_chip, sm_status, has_ssd)
            except Exception:
                pass
        threading.Thread(target=_worker, daemon=True).start()

    def _render_sysmain_chip(self, sm_status: dict, has_ssd: bool):
        try:
            if not self.winfo_exists():
                return
        except Exception:
            return

        theme = get_theme()
        is_cyber = is_cyber_mode()
        running = sm_status.get("running", False)

        if sm_status.get("error"):
            self.sysmain_chip_label.configure(
                text="⚠️ SysMain: Status Error",
                text_color="#ff4d4f"
            )
        elif running:
            if has_ssd:
                self.sysmain_chip_label.configure(
                    text="💾 SSD Active · SysMain Enabled (Disable Rec.)",
                    text_color=theme["accent_amber"] if is_cyber else "#ffaa00"
                )
            else:
                self.sysmain_chip_label.configure(
                    text="💽 HDD Active · SysMain Running",
                    text_color=theme["text_primary"]
                )
        else:
            self.sysmain_chip_label.configure(
                text="🛡️ SysMain Stopped · Zero SSD Thrashing",
                text_color=theme["accent_green"] if is_cyber else "#00ff00"
            )

    # ── AI Game Sentinel Handlers ─────────────────────────────

    def _toggle_ai_sentinel_btn(self):
        """Start or stop the AI Game Sentinel watchdog via action button."""
        theme = get_theme()
        is_cyber = is_cyber_mode()

        if not self.ai_service.is_running:
            self.ai_action_btn.configure(
                text="⏹ DEACTIVATE SENTINEL",
                fg_color="#00ff9f" if is_cyber else "#00aa00",
                hover_color="#00d685" if is_cyber else "#008800",
                text_color="#05060f" if is_cyber else "#ffffff"
            )
            self.ai_status_badge.configure(
                text="● Initializing Sentinel (1.0ms Lock)…",
                text_color=theme["accent_cyan"] if is_cyber else "#00aa00"
            )
            self.basic_status_label.configure(
                text="⚡ AI Sentinel Active · 1.0ms timer locked, game priority elevated.",
                text_color=theme["accent_green"] if is_cyber else "#00ff00"
            )
            self.hud_timer_val.configure(
                text="● 1.0ms HIGH-RES (LOCKED)",
                text_color=theme["accent_green"] if is_cyber else "#00ff00"
            )
            self.ai_service.start()
        else:
            self.ai_service.stop()
            self.ai_action_btn.configure(
                text="▶ ACTIVATE SENTINEL",
                fg_color=theme["accent_purple"] if is_cyber else "#262626",
                hover_color="#9333ea" if is_cyber else "#333333",
                text_color="#ffffff"
            )
            self.ai_status_badge.configure(
                text="○ Inactive · Click to activate 1.0ms lock",
                text_color=theme["text_secondary"]
            )
            self.basic_status_label.configure(
                text="AI Sentinel stopped. Timer resolution restored to OS default.",
                text_color=theme["text_secondary"]
            )
            self.hud_timer_val.configure(
                text="○ 15.6ms (DEFAULT)",
                text_color=theme["text_muted"]
            )

    def _on_ai_status_update(self, data: dict):
        """Callback invoked by background watchdog on state changes."""
        try:
            self.after(0, self._render_ai_status, data)
        except Exception:
            pass

    def _render_ai_status(self, data: dict):
        """Update the Sentinel card badge and info on the main thread."""
        try:
            if not self.winfo_exists():
                return
        except Exception:
            return

        state = data.get("state", "IDLE")
        message = data.get("message", "")
        active_game = data.get("active_game")
        last_action = data.get("last_action")
        theme = get_theme()
        is_cyber = is_cyber_mode()

        if state == "IDLE":
            self.ai_action_btn.configure(
                text="▶ ACTIVATE SENTINEL",
                fg_color=theme["accent_purple"] if is_cyber else "#262626",
                hover_color="#9333ea" if is_cyber else "#333333",
                text_color="#ffffff"
            )
            self.ai_status_badge.configure(
                text="○ Inactive · Click to activate 1.0ms lock",
                text_color=theme["text_secondary"]
            )
            self.hud_timer_val.configure(
                text="○ 15.6ms (DEFAULT)",
                text_color=theme["text_muted"]
            )
        elif state == "BOOTSTRAPPING":
            self.ai_action_btn.configure(
                text="⏹ DEACTIVATE SENTINEL",
                fg_color="#00ff9f" if is_cyber else "#00aa00",
                hover_color="#00d685" if is_cyber else "#008800",
                text_color="#05060f" if is_cyber else "#ffffff"
            )
            self.ai_status_badge.configure(
                text=f"● {message}",
                text_color="#ffcc00"
            )
        elif state == "TRAINING":
            self.ai_status_badge.configure(
                text="● Calibrating lightweight AI stability model…",
                text_color="#ffcc00"
            )
        elif state == "MONITORING":
            self.ai_action_btn.configure(
                text="⏹ DEACTIVATE SENTINEL",
                fg_color="#00ff9f" if is_cyber else "#00aa00",
                hover_color="#00d685" if is_cyber else "#008800",
                text_color="#05060f" if is_cyber else "#ffffff"
            )
            if active_game:
                self.ai_status_badge.configure(
                    text=f"● 🎮 Stabilizing {active_game} · 1.0ms Lock",
                    text_color=theme["accent_cyan"] if is_cyber else "#00aa00"
                )
            else:
                self.ai_status_badge.configure(
                    text="● Sentinel Active · 1.0ms Timer Locked",
                    text_color=theme["accent_cyan"] if is_cyber else "#00aa00"
                )
            self.hud_timer_val.configure(
                text="● 1.0ms HIGH-RES (LOCKED)",
                text_color=theme["accent_green"] if is_cyber else "#00ff00"
            )
        elif state == "ACTING":
            action_text = last_action or "Standby Cache Purged"
            self.ai_status_badge.configure(
                text=f"● ⚡ {action_text}",
                text_color=theme["accent_green"] if is_cyber else "#00ff00"
            )
            self.hud_timer_val.configure(
                text="● 1.0ms HIGH-RES (LOCKED)",
                text_color=theme["accent_green"] if is_cyber else "#00ff00"
            )
            self._update_ram_label()
        elif state == "ERROR":
            self.ai_status_badge.configure(
                text=f"● Error: {message}",
                text_color="#ff4d4f"
            )

    def _toggle_mode(self):
        theme = get_theme()
        if self.advanced_mode.get():
            self.basic_frame.grid_remove()
            self.advanced_frame.grid(row=1, column=0, padx=20, pady=0, sticky="nsew")
            self._load_advanced_processes()
        else:
            self.advanced_frame.grid_remove()
            self.basic_frame.grid(row=1, column=0, sticky="nsew")
            self.basic_status_label.configure(
                text="⚡ Ready · Select an action above or activate AI Sentinel for auto-pilot frame pacing.",
                text_color=theme["text_secondary"]
            )

    def _update_ram_label(self):
        ram = get_current_available_ram_mb()
        try:
            mb = get_memory_breakdown()
            ai_stat = self.ai_service.get_status()
            self._update_hud_display(mb, ai_stat)
        except Exception:
            pass
        return ram

    # ── Process Killer Dialog ──────────────────────────────────

    def _open_process_killer(self):
        """Opens a standalone dialog for browsing and killing processes."""
        theme = get_theme()
        is_cyber = is_cyber_mode()
        dialog = ctk.CTkToplevel(self)
        dialog.title("🎯 PROCESS TERMINATOR // PURGE OPS" if is_cyber else "Process Killer")
        dialog.geometry("580x540")
        dialog.attributes("-topmost", True)
        dialog.transient(self.winfo_toplevel())
        dialog.grab_set()
        dialog.configure(fg_color=theme["bg_main"])

        # Center dialog
        dialog.update_idletasks()
        try:
            top_w = self.winfo_toplevel()
            x = max(0, top_w.winfo_x() + (top_w.winfo_width() // 2) - (580 // 2))
            y = max(0, top_w.winfo_y() + (top_w.winfo_height() // 2) - (540 // 2))
            dialog.geometry(f"+{x}+{y}")
        except Exception:
            pass

        # Header row
        header = ctk.CTkFrame(dialog, fg_color="transparent")
        header.pack(fill="x", padx=20, pady=(15, 5))
        header.grid_columnconfigure(0, weight=1)

        title_lbl = ctk.CTkLabel(
            header,
            text="🎯 PROCESS TERMINATOR // PURGE OPS" if is_cyber else "Process Killer",
            font=get_font(18, "bold"),
            text_color="#f43f5e" if is_cyber else theme["text_title"]
        )
        title_lbl.grid(row=0, column=0, sticky="w")

        status_lbl = ctk.CTkLabel(
            header, text="", font=get_font(13, "bold"), text_color=theme["accent_green"]
        )
        status_lbl.grid(row=1, column=0, sticky="w", pady=(2, 0))

        rescan = ctk.CTkButton(
            header, text="⚡ RESCAN" if is_cyber else "Rescan", width=100,
            fg_color="#1e293b" if is_cyber else "#333333",
            hover_color="#334155" if is_cyber else "#444444",
            text_color="#00f0ff" if is_cyber else theme["nav_btn_text"],
            font=get_font(12, "bold"),
            corner_radius=15 if is_cyber else 8
        )
        rescan.grid(row=0, column=1, rowspan=2, sticky="e")

        # Scrollable process list
        scroll = ctk.CTkScrollableFrame(
            dialog,
            fg_color=theme["bg_card"],
            border_width=1,
            border_color="#f43f5e" if is_cyber else "#1e1e1e",
            corner_radius=12
        )
        scroll.pack(fill="both", expand=True, padx=20, pady=10)
        scroll.grid_columnconfigure(0, weight=1)

        dialog_cbs = []

        def _load_procs():
            rescan.configure(state="disabled")
            for w in scroll.winfo_children():
                w.destroy()
            dialog_cbs.clear()
            ctk.CTkLabel(scroll, text="> SCANNING ACTIVE PROCESSES...", text_color="#00f0ff" if is_cyber else "gray").grid(row=0, column=0, pady=20)

            def _worker():
                procs = get_top_memory_consumers(25)
                dialog.after(0, _render_procs, procs)

            threading.Thread(target=_worker, daemon=True).start()

        def _render_procs(procs):
            for w in scroll.winfo_children():
                w.destroy()
            if not procs:
                ctk.CTkLabel(scroll, text="No background processes found.", text_color="gray").grid(row=0, column=0, pady=20)
                rescan.configure(state="normal")
                return
            for i, p in enumerate(procs):
                cb = ctk.CTkCheckBox(
                    scroll,
                    text=f"{p['name']} (PID: {p['pid']})  —  {p['memory_mb']:,.0f} MB",
                    font=get_font(13, "normal"),
                    fg_color="#f43f5e" if is_cyber else "#1f6aa5",
                    hover_color="#ff4d6d" if is_cyber else "#2980b9",
                    checkmark_color="#ffffff"
                )
                cb.grid(row=i, column=0, padx=10, pady=6, sticky="w")
                dialog_cbs.append((cb, p['pid'], p['name']))
            rescan.configure(state="normal")

        rescan.configure(command=_load_procs)

        # Terminate button
        def _do_terminate():
            selected = [(cb, pid, name) for cb, pid, name in dialog_cbs if cb.get()]
            if not selected:
                status_lbl.configure(text="No processes selected.", text_color="#ff4d4f")
                return

            term_btn.configure(state="disabled", text="⚡ TERMINATING..." if is_cyber else "Terminating...")
            pids = [pid for _, pid, _ in selected]
            ram_before = get_current_available_ram_mb()

            def _kill():
                results = terminate_processes(pids)
                time.sleep(1.0)
                dialog.after(0, _on_done, results, ram_before)

            threading.Thread(target=_kill, daemon=True).start()

        def _on_done(results, ram_before):
            ram_after = get_current_available_ram_mb()
            recovered = ram_after - ram_before
            success = results["success"]
            if recovered > 0:
                status_lbl.configure(text=f"Purged {success} — recovered {recovered:,.0f} MB", text_color="#00ff9f" if is_cyber else "#00ff00")
            else:
                status_lbl.configure(text=f"Terminated {success} process(es).", text_color="gray")
            term_btn.configure(
                state="normal",
                text="🎯 PURGE SELECTED PROCESSES" if is_cyber else "Terminate Selected"
            )
            self._update_ram_label()
            _load_procs()

        term_btn = ctk.CTkButton(
            dialog,
            text="🎯 PURGE SELECTED PROCESSES" if is_cyber else "Terminate Selected",
            font=get_font(14, "bold"),
            fg_color="#e11d48" if is_cyber else "#cc3333",
            hover_color="#f43f5e" if is_cyber else "#ff4444",
            text_color="#ffffff",
            height=42,
            corner_radius=21 if is_cyber else 8,
            command=_do_terminate
        )
        term_btn.pack(fill="x", padx=20, pady=(0, 15))

        # Kick off the initial scan
        _load_procs()

    # ── 1-Click Boost Logic (Smart RAM Optimization) ─────────────

    def _run_auto_boost(self):
        """Clear standby memory cache + trim working sets — no processes killed."""
        is_cyber = is_cyber_mode()
        self.boost_btn.configure(
            state="disabled",
            text="⚡ PURGING STANDBY CACHE..." if is_cyber else "Flushing Memory..."
        )
        self.basic_status_label.configure(
            text="> SYSTEM_STATUS // ⚡ Purging standby cache & trimming background working sets..." if is_cyber else "⚡ Purging standby cache & trimming background working sets...",
            text_color="#00f0ff" if is_cyber else "#ffffff"
        )
        ram_before = self._update_ram_label()

        def _worker():
            fg_game = get_foreground_game_process()
            exclude_pids = [fg_game["pid"]] if fg_game else []
            # Step 1: Clear standby memory (the big win)
            standby_result = clear_standby_memory()
            # Step 2: Trim working sets (protecting active game)
            trim_result = trim_all_working_sets(exclude_pids=exclude_pids)
            # Small delay for OS to settle
            time.sleep(0.5)
            self.after(0, self._on_smart_boost_complete,
                       standby_result, trim_result, ram_before)

        threading.Thread(target=_worker, daemon=True).start()

    def _on_smart_boost_complete(self, standby_result, trim_result, ram_before):
        ram_after = self._update_ram_label()
        total_freed = max(0, ram_after - ram_before)
        is_cyber = is_cyber_mode()
        theme = get_theme()

        parts = []
        if standby_result["success"]:
            parts.append(f"Standby cache cleared ({standby_result['freed_mb']:,.0f} MB)")
        else:
            parts.append(f"Standby clear: {standby_result['error']}")

        parts.append(f"Trimmed {trim_result['trimmed']} processes")

        if total_freed > 0:
            status = f"> SYSTEM_STATUS // ✔ PURGE COMPLETE · Recovered {total_freed:,.0f} MB total. " + " · ".join(parts) if is_cyber else f"✔ Flush Complete! Recovered {total_freed:,.0f} MB total. " + " · ".join(parts)
            color = theme["accent_green"] if is_cyber else "#00ff00"
        elif standby_result["success"]:
            status = f"> SYSTEM_STATUS // ✔ PURGE COMPLETE · " + " · ".join(parts) + " — RAM was already optimal." if is_cyber else "✔ Flush Complete! " + " · ".join(parts) + " — RAM was already optimal."
            color = theme["accent_green"] if is_cyber else "#00ff00"
        else:
            status = f"> SYSTEM_STATUS // ⚠️ " + " · ".join(parts) if is_cyber else " · ".join(parts)
            color = "#ff4d4f"

        self.basic_status_label.configure(text=status, text_color=color)
        self.boost_btn.configure(
            state="normal",
            text="⚡ PURGE STANDBY RAM NOW" if is_cyber else "Flush RAM Now"
        )
        # Immediate HUD telemetry update
        try:
            mb = get_memory_breakdown()
            ai_stat = self.ai_service.get_status()
            self._update_hud_display(mb, ai_stat)
        except Exception:
            pass

    # ── SysMain Control Dialog ─────────────────────────────────

    def _open_sysmain_dialog(self):
        """Opens a dialog to check SysMain status and toggle it."""
        theme = get_theme()
        is_cyber = is_cyber_mode()
        dialog = ctk.CTkToplevel(self)
        dialog.title("💾 SYSMAIN STORAGE TWEAKER" if is_cyber else "SysMain Control")
        dialog.geometry("480x360")
        dialog.attributes("-topmost", True)
        dialog.transient(self.winfo_toplevel())
        dialog.grab_set()
        dialog.configure(fg_color=theme["bg_main"])

        # Center dialog
        dialog.update_idletasks()
        try:
            top_w = self.winfo_toplevel()
            x = max(0, top_w.winfo_x() + (top_w.winfo_width() // 2) - (480 // 2))
            y = max(0, top_w.winfo_y() + (top_w.winfo_height() // 2) - (360 // 2))
            dialog.geometry(f"+{x}+{y}")
        except Exception:
            pass

        # Title
        ctk.CTkLabel(
            dialog,
            text="💾 SYSMAIN STORAGE TWEAKER" if is_cyber else "SysMain (Superfetch)",
            font=get_font(18, "bold"),
            text_color=theme["accent_amber"] if is_cyber else theme["text_title"]
        ).pack(padx=20, pady=(15, 5), anchor="w")

        # Info label
        info_lbl = ctk.CTkLabel(
            dialog,
            text="SysMain pre-caches app data into RAM.\n"
                 "On SSDs this wastes memory — disabling it\n"
                 "frees RAM without slowing app launches.",
            font=get_font(12, "normal"),
            text_color=theme["text_secondary"],
            justify="left"
        )
        info_lbl.pack(padx=20, pady=(0, 10), anchor="w")

        # Status card
        status_card = ctk.CTkFrame(
            dialog,
            fg_color=theme["bg_card"],
            border_width=1,
            border_color="#fbbf24" if is_cyber else "#1e1e1e",
            corner_radius=12
        )
        status_card.pack(fill="x", padx=20, pady=5)

        status_lbl = ctk.CTkLabel(
            status_card, text="Checking...",
            font=get_font(13, "bold"), text_color=theme["text_primary"]
        )
        status_lbl.pack(padx=15, pady=8, anchor="w")

        ssd_lbl = ctk.CTkLabel(
            status_card, text="Detecting drive type...",
            font=get_font(12, "normal"), text_color=theme["text_secondary"]
        )
        ssd_lbl.pack(padx=15, pady=(0, 8), anchor="w")

        # Result label
        result_lbl = ctk.CTkLabel(
            dialog, text="", font=get_font(13, "bold"), text_color=theme["accent_green"]
        )
        result_lbl.pack(padx=20, pady=(5, 0), anchor="w")

        # Toggle button
        toggle_btn = ctk.CTkButton(
            dialog,
            text="Loading...",
            font=get_font(14, "bold"),
            fg_color="#334155" if is_cyber else "#555555",
            hover_color="#475569" if is_cyber else "#666666",
            text_color="#ffffff",
            height=42,
            corner_radius=21 if is_cyber else 8,
            state="disabled"
        )
        toggle_btn.pack(fill="x", padx=20, pady=(10, 15))

        # State holder for the current SysMain status
        state = {"running": None}

        def _check_status():
            def _worker():
                sm_status = get_sysmain_status()
                has_ssd = check_has_ssd()
                dialog.after(0, _render_status, sm_status, has_ssd)
            threading.Thread(target=_worker, daemon=True).start()

        def _render_status(sm_status, has_ssd):
            state["running"] = sm_status["running"]

            if sm_status["error"]:
                status_lbl.configure(text=f"Error: {sm_status['error']}", text_color="#ff4d4f")
                return

            running_text = "RUNNING" if sm_status["running"] else "STOPPED"
            start_text = sm_status["start_type"].upper()
            status_icon = "🟢" if sm_status["running"] else "🔴"
            status_lbl.configure(
                text=f"{status_icon}  SysMain is {running_text} (startup: {start_text})",
                text_color="#00ff9f" if sm_status["running"] else "#ff4d4f"
            )

            ssd_icon = "💾 SSD detected" if has_ssd else "💽 HDD detected"
            rec = " — disabling SysMain recommended!" if has_ssd and sm_status["running"] else ""
            ssd_lbl.configure(
                text=f"{ssd_icon}{rec}",
                text_color=theme["accent_amber"] if (has_ssd and sm_status["running"]) else theme["text_secondary"]
            )

            if sm_status["running"]:
                toggle_btn.configure(
                    text="⚡ DISABLE SYSMAIN SERVICE" if is_cyber else "Disable SysMain",
                    fg_color="#e11d48" if is_cyber else "#cc3333",
                    hover_color="#f43f5e" if is_cyber else "#ff4444",
                    state="normal", command=lambda: _toggle(False)
                )
            else:
                toggle_btn.configure(
                    text="⚡ ENABLE SYSMAIN SERVICE" if is_cyber else "Enable SysMain",
                    fg_color=theme["action_btn_fg"], hover_color=theme["action_btn_hover"],
                    text_color=theme["action_btn_text"],
                    state="normal", command=lambda: _toggle(True)
                )

        def _toggle(enable):
            toggle_btn.configure(state="disabled", text="Applying...")
            result_lbl.configure(text="")

            def _worker():
                res = set_sysmain_enabled(enable)
                time.sleep(1.0)
                dialog.after(0, _on_toggle_done, res, enable)

            threading.Thread(target=_worker, daemon=True).start()

        def _on_toggle_done(res, enabled):
            if res["success"]:
                action = "enabled" if enabled else "disabled"
                result_lbl.configure(
                    text=f"SysMain {action} successfully!",
                    text_color="#00ff00"
                )
            else:
                result_lbl.configure(
                    text=f"Failed: {res['error']}",
                    text_color="#ff4d4f"
                )
            self._update_ram_label()
            self._init_sysmain_status()
            _check_status()

        # Kick off initial status check
        _check_status()


    # ── Advanced Mode Logic ────────────────────────────────────

    def _load_advanced_processes(self):
        self.rescan_btn.configure(state="disabled")
        self._update_ram_label()
        
        for widget in self.list_frame.winfo_children():
            widget.destroy()
        self.checkboxes.clear()
        
        loading_lbl = ctk.CTkLabel(self.list_frame, text="Scanning...", text_color="gray")
        loading_lbl.grid(row=0, column=0, pady=20)
        
        def _worker():
            procs = get_top_memory_consumers(15)
            try:
                if self.winfo_exists():
                    self.after(0, self._render_advanced_processes, procs)
            except Exception:
                pass
            
        threading.Thread(target=_worker, daemon=True).start()

    def _render_advanced_processes(self, procs):
        for widget in self.list_frame.winfo_children():
            widget.destroy()
            
        if not procs:
            ctk.CTkLabel(self.list_frame, text="No processes found.", text_color="gray").grid(row=0, column=0, pady=20)
            self.rescan_btn.configure(state="normal")
            return

        for i, p in enumerate(procs):
            cb = ctk.CTkCheckBox(
                self.list_frame, 
                text=f"{p['name']} (PID: {p['pid']})  -  {p['memory_mb']:,.0f} MB",
                font=ctk.CTkFont(size=14)
            )
            cb.grid(row=i, column=0, padx=10, pady=8, sticky="w")
            self.checkboxes.append((cb, p['pid'], p['name']))
            
        self.rescan_btn.configure(state="normal")

    def _confirm_termination(self):
        selected = [(cb, pid, name) for cb, pid, name in self.checkboxes if cb.get()]
        if not selected:
            self.adv_result_label.configure(text="No processes selected.", text_color="#ff4d4f")
            return
            
        dialog = ctk.CTkToplevel(self)
        dialog.title("Confirm Termination")
        dialog.geometry("400x200")
        dialog.attributes("-topmost", True)
        dialog.transient(self.winfo_toplevel())
        dialog.grab_set()
        
        dialog.update_idletasks()
        try:
            top_w = self.winfo_toplevel()
            x = max(0, top_w.winfo_x() + (top_w.winfo_width() // 2) - (400 // 2))
            y = max(0, top_w.winfo_y() + (top_w.winfo_height() // 2) - (200 // 2))
            dialog.geometry(f"+{x}+{y}")
        except Exception:
            pass
        
        dialog.configure(fg_color="#0a0a0a")
        
        lbl = ctk.CTkLabel(dialog, text=f"WARNING: Terminating {len(selected)} processes.\nUnsaved data may be lost. Proceed?", text_color="#ffffff")
        lbl.pack(pady=(30, 20))
        
        btn_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        btn_frame.pack(fill="x", padx=20)
        btn_frame.grid_columnconfigure((0, 1), weight=1)

        def on_cancel():
            dialog.destroy()

        dialog.protocol("WM_DELETE_WINDOW", on_cancel)
        
        ctk.CTkButton(btn_frame, text="Cancel", fg_color="#333333", hover_color="#444444", command=on_cancel).grid(row=0, column=0, padx=10, sticky="ew")
        
        def on_confirm():
            dialog.destroy()
            self._execute_termination(selected)
            
        ctk.CTkButton(btn_frame, text="Terminate", fg_color="#ff4d4f", hover_color="#cc0000", command=on_confirm).grid(row=0, column=1, padx=10, sticky="ew")

    def _execute_termination(self, selected):
        self.terminate_btn.configure(state="disabled", text="Terminating...")
        pids_to_kill = [pid for _, pid, _ in selected]
        ram_before = self._update_ram_label()
        
        def _worker():
            results = terminate_processes(pids_to_kill)
            time.sleep(1.0)
            self.after(0, self._on_advanced_termination_complete, results, ram_before)
            
        threading.Thread(target=_worker, daemon=True).start()
        
    def _on_advanced_termination_complete(self, results, ram_before):
        ram_after = self._update_ram_label()
        recovered = ram_after - ram_before
        success = results["success"]
        
        if recovered > 0:
            self.adv_result_label.configure(text=f"Recovered {recovered:,.0f} MB.", text_color="#00ff00")
        else:
            self.adv_result_label.configure(text=f"Terminated {success} apps.", text_color="gray")
            
        self.terminate_btn.configure(
            state="normal",
            text="⚡ TERMINATE SELECTED" if is_cyber_mode() else "Terminate Selected"
        )
        self._load_advanced_processes()
