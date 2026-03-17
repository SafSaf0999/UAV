"""
Tests for main/aggregation/validator.py

Property 2: Tracking Payload Schema Validation Rejects Invalid Payloads
  Validates: Requirements 9.1, 9.2, 9.4

Unit tests:
  - Valid payload passes
  - Missing required field fails
  - Confidence out of range fails
  - Non-dict payload fails
"""

import copy
import pytest
from hypothesis import given, settings, HealthCheck
from hypothesis import strategies as st
from unittest.mock import patch

from main.aggregation.validator import validate_payload


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _valid_payload(**overrides) -> dict:
    base = {
        "device_id": "dev-001",
        "timestamp": "2024-01-01T00:00:00Z",
        "frame_id": 0,
        "detections": [],
    }
    base.update(overrides)
    return base


def _valid_detection(**overrides) -> dict:
    base = {
        "track_id": 1,
        "bbox": [10.0, 20.0, 50.0, 60.0],
        "confidence": 0.9,
        "label": "uav",
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# Property 2: Schema validation rejects invalid payloads
# Feature: anti-uav-detection-system, Property 2: Tracking Payload Schema Validation Rejects Invalid Payloads
# ---------------------------------------------------------------------------

REQUIRED_FIELDS = ["device_id", "timestamp", "frame_id", "detections"]


@given(field=st.sampled_from(REQUIRED_FIELDS))
@settings(max_examples=20, suppress_health_check=[HealthCheck.too_slow])
def test_property2_missing_required_field_rejected(field):
    """
    Property 2: Removing any required field causes validation to fail.
    """
    payload = _valid_payload()
    del payload[field]
    assert validate_payload(payload) is False


@given(
    confidence=st.one_of(
        st.floats(max_value=-0.001, allow_nan=False, allow_infinity=False),
        st.floats(min_value=1.001, max_value=100.0, allow_nan=False, allow_infinity=False),
    )
)
@settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
def test_property2_invalid_confidence_rejected(confidence):
    """
    Property 2: Detection with confidence outside [0.0, 1.0] is rejected.
    """
    payload = _valid_payload(detections=[_valid_detection(confidence=confidence)])
    assert validate_payload(payload) is False


@given(
    frame_id=st.one_of(st.text(min_size=1), st.none(), st.floats(min_value=0.1, max_value=1e6, allow_nan=False, allow_infinity=False))
)
@settings(max_examples=30, suppress_health_check=[HealthCheck.too_slow])
def test_property2_invalid_frame_id_type_rejected(frame_id):
    """
    Property 2: Non-integer frame_id is rejected by schema.
    Whole-number floats (0.0, 1.0) are valid in JSON Schema integer context,
    so we only test clearly non-integer values.
    """
    # Skip whole-number floats — JSON Schema allows them as integers
    if isinstance(frame_id, float) and frame_id == int(frame_id):
        return
    payload = _valid_payload(frame_id=frame_id)
    assert validate_payload(payload) is False


# ---------------------------------------------------------------------------
# Unit tests
# ---------------------------------------------------------------------------

def test_valid_payload_passes():
    assert validate_payload(_valid_payload()) is True


def test_valid_payload_with_detection_passes():
    payload = _valid_payload(detections=[_valid_detection()])
    assert validate_payload(payload) is True


def test_confidence_boundary_zero_passes():
    payload = _valid_payload(detections=[_valid_detection(confidence=0.0)])
    assert validate_payload(payload) is True


def test_confidence_boundary_one_passes():
    payload = _valid_payload(detections=[_valid_detection(confidence=1.0)])
    assert validate_payload(payload) is True


def test_non_dict_rejected():
    assert validate_payload("not a dict") is False
    assert validate_payload([1, 2, 3]) is False
    assert validate_payload(None) is False


def test_missing_device_id_rejected():
    payload = _valid_payload()
    del payload["device_id"]
    assert validate_payload(payload) is False


def test_missing_detections_rejected():
    payload = _valid_payload()
    del payload["detections"]
    assert validate_payload(payload) is False


def test_invalid_bbox_length_rejected():
    # bbox must have exactly 4 items
    payload = _valid_payload(detections=[_valid_detection(bbox=[1.0, 2.0])])
    assert validate_payload(payload) is False


def test_schema_disabled_still_checks_confidence():
    """When schema is None (not loaded), confidence check still runs."""
    with patch("main.aggregation.validator._SCHEMA", None):
        payload = _valid_payload(detections=[_valid_detection(confidence=1.5)])
        assert validate_payload(payload) is False


def test_schema_disabled_valid_payload_passes():
    with patch("main.aggregation.validator._SCHEMA", None):
        assert validate_payload(_valid_payload()) is True
