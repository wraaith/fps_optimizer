import os
import subprocess
import sys
import threading

import customtkinter as ctk
import psutil
try:
    import pywinstyles
except ImportError:
    pywinstyles = None

from ui.scan_view import ScanView
from ui.overlay_settings_view import OverlaySettingsView
from optimize.optimize_view import OptimizeView
from ui.history_view import HistoryView
from ui.network_view import NetworkView
from ui.sentinel_view import SentinelView
from ui.theme_manager import is_cyber_mode, set_cyber_mode, get_theme, get_font, on_theme_changed


ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("dark-blue")


class MainWindow(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("FPS Optimizer // APEX ENGINE")
        w, h = 1060, 680
        screen_w = self.winfo_screenwidth()
        screen_h = self.winfo_screenheight()
        x = max(0, (screen_w - w) // 2)
        y = max(0, (screen_h - h) // 2)
        self.geometry(f"{w}x{h}+{x}+{y}")
        self.minsize(920, 580)
        
        # Initial theme
        theme = get_theme()
        self.configure(fg_color=theme["bg_root"])

        self.grid_columnconfigure(0, weight=0)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self._overlay_proc = None
        self._overlay_settings_window = None

        self.overlay_settings = {
            "theme": "minimalist_dark",
            "text_color": "#00ff00",
            "bg_mode": "solid",
            "bg_opacity": 0.92,
            "font_size": 14,
            "scale": 1.0,
            "position": "top-right",
            "layout": "vertical",
            "click_through": True,
            "show_fps": True,
            "show_gpu": True,
            "show_gpu_temp": True,
            "show_gpu_pwr": True,
            "show_cpu": True,
            "show_cpu_temp": True,
            "show_cpu_pwr": True,
            "show_ram": True,
        }

        # ── Sidebar ─────────────────────────────────────────────
        is_cyber = is_cyber_mode()
        self.sidebar = ctk.CTkFrame(
            self,
            width=215,
            corner_radius=0,
            fg_color=theme["bg_sidebar"],
            border_width=1 if is_cyber else 0,
            border_color="#14224a" if is_cyber else "#1e1e1e"
        )
        self.sidebar.grid(row=0, column=0, sticky="ns", padx=0, pady=0)

        # Branding
        self.sidebar_header_frame = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        self.sidebar_header_frame.pack(pady=(16, 6), padx=14, fill="x")

        self.sidebar_label = ctk.CTkLabel(
            self.sidebar_header_frame,
            text="⚡ CYBER MATRIX" if is_cyber else "FPS OPTIMIZER",
            font=get_font(18, "bold"),
            text_color=theme["text_title"]
        )
        self.sidebar_label.pack(anchor="w")

        self.sidebar_sublabel = ctk.CTkLabel(
            self.sidebar_header_frame,
            text="// APEX ENGINE v2.4" if is_cyber else "Performance Suite",
            font=get_font(10, "bold"),
            text_color=theme["accent_cyan"] if is_cyber else theme["text_secondary"]
        )
        self.sidebar_sublabel.pack(anchor="w")

        # ── Cyber UI Mode Switch ──
        self.cyber_switch = ctk.CTkSwitch(
            self.sidebar,
            text="⚡ CYBER OVERDRIVE" if is_cyber else "⚡ Cyber Mode",
            font=get_font(11, "bold"),
            progress_color="#00f0ff",
            button_color="#ffffff",
            button_hover_color="#00d4e5",
            command=self._on_cyber_toggle
        )
        self.cyber_switch.pack(pady=(0, 14), padx=14, anchor="w")
        if is_cyber:
            self.cyber_switch.select()
        else:
            self.cyber_switch.deselect()

        self.nav_buttons = []
        self._active_nav_btn = None

        self.scan_button = ctk.CTkButton(
            self.sidebar, text="[01]  SYSTEM TELEMETRY" if is_cyber else "Scan Hardware", command=self.show_scan,
            fg_color=theme["nav_btn_fg"], hover_color=theme["nav_btn_hover"],
            text_color=theme["nav_btn_text"], font=get_font(12, "bold"), height=36, anchor="w"
        )
        self.scan_button.pack(pady=3, padx=10, fill="x")
        self.nav_buttons.append(self.scan_button)

        self.optimize_button = ctk.CTkButton(
            self.sidebar, text="[02]  GAME BOOSTER" if is_cyber else "Game Booster", command=self.show_optimize,
            fg_color=theme["nav_btn_fg"], hover_color=theme["nav_btn_hover"],
            text_color=theme["nav_btn_text"], font=get_font(12, "bold"), height=36, anchor="w"
        )
        self.optimize_button.pack(pady=3, padx=10, fill="x")
        self.nav_buttons.append(self.optimize_button)

        self.history_button = ctk.CTkButton(
            self.sidebar, text="[03]  TELEMETRY LOGS" if is_cyber else "History", command=self.show_history,
            fg_color=theme["nav_btn_fg"], hover_color=theme["nav_btn_hover"],
            text_color=theme["nav_btn_text"], font=get_font(12, "bold"), height=36, anchor="w"
        )
        self.history_button.pack(pady=3, padx=10, fill="x")
        self.nav_buttons.append(self.history_button)

        self.overlay_settings_btn = ctk.CTkButton(
            self.sidebar,
            text="[04]  HUD OVERLAY CONFIG" if is_cyber else "Overlay Settings",
            command=self.show_overlay_settings,
            fg_color=theme["nav_btn_fg"], hover_color=theme["nav_btn_hover"],
            text_color=theme["nav_btn_text"], font=get_font(12, "bold"), height=36, anchor="w"
        )
        self.overlay_settings_btn.pack(pady=3, padx=10, fill="x")
        self.nav_buttons.append(self.overlay_settings_btn)

        self.network_button = ctk.CTkButton(
            self.sidebar,
            text="[05]  NETWORK STABILIZER" if is_cyber else "Network Stabilizer",
            command=self.show_network,
            fg_color=theme["nav_btn_fg"], hover_color=theme["nav_btn_hover"],
            text_color=theme["nav_btn_text"], font=get_font(12, "bold"), height=36, anchor="w"
        )
        self.network_button.pack(pady=3, padx=10, fill="x")
        self.nav_buttons.append(self.network_button)

        self.sentinel_button = ctk.CTkButton(
            self.sidebar,
            text="[06]  UNIVERSAL SENTINEL" if is_cyber else "Universal Sentinel",
            command=self.show_sentinel,
            fg_color=theme["nav_btn_fg"], hover_color=theme["nav_btn_hover"],
            text_color=theme["nav_btn_text"], font=get_font(12, "bold"), height=36, anchor="w"
        )
        self.sentinel_button.pack(pady=3, padx=10, fill="x")
        self.nav_buttons.append(self.sentinel_button)

        spacer = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        spacer.pack(fill="both", expand=True)

        # ── Sidebar HUD Cockpit Module ──
        self.overlay_card = ctk.CTkFrame(
            self.sidebar,
            fg_color=theme["bg_card"],
            corner_radius=10,
            border_width=1,
            border_color="#1a2b5e" if is_cyber else "#1e1e1e"
        )
        self.overlay_card.pack(pady=(0, 14), padx=10, fill="x")

        self._overlay_status = ctk.CTkLabel(
            self.overlay_card,
            text="○ HUD: STANDBY" if is_cyber else "Overlay: OFF",
            font=get_font(11, "bold"),
            text_color=theme["text_secondary"]
        )
        self._overlay_status.pack(pady=(8, 4), padx=10)

        self.overlay_btn = ctk.CTkButton(
            self.overlay_card,
            text="⚡ ENGAGE HUD" if is_cyber else "Start Overlay",
            fg_color=theme["action_btn_fg"],
            hover_color=theme["action_btn_hover"],
            text_color=theme["action_btn_text"],
            font=get_font(12, "bold"),
            height=34,
            corner_radius=17 if is_cyber else 8,
            command=self._toggle_overlay
        )
        self.overlay_btn.pack(pady=(0, 8), padx=10, fill="x")


        # ── Main content area ──────────────────────────────────
        self.main_frame = ctk.CTkFrame(self, fg_color=theme["bg_main"])
        self.main_frame.grid(row=0, column=1, sticky="nsew", padx=10, pady=10)
        self.main_frame.grid_columnconfigure(0, weight=1)
        self.main_frame.grid_rowconfigure(0, weight=1)

        self.current_view = None
        
        # Cleanup any orphaned overlays from previous crashes
        self._stop_overlay()
        
        # Default directly to Game Booster dashboard
        self.show_optimize()

        # Listen for global theme changes
        on_theme_changed(self._apply_theme_to_ui)

        self.protocol("WM_DELETE_WINDOW", self._close_app)

    def _on_cyber_toggle(self):
        enabled = bool(self.cyber_switch.get())
        set_cyber_mode(enabled)

    def _set_active_nav_button(self, active_btn):
        self._active_nav_btn = active_btn
        is_cyber = is_cyber_mode()

        nav_labels = {
            self.scan_button: ("[01]  SYSTEM TELEMETRY" if is_cyber else "Scan Hardware"),
            self.optimize_button: ("[02]  GAME BOOSTER" if is_cyber else "Game Booster"),
            self.history_button: ("[03]  TELEMETRY LOGS" if is_cyber else "History"),
            self.overlay_settings_btn: ("[04]  HUD OVERLAY CONFIG" if is_cyber else "Overlay Settings"),
            self.network_button: ("[05]  NETWORK STABILIZER" if is_cyber else "Network Stabilizer"),
            self.sentinel_button: ("[06]  UNIVERSAL SENTINEL" if is_cyber else "Universal Sentinel"),
        }

        for btn in self.nav_buttons:
            base_label = nav_labels.get(btn, btn.cget("text"))
            if btn == active_btn:
                if is_cyber:
                    btn.configure(
                        text=f"► {base_label}",
                        fg_color="#0d183d",
                        border_width=1,
                        border_color="#00f0ff",
                        text_color="#00f0ff"
                    )
                else:
                    btn.configure(
                        text=base_label,
                        fg_color="#1f1f1f",
                        border_width=0,
                        text_color="#ffffff"
                    )
            else:
                if is_cyber:
                    btn.configure(
                        text=base_label,
                        fg_color="transparent",
                        border_width=0,
                        text_color="#8193b8"
                    )
                else:
                    btn.configure(
                        text=base_label,
                        fg_color="transparent",
                        border_width=0,
                        text_color="#888888"
                    )

    def _apply_theme_to_ui(self, is_cyber: bool):
        theme = get_theme()
        self.configure(fg_color=theme["bg_root"])
        self.sidebar.configure(
            fg_color=theme["bg_sidebar"],
            border_color="#14224a" if is_cyber else "#1e1e1e",
            border_width=1 if is_cyber else 0
        )
        self.sidebar_label.configure(
            text="⚡ CYBER MATRIX" if is_cyber else "FPS OPTIMIZER",
            font=get_font(18, "bold"),
            text_color=theme["text_title"]
        )
        self.sidebar_sublabel.configure(
            text="// APEX ENGINE v2.4" if is_cyber else "Performance Suite",
            font=get_font(10, "bold"),
            text_color=theme["accent_cyan"] if is_cyber else theme["text_secondary"]
        )
        self.cyber_switch.configure(
            text="⚡ CYBER OVERDRIVE" if is_cyber else "⚡ Cyber Mode",
            progress_color="#00f0ff"
        )
        if is_cyber:
            self.cyber_switch.select()
        else:
            self.cyber_switch.deselect()
        self.overlay_card.configure(
            fg_color=theme["bg_card"],
            border_color="#1a2b5e" if is_cyber else "#1e1e1e"
        )
        self.main_frame.configure(fg_color=theme["bg_main"])

        # Re-apply active nav button styling
        self._set_active_nav_button(self._active_nav_btn)

        running = self._is_overlay_running()
        if running:
            self._overlay_status.configure(
                text="● HUD: ONLINE" if is_cyber else "Overlay: ON",
                text_color="#00ff9f" if is_cyber else "#00ff00"
            )
            self.overlay_btn.configure(
                text="⏹ TERMINATE HUD" if is_cyber else "Stop Overlay",
                fg_color="#e11d48" if is_cyber else "#cc3333",
                hover_color="#f43f5e" if is_cyber else "#ff4444",
                text_color="#ffffff",
                corner_radius=17 if is_cyber else 8
            )
        else:
            self._overlay_status.configure(
                text="○ HUD: STANDBY" if is_cyber else "Overlay: OFF",
                text_color=theme["text_secondary"]
            )
            self.overlay_btn.configure(
                text="⚡ ENGAGE HUD" if is_cyber else "Start Overlay",
                fg_color=theme["action_btn_fg"],
                hover_color=theme["action_btn_hover"],
                text_color=theme["action_btn_text"],
                corner_radius=17 if is_cyber else 8
            )

        # Apply Windows glassmorphism effects
        self._apply_window_effects(is_cyber)

        # Notify active view if it implements apply_theme
        if self.current_view and hasattr(self.current_view, "apply_theme"):
            self.current_view.apply_theme(is_cyber)

    def _apply_window_effects(self, is_cyber: bool):
        """Apply native Windows titlebar theme safely without canvas flickering."""
        if pywinstyles is None:
            return
        try:
            if not self.winfo_exists():
                return
            # We style native titlebar colors directly. Full-window acrylic is omitted because
            # Tkinter lacks sub-widget alpha compositing, which causes redraw trails and black corners.
            if is_cyber:
                try:
                    pywinstyles.change_header_color(self, color="#04060e")
                    pywinstyles.change_border_color(self, color="#00f0ff")
                except Exception:
                    pass
            else:
                try:
                    pywinstyles.change_header_color(self, color="#0a0a0a")
                    pywinstyles.change_border_color(self, color="#1e1e1e")
                except Exception:
                    pass
        except Exception:
            pass  # Graceful fallback on older Windows versions

    # ── View switching ──────────────────────────────────────────

    def _clear_main(self):
        if self.current_view is not None and hasattr(self.current_view, "destroy"):
            try:
                self.current_view.destroy()
            except Exception:
                pass
        for widget in self.main_frame.winfo_children():
            try:
                widget.destroy()
            except Exception:
                pass
        self.current_view = None

    def show_scan(self):
        self._clear_main()
        self._set_active_nav_button(self.scan_button)
        self.current_view = ScanView(self.main_frame)
        self.current_view.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)

    def show_optimize(self):
        self._clear_main()
        self._set_active_nav_button(self.optimize_button)
        self.current_view = OptimizeView(self.main_frame)
        self.current_view.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)

    def show_history(self):
        self._clear_main()
        self._set_active_nav_button(self.history_button)
        self.current_view = HistoryView(self.main_frame)
        self.current_view.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)

    def show_network(self):
        self._clear_main()
        self._set_active_nav_button(self.network_button)
        self.current_view = NetworkView(self.main_frame)
        self.current_view.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)

    def show_sentinel(self):
        from sentinel.service import SentinelService
        self._clear_main()
        self._set_active_nav_button(self.sentinel_button)
        self.current_view = SentinelView(self.main_frame, service=SentinelService())
        self.current_view.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)

    # ── Overlay settings popup ─────────────────────────────────

    def show_overlay_settings(self):
        self._clear_main()
        self._set_active_nav_button(self.overlay_settings_btn)
        self.current_view = OverlaySettingsView(
            parent=self.main_frame,
            initial_settings=self.overlay_settings,
            on_apply=self.apply_overlay_settings
        )
        self.current_view.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)

    def show_network(self):
        self._clear_main()
        self._set_active_nav_button(self.network_button)
        self.current_view = NetworkView(self.main_frame, on_back=self.show_optimize)
        self.current_view.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)

    def apply_overlay_settings(self, settings: dict):
        self.overlay_settings = settings

        if self._is_overlay_running():
            # Auto-restart overlay so new settings take effect immediately
            self._stop_overlay()
            self._start_overlay()
        else:
            self._overlay_status.configure(
                text="Overlay settings saved",
                text_color="#4fc3f7"
            )

    # ── Overlay management ──────────────────────────────────────

    def _is_overlay_running(self) -> bool:
        return self._overlay_proc is not None and self._overlay_proc.poll() is None

    def _toggle_overlay(self):
        if self._is_overlay_running():
            self._stop_overlay()
        else:
            self._start_overlay()

    def _start_overlay(self):
        if self._is_overlay_running():
            return

        main_py = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "main.py"
        )

        try:
            env = os.environ.copy()
            env["FPS_OVERLAY_THEME"] = self.overlay_settings.get("theme", "minimalist_dark")
            env["FPS_OVERLAY_TEXT_COLOR"] = self.overlay_settings["text_color"]
            env["FPS_OVERLAY_BG_MODE"] = self.overlay_settings["bg_mode"]
            env["FPS_OVERLAY_BG_OPACITY"] = str(self.overlay_settings["bg_opacity"])
            env["FPS_OVERLAY_FONT_SIZE"] = str(self.overlay_settings["font_size"])
            env["FPS_OVERLAY_SCALE"] = str(self.overlay_settings["scale"])
            env["FPS_OVERLAY_POSITION"] = self.overlay_settings["position"]
            env["FPS_OVERLAY_LAYOUT"] = self.overlay_settings.get("layout", "vertical")
            env["FPS_OVERLAY_CLICK_THROUGH"] = str(self.overlay_settings["click_through"])
            env["FPS_OVERLAY_SHOW_FPS"] = str(self.overlay_settings["show_fps"])
            env["FPS_OVERLAY_SHOW_GPU"] = str(self.overlay_settings["show_gpu"])
            env["FPS_OVERLAY_SHOW_GPU_TEMP"] = str(self.overlay_settings["show_gpu_temp"])
            env["FPS_OVERLAY_SHOW_GPU_PWR"] = str(self.overlay_settings["show_gpu_pwr"])
            env["FPS_OVERLAY_SHOW_CPU"] = str(self.overlay_settings["show_cpu"])
            env["FPS_OVERLAY_SHOW_CPU_TEMP"] = str(self.overlay_settings["show_cpu_temp"])
            env["FPS_OVERLAY_SHOW_CPU_PWR"] = str(self.overlay_settings["show_cpu_pwr"])
            env["FPS_OVERLAY_SHOW_RAM"] = str(self.overlay_settings["show_ram"])

            creationflags = 0
            if os.name == "nt":
                creationflags = subprocess.CREATE_NO_WINDOW

            self._overlay_proc = subprocess.Popen(
                [sys.executable, main_py, "--overlay"],
                cwd=os.path.dirname(main_py),
                creationflags=creationflags,
                env=env
            )

            self._apply_theme_to_ui(is_cyber_mode())

        except Exception as e:
            self._overlay_status.configure(
                text=f"Error: {e}",
                text_color="red"
            )

    def _stop_overlay(self, async_orphan_cleanup: bool = True):
        if self._overlay_proc is not None:
            try:
                self._overlay_proc.terminate()
                try:
                    self._overlay_proc.wait(timeout=0.6)
                except Exception:
                    self._overlay_proc.kill()
            except Exception:
                pass
            self._overlay_proc = None

        def _orphan_cleanup_worker():
            try:
                current_pid = os.getpid()
                protected_pids = {current_pid}
                try:
                    p = psutil.Process(current_pid)
                    if p.parent():
                        protected_pids.add(p.parent().pid)
                except Exception:
                    pass

                for proc in psutil.process_iter(['pid', 'name']):
                    try:
                        pid = proc.info.get('pid')
                        pname = (proc.info.get('name') or '').lower()
                        if pid not in protected_pids and 'python' in pname:
                            cmdline = proc.cmdline()
                            if any('--overlay' in arg for arg in cmdline):
                                proc.terminate()
                    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                        pass
            except Exception:
                pass

            try:
                subprocess.run(
                    ["taskkill", "/F", "/IM", "PresentMon-2.5.1-x64.exe"],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)
                )
            except Exception:
                pass

        if async_orphan_cleanup:
            threading.Thread(target=_orphan_cleanup_worker, daemon=True).start()
        else:
            _orphan_cleanup_worker()

        try:
            theme = get_theme()
            self.overlay_btn.configure(
                text="▶  Start Overlay",
                fg_color=theme["action_btn_fg"],
                hover_color=theme["action_btn_hover"],
                text_color=theme["action_btn_text"]
            )
            self._overlay_status.configure(text="Overlay: OFF", text_color="gray")
        except Exception:
            pass

    def _close_app(self):
        # 1. Immediately withdraw the window so closing feels instantaneous (< 1ms)
        try:
            self.withdraw()
        except Exception:
            pass

        # 2. Stop active view background telemetry/threads cleanly
        try:
            if self.current_view and hasattr(self.current_view, "destroy"):
                self.current_view.destroy()
                self.current_view = None
        except Exception:
            pass

        # 3. Stop AI Sentinel service
        try:
            from optimize.ai_boost_service import get_ai_boost_service
            get_ai_boost_service().stop()
        except Exception:
            pass

        # 4. Stop overlay process quickly
        try:
            self._stop_overlay(async_orphan_cleanup=False)
        except Exception:
            pass

        # 5. Clean Tkinter destruction
        try:
            self.quit()
        except Exception:
            pass
        try:
            self.destroy()
        except Exception:
            pass