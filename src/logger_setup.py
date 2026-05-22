import logging
import os
import sys

def _get_log_dir():
    log_dir = os.path.join(os.environ.get("PROGRAMDATA", "C:\\ProgramData"), "MotionWake", "logs")
    try:
        os.makedirs(log_dir, exist_ok=True)
        test = os.path.join(log_dir, ".write_test")
        with open(test, "w") as f:
            f.write("test")
        os.remove(test)
        return log_dir
    except PermissionError:
        fallback = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "MotionWake", "logs")
        os.makedirs(fallback, exist_ok=True)
        return fallback

LOG_DIR = _get_log_dir()

def setup(name="motionwake", level="INFO"):
    log_file = os.path.join(LOG_DIR, "motionwake.log")

    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))

    if not logger.handlers:
        # mode='w' schoont het logbestand bij elke herstart
        fh = logging.FileHandler(log_file, mode="w", encoding="utf-8")
        fh.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
        logger.addHandler(fh)

    return logger

def set_level(level_name: str):
    """Wijzigt het logniveau van de actieve logger tijdens gebruik."""
    level = getattr(logging, level_name.upper(), logging.INFO)
    logging.getLogger("motionwake").setLevel(level)
