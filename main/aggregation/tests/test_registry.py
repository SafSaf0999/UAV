"""
Tests for main/aggregation/registry.py

Property 3: Device Registry Reflects Status Messages
  Validates: Requirements 4.3

Unit tests for DeviceRegistry.
"""

import asyncio
import pytest
from hypothesis import given, settings, HealthCheck
from hypothesis import strategies as st

from main.aggregation.registry import DeviceRegistry


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def run(coro):
    return asyncio.run(coro)


def _status_payload(device_id: str, status: str) -> dict:
    return {
        "device_id": device_id,
        "status": status,
        "timestamp": "2024-01-01T00:00:00Z",
    }


# ---------------------------------------------------------------------------
# Property 3: Device registry reflects status messages
# Feature: anti-uav-detection-system, Property 3: Device Registry Reflects Status Messages
# ---------------------------------------------------------------------------

@given(
    device_id=st.text(min_size=1, max_size=32, alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd"), whitelist_characters="-_")),
    statuses=st.lists(
        st.sampled_from(["online", "offline"]),
        min_size=1,
        max_size=20,
    ),
)
@settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
def test_property3_registry_reflects_last_status(device_id, statuses):
    """
    Property 3: Device Registry Reflects Status Messages
    After a sequence of status messages, the registry reflects the last one.
    """
    registry = DeviceRegistry()

    async def _run():
        for status in statuses:
            await registry.update_status(device_id, _status_payload(device_id, status))
        return await registry.get_device(device_id)

    state = run(_run())
    assert state is not None
    assert state["device_id"] == device_id
    assert state["status"] == statuses[-1]


@given(
    device_ids=st.lists(
        st.text(min_size=1, max_size=16, alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd"), whitelist_characters="-")),
        min_size=1,
        max_size=5,
        unique=True,
    ),
    status=st.sampled_from(["online", "offline"]),
)
@settings(max_examples=30, suppress_health_check=[HealthCheck.too_slow])
def test_property3_multiple_devices_independent(device_ids, status):
    """
    Property 3: Each device's state is tracked independently.
    """
    registry = DeviceRegistry()

    async def _run():
        for did in device_ids:
            await registry.update_status(did, _status_payload(did, status))
        return await registry.get_all_devices()

    devices = run(_run())
    ids_in_registry = {d["device_id"] for d in devices}
    for did in device_ids:
        assert did in ids_in_registry


# ---------------------------------------------------------------------------
# Unit tests
# ---------------------------------------------------------------------------

def test_update_tracking_sets_detection_count():
    registry = DeviceRegistry()
    payload = {
        "device_id": "dev-001",
        "timestamp": "2024-01-01T00:00:00Z",
        "frame_id": 1,
        "detections": [
            {"track_id": 1, "bbox": [0, 0, 10, 10], "confidence": 0.9, "label": "uav"},
            {"track_id": 2, "bbox": [5, 5, 15, 15], "confidence": 0.8, "label": "uav"},
        ],
    }
    run(registry.update_tracking(payload))
    state = run(registry.get_device("dev-001"))
    assert state["detection_count"] == 2


def test_update_status_sets_lat_lon():
    registry = DeviceRegistry()
    payload = {
        "device_id": "dev-002",
        "status": "online",
        "timestamp": "2024-01-01T00:00:00Z",
        "lat": 24.7136,
        "lon": 46.6753,
    }
    run(registry.update_status("dev-002", payload))
    state = run(registry.get_device("dev-002"))
    assert state["lat"] == pytest.approx(24.7136)
    assert state["lon"] == pytest.approx(46.6753)


def test_update_ptz_status():
    registry = DeviceRegistry()
    ptz = {"device_id": "dev-003", "last_command": "zoom_in", "success": True, "timestamp": "2024-01-01T00:00:00Z"}
    run(registry.update_ptz_status(ptz))
    state = run(registry.get_device("dev-003"))
    assert state["last_ptz_status"]["last_command"] == "zoom_in"


def test_update_sensor():
    registry = DeviceRegistry()
    sensor = {"device_id": "dev-004", "compass_bearing_deg": 90.0, "pitch_deg": 5.0, "timestamp": "2024-01-01T00:00:00Z"}
    run(registry.update_sensor(sensor))
    state = run(registry.get_device("dev-004"))
    assert state["last_sensor"]["compass_bearing_deg"] == 90.0


def test_get_unknown_device_returns_none():
    registry = DeviceRegistry()
    state = run(registry.get_device("nonexistent"))
    assert state is None


def test_listener_called_on_status_update():
    registry = DeviceRegistry()
    received = []

    def listener(device_id, state_dict):
        received.append((device_id, state_dict["status"]))

    registry.add_listener(listener)
    run(registry.update_status("dev-005", _status_payload("dev-005", "online")))
    assert received == [("dev-005", "online")]


def test_listener_removed():
    registry = DeviceRegistry()
    received = []

    def listener(device_id, state_dict):
        received.append(device_id)

    registry.add_listener(listener)
    registry.remove_listener(listener)
    run(registry.update_status("dev-006", _status_payload("dev-006", "online")))
    assert received == []
