from ui.safe_view import SafeViewMixin
"""
Network Stabilization View for FPS Optimizer.
Consolidated 6-tab interface utilizing the NetworkStabilizerFeature engine:
1. Overview (Snapshot status, system metrics, Network vs Render Stutter guide)
2. Diagnostics (Multi-target ping probes, latency trajectory canvas, bufferbloat test)
3. Windows Tweaks (Safe, reversible DNS, stack reset, NIC power, power plan, GameDVR)
4. Router QoS/SQM (Bandwidth limit calculator, OpenWrt CAKE snippet generator, stock router guides)
5. Game Profiles (In-game HUD telemetry activation, anti-stutter settings, notes journal)
6. Rollback (Targeted single-click 'Restore previous state', audit timeline, drift checker)
"""

import re
import time
import math
import tkinter as tk
import threading
import customtkinter as ctk
from typing import Optional, Callable, Dict, Any, List

from ui.theme_manager import is_cyber_mode, get_theme, get_font, on_theme_changed, remove_theme_listener
from network_stabilizer import (
    NetworkStabilizerFeature,
    DiagnosticsEngine,
    SnapshotManager,
    TweaksEngine,
    GameProfileManager,
    RouterAdvisor,
)
from network_stabilizer.constants import (
    DNS_PRESETS,
    BUFFERBLOAT_GRADES,
    STUTTER_TYPES,
    FEATURE_NAME,
    FEATURE_VERSION,
    TERM_RESTORE_RESULT,
)


# ── UI Helper Components ───────────────────────────────────────────────

class SectionHeader(ctk.CTkFrame):
    def __init__(self, parent, title: str, subtitle: Optional[str] = None, **kwargs):
        theme = get_theme()
        super().__init__(parent, fg_color="transparent", **kwargs)
        is_cyber = is_cyber_mode()

        ctk.CTkLabel(
            self,
            text=f"// {title.upper()}" if is_cyber else title,
            font=get_font(15, "bold"),
            text_color="#00f0ff" if is_cyber else theme["text_title"],
            anchor="w"
        ).pack(anchor="w", fill="x")

        if subtitle:
            ctk.CTkLabel(
                self,
                text=subtitle,
                font=get_font(11, "normal"),
                text_color=theme["text_secondary"],
                anchor="w"
            ).pack(anchor="w", fill="x", pady=(2, 0))


class StatCard(ctk.CTkFrame):
    def __init__(self, parent, icon: str, title: str, value: str = "--", subtext: str = "", **kwargs):
        theme = get_theme()
        is_cyber = is_cyber_mode()
        super().__init__(
            parent,
            fg_color=theme["bg_card"],
            corner_radius=12,
            border_width=1,
            border_color=theme.get("border_card", "#1e1e1e"),
            **kwargs
        )
        self.grid_columnconfigure(0, weight=1)

        h_frame = ctk.CTkFrame(self, fg_color="transparent")
        h_frame.pack(fill="x", padx=12, pady=(10, 2))

        ctk.CTkLabel(h_frame, text=f"{icon}  {title}", font=get_font(11, "bold"), text_color=theme["text_secondary"]).pack(anchor="w")

        self.val_lbl = ctk.CTkLabel(self, text=value, font=get_font(17, "bold"), text_color="#00f0ff" if is_cyber else theme["text_primary"])
        self.val_lbl.pack(anchor="w", padx=12, pady=(0, 2))

        self.sub_lbl = ctk.CTkLabel(self, text=subtext, font=get_font(10, "normal"), text_color=theme["text_muted"])
        self.sub_lbl.pack(anchor="w", padx=12, pady=(0, 8))

    def update_val(self, val: str, subtext: Optional[str] = None, color: Optional[str] = None):
        try:
            if getattr(self, "_is_destroyed", False) or getattr(self.val_lbl, "_is_destroyed", False):
                return
            if not self.winfo_exists() or not self.val_lbl.winfo_exists():
                return
            self.val_lbl.configure(text=val)
            if color:
                self.val_lbl.configure(text_color=color)
            if subtext is not None:
                self.sub_lbl.configure(text=subtext)
        except Exception:
            pass


class LatencyGraphCanvas(ctk.CTkFrame):
    def __init__(self, parent, width: int = 500, height: int = 130, max_points: int = 40, **kwargs):
        super().__init__(parent, fg_color="transparent", **kwargs)
        self.max_points = max_points
        self.data_points: List[float] = []

        self.canvas = tk.Canvas(
            self,
            width=width,
            height=height,
            bg="#060919" if is_cyber_mode() else "#0a0a0a",
            highlightthickness=1,
            highlightbackground="#1a2b5e" if is_cyber_mode() else "#1e1e1e"
        )
        self.canvas.pack(fill="both", expand=True)
        
        self._resize_job = None
        self._resize_guard = False
        self._last_size = None
        
        def _on_canvas_configure(e):
            if getattr(self, "_resize_guard", False):
                return
            size = (e.width, e.height)
            if getattr(self, "_last_size", None) == size:
                return
            self._last_size = size
            if getattr(self, "_resize_job", None) is not None:
                try:
                    self.after_cancel(self._resize_job)
                except Exception:
                    pass
            self._resize_job = self.after_idle(_apply_resize)
            
        def _apply_resize():
            self._resize_job = None
            if getattr(self, "_resize_guard", False) or not self.winfo_exists():
                return
            self._resize_guard = True
            try:
                self.redraw()
            finally:
                self._resize_guard = False
                
        self.bind("<Configure>", _on_canvas_configure)
        self._draw_empty()

    def add_point(self, val: float):
        self.data_points.append(val)
        if len(self.data_points) > self.max_points:
            self.data_points.pop(0)
        self.redraw()

    def _draw_empty(self):
        self.canvas.delete("all")
        w = self.canvas.winfo_width() or 400
        h = self.canvas.winfo_height() or 120
        self.canvas.create_text(
            w / 2, h / 2,
            text="// Awaiting real-time ping telemetry..." if is_cyber_mode() else "Awaiting ping data...",
            fill="#47567d" if is_cyber_mode() else "#555555",
            font=("Segoe UI", 10, "italic")
        )

    def destroy(self):
        if getattr(self, "_resize_job", None) is not None:
            try:
                self.after_cancel(self._resize_job)
            except Exception:
                pass
        super().destroy()

    def redraw(self):
        if not self.data_points:
            self._draw_empty()
            return
        w = self.canvas.winfo_width()
        h = self.canvas.winfo_height()
        if w < 20 or h < 20:
            return

        self.canvas.delete("all")
        is_cyber = is_cyber_mode()

        for y_pct in (0.25, 0.5, 0.75):
            y = h * y_pct
            self.canvas.create_line(0, y, w, y, fill="#0e183a" if is_cyber else "#141414", dash=(2, 4))

        min_val = min(self.data_points)
        max_val = max(self.data_points)
        span = max(10.0, max_val - min_val)
        y_bottom = h - 20
        y_top = 20

        pts = []
        step_x = (w - 30) / max(1, self.max_points - 1)
        for i, val in enumerate(self.data_points):
            x = 15 + i * step_x
            norm = (val - min_val) / span
            y = y_bottom - (norm * (y_bottom - y_top))
            pts.append((x, y))

        line_color = "#00f0ff" if is_cyber else "#00ff00"
        glow_color = "#0d3b66" if is_cyber else "#003300"

        if len(pts) > 1:
            poly_coords = [pts[0][0], y_bottom]
            for px, py in pts:
                poly_coords.extend([px, py])
            poly_coords.extend([pts[-1][0], y_bottom])
            self.canvas.create_polygon(poly_coords, fill=glow_color, outline="")

            flat_pts = [c for pt in pts for c in pt]
            self.canvas.create_line(flat_pts, fill=line_color, width=2, smooth=True)

            last_x, last_y = pts[-1]
            self.canvas.create_oval(last_x - 4, last_y - 4, last_x + 4, last_y + 4, fill="#ffffff", outline=line_color, width=2)

        latest = self.data_points[-1]
        self.canvas.create_text(
            w - 12, 14, anchor="e",
            text=f"Live: {latest:.1f}ms | Min: {min_val:.1f}ms | Max: {max_val:.1f}ms",
            fill="#8193b8" if is_cyber else "#888888", font=("Segoe UI", 9, "bold")
        )


# ── Main 6-Tab View ───────────────────────────────────────────────────

class NetworkView(SafeViewMixin, ctk.CTkFrame):
    """
    Dedicated in-window Network Stabilization view.
    Exposes all 6 modules: Overview, Diagnostics, Windows Tweaks,
    Router QoS/SQM, Game Profiles, and Rollback.
    """
    def __init__(self, parent, on_back: Optional[Callable] = None, **kwargs):
        theme = get_theme()
        is_cyber = is_cyber_mode()
        super().__init__(parent, fg_color=theme["bg_main"], **kwargs)

        self.on_back = on_back
        self._is_destroyed = False
        self.feature = NetworkStabilizerFeature(app_context=self)
        self._is_live_monitoring = False

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # ── Navigation Bar ─────────────────────────────────────────────
        self.nav_bar = ctk.CTkFrame(self, fg_color="transparent")
        self.nav_bar.grid(row=0, column=0, padx=16, pady=(10, 4), sticky="ew")
        self.nav_bar.grid_columnconfigure(1, weight=1)

        if self.on_back:
            self.back_btn = ctk.CTkButton(
                self.nav_bar,
                text="◄ BACK" if is_cyber else "◄ Back",
                font=get_font(11, "bold"),
                width=85, height=32,
                fg_color="#1e293b" if is_cyber else "#333333",
                hover_color="#334155" if is_cyber else "#444444",
                text_color="#00f0ff" if is_cyber else "#ffffff",
                command=self.on_back
            )
            self.back_btn.grid(row=0, column=0, padx=(0, 10), sticky="w")

        self.tab_keys = ["overview", "diagnostics", "tweaks", "router", "profiles", "rollback"]
        self.tab_labels = {
            "overview": "Overview",
            "diagnostics": "Diagnostics",
            "tweaks": "Windows Tweaks",
            "router": "Router QoS/SQM",
            "profiles": "Game Profiles",
            "rollback": "Rollback"
        }

        self.nav_buttons = {}
        btn_box = ctk.CTkFrame(self.nav_bar, fg_color="transparent")
        btn_col = 1 if self.on_back else 0
        btn_box.grid(row=0, column=btn_col, sticky="w")

        for key in self.tab_keys:
            label = self.tab_labels[key]
            btn = ctk.CTkButton(
                btn_box,
                text=label,
                font=get_font(11, "bold"),
                height=32,
                fg_color="transparent",
                hover_color="#0e183a" if is_cyber else "#222222",
                text_color="#8193b8" if is_cyber else "#aaaaaa",
                corner_radius=16 if is_cyber else 6,
                command=lambda k=key: self.switch_tab(k)
            )
            btn.pack(side="left", padx=2)
            self.nav_buttons[key] = btn

        # ── Content Viewport ───────────────────────────────────────────
        self.content_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.content_frame.grid(row=1, column=0, sticky="nsew", padx=0, pady=0)
        self.content_frame.grid_columnconfigure(0, weight=1)
        self.content_frame.grid_rowconfigure(0, weight=1)

        self.tabs = {}
        self.current_tab_key = None

        self.switch_tab("overview")
        on_theme_changed(self.apply_theme)

    def switch_tab(self, tab_key: str):
        theme = get_theme()
        is_cyber = is_cyber_mode()

        for key, btn in self.nav_buttons.items():
            if key == tab_key:
                btn.configure(
                    fg_color="#0d183d" if is_cyber else "#2a2a2a",
                    border_width=1 if is_cyber else 0,
                    border_color="#00f0ff" if is_cyber else "#2a2a2a",
                    text_color="#00f0ff" if is_cyber else "#ffffff"
                )
            else:
                btn.configure(
                    fg_color="transparent",
                    border_width=0,
                    text_color="#8193b8" if is_cyber else "#aaaaaa"
                )

        if self.current_tab_key and self.current_tab_key in self.tabs:
            if self.current_tab_key == "diagnostics" and tab_key != "diagnostics":
                self.feature.cancel_active_diagnostics()
                self._is_live_monitoring = False
            self.tabs[self.current_tab_key].grid_forget()

        if tab_key not in self.tabs:
            builder = getattr(self, f"_build_{tab_key}_tab", None)
            if builder:
                self.tabs[tab_key] = builder()

        if tab_key in self.tabs:
            self.tabs[tab_key].grid(row=0, column=0, sticky="nsew", padx=0, pady=0)
            self.current_tab_key = tab_key

    # ── Tab 1: Overview ────────────────────────────────────────────────

    def _build_overview_tab(self) -> ctk.CTkScrollableFrame:
        theme = get_theme()
        is_cyber = is_cyber_mode()
        tab = ctk.CTkScrollableFrame(self.content_frame, fg_color="transparent")
        tab.grid_columnconfigure(0, weight=1)

        # Header
        h = ctk.CTkFrame(tab, fg_color="transparent")
        h.pack(fill="x", padx=16, pady=(10, 8))
        ctk.CTkLabel(h, text="⚡ FPS NETWORK STABILIZER // MISSION CONTROL" if is_cyber else "Network Stabilizer // Overview", font=get_font(19, "bold"), text_color="#00f0ff" if is_cyber else theme["text_title"]).pack(anchor="w")
        ctk.CTkLabel(h, text="Audit, diagnose, and eliminate packet jitter and bufferbloat with targeted rollback support.", font=get_font(12, "normal"), text_color=theme["text_secondary"]).pack(anchor="w", pady=(2, 0))

        # Baseline Status Card
        self.snap_card = ctk.CTkFrame(tab, fg_color=theme["bg_card"], corner_radius=12, border_width=1, border_color="#00f0ff" if is_cyber else "#1e1e1e")
        self.snap_card.pack(fill="x", padx=16, pady=8)
        self.snap_card.grid_columnconfigure(0, weight=1)
        self.snap_card.grid_columnconfigure(1, weight=0)

        info_box = ctk.CTkFrame(self.snap_card, fg_color="transparent")
        info_box.grid(row=0, column=0, padx=16, pady=12, sticky="w")

        self.snap_title = ctk.CTkLabel(info_box, text="🛡️ BASELINE SNAPSHOT: CHECKING...", font=get_font(13, "bold"), text_color="#00ff9f" if is_cyber else theme["text_primary"])
        self.snap_title.pack(anchor="w")
        self.snap_desc = ctk.CTkLabel(info_box, text="Baseline state captured in compact JSON. Targeted rollback ready.", font=get_font(11, "normal"), text_color=theme["text_secondary"])
        self.snap_desc.pack(anchor="w", pady=(2, 0))

        self.snap_btn = ctk.CTkButton(
            self.snap_card,
            text="📸 CAPTURE BASELINE" if is_cyber else "Capture Baseline",
            font=get_font(11, "bold"),
            fg_color="#00f0ff" if is_cyber else "#333333",
            hover_color="#38bdf8" if is_cyber else "#444444",
            text_color="#020617" if is_cyber else "#ffffff",
            height=32, corner_radius=16 if is_cyber else 6,
            command=self._on_capture_baseline
        )
        self.snap_btn.grid(row=0, column=1, padx=16, pady=12, sticky="e")
        self._refresh_snapshot_card()

        # Telemetry Grid
        t_grid = ctk.CTkFrame(tab, fg_color="transparent")
        t_grid.pack(fill="x", padx=16, pady=6)
        t_grid.grid_columnconfigure((0, 1, 2, 3), weight=1)

        self.ov_adapter = StatCard(t_grid, "📶", "ACTIVE ADAPTER", "Checking...", "Scanning NIC")
        self.ov_adapter.grid(row=0, column=0, padx=4, pady=4, sticky="ew")

        self.ov_gateway = StatCard(t_grid, "🏠", "DEFAULT GATEWAY", "Detecting...", "Local Hop")
        self.ov_gateway.grid(row=0, column=1, padx=4, pady=4, sticky="ew")

        self.ov_dns = StatCard(t_grid, "🌐", "ACTIVE DNS", "Querying...", "Resolver")
        self.ov_dns.grid(row=0, column=2, padx=4, pady=4, sticky="ew")

        self.ov_power = StatCard(t_grid, "⚡", "POWER SCHEME", "Querying...", "OS Policy")
        self.ov_power.grid(row=0, column=3, padx=4, pady=4, sticky="ew")

        self._refresh_telemetry_async()

        # Stutter Comparison
        SectionHeader(tab, "DIAGNOSTIC MATRIX: NETWORK STUTTER VS RENDER STUTTER", "Identify whether your micro-hitching is caused by packet queue delays or frame-time spikes.").pack(fill="x", padx=16, pady=(16, 6))

        matrix = ctk.CTkFrame(tab, fg_color="transparent")
        matrix.pack(fill="x", padx=16, pady=4)
        matrix.grid_columnconfigure((0, 1), weight=1)

        # Left: Network
        net = STUTTER_TYPES["network"]
        n_c = ctk.CTkFrame(matrix, fg_color=theme["bg_card"], corner_radius=12, border_width=1, border_color="#00f0ff" if is_cyber else "#1e1e1e")
        n_c.grid(row=0, column=0, padx=(0, 6), sticky="nsew")
        ctk.CTkLabel(n_c, text=f"🌐  {net['title']}", font=get_font(13, "bold"), text_color="#00f0ff" if is_cyber else theme["text_title"]).pack(anchor="w", padx=14, pady=(12, 6))
        for s in net["symptoms"]:
            ctk.CTkLabel(n_c, text=f"• {s}", font=get_font(10, "normal"), text_color=theme["text_primary"], wraplength=380, justify="left").pack(anchor="w", padx=18, pady=1)
        ctk.CTkButton(n_c, text="GO TO ROUTER SQM / QOS ➔", font=get_font(11, "bold"), fg_color="#0d183d" if is_cyber else "#222222", text_color="#00f0ff" if is_cyber else "#ffffff", border_width=1, border_color="#00f0ff" if is_cyber else "#444444", height=30, command=lambda: self.switch_tab("router")).pack(fill="x", padx=14, pady=(12, 14))

        # Right: Render
        ren = STUTTER_TYPES["render"]
        r_c = ctk.CTkFrame(matrix, fg_color=theme["bg_card"], corner_radius=12, border_width=1, border_color="#a855f7" if is_cyber else "#1e1e1e")
        r_c.grid(row=0, column=1, padx=(6, 0), sticky="nsew")
        ctk.CTkLabel(r_c, text=f"🖥️  {ren['title']}", font=get_font(13, "bold"), text_color="#c084fc" if is_cyber else theme["text_title"]).pack(anchor="w", padx=14, pady=(12, 6))
        for s in ren["symptoms"]:
            ctk.CTkLabel(r_c, text=f"• {s}", font=get_font(10, "normal"), text_color=theme["text_primary"], wraplength=380, justify="left").pack(anchor="w", padx=18, pady=1)
        ctk.CTkButton(r_c, text="VIEW GAME ANTI-STUTTER GUIDES ➔", font=get_font(11, "bold"), fg_color="#1e0f38" if is_cyber else "#222222", text_color="#c084fc" if is_cyber else "#ffffff", border_width=1, border_color="#a855f7" if is_cyber else "#444444", height=30, command=lambda: self.switch_tab("profiles")).pack(fill="x", padx=14, pady=(12, 14))

        return tab

    def _refresh_snapshot_card(self):
        meta = self.feature.snapshots.get_baseline_metadata()
        if meta and meta.get("created_at"):
            self.snap_title.configure(text=f"🛡️ BASELINE SNAPSHOT: SECURED ({meta.get('created_at')})", text_color="#00ff9f")
            self.snap_desc.configure(text="Baseline state saved in state document. Targeted 1-click rollback active.")
            self.snap_btn.configure(text="REFRESH SNAPSHOT" if is_cyber_mode() else "Refresh Snapshot")
        else:
            self.snap_title.configure(text="⚠️ BASELINE SNAPSHOT: NOT CREATED YET", text_color="#fbbf24")
            self.snap_desc.configure(text="Take a pre-tweak snapshot now to record feature-managed baseline values for targeted rollback.")
            self.snap_btn.configure(text="📸 CAPTURE BASELINE" if is_cyber_mode() else "Capture Baseline")

    def _on_capture_baseline(self):
        self.snap_btn.configure(state="disabled", text="Capturing...")
        def _worker():

            try:
                from sentinel.service import SentinelService
                if SentinelService.get_instance().is_running():
                    try:
                        self.schedule_ui_callback(0, lambda: hasattr(self, 'tweak_feed') and self.tweak_feed.configure(text='Unavailable while Sentinel is active', text_color='#f43f5e'))
                    except Exception:
                        pass
                    return
            except Exception:
                pass
            self.feature.snapshots.ensure_baseline_snapshot()
            try:
                self.schedule_ui_callback(0, lambda: [self._refresh_snapshot_card(), self.snap_btn.configure(state="normal")])
            except Exception:
                pass
        threading.Thread(target=_worker, daemon=True).start()

    def _refresh_telemetry_async(self):
        def _worker():

            try:
                from sentinel.service import SentinelService
                if SentinelService.get_instance().is_running():
                    try:
                        self.schedule_ui_callback(0, lambda: hasattr(self, 'tweak_feed') and self.tweak_feed.configure(text='Unavailable while Sentinel is active', text_color='#f43f5e'))
                    except Exception:
                        pass
                    return
            except Exception:
                pass
            adp = self.feature.tweaks.get_active_adapter_name() or "Disconnected"
            gw = self.feature.diagnostics.get_default_gateway()
            meta = self.feature.snapshots.get_baseline_metadata()
            dns_str = "Auto / DHCP"
            if meta and "dns" in meta:
                for a, d in meta["dns"].items():
                    if isinstance(d, dict):
                        servers = d.get("servers", [])
                        mode = d.get("mode", "auto")
                        if mode != "auto" and servers:
                            dns_str = ", ".join(servers[:2])
                            break
                    elif isinstance(d, list) and d and d != ["dhcp"]:
                        dns_str = ", ".join(d[:2])
                        break
            pwr = meta.get("power_plan", {}).get("name", "High Performance") if meta else "Custom"
            try:
                self.schedule_ui_callback(0, lambda: [
                    self.ov_adapter.update_val(adp[:15], "Interface UP", "#00ff9f" if adp != "Disconnected" else "#f43f5e"),
                    self.ov_gateway.update_val(gw, "Home Router IP", "#38bdf8"),
                    self.ov_dns.update_val(dns_str[:16], "Active Resolver", "#fbbf24"),
                    self.ov_power.update_val(pwr[:14], "Active Profile", "#c084fc")
                ])
            except Exception:
                pass
        threading.Thread(target=_worker, daemon=True).start()

    # ── Tab 2: Diagnostics ─────────────────────────────────────────────

    def _build_diagnostics_tab(self) -> ctk.CTkScrollableFrame:
        theme = get_theme()
        is_cyber = is_cyber_mode()
        tab = ctk.CTkScrollableFrame(self.content_frame, fg_color="transparent")
        tab.grid_columnconfigure(0, weight=1)

        # Header & Control Bar
        c_bar = ctk.CTkFrame(tab, fg_color="transparent")
        c_bar.pack(fill="x", padx=16, pady=(10, 4))
        c_bar.grid_columnconfigure(0, weight=1)
        c_bar.grid_columnconfigure((1, 2), weight=0)

        ctk.CTkLabel(c_bar, text="📡 AUTOMATED NETWORK DIAGNOSTICS" if is_cyber else "Network Diagnostics", font=get_font(18, "bold"), text_color="#00f0ff" if is_cyber else theme["text_title"]).grid(row=0, column=0, sticky="w")
        self.diag_btn = ctk.CTkButton(c_bar, text="⚡ RUN PROBE NOW", font=get_font(11, "bold"), fg_color="#00f0ff" if is_cyber else "#333333", text_color="#020617" if is_cyber else "#ffffff", height=30, command=self._on_run_probe)
        self.diag_btn.grid(row=0, column=1, padx=(0, 6), sticky="e")

        self.cancel_diag_btn = ctk.CTkButton(c_bar, text="⏹ CANCEL", font=get_font(11, "bold"), fg_color="#ef4444", hover_color="#dc2626", text_color="#ffffff", width=80, height=30, command=self._on_cancel_probe)
        self.cancel_diag_btn.grid(row=0, column=2, sticky="e")

        # 4 Ping Cards (Initially with no hard-coded sample values)
        p_grid = ctk.CTkFrame(tab, fg_color="transparent")
        p_grid.pack(fill="x", padx=16, pady=4)
        p_grid.grid_columnconfigure((0, 1, 2, 3), weight=1)

        gw = self.feature.diagnostics.get_default_gateway()
        self.dg_gw = StatCard(p_grid, "🏠", "GATEWAY", "--", f"Hop: {gw}")
        self.dg_gw.grid(row=0, column=0, padx=4, pady=4, sticky="ew")

        self.dg_cf = StatCard(p_grid, "☁️", "CLOUDFLARE", "--", "1.1.1.1 Anycast")
        self.dg_cf.grid(row=0, column=1, padx=4, pady=4, sticky="ew")

        self.dg_gg = StatCard(p_grid, "🌐", "GOOGLE DNS", "--", "8.8.8.8 Anycast")
        self.dg_gg.grid(row=0, column=2, padx=4, pady=4, sticky="ew")

        self.dg_gm = StatCard(p_grid, "🎯", "GAME SERVER", "--", "AWS / Riot")
        self.dg_gm.grid(row=0, column=3, padx=4, pady=4, sticky="ew")

        # Custom Game Target input
        custom_bar = ctk.CTkFrame(tab, fg_color="transparent")
        custom_bar.pack(fill="x", padx=16, pady=(2, 6))
        custom_bar.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(custom_bar, text="Custom Game IP / Host:", font=get_font(11, "bold"), text_color=theme["text_secondary"]).grid(row=0, column=0, padx=(0, 8), sticky="w")
        self.custom_host = ctk.CTkEntry(custom_bar, font=get_font(11, "normal"), height=28)
        self.custom_host.insert(0, "dynamodb.us-east-1.amazonaws.com")
        self.custom_host.grid(row=0, column=1, sticky="ew")

        # Real-time trajectory graph
        g_bar = ctk.CTkFrame(tab, fg_color="transparent")
        g_bar.pack(fill="x", padx=16, pady=(10, 4))
        g_bar.grid_columnconfigure(0, weight=1)
        g_bar.grid_columnconfigure(1, weight=0)
        ctk.CTkLabel(g_bar, text="REAL-TIME LATENCY TRAJECTORY", font=get_font(12, "bold"), text_color="#8193b8" if is_cyber else theme["text_secondary"]).grid(row=0, column=0, sticky="w")

        self.live_btn = ctk.CTkButton(g_bar, text="▶ START LIVE MONITOR", font=get_font(11, "bold"), fg_color="#10b981", height=28, command=self._toggle_live_monitor)
        self.live_btn.grid(row=0, column=1, sticky="e")

        g_card = ctk.CTkFrame(tab, fg_color=theme["bg_card"], corner_radius=12, border_width=1, border_color=theme.get("border_card", "#1e1e1e"))
        g_card.pack(fill="x", padx=16, pady=4)
        self.graph = LatencyGraphCanvas(g_card, height=125)
        self.graph.pack(fill="both", expand=True, padx=8, pady=8)

        # Bufferbloat Section
        SectionHeader(tab, "BUFFERBLOAT & LATENCY UNDER LOAD CHECK", "Measures latency degradation during active data saturation.").pack(fill="x", padx=16, pady=(16, 6))

        b_card = ctk.CTkFrame(tab, fg_color=theme["bg_card"], corner_radius=12, border_width=1, border_color="#00f0ff" if is_cyber else "#1e1e1e")
        b_card.pack(fill="x", padx=16, pady=4)
        b_card.grid_columnconfigure((0, 1), weight=1)

        l_box = ctk.CTkFrame(b_card, fg_color="transparent")
        l_box.grid(row=0, column=0, padx=16, pady=14, sticky="nsew")
        self.bloat_stat = ctk.CTkLabel(l_box, text="Status: Ready to test", font=get_font(11, "bold"), text_color="#8193b8")
        self.bloat_stat.pack(anchor="w", pady=(0, 6))

        btn_row = ctk.CTkFrame(l_box, fg_color="transparent")
        btn_row.pack(anchor="w", pady=(0, 4))
        self.bloat_btn = ctk.CTkButton(btn_row, text="🚀 TEST BUFFERBLOAT UNDER LOAD", font=get_font(11, "bold"), fg_color="#00f0ff" if is_cyber else "#333333", text_color="#020617" if is_cyber else "#ffffff", height=32, command=self._on_run_bufferbloat)
        self.bloat_btn.pack(side="left", padx=(0, 8))
        self.bloat_stop_btn = ctk.CTkButton(btn_row, text="⏹ STOP", font=get_font(11, "bold"), fg_color="#ef4444", hover_color="#dc2626", text_color="#ffffff", width=70, height=32, command=self._on_stop_bufferbloat)
        self.bloat_stop_btn.pack(side="left")

        ctk.CTkLabel(l_box, text="* Bufferbloat grades are application-defined guidance thresholds, not official standards.", font=get_font(10, "normal"), text_color=theme["text_muted"]).pack(anchor="w", pady=(4, 0))

        r_box = ctk.CTkFrame(b_card, fg_color="transparent")
        r_box.grid(row=0, column=1, padx=16, pady=14, sticky="nsew")
        self.grade_chip = ctk.CTkLabel(r_box, text="GRADE: --", font=get_font(22, "bold"), text_color="#8193b8")
        self.grade_chip.pack(anchor="w")
        self.bloat_desc = ctk.CTkLabel(r_box, text="Run test to evaluate queue bloat rating.", font=get_font(11, "normal"), text_color=theme["text_secondary"], wraplength=340, justify="left")
        self.bloat_desc.pack(anchor="w", pady=(2, 6))

        # Verdict
        self.v_card = ctk.CTkFrame(tab, fg_color=theme["bg_card"], corner_radius=12, border_width=1, border_color="#1a2b5e" if is_cyber else "#1e1e1e")
        self.v_card.pack(fill="x", padx=16, pady=(10, 16))
        self.v_card.grid_columnconfigure(0, weight=1)
        self.v_card.grid_columnconfigure(1, weight=0)

        v_box = ctk.CTkFrame(self.v_card, fg_color="transparent")
        v_box.grid(row=0, column=0, padx=16, pady=12, sticky="w")
        self.v_title = ctk.CTkLabel(v_box, text="DIAGNOSTIC VERDICT: AWAITING PROBE", font=get_font(12, "bold"), text_color="#8193b8")
        self.v_title.pack(anchor="w")
        self.v_desc = ctk.CTkLabel(v_box, text="Run ping probes and bufferbloat test to discover root causes.", font=get_font(11, "normal"), text_color=theme["text_primary"], wraplength=520, justify="left")
        self.v_desc.pack(anchor="w", pady=(2, 0))

        self.v_btn = ctk.CTkButton(self.v_card, text="APPLY SAFE OPTIMIZATIONS ➔", font=get_font(11, "bold"), height=32, command=lambda: self.switch_tab("tweaks"))
        self.v_btn.grid(row=0, column=1, padx=16, pady=12, sticky="e")

        return tab

    def _on_run_probe(self):
        host = self.custom_host.get()
        # Strictly validate custom target before launching probe
        is_valid, err = self.feature.diagnostics.validate_target(host)
        if not is_valid:
            self.v_title.configure(text=f"INVALID TARGET: {err}", text_color="#ef4444")
            self.v_desc.configure(text=f"Target rejected: {err}. Please enter a valid IPv4 or hostname without whitespace or shell characters.")
            return

        self.diag_btn.configure(state="disabled", text="Probing...")
        def _worker():

            try:
                from sentinel.service import SentinelService
                if SentinelService.get_instance().is_running():
                    try:
                        self.schedule_ui_callback(0, lambda: hasattr(self, 'tweak_feed') and self.tweak_feed.configure(text='Unavailable while Sentinel is active', text_color='#f43f5e'))
                    except Exception:
                        pass
                    return
            except Exception:
                pass
            summary = self.feature.run_diagnostics(target=host)
            self.feature.snapshots.save_latest_diagnostics(summary)
            try:
                self.schedule_ui_callback(0, self._apply_probe_results, summary)
            except Exception:
                pass
        threading.Thread(target=_worker, daemon=True).start()

    def _on_cancel_probe(self):
        self.feature.cancel_active_diagnostics()
        self.diag_btn.configure(state="normal", text="⚡ RUN PROBE NOW")
        self.v_title.configure(text="DIAGNOSTIC PROBE CANCELLED", text_color="#fbbf24")
        self.v_desc.configure(text="Probe interrupted by user request. Subprocesses terminated.")

    def _on_stop_bufferbloat(self):
        self.feature.cancel_active_diagnostics()
        self.bloat_btn.configure(state="normal", text="🚀 TEST BUFFERBLOAT UNDER LOAD")
        self.bloat_stat.configure(text="Bufferbloat Test Interrupted", text_color="#fbbf24")

    def _apply_probe_results(self, summary: dict):
        self.diag_btn.configure(state="normal", text="⚡ RUN PROBE NOW")
        t = summary.get("targets", {})

        cards = [
            ("gateway", self.dg_gw),
            ("cloudflare", self.dg_cf),
            ("google", self.dg_gg),
            ("game", self.dg_gm)
        ]

        for tid, card in cards:
            d = t.get(tid, {})
            if d.get("avg_ms", -1) >= 0 and d.get("samples_count", 0) > 0:
                avg = d["avg_ms"]
                jitter = d.get("adjacent_jitter_ms", d.get("jitter_ms", 0.0))
                p95 = d.get("p95_ms", 0.0)
                loss = d.get("loss_pct", 0.0)
                sub = f"Adj Jitter: {jitter}ms | P95: {p95}ms | Loss: {loss}%"
                card.update_val(f"{avg} ms", sub, "#00ff9f")
                if tid in ("gateway", "cloudflare"):
                    self.graph.add_point(avg)
            elif d.get("error"):
                card.update_val("Error", d.get("error")[:25], "#ef4444")
            else:
                card.update_val("Timeout", "100% loss / unreachable", "#ef4444")

        verdict = summary.get("verdict", "Completed")
        self.v_title.configure(text=f"VERDICT: {verdict}", text_color="#00f0ff")
        self.v_desc.configure(text=summary.get("recommendation", ""))

    def _toggle_live_monitor(self):
        if self._is_live_monitoring:
            self._is_live_monitoring = False
            self.live_btn.configure(text="▶ START LIVE MONITOR", fg_color="#10b981")
        else:
            self._is_live_monitoring = True
            self.live_btn.configure(text="⏹ STOP MONITOR", fg_color="#f43f5e")
            def _loop():
                while self._is_live_monitoring and self.is_view_alive():
                    try:
                        res = self.feature.diagnostics.ping_host("1.1.1.1", count=1, timeout_ms=800)
                        if res.get("samples") and self.is_view_alive():
                            self.schedule_ui_callback(0, self.graph.add_point, res["samples"][0])
                    except Exception:
                        pass
                    time.sleep(1.0)
            threading.Thread(target=_loop, daemon=True).start()

    def _on_run_bufferbloat(self):
        self.bloat_btn.configure(state="disabled", text="Testing...")
        def _prog(m):
            try:
                self.schedule_ui_callback(0, lambda: self.bloat_stat.configure(text=m))
            except Exception:
                pass
        def _worker():

            try:
                from sentinel.service import SentinelService
                if SentinelService.get_instance().is_running():
                    try:
                        self.schedule_ui_callback(0, lambda: hasattr(self, 'tweak_feed') and self.tweak_feed.configure(text='Unavailable while Sentinel is active', text_color='#f43f5e'))
                    except Exception:
                        pass
                    return
            except Exception:
                pass
            res = self.feature.diagnostics.run_automated_bufferbloat_test(progress_callback=_prog)
            try:
                self.schedule_ui_callback(0, self._apply_bloat, res)
            except Exception:
                pass
        threading.Thread(target=_worker, daemon=True).start()

    def _apply_bloat(self, res: dict):
        self.bloat_btn.configure(state="normal", text="🚀 TEST BUFFERBLOAT UNDER LOAD")
        self.bloat_stat.configure(text="Test Complete", text_color="#00ff9f")
        delta = res.get("delta_ms", 0.0)
        grade = res.get("grade", "--")
        rating = res.get("rating", "Unknown")
        self.grade_chip.configure(text=f"GRADE: {grade} ({rating})", text_color=res.get("color", "#ffffff"))
        self.bloat_desc.configure(text=f"Idle: {res.get('idle_latency_ms', 0)}ms | Under Load: {res.get('loaded_latency_ms', 0)}ms | Delta: +{delta}ms\n{res.get('summary', '')}")

    # ── Tab 3: Windows Tweaks ──────────────────────────────────────────

    def _build_tweaks_tab(self) -> ctk.CTkScrollableFrame:
        theme = get_theme()
        is_cyber = is_cyber_mode()
        tab = ctk.CTkScrollableFrame(self.content_frame, fg_color="transparent")
        tab.grid_columnconfigure(0, weight=1)

        # Header
        h = ctk.CTkFrame(tab, fg_color="transparent")
        h.pack(fill="x", padx=16, pady=(10, 4))
        ctk.CTkLabel(h, text="⚡ REVERSIBLE WINDOWS OPTIMIZATIONS" if is_cyber else "Windows Network Tweaks", font=get_font(18, "bold"), text_color="#00f0ff" if is_cyber else theme["text_title"]).pack(anchor="w")
        ctk.CTkLabel(h, text="Every action records a change record. Restore individual tweaks here or all via the Rollback tab.", font=get_font(12, "normal"), text_color=theme["text_secondary"]).pack(anchor="w", pady=(2, 0))

        # Safe Profile One-Click Banner
        sp_card = ctk.CTkFrame(tab, fg_color="#090e23" if is_cyber else "#141414", corner_radius=12, border_width=1, border_color="#00ff9f")
        sp_card.pack(fill="x", padx=16, pady=8)
        sp_card.grid_columnconfigure(0, weight=1)
        sp_card.grid_columnconfigure(1, weight=0)

        sp_info = ctk.CTkFrame(sp_card, fg_color="transparent")
        sp_info.grid(row=0, column=0, padx=16, pady=12, sticky="w")
        ctk.CTkLabel(sp_info, text="⚡ APPLY SAFE OPTIMIZATION", font=get_font(13, "bold"), text_color="#00ff9f").pack(anchor="w")
        ctk.CTkLabel(sp_info, text="Applies verified safe optimizations: DNS cache flush, High Performance power plan, and GameDVR disable. Experimental settings are never included.", font=get_font(11, "normal"), text_color=theme["text_secondary"]).pack(anchor="w", pady=(2, 0))

        ctk.CTkButton(sp_card, text="APPLY SAFE OPTIMIZATION", font=get_font(11, "bold"), fg_color="#00ff9f", hover_color="#34d399", text_color="#020617", height=32, command=self._on_apply_safe_profile).grid(row=0, column=1, padx=16, pady=12, sticky="e")

        self.tweak_feed = ctk.CTkLabel(tab, text="", font=get_font(12, "bold"), text_color="#00ff9f", anchor="w")
        self.tweak_feed.pack(fill="x", padx=16, pady=(0, 6))

        # ── Safe Tweaks ────────────────────────────────────────────────
        # 1. DNS Switcher
        c1 = self._make_card(tab, "🌐  Fast Gaming DNS Switcher", "Configures low-latency Anycast DNS on your active adapter with one-click restore.")
        b1 = ctk.CTkFrame(c1, fg_color="transparent")
        b1.pack(fill="x", padx=16, pady=(0, 12))
        for l, p in DNS_PRESETS.items():
            ctk.CTkButton(b1, text=f"{l} ({p['primary']})", font=get_font(10, "bold"), width=150, height=30, command=lambda pri=p["primary"], sec=p["secondary"], nm=l: self._apply_dns(pri, sec, nm)).pack(side="left", padx=(0, 8))
        ctk.CTkButton(b1, text="Revert to DHCP", font=get_font(10, "bold"), width=130, height=30, fg_color="#334155", command=self._revert_dns).pack(side="left", padx=4)

        # 2. Flush DNS Cache
        c2 = self._make_card(tab, "🧹  Flush DNS Resolver Cache", "Clears stale host lookup records from the Windows DNS resolver.")
        b2 = ctk.CTkFrame(c2, fg_color="transparent")
        b2.pack(fill="x", padx=16, pady=(0, 12))
        ctk.CTkButton(b2, text="Flush DNS Cache", font=get_font(10, "bold"), width=160, height=30, fg_color="#10b981", command=lambda: self._tweak_action(self.feature.tweaks.flush_dns, "DNS Cache Flushed")).pack(side="left")

        # 3. Power Plan
        c3 = self._make_card(tab, "⚡  High & Ultimate Performance Power Plan", "Activates low-latency CPU scheduling power plans with full GUID recorded for rollback.")
        b3 = ctk.CTkFrame(c3, fg_color="transparent")
        b3.pack(fill="x", padx=16, pady=(0, 12))
        ctk.CTkButton(b3, text="High Performance", font=get_font(10, "bold"), width=160, height=30, command=lambda: self._tweak_action(intervention_name="power_plan", args={"requested_guid": "8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c"}, success_msg="High Performance Plan Applied")).pack(side="left", padx=(0, 8))
        ctk.CTkButton(b3, text="Ultimate Performance", font=get_font(10, "bold"), width=170, height=30, command=lambda: self._tweak_action(intervention_name="power_plan", args={"requested_guid": "e9a42b02-d5df-448d-aa00-03f14749eb61"}, success_msg="Ultimate Performance Plan Applied")).pack(side="left", padx=4)

        # 4. GameDVR
        c4 = self._make_card(tab, "🎮  Xbox GameDVR Background Capture", "Disables continuous background video capture hooks to free DWM rendering cycles.")
        b4 = ctk.CTkFrame(c4, fg_color="transparent")
        b4.pack(fill="x", padx=16, pady=(0, 12))
        ctk.CTkButton(b4, text="Disable GameDVR", font=get_font(10, "bold"), width=150, height=30, command=lambda: self._tweak_action(lambda: self.feature.tweaks.set_game_dvr_state(False), "GameDVR Disabled")).pack(side="left", padx=(0, 8))
        ctk.CTkButton(b4, text="Re-enable GameDVR", font=get_font(10, "bold"), width=150, height=30, fg_color="#334155", command=lambda: self._tweak_action(lambda: self.feature.tweaks.set_game_dvr_state(True), "GameDVR Re-enabled")).pack(side="left", padx=4)

        # ── Collapsed Experimental Section (Disabled by default) ───────
        exp_box = ctk.CTkFrame(tab, fg_color=theme["bg_card"], corner_radius=12, border_width=1, border_color="#e11d48" if is_cyber else "#441111")
        exp_box.pack(fill="x", padx=16, pady=(16, 12))

        exp_top = ctk.CTkFrame(exp_box, fg_color="transparent")
        exp_top.pack(fill="x", padx=16, pady=12)
        exp_top.grid_columnconfigure(0, weight=1)
        exp_top.grid_columnconfigure(1, weight=0)

        ctk.CTkLabel(exp_top, text="⚠️ EXPERIMENTAL TWEAKS — REQUIRES EXPLICIT CONFIRMATION", font=get_font(12, "bold"), text_color="#f43f5e").grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(exp_top, text="Modifies advanced TCP/IP registry parameters and adapter sleep offloads. NEVER included in Apply Safe Optimization.", font=get_font(10, "normal"), text_color=theme["text_secondary"]).grid(row=1, column=0, sticky="w", pady=(2, 0))

        self.exp_expanded = False
        self.exp_toggle_btn = ctk.CTkButton(exp_top, text="▶ SHOW", font=get_font(10, "bold"), width=80, height=28, fg_color="#334155", command=self._toggle_experimental_section)
        self.exp_toggle_btn.grid(row=0, column=1, rowspan=2, sticky="e")

        self.exp_body = ctk.CTkFrame(exp_box, fg_color="transparent")
        # Collapsed by default - self.exp_body is packed only on toggle

        self.exp_check_val = ctk.BooleanVar(value=False)
        self.exp_check = ctk.CTkCheckBox(self.exp_body, text="I understand these experimental settings alter OS network parameters outside the safe profile.", variable=self.exp_check_val, font=get_font(10, "bold"), text_color="#fbbf24", command=self._on_toggle_exp_confirmed)
        self.exp_check.pack(anchor="w", padx=16, pady=(0, 10))

        self.exp_btn_reg = ctk.CTkButton(self.exp_body, text="Apply TCP/IP Registry Tuning (Nagle Off, Throttling Removed)", font=get_font(10, "bold"), state="disabled", width=420, height=30, command=lambda: self._tweak_action(self.feature.tweaks.apply_registry_network_tuning, "Registry Tuned (Nagle disabled, throttling removed)"))
        self.exp_btn_reg.pack(anchor="w", padx=16, pady=4)

        self.exp_btn_nic = ctk.CTkButton(self.exp_body, text="Disable NIC Power Saving (Energy Efficient Ethernet)", font=get_font(10, "bold"), state="disabled", width=420, height=30, command=lambda: self._tweak_action(self.feature.tweaks.apply_experimental_nic_power, "NIC Power Saving Disabled"))
        self.exp_btn_nic.pack(anchor="w", padx=16, pady=4)

        # Winsock Reset: Recovery Action requiring restart / manual intervention
        self.exp_btn_rst = ctk.CTkButton(
            self.exp_body,
            text="🔧 Reset Winsock & TCP/IP Stack (Recovery Action — Requires Restart / Manual Intervention)",
            font=get_font(10, "bold"),
            state="disabled",
            fg_color="#881337",
            width=480,
            height=30,
            command=lambda: self._tweak_action(self.feature.tweaks.reset_network_stack, "Winsock reset initiated (Recovery action — restart / manual intervention required)")
        )
        self.exp_btn_rst.pack(anchor="w", padx=16, pady=4)
        ctk.CTkLabel(
            self.exp_body,
            text="Recovery action requiring restart / manual intervention. Cleans Winsock and IP catalogs. Cannot be rolled back automatically.",
            font=get_font(9, "normal"),
            text_color="#fbbf24"
        ).pack(anchor="w", padx=16, pady=(0, 12))

        return tab

    def _toggle_experimental_section(self):
        if self.exp_expanded:
            self.exp_body.pack_forget()
            self.exp_expanded = False
            self.exp_toggle_btn.configure(text="▶ SHOW")
        else:
            self.exp_body.pack(fill="x", padx=0, pady=(0, 8))
            self.exp_expanded = True
            self.exp_toggle_btn.configure(text="▼ HIDE")

    def _on_toggle_exp_confirmed(self):
        enabled = self.exp_check_val.get()
        new_state = "normal" if enabled else "disabled"
        self.exp_btn_reg.configure(state=new_state)
        self.exp_btn_nic.configure(state=new_state)
        self.exp_btn_rst.configure(state=new_state)

    def _make_card(self, parent, title: str, desc: str) -> ctk.CTkFrame:
        theme = get_theme()
        card = ctk.CTkFrame(parent, fg_color=theme["bg_card"], corner_radius=12, border_width=1, border_color=theme.get("border_card", "#1e1e1e"))
        card.pack(fill="x", padx=16, pady=6)
        ctk.CTkLabel(card, text=title, font=get_font(12, "bold"), text_color="#00f0ff" if is_cyber_mode() else theme["text_primary"]).pack(anchor="w", padx=16, pady=(10, 2))
        ctk.CTkLabel(card, text=desc, font=get_font(10, "normal"), text_color=theme["text_secondary"]).pack(anchor="w", padx=16, pady=(0, 8))
        return card

    def _tweak_action(self, fn=None, success_msg: str = "", intervention_name: str = None, args: dict = None):
        def _worker():
            from sentinel.service import SentinelService
            
            # Use SentinelService if typed intervention provided
            if intervention_name:
                res = SentinelService.get_instance().request_intervention(intervention_name, args)
                status = res.get("status")
                ok = status in ("applied", "dry_run")
                
                # Format specific feedback for typed interventions
                if ok:
                    msg = success_msg or f"{intervention_name} {status}"
                else:
                    msg = f"Blocked/Failed: {res.get('reason', res.get('status', 'Unknown'))}"
                
                try:
                    self.schedule_ui_callback(0, lambda: self.tweak_feed.configure(text=f"{'✅' if ok else '❌'} {msg}", text_color="#00ff9f" if ok else "#f43f5e"))
                except Exception:
                    pass
                return

            # Legacy behavior for non-typed tweaks
            try:
                if SentinelService.get_instance().is_running() and SentinelService.get_instance().controller.mode == 1: # MONITOR_ONLY fallback
                    try:
                        self.schedule_ui_callback(0, lambda: hasattr(self, 'tweak_feed') and self.tweak_feed.configure(text='❌ Blocked: MONITOR_ONLY', text_color='#f43f5e'))
                    except Exception:
                        pass
                    return
            except Exception:
                pass
            
            if fn:
                res = fn()
                ok = res.get("success", False) if isinstance(res, dict) else bool(res)
                msg = success_msg if ok else f"Failed: {res.get('error') if isinstance(res, dict) else 'Unknown'}"
                try:
                    self.schedule_ui_callback(0, lambda: self.tweak_feed.configure(text=f"{'✅' if ok else '❌'} {msg}", text_color="#00ff9f" if ok else "#f43f5e"))
                except Exception:
                    pass
        import threading
        threading.Thread(target=_worker, daemon=True).start()

    def _on_apply_safe_profile(self):
        def _worker():

            try:
                from sentinel.service import SentinelService
                if SentinelService.get_instance().is_running():
                    try:
                        self.schedule_ui_callback(0, lambda: hasattr(self, 'tweak_feed') and self.tweak_feed.configure(text='Unavailable while Sentinel is active', text_color='#f43f5e'))
                    except Exception:
                        pass
                    return
            except Exception:
                pass
            res = self.feature.apply_safe_optimization()
            ok = res.get("success", False)
            try:
                self.schedule_ui_callback(0, lambda: self.tweak_feed.configure(text=f"{'✅' if ok else '❌'} {res.get('message')}", text_color="#00ff9f" if ok else "#f43f5e"))
            except Exception:
                pass
        threading.Thread(target=_worker, daemon=True).start()

    def _apply_dns(self, p: str, s: Optional[str], nm: str):
        def _worker():
            from sentinel.service import SentinelService
            servers = []
            if s:
                servers = [x.strip() for x in str(s).split(',') if x.strip()]
                
            res = SentinelService.get_instance().request_intervention("dns", {
                "adapter_id": p,
                "servers": servers,
                "mode": nm
            })
            
            ok = res.get("status") == "applied"
            msg = f"DNS set to {nm} ({p})" if ok else f"Failed or Blocked: {res.get('reason', res.get('status'))}"
            try:
                self.schedule_ui_callback(0, lambda: self.tweak_feed.configure(text=f"{'✅' if ok else '❌'} {msg}", text_color="#00ff9f" if ok else "#f43f5e"))
            except Exception:
                pass
        import threading
        threading.Thread(target=_worker, daemon=True).start()

    def _revert_dns(self, p: str = None):
        def _worker():
            from sentinel.service import SentinelService
            res = SentinelService.get_instance().request_intervention("dns", {
                "adapter_id": p if p else "Ethernet", # Needs real adapter or logic, fallback
                "mode": "dhcp"
            })
            ok = res.get("status") == "applied"
            msg = "DNS returned to DHCP" if ok else f"Failed or Blocked: {res.get('reason', res.get('status'))}"
            try:
                self.schedule_ui_callback(0, lambda: self.tweak_feed.configure(text=f"{'✅' if ok else '❌'} {msg}", text_color="#00ff9f" if ok else "#f43f5e"))
            except Exception:
                pass
        import threading
        threading.Thread(target=_worker, daemon=True).start()

    # ── Tab 4: Router QoS/SQM ──────────────────────────────────────────

    def _build_router_tab(self) -> ctk.CTkScrollableFrame:
        theme = get_theme()
        is_cyber = is_cyber_mode()
        tab = ctk.CTkScrollableFrame(self.content_frame, fg_color="transparent")
        tab.grid_columnconfigure(0, weight=1)

        # Header & Notice
        h = ctk.CTkFrame(tab, fg_color="transparent")
        h.pack(fill="x", padx=16, pady=(10, 4))
        ctk.CTkLabel(h, text="🌐 ROUTER QUALITY OF SERVICE (QoS & SQM)" if is_cyber else "Router QoS / SQM Advisor", font=get_font(18, "bold"), text_color="#00f0ff" if is_cyber else theme["text_title"]).pack(anchor="w")

        d_card = ctk.CTkFrame(tab, fg_color="#1e1b18", corner_radius=10, border_width=1, border_color="#fbbf24")
        d_card.pack(fill="x", padx=16, pady=6)
        ctk.CTkLabel(d_card, text="⚠️  MANUAL ACTION REQUIRED: The application will never modify router hardware remotely.", font=get_font(11, "bold"), text_color="#fbbf24").pack(anchor="w", padx=12, pady=(8, 2))
        ctk.CTkLabel(d_card, text="Open your router portal (usually http://192.168.1.1) to apply the generated bandwidth limits.", font=get_font(10, "normal"), text_color="#dddddd").pack(anchor="w", padx=12, pady=(0, 8))

        # Wizard
        SectionHeader(tab, "ROUTER & BANDWIDTH CALCULATOR", "Enter measured speeds to calculate 85-92% bufferbloat ceilings.").pack(fill="x", padx=16, pady=(10, 4))

        w_card = ctk.CTkFrame(tab, fg_color=theme["bg_card"], corner_radius=12, border_width=1, border_color=theme.get("border_card", "#1e1e1e"))
        w_card.pack(fill="x", padx=16, pady=4)
        w_card.grid_columnconfigure((0, 1, 2, 3), weight=1)

        ctk.CTkLabel(w_card, text="Firmware / Brand:", font=get_font(10, "bold"), text_color=theme["text_secondary"]).grid(row=0, column=0, padx=12, pady=(10, 0), sticky="w")
        self.r_firmware = ctk.CTkOptionMenu(w_card, values=RouterAdvisor.SUPPORTED_FIRMWARES, font=get_font(10, "normal"))
        self.r_firmware.set("OpenWrt (CAKE / fq_codel)")
        self.r_firmware.grid(row=1, column=0, padx=12, pady=(2, 10), sticky="ew")

        ctk.CTkLabel(w_card, text="Down (Mbps):", font=get_font(10, "bold"), text_color=theme["text_secondary"]).grid(row=0, column=1, padx=8, pady=(10, 0), sticky="w")
        self.r_down = ctk.CTkEntry(w_card, font=get_font(10, "normal"), width=70)
        self.r_down.insert(0, "100")
        self.r_down.grid(row=1, column=1, padx=8, pady=(2, 10), sticky="ew")

        ctk.CTkLabel(w_card, text="Up (Mbps):", font=get_font(10, "bold"), text_color=theme["text_secondary"]).grid(row=0, column=2, padx=8, pady=(10, 0), sticky="w")
        self.r_up = ctk.CTkEntry(w_card, font=get_font(10, "normal"), width=70)
        self.r_up.insert(0, "20")
        self.r_up.grid(row=1, column=2, padx=8, pady=(2, 10), sticky="ew")

        ctk.CTkButton(w_card, text="⚡ Calculate", font=get_font(10, "bold"), width=90, height=28, command=self._on_calc_router).grid(row=1, column=3, padx=12, pady=(2, 10), sticky="ew")

        # Output Card
        self.out_card = ctk.CTkFrame(tab, fg_color=theme["bg_card"], corner_radius=12, border_width=1, border_color="#00f0ff" if is_cyber else "#1e1e1e")
        self.out_card.pack(fill="x", padx=16, pady=8)

        self.r_banner = ctk.CTkLabel(self.out_card, text="Target Caps: Calculating...", font=get_font(13, "bold"), text_color="#00ff9f")
        self.r_banner.pack(anchor="w", padx=16, pady=(12, 4))

        self.r_steps = ctk.CTkFrame(self.out_card, fg_color="transparent")
        self.r_steps.pack(fill="x", padx=16, pady=(0, 8))

        self.r_snippet = ctk.CTkTextbox(self.out_card, font=("Consolas", 10), height=130, fg_color="#060919", text_color="#00f0ff")
        self.r_snippet.pack(fill="x", padx=16, pady=(0, 8))

        self.copy_btn = ctk.CTkButton(self.out_card, text="📋 Copy Snippet", font=get_font(10, "bold"), width=140, height=28, command=self._copy_router_snippet)
        self.copy_btn.pack(anchor="w", padx=16, pady=(0, 12))

        self._on_calc_router()
        return tab

    def _on_calc_router(self):
        try:
            d = float(self.r_down.get())
            u = float(self.r_up.get())
        except ValueError:
            d, u = 100.0, 20.0
        fw = self.r_firmware.get()
        limits = RouterAdvisor.calculate_bandwidth_limits(d, u, "Cable")
        guide = RouterAdvisor.get_router_guide(fw, d, u, limits)

        self.r_banner.configure(text=f"Download Cap: {limits['down_limit_mbps']} Mbps ({limits['down_ratio_pct']}%) | Upload Cap: {limits['up_limit_mbps']} Mbps ({limits['up_ratio_pct']}%)")
        for w in self.r_steps.winfo_children():
            w.destroy()
        for i, s in enumerate(guide.get("steps", [])[:5]):
            ctk.CTkLabel(self.r_steps, text=f"{i+1}. {s}", font=get_font(10, "normal"), text_color=get_theme()["text_primary"], wraplength=660, justify="left").pack(anchor="w", pady=1)

        self.r_snippet.delete("1.0", "end")
        self.r_snippet.insert("1.0", guide.get("snippet", ""))

    def _copy_router_snippet(self):
        t = self.r_snippet.get("1.0", "end-1c")
        self.clipboard_clear()
        self.clipboard_append(t)
        self.copy_btn.configure(text="✅ Copied!")
        self.after(2000, lambda: self.copy_btn.configure(text="📋 Copy Snippet"))

    # ── Tab 5: Game Profiles ───────────────────────────────────────────

    def _build_profiles_tab(self) -> ctk.CTkScrollableFrame:
        theme = get_theme()
        is_cyber = is_cyber_mode()
        tab = ctk.CTkScrollableFrame(self.content_frame, fg_color="transparent")
        tab.grid_columnconfigure(0, weight=1)

        h = ctk.CTkFrame(tab, fg_color="transparent")
        h.pack(fill="x", padx=16, pady=(10, 4))
        ctk.CTkLabel(h, text="🎮 GAME PROFILES & IN-GAME TELEMETRY" if is_cyber else "Game Profiles & Settings", font=get_font(18, "bold"), text_color="#00f0ff" if is_cyber else theme["text_title"]).pack(anchor="w")

        tabview = ctk.CTkTabview(tab, fg_color=theme["bg_card"])
        tabview.pack(fill="x", padx=16, pady=4)
        tabview.add("Valorant")
        tabview.add("Fortnite")
        tabview.add("Apex & CS2")

        self._render_guide(tabview.tab("Valorant"), self.feature.profiles.GUIDES["valorant"], theme)
        self._render_guide(tabview.tab("Fortnite"), self.feature.profiles.GUIDES["fortnite"], theme)
        self._render_guide(tabview.tab("Apex & CS2"), self.feature.profiles.GUIDES["apex_cs2"], theme)

        # Journal
        SectionHeader(tab, "GAME BENCHMARK JOURNAL", "Track ping ranges, servers, and feelings across matches.").pack(fill="x", padx=16, pady=(14, 4))

        f_card = ctk.CTkFrame(tab, fg_color=theme["bg_card"], corner_radius=10)
        f_card.pack(fill="x", padx=16, pady=4)
        f_card.grid_columnconfigure((0, 1, 2, 3), weight=1)

        self.j_game = ctk.CTkEntry(f_card, placeholder_text="Game (e.g. Valorant)", font=get_font(10, "normal"))
        self.j_game.grid(row=0, column=0, padx=6, pady=10, sticky="ew")
        self.j_server = ctk.CTkEntry(f_card, placeholder_text="Server Region", font=get_font(10, "normal"))
        self.j_server.grid(row=0, column=1, padx=6, pady=10, sticky="ew")
        self.j_ping = ctk.CTkEntry(f_card, placeholder_text="Ping Range (ms)", font=get_font(10, "normal"))
        self.j_ping.grid(row=0, column=2, padx=6, pady=10, sticky="ew")

        ctk.CTkButton(f_card, text="💾 Save Note", font=get_font(10, "bold"), width=90, command=self._on_save_journal).grid(row=0, column=3, padx=6, pady=10, sticky="ew")

        self.notes_box = ctk.CTkFrame(tab, fg_color="transparent")
        self.notes_box.pack(fill="x", padx=16, pady=4)
        self._refresh_notes()

        return tab

    def _render_guide(self, parent, g: dict, theme: dict):
        ctk.CTkLabel(parent, text="HUD Telemetry Activation:", font=get_font(11, "bold"), text_color="#00f0ff").pack(anchor="w", padx=8, pady=(6, 2))
        for s in g.get("telemetry_setup", []):
            ctk.CTkLabel(parent, text=f"• {s}", font=get_font(10, "normal"), text_color=theme["text_primary"], wraplength=640, justify="left").pack(anchor="w", padx=14, pady=1)

        ctk.CTkLabel(parent, text="Anti-Stutter Settings:", font=get_font(11, "bold"), text_color="#00ff9f").pack(anchor="w", padx=8, pady=(8, 2))
        for opt in g.get("optimal_settings", [])[:3]:
            ctk.CTkLabel(parent, text=f"• {opt['setting']}: {opt['value']} — {opt['desc']}", font=get_font(10, "normal"), text_color=theme["text_secondary"]).pack(anchor="w", padx=14, pady=1)

    def _on_save_journal(self):
        g = self.j_game.get()
        s = self.j_server.get()
        p = self.j_ping.get()
        if g and s:
            self.feature.profiles.save_user_note(g, s, p, "Active", "Smooth", "")
            self.j_game.delete(0, "end")
            self.j_server.delete(0, "end")
            self.j_ping.delete(0, "end")
            self._refresh_notes()

    def _refresh_notes(self):
        for w in self.notes_box.winfo_children():
            w.destroy()
        notes = self.feature.profiles.get_user_notes()
        for n in notes:
            r = ctk.CTkFrame(self.notes_box, fg_color=get_theme()["bg_card"], corner_radius=8)
            r.pack(fill="x", pady=2)
            ctk.CTkLabel(r, text=f"🎯 {n.get('game')} | Server: {n.get('server')} | Ping: {n.get('ping_range')}", font=get_font(10, "bold"), text_color="#00f0ff").pack(side="left", padx=10, pady=6)
            ctk.CTkButton(r, text="✕", width=26, height=22, fg_color="#881337", command=lambda nid=n.get("id"): [self.feature.profiles.delete_user_note(nid), self._refresh_notes()]).pack(side="right", padx=10, pady=6)

    # ── Tab 6: Rollback ────────────────────────────────────────────────

    def _build_rollback_tab(self) -> ctk.CTkScrollableFrame:
        theme = get_theme()
        is_cyber = is_cyber_mode()
        tab = ctk.CTkScrollableFrame(self.content_frame, fg_color="transparent")
        tab.grid_columnconfigure(0, weight=1)

        h = ctk.CTkFrame(tab, fg_color="transparent")
        h.pack(fill="x", padx=16, pady=(10, 4))
        ctk.CTkLabel(h, text="🛡️ TARGETED ROLLBACK & AUDIT LEDGER" if is_cyber else "Rollback & State Recovery", font=get_font(18, "bold"), text_color="#00f0ff" if is_cyber else theme["text_title"]).pack(anchor="w")

        # Global Restore Hero Card
        h_card = ctk.CTkFrame(tab, fg_color="#090e23" if is_cyber else "#141414", corner_radius=12, border_width=2, border_color="#00f0ff" if is_cyber else "#333333")
        h_card.pack(fill="x", padx=16, pady=6)

        ctk.CTkLabel(h_card, text="RESTORE FEATURE-MANAGED SETTINGS (TARGETED ROLLBACK)", font=get_font(13, "bold"), text_color="#00f0ff").pack(anchor="w", padx=16, pady=(12, 2))
        ctk.CTkLabel(h_card, text=TERM_RESTORE_RESULT, font=get_font(11, "normal"), text_color=theme["text_secondary"]).pack(anchor="w", padx=16, pady=(0, 8))

        self.rb_stat = ctk.CTkLabel(h_card, text="Ready to restore.", font=get_font(11, "bold"), text_color="#00ff9f")
        self.rb_stat.pack(anchor="w", padx=16, pady=(0, 8))

        self.restore_btn = ctk.CTkButton(h_card, text="🔄 RESTORE FEATURE-MANAGED SETTINGS", font=get_font(12, "bold"), height=36, command=self._on_global_restore)
        self.restore_btn.pack(anchor="w", padx=16, pady=(0, 14))

        # Audit Timeline
        SectionHeader(tab, "RECORDED CHANGES & AUDIT HISTORY", "Granular timeline of applied, skipped, failed, and reverted changes.").pack(fill="x", padx=16, pady=(14, 4))

        self.timeline = ctk.CTkFrame(tab, fg_color="transparent")
        self.timeline.pack(fill="x", padx=16, pady=4)
        self._refresh_timeline()

        return tab

    def _on_global_restore(self):
        self.restore_btn.configure(state="disabled", text="Restoring & Verifying...")
        self.rb_stat.configure(text="Restoring settings and verifying post-restore state...", text_color="#fbbf24")
        def _prog(m):
            try:
                self.schedule_ui_callback(0, lambda: self.rb_stat.configure(text=m, text_color="#fbbf24"))
            except Exception:
                pass
        def _worker():

            try:
                from sentinel.service import SentinelService
                if SentinelService.get_instance().is_running():
                    try:
                        self.schedule_ui_callback(0, lambda: hasattr(self, 'tweak_feed') and self.tweak_feed.configure(text='Unavailable while Sentinel is active', text_color='#f43f5e'))
                    except Exception:
                        pass
                    return
            except Exception:
                pass
            res = self.feature.restore_previous_state(progress_callback=_prog)
            try:
                self.schedule_ui_callback(0, self._after_restore, res)
            except Exception:
                pass
        threading.Thread(target=_worker, daemon=True).start()

    def _after_restore(self, res: dict):
        self.restore_btn.configure(state="normal", text="🔄 RESTORE FEATURE-MANAGED SETTINGS")
        succ = len(res.get("successful", []))
        skip = len(res.get("skipped", []))
        fail = len(res.get("failed", []))
        reboot = res.get("reboot_required", False)

        parts = [res.get("message", TERM_RESTORE_RESULT)]
        if succ > 0:
            parts.append(f"Successful: {succ}")
            # Registry rollback reports whether a value was restored or deleted because it did not previously exist
            details = [s.get("details") for s in res.get("successful", []) if s.get("details")]
            if details:
                parts.append(f"({'; '.join(details)})")
        if skip > 0:
            skip_reasons = "; ".join([f"{s.get('setting')}: {s.get('reason')}" for s in res.get("skipped", []) if s.get("reason")])
            parts.append(f"Skipped: {skip} ({skip_reasons})" if skip_reasons else f"Skipped: {skip}")
        if fail > 0:
            fail_reasons = "; ".join([f"{f.get('setting')}: {f.get('reason')}" for f in res.get("failed", []) if f.get("reason")])
            parts.append(f"Failed: {fail} ({fail_reasons})" if fail_reasons else f"Failed: {fail}")
        if reboot:
            parts.append("Reboot Required")

        self.rb_stat.configure(
            text=" | ".join(parts),
            text_color="#00ff9f" if (fail == 0 and res.get("success", False)) else "#f43f5e"
        )
        self._refresh_timeline()

    def _refresh_timeline(self):
        for w in self.timeline.winfo_children():
            w.destroy()
        changes = self.feature.snapshots.get_change_log()
        if not changes:
            ctk.CTkLabel(self.timeline, text="// No recorded changes yet. System is at baseline.", font=get_font(11, "normal"), text_color=get_theme()["text_muted"]).pack(anchor="w", pady=6)
            return

        for c in reversed(changes):
            status = c.get("status", "applied")
            is_app = (status in ("applied", "verified"))
            row = ctk.CTkFrame(self.timeline, fg_color=get_theme()["bg_card"], corner_radius=8)
            row.pack(fill="x", pady=2)
            row.grid_columnconfigure(0, weight=1)
            row.grid_columnconfigure(1, weight=0)

            if status in ("applied", "verified"):
                icon = "🟢"
                title_color = "#00f0ff"
            elif status == "reverted":
                icon = "↩️"
                title_color = "#a78bfa"
            elif status == "skipped":
                icon = "⚠️"
                title_color = "#fbbf24"
            else: # failed / rollback_failed
                icon = "❌"
                title_color = "#f43f5e"

            info = ctk.CTkFrame(row, fg_color="transparent")
            info.grid(row=0, column=0, padx=10, pady=6, sticky="w")
            ctk.CTkLabel(info, text=f"{icon} {c.get('setting')} [{c.get('timestamp')}]", font=get_font(10, "bold"), text_color=title_color).pack(anchor="w")
            ctk.CTkLabel(info, text=f"Target: {c.get('target')} | Applied: {c.get('new_value')} | Status: {status.upper()}", font=get_font(9, "normal"), text_color=get_theme()["text_secondary"]).pack(anchor="w")

            if c.get("reason"):
                r_color = "#00ff9f" if status == "reverted" else ("#fbbf24" if status == "skipped" else "#f43f5e")
                ctk.CTkLabel(info, text=f"• Report / Reason: {c.get('reason')}", font=get_font(9, "normal"), text_color=r_color).pack(anchor="w")

            if is_app:
                ctk.CTkButton(row, text="Undo", width=60, height=24, font=get_font(9, "bold"), fg_color="#881337", command=lambda chg=c: self._undo_single(chg)).grid(row=0, column=1, padx=10, pady=6, sticky="e")

    def _undo_single(self, change: dict):
        res = self.feature.snapshots.restore_change(change)
        if res.get("success"):
            detail = res.get("details", "Restored")
            self.rb_stat.configure(text=f"Single rollback completed: {change.get('setting')} ({detail})", text_color="#00ff9f")
        elif res.get("skipped"):
            self.rb_stat.configure(text=f"Rollback skipped: {change.get('setting')} — {res.get('reason')}", text_color="#fbbf24")
        else:
            self.rb_stat.configure(text=f"Rollback failed: {change.get('setting')} — {res.get('reason')}", text_color="#f43f5e")
        self._refresh_timeline()

    def destroy(self):
        """Cancels background diagnostic threads, unregisters theme listener, and cleans up cleanly."""
        self._is_destroyed = True
        self._is_live_monitoring = False
        try:
            remove_theme_listener(self.apply_theme)
        except Exception:
            pass
        try:
            self.feature.cancel_active_diagnostics()
        except Exception:
            pass
        super().destroy()

    def apply_theme(self, is_cyber: bool):
        try:
            if not self.winfo_exists():
                return
        except Exception:
            return
        theme = get_theme()
        self.configure(fg_color=theme["bg_main"])
        if hasattr(self, "back_btn"):
            self.back_btn.configure(
                text="◄ BACK" if is_cyber else "◄ Back",
                fg_color="#1e293b" if is_cyber else "#333333",
                hover_color="#334155" if is_cyber else "#444444",
                text_color="#00f0ff" if is_cyber else "#ffffff"
            )
        if self.current_tab_key:
            self.switch_tab(self.current_tab_key)
