"""
Aggregation service — radar track normalizer (optional).

Maps raw radar track fields to the Tracking_Payload schema with
source="radar" and label="radar". Validates output against the schema.
Logs a warning every 60s if the radar source is unreachable.

Requirements: 14.1, 14.2, 14.4, 14.5
"""

import logging
import time
from datetime import datetime, timezone
from typing import Optional

from main.aggregation.validator import validate_payload

logger = logging.getLogger(__name__)

# Warn at most once per 60 seconds about unreachable radar
_last_radar_warning: float = 0.0
_RADAR_WARN_INTERVAL = 60.0


def normalize_radar_track(raw_track: dict) -> Optional[dict]:
    """
    Normalize a raw radar track dict to a Tracking_Payload-compatible dict.

    Expected raw_track fields (all optional except device_id):
      device_id:    str   — radar source identifier
      track_id:     int   — radar track number
      x_m:          float — target X position in metres (used as bbox proxy)
      y_m:          float — target Y position in metres
      range_m:      float — slant range in metres
      azimuth_deg:  float — azimuth angle in degrees
      confidence:   float — detection confidence [0.0, 1.0]
      timestamp:    str   — ISO-8601 timestamp (defaults to now)

    Returns:
        Normalized Tracking_Payload dict, or None if validation fails.
    """
    if not isinstance(raw_track, dict):
        logger.warning("radar_normalizer: raw_track is not a dict")
        return None

    device_id = raw_track.get("device_id", "radar-unknown")
    track_id = int(raw_track.get("track_id", 0))
    confidence = float(raw_track.get("confidence", 1.0))
    confidence = max(0.0, min(1.0, confidence))

    # Build a synthetic bbox from range/azimuth or x/y
    # Use a fixed 10px proxy width since radar doesn't have pixel coords
    x = float(raw_track.get("x_m", raw_track.get("range_m", 0.0)))
    y = float(raw_track.get("y_m", raw_track.get("azimuth_deg", 0.0)))
    bbox = [x, y, 10.0, 10.0]  # [x, y, w, h] — symbolic for radar

    timestamp = raw_track.get("timestamp") or datetime.now(timezone.utc).isoformat()

    normalized = {
        "device_id": device_id,
        "timestamp": timestamp,
        "frame_id": track_id,
        "source": "radar",
        "active_model": "radar",
        "detections": [
            {
                "track_id": track_id,
                "bbox": bbox,
                "confidence": confidence,
                "label": "radar",
            }
        ],
    }

    if not validate_payload(normalized):
        logger.warning(
            "radar_normalizer: normalized track failed schema validation for device '%s'",
            device_id,
        )
        return None

    return normalized


def warn_radar_unreachable(source_name: str = "radar") -> None:
    """
    Log a warning that the radar source is unreachable.
    Rate-limited to once per 60 seconds.
    """
    global _last_radar_warning
    now = time.monotonic()
    if now - _last_radar_warning >= _RADAR_WARN_INTERVAL:
        logger.warning(
            "radar_normalizer: radar source '%s' is unreachable", source_name
        )
        _last_radar_warning = now
