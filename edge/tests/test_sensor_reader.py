"""
Tests for edge/sensor_reader.py

Property 9: Sensor Payload Fields are Within Valid Ranges
  Validates: Requirements 17.3

Unit tests:
  - Valid payload is published
  - Out-of-range bearing is rejected
  - Out-of-range pitch is rejected
  - NMEA HCHDG parsing
  - NMEA GPRMC parsing
"""

import pytest
from hypothesis import given, settings, HealthCheck
from hypothesis import strategies as st
from unittest.mock import MagicMock

from edge.sensor_reader import build_sensor_payload, _parse_nmea_hchdg, _parse_nmea_gprmc


# ---------------------------------------------------------------------------
# Property 9: Sensor payload fields are within valid ranges
# Feature: anti-uav-detection-system, Property 9: Sensor Payload Fields are Within Valid Ranges
# ---------------------------------------------------------------------------

@given(
    device_id=st.text(min_size=1, max_size=32, alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd"), whitelist_characters="-_")),
    bearing=st.floats(min_value=0.0, max_value=359.9999, allow_nan=False, allow_infinity=False),
    pitch=st.floats(min_value=-90.0, max_value=90.0, allow_nan=False, allow_infinity=False),
)
@settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
def test_property9_sensor_payload_valid_ranges(device_id, bearing, pitch):
    """
    Property 9: Sensor Payload Fields are Within Valid Ranges
    For any valid bearing in [0, 360) and pitch in [-90, 90], build_sensor_payload
    returns a non-None dict with the correct field values.
    """
    payload = build_sensor_payload(device_id, bearing, pitch)
    assert payload is not None
    assert payload["device_id"] == device_id
    assert 0.0 <= payload["compass_bearing_deg"] < 360.0
    assert -90.0 <= payload["pitch_deg"] <= 90.0


@given(
    bearing=st.one_of(
        st.floats(max_value=-0.001, allow_nan=False, allow_infinity=False),
        st.floats(min_value=360.0, allow_nan=False, allow_infinity=False),
    )
)
@settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
def test_property9_invalid_bearing_rejected(bearing):
    """Out-of-range bearing causes build_sensor_payload to return None."""
    result = build_sensor_payload("dev-001", bearing, 0.0)
    assert result is None


@given(
    pitch=st.one_of(
        st.floats(max_value=-90.001, allow_nan=False, allow_infinity=False),
        st.floats(min_value=90.001, allow_nan=False, allow_infinity=False),
    )
)
@settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
def test_property9_invalid_pitch_rejected(pitch):
    """Out-of-range pitch causes build_sensor_payload to return None."""
    result = build_sensor_payload("dev-001", 180.0, pitch)
    assert result is None


# ---------------------------------------------------------------------------
# Unit tests
# ---------------------------------------------------------------------------

def test_valid_payload_has_timestamp():
    payload = build_sensor_payload("dev-001", 90.0, 10.0)
    assert payload is not None
    assert "timestamp" in payload


def test_extra_fields_included():
    payload = build_sensor_payload("dev-001", 45.0, -5.0, extra={"altitude_m": 100})
    assert payload["altitude_m"] == 100


def test_nmea_hchdg_parse():
    sentence = "$HCHDG,270.5,,,0.0,E*00"
    result = _parse_nmea_hchdg(sentence)
    assert result == pytest.approx(270.5)


def test_nmea_hchdg_wraps_360():
    sentence = "$HCHDG,365.0,,,0.0,E*00"
    result = _parse_nmea_hchdg(sentence)
    assert result == pytest.approx(5.0)


def test_nmea_gprmc_parse():
    # Active fix, COG = 123.4
    sentence = "$GPRMC,123519,A,4807.038,N,01131.000,E,022.4,123.4,230394,003.1,W*6A"
    result = _parse_nmea_gprmc(sentence)
    assert result == pytest.approx(123.4)


def test_nmea_gprmc_invalid_fix():
    # Status V = void
    sentence = "$GPRMC,123519,V,4807.038,N,01131.000,E,022.4,123.4,230394,003.1,W*6A"
    result = _parse_nmea_gprmc(sentence)
    assert result is None


def test_nmea_hchdg_malformed():
    assert _parse_nmea_hchdg("$HCHDG") is None
    assert _parse_nmea_hchdg("$HCHDG,notanumber") is None
