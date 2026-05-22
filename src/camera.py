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
        self.sensitivity = sensitivity
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

        ret, prev_frame = cap.read()
        if not ret:
            log.error("Kan geen frame lezen van camera")
            cap.release()
            return

        prev_gray = cv2.cvtColor(prev_frame, cv2.COLOR_BGR2GRAY)
        prev_gray = cv2.GaussianBlur(prev_gray, (21, 21), 0)

        while self._running:
            ret, frame = cap.read()
            if not ret:
                log.warning("Frame lezen mislukt, opnieuw proberen...")
                time.sleep(1)
                continue

            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            gray = cv2.GaussianBlur(gray, (21, 21), 0)

            delta = cv2.absdiff(prev_gray, gray)
            thresh = cv2.threshold(delta, self.sensitivity, 255, cv2.THRESH_BINARY)[1]
            motion_pixels = cv2.countNonZero(thresh)

            if motion_pixels > 500:
                log.info(f"Beweging gedetecteerd ({motion_pixels} px gewijzigd)")
                if self.on_motion:
                    self.on_motion()

            prev_gray = gray
            time.sleep(0.1)

        cap.release()
