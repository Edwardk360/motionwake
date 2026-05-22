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
from src.camera import MotionDetector, list_cameras
from src.screen import ScreenKeepAlive
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


def create_icon_image(active=False):
    img  = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    color = (0, 220, 100) if active else (0, 180, 255)
    draw.ellipse([8,  8,  56, 56], fill=color)
    draw.ellipse([20, 20, 44, 44], fill=(30, 30, 30))
    return img


class Tooltip:
    """Toont een uitleg bij hoveren over een widget."""
    def __init__(self, widget, text):
        self.widget = widget
        self.text   = text
        self.tip    = None
        widget.bind("<Enter>", self._show)
        widget.bind("<Leave>", self._hide)

    def _show(self, event=None):
        x = self.widget.winfo_rootx() + 20
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 4
        self.tip = tk.Toplevel(self.widget)
        self.tip.wm_overrideredirect(True)
        self.tip.wm_geometry(f"+{x}+{y}")
        tk.Label(
            self.tip, text=self.text, justify="left",
            background="#2a2a2a", foreground="#ffffff",
            relief="flat", font=("Segoe UI", 9),
            padx=8, pady=5, wraplength=280
        ).pack()

    def _hide(self, event=None):
        if self.tip:
            self.tip.destroy()
            self.tip = None


class SettingsWindow:
    def __init__(self, cameras):
        self.cameras = cameras
        self._preview_cap     = None
        self._preview_running = False

    def show(self):
        cfg  = config.load()
        root = tk.Tk()
        root.title("MotionWake Instellingen")
        root.resizable(False, False)
        root.configure(bg=BG)

        style = ttk.Style(root)
        style.theme_use("clam")
        style.configure(".",          background=BG, foreground=FG, font=("Segoe UI", 10))
        style.configure("TFrame",     background=BG)
        style.configure("TLabel",     background=BG, foreground=FG, font=("Segoe UI", 10))
        style.configure("TButton",    background="#333333", foreground=FG)
        style.configure("TCombobox",  fieldbackground="#333333", foreground=FG, background="#333333")
        style.configure("TEntry",     fieldbackground="#333333", foreground=FG)
        style.configure("TScale",     background=BG, troughcolor="#333333")
        style.map("TCombobox",        fieldbackground=[("readonly", "#333333")])
        style.map("TButton",          background=[("active", "#444444")])

        frame = ttk.Frame(root, padding=20)
        frame.pack(fill="both", expand=True)

        # Camera selectie
        cam_lbl = ttk.Label(frame, text="Camera:")
        cam_lbl.grid(row=0, column=0, sticky="w", pady=6)
        Tooltip(cam_lbl, "Selecteer de camera voor bewegingsdetectie.\nWebcam staat meestal op index 0.\nWindows Hello IR camera staat vaak op index 1 of hoger.\nDe live preview hieronder helpt je de juiste te kiezen.")
        cam_names = [name for _, name in self.cameras]
        cam_var   = tk.StringVar()
        cam_box   = ttk.Combobox(frame, textvariable=cam_var, values=cam_names, state="readonly", width=32)
        current_cam_idx = int(cfg.get("camera_index", 0))
        default_pos = next((i for i, (idx, _) in enumerate(self.cameras) if idx == current_cam_idx), 0)
        cam_box.current(default_pos)
        cam_box.grid(row=0, column=1, pady=6, padx=8, columnspan=2)
        Tooltip(cam_box, "Selecteer de camera voor bewegingsdetectie.\nWebcam staat meestal op index 0.\nWindows Hello IR camera staat vaak op index 1 of hoger.\nDe live preview hieronder helpt je de juiste te kiezen.")

        # Camera preview — vaste pixelgrootte via frame zodat auto-sizing direct klopt
        preview_frame = tk.Frame(frame, width=320, height=240, bg="#000000")
        preview_frame.grid(row=1, column=0, columnspan=3, pady=8)
        preview_frame.grid_propagate(False)
        preview_label = tk.Label(preview_frame, bg="#000000")
        preview_label.place(relwidth=1, relheight=1)
        Tooltip(preview_label, "Live beeld van de geselecteerde camera.\nVerander de camera selectie hierboven om een andere camera te bekijken.")

        # Gevoeligheid
        sens_lbl_title = ttk.Label(frame, text="Gevoeligheid (1-80):")
        sens_lbl_title.grid(row=2, column=0, sticky="w", pady=6)
        Tooltip(sens_lbl_title, "Hoe gevoelig de bewegingsdetectie is.\n\nLaag (1-20): detecteert kleine bewegingen zoals een hand.\nMiddel (20-40): detecteert normale loopbewegingen.\nHoog (40-80): alleen grote snelle bewegingen.\n\nBij veel valse meldingen: waarde verhogen.\nBij geen detectie: waarde verlagen.")
        sens_var   = tk.IntVar(value=int(cfg.get("sensitivity", 20)))
        sens_scale = ttk.Scale(frame, from_=1, to=80, variable=sens_var, orient="horizontal", length=200)
        sens_scale.grid(row=2, column=1, pady=6, padx=8)
        Tooltip(sens_scale, "Hoe gevoelig de bewegingsdetectie is.\n\nLaag (1-20): detecteert kleine bewegingen zoals een hand.\nMiddel (20-40): detecteert normale loopbewegingen.\nHoog (40-80): alleen grote snelle bewegingen.")
        sens_lbl   = ttk.Label(frame, text=str(sens_var.get()))
        sens_lbl.grid(row=2, column=2, padx=4)
        sens_var.trace_add("write", lambda *_: sens_lbl.config(text=str(sens_var.get())))

        # Scherm aan duur
        dur_lbl = ttk.Label(frame, text="Scherm aan (seconden):")
        dur_lbl.grid(row=3, column=0, sticky="w", pady=6)
        Tooltip(dur_lbl, "Hoe lang het scherm aan blijft na gedetecteerde beweging.\n\nVoorbeelden:\n  60 = 1 minuut\n  300 = 5 minuten\n  1200 = 20 minuten\n\nTyp het gewenste aantal seconden in het veld.")
        dur_var   = tk.IntVar(value=int(cfg.get("screen_on_duration", 60)))
        dur_entry = ttk.Entry(frame, textvariable=dur_var, width=8)
        dur_entry.grid(row=3, column=1, sticky="w", pady=6, padx=8)
        Tooltip(dur_entry, "Hoe lang het scherm aan blijft na gedetecteerde beweging.\n\nVoorbeelden:\n  60 = 1 minuut\n  300 = 5 minuten\n  1200 = 20 minuten\n\nTyp het gewenste aantal seconden in het veld.")

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
                        frame = cv2.resize(frame, (320, 240))
                        img   = ImageTk.PhotoImage(Image.fromarray(frame))
                        try:
                            preview_label.config(image=img, width=320, height=240)
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
            combobox_pos        = cam_box.current()
            actual_camera_index = self.cameras[combobox_pos][0] if self.cameras else 0
            cfg_dict = dict(cfg)
            cfg_dict["camera_index"]      = str(actual_camera_index)
            cfg_dict["sensitivity"]       = str(sens_var.get())
            cfg_dict["screen_on_duration"] = str(dur_var.get())
            config.save(cfg_dict)
            log.info(f"Instellingen opgeslagen: camera={actual_camera_index}, gevoeligheid={sens_var.get()}, duur={dur_var.get()}")
            root.destroy()

        def on_close():
            self._preview_running = False
            if self._preview_cap:
                self._preview_cap.release()
            root.destroy()

        root.protocol("WM_DELETE_WINDOW", on_close)
        ttk.Button(frame, text="Opslaan", command=save_and_close).grid(
            row=4, column=0, columnspan=3, pady=20
        )

        # Venster automatisch op juiste grootte en gecentreerd
        root.update_idletasks()
        w = root.winfo_reqwidth()
        h = root.winfo_reqheight()
        x = (root.winfo_screenwidth()  - w) // 2
        y = (root.winfo_screenheight() - h) // 2
        root.geometry(f"{w}x{h}+{x}+{y}")

        root.mainloop()


class TrayApp:
    def __init__(self):
        self.version    = read_version()
        self.cfg        = config.load()
        self.keep_alive = ScreenKeepAlive(int(self.cfg.get("screen_on_duration", 60)))
        self.detector   = None
        self.icon       = None
        self._active    = False

    def _on_motion(self):
        """Wordt aangeroepen vanuit de detector thread bij beweging."""
        self.cfg = config.load()
        self.keep_alive.duration = int(self.cfg.get("screen_on_duration", 60))
        self.keep_alive.trigger()
        self._active = True
        if self.icon:
            self.icon.icon = create_icon_image(active=True)
        # Na duration seconden icoon weer inactief
        threading.Timer(
            self.keep_alive.duration,
            lambda: self.icon and self.icon.__setattr__("icon", create_icon_image(False))
        ).start()

    def _start_detector(self):
        if self.detector:
            self.detector.stop()
        self.cfg        = config.load()
        camera_index    = int(self.cfg.get("camera_index", 0))
        sensitivity     = int(self.cfg.get("sensitivity", 20))
        self.detector   = MotionDetector(
            camera_index=camera_index,
            sensitivity=sensitivity,
            on_motion=self._on_motion,
        )
        self.detector.start()
        log.info(f"Detector gestart: camera={camera_index}, gevoeligheid={sensitivity}")

    def _watch_config(self):
        """Herlaad detector als instellingen veranderen."""
        last_cfg = dict(self.cfg)
        while True:
            time.sleep(5)
            new_cfg = config.load()
            if (new_cfg.get("camera_index")  != last_cfg.get("camera_index") or
                new_cfg.get("sensitivity")    != last_cfg.get("sensitivity")):
                log.info("Instellingen gewijzigd — detector herstarten")
                self._start_detector()
            self.keep_alive.duration = int(new_cfg.get("screen_on_duration", 60))
            last_cfg = dict(new_cfg)

    def _on_settings(self, icon, item):
        def open_settings():
            # Stop detector tijdelijk zodat settings preview camera kan gebruiken
            if self.detector:
                self.detector.stop()
            cameras = list_cameras()
            SettingsWindow(cameras).show()
            # Herstart detector na sluiten instellingen
            self._start_detector()
        threading.Thread(target=open_settings, daemon=True).start()

    def _on_about(self, icon, item):
        def show_about():
            root = tk.Tk()
            root.withdraw()
            try:
                messagebox.showinfo(
                    "Over MotionWake",
                    f"MotionWake v{self.version}\nGemaakt door Edwardk360\n\n"
                    "Bewegingsdetectie via webcam / Windows Hello sensor.\n"
                    "Wekt scherm via muisbeweging simulatie."
                )
            finally:
                try:
                    root.destroy()
                except Exception:
                    pass
        threading.Thread(target=show_about, daemon=True).start()

    def _on_quit(self, icon, item):
        if self.detector:
            self.detector.stop()
        self.keep_alive.stop()
        icon.stop()
        log.info("Tray app afgesloten")

    def run(self):
        log.info(f"MotionWake tray v{self.version} gestart")
        check_update_async(self.version, lambda v: log.info(f"Nieuwe versie beschikbaar: {v}"))

        # Start camera monitoring direct in gebruikerssessie
        self._start_detector()

        # Achtergrond thread voor config wijzigingen
        threading.Thread(target=self._watch_config, daemon=True).start()

        menu = pystray.Menu(
            pystray.MenuItem(f"MotionWake v{self.version}", None, enabled=False),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Instellingen", self._on_settings),
            pystray.MenuItem("Over",         self._on_about),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Afsluiten",    self._on_quit),
        )

        self.icon = pystray.Icon(
            "MotionWake", create_icon_image(False), "MotionWake", menu
        )
        self.icon.run()
