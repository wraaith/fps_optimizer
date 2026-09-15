# desktop-app/app/ui/scan_view.py

"""
Scan tab — shows system hardware information gathered by the scan service.
Supports both ultra-clean Performance Mode and glowing Cyber Gamer Mode.
"""

import threading
from typing import Optional, Dict, Any

import customtkinter as ctk
from services.system_scan import run_system_scan
from ui.theme_manager import is_cyber_mode, get_theme, get_font


def _safe(value, suffix: str = "", fallback: str = "Unknown") -> str:
    """Format a value for display, returning *fallback* for None / empty."""
    if value is None or value == "":
        return fallback
    return f"{value}{suffix}"


class ScanView(ctk.CTkFrame):
    def __init__(self, parent, **kwargs):
        theme = get_theme()
        super().__init__(parent, fg_color=theme["bg_main"], **kwargs)

        self._last_data: Optional[Dict[str, Any]] = None

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        # Title
        self.title = ctk.CTkLabel(
            self,
            text="⚡ SYSTEM TELEMETRY" if is_cyber_mode() else "System Scan",
            font=get_font(22, "bold"),
            text_color=theme["text_title"]
        )
        self.title.grid(row=0, column=0, pady=(20, 10))

        # Scan button
        self.scan_btn = ctk.CTkButton(
            self,
            text="⚡ RUN HARDWARE SCAN" if is_cyber_mode() else "Run Scan",
            font=get_font(14, "bold"),
            fg_color=theme["action_btn_fg"],
            hover_color=theme["action_btn_hover"],
            text_color=theme["action_btn_text"],
            height=40,
            corner_radius=20 if is_cyber_mode() else 8,
            command=self.run_scan
        )
        self.scan_btn.grid(row=1, column=0, pady=(0, 20))

        # Scrollable results frame
        self.results_frame = ctk.CTkScrollableFrame(self, fg_color=theme["bg_card"])
        self.results_frame.grid(row=2, column=0, padx=20, pady=10, sticky="nsew")
        self.results_frame.grid_columnconfigure(0, weight=1)

        # Placeholder label
        self.placeholder = ctk.CTkLabel(
            self.results_frame,
            text="Press 'Run Scan' to inspect system hardware.",
            font=get_font(14, "normal"),
            text_color="gray"
        )
        self.placeholder.grid(row=0, column=0, pady=40)

    def apply_theme(self, is_cyber: bool):
        """Re-style the scan view dynamically when mode changes."""
        theme = get_theme()
        self.configure(fg_color=theme["bg_main"])
        self.results_frame.configure(fg_color=theme["bg_card"])

        self.title.configure(
            text="⚡ SYSTEM TELEMETRY" if is_cyber else "System Scan",
            font=get_font(22, "bold"),
            text_color=theme["text_title"]
        )
        self.scan_btn.configure(
            text="⚡ RUN HARDWARE SCAN" if is_cyber else "Run Scan",
            font=get_font(14, "bold"),
            fg_color=theme["action_btn_fg"],
            hover_color=theme["action_btn_hover"],
            text_color=theme["action_btn_text"],
            corner_radius=20 if is_cyber else 8
        )

        if self._last_data:
            self._display_results(self._last_data)

    def run_scan(self):
        """Launch the scan in a background thread so the UI stays responsive."""
        theme = get_theme()
        self.scan_btn.configure(state="disabled", text="Analyzing Sensors...")
        
        # Clear frame and show loading animation
        for widget in self.results_frame.winfo_children():
            widget.destroy()
            
        self.loading_bar = ctk.CTkProgressBar(
            self.results_frame,
            mode="indeterminate",
            width=280,
            progress_color=theme["accent_cyan"]
        )
        self.loading_bar.grid(row=0, column=0, pady=(40, 10))
        self.loading_bar.start()
        
        self.loading_label = ctk.CTkLabel(
            self.results_frame, 
            text="Interrogating hardware controllers...",
            font=get_font(13, "normal"),
            text_color=theme["text_secondary"]
        )
        self.loading_label.grid(row=1, column=0)

        def _worker():
            try:
                data = run_system_scan()
                self._last_data = data
                # Schedule UI update back on the main thread
                try:
                    if self.winfo_exists():
                        self.after(0, self._display_results, data)
                except Exception:
                    pass
            except Exception as e:
                try:
                    if self.winfo_exists():
                        self.after(0, self._show_error, str(e))
                except Exception:
                    pass
            finally:
                try:
                    if self.winfo_exists():
                        self.after(0, lambda: self.scan_btn.configure(
                            state="normal",
                            text="⚡ RUN HARDWARE SCAN" if is_cyber_mode() else "Run Scan"
                        ))
                except Exception:
                    pass

        thread = threading.Thread(target=_worker, daemon=True)
        thread.start()

    def _display_results(self, data: dict):
        try:
            if not self.winfo_exists():
                return
        except Exception:
            return
        try:
            self._render_scan_data(data)
        except Exception:
            pass

    def _render_scan_data(self, data: dict):
        self._last_data = data
        for widget in self.results_frame.winfo_children():
            widget.destroy()

        theme = get_theme()
        cyber = is_cyber_mode()

        cpu = data.get("cpu", {})
        ram = data.get("ram", {})
        gpu = data.get("gpu", {})
        os_info = data.get("os", {})
        system = data.get("system", {})

        # Build display rows with safe formatting
        os_name = _safe(os_info.get("name"), fallback="")
        os_release = _safe(os_info.get("release"), fallback="")
        os_display = f"{os_name} {os_release}".strip() or "Unknown"

        phys = cpu.get("physical_cores")
        logi = cpu.get("logical_cores")
        if phys is not None and logi is not None:
            cores_display = f"{phys} Physical / {logi} Logical"
        elif logi is not None:
            cores_display = f"{logi} Logical"
        else:
            cores_display = "Unknown"

        cpu_threads = cpu.get("threads")
        threads_display = str(cpu_threads) if cpu_threads else "Unknown"

        cpu_tdp = cpu.get("tdp_w")
        if isinstance(cpu_tdp, (int, float)):
            cpu_tdp_display = f"{int(cpu_tdp)} W" if float(cpu_tdp).is_integer() else f"{cpu_tdp:.1f} W"
        else:
            cpu_tdp_display = "Unknown"

        cpu_usage = cpu.get("usage_percent")
        cpu_usage_display = f"{cpu_usage:.1f}%" if isinstance(cpu_usage, (int, float)) else "N/A"

        ram_total = ram.get("total_gb")
        ram_total_display = f"{ram_total:.1f} GB" if isinstance(ram_total, (int, float)) else "Unknown"

        ram_used = ram.get("used_gb")
        ram_used_display = f"{ram_used:.1f} GB" if isinstance(ram_used, (int, float)) else "Unknown"

        vram = gpu.get("vram_gb")
        vram_display = f"{vram} GB" if vram is not None else "Unknown"

        gpu_cores = gpu.get("cores")
        gpu_core_type = gpu.get("core_type")
        if gpu_cores and gpu_core_type:
            gpu_cores_display = f"{gpu_cores} ({gpu_core_type})"
        elif gpu_cores:
            gpu_cores_display = str(gpu_cores)
        else:
            gpu_cores_display = "Unknown"

        gpu_series = gpu.get("series")
        gpu_series_display = gpu_series if gpu_series else "Unknown"

        gpu_bw = gpu.get("bandwidth_gbs")
        gpu_bw_display = f"{gpu_bw} GB/s" if gpu_bw is not None else "Unknown"

        gpu_tdp = gpu.get("tdp_w")
        if isinstance(gpu_tdp, (int, float)):
            gpu_tdp_display = f"{int(gpu_tdp)} W" if float(gpu_tdp).is_integer() else f"{gpu_tdp:.1f} W"
        else:
            gpu_tdp_display = "Unknown"

        total_tdp = system.get("total_tdp_w")
        if isinstance(total_tdp, (int, float)):
            total_tdp_display = f"{int(total_tdp)} W" if float(total_tdp).is_integer() else f"{total_tdp:.1f} W"
        else:
            total_tdp_display = "Unknown"

        bottleneck = system.get("bottleneck_score")
        bottleneck_display = f"{bottleneck:.2f}" if isinstance(bottleneck, (int, float)) else str(bottleneck) if bottleneck is not None else "N/A"

        # ── Section definitions with cyber accents ──────────────
        cards = [
            ("⚡ OPERATING SYSTEM", theme["accent_cyan"], [
                ("OS Release", os_display),
            ]),
            ("🧠 PROCESSOR (CPU)", theme["accent_purple"] if cyber else "#ffffff", [
                ("Processor",   _safe(cpu.get("name"))),
                ("CPU Cores",   cores_display),
                ("CPU Threads", threads_display),
                ("CPU TDP",     cpu_tdp_display),
                ("Live Usage",  cpu_usage_display),
            ]),
            ("💾 MEMORY (RAM)", theme["accent_green"], [
                ("Total Installed", ram_total_display),
                ("Currently Used",  ram_used_display),
            ]),
            ("🎮 GRAPHICS (GPU)", theme["accent_cyan"] if cyber else "#ffffff", [
                ("Graphics Card", _safe(gpu.get("name"))),
                ("GPU Series",    gpu_series_display),
                ("Video Memory",  vram_display),
                ("Compute Cores", gpu_cores_display),
                ("Bandwidth",     gpu_bw_display),
                ("GPU Power Draw", gpu_tdp_display),
            ]),
            ("🔥 POWER & BOTTLENECK", theme["accent_amber"] if cyber else "#ffffff", [
                ("Total System Power", total_tdp_display),
                ("Bottleneck Ratio",   bottleneck_display),
            ]),
        ]

        if cyber:
            # ── Glassmorphism Cyber Cards ────────────────────────
            for i, (card_title, card_color, rows) in enumerate(cards):
                # Outer frosted glass pane
                card = ctk.CTkFrame(
                    self.results_frame,
                    fg_color=theme["bg_card_inner"],
                    border_color=theme["border_card"],
                    border_width=1,
                    corner_radius=theme["corner_radius"]
                )
                card.grid(row=i, column=0, padx=12, pady=7, sticky="ew")
                card.grid_columnconfigure(0, weight=0)
                card.grid_columnconfigure(1, weight=1)

                # Inner glass header strip — frosted highlight
                header_strip = ctk.CTkFrame(
                    card,
                    fg_color=theme["bg_glass"],
                    corner_radius=10,
                    height=32
                )
                header_strip.grid(row=0, column=0, columnspan=2, padx=10, pady=(10, 4), sticky="ew")
                header_strip.grid_propagate(False)
                header_strip.grid_columnconfigure(0, weight=1)
                header_strip.grid_rowconfigure(0, weight=1)

                ctk.CTkLabel(
                    header_strip,
                    text=card_title,
                    font=get_font(13, "bold"),
                    text_color=card_color,
                    anchor="w"
                ).grid(row=0, column=0, padx=12, sticky="w")

                for r_idx, (label, val) in enumerate(rows, start=1):
                    ctk.CTkLabel(
                        card,
                        text=label,
                        font=get_font(12, "bold"),
                        text_color=theme["text_secondary"],
                        anchor="w"
                    ).grid(row=r_idx, column=0, padx=(15, 8), pady=4, sticky="w")

                    ctk.CTkLabel(
                        card,
                        text=val,
                        font=get_font(13, "bold", is_stat=True),
                        text_color=theme["text_primary"],
                        anchor="e"
                    ).grid(row=r_idx, column=1, padx=(8, 15), pady=4, sticky="e")

                # Bottom padding
                ctk.CTkFrame(card, fg_color="transparent", height=6).grid(
                    row=len(rows) + 1, column=0, columnspan=2
                )
        else:
            # ── Clean Stealth Performance Rows ───────────────────
            row_idx = 0
            for card_title, _, rows in cards:
                clean_title = card_title.replace("⚡ ", "").replace("🧠 ", "").replace("💾 ", "").replace("🎮 ", "").replace("🔥 ", "")
                ctk.CTkLabel(
                    self.results_frame,
                    text=f"── {clean_title} ──",
                    font=get_font(13, "bold"),
                    text_color="#ffffff",
                    anchor="w"
                ).grid(row=row_idx, column=0, columnspan=2, padx=20, pady=(12, 4), sticky="w")
                row_idx += 1

                for label, val in rows:
                    ctk.CTkLabel(
                        self.results_frame,
                        text=label + ":",
                        font=get_font(13, "bold"),
                        text_color="#888888",
                        anchor="w"
                    ).grid(row=row_idx, column=0, padx=(20, 5), pady=3, sticky="w")

                    ctk.CTkLabel(
                        self.results_frame,
                        text=val,
                        font=get_font(13, "normal"),
                        text_color="#ffffff",
                        anchor="w"
                    ).grid(row=row_idx, column=1, padx=(5, 20), pady=3, sticky="w")
                    row_idx += 1

            self.results_frame.grid_columnconfigure(1, weight=1)

    def _show_error(self, msg: str):
        try:
            if not self.winfo_exists():
                return
            for widget in self.results_frame.winfo_children():
                widget.destroy()
            ctk.CTkLabel(
                self.results_frame,
                text=f"Error: {msg}",
                font=get_font(14, "bold"),
                text_color="#ff4d4f"
            ).grid(row=0, column=0, pady=20)
        except Exception:
            pass