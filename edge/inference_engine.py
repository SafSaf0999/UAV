"""
Edge device inference engine.

Loads a YOLO26 .pt model via ultralytics.YOLO, processes frames from a
queue.Queue at configurable target FPS, applies thermal preprocessing when
camera_mode == "thermal", runs ByteTrack tracking, and produces
Tracking_Payload dicts.

Also provides ModelManager for hot-swapping model profiles at runtime.
"""

import logging
import os
import queue
import sys
import threading
import time
from datetime import datetime, timezone
from typing import Any

import cv2
import numpy as np

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Thermal preprocessing
# ---------------------------------------------------------------------------

def apply_thermal_preprocessing(frame: np.ndarray) -> np.ndarray:
    """
    Apply CLAHE + COLORMAP_INFERNO normalization to a thermal frame.

    Converts to grayscale if needed, applies CLAHE for contrast enhancement,
    then applies the INFERNO colormap to produce a 3-channel output.

    Args:
        frame: Input BGR or grayscale numpy array.

    Returns:
        3-channel BGR numpy array with thermal colormap applied.
    """
    if frame.ndim == 3 and frame.shape[2] == 3:
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    elif frame.ndim == 2:
        gray = frame
    else:
        gray = frame[:, :, 0]

    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    enhanced = clahe.apply(gray)
    colored = cv2.applyColorMap(enhanced, cv2.COLORMAP_INFERNO)
    return colored


# ---------------------------------------------------------------------------
# InferenceEngine
# ---------------------------------------------------------------------------

class InferenceEngine:
    """
    Reads frames from a queue, runs YOLO26 + ByteTrack inference, and
    produces Tracking_Payload dicts.

    Args:
        config: Loaded Config object.
        frame_queue: queue.Queue that camera frames are pushed into.
    """

    def __init__(self, config: Any, frame_queue: queue.Queue) -> None:
        self.config = config
        self.frame_queue = frame_queue
        self.paused = threading.Event()  # set = paused, clear = running
        self.running = False
        self._thread: threading.Thread | None = None
        self.frame_id = 0

        # Load active model profile
        profiles = config.get("model_profiles") or []
        active_name = config.active_model
        active_profile = next(
            (p for p in profiles if p.get("name") == active_name), None
        )
        if active_profile is None:
            logger.error(
                "active_model '%s' not found in model_profiles", active_name
            )
            sys.exit(1)

        self.active_profile = active_profile
        self.model = self._load_model(active_profile["file_path"])

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _load_model(self, file_path: str) -> Any:
        """Load a YOLO model from file_path; exit(1) if not found."""
        if not os.path.exists(file_path):
            logger.error("PT_Model file not found: %s", file_path)
            sys.exit(1)

        try:
            from ultralytics import YOLO  # type: ignore
            model = YOLO(file_path)
            logger.info("Loaded model from %s", file_path)
            return model
        except Exception as exc:  # pragma: no cover
            logger.error("Failed to load model from %s: %s", file_path, exc)
            sys.exit(1)

    def _preprocess_frame(self, frame: np.ndarray) -> np.ndarray:
        """Apply thermal preprocessing if camera_mode == 'thermal'."""
        if self.active_profile.get("camera_mode") == "thermal":
            return apply_thermal_preprocessing(frame)
        return frame

    def _build_payload(self, results: Any) -> dict:
        """Convert ultralytics Results into a Tracking_Payload dict."""
        detections = []
        if results is not None:
            for result in results:
                boxes = result.boxes
                if boxes is None:
                    continue
                for i in range(len(boxes)):
                    track_id_tensor = boxes.id
                    track_id = (
                        int(track_id_tensor[i].item())
                        if track_id_tensor is not None
                        else 0
                    )
                    xyxy = boxes.xyxy[i].tolist()
                    x, y, x2, y2 = xyxy
                    w = x2 - x
                    h = y2 - y
                    conf = float(boxes.conf[i].item())
                    cls_idx = int(boxes.cls[i].item())
                    label = (
                        result.names[cls_idx]
                        if result.names and cls_idx in result.names
                        else str(cls_idx)
                    )
                    detections.append(
                        {
                            "track_id": track_id,
                            "bbox": [x, y, w, h],
                            "confidence": conf,
                            "label": label,
                        }
                    )

        return {
            "device_id": self.config.device_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "frame_id": self.frame_id,
            "active_model": self.active_profile["name"],
            "detections": detections,
        }

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def _run_loop(self) -> None:
        """Main inference loop — runs in a background thread."""
        target_fps = self.config.get("camera.fps", 15)
        frame_interval = 1.0 / max(target_fps, 1)

        while self.running:
            # Honour pause (during model swap)
            if self.paused.is_set():
                time.sleep(0.01)
                continue

            try:
                frame = self.frame_queue.get(timeout=frame_interval)
            except queue.Empty:
                continue

            processed = self._preprocess_frame(frame)

            try:
                results = self.model.track(
                    processed, persist=True, tracker="bytetrack", verbose=False
                )
            except Exception as exc:  # pragma: no cover
                logger.warning("Inference error: %s", exc)
                results = None

            payload = self._build_payload(results)
            self.frame_id += 1

            # Payload is available via callback or can be consumed by caller
            self._on_payload(payload)

        logger.info("Inference loop stopped")

    def _on_payload(self, payload: dict) -> None:
        """
        Called with each produced Tracking_Payload dict.
        Override or monkey-patch in tests / wiring code.
        """

    def start(self) -> None:
        """Start the inference loop in a background thread."""
        self.running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        logger.info("InferenceEngine started")

    def stop(self) -> None:
        """Stop the inference loop."""
        self.running = False
        if self._thread:
            self._thread.join(timeout=5)
        logger.info("InferenceEngine stopped")


# ---------------------------------------------------------------------------
# ModelManager
# ---------------------------------------------------------------------------

class ModelManager:
    """
    Manages named model profiles and supports hot-swapping the active model.

    Args:
        config: Loaded Config object.
        engine: InferenceEngine instance to manage.
    """

    def __init__(self, config: Any, engine: InferenceEngine) -> None:
        self.config = config
        self.engine = engine

        profiles = config.get("model_profiles") or []
        self._registry: dict[str, dict] = {
            p["name"]: p for p in profiles if isinstance(p, dict) and "name" in p
        }
        self._swap_timeout: float = float(
            config.get("model_swap_timeout_s", 5.0)
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_active_model_name(self) -> str:
        """Return the name of the currently active model profile."""
        return self.engine.active_profile.get("name", "")

    def hot_swap(self, model_name: str) -> bool:
        """
        Hot-swap the active model to the named profile.

        Pauses the inference engine, loads the new model in a background
        thread, atomically swaps engine.model and engine.active_profile,
        then resumes inference.

        Args:
            model_name: Name of the model profile to switch to.

        Returns:
            True on success, False if the model_name is unknown or the
            file_path does not exist.
        """
        if model_name not in self._registry:
            logger.error(
                "hot_swap: unknown model name '%s'. Available: %s",
                model_name,
                list(self._registry.keys()),
            )
            return False

        profile = self._registry[model_name]
        file_path = profile.get("file_path", "")

        if not os.path.exists(file_path):
            logger.error(
                "hot_swap: model file not found: %s — retaining current model '%s'",
                file_path,
                self.get_active_model_name(),
            )
            return False

        # Pause inference publishing
        self.engine.paused.set()
        logger.info("hot_swap: paused inference, loading '%s'", model_name)

        result: dict[str, Any] = {"model": None, "error": None}
        done_event = threading.Event()

        def _load() -> None:
            try:
                from ultralytics import YOLO  # type: ignore
                result["model"] = YOLO(file_path)
            except Exception as exc:  # pragma: no cover
                result["error"] = exc
            finally:
                done_event.set()

        loader = threading.Thread(target=_load, daemon=True)
        loader.start()
        finished = done_event.wait(timeout=self._swap_timeout)

        if not finished or result["error"] is not None or result["model"] is None:
            logger.error(
                "hot_swap: failed to load '%s' within %.1fs — retaining current model",
                model_name,
                self._swap_timeout,
            )
            self.engine.paused.clear()
            return False

        # Atomic swap
        self.engine.model = result["model"]
        self.engine.active_profile = profile
        self.engine.paused.clear()
        logger.info("hot_swap: successfully swapped to '%s'", model_name)
        return True
