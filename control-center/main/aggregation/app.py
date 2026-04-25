"""
Aggregation service — FastAPI app.

Endpoints:
  GET  /devices                                    → list all device states
  GET  /devices/{device_id}                        → single device state
  POST /command/{device_id}                        → publish command to MQTT
  POST /ptz/{device_id}                            → publish PTZ command to MQTT
  GET  /devices/{device_id}/detections/export      → export detections as CSV
  GET  /devices/{device_id}/thresholds             → get alert threshold config
  PUT  /devices/{device_id}/thresholds             → update alert threshold config
  WS   /ws                                         → push DeviceRegistry state updates

Requirements: 4.2, 7.1, 7.2, 13.2, 5.1, 5.3, 6.1, 6.4, 7.2, 9.1
"""

import asyncio
import json
import logging
import os
from contextlib import asynccontextmanager
from typing import Any, List, Optional

from fastapi import FastAPI, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse, Response

from main.aggregation.registry import DeviceRegistry
from main.aggregation.validator import validate_payload
from main.aggregation.mqtt_subscriber import create_subscriber_from_env
from main.aggregation.detections_db import init_detections_db, export_detections_csv
from main.aggregation.thresholds import get_threshold_store, ThresholdConfig
from main.aggregation.webhook_dispatcher import get_webhook_dispatcher
from main.aggregation.health_checker import run_health_checker

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

    # Initialize detections database
    try:
        await init_detections_db()
    except Exception as exc:
        logger.warning("aggregation: failed to init detections DB: %s", exc)

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

    # Inject publish function into registry for PTZ follow
    registry.set_publish_fn(_publish)

    # Start health checker background task
    webhook_dispatcher = get_webhook_dispatcher()
    health_task = asyncio.create_task(
        run_health_checker(registry, webhook_dispatcher)
    )

    # Background task: poll ipwebcam sensors every 30s for online devices
    async def _ipwebcam_sensor_poller():
        while True:
            await asyncio.sleep(30)
            try:
                devices = await registry.get_all_devices()
                for device in devices:
                    if device.get("status") == "online" and device.get("ipwebcam_capabilities"):
                        device_id = device["device_id"]
                        topic = f"uav/command/{device_id}"
                        payload = json.dumps({"action": "ipwebcam_sensors"})
                        try:
                            loop = asyncio.get_event_loop()
                            await loop.run_in_executor(None, _mqtt_publish_fn, topic, payload)
                        except Exception as exc:
                            logger.warning("aggregation: ipwebcam sensor poll failed for %s: %s", device_id, exc)
            except Exception as exc:
                logger.warning("aggregation: ipwebcam sensor poller error: %s", exc)

    ipwebcam_poll_task = asyncio.create_task(_ipwebcam_sensor_poller())

    yield

    task.cancel()
    health_task.cancel()
    ipwebcam_poll_task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
    try:
        await health_task
    except asyncio.CancelledError:
        pass
    try:
        await ipwebcam_poll_task
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


@app.get("/devices/{device_id}/health")
async def get_device_health(device_id: str):
    state = await registry.get_device(device_id)
    if state is None:
        raise HTTPException(status_code=404, detail=f"Device '{device_id}' not found")
    return JSONResponse(content=state.get("health"))


@app.get("/logs/{device_id}")
async def get_logs(device_id: str, limit: int = 100, level: Optional[str] = None):
    entries = await registry.get_logs(device_id, limit=limit, level=level)
    return JSONResponse(content=entries)


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
# Detection export endpoint (Task 6.4)
# ---------------------------------------------------------------------------

@app.get("/devices/{device_id}/detections/export")
async def export_detections(
    device_id: str,
    from_: Optional[str] = Query(default=None, alias="from"),
    to: Optional[str] = None,
    format: str = "csv",
):
    """
    Export detections for a device as CSV.

    Query params:
      from  (alias: from_) — ISO 8601 start timestamp (inclusive)
      to                   — ISO 8601 end timestamp (inclusive)
      format               — export format, default "csv"
    """
    from_ts = from_ or ""
    to_ts = to or "9999-12-31T23:59:59Z"
    csv_data = await export_detections_csv(device_id, from_ts, to_ts)
    filename = f"detections_{device_id}.csv"
    return Response(
        content=csv_data,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ---------------------------------------------------------------------------
# Threshold endpoints (Task 7.4)
# ---------------------------------------------------------------------------

@app.get("/devices/{device_id}/thresholds")
async def get_thresholds(device_id: str):
    """Return the alert threshold config for a device."""
    store = get_threshold_store()
    config = store.get(device_id)
    return JSONResponse(content=config.to_dict())


@app.put("/devices/{device_id}/thresholds")
async def update_thresholds(device_id: str, body: dict):
    """Update the alert threshold config for a device."""
    store = get_threshold_store()
    existing = store.get(device_id)
    # Apply provided fields
    updated = ThresholdConfig(
        device_id=device_id,
        min_confidence=float(body.get("min_confidence", existing.min_confidence)),
        consecutive_frames=int(body.get("consecutive_frames", existing.consecutive_frames)),
        alert_classes=list(body.get("alert_classes", existing.alert_classes)),
    )
    store.set(device_id, updated)
    return JSONResponse(content=updated.to_dict())


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
