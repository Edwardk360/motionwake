import cv2
import wmi
import threading
import time
from src import logger_setup

log = logger_setup.setup()

def list_cameras():
    """Return list of (index, name) for all cameras including IR/Windows Hello cameras."""
    cameras = []
    try:
        c = wmi.WMI()
        wmi_cameras = {i: dev.Name for i, dev in enumerate(c.Win32_PnPEntity(PNPClass="Camera"))}
    except Exception:
        wmi_cameras = {}

    for i in range(10):
        cap = cv2.VideoCapture(i, cv2.CAP_DSHOW)
        if cap.isOpened():
            name = wmi_cameras.get(i, f"Camera {i}")
            cameras.append((i, name))
            log.info(f"Found camera [{i}]: {name}")
            cap.release()

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
        log.info(f"Motion detector started on camera index {self.camera_index}")

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
        log.info("Motion detector stopped")

    def _run(self):
        # Use CAP_DSHOW backend — required for Windows Hello IR cameras
        cap = cv2.VideoCapture(self.camera_index, cv2.CAP_DSHOW)
        if not cap.isOpened():
            log.error(f"Cannot open camera index {self.camera_index}")
            return

        ret, prev_frame = cap.read()
        if not ret:
            log.error("Cannot read initial frame from camera")
            cap.release()
            return

        prev_gray = cv2.cvtColor(prev_frame, cv2.COLOR_BGR2GRAY)
        prev_gray = cv2.GaussianBlur(prev_gray, (21, 21), 0)

        while self._running:
            ret, frame = cap.read()
            if not ret:
                log.warning("Frame read failed, retrying...")
                time.sleep(1)
                continue

            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            gray = cv2.GaussianBlur(gray, (21, 21), 0)

            delta = cv2.absdiff(prev_gray, gray)
            thresh = cv2.threshold(delta, self.sensitivity, 255, cv2.THRESH_BINARY)[1]
            motion_pixels = cv2.countNonZero(thresh)

            if motion_pixels > 500:
                log.info(f"Motion detected ({motion_pixels} px changed)")
                if self.on_motion:
                    self.on_motion()

            prev_gray = gray
            time.sleep(0.1)

        cap.release()
