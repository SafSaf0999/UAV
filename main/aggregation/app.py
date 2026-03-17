"""
Aggregation service — FastAPI app.

Endpoints:
  GET  /devices                  → list all device states
  GET  /devices/{device_id}      → single device state
  POST /command/{device_id}      → publish command to MQTT
  POST /ptz/{device_id}          → publish PTZ command to MQTT
  WS   /ws                       → push DeviceRegistry state updates

Requirements: 4.2, 7.1, 7.2, 13.2
"""

import asyncio
import json
import logging
import os
from contextlib import asynccontextmanager
from typing import Any, List, Optional

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse

from main.aggregation.registry import DeviceRegistry
from main.aggregation.validator import validate_payload
from main.aggregation.mqtt_subscriber import create_subscriber_from_env

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Global state
# ---------------------------------------------------------------------------

registry = DeviceRegistry()
_ws_clients: List[WebSocket] = []
_mqtt_publish_fn = None   # injected at startup or in tests


# ---------------------------------------------------------------------------
# WebSocket push listener
# ---------------------------------------------------------------------------

async def _push_to_ws_clients(device_id: str, state_dict: dict) -> None:
    """Push a state update to all connected WebSocket clients."""
    message = json.dumps({"device_id": device_id, "state": state_dict})
    dead = []
    for ws in list(_ws_clients):
        try:
            await ws.send_text(message)
        except Exception:
            dead.append(ws)
    for ws in dead:
        if ws in _ws_clients:
            _ws_clients.remove(ws)


registry.add_listener(_push_to_ws_clients)


# ---------------------------------------------------------------------------
# MQTT publish helper (injected)
# ---------------------------------------------------------------------------

def _get_mqtt_client():
    """Return the aiomqtt client or a stub for testing."""
    return _mqtt_publish_fn


# ---------------------------------------------------------------------------
# App lifespan
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    global _mqtt_publish_fn

    # Start MQTT subscriber in background
    subscriber = create_subscriber_from_env(registry, validate_payload)
    task = asyncio.create_task(subscriber.run())

    # Expose a simple publish function via paho for commands
    import paho.mqtt.publish as publish  # type: ignore
    import ssl as _ssl

    def _publish(topic: str, payload: str) -> None:
        host = os.environ.get("MQTT_HOST", "mosquitto")
        port = int(os.environ.get("MQTT_PORT", "8883"))
        ca = os.environ.get("MQTT_TLS_CA", "")
        cert = os.environ.get("MQTT_TLS_CERT", "")
        key = os.environ.get("MQTT_TLS_KEY", "")
        tls = None
        if ca:
            tls = {
                "ca_certs": ca,
                "certfile": cert or None,
                "keyfile": key or None,
                "tls_version": _ssl.PROTOCOL_TLS_CLIENT,
                "cert_reqs": _ssl.CERT_REQUIRED,
            }
        try:
            publish.single(topic, payload=payload, hostname=host, port=port, qos=1, tls=tls)
        except Exception as exc:
            logger.error("aggregation: MQTT publish failed: %s", exc)

    _mqtt_publish_fn = _publish

    yield

    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


app = FastAPI(title="UAV Aggregation Service", lifespan=lifespan)


# ---------------------------------------------------------------------------
# REST endpoints
# ---------------------------------------------------------------------------

@app.get("/devices")
async def list_devices():
    devices = await registry.get_all_devices()
    return JSONResponse(content=devices)


@app.get("/devices/{device_id}")
async def get_device(device_id: str):
    state = await registry.get_device(device_id)
    if state is None:
        raise HTTPException(status_code=404, detail=f"Device '{device_id}' not found")
    return JSONResponse(content=state)


@app.post("/command/{device_id}")
async def send_command(device_id: str, body: dict):
    """
    Publish a command to uav/command/{device_id}.
    Body: {"action": "start_stream" | "stop_stream" | "switch_model", ...}
    """
    topic = f"uav/command/{device_id}"
    payload = json.dumps({"device_id": device_id, **body})
    if _mqtt_publish_fn:
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, _mqtt_publish_fn, topic, payload)
    return {"status": "published", "topic": topic}


@app.post("/ptz/{device_id}")
async def send_ptz(device_id: str, body: dict):
    """
    Publish a PTZ command to uav/ptz/{device_id}.
    Body: {"command": "pan_left", "params": {...}}
    """
    topic = f"uav/ptz/{device_id}"
    payload = json.dumps({"device_id": device_id, **body})
    if _mqtt_publish_fn:
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, _mqtt_publish_fn, topic, payload)
    return {"status": "published", "topic": topic}


# ---------------------------------------------------------------------------
# WebSocket endpoint
# ---------------------------------------------------------------------------

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    _ws_clients.append(websocket)
    logger.info("WebSocket client connected (total: %d)", len(_ws_clients))

    # Send current state snapshot on connect
    try:
        devices = await registry.get_all_devices()
        await websocket.send_text(json.dumps({"type": "snapshot", "devices": devices}))

        while True:
            # Keep connection alive; updates are pushed via registry listener
            await websocket.receive_text()

    except WebSocketDisconnect:
        pass
    except Exception as exc:
        logger.warning("WebSocket error: %s", exc)
    finally:
        if websocket in _ws_clients:
            _ws_clients.remove(websocket)
        logger.info("WebSocket client disconnected (total: %d)", len(_ws_clients))
