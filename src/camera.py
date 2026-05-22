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


def get_camera_name(camera_index: int) -> str:
    """Snelle naam-lookup via register (opent geen camera)."""
    names = _get_registry_camera_names()
    return names[camera_index] if camera_index < len(names) else f"Camera {camera_index}"


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
    """
    Camera wordt expliciet geopend en gesloten.
    Lage resolutie (320x240) en 15fps voor minimaal resourcegebruik als service.
    Retry bij camera verlies (bijv. na slaapstand).
    """
    MOTION_COOLDOWN = 5  # seconden tussen twee opeenvolgende motion events

    def __init__(self, camera_index=0, sensitivity=20, on_motion=None, camera_name=None):
        self.camera_index    = camera_index
        self.camera_name     = camera_name or get_camera_name(camera_index)
        self.sensitivity     = sensitivity
        self.on_motion       = on_motion
        self._cap            = None
        self._prev_frame     = None
        self._lock           = threading.Lock()
        self._running        = False
        self._thread         = None
        self._last_motion_ts = 0

    def _open(self) -> bool:
        with self._lock:
            if self._cap and self._cap.isOpened():
                return True
            cap = cv2.VideoCapture(self.camera_index, cv2.CAP_DSHOW)
            if not cap.isOpened():
                return False
            cap.set(cv2.CAP_PROP_FRAME_WIDTH,  320)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 240)
            cap.set(cv2.CAP_PROP_FPS,           15)
            self._cap        = cap
            self._prev_frame = None
            return True

    def _close(self):
        with self._lock:
            if self._cap:
                self._cap.release()
                self._cap = None
            self._prev_frame = None

    def _detect(self) -> bool:
        with self._lock:
            if not self._cap or not self._cap.isOpened():
                return False
            ok, frame = self._cap.read()
            if not ok:
                return False
            # IR cameras (Hello) leveren soms 1-kanaals frame — geen conversie nodig
            if len(frame.shape) == 2 or frame.shape[2] == 1:
                gray = frame if len(frame.shape) == 2 else frame[:, :, 0]
            else:
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            gray = cv2.GaussianBlur(gray, (11, 11), 0)
            if self._prev_frame is None:
                self._prev_frame = gray
                return False
            delta = cv2.absdiff(self._prev_frame, gray)
            self._prev_frame = gray
            _, thresh = cv2.threshold(delta, self.sensitivity, 255, cv2.THRESH_BINARY)
            return int(cv2.countNonZero(thresh)) > 300

    def start(self):
        self._running = True
        self._thread  = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        log.info(f"Bewegingsdetectie gestart op camera index {self.camera_index}")

    def stop(self):
        self._running = False
        self._close()
        if self._thread:
            self._thread.join(timeout=5)
        log.info("Bewegingsdetectie gestopt")

    def _run(self):
        # Probeer camera te openen, retry elke 10s bij mislukking
        while self._running:
            if self._open():
                break
            log.warning(f"Camera {self.camera_index} niet beschikbaar — opnieuw proberen in 10s")
            time.sleep(10)

        log.info(f"Camera {self.camera_index} geopend — monitoring actief")

        while self._running:
            try:
                if not self._cap or not self._cap.isOpened():
                    log.warning("Camera verbinding verloren — opnieuw verbinden...")
                    self._close()
                    time.sleep(2)
                    self._open()
                    continue

                if self._detect():
                    now = time.time()
                    if now - self._last_motion_ts >= self.MOTION_COOLDOWN:
                        self._last_motion_ts = now
                        log.info(f"Beweging gedetecteerd door: {self.camera_name}")
                        if self.on_motion:
                            self.on_motion()

            except Exception as e:
                log.error(f"Detectie fout: {e}")

            time.sleep(0.1)

        self._close()
