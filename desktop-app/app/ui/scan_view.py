# desktop-app/app/ui/scan_view.py

"""
Scan tab — shows system hardware information gathered by the scan service.
"""

import threading

import customtkinter as ctk
from services.system_scan import run_system_scan


def _safe(value, suffix: str = "", fallback: str = "Unknown") -> str:
    """Format a value for display, returning *fallback* for None / empty."""
    if value is None or value == "":
        return fallback
    return f"{value}{suffix}"


class ScanView(ctk.CTkFrame):
    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)

        self.grid_columnconfigure(0, weight=1)

        # Title
        self.title = ctk.CTkLabel(
            self, text="System Scan",
            font=ctk.CTkFont(size=22, weight="bold")
        )
        self.title.grid(row=0, column=0, pady=(20, 10))

        # Scan button
        self.scan_btn = ctk.CTkButton(
            self, text="Run Scan",
            font=ctk.CTkFont(size=14),
            command=self.run_scan
        )
        self.scan_btn.grid(row=1, column=0, pady=(0, 20))

        # Results frame
        self.results_frame = ctk.CTkFrame(self)
        self.results_frame.grid(row=2, column=0, padx=20, pady=10, sticky="ew")
        self.results_frame.grid_columnconfigure(0, weight=1)

        # Placeholder label
        self.placeholder = ctk.CTkLabel(
            self.results_frame,
            text="Press 'Run Scan' to scan your system.",
            text_color="gray"
        )
        self.placeholder.grid(row=0, column=0, pady=20)

    def run_scan(self):
        """Launch the scan in a background thread so the UI stays responsive."""
        self.scan_btn.configure(state="disabled", text="Scanning...")

        def _worker():
            try:
                data = run_system_scan()
                # Schedule UI update back on the main thread
                self.after(0, self._display_results, data)
            except Exception as e:
                self.after(0, self._show_error, str(e))
            finally:
                self.after(0, lambda: self.scan_btn.configure(
                    state="normal", text="Run Scan"
                ))

        thread = threading.Thread(target=_worker, daemon=True)
        thread.start()

    def _display_results(self, data: dict):
        # DEBUG: print raw scan data to console
        import json
        print("=" * 50)
        print("SCAN DATA RECEIVED BY UI:")
        print(json.dumps(data, indent=2, default=str))
        print("=" * 50)

        # Clear previous results
        for widget in self.results_frame.winfo_children():
            widget.destroy()

        cpu = data.get("cpu", {})
        ram = data.get("ram", {})
        gpu = data.get("gpu", {})
        os_info = data.get("os", {})

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

        cpu_usage = cpu.get("usage_percent")
        cpu_usage_display = f"{cpu_usage}%" if cpu_usage is not None else "N/A"

        ram_total = ram.get("total_gb")
        ram_used = ram.get("used_gb")

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

        rows = [
            ("OS",        os_display),
            ("CPU",       _safe(cpu.get("name"))),
            ("CPU Cores", cores_display),
            ("CPU Usage", cpu_usage_display),
            ("RAM Total", f"{ram_total} GB" if ram_total is not None else "Unknown"),
            ("RAM Used",  f"{ram_used} GB" if ram_used is not None else "Unknown"),
            ("GPU",       _safe(gpu.get("name"))),
            ("VRAM",      vram_display),
            ("GPU Cores", gpu_cores_display),
        ]

        for i, (label, value) in enumerate(rows):
            ctk.CTkLabel(
                self.results_frame,
                text=label + ":",
                font=ctk.CTkFont(weight="bold"),
                anchor="w"
            ).grid(row=i, column=0, padx=(20, 5), pady=4, sticky="w")

            ctk.CTkLabel(
                self.results_frame,
                text=value,
                anchor="w"
            ).grid(row=i, column=1, padx=(5, 20), pady=4, sticky="w")

        self.results_frame.grid_columnconfigure(1, weight=1)

    def _show_error(self, msg: str):
        for widget in self.results_frame.winfo_children():
            widget.destroy()
        ctk.CTkLabel(
            self.results_frame,
            text=f"Error: {msg}",
            text_color="red"
        ).grid(row=0, column=0, pady=20)