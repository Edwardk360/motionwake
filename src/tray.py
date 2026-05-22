import pystray
from PIL import Image, ImageDraw
import threading
import time
import tkinter as tk
from tkinter import ttk, messagebox
import os
import sys

from src import config, logger_setup
from src.screen import ScreenKeepAlive, check_motion_flag, clear_motion_flag
from src.camera import list_cameras
from src.updater import check_update_async

log = logger_setup.setup()

VERSION_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "version.txt")


def read_version():
    try:
        with open(VERSION_FILE) as f:
            return f.read().strip()
    except Exception:
        return "1.0.0"


def create_icon_image():
    img = Image.new("RGB", (64, 64), color=(30, 30, 30))
    draw = ImageDraw.Draw(img)
    draw.ellipse([8, 8, 56, 56], fill=(0, 180, 255))
    draw.ellipse([20, 20, 44, 44], fill=(30, 30, 30))
    return img


class SettingsWindow:
    def __init__(self, cameras):
        self.cameras = cameras
        self.result = None

    def show(self):
        cfg = config.load()
        root = tk.Tk()
        root.title("MotionWake Instellingen")
        root.geometry("400x320")
        root.resizable(False, False)
        root.configure(bg="#1e1e1e")

        style = ttk.Style(root)
        style.theme_use("clam")
        style.configure("TLabel", background="#1e1e1e", foreground="white", font=("Segoe UI", 10))
        style.configure("TButton", font=("Segoe UI", 10))
        style.configure("TCombobox", font=("Segoe UI", 10))
        style.configure("TScale", background="#1e1e1e")

        frame = ttk.Frame(root, padding=20)
        frame.pack(fill="both", expand=True)

        # Camera selection
        ttk.Label(frame, text="Camera:").grid(row=0, column=0, sticky="w", pady=6)
        cam_names = [f"[{i}] {name}" for i, name in self.cameras]
        cam_var = tk.StringVar()
        cam_box = ttk.Combobox(frame, textvariable=cam_var, values=cam_names, state="readonly", width=30)
        current_idx = int(cfg.get("camera_index", 0))
        cam_box.current(current_idx if current_idx < len(cam_names) else 0)
        cam_box.grid(row=0, column=1, pady=6, padx=8)

        # Sensitivity
        ttk.Label(frame, text="Gevoeligheid (1-100):").grid(row=1, column=0, sticky="w", pady=6)
        sens_var = tk.IntVar(value=int(cfg.get("sensitivity", 25)))
        sens_scale = ttk.Scale(frame, from_=1, to=100, variable=sens_var, orient="horizontal", length=180)
        sens_scale.grid(row=1, column=1, pady=6, padx=8)

        # Screen on duration
        ttk.Label(frame, text="Scherm aan (seconden):").grid(row=2, column=0, sticky="w", pady=6)
        dur_var = tk.IntVar(value=int(cfg.get("screen_on_duration", 60)))
        dur_entry = ttk.Entry(frame, textvariable=dur_var, width=8)
        dur_entry.grid(row=2, column=1, sticky="w", pady=6, padx=8)

        def save_and_close():
            idx = cam_box.current()
            cfg_dict = dict(cfg)
            cfg_dict["camera_index"] = str(idx)
            cfg_dict["sensitivity"] = str(sens_var.get())
            cfg_dict["screen_on_duration"] = str(dur_var.get())
            config.save(cfg_dict)
            log.info(f"Settings saved: camera={idx}, sensitivity={sens_var.get()}, duration={dur_var.get()}")
            messagebox.showinfo("Opgeslagen", "Instellingen opgeslagen.\nHerstart de service om wijzigingen toe te passen.")
            root.destroy()

        ttk.Button(frame, text="Opslaan", command=save_and_close).grid(
            row=3, column=0, columnspan=2, pady=20
        )

        root.mainloop()


class TrayApp:
    def __init__(self):
        self.version = read_version()
        self.cfg = config.load()
        self.keep_alive = ScreenKeepAlive(int(self.cfg.get("screen_on_duration", 60)))
        self.cameras = []
        self.icon = None

    def _poll_motion(self):
        while True:
            if check_motion_flag():
                clear_motion_flag()
                self.cfg = config.load()
                self.keep_alive.duration = int(self.cfg.get("screen_on_duration", 60))
                self.keep_alive.trigger()
            time.sleep(0.5)

    def _on_settings(self, icon, item):
        def open_settings():
            cameras = list_cameras()
            SettingsWindow(cameras).show()
        threading.Thread(target=open_settings, daemon=True).start()

    def _on_about(self, icon, item):
        def show_about():
            root = tk.Tk()
            root.withdraw()
            messagebox.showinfo("Over MotionWake", f"MotionWake v{self.version}\nGemaakt door Edwardk360\n\nBeweging detectie via webcam / Windows Hello sensor.")
            root.destroy()
        threading.Thread(target=show_about, daemon=True).start()

    def _on_quit(self, icon, item):
        self.keep_alive.stop()
        icon.stop()
        log.info("Tray app closed")

    def run(self):
        log.info(f"MotionWake tray v{self.version} starting")

        check_update_async(self.version, lambda v: log.info(f"New version available: {v}"))

        threading.Thread(target=self._poll_motion, daemon=True).start()

        menu = pystray.Menu(
            pystray.MenuItem("MotionWake v" + self.version, None, enabled=False),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Instellingen", self._on_settings),
            pystray.MenuItem("Over", self._on_about),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Afsluiten", self._on_quit),
        )

        self.icon = pystray.Icon("MotionWake", create_icon_image(), "MotionWake", menu)
        self.icon.run()
