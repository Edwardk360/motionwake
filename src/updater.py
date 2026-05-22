import requests
import threading
from src import logger_setup

log = logger_setup.setup()

GITHUB_REPO = "Edwardk360/motionwake"
RELEASES_URL = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"


def get_latest_version():
    try:
        resp = requests.get(RELEASES_URL, timeout=5)
        resp.raise_for_status()
        return resp.json().get("tag_name", "").lstrip("v")
    except Exception as e:
        log.warning(f"Update check failed: {e}")
        return None


def check_update_async(current_version, on_update_available):
    def _check():
        latest = get_latest_version()
        if latest and latest != current_version:
            log.info(f"Update available: v{latest} (current: v{current_version})")
            on_update_available(latest)

    threading.Thread(target=_check, daemon=True).start()
