"""
Tests for edge/ptz_controller.py

Property 4: PTZ Command Published to Correct Topic with Valid Structure
  Validates: Requirements 13.2, 13.3

Unit tests:
  - All 10 command types dispatched without error (digital driver)
  - PTZ disabled silently ignores commands
  - Serial port unavailable disables PTZ and continues
"""

import json
import pytest
from unittest.mock import MagicMock, patch
from hypothesis import given, settings, HealthCheck
from hypothesis import strategies as st

from edge.ptz_controller import PTZController, DigitalZoomDriver, VALID_COMMANDS


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_config(enabled=True, hw_type="digital", device_id="dev-001"):
    cfg = MagicMock()
    cfg.device_id = device_id
    cfg.get = lambda key, default=None: {
        "ptz.enabled": enabled,
        "ptz.hardware_type": hw_type,
        "ptz.serial_port": "/dev/ttyUSB0",
        "ptz.baudrate": 9600,
    }.get(key, default)
    return cfg


def _make_mqtt():
    return MagicMock()


def _ptz_payload(command: str, params: dict = None) -> bytes:
    return json.dumps({"command": command, "params": params or {}}).encode()


# ---------------------------------------------------------------------------
# Property 4: PTZ command topic and structure
# Feature: anti-uav-detection-system, Property 4: PTZ Command Published to Correct Topic with Valid Structure
# ---------------------------------------------------------------------------

@given(
    device_id=st.text(min_size=1, max_size=32, alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd"), whitelist_characters="-_")),
    command=st.sampled_from(sorted(VALID_COMMANDS)),
)
@settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
def test_property4_ptz_command_topic_and_structure(device_id, command):
    """
    Property 4: PTZ Command Published to Correct Topic with Valid Structure
    For any valid device_id and command, the published PTZ status must contain
    the correct device_id, a valid command name, and a boolean success field.
    """
    cfg = _make_config(enabled=True, hw_type="digital", device_id=device_id)
    mqtt = _make_mqtt()
    ctrl = PTZController(cfg, mqtt)

    payload = _ptz_payload(command)
    topic = f"uav/ptz/{device_id}"
    ctrl.handle(topic, payload)

    assert mqtt.publish_ptz_status.called
    published = mqtt.publish_ptz_status.call_args[0][0]
    assert published["device_id"] == device_id
    assert published["last_command"] == command
    assert isinstance(published["success"], bool)
    assert "timestamp" in published


# ---------------------------------------------------------------------------
# Unit tests — all 10 command types (digital driver)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("command", sorted(VALID_COMMANDS))
def test_all_commands_dispatched_digital(command):
    """All 10 PTZ commands execute without error on the digital driver."""
    cfg = _make_config(enabled=True, hw_type="digital")
    mqtt = _make_mqtt()
    ctrl = PTZController(cfg, mqtt)

    payload = _ptz_payload(command, {"step": 0.1, "pan": 0.5, "tilt": 0.3, "zoom": 2.0})
    ctrl.handle(f"uav/ptz/dev-001", payload)

    assert mqtt.publish_ptz_status.called
    status = mqtt.publish_ptz_status.call_args[0][0]
    assert status["success"] is True


def test_ptz_disabled_silently_ignores():
    """PTZ disabled: handle() returns without calling publish_ptz_status."""
    cfg = _make_config(enabled=False)
    mqtt = _make_mqtt()
    ctrl = PTZController(cfg, mqtt)

    ctrl.handle("uav/ptz/dev-001", _ptz_payload("zoom_in"))
    mqtt.publish_ptz_status.assert_not_called()


def test_ptz_disabled_no_log(caplog):
    """PTZ disabled: no warning or error logged for ignored commands."""
    import logging
    cfg = _make_config(enabled=False)
    mqtt = _make_mqtt()
    ctrl = PTZController(cfg, mqtt)

    with caplog.at_level(logging.WARNING, logger="edge.ptz_controller"):
        ctrl.handle("uav/ptz/dev-001", _ptz_payload("pan_left"))

    assert caplog.records == []


def test_serial_port_unavailable_disables_ptz():
    """Serial port unavailable: PTZ is disabled for the session."""
    cfg = _make_config(enabled=True, hw_type="visca_serial")
    mqtt = _make_mqtt()

    with patch("edge.ptz_controller.ViscaSerialDriver") as MockSerial:
        instance = MockSerial.return_value
        instance._serial = None  # simulate unavailable port
        ctrl = PTZController(cfg, mqtt)

    assert ctrl._enabled is False
    ctrl.handle("uav/ptz/dev-001", _ptz_payload("pan_left"))
    mqtt.publish_ptz_status.assert_not_called()


def test_unknown_command_ignored():
    """Unknown command is logged as warning and not dispatched."""
    cfg = _make_config(enabled=True, hw_type="digital")
    mqtt = _make_mqtt()
    ctrl = PTZController(cfg, mqtt)

    payload = json.dumps({"command": "fly_away", "params": {}}).encode()
    ctrl.handle("uav/ptz/dev-001", payload)
    mqtt.publish_ptz_status.assert_not_called()


def test_digital_driver_zoom_clamps():
    """DigitalZoomDriver zoom_level is clamped between 1.0 and 8.0."""
    driver = DigitalZoomDriver()
    for _ in range(100):
        driver.execute("zoom_in", {"step": 1.0})
    assert driver.zoom_level == 8.0

    for _ in range(100):
        driver.execute("zoom_out", {"step": 1.0})
    assert driver.zoom_level == 1.0


def test_digital_driver_home_resets():
    """DigitalZoomDriver home command resets all offsets."""
    driver = DigitalZoomDriver()
    driver.execute("pan_right", {"step": 0.5})
    driver.execute("tilt_up", {"step": 0.5})
    driver.execute("zoom_in", {"step": 2.0})
    driver.execute("home", {})
    assert driver.zoom_level == 1.0
    assert driver.pan_offset == 0.0
    assert driver.tilt_offset == 0.0


def test_malformed_payload_ignored():
    """Malformed JSON payload is handled gracefully."""
    cfg = _make_config(enabled=True, hw_type="digital")
    mqtt = _make_mqtt()
    ctrl = PTZController(cfg, mqtt)

    ctrl.handle("uav/ptz/dev-001", b"not json {{{")
    mqtt.publish_ptz_status.assert_not_called()
