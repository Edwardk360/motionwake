import logging
import os
import tempfile


def _make_handler(log_path: str) -> logging.FileHandler:
    os.makedirs(os.path.dirname(log_path), exist_ok=True)
    fh = logging.FileHandler(log_path, mode="w", encoding="utf-8")
    fh.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
    return fh


def setup(name="motionwake", level="INFO"):
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))

    if not logger.handlers:
        programdata = os.path.join(
            os.environ.get("PROGRAMDATA", "C:\\ProgramData"), "MotionWake", "logs", f"{name}.log"
        )
        appdata = os.path.join(
            os.environ.get("APPDATA", os.path.expanduser("~")), "MotionWake", "logs", f"{name}.log"
        )
        temp = os.path.join(tempfile.gettempdir(), "MotionWake", f"{name}.log")

        for log_path in [programdata, appdata, temp]:
            try:
                fh = _make_handler(log_path)
                logger.addHandler(fh)
                break
            except (PermissionError, OSError):
                continue
        else:
            # Absolute fallback: log naar stderr zodat er altijd output is
            logger.addHandler(logging.StreamHandler())

    return logger


def set_level(level_name: str):
    """Wijzigt het logniveau van de actieve logger tijdens gebruik."""
    level = getattr(logging, level_name.upper(), logging.INFO)
    logging.getLogger("motionwake").setLevel(level)
