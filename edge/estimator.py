"""
Edge device — distance and trajectory estimator (optional).

Provides:
  estimate_distance(bbox_width_px, frame_width_px, fov_deg, reference_size_m)
    → estimated distance in metres using the pinhole camera formula.

  estimate_trajectory(centroid_history, window_frames)
    → (dx, dy) mean displacement vector over the last window_frames frames.

Results are attached to the Tracking_Payload as:
  "estimated_distance_m"  (float, metres)
  "trajectory_vector"     {"dx": float, "dy": float}

Requirements: 17.1, 17.2, 17.5, 17.7
"""

import logging
import math
from typing import List, Optional, Tuple

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Distance estimation — pinhole camera model
# ---------------------------------------------------------------------------

def estimate_distance(
    bbox_width_px: float,
    frame_width_px: float,
    fov_deg: float,
    reference_size_m: float,
) -> float:
    """
    Estimate the distance to a UAV using the pinhole camera formula.

    Formula:
        focal_length_px = frame_width_px / (2 * tan(fov_deg/2))
        distance_m      = (reference_size_m * focal_length_px) / bbox_width_px

    Args:
        bbox_width_px:    Width of the detection bounding box in pixels.
        frame_width_px:   Width of the full frame in pixels.
        fov_deg:          Horizontal field of view of the camera in degrees.
        reference_size_m: Known physical width of the UAV in metres.

    Returns:
        Estimated distance in metres (always positive).

    Raises:
        ValueError: If any argument is non-positive.
    """
    if bbox_width_px <= 0:
        raise ValueError(f"bbox_width_px must be > 0, got {bbox_width_px}")
    if frame_width_px <= 0:
        raise ValueError(f"frame_width_px must be > 0, got {frame_width_px}")
    if fov_deg <= 0 or fov_deg >= 180:
        raise ValueError(f"fov_deg must be in (0, 180), got {fov_deg}")
    if reference_size_m <= 0:
        raise ValueError(f"reference_size_m must be > 0, got {reference_size_m}")

    focal_length_px = frame_width_px / (2.0 * math.tan(math.radians(fov_deg / 2.0)))
    distance_m = (reference_size_m * focal_length_px) / bbox_width_px
    return distance_m


# ---------------------------------------------------------------------------
# Trajectory estimation
# ---------------------------------------------------------------------------

def estimate_trajectory(
    centroid_history: List[Tuple[float, float]],
    window_frames: int = 10,
) -> Optional[dict]:
    """
    Estimate the trajectory vector as the mean of frame-to-frame displacements.

    Args:
        centroid_history: List of (cx, cy) centroid positions, oldest first.
        window_frames:    Number of recent frames to consider.

    Returns:
        {"dx": float, "dy": float} mean displacement per frame,
        or None if fewer than 2 points are available.
    """
    if len(centroid_history) < 2:
        return None

    # Use the last window_frames+1 points to get window_frames displacements
    recent = centroid_history[-(window_frames + 1):]
    displacements = [
        (recent[i + 1][0] - recent[i][0], recent[i + 1][1] - recent[i][1])
        for i in range(len(recent) - 1)
    ]

    if not displacements:
        return None

    dx = sum(d[0] for d in displacements) / len(displacements)
    dy = sum(d[1] for d in displacements) / len(displacements)
    return {"dx": dx, "dy": dy}


# ---------------------------------------------------------------------------
# Estimator — attaches results to payload dicts
# ---------------------------------------------------------------------------

class Estimator:
    """
    Wraps distance and trajectory estimation and attaches results to payloads.

    Args:
        config: Loaded Config object.
    """

    def __init__(self, config) -> None:
        self._enabled: bool = bool(config.get("estimator.enabled", False))
        self._fov_deg: float = float(config.get("estimator.fov_deg", 60.0))
        self._reference_size_m: float = float(config.get("estimator.reference_size_m", 0.5))
        self._window_frames: int = int(config.get("estimator.window_frames", 10))
        # Per-track centroid history: {track_id: [(cx, cy), ...]}
        self._histories: dict = {}

    def annotate_payload(self, payload: dict, frame_width_px: int) -> dict:
        """
        Annotate a Tracking_Payload dict with distance and trajectory estimates.

        Modifies payload in-place and returns it.
        """
        if not self._enabled:
            return payload

        for detection in payload.get("detections", []):
            bbox = detection.get("bbox")  # [x, y, w, h]
            track_id = detection.get("track_id")
            if bbox is None or len(bbox) < 4:
                continue

            bbox_width_px = float(bbox[2])
            cx = float(bbox[0]) + bbox_width_px / 2.0
            cy = float(bbox[1]) + float(bbox[3]) / 2.0

            # Distance
            try:
                dist = estimate_distance(
                    bbox_width_px, frame_width_px, self._fov_deg, self._reference_size_m
                )
                detection["estimated_distance_m"] = round(dist, 2)
            except ValueError as exc:
                logger.debug("Estimator: distance skipped: %s", exc)

            # Trajectory
            if track_id is not None:
                history = self._histories.setdefault(track_id, [])
                history.append((cx, cy))
                # Keep history bounded
                if len(history) > self._window_frames + 1:
                    self._histories[track_id] = history[-(self._window_frames + 1):]
                traj = estimate_trajectory(history, self._window_frames)
                if traj is not None:
                    detection["trajectory_vector"] = traj

        return payload
