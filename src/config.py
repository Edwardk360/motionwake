import configparser
import os

CONFIG_PATH = os.path.join(os.environ.get("PROGRAMDATA", "C:\\ProgramData"), "MotionWake", "config.ini")

DEFAULTS = {
    "camera_index": "0",
    "sensitivity": "25",
    "screen_on_duration": "60",
    "check_interval": "1",
    "github_update_check": "true",
    "log_level": "INFO",
}

def load():
    cfg = configparser.ConfigParser()
    cfg["motionwake"] = DEFAULTS
    if os.path.exists(CONFIG_PATH):
        cfg.read(CONFIG_PATH)
    return cfg["motionwake"]

def save(section: dict):
    cfg = configparser.ConfigParser()
    cfg["motionwake"] = section
    os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
    with open(CONFIG_PATH, "w") as f:
        cfg.write(f)
