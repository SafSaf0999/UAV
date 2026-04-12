"""
Edge device — MQTT client.

Provides MQTTClient: connects to the MQTT broker with TLS (cert-based) or
username/password fallback, sets LWT, subscribes to command/ptz topics, and
exposes publish helpers for tracking, status, PTZ status, and sensor payloads.

Reconnection uses exponential backoff: 1s, 2s, 4s, 8s … capped at 60s.
"""

import json
import logging
import threading
import time
from datetime import datetime, timezone
from typing import Callable, Optional

import paho.mqtt.client as mqtt

from edge.config import Config

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Backoff helper
# ---------------------------------------------------------------------------

def _backoff_delay(attempt: int, base: float = 1.0, cap: float = 60.0) -> float:
    """Return exponential backoff delay for the given attempt number (0-indexed).

    delay = min(base * 2**attempt, cap)
    """
    return min(base * (2 ** attempt), cap)


# ---------------------------------------------------------------------------
# MQTTClient
# ---------------------------------------------------------------------------

class MQTTClient:
    """
    MQTT client for an edge device.

    Args:
        config:           Loaded Config object.
        message_callback: Optional callable(topic: str, payload: bytes) invoked
                          for messages received on subscribed topics
                          (uav/command/{device_id} and uav/ptz/{device_id}).
    """

    def __init__(
        self,
        config: Config,
        message_callback: Optional[Callable[[str, bytes], None]] = None,
    ) -> None:
        self._config = config
        self._device_id: str = config.device_id
        self._message_callback = message_callback

        self._client = mqtt.Client(client_id=self._device_id, clean_session=True)
        self._reconnect_attempt: int = 0
        self._running: bool = False
        self._reconnect_thread: Optional[threading.Thread] = None

        self._configure_client()

    # ------------------------------------------------------------------
    # Internal setup
    # ------------------------------------------------------------------

    def _configure_client(self) -> None:
        """Configure TLS / auth and LWT on the paho client."""
        # --- TLS (CA cert for server verification; always applied when present) ---
        ca_cert = self._config.get("mqtt.tls.ca_cert")
        client_cert = self._config.get("mqtt.tls.client_cert")
        client_key = self._config.get("mqtt.tls.client_key")

        # --- Primary auth: username/password ---
        username = self._config.get("mqtt.username")
        password = self._config.get("mqtt.password")

        if username:
            # Set up TLS with CA cert only (server verification); no client cert needed
            if ca_cert:
                self._client.tls_set(ca_certs=ca_cert)
            self._client.username_pw_set(username, password)
            logger.info("MQTT configured with username/password authentication")
        elif client_cert and client_key:
            # Legacy/optional fallback: mutual TLS with client certificate
            if ca_cert:
                self._client.tls_set(
                    ca_certs=ca_cert,
                    certfile=client_cert,
                    keyfile=client_key,
                )
            else:
                self._client.tls_set(
                    certfile=client_cert,
                    keyfile=client_key,
                )
            logger.info("MQTT TLS configured with client certificate (legacy auth)")
        else:
            # No credentials — unauthenticated; still apply CA cert for TLS if available
            if ca_cert:
                self._client.tls_set(ca_certs=ca_cert)
            logger.warning(
                "MQTT: no username configured — connecting unauthenticated (not recommended)"
            )

        # --- LWT ---
        lwt_topic = f"uav/status/{self._device_id}"
        lwt_payload = json.dumps(
            {
                "device_id": self._device_id,
                "status": "offline",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        )
        self._client.will_set(lwt_topic, payload=lwt_payload, qos=1, retain=True)

        # --- Callbacks ---
        self._client.on_connect = self._on_connect
        self._client.on_disconnect = self._on_disconnect
        self._client.on_message = self._on_message

    # ------------------------------------------------------------------
    # paho callbacks
    # ------------------------------------------------------------------

    def _read_cert_info(self) -> dict | None:
        """
        Read the client TLS certificate and extract CN, expiry date, and issuer.
        Returns None if cert path is not configured or file is unreadable.
        """
        cert_path = self._config.get("mqtt.tls.client_cert")
        if not cert_path:
            return None
        try:
            import ssl
            import datetime as _dt
            cert_dict = ssl._ssl._test_decode_cert(cert_path)  # type: ignore[attr-defined]
            subject = dict(x[0] for x in cert_dict.get("subject", ()))
            issuer = dict(x[0] for x in cert_dict.get("issuer", ()))
            not_after = cert_dict.get("notAfter", "")
            # Parse "Jan  1 00:00:00 2035 GMT" format
            try:
                expires_at = _dt.datetime.strptime(not_after, "%b %d %H:%M:%S %Y %Z").isoformat() + "Z"
            except ValueError:
                expires_at = not_after
            return {
                "cn": subject.get("commonName", ""),
                "expires_at": expires_at,
                "issuer": issuer.get("commonName", issuer.get("organizationName", "")),
            }
        except Exception as exc:
            logger.warning("MQTTClient: could not read cert info from %s: %s", cert_path, exc)
            return None

    def _on_connect(self, client: mqtt.Client, userdata, flags, rc: int) -> None:
        if rc != 0:
            logger.error("MQTT connection failed with code %d", rc)
            return

        logger.info("MQTT connected (rc=%d)", rc)
        self._reconnect_attempt = 0  # reset backoff on successful connect

        # Build online status payload, optionally including cert_info
        status_payload: dict = {
            "device_id": self._device_id,
            "status": "online",
            "active_model": self._config.active_model,
            "lat": self._config.get("location.lat"),
            "lon": self._config.get("location.lon"),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        cert_info = self._read_cert_info()
        if cert_info:
            status_payload["cert_info"] = cert_info

        # Publish retained online status
        self.publish_status(status_payload)

        # Subscribe to command and PTZ topics
        command_topic = f"uav/command/{self._device_id}"
        ptz_topic = f"uav/ptz/{self._device_id}"
        client.subscribe(command_topic, qos=1)
        client.subscribe(ptz_topic, qos=0)
        logger.info("Subscribed to %s and %s", command_topic, ptz_topic)

    def _on_disconnect(self, client: mqtt.Client, userdata, rc: int) -> None:
        if rc == 0:
            logger.info("MQTT disconnected cleanly")
            return

        logger.warning("MQTT disconnected unexpectedly (rc=%d), will reconnect", rc)
        if self._running:
            self._schedule_reconnect()

    def _on_message(self, client: mqtt.Client, userdata, msg: mqtt.MQTTMessage) -> None:
        if self._message_callback is not None:
            try:
                self._message_callback(msg.topic, msg.payload)
            except Exception:
                logger.exception("Error in message_callback for topic %s", msg.topic)

    # ------------------------------------------------------------------
    # Reconnect logic
    # ------------------------------------------------------------------

    def _schedule_reconnect(self) -> None:
        """Spawn a background thread that waits and then reconnects."""
        if self._reconnect_thread and self._reconnect_thread.is_alive():
            return  # already reconnecting

        self._reconnect_thread = threading.Thread(
            target=self._reconnect_loop, daemon=True, name="mqtt-reconnect"
        )
        self._reconnect_thread.start()

    def _reconnect_loop(self) -> None:
        while self._running:
            delay = _backoff_delay(self._reconnect_attempt)
            logger.info(
                "MQTT reconnect attempt %d in %.0fs", self._reconnect_attempt + 1, delay
            )
            time.sleep(delay)
            self._reconnect_attempt += 1
            try:
                self._client.reconnect()
                return  # success — paho will call _on_connect
            except Exception as exc:
                logger.warning("MQTT reconnect failed: %s", exc)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Connect to the broker and start the paho network loop."""
        host = self._config.get("mqtt.host", "localhost")
        port = int(self._config.get("mqtt.port", 8883))
        self._running = True
        self._client.connect(host, port, keepalive=60)
        self._client.loop_start()
        logger.info("MQTT client started, connecting to %s:%d", host, port)

    def stop(self) -> None:
        """Publish offline status, disconnect, and stop the network loop."""
        self._running = False
        try:
            self.publish_status(
                {
                    "device_id": self._device_id,
                    "status": "offline",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
            )
        except Exception:
            pass
        self._client.loop_stop()
        self._client.disconnect()
        logger.info("MQTT client stopped")

    # ------------------------------------------------------------------
    # Publish helpers
    # ------------------------------------------------------------------

    def publish_tracking(self, payload_bytes: bytes) -> None:
        """Publish pre-serialized tracking payload bytes (QoS 0)."""
        topic = f"uav/tracking/{self._device_id}"
        self._client.publish(topic, payload=payload_bytes, qos=0, retain=False)

    def publish_status(self, status_dict: dict) -> None:
        """Publish retained status message (QoS 1)."""
        topic = f"uav/status/{self._device_id}"
        payload = json.dumps(status_dict, ensure_ascii=False)
        self._client.publish(topic, payload=payload, qos=1, retain=True)

    def publish_ptz_status(self, ptz_status_dict: dict) -> None:
        """Publish PTZ status (QoS 0, not retained)."""
        topic = f"uav/ptz/status/{self._device_id}"
        payload = json.dumps(ptz_status_dict, ensure_ascii=False)
        self._client.publish(topic, payload=payload, qos=0, retain=False)

    def publish_sensor(self, sensor_dict: dict) -> None:
        """Publish sensor data (QoS 0, not retained)."""
        topic = f"uav/sensor/{self._device_id}"
        payload = json.dumps(sensor_dict, ensure_ascii=False)
        self._client.publish(topic, payload=payload, qos=0, retain=False)

    def publish_health(self, payload_bytes: bytes) -> None:
        """Publish health payload (QoS 0, not retained)."""
        topic = f"uav/health/{self._device_id}"
        self._client.publish(topic, payload=payload_bytes, qos=0, retain=False)

    def publish_log(self, payload_bytes: bytes) -> None:
        """Publish log entry (QoS 0, not retained)."""
        topic = f"uav/log/{self._device_id}"
        self._client.publish(topic, payload=payload_bytes, qos=0, retain=False)

    def publish_raw(self, topic: str, payload_bytes: bytes) -> None:
        """Publish raw bytes to an arbitrary topic (QoS 0, not retained)."""
        self._client.publish(topic, payload=payload_bytes, qos=0, retain=False)
