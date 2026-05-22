import sys
import traceback
import tkinter as tk
from tkinter import messagebox


def show_crash(exc):
    err = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
    root = tk.Tk()
    root.withdraw()
    try:
        messagebox.showerror(
            "MotionWake - Fout",
            f"Er is een onverwachte fout opgetreden:\n\n{err}\n\nKopieer de tekst en neem contact op met de ontwikkelaar.",
        )
    finally:
        try:
            root.destroy()
        except Exception:
            pass


def main():
    arg = sys.argv[1] if len(sys.argv) > 1 else "--tray"

    if arg == "--tray":
        from src.tray import TrayApp
        TrayApp().run()

    elif arg == "--service":
        import win32serviceutil
        import servicemanager
        from src.service import MotionWakeService
        if len(sys.argv) == 2:
            servicemanager.Initialize()
            servicemanager.PrepareToHostSingle(MotionWakeService)
            servicemanager.StartServiceCtrlDispatcher()
        else:
            win32serviceutil.HandleCommandLine(MotionWakeService)

    elif arg == "--install":
        from src.service import install_service
        install_service()

    elif arg == "--uninstall":
        from src.service import uninstall_service
        uninstall_service()

    else:
        print("Gebruik: motionwake.exe [--tray | --service | --install | --uninstall]")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        show_crash(e)
