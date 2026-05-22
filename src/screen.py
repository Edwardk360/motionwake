import ctypes
import ctypes.wintypes
import threading
import time
import winreg
from src import logger_setup

log = logger_setup.setup()

REGISTRY_KEY   = r"SOFTWARE\MotionWake"
REGISTRY_VALUE = "MotionDetected"

# SetThreadExecutionState flags — houdt scherm aan nadat het gewekt is
ES_CONTINUOUS       = 0x80000000
ES_DISPLAY_REQUIRED = 0x00000002
ES_SYSTEM_REQUIRED  = 0x00000001

# SendInput structuren — exact hetzelfde als echte muis input
INPUT_MOUSE        = 0
MOUSEEVENTF_MOVE   = 0x0001

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
    """
    Simuleert een muisbeweging via SendInput — wekt het scherm op exact
    zoals het aanraken van een echte muis. Werkt vanuit de gebruikerssessie.
    """
    inp = _INPUT()
    inp.type    = INPUT_MOUSE
    inp.mi.dwFlags = MOUSEEVENTF_MOVE

    inp.mi.dx = 1
    ctypes.windll.user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(inp))
    inp.mi.dx = -1
    ctypes.windll.user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(inp))


def wake_screen():
    """
    Wekt het scherm op door muisbeweging te simuleren (SendInput).
    Daarna SetThreadExecutionState zodat het scherm aan blijft.
    """
    _simulate_mouse_move()
    ctypes.windll.kernel32.SetThreadExecutionState(
        ES_CONTINUOUS | ES_DISPLAY_REQUIRED | ES_SYSTEM_REQUIRED
    )
    log.info("Scherm gewekt via SendInput (muisbeweging gesimuleerd)")


def allow_sleep():
    """Geeft Windows toestemming om het scherm weer uit te zetten."""
    ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS)
    log.info("Scherm wake lock vrijgegeven")


def set_motion_flag():
    """Service schrijft deze vlag — tray app leest hem."""
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
    """Houdt scherm aan voor `duration` seconden na beweging."""
    def __init__(self, duration=60):
        self.duration = duration
        self._timer   = None

    def trigger(self):
        wake_screen()
        if self._timer:
            self._timer.cancel()
        self._timer = threading.Timer(self.duration, allow_sleep)
        self._timer.start()
        log.info(f"Scherm blijft {self.duration} seconden aan")

    def stop(self):
        if self._timer:
            self._timer.cancel()
        allow_sleep()
