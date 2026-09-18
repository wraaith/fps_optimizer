import sys
import ctypes
import ctypes.wintypes
import os
import subprocess
import tkinter as tk
import faulthandler
import time

# Ensure app and desktop-app directories are on sys.path for robust relative/absolute imports
_APP_DIR = os.path.dirname(os.path.abspath(__file__))
_DESKTOP_DIR = os.path.dirname(_APP_DIR)
for _p in (_APP_DIR, _DESKTOP_DIR):
    if _p not in sys.path:
        sys.path.insert(0, _p)

_CRASH_LOG = os.path.join(os.path.dirname(_APP_DIR), "crash.log")
try:
    _crash_file = open(_CRASH_LOG, "a", encoding="utf-8")
    faulthandler.enable(file=_crash_file)
except Exception:
    try:
        faulthandler.enable()
    except Exception:
        pass

def _global_exception_handler(exctype, value, tb):
    import traceback
    err_str = "".join(traceback.format_exception(exctype, value, tb))
    print(f"[FATAL ERROR]\n{err_str}", file=sys.stderr)
    try:
        with open(_CRASH_LOG, "a", encoding="utf-8") as f:
            f.write(f"\n--- Unhandled Exception at {time.ctime()} ---\n{err_str}\n")
    except Exception:
        pass
    try:
        import tkinter.messagebox as mb
        mb.showerror(
            "FPS Optimizer Error",
            f"An unexpected error occurred:\n\n{value}\n\nDetails have been logged to crash.log."
        )
    except Exception:
        pass

sys.excepthook = _global_exception_handler

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
    "numpy": "numpy>=1.24.0",
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

    def _tk_callback_error(exc, val, tb):
        import traceback
        err_str = "".join(traceback.format_exception(exc, val, tb))
        print(f"[Tkinter Callback Error]\n{err_str}", file=sys.stderr)
        try:
            with open(_CRASH_LOG, "a", encoding="utf-8") as f:
                f.write(f"\n--- Tkinter Error at {time.ctime()} ---\n{err_str}\n")
        except Exception:
            pass

    app.report_callback_exception = _tk_callback_error
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