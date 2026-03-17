"""
Edge device camera source.

Reads frames from a USB, RTSP, or HTTP camera source via OpenCV and pushes
them into a queue.Queue at the configured target FPS.  Automatically retries
on disconnection and resumes when the camera becomes available again.
"""

import logging
import queue
import threading
import time

import cv2

logger = logging.getLogger(__name__)

_RETRY_INTERVAL_S = 5.0


class CameraSource:
    """
    Captures frames from a camera and pushes them into a queue.

    Args:
        source: Camera source string — /dev/videoN, rtsp://, or http://.
        fps:    Target capture frame rate.
        frame_queue: Queue to push captured frames into.
    """

    def __init__(self, source: str, fps: int, frame_queue: queue.Queue) -> None:
        self.source = source
        self.fps = max(fps, 1)
        self.frame_queue = frame_queue
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _open_capture(self) -> cv2.VideoCapture | None:
        """Open the camera; return the capture object or None on failure."""
        cap = cv2.VideoCapture(self.source)
        if cap.isOpened():
            return cap
        cap.release()
        return None

    def _run_loop(self) -> None:
        """Background thread: capture frames and push to queue."""
        frame_interval = 1.0 / self.fps
        cap: cv2.VideoCapture | None = None

        while not self._stop_event.is_set():
            # --- (Re)connect ---
            if cap is None:
                cap = self._open_capture()
                if cap is None:
                    logger.error(
                        "CameraSource: failed to open '%s', retrying in %ss",
                        self.source,
                        _RETRY_INTERVAL_S,
                    )
                    self._stop_event.wait(timeout=_RETRY_INTERVAL_S)
                    continue
                logger.info("CameraSource: connected to '%s'", self.source)

            # --- Read one frame ---
            t0 = time.monotonic()
            ret, frame = cap.read()

            if not ret or frame is None:
                logger.error(
                    "CameraSource: lost connection to '%s', retrying in %ss",
                    self.source,
                    _RETRY_INTERVAL_S,
                )
                cap.release()
                cap = None
                self._stop_event.wait(timeout=_RETRY_INTERVAL_S)
                continue

            # Push frame (non-blocking; drop if queue is full)
            try:
                self.frame_queue.put_nowait(frame)
            except queue.Full:
                pass

            # Pace to target FPS
            elapsed = time.monotonic() - t0
            sleep_for = frame_interval - elapsed
            if sleep_for > 0:
                self._stop_event.wait(timeout=sleep_for)

        if cap is not None:
            cap.release()
        logger.info("CameraSource: stopped '%s'", self.source)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Start capturing frames in a background thread."""
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        logger.info("CameraSource: started '%s' at %d fps", self.source, self.fps)

    def stop(self) -> None:
        """Signal the capture loop to exit and wait for the thread to finish."""
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=10)
        logger.info("CameraSource: stop requested for '%s'", self.source)
