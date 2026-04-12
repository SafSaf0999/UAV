#!/usr/bin/env python3
"""
Edge device simulator — edge_sim.py

Simulates a second edge device publishing health and tracking payloads
over MQTT with TLS + username/password authentication.

Usage:
    python edge_sim.py --host 10.x.x.x --port 8883 --ca secrets/ca.crt \\
                       --username edge-sim --password secret --device-id edge-sim

Publishes:
  - uav/health/{device_id}    every 30 seconds
  - uav/tracking/{device_id}  every 2 seconds (with a fake drone detection)
  - uav/status/{device_id}    once on connect (online), LWT for offline

Requirements: 7.3
"""

import argparse
import json
import logging
import random
import ssl
import sys
import time
from datetime import datetime, timezone

try:
    import paho.mqtt.client as mqtt
except ImportError:
    print("ERROR: paho-mqtt is required. Install with: pip install paho-mqtt", file=sys.stderr)
    sys.exit(1)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("edge_sim")

HEALTH_INTERVAL = 30   # seconds
TRACKING_INTERVAL = 2  # seconds


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _make_health_payload(device_id: str) -> dict:
    """Generate a fake health payload."""
    return {
        "device_id": device_id,
        "timestamp": _now_iso(),
        "cpu_percent": round(random.uniform(10.0, 80.0), 1),
        "memory_percent": round(random.uniform(20.0, 70.0), 1),
        "disk_percent": round(random.uniform(5.0, 50.0), 1),
        "temperature": round(random.uniform(35.0, 65.0), 1),
        "uptime_seconds": int(time.monotonic()),
    }


def _make_tracking_payload(device_id: str) -> dict:
    """Generate a fake tracking payload with one drone detection."""
    cx = round(random.uniform(0.2, 0.8), 3)
    cy = round(random.uniform(0.2, 0.8), 3)
    w = round(random.uniform(0.05, 0.2), 3)
    h = round(random.uniform(0.05, 0.2), 3)
    return {
        "device_id": device_id,
        "timestamp": _now_iso(),
        "active_model": "yolov8n",
        "detections": [
            {
                "label": "drone",
                "confidence": round(random.uniform(0.6, 0.99), 3),
                "bbox": [cx - w / 2, cy - h / 2, w, h],
                "track_id": 1,
            }
        ],
    }


def _make_status_payload(device_id: str, status: str) -> dict:
    """Generate a status payload."""
    return {
        "device_id": device_id,
        "timestamp": _now_iso(),
        "status": status,
        "active_model": "yolov8n",
    }


def run(args: argparse.Namespace) -> None:
    """Main simulation loop."""
    device_id = args.device_id

    # Build LWT payload
    lwt_payload = json.dumps(_make_status_payload(device_id, "offline"))

    client = mqtt.Client(client_id=device_id, protocol=mqtt.MQTTv311)

    # TLS configuration
    if args.ca:
        tls_ctx = ssl.create_default_context(ssl.Purpose.SERVER_AUTH)
        tls_ctx.load_verify_locations(args.ca)
        if args.cert and args.key:
            tls_ctx.load_cert_chain(args.cert, args.key)
        client.tls_set_context(tls_ctx)

    # Username/password auth
    if args.username:
        client.username_pw_set(args.username, args.password or "")

    # Last Will and Testament
    client.will_set(
        f"uav/status/{device_id}",
        payload=lwt_payload,
        qos=1,
        retain=False,
    )

    def on_connect(client, userdata, flags, rc):
        if rc == 0:
            logger.info("edge_sim: connected to %s:%d as %s", args.host, args.port, device_id)
            # Publish online status
            status_payload = json.dumps(_make_status_payload(device_id, "online"))
            client.publish(f"uav/status/{device_id}", status_payload, qos=1)
        else:
            logger.error("edge_sim: connection failed with rc=%d", rc)

    def on_disconnect(client, userdata, rc):
        logger.warning("edge_sim: disconnected (rc=%d)", rc)

    client.on_connect = on_connect
    client.on_disconnect = on_disconnect

    client.connect(args.host, args.port, keepalive=60)
    client.loop_start()

    last_health = 0.0
    last_tracking = 0.0

    logger.info("edge_sim: starting simulation loop for device '%s'", device_id)
    try:
        while True:
            now = time.monotonic()

            if now - last_health >= HEALTH_INTERVAL:
                payload = json.dumps(_make_health_payload(device_id))
                client.publish(f"uav/health/{device_id}", payload, qos=0)
                logger.debug("edge_sim: published health")
                last_health = now

            if now - last_tracking >= TRACKING_INTERVAL:
                payload = json.dumps(_make_tracking_payload(device_id))
                client.publish(f"uav/tracking/{device_id}", payload, qos=0)
                logger.debug("edge_sim: published tracking")
                last_tracking = now

            time.sleep(0.1)

    except KeyboardInterrupt:
        logger.info("edge_sim: shutting down")
    finally:
        offline_payload = json.dumps(_make_status_payload(device_id, "offline"))
        client.publish(f"uav/status/{device_id}", offline_payload, qos=1)
        time.sleep(0.5)
        client.loop_stop()
        client.disconnect()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Simulate an edge device publishing MQTT payloads."
    )
    parser.add_argument("--host", default="localhost", help="MQTT broker host")
    parser.add_argument("--port", type=int, default=8883, help="MQTT broker port")
    parser.add_argument("--ca", default="", help="Path to CA certificate (for TLS)")
    parser.add_argument("--cert", default="", help="Path to client certificate (optional)")
    parser.add_argument("--key", default="", help="Path to client private key (optional)")
    parser.add_argument("--username", default="edge-sim", help="MQTT username")
    parser.add_argument("--password", default="secret", help="MQTT password")
    parser.add_argument("--device-id", default="edge-sim", help="Device ID to simulate")
    args = parser.parse_args()
    run(args)


if __name__ == "__main__":
    main()
