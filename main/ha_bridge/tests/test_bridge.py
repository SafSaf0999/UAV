"""
Tests for main/ha_bridge/bridge.py

Unit tests:
  - Discovery config contains required fields (unique_id, name, state_topic, device block)
  - State update published after tracking message
  - binary_sensor ON when detection_count > 0
  - binary_sensor OFF when no detections

Property test:
  - Property 5: Backend Bridge Discovery Config Contains Required Fields
    Validates: Requirements v2-11.3, v2-11.6
"""

import json
import sys
import importlib.util
from pathlib import Path
from unittest.mock import MagicMock, call

import pytest
from hypothesis import given, settings, HealthCheck
from hypothesis import strategies as st

# ---------------------------------------------------------------------------
# Import bridge module directly (not a package import)
# ---------------------------------------------------------------------------

_BRIDGE_PATH = Path(__file__).parent.parent / "bridge.py"

def _load_bridge():
    spec = importlib.util.spec_from_file_location("bridge", _BRIDGE_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

bridge = _load_bridge()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_mqtt_client():
    return MagicMock()


def _make_tracking_payload(device_id: str, detections: list) -> dict:
    return {
        "device_id": device_id,
        "timestamp": "2026-01-01T00:00:00Z",
        "frame_id": 1,
        "active_model": "daylight-v1",
        "detections": detections,
    }


def _make_detection(label: str) -> dict:
    return {"track_id": 1, "bbox": [0, 0, 10, 10], "confidence": 0.9, "label": label}


# ---------------------------------------------------------------------------
# Unit tests — discovery config structure
# ---------------------------------------------------------------------------

class TestDiscoveryConfig:
    def test_sensor_config_has_required_fields(self):
        config = bridge._sensor_config("edge-01", "detection_count", "Detection Count")
        assert "unique_id" in config
        assert "name" in config
        assert "state_topic" in config
        assert "device" in config
        assert "identifiers" in config["device"]

    def test_binary_sensor_config_has_required_fields(self):
        config = bridge._binary_sensor_config("edge-01", "uav_detected", "UAV Detected")
        assert "unique_id" in config
        assert "name" in config
        assert "state_topic" in config
        assert "device" in config
        assert "identifiers" in config["device"]

    def test_unique_id_contains_device_id(self):
        config = bridge._sensor_config("edge-01", "cpu_percent", "CPU")
        assert "edge_01" in config["unique_id"] or "edge-01" in config["unique_id"]

    def test_state_topic_contains_device_id(self):
        config = bridge._sensor_config("edge-01", "detection_count", "Detection Count")
        assert "edge-01" in config["state_topic"]

    def test_publish_discovery_calls_publish_for_each_entity(self):
        client = _make_mqtt_client()
        bridge.publish_discovery(client, "edge-01")
        # Should publish at least 8 configs (binary_sensor + 7 sensors)
        assert client.publish.call_count >= 8

    def test_publish_discovery_uses_retain(self):
        client = _make_mqtt_client()
        bridge.publish_discovery(client, "edge-01")
        for c in client.publish.call_args_list:
            assert c.kwargs.get("retain") is True or (len(c.args) >= 4 and c.args[3] is True)

    def test_publish_discovery_per_class_sensor(self):
        client = _make_mqtt_client()
        bridge.publish_discovery(client, "edge-01", class_labels=["drone", "bird"])
        topics = [c.args[0] for c in client.publish.call_args_list]
        assert any("class_drone" in t for t in topics)
        assert any("class_bird" in t for t in topics)


# ---------------------------------------------------------------------------
# Unit tests — state updates
# ---------------------------------------------------------------------------

class TestStateUpdates:
    def test_tracking_publishes_detection_count(self):
        client = _make_mqtt_client()
        payload = _make_tracking_payload("edge-01", [_make_detection("drone")])
        bridge.publish_tracking_state(client, "edge-01", payload)
        topics = [c.args[0] for c in client.publish.call_args_list]
        assert any("detection_count" in t for t in topics)

    def test_binary_sensor_on_when_detections(self):
        client = _make_mqtt_client()
        payload = _make_tracking_payload("edge-01", [_make_detection("drone")])
        bridge.publish_tracking_state(client, "edge-01", payload)
        # Find the binary_sensor state publish
        for c in client.publish.call_args_list:
            if "uav_detected" in c.args[0]:
                assert c.args[1] == "ON"
                return
        pytest.fail("binary_sensor state not published")

    def test_binary_sensor_off_when_no_detections(self):
        client = _make_mqtt_client()
        payload = _make_tracking_payload("edge-01", [])
        bridge.publish_tracking_state(client, "edge-01", payload)
        for c in client.publish.call_args_list:
            if "uav_detected" in c.args[0]:
                assert c.args[1] == "OFF"
                return
        pytest.fail("binary_sensor state not published")

    def test_health_publishes_cpu_percent(self):
        client = _make_mqtt_client()
        bridge.publish_health_state(client, "edge-01", {"cpu_percent": 45.0})
        topics = [c.args[0] for c in client.publish.call_args_list]
        assert any("cpu_percent" in t for t in topics)

    def test_sensor_publishes_compass_bearing(self):
        client = _make_mqtt_client()
        bridge.publish_sensor_state(client, "edge-01", {"compass_bearing_deg": 270.0})
        topics = [c.args[0] for c in client.publish.call_args_list]
        assert any("compass_bearing" in t for t in topics)


# ---------------------------------------------------------------------------
# Property 5: Discovery Config Contains Required Fields
# ---------------------------------------------------------------------------

@given(
    device_id=st.from_regex(r"[a-z][a-z0-9\-]{0,20}", fullmatch=True),
    entity=st.from_regex(r"[a-z][a-z0-9_]{0,20}", fullmatch=True),
    name=st.text(min_size=1, max_size=64),
)
@settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
def test_property_5_discovery_config_required_fields(device_id, entity, name):
    """
    Property 5: Backend Bridge Discovery Config Contains Required Fields
    For any device_id, the discovery config must contain unique_id, name,
    state_topic, and a device block with identifiers.
    Validates: Requirements v2-11.3, v2-11.6
    """
    config = bridge._sensor_config(device_id, entity, name)

    assert "unique_id" in config and len(config["unique_id"]) > 0
    assert "name" in config and len(config["name"]) > 0
    assert "state_topic" in config and len(config["state_topic"]) > 0
    assert "device" in config
    assert "identifiers" in config["device"]
    assert len(config["device"]["identifiers"]) > 0

    # state_topic must contain device_id
    assert device_id in config["state_topic"]
