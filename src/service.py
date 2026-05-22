import win32serviceutil
import win32service
import win32event
import servicemanager
import socket
import sys

from src import config, logger_setup
from src.camera import MotionDetector
from src.screen import set_motion_flag

log = logger_setup.setup()

SERVICE_NAME = "MotionWakeSvc"
SERVICE_DISPLAY_NAME = "MotionWake Service"
SERVICE_DESCRIPTION = "Detects motion via webcam/Windows Hello sensor and wakes the screen."


class MotionWakeService(win32serviceutil.ServiceFramework):
    _svc_name_ = SERVICE_NAME
    _svc_display_name_ = SERVICE_DISPLAY_NAME
    _svc_description_ = SERVICE_DESCRIPTION

    def __init__(self, args):
        win32serviceutil.ServiceFramework.__init__(self, args)
        self.stop_event = win32event.CreateEvent(None, 0, 0, None)
        self.detector = None

    def SvcStop(self):
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        win32event.SetEvent(self.stop_event)
        if self.detector:
            self.detector.stop()
        log.info("Service stopping")

    def SvcDoRun(self):
        servicemanager.LogMsg(
            servicemanager.EVENTLOG_INFORMATION_TYPE,
            servicemanager.PYS_SERVICE_STARTED,
            (self._svc_name_, ""),
        )
        log.info("Service started")
        self.main()

    def main(self):
        cfg = config.load()
        camera_index = int(cfg.get("camera_index", 0))
        sensitivity = int(cfg.get("sensitivity", 25))

        def on_motion():
            set_motion_flag()

        self.detector = MotionDetector(
            camera_index=camera_index,
            sensitivity=sensitivity,
            on_motion=on_motion,
        )
        self.detector.start()

        win32event.WaitForSingleObject(self.stop_event, win32event.INFINITE)
        self.detector.stop()


def install_service():
    win32serviceutil.InstallService(
        None,
        SERVICE_NAME,
        SERVICE_DISPLAY_NAME,
        startType=win32service.SERVICE_AUTO_START,
        description=SERVICE_DESCRIPTION,
    )
    print(f"Service '{SERVICE_NAME}' installed.")
    log.info("Service installed")


def uninstall_service():
    win32serviceutil.RemoveService(SERVICE_NAME)
    print(f"Service '{SERVICE_NAME}' removed.")
    log.info("Service uninstalled")


if __name__ == "__main__":
    if len(sys.argv) == 1:
        servicemanager.Initialize()
        servicemanager.PrepareToHostSingle(MotionWakeService)
        servicemanager.StartServiceCtrlDispatcher()
    else:
        win32serviceutil.HandleCommandLine(MotionWakeService)
