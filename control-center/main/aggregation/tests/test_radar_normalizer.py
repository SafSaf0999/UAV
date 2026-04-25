"""
Tests for main/aggregation/radar_normalizer.py

Property 6: Radar Track Normalization Preserves Required Fields
  Validates: Requirements 14.2

Unit tests for normalize_radar_track.
"""

import pytest
from hypothesis import given, settings, HealthCheck
from hypothesis import strategies as st
from unittest.mock import patch

from main.aggregation.radar_normalizer import normalize_radar_track


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _raw_track(**overrides) -> dict:
    base = {
        "device_id": "radar-001",
        "track_id": 1,
        "x_m": 100.0,
        "y_m": 200.0,
        "confidence": 0.95,
        "timestamp": "2024-01-01T00:00:00Z",
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# Property 6: Radar track normalization preserves required fields
# Feature: anti-uav-detection-system, Property 6: Radar Track Normalization Preserves Required Fields
# ---------------------------------------------------------------------------

@given(
    device_id=st.text(min_size=1, max_size=32, alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd"), whitelist_characters="-_")),
    track_id=st.integers(min_value=0, max_value=9999),
    confidence=st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
    x_m=st.floats(min_value=-10000.0, max_value=10000.0, allow_nan=False, allow_infinity=False),
    y_m=st.floats(min_value=-10000.0, max_value=10000.0, allow_nan=False, allow_infinity=False),
)
@settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
def test_property6_radar_normalization_preserves_required_fields(
    device_id, track_id, confidence, x_m, y_m
):
    """
    Property 6: Radar Track Normalization Preserves Required Fields
    For any valid radar track, normalize_radar_track returns a dict with
    source="radar", label="radar", and passes schema validation.
    """
    raw = _raw_track(
        device_id=device_id,
        track_id=track_id,
        confidence=confidence,
        x_m=x_m,
        y_m=y_m,
    )
    result = normalize_radar_track(raw)
    assert result is not None
    assert result["source"] == "radar"
    assert result["device_id"] == device_id
    assert len(result["detections"]) == 1
    assert result["detections"][0]["label"] == "radar"
    assert result["detections"][0]["confidence"] == pytest.approx(confidence, abs=1e-6)


# ---------------------------------------------------------------------------
# Unit tests
# ---------------------------------------------------------------------------

def test_normalize_basic():
    result = normalize_radar_track(_raw_track())
    assert result is not None
    assert result["source"] == "radar"
    assert result["detections"][0]["label"] == "radar"


def test_normalize_non_dict_returns_none():
    assert normalize_radar_track("not a dict") is None
    assert normalize_radar_track(None) is None
    assert normalize_radar_track([1, 2, 3]) is None


def test_normalize_confidence_clamped():
    # Confidence > 1.0 should be clamped to 1.0
    result = normalize_radar_track(_raw_track(confidence=1.5))
    assert result is not None
    assert result["detections"][0]["confidence"] == pytest.approx(1.0)


def test_normalize_confidence_negative_clamped():
    result = normalize_radar_track(_raw_track(confidence=-0.5))
    assert result is not None
    assert result["detections"][0]["confidence"] == pytest.approx(0.0)


def test_normalize_missing_device_id_uses_default():
    raw = _raw_track()
    del raw["device_id"]
    result = normalize_radar_track(raw)
    assert result is not None
    assert result["device_id"] == "radar-unknown"


def test_normalize_uses_range_azimuth_fallback():
    raw = {"device_id": "radar-002", "track_id": 5, "range_m": 500.0, "azimuth_deg": 45.0,
           "confidence": 0.8, "timestamp": "2024-01-01T00:00:00Z"}
    result = normalize_radar_track(raw)
    assert result is not None
    bbox = result["detections"][0]["bbox"]
    assert bbox[0] == pytest.approx(500.0)
    assert bbox[1] == pytest.approx(45.0)


def test_normalize_timestamp_defaults_to_now():
    raw = _raw_track()
    del raw["timestamp"]
    result = normalize_radar_track(raw)
    assert result is not None
    assert "T" in result["timestamp"]  # ISO-8601 format
