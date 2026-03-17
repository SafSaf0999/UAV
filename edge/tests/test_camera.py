"""
Unit tests for edge/camera.py

Tests:
  - Frames are pushed to the queue when the camera is working
  - Disconnection triggers the retry loop (mock cv2.VideoCapture to fail then succeed)
  - stop() terminates the loop cleanly
"""

import queue
import threading
import time
import unittest
from unittest.mock import MagicMock, patch, call

import numpy as np

from edge.camera import CameraSource


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_frame(h: int = 64, w: int = 64) -> np.ndarray:
    """Return a small random BGR frame."""
    return np.random.randint(0, 256, (h, w, 3), dtype=np.uint8)


def _make_cap(frames: list, *, opened: bool = True) -> MagicMock:
    """
    Build a mock cv2.VideoCapture that returns the given (ret, frame) pairs
    from successive read() calls.
    """
    cap = MagicMock()
    cap.isOpened.return_value = opened
    cap.read.side_effect = frames
    return cap


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestCameraSourceFramePush(unittest.TestCase):
    """Frames are pushed to the queue when the camera is working."""

    def test_frames_pushed_to_queue(self):
        frame = _make_frame()
        # Provide several good frames then block via stop_event
        good_reads = [(True, frame)] * 10

        cap = _make_cap(good_reads)
        q: queue.Queue = queue.Queue()

        with patch("edge.camera.cv2.VideoCapture", return_value=cap):
            src = CameraSource("/dev/video0", fps=30, frame_queue=q)
            src.start()
            # Wait until at least one frame arrives
            got = q.get(timeout=2.0)
            src.stop()

        self.assertIsNotNone(got)
        self.assertTrue(np.array_equal(got, frame))


class TestCameraSourceDisconnectRetry(unittest.TestCase):
    """Disconnection triggers retry; on reconnect frames resume."""

    def test_retry_on_failed_read_then_reconnect(self):
        frame = _make_frame()

        # First capture: read() always fails (simulates disconnection)
        cap_fail = _make_cap([(False, None)] * 100)
        # Second capture (after retry): returns good frames
        cap_ok = _make_cap([(True, frame)] * 100)

        call_count = {"n": 0}

        def _make_capture(source):
            call_count["n"] += 1
            if call_count["n"] == 1:
                return cap_fail
            return cap_ok

        q: queue.Queue = queue.Queue()

        # Patch retry interval to 0 so the test doesn't wait 5 s
        with patch("edge.camera.cv2.VideoCapture", side_effect=_make_capture), \
             patch("edge.camera._RETRY_INTERVAL_S", 0.0):
            src = CameraSource("rtsp://cam/stream", fps=30, frame_queue=q)
            src.start()
            # Wait for a frame from the second (good) capture
            got = q.get(timeout=3.0)
            src.stop()

        self.assertIsNotNone(got)
        self.assertTrue(np.array_equal(got, frame))
        # VideoCapture must have been called at least twice (fail + retry)
        self.assertGreaterEqual(call_count["n"], 2)

    def test_retry_when_capture_fails_to_open(self):
        """If VideoCapture.isOpened() returns False, retry after interval."""
        frame = _make_frame()

        cap_fail = _make_cap([], opened=False)
        cap_ok = _make_cap([(True, frame)] * 100, opened=True)

        call_count = {"n": 0}

        def _make_capture(source):
            call_count["n"] += 1
            return cap_fail if call_count["n"] == 1 else cap_ok

        q: queue.Queue = queue.Queue()

        with patch("edge.camera.cv2.VideoCapture", side_effect=_make_capture), \
             patch("edge.camera._RETRY_INTERVAL_S", 0.0):
            src = CameraSource("/dev/video0", fps=30, frame_queue=q)
            src.start()
            got = q.get(timeout=3.0)
            src.stop()

        self.assertIsNotNone(got)
        self.assertGreaterEqual(call_count["n"], 2)


class TestCameraSourceStop(unittest.TestCase):
    """stop() terminates the loop cleanly."""

    def test_stop_terminates_thread(self):
        frame = _make_frame()
        cap = _make_cap([(True, frame)] * 1000)
        q: queue.Queue = queue.Queue()

        with patch("edge.camera.cv2.VideoCapture", return_value=cap):
            src = CameraSource("/dev/video0", fps=30, frame_queue=q)
            src.start()
            self.assertTrue(src._thread.is_alive())
            src.stop()
            # Thread must have exited
            self.assertFalse(src._thread.is_alive())

    def test_stop_before_start_is_safe(self):
        """Calling stop() before start() must not raise."""
        src = CameraSource("/dev/video0", fps=15, frame_queue=queue.Queue())
        src.stop()  # should not raise

    def test_stop_event_is_set_after_stop(self):
        frame = _make_frame()
        cap = _make_cap([(True, frame)] * 1000)
        q: queue.Queue = queue.Queue()

        with patch("edge.camera.cv2.VideoCapture", return_value=cap):
            src = CameraSource("/dev/video0", fps=30, frame_queue=q)
            src.start()
            src.stop()

        self.assertTrue(src._stop_event.is_set())
