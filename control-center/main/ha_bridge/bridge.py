"""
Backend data bridge — silently forwards UAV MQTT state to external
automation systems via MQTT Discovery protocol.

Runs as a standalone Docker service with no user-facing presence.
Connects to Mosquitto on the internal Docker network (port 1883, no TLS).

Discovery topics: homeassistant/{type}/{device_id}/{entity}/config
State topics:     homeassistant/{type}/{device_id}/{entity}/state

Requirements: v2-11.1 through v2-11.9
"""

import json
import logging
import os
import time
from typing import Optional

import paho.mqtt.client as mqtt

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
logger = logging.getLogger(__name__)

MQTT_HOST = os.environ.get("MQTT_HOST", "mosquitto")
MQTT_PORT = int(os.environ.get("MQTT_PORT", "1883"))

# Tracks which device_ids have had discovery configs published
_discovered: set[str] = set()


# ---------------------------------------------------------------------------
# Discovery config builders
# ---------------------------------------------------------------------------

def _device_block(device_id: str) -> dict:
    return {
        "identifiers": [f"uav_{device_id.replace('-', '_')}"],
        "name": f"UAV Edge Device {device_id}",
        "model": "Anti-UAV Edge",
        "manufacturer": "UAV System",
    }


def _sensor_config(device_id: str, entity: str, name: str, **kwargs) -> dict:
    safe_id = device_id.replace("-", "_")
    return {
        "unique_id": f"uav_{safe_id}_{entity}",
        "name": f"{device_id} {name}",
        "state_topic": f"homeassistant/sensor/{device_id}/{entity}/state",
        "device": _device_block(device_id),
        **kwargs,
    }


def _binary_sensor_config(device_id: str, entity: str, name: str, **kwargs) -> dict:
    safe_id = device_id.replace("-", "_")
    return {
        "unique_id": f"uav_{safe_id}_{entity}",
        "name": f"{device_id} {name}",
        "state_topic": f"homeassistant/binary_sensor/{device_id}/{entity}/state",
        "payload_on": "ON",
        "payload_off": "OFF",
        "device": _device_block(device_id),
        **kwargs,
    }


def publish_discovery(client: mqtt.Client, device_id: str, class_labels: list[str] = None) -> None:
    """Publish MQTT Discovery config for all entities of a device."""
    if class_labels is None:
        class_labels = []

    configs = [
        # Binary sensor
        (
            f"homeassistant/binary_sensor/{device_id}/uav_detected/config",
            _binary_sensor_config(device_id, "uav_detected", "UAV Detected",
                                  icon="mdi:radar"),
        ),
        # Sensors
        (
            f"homeassistant/sensor/{device_id}/detection_count/config",
            _sensor_config(device_id, "detection_count", "Detection Count",
                           unit_of_measurement="detections", icon="mdi:counter"),
        ),
        (
            f"homeassistant/sensor/{device_id}/active_model/config",
            _sensor_config(device_id, "active_model", "Active Model", icon="mdi:brain"),
        ),
        (
            f"homeassistant/sensor/{device_id}/device_status/config",
            _sensor_config(device_id, "device_status", "Status", icon="mdi:circle"),
        ),
        (
            f"homeassistant/sensor/{device_id}/cpu_percent/config",
            _sensor_config(device_id, "cpu_percent", "CPU",
                           unit_of_measurement="%", device_class="power_factor"),
        ),
        (
            f"homeassistant/sensor/{device_id}/inference_fps/config",
            _sensor_config(device_id, "inference_fps", "Inference FPS",
                           unit_of_measurement="fps", icon="mdi:speedometer"),
        ),
        (
            f"homeassistant/sensor/{device_id}/last_detection/config",
            _sensor_config(device_id, "last_detection", "Last Detection",
                           device_class="timestamp", icon="mdi:clock-outline"),
        ),
        (
            f"homeassistant/sensor/{device_id}/compass_bearing/config",
            _sensor_config(device_id, "compass_bearing", "Compass Bearing",
                           unit_of_measurement="°", icon="mdi:compass"),
        ),
    ]

    # Per-class count sensors
    for label in class_labels:
        safe_label = label.replace(" ", "_").replace("-", "_")
        configs.append((
            f"homeassistant/sensor/{device_id}/class_{safe_label}/config",
            _sensor_config(device_id, f"class_{safe_label}", f"{label.title()} Count",
                           unit_of_measurement="detections", icon="mdi:counter"),
        ))

    for topic, config in configs:
        client.publish(topic, json.dumps(config), qos=1, retain=True)

    logger.info("Bridge: published discovery for device '%s'", device_id)


# ---------------------------------------------------------------------------
# State update publishers
# ---------------------------------------------------------------------------

def publish_tracking_state(client: mqtt.Client, device_id: str, payload: dict) -> None:
    detections = payload.get("detections", [])
    detection_count = len(detections)
    uav_detected = "ON" if detection_count > 0 else "OFF"

    client.publish(
        f"homeassistant/binary_sensor/{device_id}/uav_detected/state",
        uav_detected, qos=0,
    )
    client.publish(
        f"homeassistant/sensor/{device_id}/detection_count/state",
        str(detection_count), qos=0,
    )
    if payload.get("active_model"):
        client.publish(
            f"homeassistant/sensor/{device_id}/active_model/state",
            payload["active_model"], qos=0,
        )
    if payload.get("timestamp"):
        client.publish(
            f"homeassistant/sensor/{device_id}/last_detection/state",
            payload["timestamp"], qos=0,
        )

    # Per-class counts
    from collections import Counter
    class_counts = Counter(d.get("label", "unknown") for d in detections)
    for label, count in class_counts.items():
        safe_label = label.replace(" ", "_").replace("-", "_")
        client.publish(
            f"homeassistant/sensor/{device_id}/class_{safe_label}/state",
            str(count), qos=0,
        )


def publish_status_state(client: mqtt.Client, device_id: str, payload: dict) -> None:
    status = payload.get("status", "unknown")
    client.publish(
        f"homeassistant/sensor/{device_id}/device_status/state",
        status, qos=0,
    )
    if payload.get("active_model"):
        client.publish(
            f"homeassistant/sensor/{device_id}/active_model/state",
            payload["active_model"], qos=0,
        )


def publish_health_state(client: mqtt.Client, device_id: str, payload: dict) -> None:
    if "cpu_percent" in payload:
        client.publish(
            f"homeassistant/sensor/{device_id}/cpu_percent/state",
            str(payload["cpu_percent"]), qos=0,
        )
    if "inference_fps" in payload:
        client.publish(
            f"homeassistant/sensor/{device_id}/inference_fps/state",
            str(payload["inference_fps"]), qos=0,
        )


def publish_sensor_state(client: mqtt.Client, device_id: str, payload: dict) -> None:
    if "compass_bearing_deg" in payload:
        client.publish(
            f"homeassistant/sensor/{device_id}/compass_bearing/state",
            str(payload["compass_bearing_deg"]), qos=0,
        )


# ---------------------------------------------------------------------------
# MQTT callbacks
# ---------------------------------------------------------------------------

def _on_connect(client: mqtt.Client, userdata, flags, rc: int) -> None:
    if rc != 0:
        logger.error("Bridge: MQTT connection failed (rc=%d)", rc)
        return
    logger.info("Bridge: connected to %s:%d", MQTT_HOST, MQTT_PORT)
    # Re-publish discovery for all known devices on reconnect
    for device_id in list(_discovered):
        publish_discovery(client, device_id)
    # Subscribe to all UAV topics
    for topic in ["uav/tracking/#", "uav/status/#", "uav/health/#", "uav/sensor/#"]:
        client.subscribe(topic, qos=0)
        logger.info("Bridge: subscribed to %s", topic)


def _on_message(client: mqtt.Client, userdata, msg: mqtt.MQTTMessage) -> None:
    topic = msg.topic
    try:
        payload = json.loads(msg.payload.decode("utf-8"))
    except Exception as exc:
        logger.warning("Bridge: failed to parse message on %s: %s", topic, exc)
        return

    device_id = payload.get("device_id")
    if not device_id:
        return

    # Publish discovery on first message from this device
    if device_id not in _discovered:
        _discovered.add(device_id)
        publish_discovery(client, device_id)

    # Dispatch state updates
    if topic.startswith("uav/tracking/"):
        publish_tracking_state(client, device_id, payload)
    elif topic.startswith("uav/status/"):
        publish_status_state(client, device_id, payload)
    elif topic.startswith("uav/health/"):
        publish_health_state(client, device_id, payload)
    elif topic.startswith("uav/sensor/"):
        publish_sensor_state(client, device_id, payload)


# ---------------------------------------------------------------------------
# Main loop with exponential backoff reconnect
# ---------------------------------------------------------------------------

def run() -> None:
    client = mqtt.Client(client_id="uav-bridge", clean_session=True)
    client.on_connect = _on_connect
    client.on_message = _on_message

    attempt = 0
    while True:
        try:
            logger.info("Bridge: connecting to %s:%d (attempt %d)", MQTT_HOST, MQTT_PORT, attempt + 1)
            client.connect(MQTT_HOST, MQTT_PORT, keepalive=60)
            client.loop_forever()
            attempt = 0  # reset on clean disconnect
        except Exception as exc:
            delay = min(1.0 * (2 ** attempt), 60.0)
            logger.warning("Bridge: disconnected (%s), reconnecting in %.0fs", exc, delay)
            time.sleep(delay)
            attempt += 1


if __name__ == "__main__":
    run()
