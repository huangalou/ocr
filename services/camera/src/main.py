import logging
import time
import threading

from .config import fetch_active_cameras
from .capture import capture_loop

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")
logger = logging.getLogger("camera-service")

POLL_INTERVAL = 30


def main():
    logger.info("Camera service started")
    active_threads: dict[str, threading.Thread] = {}

    while True:
        cameras = fetch_active_cameras()
        active_ids = {c["id"] for c in cameras}

        for cam in cameras:
            cid = cam["id"]
            if cid not in active_threads or not active_threads[cid].is_alive():
                t = threading.Thread(target=capture_loop, args=(cam,), daemon=True)
                t.start()
                active_threads[cid] = t
                logger.info(f"Started thread for camera '{cam['name']}'")

        for cid in list(active_threads):
            if cid not in active_ids:
                logger.info(f"Camera {cid} no longer active, thread will stop on next iteration")
                del active_threads[cid]

        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    main()
