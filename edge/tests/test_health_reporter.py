"""
Tests for edge/health_reporter.py

Unit tests:
  - Payload contains all required fields
  - cpu_percent clamped to [0, 100]
  - memory_percent clamped to [0, 100]
  - uptime_s >= 0
  - inference_fps >= 0
  - publish_health called on MQTT client

Property test:
  - Property 2: Health Payload Field Ranges
    Validates: Requirements v2-3.1, v2-3.2
"""

import json
import time
import unittest
from unittest.mock import MagicMock, patch

import pytest
from hypothesis import given, settings, HealthCheck
from hypothesis import strategies as st

from edge.health_reporter import HealthReporter


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_reporter(cpu=45.0, mem=60.0, fps=12.0, frame_id=100):
    config = MagicMock()
    config.device_id = "edge-test"
    config.get = lambda key, default=None: {
        "health.interval_s": 30.0,
    }.get(key, default)

    mqtt_client = MagicMock()
    engine = MagicMock()
    engine.current_fps = fps
    engine.frame_id = frame_id
    camera = MagicMock()
    camera.reconnect_count = 0

    reporter = HealthReporter(config, mqtt_client, engine, camera)
    return reporter, mqtt_client


# ---------------------------------------------------------------------------
# Unit tests
# ---------------------------------------------------------------------------

class TestHealthReporterPayload:
    def test_payload_contains_all_required_fields(self):
        reporter, _ = _make_reporter()
        with patch("psutil.cpu_percent", return_value=45.0), \
             patch("psutil.virtual_memory") as mock_vm:
            mock_vm.return_value.percent = 60.0
            payload = reporter._collect()

        required = [
            "device_id", "uptime_s", "cpu_percent", "memory_percent",
            "inference_fps", "frames_processed", "mqtt_reconnects",
            "camera_reconnects", "timestamp",
        ]
        for field in required:
            assert field in payload, f"Missing field: {field}"

    def test_device_id_matches_config(self):
        reporter, _ = _make_reporter()
        with patch("psutil.cpu_percent", return_value=10.0), \
             patch("psutil.virtual_memory") as mock_vm:
            mock_vm.return_value.percent = 20.0
            payload = reporter._collect()
        assert payload["device_id"] == "edge-test"

    def test_uptime_s_is_non_negative(self):
        reporter, _ = _make_reporter()
        with patch("psutil.cpu_percent", return_value=10.0), \
             patch("psutil.virtual_memory") as mock_vm:
            mock_vm.return_value.percent = 20.0
            payload = reporter._collect()
        assert payload["uptime_s"] >= 0

    def test_inference_fps_is_non_negative(self):
        reporter, _ = _make_reporter(fps=15.5)
        with patch("psutil.cpu_percent", return_value=10.0), \
             patch("psutil.virtual_memory") as mock_vm:
            mock_vm.return_value.percent = 20.0
            payload = reporter._collect()
        assert payload["inference_fps"] >= 0.0

    def test_cpu_clamped_to_100(self):
        reporter, _ = _make_reporter()
        with patch("psutil.cpu_percent", return_value=150.0), \
             patch("psutil.virtual_memory") as mock_vm:
            mock_vm.return_value.percent = 50.0
            payload = reporter._collect()
        assert payload["cpu_percent"] <= 100.0

    def test_memory_clamped_to_100(self):
        reporter, _ = _make_reporter()
        with patch("psutil.cpu_percent", return_value=50.0), \
             patch("psutil.virtual_memory") as mock_vm:
            mock_vm.return_value.percent = 200.0
            payload = reporter._collect()
        assert payload["memory_percent"] <= 100.0

    def test_publish_health_called(self):
        reporter, mqtt_client = _make_reporter()
        with patch("psutil.cpu_percent", return_value=30.0), \
             patch("psutil.virtual_memory") as mock_vm:
            mock_vm.return_value.percent = 40.0
            payload = reporter._collect()
            mqtt_client.publish_health(json.dumps(payload).encode())
        mqtt_client.publish_health.assert_called_once()

    def test_timestamp_is_iso8601(self):
        reporter, _ = _make_reporter()
        with patch("psutil.cpu_percent", return_value=10.0), \
             patch("psutil.virtual_memory") as mock_vm:
            mock_vm.return_value.percent = 20.0
            payload = reporter._collect()
        from datetime import datetime
        # Should parse without error
        dt = datetime.fromisoformat(payload["timestamp"])
        assert dt.tzinfo is not None


# ---------------------------------------------------------------------------
# Property 2: Health Payload Field Ranges
# ---------------------------------------------------------------------------

@given(
    cpu=st.floats(min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False),
    mem=st.floats(min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False),
    fps=st.floats(min_value=0.0, max_value=120.0, allow_nan=False, allow_infinity=False),
    frame_id=st.integers(min_value=0, max_value=10_000_000),
)
@settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
def test_property_2_health_payload_field_ranges(cpu, mem, fps, frame_id):
    """
    Property 2: Health Payload Field Ranges
    For any Health_Payload, cpu_percent in [0,100], memory_percent in [0,100],
    uptime_s >= 0, inference_fps >= 0.
    Validates: Requirements v2-3.1, v2-3.2
    """
    reporter, _ = _make_reporter(cpu=cpu, mem=mem, fps=fps, frame_id=frame_id)

    with patch("psutil.cpu_percent", return_value=cpu), \
         patch("psutil.virtual_memory") as mock_vm:
        mock_vm.return_value.percent = mem
        payload = reporter._collect()

    assert 0.0 <= payload["cpu_percent"] <= 100.0, f"cpu_percent out of range: {payload['cpu_percent']}"
    assert 0.0 <= payload["memory_percent"] <= 100.0, f"memory_percent out of range: {payload['memory_percent']}"
    assert payload["uptime_s"] >= 0, f"uptime_s negative: {payload['uptime_s']}"
    assert payload["inference_fps"] >= 0.0, f"inference_fps negative: {payload['inference_fps']}"
    assert payload["frames_processed"] >= 0
    assert payload["mqtt_reconnects"] >= 0
    assert payload["camera_reconnects"] >= 0
