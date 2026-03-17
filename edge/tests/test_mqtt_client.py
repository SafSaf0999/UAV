"""
Unit tests for edge/mqtt_client.py

Tests:
  - Exponential backoff sequence caps at 60s
  - LWT message is configured correctly on connect
  - TLS parameters are passed from config to paho client
"""

# Feature: anti-uav-detection-system, Requirements 2.3, 2.4, 2.5

import json
import unittest
from unittest.mock import MagicMock, call, patch

from edge.config import Config
from edge.mqtt_client import MQTTClient, _backoff_delay


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_config(overrides: dict | None = None) -> Config:
    """Build a minimal Config object for testing."""
    raw = {
        "device_id": "edge-test",
        "active_model": "daylight-v1",
        "mqtt": {
            "host": "broker.example.com",
            "port": 8883,
            "tls": {
                "ca_cert": "/certs/ca.crt",
                "client_cert": "/certs/edge-test.crt",
                "client_key": "/certs/edge-test.key",
            },
        },
        "camera": {"source": "/dev/video0"},
        "location": {"lat": 24.7136, "lon": 46.6753},
        "model_profiles": [{"name": "daylight-v1", "file_path": "/models/m.pt", "camera_mode": "daylight"}],
    }
    if overrides:
        raw.update(overrides)
    return Config(raw=raw)


def _make_config_userpass() -> Config:
    """Config with username/password instead of TLS certs."""
    raw = {
        "device_id": "edge-test",
        "active_model": "daylight-v1",
        "mqtt": {
            "host": "broker.example.com",
            "port": 8883,
            "username": "myuser",
            "password": "mypass",
        },
        "camera": {"source": "/dev/video0"},
        "location": {"lat": 0.0, "lon": 0.0},
        "model_profiles": [{"name": "daylight-v1", "file_path": "/models/m.pt", "camera_mode": "daylight"}],
    }
    return Config(raw=raw)


# ---------------------------------------------------------------------------
# Backoff tests
# ---------------------------------------------------------------------------

class TestBackoffDelay(unittest.TestCase):
    """Test the exponential backoff helper directly (Requirement 2.4)."""

    def test_first_attempt_is_one_second(self):
        self.assertEqual(_backoff_delay(0), 1.0)

    def test_doubles_each_attempt(self):
        self.assertEqual(_backoff_delay(1), 2.0)
        self.assertEqual(_backoff_delay(2), 4.0)
        self.assertEqual(_backoff_delay(3), 8.0)
        self.assertEqual(_backoff_delay(4), 16.0)
        self.assertEqual(_backoff_delay(5), 32.0)

    def test_caps_at_60_seconds(self):
        self.assertEqual(_backoff_delay(6), 60.0)   # 64 → capped
        self.assertEqual(_backoff_delay(7), 60.0)   # 128 → capped
        self.assertEqual(_backoff_delay(10), 60.0)  # 1024 → capped
        self.assertEqual(_backoff_delay(100), 60.0) # huge → capped

    def test_never_exceeds_cap(self):
        for attempt in range(20):
            self.assertLessEqual(_backoff_delay(attempt), 60.0)

    def test_always_positive(self):
        for attempt in range(20):
            self.assertGreater(_backoff_delay(attempt), 0.0)

    def test_sequence_is_non_decreasing(self):
        delays = [_backoff_delay(i) for i in range(15)]
        for a, b in zip(delays, delays[1:]):
            self.assertLessEqual(a, b)


# ---------------------------------------------------------------------------
# LWT tests
# ---------------------------------------------------------------------------

class TestLWT(unittest.TestCase):
    """Test that LWT is configured correctly (Requirement 2.5)."""

    @patch("edge.mqtt_client.mqtt.Client")
    def test_lwt_topic_and_payload(self, MockClient):
        mock_instance = MagicMock()
        MockClient.return_value = mock_instance

        config = _make_config()
        MQTTClient(config)

        mock_instance.will_set.assert_called_once()
        args, kwargs = mock_instance.will_set.call_args

        # Topic
        topic = args[0] if args else kwargs.get("topic")
        self.assertEqual(topic, "uav/status/edge-test")

        # Payload
        payload_raw = kwargs.get("payload") or (args[1] if len(args) > 1 else None)
        payload = json.loads(payload_raw)
        self.assertEqual(payload["status"], "offline")
        self.assertEqual(payload["device_id"], "edge-test")

    @patch("edge.mqtt_client.mqtt.Client")
    def test_lwt_qos_1_and_retained(self, MockClient):
        mock_instance = MagicMock()
        MockClient.return_value = mock_instance

        config = _make_config()
        MQTTClient(config)

        _, kwargs = mock_instance.will_set.call_args
        self.assertEqual(kwargs.get("qos"), 1)
        self.assertTrue(kwargs.get("retain"))

    @patch("edge.mqtt_client.mqtt.Client")
    def test_lwt_set_before_connect(self, MockClient):
        """LWT must be configured during __init__, before start() is called."""
        mock_instance = MagicMock()
        MockClient.return_value = mock_instance

        config = _make_config()
        client = MQTTClient(config)

        # will_set called during construction, not after start()
        mock_instance.will_set.assert_called_once()
        mock_instance.connect.assert_not_called()


# ---------------------------------------------------------------------------
# TLS configuration tests
# ---------------------------------------------------------------------------

class TestTLSConfiguration(unittest.TestCase):
    """Test that TLS parameters from config are passed to paho (Requirement 2.3, 11.1, 11.3)."""

    @patch("edge.mqtt_client.mqtt.Client")
    def test_tls_set_called_with_cert_paths(self, MockClient):
        mock_instance = MagicMock()
        MockClient.return_value = mock_instance

        config = _make_config()
        MQTTClient(config)

        mock_instance.tls_set.assert_called_once_with(
            ca_certs="/certs/ca.crt",
            certfile="/certs/edge-test.crt",
            keyfile="/certs/edge-test.key",
        )

    @patch("edge.mqtt_client.mqtt.Client")
    def test_username_password_fallback_when_no_tls_certs(self, MockClient):
        mock_instance = MagicMock()
        MockClient.return_value = mock_instance

        config = _make_config_userpass()
        MQTTClient(config)

        mock_instance.tls_set.assert_not_called()
        mock_instance.username_pw_set.assert_called_once_with("myuser", "mypass")

    @patch("edge.mqtt_client.mqtt.Client")
    def test_tls_not_called_when_certs_missing(self, MockClient):
        """If only some TLS fields are present, fall back to user/pass."""
        mock_instance = MagicMock()
        MockClient.return_value = mock_instance

        raw = {
            "device_id": "edge-test",
            "active_model": "daylight-v1",
            "mqtt": {
                "host": "broker.example.com",
                "port": 8883,
                "tls": {"ca_cert": "/certs/ca.crt"},  # missing client_cert and client_key
            },
            "camera": {"source": "/dev/video0"},
            "location": {"lat": 0.0, "lon": 0.0},
            "model_profiles": [{"name": "daylight-v1", "file_path": "/m.pt", "camera_mode": "daylight"}],
        }
        config = Config(raw=raw)
        MQTTClient(config)

        mock_instance.tls_set.assert_not_called()


# ---------------------------------------------------------------------------
# On-connect behaviour tests
# ---------------------------------------------------------------------------

class TestOnConnect(unittest.TestCase):
    """Test that on_connect publishes online status and subscribes correctly."""

    @patch("edge.mqtt_client.mqtt.Client")
    def test_on_connect_publishes_online_status(self, MockClient):
        mock_instance = MagicMock()
        MockClient.return_value = mock_instance

        config = _make_config()
        client = MQTTClient(config)

        # Simulate paho calling on_connect
        client._on_connect(mock_instance, None, {}, 0)

        # Find the publish call for the status topic
        status_calls = [
            c for c in mock_instance.publish.call_args_list
            if c.args and c.args[0] == "uav/status/edge-test"
        ]
        self.assertTrue(len(status_calls) >= 1, "Expected at least one publish to uav/status/edge-test")

        payload = json.loads(status_calls[0].args[1] if len(status_calls[0].args) > 1
                             else status_calls[0].kwargs.get("payload"))
        self.assertEqual(payload["status"], "online")
        self.assertEqual(payload["device_id"], "edge-test")

    @patch("edge.mqtt_client.mqtt.Client")
    def test_on_connect_subscribes_to_command_and_ptz(self, MockClient):
        mock_instance = MagicMock()
        MockClient.return_value = mock_instance

        config = _make_config()
        client = MQTTClient(config)
        client._on_connect(mock_instance, None, {}, 0)

        subscribed_topics = [c.args[0] for c in mock_instance.subscribe.call_args_list]
        self.assertIn("uav/command/edge-test", subscribed_topics)
        self.assertIn("uav/ptz/edge-test", subscribed_topics)

    @patch("edge.mqtt_client.mqtt.Client")
    def test_on_connect_resets_reconnect_attempt(self, MockClient):
        mock_instance = MagicMock()
        MockClient.return_value = mock_instance

        config = _make_config()
        client = MQTTClient(config)
        client._reconnect_attempt = 5  # simulate previous failures

        client._on_connect(mock_instance, None, {}, 0)

        self.assertEqual(client._reconnect_attempt, 0)

    @patch("edge.mqtt_client.mqtt.Client")
    def test_on_connect_failed_rc_does_not_publish(self, MockClient):
        mock_instance = MagicMock()
        MockClient.return_value = mock_instance

        config = _make_config()
        client = MQTTClient(config)
        client._on_connect(mock_instance, None, {}, rc=5)  # rc != 0

        mock_instance.publish.assert_not_called()


# ---------------------------------------------------------------------------
# Publish helpers tests
# ---------------------------------------------------------------------------

class TestPublishHelpers(unittest.TestCase):
    """Verify publish helpers use correct topics, QoS, and retain flags."""

    @patch("edge.mqtt_client.mqtt.Client")
    def _make_client(self, MockClient):
        mock_instance = MagicMock()
        MockClient.return_value = mock_instance
        config = _make_config()
        client = MQTTClient(config)
        return client, mock_instance

    def test_publish_tracking_uses_qos0_no_retain(self):
        client, mock_instance = self._make_client()
        client.publish_tracking(b'{"frame_id": 1}')
        mock_instance.publish.assert_called_once_with(
            "uav/tracking/edge-test",
            payload=b'{"frame_id": 1}',
            qos=0,
            retain=False,
        )

    def test_publish_status_uses_qos1_retained(self):
        client, mock_instance = self._make_client()
        client.publish_status({"status": "online", "device_id": "edge-test"})
        call_kwargs = mock_instance.publish.call_args
        self.assertEqual(call_kwargs.args[0], "uav/status/edge-test")
        self.assertEqual(call_kwargs.kwargs.get("qos"), 1)
        self.assertTrue(call_kwargs.kwargs.get("retain"))

    def test_publish_ptz_status_uses_qos0(self):
        client, mock_instance = self._make_client()
        client.publish_ptz_status({"zoom_level": 3})
        call_kwargs = mock_instance.publish.call_args
        self.assertEqual(call_kwargs.args[0], "uav/ptz/status/edge-test")
        self.assertEqual(call_kwargs.kwargs.get("qos"), 0)

    def test_publish_sensor_uses_qos0(self):
        client, mock_instance = self._make_client()
        client.publish_sensor({"compass_bearing_deg": 90.0})
        call_kwargs = mock_instance.publish.call_args
        self.assertEqual(call_kwargs.args[0], "uav/sensor/edge-test")
        self.assertEqual(call_kwargs.kwargs.get("qos"), 0)
