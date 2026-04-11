# desktop-app/app/ui/scan_view.py

import customtkinter as ctk
from services.system_scan import run_system_scan


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
        self.scan_btn.configure(state="disabled", text="Scanning...")
        self.update()

        try:
            data = run_system_scan()
            self._display_results(data)
        except Exception as e:
            self._show_error(str(e))
        finally:
            self.scan_btn.configure(state="normal", text="Run Scan")

    def _display_results(self, data: dict):
        # Clear previous results
        for widget in self.results_frame.winfo_children():
            widget.destroy()

        cpu = data.get("cpu", {})
        ram = data.get("ram", {})
        gpu = data.get("gpu", {})
        os_info = data.get("os", {})

        rows = [
            ("OS",        f"{os_info.get('name')} {os_info.get('release')}"),
            ("CPU",       cpu.get("name", "Unknown")),
            ("CPU Cores", f"{cpu.get('physical_cores')} Physical / {cpu.get('logical_cores')} Logical"),
            ("CPU Usage", f"{cpu.get('usage_percent')}%"),
            ("RAM Total", f"{ram.get('total_gb')} GB"),
            ("RAM Used",  f"{ram.get('used_gb')} GB"),
            ("GPU",       gpu.get("name", "Unknown")),
            ("VRAM",      f"{gpu.get('vram_gb')} GB" if gpu.get('vram_gb') else "Unknown"),
            ("GPU Cores", f"{gpu.get('cores')} ({gpu.get('core_type')})" if gpu.get('cores') else "Unknown"),
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