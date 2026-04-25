"""
Aggregation service — device state registry.

Thread-safe registry of all known edge device states.
Updated by the MQTT subscriber as messages arrive.

Requirements: 4.2, 4.3, 6.5, v2-3.4, v2-3.5, v2-4.9, v2-5.6, v2-5.7,
              5.1, 5.2, 6.2, 6.3, 6.4, 7.2, 7.4, 9.1, 9.2
"""

import asyncio
import inspect
import logging
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)

_MAX_LOG_ENTRIES = 500
_MAX_DETECTION_HISTORY = 50


@dataclass
class DeviceState:
    """Current known state of one edge device."""

    device_id: str
    status: str = "unknown"          # "online" | "offline" | "unknown" | "health_timeout"
    active_model: Optional[str] = None
    lat: Optional[float] = None
    lon: Optional[float] = None
    last_status_ts: Optional[str] = None

    # Latest tracking payload
    last_tracking: Optional[dict] = None
    detection_count: int = 0

    # Per-class detection counts from latest tracking payload
    class_counts: dict = field(default_factory=dict)

    # Last 50 detections (timestamp, label, confidence, bbox)
    detection_history: list = field(default_factory=list)

    # Latest PTZ status
    last_ptz_status: Optional[dict] = None

    # Latest sensor data
    last_sensor: Optional[dict] = None

    # Latest health payload
    health: Optional[dict] = None

    # Certificate info from status payload
    cert_info: Optional[dict] = None

    # Last 500 log entries (WARNING+)
    log_entries: list = field(default_factory=list)

    # Monotonic timestamp of last health message (for health timeout checker)
    last_health_ts: Optional[float] = None

    # PTZ follow: device_id of the leader this device follows (from status payload)
    follow_leader: Optional[str] = None

    # IP Webcam data
    ipwebcam_capabilities: Optional[dict] = None
    ipwebcam_sensors: Optional[dict] = None
    last_snapshot: Optional[str] = None  # base64-encoded JPEG

    def to_dict(self) -> dict:
        return {
            "device_id": self.device_id,
            "status": self.status,
            "active_model": self.active_model,
            "lat": self.lat,
            "lon": self.lon,
            "last_status_ts": self.last_status_ts,
            "detection_count": self.detection_count,
            "class_counts": self.class_counts,
            "last_tracking": self.last_tracking,
            "last_ptz_status": self.last_ptz_status,
            "last_sensor": self.last_sensor,
            "health": self.health,
            "cert_info": self.cert_info,
            "follow_leader": self.follow_leader,
            "ipwebcam_capabilities": self.ipwebcam_capabilities,
            "ipwebcam_sensors": self.ipwebcam_sensors,
            # Omit log_entries, detection_history, and last_snapshot from WS push (too large)
        }

    def to_dict_full(self) -> dict:
        """Full dict including detection_history and log_entries (for REST API)."""
        d = self.to_dict()
        d["detection_history"] = self.detection_history
        d["log_entries"] = self.log_entries
        return d


def _compute_class_counts(detections: list) -> dict:
    """Count detections grouped by label."""
    counts: dict = defaultdict(int)
    for det in detections:
        label = det.get("label", "unknown")
        counts[label] += 1
    return dict(counts)


class DeviceRegistry:
    """
    Thread-safe registry of DeviceState objects keyed by device_id.

    Uses asyncio.Lock for async-safe access from the MQTT subscriber coroutines.
    """

    def __init__(self) -> None:
        self._devices: Dict[str, DeviceState] = {}
        self._lock = asyncio.Lock()
        self._listeners: List[Any] = []  # callables notified on state change
        # Per-device per-label consecutive detection counters for threshold evaluation
        self._consecutive_counts: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
        # MQTT publish callback (injected by app.py lifespan)
        self._publish_fn: Optional[Callable] = None

    # ------------------------------------------------------------------
    # Publish function injection
    # ------------------------------------------------------------------

    def set_publish_fn(self, fn: Callable) -> None:
        """Inject the MQTT publish callback used for PTZ follow commands."""
        self._publish_fn = fn

    # ------------------------------------------------------------------
    # Listener management (for WebSocket push)
    # ------------------------------------------------------------------

    def add_listener(self, callback) -> None:
        """Register a callback(device_id, state_dict) for state changes."""
        self._listeners.append(callback)

    def remove_listener(self, callback) -> None:
        self._listeners = [l for l in self._listeners if l is not callback]

    async def _notify(self, device_id: str) -> None:
        state = self._devices.get(device_id)
        if state is None:
            return
        state_dict = state.to_dict()
        for cb in list(self._listeners):
            try:
                if inspect.iscoroutinefunction(cb):
                    await cb(device_id, state_dict)
                else:
                    cb(device_id, state_dict)
            except Exception as exc:
                logger.warning("DeviceRegistry: listener error: %s", exc)

    # ------------------------------------------------------------------
    # Update methods
    # ------------------------------------------------------------------

    async def update_tracking(self, payload: dict) -> None:
        """Update tracking state from a validated Tracking_Payload dict."""
        device_id = payload.get("device_id")
        if not device_id:
            return
        async with self._lock:
            state = self._devices.setdefault(device_id, DeviceState(device_id=device_id))
            state.last_tracking = payload
            detections = payload.get("detections", [])
            state.detection_count = len(detections)
            state.class_counts = _compute_class_counts(detections)
            if payload.get("active_model"):
                state.active_model = payload["active_model"]
            # Append to detection history (capped at _MAX_DETECTION_HISTORY)
            for det in detections:
                entry = {
                    "timestamp": payload.get("timestamp"),
                    "label": det.get("label"),
                    "confidence": det.get("confidence"),
                    "bbox": det.get("bbox"),
                }
                state.detection_history.append(entry)
            if len(state.detection_history) > _MAX_DETECTION_HISTORY:
                state.detection_history = state.detection_history[-_MAX_DETECTION_HISTORY:]

        # Persist detections to DB (best-effort)
        try:
            from main.aggregation.detections_db import insert_detections
            ts = payload.get("timestamp", "")
            await insert_detections(device_id, ts, detections)
        except Exception as exc:
            logger.warning("registry: failed to persist detections for %s: %s", device_id, exc)

        # Evaluate detections against per-device threshold
        alert_detections = []
        try:
            from main.aggregation.thresholds import get_threshold_store
            threshold = get_threshold_store().get(device_id)
            for det in detections:
                label = det.get("label", "")
                confidence = float(det.get("confidence", 0.0))
                if label in threshold.alert_classes and confidence >= threshold.min_confidence:
                    count = self._consecutive_counts[device_id][label] + 1
                    self._consecutive_counts[device_id][label] = count
                    if count >= threshold.consecutive_frames:
                        alert_detections.append(det)
                else:
                    # Reset consecutive counter for this label
                    self._consecutive_counts[device_id][label] = 0
        except Exception as exc:
            logger.warning("registry: threshold evaluation failed for %s: %s", device_id, exc)
            # Fall back: notify for all detections
            alert_detections = detections

        # Dispatch detection_alert webhook if threshold met
        if alert_detections:
            try:
                from main.aggregation.webhook_dispatcher import get_webhook_dispatcher
                get_webhook_dispatcher().dispatch(
                    "detection_alert",
                    device_id,
                    {
                        "detections": alert_detections,
                        "confidence_max": max(
                            (float(d.get("confidence", 0.0)) for d in alert_detections),
                            default=0.0,
                        ),
                    },
                )
            except Exception as exc:
                logger.warning("registry: webhook dispatch failed for %s: %s", device_id, exc)

        # PTZ follow: check if any device follows this device_id as leader
        if detections and self._publish_fn is not None:
            try:
                await self._dispatch_ptz_follow(device_id, payload, detections)
            except Exception as exc:
                logger.warning("registry: PTZ follow dispatch failed: %s", exc)

        await self._notify(device_id)

    async def update_status(self, device_id: str, status_payload: dict) -> None:
        """Update device online/offline status from a Status_Payload dict."""
        if not device_id:
            return
        new_status = status_payload.get("status", "unknown")
        async with self._lock:
            state = self._devices.setdefault(device_id, DeviceState(device_id=device_id))
            old_status = state.status
            state.status = new_status
            state.last_status_ts = status_payload.get("timestamp")
            if status_payload.get("active_model"):
                state.active_model = status_payload["active_model"]
            if status_payload.get("lat") is not None:
                state.lat = float(status_payload["lat"])
            if status_payload.get("lon") is not None:
                state.lon = float(status_payload["lon"])
            if status_payload.get("cert_info"):
                state.cert_info = status_payload["cert_info"]
            if "follow_leader" in status_payload:
                state.follow_leader = status_payload["follow_leader"]

        # Dispatch webhooks for online/offline transitions
        try:
            from main.aggregation.webhook_dispatcher import get_webhook_dispatcher
            dispatcher = get_webhook_dispatcher()
            if new_status == "online" and old_status != "online":
                dispatcher.dispatch("device_online", device_id, {"status": new_status})
            elif new_status == "offline" and old_status != "offline":
                dispatcher.dispatch("device_offline", device_id, {"status": new_status})
        except Exception as exc:
            logger.warning("registry: webhook dispatch failed for status %s: %s", device_id, exc)

        await self._notify(device_id)

    async def update_ptz_status(self, payload: dict) -> None:
        """Update PTZ status from a PTZ_Status_Payload dict."""
        device_id = payload.get("device_id")
        if not device_id:
            return
        async with self._lock:
            state = self._devices.setdefault(device_id, DeviceState(device_id=device_id))
            state.last_ptz_status = payload
        await self._notify(device_id)

    async def update_sensor(self, payload: dict) -> None:
        """Update sensor data from a Sensor_Payload dict."""
        device_id = payload.get("device_id")
        if not device_id:
            return
        async with self._lock:
            state = self._devices.setdefault(device_id, DeviceState(device_id=device_id))
            state.last_sensor = payload
        await self._notify(device_id)

    async def update_health(self, payload: dict) -> None:
        """Update health data from a Health_Payload dict."""
        device_id = payload.get("device_id")
        if not device_id:
            return
        async with self._lock:
            state = self._devices.setdefault(device_id, DeviceState(device_id=device_id))
            state.health = payload
            state.last_health_ts = time.monotonic()
        await self._notify(device_id)

    async def update_log(self, entry: dict) -> None:
        """Append a Log_Entry (no WS push — log entries are fetched via REST)."""
        device_id = entry.get("device_id")
        if not device_id:
            return
        async with self._lock:
            state = self._devices.setdefault(device_id, DeviceState(device_id=device_id))
            state.log_entries.append(entry)
            if len(state.log_entries) > _MAX_LOG_ENTRIES:
                state.log_entries = state.log_entries[-_MAX_LOG_ENTRIES:]
        # No WS notify for log entries

    async def update_ipwebcam_capabilities(self, device_id: str, data: dict) -> None:
        """Store IP Webcam capabilities for a device."""
        if not device_id:
            return
        async with self._lock:
            state = self._devices.setdefault(device_id, DeviceState(device_id=device_id))
            state.ipwebcam_capabilities = data
        await self._notify(device_id)

    async def update_ipwebcam_sensors(self, device_id: str, data: dict) -> None:
        """Store latest IP Webcam sensor data for a device."""
        if not device_id:
            return
        async with self._lock:
            state = self._devices.setdefault(device_id, DeviceState(device_id=device_id))
            state.ipwebcam_sensors = data
        await self._notify(device_id)

    async def update_snapshot(self, device_id: str, data: str) -> None:
        """Store latest snapshot (base64) and forward via _notify with snapshot key."""
        if not device_id:
            return
        async with self._lock:
            state = self._devices.setdefault(device_id, DeviceState(device_id=device_id))
            state.last_snapshot = data
        # Notify with a special snapshot key so listeners can forward it
        snapshot_state = {"snapshot": data, "device_id": device_id}
        for cb in list(self._listeners):
            try:
                if inspect.iscoroutinefunction(cb):
                    await cb(device_id, snapshot_state)
                else:
                    cb(device_id, snapshot_state)
            except Exception as exc:
                logger.warning("DeviceRegistry: snapshot listener error: %s", exc)

    # ------------------------------------------------------------------
    # PTZ follow helper
    # ------------------------------------------------------------------

    async def _dispatch_ptz_follow(
        self, leader_id: str, payload: dict, detections: list
    ) -> None:
        """
        For each device that has follow_leader == leader_id, compute bearing
        from the first detection's bounding box center and publish a PTZ command.
        """
        from main.aggregation.ptz_follow import compute_bearing
        import json

        # Get compass bearing from leader's last sensor payload
        async with self._lock:
            leader_state = self._devices.get(leader_id)
            compass_bearing = 0.0
            if leader_state and leader_state.last_sensor:
                compass_bearing = float(
                    leader_state.last_sensor.get("compass_bearing", 0.0)
                )
            # Find all followers
            followers = [
                s.device_id
                for s in self._devices.values()
                if s.follow_leader == leader_id
            ]

        if not followers:
            return

        # Use first detection's bbox center
        first_det = detections[0]
        bbox = first_det.get("bbox") or [0.0, 0.0, 0.0, 0.0]
        if isinstance(bbox, (list, tuple)) and len(bbox) >= 4:
            cx = float(bbox[0]) + float(bbox[2]) / 2.0
        else:
            cx = 0.5

        bearing = compute_bearing(cx, compass_bearing)
        ptz_payload = json.dumps({
            "command": "absolute_pan",
            "params": {"bearing": bearing},
            "source": "ptz_follow",
            "leader_id": leader_id,
        })

        for follower_id in followers:
            topic = f"uav/ptz/{follower_id}"
            try:
                import asyncio as _asyncio
                loop = _asyncio.get_event_loop()
                await loop.run_in_executor(None, self._publish_fn, topic, ptz_payload)
                logger.debug(
                    "registry: PTZ follow: sent bearing=%.1f to %s (leader=%s)",
                    bearing, follower_id, leader_id,
                )
            except Exception as exc:
                logger.warning(
                    "registry: PTZ follow publish failed for %s: %s", follower_id, exc
                )

    # ------------------------------------------------------------------
    # Read methods
    # ------------------------------------------------------------------

    async def get_device(self, device_id: str) -> Optional[dict]:
        async with self._lock:
            state = self._devices.get(device_id)
            return state.to_dict() if state else None

    async def get_device_full(self, device_id: str) -> Optional[dict]:
        """Return full device state including detection_history and log_entries."""
        async with self._lock:
            state = self._devices.get(device_id)
            return state.to_dict_full() if state else None

    async def get_all_devices(self) -> List[dict]:
        async with self._lock:
            return [s.to_dict() for s in self._devices.values()]

    async def get_logs(
        self,
        device_id: str,
        limit: int = 100,
        level: Optional[str] = None,
    ) -> List[dict]:
        """Return filtered log entries for a device."""
        async with self._lock:
            state = self._devices.get(device_id)
            if not state:
                return []
            entries = state.log_entries
            if level:
                entries = [e for e in entries if e.get("level") == level.upper()]
            return entries[-limit:]
