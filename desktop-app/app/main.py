import sys
import ctypes
import ctypes.wintypes
import os

# ── DPI awareness (must run BEFORE any Tk window is created) ──────────
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)   # Per-Monitor v2
except Exception:
    try:
        ctypes.windll.user32.SetProcessDPIAware()     # System DPI Aware
    except Exception:
        pass

import tkinter as tk

def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False

if not is_admin():
    # Re-run the script with administrative privileges
    print("Requesting administrator privileges...")
    ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, " ".join(sys.argv), None, 1)
    sys.exit()


def launch_overlay():
    import customtkinter as ctk
    from overlay.overlay_window import OverlayWindow

    ctk.set_appearance_mode("dark")

    root = ctk.CTk()
    root.withdraw()

    overlay = OverlayWindow(root)
    overlay.deiconify()
    overlay.state("normal")
    overlay.lift()
    overlay.attributes("-topmost", True)
    overlay.update_idletasks()
    overlay.update()

    def close_overlay():
        try:
            overlay.close()
        finally:
            root.destroy()

    overlay.protocol("WM_DELETE_WINDOW", close_overlay)
    root.mainloop()


def launch_main_window():
    from ui.main_window import MainWindow

    app = MainWindow()
    app.mainloop()


def main():
    if "--overlay" in sys.argv:
        launch_overlay()
    else:
        launch_main_window()


if __name__ == "__main__":
    main()