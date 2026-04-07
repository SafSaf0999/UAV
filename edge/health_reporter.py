"""
Edge device — health reporter.

Publishes a Health_Payload to uav/health/{device_id} every 30 seconds.
Collects CPU and memory via psutil, reads inference FPS and frame count
from the InferenceEngine, and tracks reconnect counters from MQTTClient
and CameraSource.

Requirements: v2-3.1, v2-3.2, v2-3.3
"""

import json
import logging
import threading
import time
from datetime import datetime, timezone
from typing import Any, Optional

logger = logging.getLogger(__name__)


class HealthReporter:
    """
    Publishes Health_Payload to MQTT every interval_s seconds.

    Args:
        config:           Loaded Config object.
        mqtt_client:      MQTTClient instance.
        inference_engine: InferenceEngine instance (for FPS and frame count).
        camera_source:    CameraSource instance (for reconnect counter).
    """

    def __init__(
        self,
        config: Any,
        mqtt_client: Any,
        inference_engine: Any,
        camera_source: Any,
    ) -> None:
        self._config = config
        self._mqtt_client = mqtt_client
        self._engine = inference_engine
        self._camera = camera_source
        self._device_id: str = config.device_id
        self._interval: float = float(config.get("health.interval_s", 30.0))
        self._start_time: float = time.monotonic()
        self._running = False
        self._thread: Optional[threading.Thread] = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start(self) -> None:
        self._running = True
        self._thread = threading.Thread(
            target=self._run_loop, daemon=True, name="health-reporter"
        )
        self._thread.start()
        logger.info("HealthReporter: started (interval=%.0fs)", self._interval)

    def stop(self) -> None:
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
        logger.info("HealthReporter: stopped")

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _collect(self) -> dict:
        import psutil

        uptime_s = int(time.monotonic() - self._start_time)
        cpu = psutil.cpu_percent(interval=None)
        mem = psutil.virtual_memory().percent

        # Inference FPS and frame count from engine
        inference_fps = getattr(self._engine, "current_fps", 0.0)
        frames_processed = getattr(self._engine, "frame_id", 0)

        # Reconnect counters
        mqtt_reconnects = getattr(self._mqtt_client, "_reconnect_attempt", 0)
        camera_reconnects = getattr(self._camera, "reconnect_count", 0)

        return {
            "device_id": self._device_id,
            "uptime_s": max(0, uptime_s),
            "cpu_percent": max(0.0, min(100.0, float(cpu))),
            "memory_percent": max(0.0, min(100.0, float(mem))),
            "inference_fps": max(0.0, float(inference_fps)),
            "frames_processed": max(0, int(frames_processed)),
            "mqtt_reconnects": max(0, int(mqtt_reconnects)),
            "camera_reconnects": max(0, int(camera_reconnects)),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    def _run_loop(self) -> None:
        while self._running:
            try:
                payload = self._collect()
                self._mqtt_client.publish_health(
                    json.dumps(payload, ensure_ascii=False).encode("utf-8")
                )
            except Exception as exc:
                logger.warning("HealthReporter: publish failed: %s", exc)
            # Sleep in small increments so stop() is responsive
            for _ in range(int(self._interval * 10)):
                if not self._running:
                    break
                time.sleep(0.1)
