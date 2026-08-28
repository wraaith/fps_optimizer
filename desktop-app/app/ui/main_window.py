import subprocess
import sys
import os

import customtkinter as ctk
from ui.scan_view import ScanView
from ui.overlay_settings_view import OverlaySettingsView


ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("dark-blue")


class MainWindow(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("FPS Optimizer")
        self.geometry("900x600")
        self.minsize(800, 500)

        self.grid_columnconfigure(0, weight=0)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self._overlay_proc = None
        self._overlay_settings_window = None

        self.overlay_settings = {
            "text_color": "#00ff00",
            "bg_mode": "transparent",
            "bg_opacity": 0.35,
            "font_size": 18,
            "scale": 1.0,
            "position": "top-right",
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
        self.sidebar = ctk.CTkFrame(self, width=200, corner_radius=0)
        self.sidebar.grid(row=0, column=0, sticky="ns", padx=(0, 10), pady=0)

        self.sidebar_label = ctk.CTkLabel(
            self.sidebar,
            text="FPS Optimizer",
            font=ctk.CTkFont(size=18, weight="bold")
        )
        self.sidebar_label.pack(pady=(20, 10), padx=10)

        self.scan_button = ctk.CTkButton(
            self.sidebar, text="Scan", command=self.show_scan
        )
        self.scan_button.pack(pady=8, padx=10, fill="x")

        self.predict_button = ctk.CTkButton(
            self.sidebar, text="Predict", command=self.show_predict
        )
        self.predict_button.pack(pady=8, padx=10, fill="x")

        self.history_button = ctk.CTkButton(
            self.sidebar, text="History", command=self.show_history
        )
        self.history_button.pack(pady=8, padx=10, fill="x")

        self.overlay_settings_btn = ctk.CTkButton(
            self.sidebar,
            text="Overlay Settings",
            command=self.show_overlay_settings
        )
        self.overlay_settings_btn.pack(pady=8, padx=10, fill="x")

        spacer = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        spacer.pack(fill="both", expand=True)

        self._overlay_status = ctk.CTkLabel(
            self.sidebar,
            text="Overlay: OFF",
            font=ctk.CTkFont(size=11),
            text_color="gray"
        )
        self._overlay_status.pack(pady=(0, 4), padx=10)

        self.overlay_btn = ctk.CTkButton(
            self.sidebar,
            text="▶  Start Overlay",
            fg_color="#1a7a3a",
            hover_color="#15602e",
            command=self._toggle_overlay
        )
        self.overlay_btn.pack(pady=(0, 10), padx=10, fill="x")

        self.close_btn = ctk.CTkButton(
            self.sidebar,
            text="✕  Close App",
            fg_color="#8b1a1a",
            hover_color="#6b1414",
            command=self._close_app
        )
        self.close_btn.pack(pady=(0, 16), padx=10, fill="x")

        # ── Main content area ──────────────────────────────────
        self.main_frame = ctk.CTkFrame(self)
        self.main_frame.grid(row=0, column=1, sticky="nsew", padx=10, pady=10)
        self.main_frame.grid_columnconfigure(0, weight=1)
        self.main_frame.grid_rowconfigure(0, weight=1)

        self.current_view = None
        self._show_welcome()

        self.protocol("WM_DELETE_WINDOW", self._close_app)

    # ── View switching ──────────────────────────────────────────

    def _clear_main(self):
        for widget in self.main_frame.winfo_children():
            widget.destroy()
        self.current_view = None

    def _show_welcome(self):
        self._clear_main()
        label = ctk.CTkLabel(
            self.main_frame,
            text="Welcome to FPS Optimizer\nSelect an option from the left.",
            font=ctk.CTkFont(size=16),
            justify="center"
        )
        label.grid(row=0, column=0, padx=20, pady=20)

    def show_scan(self):
        self._clear_main()
        self.current_view = ScanView(self.main_frame)
        self.current_view.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)

    def show_predict(self):
        self._clear_main()
        label = ctk.CTkLabel(
            self.main_frame,
            text="Predict view coming soon.",
            font=ctk.CTkFont(size=16)
        )
        label.grid(row=0, column=0, padx=20, pady=20)

    def show_history(self):
        self._clear_main()
        label = ctk.CTkLabel(
            self.main_frame,
            text="History view coming soon.",
            font=ctk.CTkFont(size=16)
        )
        label.grid(row=0, column=0, padx=20, pady=20)

    # ── Overlay settings popup ─────────────────────────────────

    def show_overlay_settings(self):
        self._clear_main()
        self.current_view = OverlaySettingsView(
            parent=self.main_frame,
            initial_settings=self.overlay_settings,
            on_apply=self.apply_overlay_settings
        )
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
            env["FPS_OVERLAY_TEXT_COLOR"] = self.overlay_settings["text_color"]
            env["FPS_OVERLAY_BG_MODE"] = self.overlay_settings["bg_mode"]
            env["FPS_OVERLAY_BG_OPACITY"] = str(self.overlay_settings["bg_opacity"])
            env["FPS_OVERLAY_FONT_SIZE"] = str(self.overlay_settings["font_size"])
            env["FPS_OVERLAY_SCALE"] = str(self.overlay_settings["scale"])
            env["FPS_OVERLAY_POSITION"] = self.overlay_settings["position"]
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
                creationflags=creationflags,
                env=env
            )

            self.overlay_btn.configure(
                text="■  Stop Overlay",
                fg_color="#8b6914",
                hover_color="#6b5010"
            )
            self._overlay_status.configure(text="Overlay: ON", text_color="#00e676")

        except Exception as e:
            self._overlay_status.configure(
                text=f"Error: {e}",
                text_color="red"
            )

    def _stop_overlay(self):
        if self._overlay_proc is not None:
            try:
                self._overlay_proc.terminate()
                self._overlay_proc.wait(timeout=3)
            except Exception:
                try:
                    self._overlay_proc.kill()
                except Exception:
                    pass
            self._overlay_proc = None
            
            # Hard-kill any lingering PresentMon background instances since terminate() skips overlay's atexit
            try:
                subprocess.run(["taskkill", "/F", "/IM", "PresentMon-2.5.1-x64.exe"],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=subprocess.CREATE_NO_WINDOW)
            except Exception:
                pass

        self.overlay_btn.configure(
            text="▶  Start Overlay",
            fg_color="#1a7a3a",
            hover_color="#15602e"
        )
        self._overlay_status.configure(text="Overlay: OFF", text_color="gray")

    def _close_app(self):
        self._stop_overlay()
        try:
            self.destroy()
        except Exception:
            pass
        os._exit(0)