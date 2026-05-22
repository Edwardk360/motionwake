import logging
import os
import sys


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

        for log_path in [programdata, appdata]:
            try:
                os.makedirs(os.path.dirname(log_path), exist_ok=True)
                # mode='w' schoont het logbestand bij elke herstart
                fh = logging.FileHandler(log_path, mode="w", encoding="utf-8")
                fh.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
                logger.addHandler(fh)
                break
            except PermissionError:
                continue

    return logger


def set_level(level_name: str):
    """Wijzigt het logniveau van de actieve logger tijdens gebruik."""
    level = getattr(logging, level_name.upper(), logging.INFO)
    logging.getLogger("motionwake").setLevel(level)
