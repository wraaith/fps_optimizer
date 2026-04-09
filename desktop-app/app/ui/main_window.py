import customtkinter as ctk

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

        self.sidebar = ctk.CTkFrame(self, width=200, corner_radius=0)
        self.sidebar.grid(row=0, column=0, sticky="ns", padx=(0, 10), pady=0)

        self.sidebar_label = ctk.CTkLabel(
            self.sidebar,
            text="FPS Optimizer",
            font=ctk.CTkFont(size=18, weight="bold")
        )
        self.sidebar_label.pack(pady=(20, 10), padx=10)

        self.scan_button = ctk.CTkButton(
            self.sidebar,
            text="Scan",
            command=self.on_scan_click
        )
        self.scan_button.pack(pady=8, padx=10, fill="x")

        self.predict_button = ctk.CTkButton(
            self.sidebar,
            text="Predict",
            command=self.on_predict_click
        )
        self.predict_button.pack(pady=8, padx=10, fill="x")

        self.history_button = ctk.CTkButton(
            self.sidebar,
            text="History",
            command=self.on_history_click
        )
        self.history_button.pack(pady=8, padx=10, fill="x")

        self.main_frame = ctk.CTkFrame(self)
        self.main_frame.grid(row=0, column=1, sticky="nsew", padx=10, pady=10)

        self.main_label = ctk.CTkLabel(
            self.main_frame,
            text="Welcome to FPS Optimizer\nSelect an option from the left.",
            justify="left"
        )
        self.main_label.pack(padx=20, pady=20)

    def on_scan_click(self):
        self.main_label.configure(text="Scan clicked")

    def on_predict_click(self):
        self.main_label.configure(text="Predict clicked")

    def on_history_click(self):
        self.main_label.configure(text="History clicked")