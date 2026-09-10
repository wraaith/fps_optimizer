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
    stabilize_network,
    get_network_status,
    flush_dns_cache,
    optimize_dns_servers,
    disable_network_power_saving,
    disable_network_throttling,
    optimize_tcp_settings,
    reset_network_stack,
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
        self.advanced_mode = ctk.BooleanVar(value=False)

        # ── Game Booster Dashboard UI ──────────────────────────
        self.basic_frame = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.basic_frame.grid(row=1, column=0, sticky="nsew")
        self.basic_frame.grid_columnconfigure(0, weight=1)
        self.basic_frame.grid_rowconfigure(0, weight=0)  # HUD banner
        self.basic_frame.grid_rowconfigure(1, weight=1)  # 2x2 grid
        self.basic_frame.grid_rowconfigure(2, weight=0)  # Bottom status pill

        # AI Sentinel Background Service
        self._telemetry_stop = threading.Event()
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
        self.btn_container.grid_rowconfigure(2, weight=0)  # Network row

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
            wraplength=340
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
            font=get_font(12, "bold"),
            fg_color=theme["action_btn_fg"],
            hover_color=theme["action_btn_hover"],
            text_color=theme["action_btn_text"],
            height=36,
            corner_radius=18 if is_cyber else 8,
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
            wraplength=340
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

        # Row 3: Action button + Diagnostics button paired side-by-side
        self.ai_btn_frame = ctk.CTkFrame(self.ai_card, fg_color="transparent")
        self.ai_btn_frame.grid(row=3, column=0, padx=14, pady=(0, 12), sticky="ew")
        self.ai_btn_frame.grid_columnconfigure(0, weight=1)
        self.ai_btn_frame.grid_columnconfigure(1, weight=0)

        self.ai_action_btn = ctk.CTkButton(
            self.ai_btn_frame,
            text="⚡ ACTIVATE SENTINEL" if not self.ai_service.is_running else "⏹ DEACTIVATE SENTINEL",
            font=get_font(12, "bold"),
            fg_color=theme["accent_purple"] if (is_cyber and not self.ai_service.is_running) else ("#00ff9f" if is_cyber else ("#00aa00" if self.ai_service.is_running else "#262626")),
            hover_color="#9333ea" if (is_cyber and not self.ai_service.is_running) else ("#34d399" if is_cyber else ("#008800" if self.ai_service.is_running else "#333333")),
            text_color="#ffffff" if (not is_cyber or not self.ai_service.is_running) else "#020617",
            height=36,
            corner_radius=18 if is_cyber else 8,
            command=self._toggle_ai_sentinel_btn
        )
        self.ai_action_btn.grid(row=0, column=0, padx=(0, 6), sticky="ew")

        self.ai_diag_btn = ctk.CTkButton(
            self.ai_btn_frame,
            text="🩺 DIAG" if is_cyber else "🩺 Diag",
            font=get_font(11, "bold"),
            fg_color=theme["bg_card_inner"],
            hover_color="#1e293b" if is_cyber else "#222222",
            text_color=theme["accent_cyan"] if is_cyber else theme["text_secondary"],
            border_width=1,
            border_color=theme.get("border_glow", "#333333") if is_cyber else "#333333",
            width=78,
            height=36,
            corner_radius=18 if is_cyber else 8,
            command=self._open_sentinel_diagnostics
        )
        self.ai_diag_btn.grid(row=0, column=1, sticky="e")

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
            wraplength=340
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
            font=get_font(12, "bold"),
            fg_color="#e11d48" if is_cyber else "#8b1515",
            hover_color="#f43f5e" if is_cyber else "#aa1818",
            text_color="#ffffff",
            height=36,
            corner_radius=18 if is_cyber else 8,
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
            wraplength=340
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
            font=get_font(12, "bold"),
            fg_color="#0f172a" if is_cyber else "#262626",
            hover_color="#1e293b" if is_cyber else "#333333",
            text_color=theme["accent_cyan"] if is_cyber else "#ffffff",
            border_width=1 if is_cyber else 0,
            border_color="#00f0ff" if is_cyber else "#333333",
            height=36,
            corner_radius=18 if is_cyber else 8,
            command=self._open_sysmain_dialog
        )
        self.sysmain_btn.grid(row=3, column=0, padx=14, pady=(0, 12), sticky="ew")

        # ── Card 5: Network Stabilization (spans both columns) ──
        self.net_card = ctk.CTkFrame(
            self.btn_container,
            fg_color=theme["bg_card"],
            corner_radius=14,
            border_width=1,
            border_color=theme.get("border_green", "#1e1e1e") if is_cyber else "#1e1e1e"
        )
        self.net_card.grid(row=2, column=0, columnspan=2, padx=6, pady=(3, 5), sticky="ew")
        self.net_card.grid_columnconfigure(0, weight=1)
        self.net_card.grid_columnconfigure(1, weight=0)

        # Left side: title + status
        self.net_info_frame = ctk.CTkFrame(self.net_card, fg_color="transparent")
        self.net_info_frame.grid(row=0, column=0, padx=14, pady=10, sticky="ew")

        self.net_title = ctk.CTkLabel(
            self.net_info_frame,
            text="🌐 NETWORK STABILIZER" if is_cyber else "🌐 Network Stabilizer",
            font=get_font(14, "bold"),
            text_color=theme.get("accent_green", "#00ff9f") if is_cyber else theme["text_title"]
        )
        self.net_title.pack(anchor="w")

        self.net_status_label = ctk.CTkLabel(
            self.net_info_frame,
            text="○ Flush DNS · Disable Throttling · Optimize TCP · Fix Latency",
            font=get_font(10, "normal"),
            text_color=theme["text_secondary"]
        )
        self.net_status_label.pack(anchor="w", pady=(2, 0))

        # Right side: buttons
        self.net_btn_frame = ctk.CTkFrame(self.net_card, fg_color="transparent")
        self.net_btn_frame.grid(row=0, column=1, padx=(0, 14), pady=10, sticky="e")

        self.net_quick_btn = ctk.CTkButton(
            self.net_btn_frame,
            text="⚡ STABILIZE" if is_cyber else "Stabilize",
            font=get_font(12, "bold"),
            fg_color=theme.get("accent_green", "#00ff9f") if is_cyber else "#1a6b3a",
            hover_color="#34d399" if is_cyber else "#22804a",
            text_color="#020617" if is_cyber else "#ffffff",
            width=100,
            height=32,
            corner_radius=16 if is_cyber else 6,
            command=self._run_quick_network_stabilize
        )
        self.net_quick_btn.pack(side="left", padx=(0, 6))

        self.net_advanced_btn = ctk.CTkButton(
            self.net_btn_frame,
            text="⚙️ ADVANCED" if is_cyber else "⚙️ Advanced",
            font=get_font(11, "bold"),
            fg_color=theme["bg_card_inner"],
            hover_color="#1e293b" if is_cyber else "#222222",
            text_color=theme["accent_cyan"] if is_cyber else theme["text_secondary"],
            border_width=1,
            border_color=theme.get("border_green", "#333333") if is_cyber else "#333333",
            width=100,
            height=32,
            corner_radius=16 if is_cyber else 6,
            command=self._open_network_dialog
        )
        self.net_advanced_btn.pack(side="left")

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

        # ── In-Window Subview Panels (Hidden Initially) ──
        self._pk_cbs = []
        self._init_process_killer_frame(theme, is_cyber)
        self._init_diagnostics_frame(theme, is_cyber)
        self._init_network_frame(theme, is_cyber)
        self._init_sysmain_frame(theme, is_cyber)

        # Initial Setup & Telemetry Daemon
        self._update_ram_label()
        self._init_sysmain_status()
        self._start_telemetry_loop()

    def apply_theme(self, is_cyber: bool):
        """Update optimize view styling when theme mode toggles."""
        theme = CYBER_THEME if is_cyber else PERFORMANCE_THEME
        self.configure(fg_color=theme["bg_main"])

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
            font=get_font(12, "bold"),
            fg_color=theme["action_btn_fg"],
            hover_color=theme["action_btn_hover"],
            text_color=theme["action_btn_text"],
            corner_radius=18 if is_cyber else 8
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
                text="⚡ ACTIVATE SENTINEL" if is_cyber else "ACTIVATE SENTINEL",
                font=get_font(12, "bold"),
                fg_color=theme["accent_purple"] if is_cyber else "#262626",
                hover_color="#9333ea" if is_cyber else "#333333",
                text_color="#ffffff",
                corner_radius=18 if is_cyber else 8
            )
        else:
            self.ai_action_btn.configure(
                text="⏹ DEACTIVATE SENTINEL" if is_cyber else "DEACTIVATE SENTINEL",
                font=get_font(12, "bold"),
                fg_color="#00ff9f" if is_cyber else "#00aa00",
                hover_color="#00d685" if is_cyber else "#008800",
                text_color="#05060f" if is_cyber else "#ffffff",
                corner_radius=18 if is_cyber else 8
            )

        self.ai_diag_btn.configure(
            text="🩺 DIAG" if is_cyber else "🩺 Diag",
            font=get_font(11, "bold"),
            fg_color=theme["bg_card_inner"],
            hover_color="#1e293b" if is_cyber else "#222222",
            text_color=theme["accent_cyan"] if is_cyber else theme["text_secondary"],
            border_color=theme.get("border_glow", "#333333") if is_cyber else "#333333",
            corner_radius=18 if is_cyber else 8
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
            font=get_font(12, "bold"),
            fg_color="#e11d48" if is_cyber else "#8b1515",
            hover_color="#f43f5e" if is_cyber else "#aa1818",
            text_color="#ffffff",
            corner_radius=18 if is_cyber else 8
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
            font=get_font(12, "bold"),
            fg_color="#0f172a" if is_cyber else "#262626",
            hover_color="#1e293b" if is_cyber else "#333333",
            text_color=theme["accent_cyan"] if is_cyber else "#ffffff",
            border_width=1 if is_cyber else 0,
            border_color="#00f0ff" if is_cyber else "#333333",
            corner_radius=18 if is_cyber else 8
        )

        # Card 5: Network Stabilizer
        self.net_card.configure(
            fg_color=theme["bg_card"],
            border_color=theme.get("border_green", "#10b981") if is_cyber else "#1e1e1e",
            corner_radius=14
        )
        self.net_title.configure(
            text="🌐 NETWORK STABILIZER" if is_cyber else "🌐 Network Stabilizer",
            font=get_font(14, "bold"),
            text_color=theme.get("accent_green", "#00ff9f") if is_cyber else theme["text_title"]
        )
        self.net_status_label.configure(
            font=get_font(10, "normal"),
            text_color=theme["text_secondary"]
        )
        self.net_quick_btn.configure(
            text="⚡ STABILIZE" if is_cyber else "Stabilize",
            font=get_font(12, "bold"),
            fg_color=theme.get("accent_green", "#00ff9f") if is_cyber else "#1a6b3a",
            hover_color="#34d399" if is_cyber else "#22804a",
            text_color="#020617" if is_cyber else "#ffffff",
            corner_radius=16 if is_cyber else 6
        )
        self.net_advanced_btn.configure(
            text="⚙️ ADVANCED" if is_cyber else "⚙️ Advanced",
            font=get_font(11, "bold"),
            fg_color=theme["bg_card_inner"],
            hover_color="#1e293b" if is_cyber else "#222222",
            text_color=theme["accent_cyan"] if is_cyber else theme["text_secondary"],
            border_color=theme.get("border_green", "#333333") if is_cyber else "#333333",
            corner_radius=16 if is_cyber else 6
        )

        # In-Window Subview Panels
        if hasattr(self, "process_killer_frame"):
            self.process_killer_frame.configure(fg_color=theme["bg_main"])
            self.pk_back_btn.configure(
                text="◄ BACK TO GAME BOOSTER" if is_cyber else "◄ Back to Game Booster",
                fg_color="#1e293b" if is_cyber else "#333333",
                hover_color="#334155" if is_cyber else "#444444",
                text_color="#00f0ff" if is_cyber else "#ffffff",
                corner_radius=17 if is_cyber else 8
            )
            self.pk_title_lbl.configure(
                text="🎯 PROCESS TERMINATOR // PURGE OPS" if is_cyber else "🎯 Process Terminator",
                text_color="#f43f5e" if is_cyber else theme["text_title"]
            )
            self.pk_subtitle_lbl.configure(
                text="// Inspect running tasks, identify RAM consumers, and terminate bloatware" if is_cyber else "Inspect running tasks, identify RAM consumers, and terminate bloatware.",
                text_color=theme["text_secondary"]
            )
            self.pk_select_all_btn.configure(
                fg_color="#1e293b" if is_cyber else "#333333",
                hover_color="#334155" if is_cyber else "#444444",
                text_color="#ffffff",
                corner_radius=16 if is_cyber else 6
            )
            self.pk_rescan_btn.configure(
                text="⚡ RESCAN" if is_cyber else "Rescan",
                fg_color="#1e293b" if is_cyber else "#333333",
                hover_color="#334155" if is_cyber else "#444444",
                text_color="#00f0ff" if is_cyber else theme["nav_btn_text"],
                corner_radius=16 if is_cyber else 6
            )
            self.pk_scroll.configure(
                fg_color=theme["bg_card"],
                border_color="#f43f5e" if is_cyber else "#1e1e1e"
            )
            self.pk_bottom_frame.configure(
                fg_color=theme["bg_card"],
                border_color="#f43f5e" if is_cyber else "#1e1e1e"
            )
            self.pk_summary_lbl.configure(text_color=theme["text_primary"])
            self.pk_status_lbl.configure(text_color=theme["text_secondary"])
            self.pk_term_btn.configure(
                corner_radius=19 if is_cyber else 8
            )

        if hasattr(self, "diagnostics_frame"):
            self.diagnostics_frame.configure(fg_color=theme["bg_main"])
            self.diag_back_btn.configure(
                text="◄ BACK TO GAME BOOSTER" if is_cyber else "◄ Back to Game Booster",
                fg_color="#1e293b" if is_cyber else "#333333",
                hover_color="#334155" if is_cyber else "#444444",
                text_color="#00f0ff" if is_cyber else "#ffffff",
                corner_radius=17 if is_cyber else 8
            )
            self.diag_title_lbl.configure(
                text="🩺 SENTINEL HEALTH DIAGNOSTICS" if is_cyber else "🩺 Sentinel Health Check",
                text_color="#00f0ff" if is_cyber else theme["text_title"]
            )
            self.diag_rerun_btn.configure(
                text="⚡ RE-RUN" if is_cyber else "Re-run",
                fg_color="#1e293b" if is_cyber else "#333333",
                hover_color="#334155" if is_cyber else "#444444",
                text_color="#00f0ff" if is_cyber else theme["nav_btn_text"],
                corner_radius=16 if is_cyber else 6
            )
            self.diag_summary_frame.configure(
                fg_color=theme["bg_card"],
                border_color=theme.get("border_glow", "#1e1e1e") if is_cyber else "#1e1e1e"
            )
            self.diag_scroll.configure(
                fg_color=theme["bg_card"],
                border_color=theme.get("border_card", "#1e1e1e")
            )

        if hasattr(self, "network_frame"):
            self.network_frame.configure(fg_color=theme["bg_main"])
            self.net_back_btn.configure(
                text="◄ BACK TO GAME BOOSTER" if is_cyber else "◄ Back to Game Booster",
                fg_color="#1e293b" if is_cyber else "#333333",
                hover_color="#334155" if is_cyber else "#444444",
                text_color="#00f0ff" if is_cyber else "#ffffff",
                corner_radius=17 if is_cyber else 8
            )
            self.net_top_title.configure(
                text="🌐 NETWORK STABILIZATION CENTER" if is_cyber else "🌐 Network Stabilizer",
                text_color="#00f0ff" if is_cyber else theme["text_title"]
            )
            self.net_probe_btn.configure(
                text="⚡ RE-PROBE" if is_cyber else "Re-probe",
                fg_color="#1e293b" if is_cyber else "#333333",
                hover_color="#334155" if is_cyber else "#444444",
                text_color="#00f0ff" if is_cyber else theme["nav_btn_text"],
                corner_radius=16 if is_cyber else 6
            )
            self.net_status_card.configure(
                fg_color=theme["bg_card"],
                border_color=theme.get("border_glow", "#1e1e1e") if is_cyber else "#1e1e1e"
            )
            self.net_scroll.configure(
                fg_color=theme["bg_card"],
                border_color=theme.get("border_card", "#1e1e1e")
            )

        if hasattr(self, "sysmain_frame"):
            self.sysmain_frame.configure(fg_color=theme["bg_main"])
            self.sm_back_btn.configure(
                text="◄ BACK TO GAME BOOSTER" if is_cyber else "◄ Back to Game Booster",
                fg_color="#1e293b" if is_cyber else "#333333",
                hover_color="#334155" if is_cyber else "#444444",
                text_color="#00f0ff" if is_cyber else "#ffffff",
                corner_radius=17 if is_cyber else 8
            )
            self.sm_top_title.configure(
                text="💾 SYSMAIN STORAGE TWEAKER" if is_cyber else "💾 SysMain (Superfetch)",
                text_color=theme["accent_amber"] if is_cyber else theme["text_title"]
            )
            self.sm_info_card.configure(
                fg_color=theme["bg_card"],
                border_color=theme.get("border_card", "#1e1e1e")
            )
            self.sm_status_card.configure(
                fg_color=theme["bg_card"],
                border_color="#fbbf24" if is_cyber else "#1e1e1e"
            )

        self._update_ram_label()

    def destroy(self):
        """Clean up background telemetry thread and Sentinel callback."""
        if hasattr(self, "_telemetry_stop"):
            self._telemetry_stop.set()
        if hasattr(self, "ai_service") and self.ai_service:
            self.ai_service.set_callback(None)
        super().destroy()

    # ── Live Telemetry & Real-Time Refresher Daemon ────────────

    def _start_telemetry_loop(self):
        """Background thread updating the HUD memory telemetry every 3s."""
        def _worker():
            while not self._telemetry_stop.is_set():
                try:
                    mb = get_memory_breakdown()
                    ai_stat = self.ai_service.get_status()
                    try:
                        if not self._telemetry_stop.is_set() and self.winfo_exists():
                            self.after(0, self._update_hud_display, mb, ai_stat)
                    except Exception:
                        pass
                except Exception:
                    pass
                if self._telemetry_stop.wait(3.0):
                    break

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
                try:
                    if hasattr(self, "_telemetry_stop") and not self._telemetry_stop.is_set() and self.winfo_exists():
                        self.after(0, self._render_sysmain_chip, sm_status, has_ssd)
                except Exception:
                    pass
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

    # ── In-Window Sentinel Diagnostics View ────────────────────

    def _init_diagnostics_frame(self, theme: dict, is_cyber: bool):
        """Construct the in-window Sentinel Diagnostics panel."""
        self.diagnostics_frame = ctk.CTkFrame(self, fg_color="transparent")

        # Top Bar: Back Button, Title, Subtitle, and Action Controls
        self.diag_top_bar = ctk.CTkFrame(self.diagnostics_frame, fg_color="transparent")
        self.diag_top_bar.pack(fill="x", padx=15, pady=(12, 6))
        self.diag_top_bar.grid_columnconfigure(1, weight=1)

        self.diag_back_btn = ctk.CTkButton(
            self.diag_top_bar,
            text="◄ BACK TO GAME BOOSTER" if is_cyber else "◄ Back to Game Booster",
            font=get_font(12, "bold"),
            fg_color="#1e293b" if is_cyber else "#333333",
            hover_color="#334155" if is_cyber else "#444444",
            text_color="#00f0ff" if is_cyber else "#ffffff",
            width=190,
            height=34,
            corner_radius=17 if is_cyber else 8,
            command=self.show_dashboard
        )
        self.diag_back_btn.grid(row=0, column=0, rowspan=2, padx=(0, 14), sticky="w")

        self.diag_title_lbl = ctk.CTkLabel(
            self.diag_top_bar,
            text="🩺 SENTINEL HEALTH DIAGNOSTICS" if is_cyber else "🩺 Sentinel Health Check",
            font=get_font(18, "bold"),
            text_color="#00f0ff" if is_cyber else theme["text_title"],
            anchor="w"
        )
        self.diag_title_lbl.grid(row=0, column=1, sticky="w")

        self.diag_subtitle_lbl = ctk.CTkLabel(
            self.diag_top_bar,
            text="// Autonomous watchdog diagnostics, kernel timer lock & subsystem health verification" if is_cyber else "Autonomous watchdog diagnostics and subsystem health probe.",
            font=get_font(11, "normal"),
            text_color=theme["text_secondary"],
            anchor="w"
        )
        self.diag_subtitle_lbl.grid(row=1, column=1, sticky="w", pady=(2, 0))

        self.diag_rerun_btn = ctk.CTkButton(
            self.diag_top_bar,
            text="⚡ RE-RUN" if is_cyber else "Re-run",
            font=get_font(12, "bold"),
            fg_color="#1e293b" if is_cyber else "#333333",
            hover_color="#334155" if is_cyber else "#444444",
            text_color="#00f0ff" if is_cyber else theme["nav_btn_text"],
            width=100,
            height=32,
            corner_radius=16 if is_cyber else 6,
            command=self._diag_run
        )
        self.diag_rerun_btn.grid(row=0, column=2, rowspan=2, sticky="e")

        # Summary banner
        self.diag_summary_frame = ctk.CTkFrame(
            self.diagnostics_frame,
            fg_color=theme["bg_card"],
            corner_radius=12,
            border_width=1,
            border_color=theme.get("border_glow", "#1e1e1e") if is_cyber else "#1e1e1e"
        )
        self.diag_summary_frame.pack(fill="x", padx=15, pady=(4, 6))

        self.diag_summary_label = ctk.CTkLabel(
            self.diag_summary_frame,
            text="⏳ Running diagnostics…",
            font=get_font(13, "bold"),
            text_color=theme["accent_cyan"] if is_cyber else theme["text_primary"]
        )
        self.diag_summary_label.pack(padx=14, pady=10)

        # Scrollable results area
        self.diag_scroll = ctk.CTkScrollableFrame(
            self.diagnostics_frame,
            fg_color=theme["bg_card"],
            corner_radius=12,
            border_width=1,
            border_color=theme.get("border_card", "#1e1e1e")
        )
        self.diag_scroll.pack(fill="both", expand=True, padx=15, pady=(4, 12))
        self.diag_scroll.grid_columnconfigure(0, weight=0)  # icon
        self.diag_scroll.grid_columnconfigure(1, weight=1)  # label + detail
        self.diag_scroll.grid_columnconfigure(2, weight=0)  # badge

    def show_diagnostics(self):
        """Transition into the in-window Sentinel Diagnostics panel."""
        self._switch_to_subview(self.diagnostics_frame)
        self._diag_run()

    def _open_sentinel_diagnostics(self):
        """Open diagnostic health-check panel in the main window."""
        self.show_diagnostics()

    def _diag_run(self, sync: bool = False):
        """Probe all Sentinel subsystems in background and display results."""
        theme = get_theme()
        is_cyber = is_cyber_mode()

        self.diag_summary_label.configure(
            text="⏳ Running diagnostics…",
            text_color=theme["accent_cyan"] if is_cyber else theme["text_primary"]
        )
        self.diag_subtitle_lbl.configure(
            text="// Autonomous watchdog diagnostics, kernel timer lock & subsystem health verification" if is_cyber else "Probing all subsystems…"
        )

        for child in self.diag_scroll.winfo_children():
            child.destroy()

        def _worker():
            report = self.ai_service.run_diagnostics()
            try:
                self.after(0, lambda: self._diag_render(report))
            except Exception:
                if sync:
                    self._diag_render(report)

        if sync:
            _worker()
        else:
            threading.Thread(target=_worker, daemon=True, name="SentinelDiag").start()

    def _diag_render(self, report: dict):
        """Render diagnostic report cards on the main thread."""
        try:
            if not self.winfo_exists():
                return
        except Exception:
            return

        theme = get_theme()
        is_cyber = is_cyber_mode()

        overall = report.get("overall", "UNKNOWN")
        p, f, w = report.get("passed", 0), report.get("failed", 0), report.get("warned", 0)

        if overall == "HEALTHY":
            icon = "✅"
            color = theme["accent_green"] if is_cyber else "#00ff00"
            verdict = "ALL SYSTEMS OPERATIONAL"
        else:
            icon = "⚠️"
            color = "#fbbf24" if f == 0 else "#f43f5e"
            verdict = "SYSTEM DEGRADED" if f > 0 else "PARTIAL WARNINGS"

        self.diag_summary_label.configure(
            text=f"{icon}  {verdict}  —  {p} Passed · {w} Warn · {f} Failed",
            text_color=color
        )
        self.diag_subtitle_lbl.configure(
            text="// Subsystem diagnostics complete · Watchdog thread active" if is_cyber else "Diagnostics complete."
        )

        STATUS_ICONS = {"PASS": "✅", "FAIL": "❌", "WARN": "⚠️"}
        STATUS_COLORS = {
            "PASS": theme["accent_green"] if is_cyber else "#00cc66",
            "FAIL": "#f43f5e",
            "WARN": "#fbbf24",
        }

        for idx, check in enumerate(report.get("checks", [])):
            status = check["status"]
            s_icon = STATUS_ICONS.get(status, "❓")
            s_color = STATUS_COLORS.get(status, theme["text_secondary"])

            # Status icon
            icon_lbl = ctk.CTkLabel(
                self.diag_scroll,
                text=s_icon,
                font=get_font(16, "bold"),
                width=28
            )
            icon_lbl.grid(row=idx, column=0, padx=(10, 4), pady=6, sticky="w")

            # Label + detail column
            info_frame = ctk.CTkFrame(self.diag_scroll, fg_color="transparent")
            info_frame.grid(row=idx, column=1, padx=4, pady=6, sticky="ew")

            name_lbl = ctk.CTkLabel(
                info_frame,
                text=check["label"],
                font=get_font(13, "bold"),
                text_color=theme["text_primary"]
            )
            name_lbl.pack(anchor="w")

            detail_lbl = ctk.CTkLabel(
                info_frame,
                text=check["detail"],
                font=get_font(10, "normal"),
                text_color=theme["text_secondary"],
                wraplength=480
            )
            detail_lbl.pack(anchor="w")

            # Status badge pill
            badge = ctk.CTkLabel(
                self.diag_scroll,
                text=f" {status} ",
                font=get_font(10, "bold"),
                fg_color=s_color,
                text_color="#000000" if status != "FAIL" else "#ffffff",
                corner_radius=6,
                padx=6,
                pady=2
            )
            badge.grid(row=idx, column=2, padx=(4, 10), pady=6, sticky="e")

    def _on_ai_status_update(self, data: dict):
        """Callback invoked by background watchdog on state changes."""
        try:
            if hasattr(self, "_telemetry_stop") and not self._telemetry_stop.is_set() and self.winfo_exists():
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
    def _update_ram_label(self):
        ram = get_current_available_ram_mb()
        try:
            mb = get_memory_breakdown()
            ai_stat = self.ai_service.get_status()
            self._update_hud_display(mb, ai_stat)
        except Exception:
            pass
        return ram

    # ── In-Window Process Killer View ──────────────────────────

    def _init_process_killer_frame(self, theme: dict, is_cyber: bool):
        """Construct the in-window process terminator panel (swapped with basic_frame)."""
        self.process_killer_frame = ctk.CTkFrame(self, fg_color="transparent")
        # Initially not gridded; activated via self.show_process_killer()

        # Top Bar: Back Button, Title, Subtitle, and Action Controls
        self.pk_top_bar = ctk.CTkFrame(self.process_killer_frame, fg_color="transparent")
        self.pk_top_bar.pack(fill="x", padx=15, pady=(12, 6))
        self.pk_top_bar.grid_columnconfigure(1, weight=1)

        self.pk_back_btn = ctk.CTkButton(
            self.pk_top_bar,
            text="◄ BACK TO GAME BOOSTER" if is_cyber else "◄ Back to Game Booster",
            font=get_font(12, "bold"),
            fg_color="#1e293b" if is_cyber else "#333333",
            hover_color="#334155" if is_cyber else "#444444",
            text_color="#00f0ff" if is_cyber else "#ffffff",
            width=190,
            height=34,
            corner_radius=17 if is_cyber else 8,
            command=self.show_dashboard
        )
        self.pk_back_btn.grid(row=0, column=0, rowspan=2, padx=(0, 14), sticky="w")

        self.pk_title_lbl = ctk.CTkLabel(
            self.pk_top_bar,
            text="🎯 PROCESS TERMINATOR // PURGE OPS" if is_cyber else "🎯 Process Terminator",
            font=get_font(18, "bold"),
            text_color="#f43f5e" if is_cyber else theme["text_title"],
            anchor="w"
        )
        self.pk_title_lbl.grid(row=0, column=1, sticky="w")

        self.pk_subtitle_lbl = ctk.CTkLabel(
            self.pk_top_bar,
            text="// Inspect running tasks, identify RAM consumers, and terminate bloatware" if is_cyber else "Inspect running tasks, identify RAM consumers, and terminate bloatware.",
            font=get_font(11, "normal"),
            text_color=theme["text_secondary"],
            anchor="w"
        )
        self.pk_subtitle_lbl.grid(row=1, column=1, sticky="w", pady=(2, 0))

        # Top right action buttons
        self.pk_btn_box = ctk.CTkFrame(self.pk_top_bar, fg_color="transparent")
        self.pk_btn_box.grid(row=0, column=2, rowspan=2, sticky="e")

        self.pk_select_all_btn = ctk.CTkButton(
            self.pk_btn_box,
            text="Select All",
            font=get_font(12, "bold"),
            fg_color="#1e293b" if is_cyber else "#333333",
            hover_color="#334155" if is_cyber else "#444444",
            text_color="#ffffff",
            width=95,
            height=32,
            corner_radius=16 if is_cyber else 6,
            command=self._pk_toggle_select_all
        )
        self.pk_select_all_btn.pack(side="left", padx=(0, 8))

        self.pk_rescan_btn = ctk.CTkButton(
            self.pk_btn_box,
            text="⚡ RESCAN" if is_cyber else "Rescan",
            font=get_font(12, "bold"),
            fg_color="#1e293b" if is_cyber else "#333333",
            hover_color="#334155" if is_cyber else "#444444",
            text_color="#00f0ff" if is_cyber else theme["nav_btn_text"],
            width=95,
            height=32,
            corner_radius=16 if is_cyber else 6,
            command=self._pk_load_procs
        )
        self.pk_rescan_btn.pack(side="left")

        # Middle Scrollable Process List
        self.pk_scroll = ctk.CTkScrollableFrame(
            self.process_killer_frame,
            fg_color=theme["bg_card"],
            border_width=1,
            border_color="#f43f5e" if is_cyber else "#1e1e1e",
            corner_radius=12
        )
        self.pk_scroll.pack(fill="both", expand=True, padx=15, pady=(4, 8))
        self.pk_scroll.grid_columnconfigure(0, weight=1)

        # Bottom Action Bar
        self.pk_bottom_frame = ctk.CTkFrame(
            self.process_killer_frame,
            fg_color=theme["bg_card"],
            corner_radius=12,
            border_width=1,
            border_color="#f43f5e" if is_cyber else "#1e1e1e"
        )
        self.pk_bottom_frame.pack(fill="x", padx=15, pady=(0, 10))
        self.pk_bottom_frame.grid_columnconfigure(0, weight=1)
        self.pk_bottom_frame.grid_columnconfigure(1, weight=0)

        self.pk_info_box = ctk.CTkFrame(self.pk_bottom_frame, fg_color="transparent")
        self.pk_info_box.grid(row=0, column=0, padx=16, pady=8, sticky="w")

        self.pk_summary_lbl = ctk.CTkLabel(
            self.pk_info_box,
            text="0 processes selected · 0 MB reclaimable",
            font=get_font(12, "bold"),
            text_color=theme["text_primary"]
        )
        self.pk_summary_lbl.pack(anchor="w")

        self.pk_status_lbl = ctk.CTkLabel(
            self.pk_info_box,
            text="Select background apps to terminate without closing game engines",
            font=get_font(11, "normal"),
            text_color=theme["text_secondary"]
        )
        self.pk_status_lbl.pack(anchor="w", pady=(2, 0))

        self.pk_term_btn = ctk.CTkButton(
            self.pk_bottom_frame,
            text="🎯 PURGE SELECTED PROCESSES" if is_cyber else "Terminate Selected",
            font=get_font(13, "bold"),
            fg_color="#e11d48" if is_cyber else "#cc3333",
            hover_color="#f43f5e" if is_cyber else "#ff4444",
            text_color="#ffffff",
            height=38,
            corner_radius=19 if is_cyber else 8,
            command=self._pk_do_terminate
        )
        self.pk_term_btn.grid(row=0, column=1, padx=14, pady=10, sticky="e")

    def _switch_to_subview(self, target_frame):
        """Hides the main dashboard and any active subview, displaying the target panel."""
        self.header_frame.grid_remove()
        self.basic_frame.grid_remove()
        for frame in (
            getattr(self, "process_killer_frame", None),
            getattr(self, "diagnostics_frame", None),
            getattr(self, "network_frame", None),
            getattr(self, "sysmain_frame", None),
        ):
            if frame and frame != target_frame:
                frame.grid_remove()
        target_frame.grid(row=0, column=0, rowspan=2, sticky="nsew")

    def show_process_killer(self):
        """Transition into the in-window Process Terminator panel."""
        self._switch_to_subview(self.process_killer_frame)
        self._pk_load_procs()

    def show_dashboard(self):
        """Transition back to the primary Game Booster dashboard."""
        for frame in (
            getattr(self, "process_killer_frame", None),
            getattr(self, "diagnostics_frame", None),
            getattr(self, "network_frame", None),
            getattr(self, "sysmain_frame", None),
        ):
            if frame:
                frame.grid_remove()
        self.header_frame.grid(row=0, column=0, padx=20, pady=(15, 6), sticky="ew")
        self.basic_frame.grid(row=1, column=0, sticky="nsew")
        self._update_ram_label()

    def _open_process_killer(self):
        """Opens process killer in the same window (backward compatible entry point)."""
        self.show_process_killer()

    def _pk_toggle_select_all(self):
        if not self._pk_cbs:
            return
        all_checked = all(cb.get() for cb, _, _, _ in self._pk_cbs)
        for cb, _, _, _ in self._pk_cbs:
            if all_checked:
                cb.deselect()
            else:
                cb.select()
        self.pk_select_all_btn.configure(text="Select All" if all_checked else "Deselect All")
        self._pk_update_selection_summary()

    def _pk_update_selection_summary(self):
        selected = [(cb, pid, name, mem) for cb, pid, name, mem in self._pk_cbs if cb.get()]
        count = len(selected)
        tot_mb = sum(mem for _, _, _, mem in selected)
        is_cyber = is_cyber_mode()

        if count == 0:
            self.pk_summary_lbl.configure(text="0 processes selected · 0 MB reclaimable")
            self.pk_term_btn.configure(
                state="disabled",
                fg_color="#334155" if is_cyber else "#333333",
                text="SELECT PROCESSES" if is_cyber else "Select Processes"
            )
        else:
            self.pk_summary_lbl.configure(text=f"{count} process(es) selected · ~{tot_mb:,.0f} MB reclaimable")
            self.pk_term_btn.configure(
                state="normal",
                fg_color="#e11d48" if is_cyber else "#cc3333",
                text=f"🎯 PURGE {count} PROCESS(ES)" if is_cyber else f"Terminate {count} Process(es)"
            )

    def _pk_load_procs(self, sync: bool = False):
        self.pk_rescan_btn.configure(state="disabled")
        self.pk_select_all_btn.configure(state="disabled")
        for w in self.pk_scroll.winfo_children():
            w.destroy()
        self._pk_cbs.clear()
        is_cyber = is_cyber_mode()

        if sync:
            procs = get_top_memory_consumers(30)
            self._pk_render_procs(procs)
            return

        loading_lbl = ctk.CTkLabel(
            self.pk_scroll,
            text="> SCANNING ACTIVE PROCESSES...",
            text_color="#00f0ff" if is_cyber else "gray",
            font=get_font(13, "bold")
        )
        loading_lbl.grid(row=0, column=0, pady=30)

        def _worker():
            procs = get_top_memory_consumers(30)
            try:
                self.after(0, self._pk_render_procs, procs)
            except Exception:
                pass

        threading.Thread(target=_worker, daemon=True).start()

    def _pk_render_procs(self, procs):
        for w in self.pk_scroll.winfo_children():
            w.destroy()
        self._pk_cbs.clear()

        if not procs:
            ctk.CTkLabel(
                self.pk_scroll,
                text="No background processes found.",
                text_color="gray",
                font=get_font(12, "normal")
            ).grid(row=0, column=0, pady=30)
            self.pk_rescan_btn.configure(state="normal")
            self.pk_select_all_btn.configure(state="normal", text="Select All")
            self._pk_update_selection_summary()
            return

        theme = get_theme()
        is_cyber = is_cyber_mode()

        for i, p in enumerate(procs):
            row_frame = ctk.CTkFrame(
                self.pk_scroll,
                fg_color=theme.get("bg_card_inner", "#0f172a") if is_cyber else "#1f1f1f",
                corner_radius=8,
                border_width=1 if is_cyber else 0,
                border_color="#1a2b5e" if is_cyber else "#262626"
            )
            row_frame.grid(row=i, column=0, padx=10, pady=4, sticky="ew")
            row_frame.grid_columnconfigure(0, weight=1)
            row_frame.grid_columnconfigure(1, weight=0)

            cb = ctk.CTkCheckBox(
                row_frame,
                text=f"{p['name']}  [PID: {p['pid']}]",
                font=get_font(13, "normal"),
                fg_color="#f43f5e" if is_cyber else "#1f6aa5",
                hover_color="#ff4d6d" if is_cyber else "#2980b9",
                checkmark_color="#ffffff",
                command=self._pk_update_selection_summary
            )
            cb.grid(row=0, column=0, padx=12, pady=8, sticky="w")

            mem_badge = ctk.CTkLabel(
                row_frame,
                text=f"{p['memory_mb']:,.0f} MB",
                font=get_font(12, "bold", is_stat=True),
                fg_color="#1e293b" if is_cyber else "#262626",
                text_color="#f43f5e" if is_cyber else "#ffffff",
                corner_radius=6,
                padx=8,
                pady=2
            )
            mem_badge.grid(row=0, column=1, padx=12, pady=8, sticky="e")

            self._pk_cbs.append((cb, p['pid'], p['name'], p['memory_mb']))

        self.pk_rescan_btn.configure(state="normal")
        self.pk_select_all_btn.configure(state="normal", text="Select All")
        self._pk_update_selection_summary()

    def _pk_do_terminate(self):
        selected = [(cb, pid, name, mem) for cb, pid, name, mem in self._pk_cbs if cb.get()]
        if not selected:
            self.pk_status_lbl.configure(text="No processes selected.", text_color="#ff4d4f")
            return

        is_cyber = is_cyber_mode()
        self.pk_term_btn.configure(state="disabled", text="⚡ TERMINATING..." if is_cyber else "Terminating...")
        pids = [pid for _, pid, _, _ in selected]
        ram_before = get_current_available_ram_mb()

        def _kill():
            results = terminate_processes(pids)
            time.sleep(1.0)
            try:
                if self.winfo_exists():
                    try:
                        self.after(0, self._pk_on_terminate_done, results, ram_before)
                    except RuntimeError:
                        self._pk_on_terminate_done(results, ram_before)
            except Exception:
                pass

        threading.Thread(target=_kill, daemon=True).start()

    def _pk_on_terminate_done(self, results, ram_before):
        ram_after = get_current_available_ram_mb()
        recovered = ram_after - ram_before
        success = results["success"]
        is_cyber = is_cyber_mode()

        if recovered > 0:
            self.pk_status_lbl.configure(
                text=f"Purged {success} process(es) — recovered {recovered:,.0f} MB RAM",
                text_color="#00ff9f" if is_cyber else "#00ff00"
            )
        else:
            self.pk_status_lbl.configure(
                text=f"Terminated {success} process(es).",
                text_color="gray"
            )
        self.pk_term_btn.configure(
            state="normal",
            text="🎯 PURGE SELECTED PROCESSES" if is_cyber else "Terminate Selected"
        )
        self._update_ram_label()
        self._pk_load_procs()

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
            try:
                if self.winfo_exists():
                    self.after(0, self._on_smart_boost_complete,
                               standby_result, trim_result, ram_before)
            except Exception:
                pass

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

    # ── Network Stabilization Handlers ─────────────────────────

    def _run_quick_network_stabilize(self):
        """1-click network stabilization: DNS flush + Nagle + throttling + TCP."""
        theme = get_theme()
        is_cyber = is_cyber_mode()
        self.net_quick_btn.configure(state="disabled", text="Stabilizing...")
        self.net_status_label.configure(
            text="⚡ Running network stabilization...",
            text_color=theme["accent_cyan"] if is_cyber else "#ffcc00"
        )

        def _worker():
            result = stabilize_network()
            try:
                if self.winfo_exists():
                    self.after(0, _done, result)
            except Exception:
                pass

        def _done(result):
            try:
                if not self.winfo_exists():
                    return
            except Exception:
                return

            if result.get("success"):
                self.net_status_label.configure(
                    text="● DNS Flushed · TCP Optimized · Throttling Disabled · Nagle Off",
                    text_color=theme.get("accent_green", "#00ff9f") if is_cyber else "#00cc66"
                )
                self.basic_status_label.configure(
                    text="⚡ Network stabilized — DNS flushed, TCP optimized, throttling disabled.",
                    text_color=theme.get("accent_green", "#00ff9f") if is_cyber else "#00ff00"
                )
            else:
                self.net_status_label.configure(
                    text="⚠️ Some optimizations need admin privileges",
                    text_color="#fbbf24"
                )
            self.net_quick_btn.configure(
                state="normal",
                text="⚡ STABILIZE" if is_cyber else "Stabilize"
            )

        threading.Thread(target=_worker, daemon=True).start()

    # ── In-Window Network Stabilizer View ───────────────────────

    def _init_network_frame(self, theme: dict, is_cyber: bool):
        """Construct the in-window Network Stabilization Center panel."""
        self.network_frame = ctk.CTkFrame(self, fg_color="transparent")

        # Top Bar
        self.net_top_bar = ctk.CTkFrame(self.network_frame, fg_color="transparent")
        self.net_top_bar.pack(fill="x", padx=15, pady=(12, 6))
        self.net_top_bar.grid_columnconfigure(1, weight=1)

        self.net_back_btn = ctk.CTkButton(
            self.net_top_bar,
            text="◄ BACK TO GAME BOOSTER" if is_cyber else "◄ Back to Game Booster",
            font=get_font(12, "bold"),
            fg_color="#1e293b" if is_cyber else "#333333",
            hover_color="#334155" if is_cyber else "#444444",
            text_color="#00f0ff" if is_cyber else "#ffffff",
            width=190,
            height=34,
            corner_radius=17 if is_cyber else 8,
            command=self.show_dashboard
        )
        self.net_back_btn.grid(row=0, column=0, rowspan=2, padx=(0, 14), sticky="w")

        self.net_top_title = ctk.CTkLabel(
            self.net_top_bar,
            text="🌐 NETWORK STABILIZATION CENTER" if is_cyber else "🌐 Network Stabilizer",
            font=get_font(18, "bold"),
            text_color="#00f0ff" if is_cyber else theme["text_title"],
            anchor="w"
        )
        self.net_top_title.grid(row=0, column=1, sticky="w")

        self.net_top_subtitle = ctk.CTkLabel(
            self.net_top_bar,
            text="// Low-latency TCP/IP tuning, adapter power optimization, and DNS calibration" if is_cyber else "Optimize your network stack for minimum latency gaming.",
            font=get_font(11, "normal"),
            text_color=theme["text_secondary"],
            anchor="w"
        )
        self.net_top_subtitle.grid(row=1, column=1, sticky="w", pady=(2, 0))

        self.net_probe_btn = ctk.CTkButton(
            self.net_top_bar,
            text="⚡ RE-PROBE" if is_cyber else "Re-probe",
            font=get_font(12, "bold"),
            fg_color="#1e293b" if is_cyber else "#333333",
            hover_color="#334155" if is_cyber else "#444444",
            text_color="#00f0ff" if is_cyber else theme["nav_btn_text"],
            width=100,
            height=32,
            corner_radius=16 if is_cyber else 6,
            command=self._net_probe_status
        )
        self.net_probe_btn.grid(row=0, column=2, rowspan=2, sticky="e")

        # Live status banner
        self.net_status_card = ctk.CTkFrame(
            self.network_frame,
            fg_color=theme["bg_card"],
            corner_radius=12,
            border_width=1,
            border_color=theme.get("border_glow", "#1e1e1e") if is_cyber else "#1e1e1e"
        )
        self.net_status_card.pack(fill="x", padx=15, pady=(4, 6))
        self.net_status_card.grid_columnconfigure((0, 1, 2), weight=1)

        self.net_adapter_lbl = ctk.CTkLabel(
            self.net_status_card, text="Adapter: Checking...",
            font=get_font(11, "bold"), text_color=theme["text_secondary"]
        )
        self.net_adapter_lbl.grid(row=0, column=0, padx=14, pady=10, sticky="w")

        self.net_latency_lbl = ctk.CTkLabel(
            self.net_status_card, text="Latency: --",
            font=get_font(11, "bold"), text_color=theme["text_secondary"]
        )
        self.net_latency_lbl.grid(row=0, column=1, padx=14, pady=10)

        self.net_dns_lbl = ctk.CTkLabel(
            self.net_status_card, text="DNS: --",
            font=get_font(11, "bold"), text_color=theme["text_secondary"]
        )
        self.net_dns_lbl.grid(row=0, column=2, padx=14, pady=10, sticky="e")

        # Result status feedback
        self.net_result_lbl = ctk.CTkLabel(
            self.network_frame, text="", font=get_font(12, "bold"),
            text_color=theme.get("accent_green", "#00ff00")
        )
        self.net_result_lbl.pack(padx=15, pady=(2, 4), anchor="w")

        # Scrollable action buttons
        self.net_scroll = ctk.CTkScrollableFrame(
            self.network_frame,
            fg_color=theme["bg_card"],
            corner_radius=12,
            border_width=1,
            border_color=theme.get("border_card", "#1e1e1e")
        )
        self.net_scroll.pack(fill="both", expand=True, padx=15, pady=(0, 12))
        self.net_scroll.grid_columnconfigure(0, weight=1)

        self._build_network_actions(theme, is_cyber)

    def _build_network_actions(self, theme: dict, is_cyber: bool):
        """Populate the network actions list."""
        def _make_row(parent, row, icon, title, desc, btn_text, command):
            frame = ctk.CTkFrame(parent, fg_color="transparent")
            frame.grid(row=row, column=0, padx=12, pady=6, sticky="ew")
            frame.grid_columnconfigure(0, weight=1)
            frame.grid_columnconfigure(1, weight=0)

            info = ctk.CTkFrame(frame, fg_color="transparent")
            info.grid(row=0, column=0, sticky="ew")

            ctk.CTkLabel(
                info, text=f"{icon}  {title}",
                font=get_font(13, "bold"),
                text_color=theme["text_primary"]
            ).pack(anchor="w")

            ctk.CTkLabel(
                info, text=desc,
                font=get_font(11, "normal"),
                text_color=theme["text_secondary"],
                wraplength=520
            ).pack(anchor="w")

            btn = ctk.CTkButton(
                frame, text=btn_text,
                font=get_font(11, "bold"),
                fg_color=theme.get("accent_green", "#00ff9f") if is_cyber else "#1a6b3a",
                hover_color="#34d399" if is_cyber else "#22804a",
                text_color="#020617" if is_cyber else "#ffffff",
                width=100, height=32,
                corner_radius=16 if is_cyber else 6,
                command=command
            )
            btn.grid(row=0, column=1, padx=(12, 0), sticky="e")
            return btn

        self.net_btn1 = _make_row(
            self.net_scroll, 0, "🧹", "Flush DNS Cache",
            "Clear stale DNS entries for fresh game server lookups.",
            "Flush",
            lambda: self._net_run_action(self.net_btn1, flush_dns_cache, "DNS cache flushed", "DNS flush failed")
        )

        self.net_btn2 = _make_row(
            self.net_scroll, 1, "🚀", "Optimize DNS Servers",
            "Set Cloudflare (1.1.1.1) + Google (8.8.8.8) for fastest lookups.",
            "Optimize",
            lambda: self._net_run_action(self.net_btn2, optimize_dns_servers, "DNS servers optimized", "DNS change failed")
        )

        self.net_btn3 = _make_row(
            self.net_scroll, 2, "⚡", "Disable Network Throttling",
            "Remove Windows throughput limiter that causes lag spikes.",
            "Disable",
            lambda: self._net_run_action(self.net_btn3, disable_network_throttling, "Network throttling disabled", "Throttling fix failed")
        )

        self.net_btn4 = _make_row(
            self.net_scroll, 3, "📶", "Disable Adapter Power Saving",
            "Prevent NIC sleep mode that causes periodic latency spikes.",
            "Disable",
            lambda: self._net_run_action(self.net_btn4, disable_network_power_saving, "Adapter power saving disabled", "Power config failed")
        )

        self.net_btn5 = _make_row(
            self.net_scroll, 4, "🔧", "Optimize TCP/IP Stack",
            "Tune auto-tuning, DCA, and congestion provider for gaming.",
            "Tune",
            lambda: self._net_run_action(self.net_btn5, optimize_tcp_settings, "TCP stack optimized", "TCP tuning failed")
        )

        self.net_btn6 = _make_row(
            self.net_scroll, 5, "⚠️", "Reset Network Stack (Reboot)",
            "Nuclear reset: Winsock + TCP/IP. Fixes deep corruption. Needs reboot.",
            "Reset",
            lambda: self._net_run_action(self.net_btn6, reset_network_stack, "Network stack reset (reboot required)", "Stack reset failed")
        )
        self.net_btn6.configure(
            fg_color="#e11d48" if is_cyber else "#8b1515",
            hover_color="#f43f5e" if is_cyber else "#aa1818",
            text_color="#ffffff"
        )

    def show_network(self):
        """Transition to the dedicated Network Stabilizer view via window shift."""
        try:
            top = self.winfo_toplevel()
            if hasattr(top, "show_network"):
                top.show_network()
                return
        except Exception:
            pass
        self._switch_to_subview(self.network_frame)
        self._net_probe_status()

    def _open_network_dialog(self):
        """Open advanced network stabilization via window shift."""
        self.show_network()

    def _net_run_action(self, btn, action_fn, success_msg, fail_msg):
        """Run a network tuning action asynchronously with feedback."""
        theme = get_theme()
        orig_text = btn.cget("text")
        btn.configure(state="disabled", text="...")
        self.net_result_lbl.configure(text="")

        def _worker():
            res = action_fn()
            try:
                self.after(0, _done, res)
            except Exception:
                try:
                    _done(res)
                except Exception:
                    pass

        def _done(res):
            try:
                if not self.winfo_exists():
                    return
            except Exception:
                return
            btn.configure(state="normal", text=orig_text)
            if res.get("success"):
                self.net_result_lbl.configure(text=f"✅  {success_msg}", text_color=theme.get("accent_green", "#00ff00"))
            else:
                err = res.get("error", "Unknown error")
                self.net_result_lbl.configure(text=f"❌  {fail_msg}: {err}", text_color="#f43f5e")
            self._net_probe_status()

        threading.Thread(target=_worker, daemon=True).start()

    def _net_probe_status(self, sync: bool = False):
        """Probe live network adapter, latency, and DNS status."""
        def _worker():
            info = get_network_status()
            try:
                self.after(0, self._net_render_status, info)
            except Exception:
                if sync:
                    self._net_render_status(info)

        if sync:
            _worker()
        else:
            threading.Thread(target=_worker, daemon=True).start()

    def _net_render_status(self, info: dict):
        """Update network status banner on the main thread."""
        try:
            if not self.winfo_exists():
                return
        except Exception:
            return

        theme = get_theme()

        if info.get("connected"):
            self.net_adapter_lbl.configure(
                text=f"🟢  {info.get('adapter', '?')} ({info.get('link_speed', '?')})",
                text_color=theme.get("accent_green", "#00ff00")
            )
        else:
            self.net_adapter_lbl.configure(text="🔴  Disconnected", text_color="#f43f5e")

        lat = info.get("latency_ms", -1)
        if lat >= 0:
            lat_color = theme.get("accent_green", "#00ff00") if lat < 50 else ("#fbbf24" if lat < 100 else "#f43f5e")
            self.net_latency_lbl.configure(text=f"Ping: {lat}ms", text_color=lat_color)
        else:
            self.net_latency_lbl.configure(text="Ping: --", text_color=theme["text_secondary"])

        dns_list = info.get("dns", [])
        if dns_list:
            self.net_dns_lbl.configure(text=f"DNS: {', '.join(dns_list[:2])}", text_color=theme["text_primary"])
        else:
            self.net_dns_lbl.configure(text="DNS: Auto", text_color=theme["text_secondary"])

    # ── In-Window SysMain Control View ─────────────────────────

    def _init_sysmain_frame(self, theme: dict, is_cyber: bool):
        """Construct the in-window SysMain Storage Tweaker panel."""
        self.sysmain_frame = ctk.CTkFrame(self, fg_color="transparent")
        self._sm_state = {"running": None}

        # Top Bar
        self.sm_top_bar = ctk.CTkFrame(self.sysmain_frame, fg_color="transparent")
        self.sm_top_bar.pack(fill="x", padx=15, pady=(12, 6))
        self.sm_top_bar.grid_columnconfigure(1, weight=1)

        self.sm_back_btn = ctk.CTkButton(
            self.sm_top_bar,
            text="◄ BACK TO GAME BOOSTER" if is_cyber else "◄ Back to Game Booster",
            font=get_font(12, "bold"),
            fg_color="#1e293b" if is_cyber else "#333333",
            hover_color="#334155" if is_cyber else "#444444",
            text_color="#00f0ff" if is_cyber else "#ffffff",
            width=190,
            height=34,
            corner_radius=17 if is_cyber else 8,
            command=self.show_dashboard
        )
        self.sm_back_btn.grid(row=0, column=0, rowspan=2, padx=(0, 14), sticky="w")

        self.sm_top_title = ctk.CTkLabel(
            self.sm_top_bar,
            text="💾 SYSMAIN STORAGE TWEAKER" if is_cyber else "💾 SysMain (Superfetch)",
            font=get_font(18, "bold"),
            text_color=theme["accent_amber"] if is_cyber else theme["text_title"],
            anchor="w"
        )
        self.sm_top_title.grid(row=0, column=1, sticky="w")

        self.sm_top_subtitle = ctk.CTkLabel(
            self.sm_top_bar,
            text="// Disable background superfetch caching & RAM prefetching on SSDs" if is_cyber else "Configure SysMain service to prevent memory bloat on SSD systems.",
            font=get_font(11, "normal"),
            text_color=theme["text_secondary"],
            anchor="w"
        )
        self.sm_top_subtitle.grid(row=1, column=1, sticky="w", pady=(2, 0))

        # Info card
        self.sm_info_card = ctk.CTkFrame(
            self.sysmain_frame,
            fg_color=theme["bg_card"],
            corner_radius=12,
            border_width=1,
            border_color=theme.get("border_card", "#1e1e1e")
        )
        self.sm_info_card.pack(fill="x", padx=15, pady=(4, 6))

        self.sm_info_lbl = ctk.CTkLabel(
            self.sm_info_card,
            text="SysMain (Superfetch) pre-caches application data into RAM in the background.\n"
                 "On SSDs and NVMe drives, this wastes valuable memory bandwidth and can cause in-game micro-stutter.\n"
                 "Disabling SysMain eliminates background indexing spikes and frees RAM without slowing app launches.",
            font=get_font(12, "normal"),
            text_color=theme["text_secondary"],
            justify="left"
        )
        self.sm_info_lbl.pack(padx=16, pady=12, anchor="w")

        # Live Status Card
        self.sm_status_card = ctk.CTkFrame(
            self.sysmain_frame,
            fg_color=theme["bg_card"],
            border_width=1,
            border_color="#fbbf24" if is_cyber else "#1e1e1e",
            corner_radius=12
        )
        self.sm_status_card.pack(fill="x", padx=15, pady=6)

        self.sm_status_lbl = ctk.CTkLabel(
            self.sm_status_card, text="Checking...",
            font=get_font(13, "bold"), text_color=theme["text_primary"]
        )
        self.sm_status_lbl.pack(padx=16, pady=(12, 4), anchor="w")

        self.sm_ssd_lbl = ctk.CTkLabel(
            self.sm_status_card, text="Detecting drive type...",
            font=get_font(12, "normal"), text_color=theme["text_secondary"]
        )
        self.sm_ssd_lbl.pack(padx=16, pady=(0, 12), anchor="w")

        # Result feedback label
        self.sm_result_lbl = ctk.CTkLabel(
            self.sysmain_frame, text="", font=get_font(13, "bold"), text_color=theme["accent_green"]
        )
        self.sm_result_lbl.pack(padx=15, pady=(4, 0), anchor="w")

        # Toggle Button
        self.sm_toggle_btn = ctk.CTkButton(
            self.sysmain_frame,
            text="Loading...",
            font=get_font(14, "bold"),
            fg_color="#334155" if is_cyber else "#555555",
            hover_color="#475569" if is_cyber else "#666666",
            text_color="#ffffff",
            height=44,
            corner_radius=22 if is_cyber else 8,
            state="disabled"
        )
        self.sm_toggle_btn.pack(fill="x", padx=15, pady=(10, 15))

    def show_sysmain(self):
        """Transition into the in-window SysMain Control panel."""
        self._switch_to_subview(self.sysmain_frame)
        self._sm_check_status()

    def _open_sysmain_dialog(self):
        """Opens SysMain tweaker in the same window (backward compatible entry point)."""
        self.show_sysmain()

    def _sm_check_status(self, sync: bool = False):
        """Check SysMain service status and drive type."""
        def _worker():
            sm_status = get_sysmain_status()
            has_ssd = check_has_ssd()
            try:
                self.after(0, self._sm_render_status, sm_status, has_ssd)
            except Exception:
                if sync:
                    self._sm_render_status(sm_status, has_ssd)

        if sync:
            _worker()
        else:
            threading.Thread(target=_worker, daemon=True).start()

    def _sm_render_status(self, sm_status: dict, has_ssd: bool):
        """Render SysMain status and update toggle button on the main thread."""
        try:
            if not self.winfo_exists():
                return
        except Exception:
            return

        theme = get_theme()
        is_cyber = is_cyber_mode()

        self._sm_state["running"] = sm_status.get("running")

        if sm_status.get("error"):
            self.sm_status_lbl.configure(text=f"Error: {sm_status['error']}", text_color="#ff4d4f")
            return

        running = sm_status.get("running", False)
        running_text = "RUNNING" if running else "STOPPED"
        start_text = sm_status.get("start_type", "unknown").upper()
        status_icon = "🟢" if running else "🔴"
        self.sm_status_lbl.configure(
            text=f"{status_icon}  SysMain is {running_text} (startup: {start_text})",
            text_color="#00ff9f" if running else "#ff4d4f"
        )

        ssd_icon = "💾 SSD detected" if has_ssd else "💽 HDD detected"
        rec = " — disabling SysMain recommended!" if has_ssd and running else ""
        self.sm_ssd_lbl.configure(
            text=f"{ssd_icon}{rec}",
            text_color=theme["accent_amber"] if (has_ssd and running) else theme["text_secondary"]
        )

        if running:
            self.sm_toggle_btn.configure(
                text="⚡ DISABLE SYSMAIN SERVICE" if is_cyber else "Disable SysMain",
                fg_color="#e11d48" if is_cyber else "#cc3333",
                hover_color="#f43f5e" if is_cyber else "#ff4444",
                text_color="#ffffff",
                state="normal",
                command=lambda: self._sm_toggle(False)
            )
        else:
            self.sm_toggle_btn.configure(
                text="⚡ ENABLE SYSMAIN SERVICE" if is_cyber else "Enable SysMain",
                fg_color=theme["action_btn_fg"],
                hover_color=theme["action_btn_hover"],
                text_color=theme["action_btn_text"],
                state="normal",
                command=lambda: self._sm_toggle(True)
            )

    def _sm_toggle(self, enable: bool):
        """Toggle SysMain service state asynchronously."""
        self.sm_toggle_btn.configure(state="disabled", text="Applying...")
        self.sm_result_lbl.configure(text="")

        def _worker():
            res = set_sysmain_enabled(enable)
            time.sleep(0.5)
            try:
                self.after(0, self._sm_on_toggle_done, res, enable)
            except Exception:
                try:
                    self._sm_on_toggle_done(res, enable)
                except Exception:
                    pass

        threading.Thread(target=_worker, daemon=True).start()

    def _sm_on_toggle_done(self, res: dict, enabled: bool):
        """Handle SysMain toggle completion and update status."""
        try:
            if not self.winfo_exists():
                return
        except Exception:
            return

        if res.get("success"):
            action = "enabled" if enabled else "disabled"
            self.sm_result_lbl.configure(
                text=f"SysMain {action} successfully!",
                text_color="#00ff00"
            )
        else:
            self.sm_result_lbl.configure(
                text=f"Failed: {res.get('error', 'Unknown error')}",
                text_color="#ff4d4f"
            )
        self._update_ram_label()
        self._init_sysmain_status()
        self._sm_check_status()


