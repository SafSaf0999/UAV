"""
Aggregation service — device state registry.

Thread-safe registry of all known edge device states.
Updated by the MQTT subscriber as messages arrive.

Requirements: 4.2, 4.3, 6.5, v2-3.4, v2-3.5, v2-4.9, v2-5.6, v2-5.7
"""

import asyncio
import inspect
import logging
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_MAX_LOG_ENTRIES = 500
_MAX_DETECTION_HISTORY = 50


@dataclass
class DeviceState:
    """Current known state of one edge device."""

    device_id: str
    status: str = "unknown"          # "online" | "offline" | "unknown"
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
            # Omit log_entries and detection_history from WS push (too large)
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
        await self._notify(device_id)

    async def update_status(self, device_id: str, status_payload: dict) -> None:
        """Update device online/offline status from a Status_Payload dict."""
        if not device_id:
            return
        async with self._lock:
            state = self._devices.setdefault(device_id, DeviceState(device_id=device_id))
            state.status = status_payload.get("status", "unknown")
            state.last_status_ts = status_payload.get("timestamp")
            if status_payload.get("active_model"):
                state.active_model = status_payload["active_model"]
            if status_payload.get("lat") is not None:
                state.lat = float(status_payload["lat"])
            if status_payload.get("lon") is not None:
                state.lon = float(status_payload["lon"])
            if status_payload.get("cert_info"):
                state.cert_info = status_payload["cert_info"]
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
