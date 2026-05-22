import sys
import os
import time
import subprocess
import win32serviceutil
import win32service
import win32event
import win32ts
import win32security
import win32process
import win32con
import servicemanager

from src import logger_setup

log = logger_setup.setup(name="motionwake_service")

SERVICE_NAME         = "MotionWakeSvc"
SERVICE_DISPLAY_NAME = "MotionWake Service"
SERVICE_DESCRIPTION  = "Beheert de MotionWake tray applicatie voor alle gebruikers inclusief Kiosk."


class MotionWakeService(win32serviceutil.ServiceFramework):
    _svc_name_         = SERVICE_NAME
    _svc_display_name_ = SERVICE_DISPLAY_NAME
    _svc_description_  = SERVICE_DESCRIPTION

    def __init__(self, args):
        win32serviceutil.ServiceFramework.__init__(self, args)
        self.stop_event = win32event.CreateEvent(None, 0, 0, None)

    def SvcStop(self):
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        win32event.SetEvent(self.stop_event)
        log.info("Service gestopt")

    def SvcDoRun(self):
        servicemanager.LogMsg(
            servicemanager.EVENTLOG_INFORMATION_TYPE,
            servicemanager.PYS_SERVICE_STARTED,
            (self._svc_name_, ""),
        )
        log.info("Service gestart — tray app wordt beheerd per gebruikerssessie")
        self._run()

    def _get_active_sessions(self):
        """Geeft alle actieve interactieve sessies — werkt ook voor Kiosk."""
        active = []
        # Methode 1: console sessie
        try:
            cid = win32ts.WTSGetActiveConsoleSessionId()
            if cid != 0xFFFFFFFF:
                active.append(cid)
        except Exception:
            pass
        # Methode 2: alle WTS sessies (vangnet voor Kiosk)
        try:
            for s in win32ts.WTSEnumerateSessions():
                sid   = s["SessionId"]
                state = s["State"]
                if state == win32ts.WTSActive and sid not in active and sid != 0:
                    log.info(f"Kiosk/extra sessie gevonden via WTSEnumerateSessions: {sid}")
                    active.append(sid)
        except Exception as e:
            log.warning(f"WTSEnumerateSessions mislukt: {e}")
        return active

    def _run(self):
        session_processes = {}

        while win32event.WaitForSingleObject(self.stop_event, 5000) == win32event.WAIT_TIMEOUT:
            try:
                sessions = self._get_active_sessions()

                for session_id in sessions:
                    proc = session_processes.get(session_id)
                    if proc is None:
                        proc = self._launch_tray(session_id)
                        if proc:
                            session_processes[session_id] = proc
                    else:
                        exit_code = win32process.GetExitCodeProcess(proc)
                        if exit_code != 259:  # 259 = STILL_ACTIVE
                            log.warning(f"Tray gestopt in sessie {session_id} (exit {exit_code}) — herstarten")
                            del session_processes[session_id]
                            proc = self._launch_tray(session_id)
                            if proc:
                                session_processes[session_id] = proc

                # Sessies opruimen die niet meer actief zijn
                for sid in list(session_processes.keys()):
                    if sid not in sessions:
                        del session_processes[sid]
                        log.info(f"Sessie {sid} niet meer actief — opgeruimd")

            except Exception as e:
                log.warning(f"Sessie check mislukt: {e}")

    def _launch_tray(self, session_id):
        """Start de tray app in de actieve gebruikerssessie, geeft process handle terug."""
        try:
            tray_exe = os.path.join(os.path.dirname(sys.executable), "motionwake.exe")
            if not os.path.exists(tray_exe):
                log.error(f"Tray exe niet gevonden: {tray_exe}")
                return None

            token = win32ts.WTSQueryUserToken(session_id)
            dup_token = win32security.DuplicateTokenEx(
                token,
                win32security.SecurityImpersonation,
                None,
                win32security.TokenPrimary,
                None,
            )

            startup = win32process.STARTUPINFO()
            startup.dwFlags     = win32con.STARTF_USESHOWWINDOW
            startup.wShowWindow = win32con.SW_HIDE
            startup.lpDesktop   = "winsta0\\default"

            proc_info = win32process.CreateProcessAsUser(
                dup_token,
                tray_exe,
                f'"{tray_exe}" --tray',
                None, None, False,
                win32process.NORMAL_PRIORITY_CLASS,
                None, None, startup,
            )
            log.info(f"Tray app gestart in sessie {session_id}")
            return proc_info[0]  # process handle
        except Exception as e:
            log.error(f"Tray app starten mislukt in sessie {session_id}: {e}")
            return None


def _service_exists():
    try:
        hscm = win32service.OpenSCManager(None, None, win32service.SC_MANAGER_CONNECT)
        hs   = win32service.OpenService(hscm, SERVICE_NAME, win32service.SERVICE_QUERY_STATUS)
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
            time.sleep(2)
    except Exception:
        pass


def install_service():
    if _service_exists():
        log.info("Service bestaat al — eerst verwijderen")
        _stop_service_if_running()
        win32serviceutil.RemoveService(SERVICE_NAME)

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

    log.info(f"Service geïnstalleerd: {binary_path}")


def uninstall_service():
    if not _service_exists():
        log.warning("Service bestaat niet")
        return
    _stop_service_if_running()
    win32serviceutil.RemoveService(SERVICE_NAME)
    log.info("Service verwijderd")


if __name__ == "__main__":
    if len(sys.argv) == 1:
        servicemanager.Initialize()
        servicemanager.PrepareToHostSingle(MotionWakeService)
        servicemanager.StartServiceCtrlDispatcher()
    else:
        win32serviceutil.HandleCommandLine(MotionWakeService)
