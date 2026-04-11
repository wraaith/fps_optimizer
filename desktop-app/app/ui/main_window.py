import customtkinter as ctk
from ui.scan_view import ScanView

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

        # Sidebar
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

        # Main content area
        self.main_frame = ctk.CTkFrame(self)
        self.main_frame.grid(row=0, column=1, sticky="nsew", padx=10, pady=10)
        self.main_frame.grid_columnconfigure(0, weight=1)
        self.main_frame.grid_rowconfigure(0, weight=1)

        self.current_view = None

        # Show welcome screen by default
        self._show_welcome()

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