"""
Edge device — Tracking_Payload builder and serialization.

Provides:
  build_tracking_payload(device_id, frame_id, results, active_model, sensor_data=None) -> dict
  serialize(payload: dict) -> bytes
  deserialize(data: bytes) -> dict

No jsonschema dependency — validation is handled by the aggregation service.
"""

import json
from datetime import datetime, timezone
from typing import Any


def build_tracking_payload(
    device_id: str,
    frame_id: int,
    results: list[dict],
    active_model: str,
    sensor_data: dict | None = None,
    source: str = "camera",
) -> dict:
    """
    Build a Tracking_Payload dict from inference results.

    Args:
        device_id:    Unique identifier for this edge device.
        frame_id:     Monotonically increasing frame counter (>= 0).
        results:      List of detection dicts, each with keys:
                        track_id (int), bbox [x,y,w,h], confidence (float),
                        label (str), and optionally estimated_distance_m (float)
                        and trajectory_vector {"dx_px_per_frame", "dy_px_per_frame"}.
        active_model: Name of the currently active model profile.
        sensor_data:  Optional dict with compass_bearing_deg and/or pitch_deg.
        source:       "camera" (default) or "radar".

    Returns:
        A dict conforming to tracking_payload.schema.json.
    """
    detections = []
    for r in results:
        det: dict[str, Any] = {
            "track_id": int(r["track_id"]),
            "bbox": [float(v) for v in r["bbox"]],
            "confidence": float(r["confidence"]),
            "label": str(r["label"]),
        }
        if "estimated_distance_m" in r:
            det["estimated_distance_m"] = float(r["estimated_distance_m"])
        if "trajectory_vector" in r:
            tv = r["trajectory_vector"]
            det["trajectory_vector"] = {
                "dx_px_per_frame": float(tv["dx_px_per_frame"]),
                "dy_px_per_frame": float(tv["dy_px_per_frame"]),
            }
        detections.append(det)

    payload: dict[str, Any] = {
        "device_id": device_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "frame_id": int(frame_id),
        "active_model": active_model,
        "source": source,
        "detections": detections,
    }

    if sensor_data is not None:
        payload["sensor_data"] = {k: v for k, v in sensor_data.items()}

    return payload


def serialize(payload: dict) -> bytes:
    """Encode a Tracking_Payload dict to UTF-8 JSON bytes."""
    return json.dumps(payload, ensure_ascii=False).encode("utf-8")


def deserialize(data: bytes) -> dict:
    """Decode UTF-8 JSON bytes back to a Tracking_Payload dict."""
    return json.loads(data.decode("utf-8"))
