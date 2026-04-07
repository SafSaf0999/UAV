"""
Tests for aggregation service extensions (registry.py)

Unit tests:
  - update_health stores payload in DeviceState
  - update_log caps at 500 entries
  - class_counts computed correctly from detections

Property test:
  - Property 3: Class Counts Sum Equals Total Detection Count
    Validates: Requirements v2-5.6, v2-5.7
"""

import asyncio
import pytest
from hypothesis import given, settings, HealthCheck
from hypothesis import strategies as st

from main.aggregation.registry import DeviceRegistry, _compute_class_counts


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_tracking_payload(device_id: str, detections: list) -> dict:
    return {
        "device_id": device_id,
        "timestamp": "2026-01-01T00:00:00Z",
        "frame_id": 1,
        "active_model": "daylight-v1",
        "detections": detections,
    }


def _make_detection(label: str, confidence: float = 0.9) -> dict:
    return {
        "track_id": 1,
        "bbox": [10.0, 20.0, 50.0, 60.0],
        "confidence": confidence,
        "label": label,
    }


# ---------------------------------------------------------------------------
# Unit tests — update_health
# ---------------------------------------------------------------------------

class TestUpdateHealth:
    def test_health_stored_in_device_state(self):
        async def _test():
            registry = DeviceRegistry()
            payload = {
                "device_id": "edge-01",
                "uptime_s": 3600,
                "cpu_percent": 45.0,
                "memory_percent": 60.0,
                "inference_fps": 12.0,
                "frames_processed": 1000,
                "mqtt_reconnects": 0,
                "camera_reconnects": 0,
                "timestamp": "2026-01-01T00:00:00Z",
            }
            await registry.update_health(payload)
            state = await registry.get_device("edge-01")
            assert state is not None
            assert state["health"]["cpu_percent"] == 45.0
            assert state["health"]["uptime_s"] == 3600
        asyncio.run(_test())

    def test_health_updated_on_second_call(self):
        async def _test():
            registry = DeviceRegistry()
            await registry.update_health({"device_id": "edge-01", "cpu_percent": 30.0, "timestamp": "t"})
            await registry.update_health({"device_id": "edge-01", "cpu_percent": 75.0, "timestamp": "t2"})
            state = await registry.get_device("edge-01")
            assert state["health"]["cpu_percent"] == 75.0
        asyncio.run(_test())

    def test_health_missing_device_id_ignored(self):
        async def _test():
            registry = DeviceRegistry()
            await registry.update_health({"cpu_percent": 50.0})
            devices = await registry.get_all_devices()
            assert len(devices) == 0
        asyncio.run(_test())


# ---------------------------------------------------------------------------
# Unit tests — update_log
# ---------------------------------------------------------------------------

class TestUpdateLog:
    def test_log_entry_stored(self):
        async def _test():
            registry = DeviceRegistry()
            entry = {
                "device_id": "edge-01",
                "timestamp": "2026-01-01T00:00:00Z",
                "level": "WARNING",
                "logger": "edge.camera",
                "message": "Camera disconnected",
            }
            await registry.update_log(entry)
            logs = await registry.get_logs("edge-01")
            assert len(logs) == 1
            assert logs[0]["message"] == "Camera disconnected"
        asyncio.run(_test())

    def test_log_entries_capped_at_500(self):
        async def _test():
            registry = DeviceRegistry()
            for i in range(600):
                await registry.update_log({
                    "device_id": "edge-01",
                    "timestamp": "t",
                    "level": "WARNING",
                    "logger": "test",
                    "message": f"msg {i}",
                })
            logs = await registry.get_logs("edge-01", limit=1000)
            assert len(logs) <= 500
        asyncio.run(_test())

    def test_log_filter_by_level(self):
        async def _test():
            registry = DeviceRegistry()
            await registry.update_log({"device_id": "edge-01", "level": "WARNING", "message": "w", "timestamp": "t", "logger": "l"})
            await registry.update_log({"device_id": "edge-01", "level": "ERROR", "message": "e", "timestamp": "t", "logger": "l"})
            warnings = await registry.get_logs("edge-01", level="WARNING")
            assert all(e["level"] == "WARNING" for e in warnings)
            assert len(warnings) == 1
        asyncio.run(_test())

    def test_log_no_ws_push(self):
        async def _test():
            registry = DeviceRegistry()
            notified = []
            async def _cb(did, state):
                notified.append(did)
            registry.add_listener(_cb)
            await registry.update_log({"device_id": "edge-01", "level": "WARNING", "message": "x", "timestamp": "t", "logger": "l"})
            assert len(notified) == 0
        asyncio.run(_test())


# ---------------------------------------------------------------------------
# Unit tests — class_counts
# ---------------------------------------------------------------------------

class TestClassCounts:
    def test_class_counts_computed_from_detections(self):
        detections = [
            _make_detection("drone"),
            _make_detection("drone"),
            _make_detection("bird"),
        ]
        counts = _compute_class_counts(detections)
        assert counts["drone"] == 2
        assert counts["bird"] == 1

    def test_class_counts_empty_detections(self):
        assert _compute_class_counts([]) == {}

    def test_class_counts_stored_in_state(self):
        async def _test():
            registry = DeviceRegistry()
            payload = _make_tracking_payload("edge-01", [
                _make_detection("drone"),
                _make_detection("drone"),
                _make_detection("bird"),
            ])
            await registry.update_tracking(payload)
            state = await registry.get_device("edge-01")
            assert state["class_counts"]["drone"] == 2
            assert state["class_counts"]["bird"] == 1
        asyncio.run(_test())

    def test_class_counts_sum_equals_detection_count(self):
        async def _test():
            registry = DeviceRegistry()
            detections = [_make_detection("drone")] * 3 + [_make_detection("bird")] * 2
            payload = _make_tracking_payload("edge-01", detections)
            await registry.update_tracking(payload)
            state = await registry.get_device("edge-01")
            assert sum(state["class_counts"].values()) == state["detection_count"]
        asyncio.run(_test())


# ---------------------------------------------------------------------------
# Property 3: Class Counts Sum Equals Total Detection Count
# ---------------------------------------------------------------------------

label_strategy = st.text(
    min_size=1, max_size=20,
    alphabet=st.characters(whitelist_categories=("Ll", "Lu"), whitelist_characters="_-")
)

detection_strategy = st.fixed_dictionaries({
    "track_id": st.integers(min_value=0, max_value=1000),
    "bbox": st.lists(
        st.floats(min_value=0.0, max_value=1000.0, allow_nan=False),
        min_size=4, max_size=4
    ),
    "confidence": st.floats(min_value=0.0, max_value=1.0, allow_nan=False),
    "label": label_strategy,
})


@given(detections=st.lists(detection_strategy, min_size=0, max_size=20))
@settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
def test_property_3_class_counts_sum_equals_detection_count(detections):
    """
    Property 3: Class Counts Sum Equals Total Detection Count
    For any list of detections, sum(class_counts.values()) == len(detections).
    Validates: Requirements v2-5.6, v2-5.7
    """
    counts = _compute_class_counts(detections)
    assert sum(counts.values()) == len(detections), (
        f"class_counts sum {sum(counts.values())} != detection count {len(detections)}"
    )
