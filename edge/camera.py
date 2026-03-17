"""
Edge device camera source.

Reads frames from a USB, RTSP, or HTTP camera source via OpenCV and pushes
them into a queue.Queue at the configured target FPS.  Automatically retries
on disconnection and resumes when the camera becomes available again.

HTTP sources (e.g. IP Webcam MJPEG stream) use a manual JPEG boundary parser
because opencv-python-headless lacks FFMPEG support for HTTP URLs.
"""

import logging
import queue
import threading
import time
import urllib.request

import cv2
import numpy as np

logger = logging.getLogger(__name__)

_RETRY_INTERVAL_S = 5.0


def _is_http_source(source: str) -> bool:
    return source.startswith("http://") or source.startswith("https://")


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
    # HTTP MJPEG reader
    # ------------------------------------------------------------------

    def _run_http_loop(self) -> None:
        """Read MJPEG stream over HTTP using boundary parsing."""
        frame_interval = 1.0 / self.fps

        while not self._stop_event.is_set():
            try:
                logger.info("CameraSource: connecting to HTTP source '%s'", self.source)
                req = urllib.request.urlopen(self.source, timeout=10)
                buf = b""
                logger.info("CameraSource: connected to '%s'", self.source)

                while not self._stop_event.is_set():
                    t0 = time.monotonic()
                    chunk = req.read(4096)
                    if not chunk:
                        break
                    buf += chunk

                    # Find JPEG boundaries
                    start = buf.find(b"\xff\xd8")
                    end = buf.find(b"\xff\xd9")
                    if start != -1 and end != -1 and end > start:
                        jpg = buf[start:end + 2]
                        buf = buf[end + 2:]
                        frame = cv2.imdecode(
                            np.frombuffer(jpg, dtype=np.uint8), cv2.IMREAD_COLOR
                        )
                        if frame is not None:
                            try:
                                self.frame_queue.put_nowait(frame)
                            except queue.Full:
                                pass

                        elapsed = time.monotonic() - t0
                        sleep_for = frame_interval - elapsed
                        if sleep_for > 0:
                            self._stop_event.wait(timeout=sleep_for)

            except Exception as exc:
                logger.error(
                    "CameraSource: HTTP error '%s': %s, retrying in %ss",
                    self.source, exc, _RETRY_INTERVAL_S,
                )
                self._stop_event.wait(timeout=_RETRY_INTERVAL_S)

        logger.info("CameraSource: stopped '%s'", self.source)

    # ------------------------------------------------------------------
    # OpenCV reader (RTSP / device)
    # ------------------------------------------------------------------

    def _open_capture(self) -> cv2.VideoCapture | None:
        cap = cv2.VideoCapture(self.source)
        if cap.isOpened():
            return cap
        cap.release()
        return None

    def _run_cv_loop(self) -> None:
        frame_interval = 1.0 / self.fps
        cap: cv2.VideoCapture | None = None

        while not self._stop_event.is_set():
            if cap is None:
                cap = self._open_capture()
                if cap is None:
                    logger.error(
                        "CameraSource: failed to open '%s', retrying in %ss",
                        self.source, _RETRY_INTERVAL_S,
                    )
                    self._stop_event.wait(timeout=_RETRY_INTERVAL_S)
                    continue
                logger.info("CameraSource: connected to '%s'", self.source)

            t0 = time.monotonic()
            ret, frame = cap.read()

            if not ret or frame is None:
                logger.error(
                    "CameraSource: lost connection to '%s', retrying in %ss",
                    self.source, _RETRY_INTERVAL_S,
                )
                cap.release()
                cap = None
                self._stop_event.wait(timeout=_RETRY_INTERVAL_S)
                continue

            try:
                self.frame_queue.put_nowait(frame)
            except queue.Full:
                pass

            elapsed = time.monotonic() - t0
            sleep_for = frame_interval - elapsed
            if sleep_for > 0:
                self._stop_event.wait(timeout=sleep_for)

        if cap is not None:
            cap.release()
        logger.info("CameraSource: stopped '%s'", self.source)

    def _run_loop(self) -> None:
        if _is_http_source(self.source):
            self._run_http_loop()
        else:
            self._run_cv_loop()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start(self) -> None:
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        logger.info("CameraSource: started '%s' at %d fps", self.source, self.fps)

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=10)
        logger.info("CameraSource: stop requested for '%s'", self.source)
