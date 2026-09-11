# desktop-app/app/ui/history_view.py

"""
History View — Telemetry Archive & Live Gameplay FPS Boost Log.
Displays recorded gameplay sessions, FPS gains, 1% low frame pacing,
and memory optimization metrics. Supports Cyber Mode & Performance Mode.
"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional
import tkinter.messagebox as mb
from tkinter import filedialog

import customtkinter as ctk

from services.benchmark_logger import get_history_service
from ui.theme_manager import get_font, get_theme, is_cyber_mode


class HistoryView(ctk.CTkFrame):
    """Rich telemetry dashboard displaying historical gameplay FPS boost records."""

    def __init__(self, parent, **kwargs) -> None:
        theme = get_theme()
        super().__init__(parent, fg_color=theme["bg_main"], **kwargs)

        self.history_service = get_history_service()

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        # ── Header ───────────────────────────────────────────────
        self.header_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.header_frame.grid(row=0, column=0, sticky="ew", padx=20, pady=(15, 10))
        self.header_frame.grid_columnconfigure(0, weight=1)

        self.title_label = ctk.CTkLabel(
            self.header_frame,
            text="⚡ TELEMETRY ARCHIVE" if is_cyber_mode() else "Gameplay Telemetry & Logs",
            font=get_font(18, "bold"),
            text_color=theme["text_title"],
            anchor="w",
        )
        self.title_label.grid(row=0, column=0, sticky="w")

        self.subtitle_label = ctk.CTkLabel(
            self.header_frame,
            text="// Session benchmarks, frametime stability gains, and memory purge records" if is_cyber_mode()
            else "Session benchmarks, frametime stability gains, and memory purge records.",
            font=get_font(12, "normal"),
            text_color=theme["text_secondary"],
            anchor="w",
        )
        self.subtitle_label.grid(row=1, column=0, sticky="w", pady=(2, 0))

        # Sentinel Active Logging Indicator
        self.sentinel_pill_frame = ctk.CTkFrame(self.header_frame, fg_color="transparent")
        self.sentinel_pill_frame.grid(row=2, column=0, columnspan=2, sticky="w", pady=(6, 0))

        is_sentinel_on = self.history_service.is_sentinel_running()
        self.sentinel_status_badge = ctk.CTkLabel(
            self.sentinel_pill_frame,
            text="● SENTINEL ACTIVE // TELEMETRY LOGGING ENGAGED" if is_sentinel_on
            else "○ SENTINEL IDLE // LOGGING PAUSED (ACTIVATE IN GAME BOOSTER)",
            font=get_font(10, "bold"),
            fg_color="#064e3b" if is_sentinel_on else "#1f2937",
            text_color="#00ff9f" if is_sentinel_on else "#9ca3af",
            corner_radius=6,
            padx=10,
            pady=3,
        )
        self.sentinel_status_badge.pack(side="left")

        # ── Actions Bar ──────────────────────────────────────────
        self.actions_frame = ctk.CTkFrame(self.header_frame, fg_color="transparent")
        self.actions_frame.grid(row=0, column=1, rowspan=2, sticky="e")

        self.demo_btn = ctk.CTkButton(
            self.actions_frame,
            text="⚡ + SAMPLE" if is_cyber_mode() else "+ Sample",
            font=get_font(11, "bold"),
            fg_color=theme["action_btn_fg"],
            hover_color=theme["action_btn_hover"],
            text_color=theme["action_btn_text"],
            height=30,
            width=88,
            corner_radius=15 if is_cyber_mode() else 6,
            command=self._on_record_demo,
        )
        self.demo_btn.pack(side="left", padx=(0, 6))

        self.export_btn = ctk.CTkButton(
            self.actions_frame,
            text="💾 EXPORT" if is_cyber_mode() else "Export",
            font=get_font(11, "bold"),
            fg_color="#1e293b" if is_cyber_mode() else "#2b2b2b",
            hover_color="#334155" if is_cyber_mode() else "#3b3b3b",
            text_color="#f0f4ff" if is_cyber_mode() else "#ffffff",
            height=30,
            width=78,
            corner_radius=15 if is_cyber_mode() else 6,
            command=self._on_export_csv,
        )
        self.export_btn.pack(side="left", padx=(0, 6))

        self.clear_btn = ctk.CTkButton(
            self.actions_frame,
            text="🗑 CLEAR" if is_cyber_mode() else "Clear",
            font=get_font(11, "bold"),
            fg_color="#450a0a" if is_cyber_mode() else "#331111",
            hover_color="#7f1d1d" if is_cyber_mode() else "#551111",
            text_color="#fca5a5",
            height=30,
            width=65,
            corner_radius=15 if is_cyber_mode() else 6,
            command=self._on_clear_history,
        )
        self.clear_btn.pack(side="left")

        # ── KPI Summary Cards Grid ───────────────────────────────
        self.kpi_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.kpi_frame.grid(row=1, column=0, sticky="ew", padx=20, pady=(0, 10))
        for col in range(4):
            self.kpi_frame.grid_columnconfigure(col, weight=1)

        self._kpi_cards = {}
        self._build_kpi_cards()

        # ── Sessions Feed Frame ──────────────────────────────────
        self.feed_container = ctk.CTkScrollableFrame(
            self,
            fg_color=theme["bg_card"],
            corner_radius=12 if is_cyber_mode() else 8,
            border_width=1 if is_cyber_mode() else 0,
            border_color=theme.get("border_card", "#1e1e1e"),
        )
        self.feed_container.grid(row=2, column=0, sticky="nsew", padx=20, pady=(0, 15))
        self.feed_container.grid_columnconfigure(0, weight=1)

        self.refresh()

    def _build_kpi_cards(self) -> None:
        theme = get_theme()
        is_cyber = is_cyber_mode()

        kpi_defs = [
            ("sessions", "TOTAL SESSIONS", "0", theme["text_primary"]),
            ("avg_boost", "AVG FPS GAIN", "+0.0%", "#00ff9f" if is_cyber else "#00ff00"),
            ("low_1pct", "1% LOW STABILITY", "--", "#38bdf8" if is_cyber else "#4fc3f7"),
            ("ram_freed", "TOTAL RAM FREED", "0 MB", "#c084fc" if is_cyber else "#d1c4e9"),
        ]

        for col, (key, label_text, default_val, text_col) in enumerate(kpi_defs):
            card = ctk.CTkFrame(
                self.kpi_frame,
                fg_color=theme["bg_card"],
                corner_radius=10 if is_cyber else 6,
                border_width=1 if is_cyber else 0,
                border_color=theme.get("border_card", "#1e1e1e"),
            )
            card.grid(row=0, column=col, padx=(0 if col == 0 else 6, 0 if col == 3 else 6), sticky="nsew")
            card.grid_columnconfigure(0, weight=1)

            lbl = ctk.CTkLabel(
                card,
                text=label_text,
                font=get_font(10, "bold"),
                text_color=theme["text_secondary"],
            )
            lbl.grid(row=0, column=0, padx=12, pady=(10, 2), sticky="w")

            val = ctk.CTkLabel(
                card,
                text=default_val,
                font=get_font(18, "bold", is_stat=True),
                text_color=text_col,
            )
            val.grid(row=1, column=0, padx=12, pady=(0, 10), sticky="w")

            self._kpi_cards[key] = {"card": card, "label": lbl, "val": val}

    def refresh(self) -> None:
        """Reload all metrics and session cards from history."""
        if not self.winfo_exists():
            return

        theme = get_theme()
        is_cyber = is_cyber_mode()
        metrics = self.history_service.get_summary_metrics()
        sessions = self.history_service.get_all_sessions()

        # Update KPI cards
        self._kpi_cards["sessions"]["val"].configure(text=f"{metrics['total_sessions']}")
        boost_str = f"+{metrics['avg_boost_pct']}%" if metrics['avg_boost_pct'] > 0 else "--"
        if metrics['avg_boost_fps'] > 0:
            boost_str += f" (+{metrics['avg_boost_fps']:.0f} FPS)"
        self._kpi_cards["avg_boost"]["val"].configure(text=boost_str)

        low_str = f"{metrics['avg_1pct_low']:.0f} FPS Avg" if metrics['avg_1pct_low'] > 0 else "--"
        self._kpi_cards["low_1pct"]["val"].configure(text=low_str)

        ram_freed_val = metrics["total_ram_freed_mb"]
        if ram_freed_val >= 1024:
            ram_str = f"{ram_freed_val / 1024.0:.1f} GB"
        else:
            ram_str = f"{ram_freed_val:,.0f} MB"
        self._kpi_cards["ram_freed"]["val"].configure(text=ram_str)

        # Update Sentinel Live Status badge
        is_sentinel_on = self.history_service.is_sentinel_running()
        if is_sentinel_on:
            self.sentinel_status_badge.configure(
                text="● SENTINEL ACTIVE // TELEMETRY LOGGING ENGAGED" if is_cyber
                else "● Sentinel Active — Logging Live Gameplay Telemetry",
                fg_color="#064e3b" if is_cyber else "#14532d",
                text_color="#00ff9f" if is_cyber else "#22c55e",
            )
        else:
            self.sentinel_status_badge.configure(
                text="○ SENTINEL INACTIVE // LOGGING PAUSED (ACTIVATE IN GAME BOOSTER)" if is_cyber
                else "○ Sentinel Inactive — Logging Paused (Activate in Game Booster)",
                fg_color="#1e293b" if is_cyber else "#262626",
                text_color="#94a3b8" if is_cyber else "#888888",
            )

        # Clear feed container
        for widget in self.feed_container.winfo_children():
            widget.destroy()

        if not sessions:
            self._render_empty_state()
            return

        # Render each session card
        for idx, s in enumerate(sessions):
            try:
                self._render_session_card(idx, s)
            except Exception:
                pass

    def _render_empty_state(self) -> None:
        theme = get_theme()
        is_cyber = is_cyber_mode()

        frame = ctk.CTkFrame(self.feed_container, fg_color="transparent")
        frame.pack(fill="both", expand=True, padx=20, pady=40)

        icon_lbl = ctk.CTkLabel(
            frame,
            text="🎮 📈",
            font=ctk.CTkFont(size=36),
        )
        icon_lbl.pack(pady=(10, 8))

        heading = ctk.CTkLabel(
            frame,
            text="NO GAMEPLAY SESSIONS RECORDED YET" if is_cyber else "No Gameplay Sessions Logged",
            font=get_font(16, "bold"),
            text_color=theme["text_title"],
        )
        heading.pack(pady=(0, 6))

        info_text = (
            "Sessions & FPS gains are recorded ONLY when the AI Sentinel is actively running.\n"
            "Activate the Sentinel in [02] GAME BOOSTER before playing, and your baseline FPS,\n"
            "boosted framerates, 1% low stability, and memory purges will be logged automatically.\n\n"
            "Click below to generate a sample session and preview the telemetry dashboard."
        )
        info_lbl = ctk.CTkLabel(
            frame,
            text=info_text,
            font=get_font(12, "normal"),
            text_color=theme["text_secondary"],
            justify="center",
        )
        info_lbl.pack(pady=(0, 16))

        action_btn = ctk.CTkButton(
            frame,
            text="⚡ RECORD SAMPLE VALORANT SESSION" if is_cyber else "Record Sample Benchmark Session",
            font=get_font(12, "bold"),
            fg_color=theme["action_btn_fg"],
            hover_color=theme["action_btn_hover"],
            text_color=theme["action_btn_text"],
            height=36,
            corner_radius=18 if is_cyber else 8,
            command=self._on_record_demo,
        )
        action_btn.pack()

    def _render_session_card(self, idx: int, session: Dict[str, Any]) -> None:
        theme = get_theme()
        is_cyber = is_cyber_mode()

        card = ctk.CTkFrame(
            self.feed_container,
            fg_color=theme.get("bg_card_inner", "#0f172a") if is_cyber else "#171717",
            corner_radius=10 if is_cyber else 6,
            border_width=1 if is_cyber else 0,
            border_color="#1a2b5e" if is_cyber else "#262626",
        )
        card.pack(fill="x", padx=10, pady=(0, 10))
        card.grid_columnconfigure(0, weight=1)

        # Row 1: Game Title, Date, Duration
        header_row = ctk.CTkFrame(card, fg_color="transparent")
        header_row.pack(fill="x", padx=14, pady=(12, 6))
        header_row.grid_columnconfigure(0, weight=1)

        game_title = f"🎮 {session.get('game_name', 'Unknown Game')}"
        title_lbl = ctk.CTkLabel(
            header_row,
            text=game_title,
            font=get_font(15, "bold"),
            text_color="#00f0ff" if is_cyber else theme["text_title"],
        )
        title_lbl.grid(row=0, column=0, sticky="w")

        duration_min = float(session.get("duration_minutes") or 0.0)
        time_str = f"{session.get('start_time', '')}  ·  ⏱ {duration_min:.1f} mins"
        time_lbl = ctk.CTkLabel(
            header_row,
            text=time_str,
            font=get_font(11, "normal"),
            text_color=theme["text_secondary"],
        )
        time_lbl.grid(row=0, column=1, sticky="e")

        # Row 2: FPS Metrics & Comparison Badge
        stats_row = ctk.CTkFrame(card, fg_color="transparent")
        stats_row.pack(fill="x", padx=14, pady=(0, 8))
        stats_row.grid_columnconfigure(1, weight=1)

        baseline = float(session.get("baseline_fps") or 0.0)
        boosted = float(session.get("avg_fps") or 0.0)
        gain_fps = float(session.get("fps_gain") or 0.0)
        gain_pct = float(session.get("fps_gain_pct") or 0.0)
        low_1pct = float(session.get("low_1pct_fps") or 0.0)
        peak_fps = float(session.get("peak_fps") or 0.0)
        ram_freed = float(session.get("ram_freed_mb") or 0.0)

        fps_comp_text = f"Baseline: {baseline:.0f} FPS  ➜  Boosted: {boosted:.0f} FPS"
        fps_comp_lbl = ctk.CTkLabel(
            stats_row,
            text=fps_comp_text,
            font=get_font(13, "bold"),
            text_color=theme["text_primary"],
        )
        fps_comp_lbl.grid(row=0, column=0, sticky="w")

        # Gain badge
        gain_badge = ctk.CTkLabel(
            stats_row,
            text=f"  +{gain_fps:.0f} FPS (+{gain_pct:.1f}%)  ",
            font=get_font(12, "bold", is_stat=True),
            fg_color="#064e3b" if is_cyber else "#14532d",
            text_color="#00ff9f" if is_cyber else "#22c55e",
            corner_radius=6,
        )
        gain_badge.grid(row=0, column=1, sticky="e")

        # Row 3: Secondary Metrics (1% Low, Peak, RAM Freed, Stability)
        sub_row = ctk.CTkFrame(card, fg_color="transparent")
        sub_row.pack(fill="x", padx=14, pady=(0, 8))
        sub_row.grid_columnconfigure((0, 1, 2, 3), weight=1)

        sub_stats = [
            f"🎯 1% Low: {low_1pct:.0f} FPS",
            f"⚡ Peak: {peak_fps:.0f} FPS",
            f"🛡️ Pacing: {session.get('stability_score', '95%')}",
            f"💾 Purged: {ram_freed:,.0f} MB",
        ]
        for c_idx, sub_text in enumerate(sub_stats):
            ctk.CTkLabel(
                sub_row,
                text=sub_text,
                font=get_font(11, "normal"),
                text_color=theme["text_secondary"],
                anchor="w",
            ).grid(row=0, column=c_idx, sticky="w", padx=(0, 6))

        # Row 4: Action Tags
        actions = session.get("actions_taken", [])
        if actions:
            tags_row = ctk.CTkFrame(card, fg_color="transparent")
            tags_row.pack(fill="x", padx=14, pady=(0, 10))
            for action in actions[:3]:
                tag = ctk.CTkLabel(
                    tags_row,
                    text=f"✔ {action}",
                    font=get_font(10, "normal"),
                    fg_color="#1e293b" if is_cyber else "#262626",
                    text_color="#94a3b8" if is_cyber else "#a3a3a3",
                    corner_radius=4,
                )
                tag.pack(side="left", padx=(0, 6))

    def _on_record_demo(self) -> None:
        """Inject a demo benchmark record for immediate verification."""
        self.history_service.create_demo_session(
            game_name="VALORANT",
            executable="VALORANT-Win64-Shipping.exe",
            baseline_fps=142.0,
            boost_fps=171.0,
        )
        self.refresh()

    def _on_clear_history(self) -> None:
        """Prompt to clear all history."""
        if mb.askyesno("Clear History", "Are you sure you want to clear all recorded gameplay sessions?"):
            self.history_service.clear_history()
            self.refresh()

    def _on_export_csv(self) -> None:
        """Export history to user-selected CSV file."""
        path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV Files", "*.csv"), ("All Files", "*.*")],
            initialfile="fps_boost_history.csv",
        )
        if path:
            ok = self.history_service.export_csv(path)
            if ok:
                mb.showinfo("Export Successful", f"Gameplay telemetry exported successfully to:\n{path}")
            else:
                mb.showerror("Export Failed", "Failed to export session history.")

    def apply_theme(self, is_cyber: bool) -> None:
        """Re-style the history dashboard dynamically when theme changes."""
        theme = get_theme()
        self.configure(fg_color=theme["bg_main"])
        self.feed_container.configure(
            fg_color=theme["bg_card"],
            border_color=theme.get("border_card", "#1e1e1e"),
            border_width=1 if is_cyber else 0,
        )
        self.title_label.configure(
            text="⚡ TELEMETRY ARCHIVE" if is_cyber else "Gameplay Telemetry & Logs",
            font=get_font(18, "bold"),
            text_color=theme["text_title"],
        )
        self.subtitle_label.configure(
            text="// Session benchmarks, frametime stability gains, and memory purge records" if is_cyber
            else "Session benchmarks, frametime stability gains, and memory purge records.",
            font=get_font(12, "normal"),
            text_color=theme["text_secondary"],
        )
        self.demo_btn.configure(
            text="⚡ + SAMPLE" if is_cyber else "+ Sample",
            font=get_font(11, "bold"),
            fg_color=theme["action_btn_fg"],
            hover_color=theme["action_btn_hover"],
            text_color=theme["action_btn_text"],
            corner_radius=15 if is_cyber else 6,
        )
        self.export_btn.configure(
            text="💾 EXPORT" if is_cyber else "Export",
            font=get_font(11, "bold"),
            corner_radius=15 if is_cyber else 6,
        )
        self.clear_btn.configure(
            text="🗑 CLEAR" if is_cyber else "Clear",
            font=get_font(11, "bold"),
            corner_radius=15 if is_cyber else 6,
        )

        for col_data in self._kpi_cards.values():
            col_data["card"].configure(
                fg_color=theme["bg_card"],
                border_color=theme.get("border_card", "#1e1e1e"),
                border_width=1 if is_cyber else 0,
            )
            col_data["label"].configure(text_color=theme["text_secondary"])

        self.refresh()
