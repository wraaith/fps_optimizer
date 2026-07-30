
import sys


print("starting main.py")  # debug



def main():
    if "--overlay" in sys.argv:
        print("launching overlay")  # debug
        from overlay.overlay_window import OverlayWindow
        overlay = OverlayWindow()
        overlay.run()
    else:
        print("creating window")  # debug
        from ui.main_window import MainWindow
        app = MainWindow()
        app.mainloop()



if __name__ == "__main__":
    main()