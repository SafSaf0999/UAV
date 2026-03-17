"""
Tests for edge/payload.py

Unit tests:
  - build_tracking_payload produces required fields
  - Optional fields (sensor_data, estimated_distance_m, trajectory_vector) included only when provided
  - serialize produces valid UTF-8 JSON bytes
  - deserialize recovers the original dict

Property tests (hypothesis):
  - Property 1: Tracking Payload Round-Trip Serialization
"""

# Feature: anti-uav-detection-system, Property 1: Tracking Payload Round-Trip Serialization

import json
import unittest

import pytest
from hypothesis import given, settings, HealthCheck
from hypothesis import strategies as st

from hypothesis import settings as hyp_settings

hyp_settings.register_profile(
    "ci",
    max_examples=100,
    suppress_health_check=[HealthCheck.too_slow],
)
hyp_settings.load_profile("ci")

from edge.payload import build_tracking_payload, deserialize, serialize


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

_trajectory_vector_st = st.fixed_dictionaries(
    {
        "dx_px_per_frame": st.floats(allow_nan=False, allow_infinity=False),
        "dy_px_per_frame": st.floats(allow_nan=False, allow_infinity=False),
    }
)

_detection_st = st.fixed_dictionaries(
    {
        "track_id": st.integers(min_value=0, max_value=10_000),
        "bbox": st.lists(
            st.floats(min_value=0.0, max_value=4096.0, allow_nan=False, allow_infinity=False),
            min_size=4,
            max_size=4,
        ),
        "confidence": st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
        "label": st.text(min_size=1, max_size=32),
    }
).flatmap(
    lambda base: st.one_of(
        # No optional fields
        st.just(base),
        # With estimated_distance_m
        st.floats(min_value=0.0, max_value=10_000.0, allow_nan=False, allow_infinity=False).map(
            lambda d: {**base, "estimated_distance_m": d}
        ),
        # With trajectory_vector
        _trajectory_vector_st.map(lambda tv: {**base, "trajectory_vector": tv}),
        # With both
        st.tuples(
            st.floats(min_value=0.0, max_value=10_000.0, allow_nan=False, allow_infinity=False),
            _trajectory_vector_st,
        ).map(lambda pair: {**base, "estimated_distance_m": pair[0], "trajectory_vector": pair[1]}),
    )
)

_sensor_data_st = st.fixed_dictionaries(
    {
        "compass_bearing_deg": st.floats(min_value=0.0, max_value=360.0, allow_nan=False, allow_infinity=False),
        "pitch_deg": st.floats(min_value=-90.0, max_value=90.0, allow_nan=False, allow_infinity=False),
    }
)

_payload_st = st.fixed_dictionaries(
    {
        "device_id": st.text(min_size=1, max_size=64),
        "frame_id": st.integers(min_value=0, max_value=2**31 - 1),
        "results": st.lists(_detection_st, min_size=0, max_size=8),
        "active_model": st.text(min_size=1, max_size=64),
    }
).flatmap(
    lambda base: st.one_of(
        st.just({**base, "sensor_data": None}),
        _sensor_data_st.map(lambda sd: {**base, "sensor_data": sd}),
    )
)


# ---------------------------------------------------------------------------
# Unit Tests
# ---------------------------------------------------------------------------

class TestBuildTrackingPayload(unittest.TestCase):

    def _minimal_result(self):
        return {"track_id": 1, "bbox": [10.0, 20.0, 50.0, 60.0], "confidence": 0.9, "label": "uav"}

    def test_required_fields_present(self):
        payload = build_tracking_payload("edge-01", 0, [], "daylight-v1")
        for field in ("device_id", "timestamp", "frame_id", "active_model", "source", "detections"):
            self.assertIn(field, payload)

    def test_device_id_and_frame_id(self):
        payload = build_tracking_payload("edge-42", 7, [], "thermal-v1")
        self.assertEqual(payload["device_id"], "edge-42")
        self.assertEqual(payload["frame_id"], 7)
        self.assertEqual(payload["active_model"], "thermal-v1")

    def test_default_source_is_camera(self):
        payload = build_tracking_payload("edge-01", 0, [], "daylight-v1")
        self.assertEqual(payload["source"], "camera")

    def test_detections_mapped_correctly(self):
        results = [self._minimal_result()]
        payload = build_tracking_payload("edge-01", 1, results, "daylight-v1")
        self.assertEqual(len(payload["detections"]), 1)
        det = payload["detections"][0]
        self.assertEqual(det["track_id"], 1)
        self.assertEqual(det["bbox"], [10.0, 20.0, 50.0, 60.0])
        self.assertAlmostEqual(det["confidence"], 0.9)
        self.assertEqual(det["label"], "uav")

    def test_optional_estimated_distance_included(self):
        results = [{**self._minimal_result(), "estimated_distance_m": 42.5}]
        payload = build_tracking_payload("edge-01", 0, results, "daylight-v1")
        self.assertIn("estimated_distance_m", payload["detections"][0])
        self.assertAlmostEqual(payload["detections"][0]["estimated_distance_m"], 42.5)

    def test_optional_trajectory_vector_included(self):
        tv = {"dx_px_per_frame": 1.5, "dy_px_per_frame": -0.3}
        results = [{**self._minimal_result(), "trajectory_vector": tv}]
        payload = build_tracking_payload("edge-01", 0, results, "daylight-v1")
        self.assertIn("trajectory_vector", payload["detections"][0])

    def test_optional_fields_absent_when_not_provided(self):
        results = [self._minimal_result()]
        payload = build_tracking_payload("edge-01", 0, results, "daylight-v1")
        det = payload["detections"][0]
        self.assertNotIn("estimated_distance_m", det)
        self.assertNotIn("trajectory_vector", det)

    def test_sensor_data_included_when_provided(self):
        sd = {"compass_bearing_deg": 270.0, "pitch_deg": -5.0}
        payload = build_tracking_payload("edge-01", 0, [], "daylight-v1", sensor_data=sd)
        self.assertIn("sensor_data", payload)
        self.assertAlmostEqual(payload["sensor_data"]["compass_bearing_deg"], 270.0)

    def test_sensor_data_absent_when_none(self):
        payload = build_tracking_payload("edge-01", 0, [], "daylight-v1", sensor_data=None)
        self.assertNotIn("sensor_data", payload)

    def test_timestamp_is_iso8601_utc(self):
        from datetime import datetime, timezone
        payload = build_tracking_payload("edge-01", 0, [], "daylight-v1")
        ts = payload["timestamp"]
        # Must parse without error and be timezone-aware
        parsed = datetime.fromisoformat(ts)
        self.assertIsNotNone(parsed.tzinfo)

    def test_empty_detections(self):
        payload = build_tracking_payload("edge-01", 0, [], "daylight-v1")
        self.assertEqual(payload["detections"], [])


class TestSerializeDeserialize(unittest.TestCase):

    def _make_payload(self):
        return build_tracking_payload(
            "edge-01", 5,
            [{"track_id": 2, "bbox": [0.0, 0.0, 100.0, 80.0], "confidence": 0.75, "label": "uav"}],
            "daylight-v1",
        )

    def test_serialize_returns_bytes(self):
        payload = self._make_payload()
        data = serialize(payload)
        self.assertIsInstance(data, bytes)

    def test_serialize_is_valid_json(self):
        payload = self._make_payload()
        data = serialize(payload)
        parsed = json.loads(data.decode("utf-8"))
        self.assertIsInstance(parsed, dict)

    def test_deserialize_recovers_dict(self):
        payload = self._make_payload()
        data = serialize(payload)
        recovered = deserialize(data)
        self.assertEqual(payload, recovered)

    def test_round_trip_empty_detections(self):
        payload = build_tracking_payload("edge-02", 0, [], "thermal-v1")
        self.assertEqual(payload, deserialize(serialize(payload)))


# ---------------------------------------------------------------------------
# Property 1: Tracking Payload Round-Trip Serialization
# ---------------------------------------------------------------------------

@given(params=_payload_st)
@settings(max_examples=100)
def test_property_1_round_trip_serialization(params):
    """
    # Feature: anti-uav-detection-system, Property 1: Tracking Payload Round-Trip Serialization
    **Validates: Requirements 9.3**

    For any valid Tracking_Payload produced by build_tracking_payload,
    serialize → deserialize must produce a structurally equal dict.
    """
    payload = build_tracking_payload(
        device_id=params["device_id"],
        frame_id=params["frame_id"],
        results=params["results"],
        active_model=params["active_model"],
        sensor_data=params["sensor_data"],
    )
    recovered = deserialize(serialize(payload))
    assert payload == recovered, (
        f"Round-trip mismatch.\nOriginal: {payload}\nRecovered: {recovered}"
    )
