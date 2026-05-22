import logging
import os
import sys
from datetime import datetime

def _get_log_dir():
    # Probeer eerst de installatiedirectory (logs naast de exe)
    if getattr(sys, "frozen", False):
        install_logs = os.path.join(os.path.dirname(sys.executable), "logs")
    else:
        install_logs = os.path.join(os.path.abspath(os.path.join(__file__, "../../")), "logs")

    try:
        os.makedirs(install_logs, exist_ok=True)
        # Testschrijving om rechten te controleren
        test = os.path.join(install_logs, ".write_test")
        with open(test, "w") as f:
            f.write("test")
        os.remove(test)
        return install_logs
    except PermissionError:
        # Fallback naar gebruikersprofiel als geen schrijfrechten
        fallback = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "MotionWake", "logs")
        os.makedirs(fallback, exist_ok=True)
        return fallback

LOG_DIR = _get_log_dir()

def setup(name="motionwake"):
    log_file = os.path.join(LOG_DIR, "motionwake.log")

    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)

    if not logger.handlers:
        # mode='w' schoont het logbestand bij elke herstart
        fh = logging.FileHandler(log_file, mode="w", encoding="utf-8")
        fh.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
        logger.addHandler(fh)

    return logger
