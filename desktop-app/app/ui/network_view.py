import customtkinter as ctk
import threading
from typing import Optional, Callable

from optimize.optimizer_service import (
    stabilize_network,
    get_network_status,
    flush_dns_cache,
    optimize_dns_servers,
    disable_network_power_saving,
    disable_network_throttling,
    optimize_tcp_settings,
    reset_network_stack,
)
from ui.theme_manager import is_cyber_mode, get_theme, get_font, PERFORMANCE_THEME, CYBER_THEME


class NetworkView(ctk.CTkFrame):
    """
    Dedicated in-window Network Stabilization view.
    Provides live latency ping monitoring, adapter telemetry, and 6 one-click tuning operations.
    """
    def __init__(self, parent, on_back: Optional[Callable] = None, **kwargs):
        theme = get_theme()
        is_cyber = is_cyber_mode()
        super().__init__(parent, fg_color=theme["bg_main"], **kwargs)

        self.on_back = on_back
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        # ── Top Bar ─────────────────────────────────────────────
        self.top_bar = ctk.CTkFrame(self, fg_color="transparent")
        self.top_bar.grid(row=0, column=0, padx=20, pady=(15, 6), sticky="ew")
        self.top_bar.grid_columnconfigure(1, weight=1)

        if self.on_back:
            self.back_btn = ctk.CTkButton(
                self.top_bar,
                text="◄ BACK TO GAME BOOSTER" if is_cyber else "◄ Back to Game Booster",
                font=get_font(12, "bold"),
                fg_color="#1e293b" if is_cyber else "#333333",
                hover_color="#334155" if is_cyber else "#444444",
                text_color="#00f0ff" if is_cyber else "#ffffff",
                width=190,
                height=34,
                corner_radius=17 if is_cyber else 8,
                command=self.on_back
            )
            self.back_btn.grid(row=0, column=0, rowspan=2, padx=(0, 14), sticky="w")

        title_col = 1 if self.on_back else 0
        self.title_lbl = ctk.CTkLabel(
            self.top_bar,
            text="🌐 NETWORK STABILIZATION CENTER" if is_cyber else "🌐 Network Stabilizer",
            font=get_font(20, "bold"),
            text_color="#00f0ff" if is_cyber else theme["text_title"],
            anchor="w"
        )
        self.title_lbl.grid(row=0, column=title_col, sticky="w")

        self.subtitle_lbl = ctk.CTkLabel(
            self.top_bar,
            text="// Low-latency TCP/IP tuning, adapter power optimization, and DNS calibration" if is_cyber else "Optimize your network stack for minimum latency gaming.",
            font=get_font(11, "normal"),
            text_color=theme["text_secondary"],
            anchor="w"
        )
        self.subtitle_lbl.grid(row=1, column=title_col, sticky="w", pady=(2, 0))

        self.probe_btn = ctk.CTkButton(
            self.top_bar,
            text="⚡ RE-PROBE" if is_cyber else "Re-probe",
            font=get_font(12, "bold"),
            fg_color="#1e293b" if is_cyber else "#333333",
            hover_color="#334155" if is_cyber else "#444444",
            text_color="#00f0ff" if is_cyber else theme["nav_btn_text"],
            width=100,
            height=32,
            corner_radius=16 if is_cyber else 6,
            command=self._probe_status
        )
        self.probe_btn.grid(row=0, column=title_col + 1, rowspan=2, sticky="e")

        # ── Live Status Banner ──────────────────────────────────
        self.status_card = ctk.CTkFrame(
            self,
            fg_color=theme["bg_card"],
            corner_radius=12,
            border_width=1,
            border_color=theme.get("border_glow", "#1e1e1e") if is_cyber else "#1e1e1e"
        )
        self.status_card.grid(row=1, column=0, padx=20, pady=(6, 6), sticky="ew")
        self.status_card.grid_columnconfigure((0, 1, 2), weight=1)

        self.adapter_lbl = ctk.CTkLabel(
            self.status_card, text="Adapter: Checking...",
            font=get_font(11, "bold"), text_color=theme["text_secondary"]
        )
        self.adapter_lbl.grid(row=0, column=0, padx=14, pady=10, sticky="w")

        self.latency_lbl = ctk.CTkLabel(
            self.status_card, text="Latency: --",
            font=get_font(11, "bold"), text_color=theme["text_secondary"]
        )
        self.latency_lbl.grid(row=0, column=1, padx=14, pady=10)

        self.dns_lbl = ctk.CTkLabel(
            self.status_card, text="DNS: --",
            font=get_font(11, "bold"), text_color=theme["text_secondary"]
        )
        self.dns_lbl.grid(row=0, column=2, padx=14, pady=10, sticky="e")

        # ── Middle Scrollable Action Container ──────────────────
        self.action_container = ctk.CTkFrame(self, fg_color="transparent")
        self.action_container.grid(row=2, column=0, padx=20, pady=(2, 10), sticky="nsew")
        self.action_container.grid_columnconfigure(0, weight=1)
        self.action_container.grid_rowconfigure(1, weight=1)

        self.result_lbl = ctk.CTkLabel(
            self.action_container, text="", font=get_font(12, "bold"),
            text_color=theme.get("accent_green", "#00ff00")
        )
        self.result_lbl.grid(row=0, column=0, padx=4, pady=(2, 4), sticky="w")

        self.actions_scroll = ctk.CTkScrollableFrame(
            self.action_container,
            fg_color=theme["bg_card"],
            corner_radius=12,
            border_width=1,
            border_color=theme.get("border_card", "#1e1e1e")
        )
        self.actions_scroll.grid(row=1, column=0, sticky="nsew")
        self.actions_scroll.grid_columnconfigure(0, weight=1)

        self._action_buttons = []
        self._build_action_rows(theme, is_cyber)
        self._probe_status()

    def _build_action_rows(self, theme: dict, is_cyber: bool):
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
            self._action_buttons.append(btn)
            return btn

        self.btn1 = _make_row(
            self.actions_scroll, 0, "🧹", "Flush DNS Cache",
            "Clear stale DNS entries for fresh game server lookups.",
            "Flush",
            lambda: self._run_action(self.btn1, flush_dns_cache, "DNS cache flushed", "DNS flush failed")
        )

        self.btn2 = _make_row(
            self.actions_scroll, 1, "🚀", "Optimize DNS Servers",
            "Set Cloudflare (1.1.1.1) + Google (8.8.8.8) for fastest lookups.",
            "Optimize",
            lambda: self._run_action(self.btn2, optimize_dns_servers, "DNS servers optimized", "DNS change failed")
        )

        self.btn3 = _make_row(
            self.actions_scroll, 2, "⚡", "Disable Network Throttling",
            "Remove Windows throughput limiter that causes lag spikes.",
            "Disable",
            lambda: self._run_action(self.btn3, disable_network_throttling, "Network throttling disabled", "Throttling fix failed")
        )

        self.btn4 = _make_row(
            self.actions_scroll, 3, "📶", "Disable Adapter Power Saving",
            "Prevent NIC sleep mode that causes periodic latency spikes.",
            "Disable",
            lambda: self._run_action(self.btn4, disable_network_power_saving, "Adapter power saving disabled", "Power config failed")
        )

        self.btn5 = _make_row(
            self.actions_scroll, 4, "🔧", "Optimize TCP/IP Stack",
            "Tune auto-tuning, DCA, and congestion provider for gaming.",
            "Tune",
            lambda: self._run_action(self.btn5, optimize_tcp_settings, "TCP stack optimized", "TCP tuning failed")
        )

        self.btn6 = _make_row(
            self.actions_scroll, 5, "⚠️", "Reset Network Stack (Reboot)",
            "Nuclear reset: Winsock + TCP/IP. Fixes deep corruption. Needs reboot.",
            "Reset",
            lambda: self._run_action(self.btn6, reset_network_stack, "Network stack reset (reboot required)", "Stack reset failed")
        )
        self.btn6.configure(
            fg_color="#e11d48" if is_cyber else "#8b1515",
            hover_color="#f43f5e" if is_cyber else "#aa1818",
            text_color="#ffffff"
        )

    def _run_action(self, btn, action_fn, success_msg, fail_msg):
        theme = get_theme()
        orig_text = btn.cget("text")
        btn.configure(state="disabled", text="...")
        self.result_lbl.configure(text="")

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
                self.result_lbl.configure(text=f"✅  {success_msg}", text_color=theme.get("accent_green", "#00ff00"))
            else:
                err = res.get("error", "Unknown error")
                self.result_lbl.configure(text=f"❌  {fail_msg}: {err}", text_color="#f43f5e")
            self._probe_status()

        threading.Thread(target=_worker, daemon=True).start()

    def _probe_status(self, sync: bool = False):
        def _worker():
            info = get_network_status()
            try:
                self.after(0, self._render_status, info)
            except Exception:
                if sync:
                    self._render_status(info)

        if sync:
            _worker()
        else:
            threading.Thread(target=_worker, daemon=True).start()

    def _render_status(self, info: dict):
        try:
            if not self.winfo_exists():
                return

            theme = get_theme()

            if info.get("connected"):
                self.adapter_lbl.configure(
                    text=f"🟢  {info.get('adapter', '?')} ({info.get('link_speed', '?')})",
                    text_color=theme.get("accent_green", "#00ff00")
                )
            else:
                self.adapter_lbl.configure(text="🔴  Disconnected", text_color="#f43f5e")

            lat = info.get("latency_ms", -1)
            if lat >= 0:
                lat_color = theme.get("accent_green", "#00ff00") if lat < 50 else ("#fbbf24" if lat < 100 else "#f43f5e")
                self.latency_lbl.configure(text=f"Ping: {lat}ms", text_color=lat_color)
            else:
                self.latency_lbl.configure(text="Ping: --", text_color=theme["text_secondary"])

            dns_list = info.get("dns", [])
            if dns_list:
                self.dns_lbl.configure(text=f"DNS: {', '.join(dns_list[:2])}", text_color=theme["text_primary"])
            else:
                self.dns_lbl.configure(text="DNS: Auto", text_color=theme["text_secondary"])
        except Exception:
            pass

    def apply_theme(self, is_cyber: bool):
        theme = CYBER_THEME if is_cyber else PERFORMANCE_THEME
        self.configure(fg_color=theme["bg_main"])
        if hasattr(self, "back_btn"):
            self.back_btn.configure(
                text="◄ BACK TO GAME BOOSTER" if is_cyber else "◄ Back to Game Booster",
                fg_color="#1e293b" if is_cyber else "#333333",
                hover_color="#334155" if is_cyber else "#444444",
                text_color="#00f0ff" if is_cyber else "#ffffff",
                corner_radius=17 if is_cyber else 8
            )
        self.title_lbl.configure(
            text="🌐 NETWORK STABILIZATION CENTER" if is_cyber else "🌐 Network Stabilizer",
            text_color="#00f0ff" if is_cyber else theme["text_title"]
        )
        self.probe_btn.configure(
            text="⚡ RE-PROBE" if is_cyber else "Re-probe",
            fg_color="#1e293b" if is_cyber else "#333333",
            hover_color="#334155" if is_cyber else "#444444",
            text_color="#00f0ff" if is_cyber else theme["nav_btn_text"],
            corner_radius=16 if is_cyber else 6
        )
        self.status_card.configure(
            fg_color=theme["bg_card"],
            border_color=theme.get("border_glow", "#1e1e1e") if is_cyber else "#1e1e1e"
        )
        self.actions_scroll.configure(
            fg_color=theme["bg_card"],
            border_color=theme.get("border_card", "#1e1e1e")
        )
