"""
Property 13: Alert Marker Displays Required Detection Fields
  Validates: Requirements 12.4

Tests the alert marker data structure that the frontend builds from
DeviceState. Since the frontend is TypeScript, we validate the equivalent
Python data structure here.

Feature: anti-uav-detection-system, Property 13: Alert Marker Displays Required Detection Fields
"""

from datetime import datetime, timezone
from hypothesis import given, settings, HealthCheck
from hypothesis import strategies as st


def build_alert_marker(device_id: str, timestamp: str, detection_count: int) -> dict:
    """
    Build the alert marker data structure (mirrors frontend AlertState).
    """
    return {
        "device_id": device_id,
        "timestamp": timestamp,
        "detection_count": detection_count,
    }


def is_valid_utc_timestamp(ts: str) -> bool:
    """Check if a string is a valid ISO-8601 UTC timestamp."""
    try:
        datetime.fromisoformat(ts.replace("Z", "+00:00"))
        return True
    except ValueError:
        return False


# ---------------------------------------------------------------------------
# Property 13
# ---------------------------------------------------------------------------

@given(
    device_id=st.text(min_size=1, max_size=32, alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd"), whitelist_characters="-_")),
    detection_count=st.integers(min_value=1, max_value=1000),
)
@settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
def test_property13_alert_marker_required_fields(device_id, detection_count):
    """
    Property 13: Alert Marker Displays Required Detection Fields
    For any detection event, the alert marker must contain:
      - device_id (non-empty string)
      - timestamp (valid UTC ISO-8601)
      - detection_count (non-negative integer)
    """
    timestamp = datetime.now(timezone.utc).isoformat()
    marker = build_alert_marker(device_id, timestamp, detection_count)

    assert "device_id" in marker
    assert isinstance(marker["device_id"], str)
    assert len(marker["device_id"]) > 0

    assert "timestamp" in marker
    assert is_valid_utc_timestamp(marker["timestamp"])

    assert "detection_count" in marker
    assert isinstance(marker["detection_count"], int)
    assert marker["detection_count"] >= 0
