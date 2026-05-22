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


def _service_exists():
    try:
        hscm = win32service.OpenSCManager(None, None, win32service.SC_MANAGER_CONNECT)
        hs = win32service.OpenService(hscm, SERVICE_NAME, win32service.SERVICE_QUERY_STATUS)
        win32service.CloseServiceHandle(hs)
        win32service.CloseServiceHandle(hscm)
        return True
    except win32service.error:
        return False


def _stop_service_if_running():
    try:
        status = win32serviceutil.QueryServiceStatus(SERVICE_NAME)
        if status[1] == win32service.SERVICE_RUNNING:
            win32serviceutil.StopService(SERVICE_NAME)
            import time
            time.sleep(2)
    except Exception:
        pass


def install_service():
    if _service_exists():
        log.info("Service bestaat al — eerst verwijderen voor herinstallatie")
        _stop_service_if_running()
        win32serviceutil.RemoveService(SERVICE_NAME)

    # Expliciet --service meegeven zodat Windows de juiste modus start
    binary_path = f'"{sys.executable}" --service'

    hscm = win32service.OpenSCManager(None, None, win32service.SC_MANAGER_CREATE_SERVICE)
    try:
        hs = win32service.CreateService(
            hscm,
            SERVICE_NAME,
            SERVICE_DISPLAY_NAME,
            win32service.SERVICE_ALL_ACCESS,
            win32service.SERVICE_WIN32_OWN_PROCESS,
            win32service.SERVICE_AUTO_START,
            win32service.SERVICE_ERROR_NORMAL,
            binary_path,
            None, 0, None, None, None,
        )
        win32service.ChangeServiceConfig2(
            hs, win32service.SERVICE_CONFIG_DESCRIPTION, SERVICE_DESCRIPTION
        )
        win32service.CloseServiceHandle(hs)
    finally:
        win32service.CloseServiceHandle(hscm)

    print(f"Service '{SERVICE_NAME}' geïnstalleerd met: {binary_path}")
    log.info(f"Service installed: {binary_path}")


def uninstall_service():
    if not _service_exists():
        print(f"Service '{SERVICE_NAME}' bestaat niet.")
        log.warning("Uninstall called but service does not exist")
        return
    _stop_service_if_running()
    win32serviceutil.RemoveService(SERVICE_NAME)
    print(f"Service '{SERVICE_NAME}' verwijderd.")
    log.info("Service uninstalled")


if __name__ == "__main__":
    if len(sys.argv) == 1:
        servicemanager.Initialize()
        servicemanager.PrepareToHostSingle(MotionWakeService)
        servicemanager.StartServiceCtrlDispatcher()
    else:
        win32serviceutil.HandleCommandLine(MotionWakeService)
