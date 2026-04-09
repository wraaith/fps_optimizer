from ui.main_window import MainWindow

print("starting main.py")  # debug


def main():
    print("creating window")  # debug
    app = MainWindow()
    app.mainloop()


if __name__ == "__main__":
    main()
