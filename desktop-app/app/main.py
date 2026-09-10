import sys
import ctypes
import ctypes.wintypes
import os
import subprocess
import tkinter as tk

# Ensure app directory is on sys.path for robust relative module imports
_APP_DIR = os.path.dirname(os.path.abspath(__file__))
if _APP_DIR not in sys.path:
    sys.path.insert(0, _APP_DIR)

# ── DPI awareness (must run BEFORE any Tk window is created) ──────────
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)   # Per-Monitor v2
except Exception:
    try:
        ctypes.windll.user32.SetProcessDPIAware()     # System DPI Aware
    except Exception:
        pass

def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except Exception:
        return False


REQUIRED_PACKAGES = {
    "customtkinter": "customtkinter>=5.2",
    "pywinstyles": "pywinstyles>=1.8",
    "psutil": "psutil>=5.9",
    "wmi": "WMI>=1.5",
    "win32api": "pywin32>=300",
    "pynvml": "nvidia-ml-py>=12.0",
    "pandas": "pandas>=2.0.0",
    "numpy": "numpy>=1.24.0",
    "sklearn": "scikit-learn>=1.3.0",
    "joblib": "joblib>=1.3.0",
}


def ensure_dependencies():
    """Verify and automatically install all required packages on-the-fly (fast spec check)."""
    import importlib.util
    missing = []
    for mod, pkg in REQUIRED_PACKAGES.items():
        if importlib.util.find_spec(mod) is None:
            missing.append(pkg)

    if not missing:
        return

    print(f"[FPS Optimizer] Integrating missing dependencies: {', '.join(missing)}...")
    req_file = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "requirements.txt")
    try:
        if os.path.isfile(req_file):
            cmd = [sys.executable, "-m", "pip", "install", "-r", req_file, "--quiet"]
        else:
            cmd = [sys.executable, "-m", "pip", "install"] + missing + ["--quiet"]
        subprocess.check_call(cmd)
        print("[FPS Optimizer] All dependencies successfully integrated!")
    except Exception as e:
        print(f"[FPS Optimizer] Auto-install note: {e}")


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
    ensure_dependencies()

    if "--elevate" in sys.argv and not is_admin() and "--overlay" not in sys.argv:
        print("Requesting administrator privileges...")
        script_path = os.path.abspath(sys.argv[0])
        script_dir = os.path.dirname(script_path)
        cmd_args = [script_path] + [a for a in sys.argv[1:] if a != "--elevate"]
        cmdline = subprocess.list2cmdline(cmd_args)
        ret = ctypes.windll.shell32.ShellExecuteW(
            None, "runas", sys.executable, cmdline, script_dir, 1
        )
        if ret > 32:
            sys.exit(0)
        else:
            print("Administrator privileges not granted. Running in standard mode...")
    elif not is_admin() and "--overlay" not in sys.argv:
        print("[FPS Optimizer] Running in standard user mode.")
        print("[FPS Optimizer] (For Standby RAM flush & network tuning, launch run.bat or run as Administrator)")

    try:
        if "--overlay" in sys.argv:
            launch_overlay()
        else:
            launch_main_window()
    except Exception as e:
        import traceback
        traceback.print_exc()
        try:
            import tkinter.messagebox as mb
            mb.showerror("FPS Optimizer Error", f"An error occurred while launching:\n\n{e}\n\n{traceback.format_exc()}")
        except Exception:
            pass


if __name__ == "__main__":
    main()