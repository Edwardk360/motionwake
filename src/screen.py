import ctypes
import time
import threading
import winreg
from src import logger_setup

log = logger_setup.setup()

REGISTRY_KEY = r"SOFTWARE\MotionWake"
REGISTRY_VALUE = "MotionDetected"

ES_CONTINUOUS = 0x80000000
ES_DISPLAY_REQUIRED = 0x00000002
ES_SYSTEM_REQUIRED = 0x00000001


def wake_screen():
    """Wake the monitor and prevent it from sleeping temporarily."""
    ctypes.windll.kernel32.SetThreadExecutionState(
        ES_CONTINUOUS | ES_DISPLAY_REQUIRED | ES_SYSTEM_REQUIRED
    )
    # Send WM_SYSCOMMAND SC_MONITORPOWER -1 to wake monitor
    ctypes.windll.user32.SendMessageW(0xFFFF, 0x0112, 0xF170, -1)
    log.info("Screen wake signal sent")


def allow_sleep():
    ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS)


def set_motion_flag():
    """Service writes this flag; tray app reads it."""
    try:
        key = winreg.CreateKey(winreg.HKEY_LOCAL_MACHINE, REGISTRY_KEY)
        winreg.SetValueEx(key, REGISTRY_VALUE, 0, winreg.REG_DWORD, 1)
        winreg.CloseKey(key)
    except Exception as e:
        log.error(f"Failed to set motion flag: {e}")


def clear_motion_flag():
    try:
        key = winreg.CreateKey(winreg.HKEY_LOCAL_MACHINE, REGISTRY_KEY)
        winreg.SetValueEx(key, REGISTRY_VALUE, 0, winreg.REG_DWORD, 0)
        winreg.CloseKey(key)
    except Exception:
        pass


def check_motion_flag():
    try:
        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, REGISTRY_KEY)
        val, _ = winreg.QueryValueEx(key, REGISTRY_VALUE)
        winreg.CloseKey(key)
        return val == 1
    except Exception:
        return False


class ScreenKeepAlive:
    """Keeps screen on for `duration` seconds after motion, then releases."""
    def __init__(self, duration=60):
        self.duration = duration
        self._timer = None

    def trigger(self):
        wake_screen()
        if self._timer:
            self._timer.cancel()
        self._timer = threading.Timer(self.duration, allow_sleep)
        self._timer.start()
        log.info(f"Screen will stay on for {self.duration} seconds")

    def stop(self):
        if self._timer:
            self._timer.cancel()
        allow_sleep()
