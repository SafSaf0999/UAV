"""
Aggregation service — MQTT subscriber.

Subscribes to all UAV topics, validates tracking payloads, and updates
the DeviceRegistry. Reconnects with exponential backoff on broker disconnect.

Topics:
  uav/tracking/#    → validate + update_tracking
  uav/status/#      → update_status
  uav/ptz/status/#  → update_ptz_status
  uav/sensor/#      → update_sensor
  uav/radar/#       → radar_normalizer (if RADAR_ENABLED)

Requirements: 4.1, 4.2, 4.3, 4.4, 14.1
"""

import asyncio
import json
import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

TOPICS = [
    "uav/tracking/#",
    "uav/status/#",
    "uav/ptz/status/#",
    "uav/sensor/#",
]

RADAR_TOPIC = "uav/radar/#"


class MQTTSubscriber:
    """
    Async MQTT subscriber using aiomqtt (asyncio-mqtt).

    Args:
        registry:          DeviceRegistry instance.
        validator:         validate_payload callable.
        radar_normalizer:  Optional normalize_radar_track callable.
        host:              MQTT broker host.
        port:              MQTT broker port.
        tls_params:        Optional dict with ca_cert, client_cert, client_key paths.
        username:          Optional MQTT username.
        password:          Optional MQTT password.
        radar_enabled:     Whether to subscribe to radar topic.
    """

    def __init__(
        self,
        registry,
        validator,
        radar_normalizer=None,
        host: str = "localhost",
        port: int = 8883,
        tls_params: Optional[dict] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        radar_enabled: bool = False,
    ) -> None:
        self._registry = registry
        self._validator = validator
        self._radar_normalizer = radar_normalizer
        self._host = host
        self._port = port
        self._tls_params = tls_params
        self._username = username
        self._password = password
        self._radar_enabled = radar_enabled
        self._running = False

    async def run(self) -> None:
        """Run the subscriber loop with reconnect backoff."""
        self._running = True
        attempt = 0
        while self._running:
            try:
                await self._connect_and_subscribe()
                attempt = 0  # reset on clean disconnect
            except Exception as exc:
                if not self._running:
                    break
                delay = min(1.0 * (2 ** attempt), 60.0)
                logger.warning(
                    "MQTTSubscriber: disconnected (%s), reconnecting in %.0fs", exc, delay
                )
                await asyncio.sleep(delay)
                attempt += 1

    async def _connect_and_subscribe(self) -> None:
        try:
            import aiomqtt  # type: ignore
        except ImportError:
            logger.error("MQTTSubscriber: aiomqtt not installed")
            self._running = False
            return

        tls_context = None
        if self._tls_params:
            import ssl
            tls_context = ssl.create_default_context(ssl.Purpose.SERVER_AUTH)
            tls_context.load_verify_locations(self._tls_params["ca_cert"])
            if self._tls_params.get("client_cert") and self._tls_params.get("client_key"):
                tls_context.load_cert_chain(
                    self._tls_params["client_cert"],
                    self._tls_params["client_key"],
                )

        topics = list(TOPICS)
        if self._radar_enabled:
            topics.append(RADAR_TOPIC)

        async with aiomqtt.Client(
            hostname=self._host,
            port=self._port,
            tls_context=tls_context,
            username=self._username,
            password=self._password,
        ) as client:
            logger.info("MQTTSubscriber: connected to %s:%d", self._host, self._port)
            for topic in topics:
                await client.subscribe(topic)
                logger.info("MQTTSubscriber: subscribed to %s", topic)

            async for message in client.messages:
                if not self._running:
                    break
                await self._dispatch(str(message.topic), message.payload)

    async def _dispatch(self, topic: str, payload_bytes: bytes) -> None:
        try:
            data = json.loads(payload_bytes.decode("utf-8"))
        except Exception as exc:
            logger.warning("MQTTSubscriber: failed to parse message on %s: %s", topic, exc)
            return

        if topic.startswith("uav/tracking/"):
            if self._validator(data):
                await self._registry.update_tracking(data)
            else:
                logger.warning("MQTTSubscriber: invalid tracking payload from %s", topic)

        elif topic.startswith("uav/status/"):
            device_id = topic.split("/")[-1]
            await self._registry.update_status(device_id, data)

        elif topic.startswith("uav/ptz/status/"):
            await self._registry.update_ptz_status(data)

        elif topic.startswith("uav/sensor/"):
            await self._registry.update_sensor(data)

        elif topic.startswith("uav/radar/") and self._radar_normalizer:
            normalized = self._radar_normalizer(data)
            if normalized and self._validator(normalized):
                await self._registry.update_tracking(normalized)

    def stop(self) -> None:
        self._running = False


def create_subscriber_from_env(registry, validator, radar_normalizer=None) -> "MQTTSubscriber":
    """Factory that reads broker config from environment variables."""
    ca = os.environ.get("MQTT_TLS_CA", "")
    cert = os.environ.get("MQTT_TLS_CERT", "")
    key = os.environ.get("MQTT_TLS_KEY", "")
    tls_params = {
        "ca_cert": ca,
        "client_cert": cert,
        "client_key": key,
    } if ca else None
    return MQTTSubscriber(
        registry=registry,
        validator=validator,
        radar_normalizer=radar_normalizer,
        host=os.environ.get("MQTT_HOST", "mosquitto"),
        port=int(os.environ.get("MQTT_PORT", "8883")),
        tls_params=tls_params,
        username=os.environ.get("MQTT_USERNAME"),
        password=os.environ.get("MQTT_PASSWORD"),
        radar_enabled=os.environ.get("RADAR_ENABLED", "false").lower() == "true",
    )
