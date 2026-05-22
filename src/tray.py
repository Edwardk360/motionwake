import pystray
from PIL import Image, ImageDraw, ImageTk
import threading
import time
import tkinter as tk
from tkinter import ttk, messagebox
import os
import sys
import cv2

import win32serviceutil
import win32service
from src import config, logger_setup
from src.screen import ScreenKeepAlive, check_motion_flag, clear_motion_flag
from src.camera import list_cameras
from src.updater import check_update_async

log = logger_setup.setup()

SERVICE_NAME = "MotionWakeSvc"
BG = "#1e1e1e"
FG = "#ffffff"
ACCENT = "#0ab4ff"

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


def _restart_service():
    try:
        status = win32serviceutil.QueryServiceStatus(SERVICE_NAME)[1]
        if status == win32service.SERVICE_RUNNING:
            win32serviceutil.RestartService(SERVICE_NAME)
            log.info("Service herstart na opslaan instellingen")
        else:
            win32serviceutil.StartService(SERVICE_NAME)
            log.info("Service gestart na opslaan instellingen")
    except Exception as e:
        log.warning(f"Service herstarten mislukt: {e}")


class SettingsWindow:
    def __init__(self, cameras):
        self.cameras = cameras  # list of (actual_index, name)
        self._preview_cap = None
        self._preview_running = False

    def show(self):
        cfg = config.load()
        root = tk.Tk()
        root.title("MotionWake Instellingen")
        root.geometry("500x420")
        root.resizable(False, False)
        root.configure(bg=BG)

        style = ttk.Style(root)
        style.theme_use("clam")
        style.configure(".",           background=BG, foreground=FG, font=("Segoe UI", 10))
        style.configure("TFrame",      background=BG)
        style.configure("TLabel",      background=BG, foreground=FG, font=("Segoe UI", 10))
        style.configure("TButton",     background="#333333", foreground=FG, font=("Segoe UI", 10))
        style.configure("TCombobox",   fieldbackground="#333333", foreground=FG, background="#333333")
        style.configure("TEntry",      fieldbackground="#333333", foreground=FG)
        style.configure("TScale",      background=BG, troughcolor="#333333")
        style.map("TCombobox",         fieldbackground=[("readonly", "#333333")])
        style.map("TButton",           background=[("active", "#444444")])

        frame = ttk.Frame(root, padding=20)
        frame.pack(fill="both", expand=True)

        # Camera selectie
        ttk.Label(frame, text="Camera:").grid(row=0, column=0, sticky="w", pady=6)
        cam_names = [name for _, name in self.cameras]
        cam_var = tk.StringVar()
        cam_box = ttk.Combobox(frame, textvariable=cam_var, values=cam_names, state="readonly", width=32)
        current_cam_idx = int(cfg.get("camera_index", 0))
        # Zoek de combobox positie op basis van het echte camera index
        default_pos = next((i for i, (idx, _) in enumerate(self.cameras) if idx == current_cam_idx), 0)
        cam_box.current(default_pos)
        cam_box.grid(row=0, column=1, pady=6, padx=8, columnspan=2)

        # Camera preview
        preview_label = tk.Label(frame, bg="#000000", width=40, height=8)
        preview_label.grid(row=1, column=0, columnspan=3, pady=8)

        # Gevoeligheid
        ttk.Label(frame, text="Gevoeligheid (1-100):").grid(row=2, column=0, sticky="w", pady=6)
        sens_var = tk.IntVar(value=int(cfg.get("sensitivity", 25)))
        sens_scale = ttk.Scale(frame, from_=1, to=100, variable=sens_var, orient="horizontal", length=200)
        sens_scale.grid(row=2, column=1, pady=6, padx=8)
        sens_lbl = ttk.Label(frame, text=str(sens_var.get()))
        sens_lbl.grid(row=2, column=2, padx=4)
        sens_var.trace_add("write", lambda *_: sens_lbl.config(text=str(sens_var.get())))

        # Scherm aan duur
        ttk.Label(frame, text="Scherm aan (seconden):").grid(row=3, column=0, sticky="w", pady=6)
        dur_var = tk.IntVar(value=int(cfg.get("screen_on_duration", 60)))
        dur_entry = ttk.Entry(frame, textvariable=dur_var, width=8)
        dur_entry.grid(row=3, column=1, sticky="w", pady=6, padx=8)

        # Preview thread
        self._preview_running = True

        def update_preview():
            actual_idx = self.cameras[cam_box.current()][0] if self.cameras else 0
            if self._preview_cap is not None:
                self._preview_cap.release()
            self._preview_cap = cv2.VideoCapture(actual_idx, cv2.CAP_DSHOW)

            while self._preview_running:
                if self._preview_cap and self._preview_cap.isOpened():
                    ret, frame = self._preview_cap.read()
                    if ret:
                        frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                        frame = cv2.resize(frame, (320, 180))
                        img = ImageTk.PhotoImage(Image.fromarray(frame))
                        try:
                            preview_label.config(image=img, width=320, height=180)
                            preview_label.image = img
                        except Exception:
                            break
                time.sleep(0.05)

        def on_camera_change(event=None):
            self._preview_running = False
            time.sleep(0.15)
            self._preview_running = True
            threading.Thread(target=update_preview, daemon=True).start()

        cam_box.bind("<<ComboboxSelected>>", on_camera_change)
        threading.Thread(target=update_preview, daemon=True).start()

        def save_and_close():
            self._preview_running = False
            if self._preview_cap:
                self._preview_cap.release()

            combobox_pos = cam_box.current()
            actual_camera_index = self.cameras[combobox_pos][0] if self.cameras else 0

            cfg_dict = dict(cfg)
            cfg_dict["camera_index"] = str(actual_camera_index)
            cfg_dict["sensitivity"] = str(sens_var.get())
            cfg_dict["screen_on_duration"] = str(dur_var.get())
            config.save(cfg_dict)
            log.info(f"Instellingen opgeslagen: camera={actual_camera_index}, gevoeligheid={sens_var.get()}, duur={dur_var.get()}")
            root.destroy()
            _restart_service()

        def on_close():
            self._preview_running = False
            if self._preview_cap:
                self._preview_cap.release()
            root.destroy()

        root.protocol("WM_DELETE_WINDOW", on_close)

        ttk.Button(frame, text="Opslaan & Toepassen", command=save_and_close).grid(
            row=4, column=0, columnspan=3, pady=20
        )

        root.mainloop()


class TrayApp:
    def __init__(self):
        self.version = read_version()
        self.cfg = config.load()
        self.keep_alive = ScreenKeepAlive(int(self.cfg.get("screen_on_duration", 60)))
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
            try:
                messagebox.showinfo(
                    "Over MotionWake",
                    f"MotionWake v{self.version}\nGemaakt door Edwardk360\n\nBewegingsdetectie via webcam / Windows Hello sensor."
                )
            finally:
                try:
                    root.destroy()
                except Exception:
                    pass
        threading.Thread(target=show_about, daemon=True).start()

    def _on_quit(self, icon, item):
        self.keep_alive.stop()
        icon.stop()
        log.info("Tray app afgesloten")

    def run(self):
        log.info(f"MotionWake tray v{self.version} gestart")
        check_update_async(self.version, lambda v: log.info(f"Nieuwe versie beschikbaar: {v}"))
        threading.Thread(target=self._poll_motion, daemon=True).start()

        menu = pystray.Menu(
            pystray.MenuItem(f"MotionWake v{self.version}", None, enabled=False),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Instellingen", self._on_settings),
            pystray.MenuItem("Over", self._on_about),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Afsluiten", self._on_quit),
        )

        self.icon = pystray.Icon("MotionWake", create_icon_image(), "MotionWake", menu)
        self.icon.run()
