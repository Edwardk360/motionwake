import cv2
import winreg
import threading
import time
from src import logger_setup

log = logger_setup.setup()

CLSID_VIDEO_INPUT = "{860BB310-5D01-11D0-BD3B-00A0C911CE86}"


def _get_registry_camera_names():
    """Cameranamen uit Windows register — zelfde volgorde als DirectShow/OpenCV."""
    names = []
    key_path = f"SOFTWARE\\Classes\\CLSID\\{CLSID_VIDEO_INPUT}\\Instance"
    try:
        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_path)
        i = 0
        while True:
            try:
                subkey_name = winreg.EnumKey(key, i)
                subkey = winreg.OpenKey(key, subkey_name)
                try:
                    friendly_name, _ = winreg.QueryValueEx(subkey, "FriendlyName")
                    names.append(friendly_name)
                except FileNotFoundError:
                    names.append(f"Camera {i}")
                winreg.CloseKey(subkey)
                i += 1
            except OSError:
                break
        winreg.CloseKey(key)
    except Exception as e:
        log.warning(f"Register cameranamen ophalen mislukt: {e}")
    return names


def list_cameras():
    """Geeft lijst van (index, naam) voor alle cameras inclusief IR/Windows Hello."""
    registry_names = _get_registry_camera_names()
    cameras = []
    reg_idx = 0

    for i in range(10):
        cap = cv2.VideoCapture(i, cv2.CAP_DSHOW)
        if cap.isOpened():
            name = registry_names[reg_idx] if reg_idx < len(registry_names) else f"Camera {i}"
            cameras.append((i, name))
            log.info(f"Camera gevonden [{i}]: {name}")
            cap.release()
            reg_idx += 1

    return cameras


class MotionDetector:
    def __init__(self, camera_index=0, sensitivity=25, on_motion=None):
        self.camera_index = camera_index
        self.sensitivity = sensitivity  # 1-100, hogere waarde = minder gevoelig
        self.on_motion = on_motion
        self._running = False
        self._thread = None

    def start(self):
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        log.info(f"Bewegingsdetectie gestart op camera index {self.camera_index}")

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
        log.info("Bewegingsdetectie gestopt")

    def _run(self):
        cap = cv2.VideoCapture(self.camera_index, cv2.CAP_DSHOW)
        if not cap.isOpened():
            log.error(f"Kan camera index {self.camera_index} niet openen")
            return

        # BackgroundSubtractorMOG2 leert de achtergrond en past zich automatisch
        # aan lichtveranderingen aan — werkt overdag én 's nachts correct
        bg_subtractor = cv2.createBackgroundSubtractorMOG2(
            history=500,        # aantal frames voor achtergrondmodel
            varThreshold=16,    # gevoeligheid voor voorgrond detectie
            detectShadows=True  # schaduwen apart markeren (grijs), niet als beweging tellen
        )

        # Eerste frames gebruiken om achtergrond op te bouwen
        warmup_frames = 30
        log.info(f"Achtergrond opbouwen ({warmup_frames} frames)...")
        for _ in range(warmup_frames):
            ret, frame = cap.read()
            if ret:
                bg_subtractor.apply(frame)
            time.sleep(0.05)

        log.info("Detectie actief")

        while self._running:
            ret, frame = cap.read()
            if not ret:
                log.warning("Frame lezen mislukt, camera opnieuw verbinden...")
                cap.release()
                time.sleep(2)
                cap = cv2.VideoCapture(self.camera_index, cv2.CAP_DSHOW)
                continue

            # Bewegingsmasker: wit = beweging, grijs = schaduw, zwart = achtergrond
            mask = bg_subtractor.apply(frame)

            # Schaduwen (grijs = 127) uitsluiten — alleen echte beweging (wit = 255)
            _, mask = cv2.threshold(mask, 254, 255, cv2.THRESH_BINARY)

            # Ruis verminderen
            mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5)))

            motion_pixels = cv2.countNonZero(mask)

            # Drempelwaarde schalen op basis van gevoeligheidsinstelling (1=meest gevoelig, 100=minst)
            pixel_threshold = int(200 + (self.sensitivity / 100) * 3000)

            if motion_pixels > pixel_threshold:
                log.info(f"Beweging gedetecteerd ({motion_pixels} px, drempel={pixel_threshold})")
                if self.on_motion:
                    self.on_motion()

            time.sleep(0.1)

        cap.release()
