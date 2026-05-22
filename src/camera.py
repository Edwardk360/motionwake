import cv2
import subprocess
import threading
import time
from src import logger_setup

log = logger_setup.setup()


def _get_wmi_camera_names():
    """Haal logische cameranamen op via PowerShell in DirectShow volgorde."""
    try:
        cmd = (
            "Get-PnpDevice -Class Camera -Status OK | "
            "Sort-Object FriendlyName | "
            "Select-Object -ExpandProperty FriendlyName"
        )
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command", cmd],
            capture_output=True, text=True, timeout=5
        )
        names = [line.strip() for line in result.stdout.splitlines() if line.strip()]
        return names
    except Exception:
        return []


def list_cameras():
    """Geeft lijst van (index, naam) voor alle cameras inclusief IR/Windows Hello."""
    wmi_names = _get_wmi_camera_names()
    cameras = []
    wmi_idx = 0

    for i in range(10):
        cap = cv2.VideoCapture(i, cv2.CAP_DSHOW)
        if cap.isOpened():
            name = wmi_names[wmi_idx] if wmi_idx < len(wmi_names) else f"Camera {i}"
            cameras.append((i, name))
            log.info(f"Camera gevonden [{i}]: {name}")
            cap.release()
            wmi_idx += 1

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
