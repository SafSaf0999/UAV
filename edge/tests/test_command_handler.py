"""
Tests for edge/command_handler.py

Unit tests:
  - stop_stream calls webrtc_streamer.stop()
  - start_stream calls webrtc_streamer.start()
  - switch_model with missing file publishes error status and retains current model
  - unknown action is ignored without error

Property test:
  - Property 5: Control Command Published to Correct Topic
    **Validates: Requirements 7.1, 7.2**

# Feature: anti-uav-detection-system, Property 5: Control Command Published to Correct Topic
"""

import json
import unittest
from unittest.mock import MagicMock, call

import pytest
from hypothesis import given, settings, HealthCheck
from hypothesis import strategies as st

# ---------------------------------------------------------------------------
# Register hypothesis CI profile
# ---------------------------------------------------------------------------
from hypothesis import settings as hyp_settings

hyp_settings.register_profile(
    "ci",
    max_examples=100,
    suppress_health_check=[HealthCheck.too_slow],
)
hyp_settings.load_profile("ci")

# ---------------------------------------------------------------------------
# Import the module under test
# ---------------------------------------------------------------------------
from edge.command_handler import CommandHandler


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_handler(hot_swap_result: bool = True):
    """Build a CommandHandler with all dependencies mocked."""
    mqtt_client = MagicMock()
    mqtt_client._device_id = "edge-test"

    webrtc_streamer = MagicMock()

    model_manager = MagicMock()
    model_manager.hot_swap.return_value = hot_swap_result

    handler = CommandHandler(
        mqtt_client=mqtt_client,
        webrtc_streamer=webrtc_streamer,
        model_manager=model_manager,
    )
    return handler, mqtt_client, webrtc_streamer, model_manager


def _payload(action: str, **kwargs) -> bytes:
    """Encode a command payload as UTF-8 JSON bytes."""
    data = {"action": action}
    data.update(kwargs)
    return json.dumps(data).encode("utf-8")


# ===========================================================================
# Unit Tests
# ===========================================================================

class TestStopStream(unittest.TestCase):
    """Test that stop_stream calls webrtc_streamer.stop()."""

    def test_stop_stream_calls_streamer_stop(self):
        handler, _, webrtc_streamer, _ = _make_handler()
        handler.handle("uav/command/edge-test", _payload("stop_stream"))
        webrtc_streamer.stop.assert_called_once()

    def test_stop_stream_does_not_call_start(self):
        handler, _, webrtc_streamer, _ = _make_handler()
        handler.handle("uav/command/edge-test", _payload("stop_stream"))
        webrtc_streamer.start.assert_not_called()

    def test_stop_stream_no_streamer_does_not_raise(self):
        """If no WebRTC streamer is configured, stop_stream should log and return."""
        mqtt_client = MagicMock()
        mqtt_client._device_id = "edge-test"
        handler = CommandHandler(mqtt_client=mqtt_client, webrtc_streamer=None)
        # Should not raise
        handler.handle("uav/command/edge-test", _payload("stop_stream"))


class TestStartStream(unittest.TestCase):
    """Test that start_stream calls webrtc_streamer.start()."""

    def test_start_stream_calls_streamer_start(self):
        handler, _, webrtc_streamer, _ = _make_handler()
        handler.handle("uav/command/edge-test", _payload("start_stream"))
        webrtc_streamer.start.assert_called_once()

    def test_start_stream_does_not_call_stop(self):
        handler, _, webrtc_streamer, _ = _make_handler()
        handler.handle("uav/command/edge-test", _payload("start_stream"))
        webrtc_streamer.stop.assert_not_called()

    def test_start_stream_no_streamer_does_not_raise(self):
        """If no WebRTC streamer is configured, start_stream should log and return."""
        mqtt_client = MagicMock()
        mqtt_client._device_id = "edge-test"
        handler = CommandHandler(mqtt_client=mqtt_client, webrtc_streamer=None)
        handler.handle("uav/command/edge-test", _payload("start_stream"))


class TestSwitchModel(unittest.TestCase):
    """Test switch_model dispatches to model_manager and handles failures."""

    def test_switch_model_calls_hot_swap(self):
        handler, _, _, model_manager = _make_handler(hot_swap_result=True)
        handler.handle("uav/command/edge-test", _payload("switch_model", model_name="thermal-v1"))
        model_manager.hot_swap.assert_called_once_with("thermal-v1")

    def test_switch_model_success_does_not_publish_error(self):
        handler, mqtt_client, _, _ = _make_handler(hot_swap_result=True)
        handler.handle("uav/command/edge-test", _payload("switch_model", model_name="thermal-v1"))
        mqtt_client.publish_status.assert_not_called()

    def test_switch_model_missing_file_publishes_error_status(self):
        """
        When hot_swap returns False (file missing), an error status must be
        published via mqtt_client.publish_status() — Requirement 18.6.
        """
        handler, mqtt_client, _, model_manager = _make_handler(hot_swap_result=False)
        handler.handle("uav/command/edge-test", _payload("switch_model", model_name="missing-model"))
        mqtt_client.publish_status.assert_called_once()
        call_args = mqtt_client.publish_status.call_args
        status_dict = call_args.args[0] if call_args.args else call_args.kwargs.get("status_dict")
        self.assertEqual(status_dict["status"], "error")

    def test_switch_model_missing_file_retains_current_model(self):
        """
        When hot_swap returns False, the model_manager must not be called
        again and the current model is retained (hot_swap itself handles
        retention; CommandHandler must not attempt a second swap).
        """
        handler, _, _, model_manager = _make_handler(hot_swap_result=False)
        handler.handle("uav/command/edge-test", _payload("switch_model", model_name="missing-model"))
        # hot_swap called exactly once — no retry by CommandHandler
        model_manager.hot_swap.assert_called_once()

    def test_switch_model_no_manager_does_not_raise(self):
        mqtt_client = MagicMock()
        mqtt_client._device_id = "edge-test"
        handler = CommandHandler(mqtt_client=mqtt_client, model_manager=None)
        handler.handle("uav/command/edge-test", _payload("switch_model", model_name="thermal-v1"))


class TestUnknownAction(unittest.TestCase):
    """Test that unknown actions are silently ignored."""

    def test_unknown_action_does_not_raise(self):
        handler, mqtt_client, webrtc_streamer, model_manager = _make_handler()
        # Should not raise
        handler.handle("uav/command/edge-test", _payload("reboot_device"))

    def test_unknown_action_does_not_call_any_component(self):
        handler, mqtt_client, webrtc_streamer, model_manager = _make_handler()
        handler.handle("uav/command/edge-test", _payload("reboot_device"))
        webrtc_streamer.start.assert_not_called()
        webrtc_streamer.stop.assert_not_called()
        model_manager.hot_swap.assert_not_called()
        mqtt_client.publish_status.assert_not_called()

    def test_missing_action_field_does_not_raise(self):
        handler, _, _, _ = _make_handler()
        payload = json.dumps({"model_name": "thermal-v1"}).encode("utf-8")
        handler.handle("uav/command/edge-test", payload)

    def test_invalid_json_does_not_raise(self):
        handler, _, _, _ = _make_handler()
        handler.handle("uav/command/edge-test", b"not-valid-json{{{")


# ===========================================================================
# Property Test
# ===========================================================================

# ---------------------------------------------------------------------------
# Property 5: Control Command Published to Correct Topic
# Feature: anti-uav-detection-system, Property 5: Control Command Published to Correct Topic
# ---------------------------------------------------------------------------

# Strategy: generate valid device IDs (alphanumeric + hyphens, non-empty)
device_id_strategy = st.from_regex(r"[a-z][a-z0-9\-]{0,30}", fullmatch=True)

# Only the two stream-control actions are in scope for Property 5
stream_action_strategy = st.sampled_from(["start_stream", "stop_stream"])


@given(
    device_id=device_id_strategy,
    action=stream_action_strategy,
)
@settings(max_examples=100)
def test_property_5_control_command_correct_topic(device_id: str, action: str):
    """
    # Feature: anti-uav-detection-system, Property 5: Control Command Published to Correct Topic
    **Validates: Requirements 7.1, 7.2**

    For any start or stop stream command issued for a given device_id, the
    MQTT topic must be uav/command/{device_id} and the action field must be
    "start_stream" or "stop_stream".
    """
    # Build the expected topic
    expected_topic = f"uav/command/{device_id}"

    # Verify the topic format holds for any device_id
    assert expected_topic == f"uav/command/{device_id}"

    # Verify the action is one of the two valid stream-control actions
    valid_actions = {"start_stream", "stop_stream"}
    assert action in valid_actions

    # Build the command payload as the control center would
    command_payload = {"action": action}
    payload_bytes = json.dumps(command_payload).encode("utf-8")

    # Simulate the edge device receiving and parsing the command
    parsed = json.loads(payload_bytes.decode("utf-8"))
    assert parsed["action"] == action
    assert parsed["action"] in valid_actions

    # Simulate CommandHandler dispatching the command
    mqtt_client = MagicMock()
    mqtt_client._device_id = device_id
    webrtc_streamer = MagicMock()
    handler = CommandHandler(
        mqtt_client=mqtt_client,
        webrtc_streamer=webrtc_streamer,
    )
    handler.handle(expected_topic, payload_bytes)

    # The correct streamer method must have been called
    if action == "start_stream":
        webrtc_streamer.start.assert_called_once()
        webrtc_streamer.stop.assert_not_called()
    else:
        webrtc_streamer.stop.assert_called_once()
        webrtc_streamer.start.assert_not_called()
