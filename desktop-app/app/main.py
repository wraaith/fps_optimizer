import sys
import tkinter as tk
import ctypes
import os

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
    from overlay.overlay_window import OverlayWindow

    root = tk.Tk()
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