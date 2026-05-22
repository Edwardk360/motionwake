import ctypes
import ctypes.wintypes
import threading
import time
import winreg
from src import logger_setup

log = logger_setup.setup()

REGISTRY_KEY   = r"SOFTWARE\MotionWake"
REGISTRY_VALUE = "MotionDetected"

ES_CONTINUOUS       = 0x80000000
ES_DISPLAY_REQUIRED = 0x00000002
ES_SYSTEM_REQUIRED  = 0x00000001

INPUT_MOUSE      = 0
MOUSEEVENTF_MOVE = 0x0001


class _MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx",          ctypes.c_long),
        ("dy",          ctypes.c_long),
        ("mouseData",   ctypes.c_ulong),
        ("dwFlags",     ctypes.c_ulong),
        ("time",        ctypes.c_ulong),
        ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong)),
    ]


class _INPUT(ctypes.Structure):
    _fields_ = [
        ("type", ctypes.c_ulong),
        ("mi",   _MOUSEINPUT),
    ]


def _simulate_mouse_move():
    """Simuleert muisbeweging via SendInput — wekt scherm vanuit gebruikerssessie."""
    inp = _INPUT()
    inp.type       = INPUT_MOUSE
    inp.mi.dwFlags = MOUSEEVENTF_MOVE
    inp.mi.dx = 1
    ctypes.windll.user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(inp))
    inp.mi.dx = -1
    ctypes.windll.user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(inp))


def set_motion_flag():
    try:
        key = winreg.CreateKey(winreg.HKEY_LOCAL_MACHINE, REGISTRY_KEY)
        winreg.SetValueEx(key, REGISTRY_VALUE, 0, winreg.REG_DWORD, 1)
        winreg.CloseKey(key)
    except Exception as e:
        log.error(f"Motion vlag zetten mislukt: {e}")


def clear_motion_flag():
    try:
        key = winreg.CreateKey(winreg.HKEY_LOCAL_MACHINE, REGISTRY_KEY)
        winreg.SetValueEx(key, REGISTRY_VALUE, 0, winreg.REG_DWORD, 0)
        winreg.CloseKey(key)
    except Exception:
        pass


def check_motion_flag() -> bool:
    try:
        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, REGISTRY_KEY)
        val, _ = winreg.QueryValueEx(key, REGISTRY_VALUE)
        winreg.CloseKey(key)
        return val == 1
    except Exception:
        return False


class ScreenKeepAlive:
    """
    Houdt het scherm aan via een dedicated thread.
    SetThreadExecutionState is per-thread — alle aanroepen moeten vanuit
    dezelfde thread komen, anders werkt het vrijgeven niet.
    """
    def __init__(self, duration=60):
        self.duration    = duration
        self._keep_until = 0.0
        self._running    = True
        self._thread     = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def trigger(self):
        _simulate_mouse_move()
        self._keep_until = time.time() + self.duration
        log.info(f"Scherm gewekt — blijft {self.duration} seconden aan")

    def _loop(self):
        awake = False
        while self._running:
            if time.time() < self._keep_until:
                if not awake:
                    ctypes.windll.kernel32.SetThreadExecutionState(
                        ES_CONTINUOUS | ES_DISPLAY_REQUIRED | ES_SYSTEM_REQUIRED
                    )
                    awake = True
            else:
                if awake:
                    ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS)
                    log.info("Scherm wake lock vrijgegeven")
                    awake = False
            time.sleep(1)

    def stop(self):
        self._running    = False
        self._keep_until = 0.0
        ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS)
