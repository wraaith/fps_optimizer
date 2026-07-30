import customtkinter as ctk


class OverlaySettingsWindow(ctk.CTkToplevel):
    def __init__(self, parent, initial_settings: dict, on_apply):
        super().__init__(parent)

        self.parent = parent
        self.on_apply = on_apply

        self.title("Overlay Settings")
        self.geometry("520x760")
        self.minsize(480, 700)

        self.attributes("-topmost", True)
        self.focus()

        self.grid_columnconfigure(0, weight=1)

        self.settings = dict(initial_settings)

        self.title_label = ctk.CTkLabel(
            self,
            text="Overlay Settings",
            font=ctk.CTkFont(size=24, weight="bold")
        )
        self.title_label.grid(row=0, column=0, padx=20, pady=(20, 10), sticky="w")

        self.desc_label = ctk.CTkLabel(
            self,
            text="Customize overlay appearance and visible metrics.",
            font=ctk.CTkFont(size=14),
            text_color="gray"
        )
        self.desc_label.grid(row=1, column=0, padx=20, pady=(0, 15), sticky="w")

        self.content = ctk.CTkScrollableFrame(self)
        self.content.grid(row=2, column=0, padx=20, pady=10, sticky="nsew")
        self.grid_rowconfigure(2, weight=1)
        self.content.grid_columnconfigure(0, weight=1)

        row = 0

        # Text color
        ctk.CTkLabel(
            self.content,
            text="Text Color",
            font=ctk.CTkFont(size=16, weight="bold")
        ).grid(row=row, column=0, padx=10, pady=(10, 6), sticky="w")
        row += 1

        self.text_color_segment = ctk.CTkSegmentedButton(
            self.content,
            values=["Green", "White", "Yellow", "Cyan", "Red"]
        )
        self.text_color_segment.grid(row=row, column=0, padx=10, pady=(0, 14), sticky="ew")
        row += 1

        # Background mode
        ctk.CTkLabel(
            self.content,
            text="Background Mode",
            font=ctk.CTkFont(size=16, weight="bold")
        ).grid(row=row, column=0, padx=10, pady=(10, 6), sticky="w")
        row += 1

        self.bg_mode_segment = ctk.CTkSegmentedButton(
            self.content,
            values=["Transparent", "Solid"]
        )
        self.bg_mode_segment.grid(row=row, column=0, padx=10, pady=(0, 14), sticky="ew")
        row += 1

        # Background opacity
        self.bg_opacity_label = ctk.CTkLabel(
            self.content,
            text="Background Opacity: 0.35",
            font=ctk.CTkFont(size=16, weight="bold")
        )
        self.bg_opacity_label.grid(row=row, column=0, padx=10, pady=(10, 6), sticky="w")
        row += 1

        self.bg_opacity_slider = ctk.CTkSlider(
            self.content,
            from_=0.0,
            to=1.0,
            number_of_steps=20,
            command=self._on_bg_opacity_change
        )
        self.bg_opacity_slider.grid(row=row, column=0, padx=10, pady=(0, 14), sticky="ew")
        row += 1

        # Font size
        self.font_size_label = ctk.CTkLabel(
            self.content,
            text="Font Size: 18",
            font=ctk.CTkFont(size=16, weight="bold")
        )
        self.font_size_label.grid(row=row, column=0, padx=10, pady=(10, 6), sticky="w")
        row += 1

        self.font_size_slider = ctk.CTkSlider(
            self.content,
            from_=12,
            to=32,
            number_of_steps=20,
            command=self._on_font_size_change
        )
        self.font_size_slider.grid(row=row, column=0, padx=10, pady=(0, 14), sticky="ew")
        row += 1

        # Scale
        self.scale_label = ctk.CTkLabel(
            self.content,
            text="Overlay Scale: 1.00",
            font=ctk.CTkFont(size=16, weight="bold")
        )
        self.scale_label.grid(row=row, column=0, padx=10, pady=(10, 6), sticky="w")
        row += 1

        self.scale_slider = ctk.CTkSlider(
            self.content,
            from_=0.8,
            to=2.0,
            number_of_steps=12,
            command=self._on_scale_change
        )
        self.scale_slider.grid(row=row, column=0, padx=10, pady=(0, 14), sticky="ew")
        row += 1

        # Position
        ctk.CTkLabel(
            self.content,
            text="Position",
            font=ctk.CTkFont(size=16, weight="bold")
        ).grid(row=row, column=0, padx=10, pady=(10, 6), sticky="w")
        row += 1

        self.position_segment = ctk.CTkSegmentedButton(
            self.content,
            values=["Top Left", "Top Right", "Bottom Left", "Bottom Right"]
        )
        self.position_segment.grid(row=row, column=0, padx=10, pady=(0, 14), sticky="ew")
        row += 1

        # Click-through
        ctk.CTkLabel(
            self.content,
            text="Overlay Behavior",
            font=ctk.CTkFont(size=16, weight="bold")
        ).grid(row=row, column=0, padx=10, pady=(10, 6), sticky="w")
        row += 1

        self.click_through_checkbox = ctk.CTkCheckBox(
            self.content,
            text="Enable click-through"
        )
        self.click_through_checkbox.grid(row=row, column=0, padx=10, pady=(0, 14), sticky="w")
        row += 1

        # Metric toggles
        ctk.CTkLabel(
            self.content,
            text="Visible Metrics",
            font=ctk.CTkFont(size=16, weight="bold")
        ).grid(row=row, column=0, padx=10, pady=(10, 6), sticky="w")
        row += 1

        self.show_fps_checkbox = ctk.CTkCheckBox(self.content, text="Show FPS")
        self.show_fps_checkbox.grid(row=row, column=0, padx=10, pady=4, sticky="w")
        row += 1

        self.show_gpu_checkbox = ctk.CTkCheckBox(self.content, text="Show GPU")
        self.show_gpu_checkbox.grid(row=row, column=0, padx=10, pady=4, sticky="w")
        row += 1

        self.show_cpu_checkbox = ctk.CTkCheckBox(self.content, text="Show CPU")
        self.show_cpu_checkbox.grid(row=row, column=0, padx=10, pady=4, sticky="w")
        row += 1

        self.show_ram_checkbox = ctk.CTkCheckBox(self.content, text="Show RAM")
        self.show_ram_checkbox.grid(row=row, column=0, padx=10, pady=(4, 14), sticky="w")
        row += 1

        # Bottom buttons
        self.button_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.button_frame.grid(row=3, column=0, padx=20, pady=(10, 20), sticky="ew")
        self.button_frame.grid_columnconfigure((0, 1), weight=1)

        self.apply_button = ctk.CTkButton(
            self.button_frame,
            text="Apply",
            command=self.apply_settings
        )
        self.apply_button.grid(row=0, column=0, padx=(0, 8), sticky="ew")

        self.close_button = ctk.CTkButton(
            self.button_frame,
            text="Close",
            fg_color="#444",
            hover_color="#333",
            command=self.destroy
        )
        self.close_button.grid(row=0, column=1, padx=(8, 0), sticky="ew")

        self._load_initial_values()

    def _load_initial_values(self):
        color_map = {
            "#00ff00": "Green",
            "#ffffff": "White",
            "#ffff00": "Yellow",
            "#00ffff": "Cyan",
            "#ff4d4f": "Red",
        }
        reverse_bg_map = {
            "transparent": "Transparent",
            "solid": "Solid",
        }
        reverse_position_map = {
            "top-left": "Top Left",
            "top-right": "Top Right",
            "bottom-left": "Bottom Left",
            "bottom-right": "Bottom Right",
        }

        self.text_color_segment.set(color_map.get(self.settings["text_color"], "Green"))
        self.bg_mode_segment.set(reverse_bg_map.get(self.settings["bg_mode"], "Transparent"))
        self.bg_opacity_slider.set(float(self.settings["bg_opacity"]))
        self.font_size_slider.set(int(self.settings["font_size"]))
        self.scale_slider.set(float(self.settings["scale"]))
        self.position_segment.set(reverse_position_map.get(self.settings["position"], "Top Right"))

        self._on_bg_opacity_change(float(self.settings["bg_opacity"]))
        self._on_font_size_change(float(self.settings["font_size"]))
        self._on_scale_change(float(self.settings["scale"]))

        if self.settings["click_through"]:
            self.click_through_checkbox.select()
        else:
            self.click_through_checkbox.deselect()

        if self.settings["show_fps"]:
            self.show_fps_checkbox.select()
        else:
            self.show_fps_checkbox.deselect()

        if self.settings["show_gpu"]:
            self.show_gpu_checkbox.select()
        else:
            self.show_gpu_checkbox.deselect()

        if self.settings["show_cpu"]:
            self.show_cpu_checkbox.select()
        else:
            self.show_cpu_checkbox.deselect()

        if self.settings["show_ram"]:
            self.show_ram_checkbox.select()
        else:
            self.show_ram_checkbox.deselect()

    def _on_bg_opacity_change(self, value):
        self.bg_opacity_label.configure(text=f"Background Opacity: {float(value):.2f}")

    def _on_font_size_change(self, value):
        self.font_size_label.configure(text=f"Font Size: {int(float(value))}")

    def _on_scale_change(self, value):
        self.scale_label.configure(text=f"Overlay Scale: {float(value):.2f}")

    def apply_settings(self):
        color_map = {
            "Green": "#00ff00",
            "White": "#ffffff",
            "Yellow": "#ffff00",
            "Cyan": "#00ffff",
            "Red": "#ff4d4f",
        }
        bg_map = {
            "Transparent": "transparent",
            "Solid": "solid",
        }
        position_map = {
            "Top Left": "top-left",
            "Top Right": "top-right",
            "Bottom Left": "bottom-left",
            "Bottom Right": "bottom-right",
        }

        settings = {
            "text_color": color_map.get(self.text_color_segment.get(), "#00ff00"),
            "bg_mode": bg_map.get(self.bg_mode_segment.get(), "transparent"),
            "bg_opacity": round(float(self.bg_opacity_slider.get()), 2),
            "font_size": int(float(self.font_size_slider.get())),
            "scale": round(float(self.scale_slider.get()), 2),
            "position": position_map.get(self.position_segment.get(), "top-right"),
            "click_through": bool(self.click_through_checkbox.get()),
            "show_fps": bool(self.show_fps_checkbox.get()),
            "show_gpu": bool(self.show_gpu_checkbox.get()),
            "show_cpu": bool(self.show_cpu_checkbox.get()),
            "show_ram": bool(self.show_ram_checkbox.get()),
        }

        self.on_apply(settings)