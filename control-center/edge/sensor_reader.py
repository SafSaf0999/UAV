"""
Edge device — sensor reader (optional).

Reads compass bearing and pitch from a configurable source:
  - "serial_nmea": reads NMEA sentences from a serial port
  - "http":        polls an IP Webcam / HTTP endpoint for JSON sensor data

Validates bearing in [0, 360) and pitch in [-90, 90] before publishing.
Publishes uav/sensor/{device_id} (QoS 0) as Sensor_Payload JSON.

Requirements: 17.3, 17.4
"""

import json
import logging
import threading
import time
from datetime import datetime, timezone
from typing import Any, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Sensor_Payload builder
# ---------------------------------------------------------------------------

def build_sensor_payload(
    device_id: str,
    compass_bearing_deg: float,
    pitch_deg: float,
    extra: Optional[dict] = None,
) -> dict:
    """
    Build a Sensor_Payload dict.

    Args:
        device_id:            Edge device identifier.
        compass_bearing_deg:  Bearing in [0, 360).
        pitch_deg:            Pitch in [-90, 90].
        extra:                Optional additional fields.

    Returns:
        Sensor_Payload dict, or None if values are out of range.
    """
    if not (0.0 <= compass_bearing_deg < 360.0):
        logger.warning(
            "SensorReader: compass_bearing_deg %.2f out of range [0, 360) — skipping",
            compass_bearing_deg,
        )
        return None
    if not (-90.0 <= pitch_deg <= 90.0):
        logger.warning(
            "SensorReader: pitch_deg %.2f out of range [-90, 90] — skipping",
            pitch_deg,
        )
        return None

    payload = {
        "device_id": device_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "compass_bearing_deg": compass_bearing_deg,
        "pitch_deg": pitch_deg,
    }
    if extra:
        payload.update(extra)
    return payload


# ---------------------------------------------------------------------------
# NMEA parser helpers
# ---------------------------------------------------------------------------

def _parse_nmea_hchdg(sentence: str) -> Optional[float]:
    """
    Parse NMEA HCHDG sentence for magnetic heading.
    $HCHDG,<heading>,,,<variation>,<E/W>*<checksum>
    Returns bearing in [0, 360) or None on parse error.
    """
    try:
        parts = sentence.strip().split(",")
        if len(parts) < 2:
            return None
        heading = float(parts[1])
        return heading % 360.0
    except (ValueError, IndexError):
        return None


def _parse_nmea_gprmc(sentence: str) -> Optional[float]:
    """
    Parse NMEA GPRMC sentence for course over ground.
    Returns bearing in [0, 360) or None.
    """
    try:
        parts = sentence.strip().split(",")
        if len(parts) < 9 or parts[2] != "A":
            return None
        cog = float(parts[8])
        return cog % 360.0
    except (ValueError, IndexError):
        return None


# ---------------------------------------------------------------------------
# SensorReader
# ---------------------------------------------------------------------------

class SensorReader:
    """
    Reads sensor data and publishes Sensor_Payload via MQTT.

    Args:
        config:      Loaded Config object.
        mqtt_client: MQTTClient for publishing sensor payloads.
    """

    def __init__(self, config: Any, mqtt_client: Any) -> None:
        self._config = config
        self._mqtt_client = mqtt_client
        self._device_id: str = config.device_id
        self._source: str = config.get("sensor.source", "http")
        self._interval: float = float(config.get("sensor.poll_interval_s", 1.0))
        self._running = False
        self._thread: Optional[threading.Thread] = None

        # Latest readings (thread-safe via GIL for simple float assignment)
        self.last_bearing: Optional[float] = None
        self.last_pitch: Optional[float] = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start(self) -> None:
        self._running = True
        self._thread = threading.Thread(
            target=self._run_loop, daemon=True, name="sensor-reader"
        )
        self._thread.start()
        logger.info("SensorReader: started (source=%s)", self._source)

    def stop(self) -> None:
        self._running = False
        if self._thread:
            self._thread.join(timeout=3)
        logger.info("SensorReader: stopped")

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _run_loop(self) -> None:
        while self._running:
            try:
                if self._source == "serial_nmea":
                    self._read_serial()
                else:
                    self._read_http()
            except Exception as exc:
                logger.warning("SensorReader: read error: %s", exc)
            time.sleep(self._interval)

    def _read_http(self) -> None:
        """Poll an HTTP endpoint (e.g. IP Webcam /sensors.json)."""
        import urllib.request
        url = self._config.get("sensor.http_url", "http://localhost:8080/sensors.json")
        try:
            with urllib.request.urlopen(url, timeout=2) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except Exception as exc:
            logger.debug("SensorReader: HTTP poll failed: %s", exc)
            return

        # IP Webcam app format: {"orientation": {"azimuth": ..., "pitch": ...}}
        orientation = data.get("orientation", {})
        bearing_raw = orientation.get("azimuth", data.get("compass_bearing_deg"))
        pitch_raw = orientation.get("pitch", data.get("pitch_deg"))

        if bearing_raw is None or pitch_raw is None:
            logger.debug("SensorReader: missing bearing/pitch in HTTP response")
            return

        bearing = float(bearing_raw) % 360.0
        pitch = max(-90.0, min(90.0, float(pitch_raw)))

        self._publish(bearing, pitch)

    def _read_serial(self) -> None:
        """Read NMEA sentences from a serial port."""
        port = self._config.get("sensor.serial_port", "/dev/ttyUSB1")
        baud = int(self._config.get("sensor.baudrate", 4800))

        try:
            import serial  # type: ignore
            with serial.Serial(port, baud, timeout=2) as ser:
                line = ser.readline().decode("ascii", errors="ignore").strip()
        except Exception as exc:
            logger.warning("SensorReader: serial read failed on %s: %s", port, exc)
            return

        bearing = None
        if line.startswith("$HCHDG"):
            bearing = _parse_nmea_hchdg(line)
        elif line.startswith("$GPRMC"):
            bearing = _parse_nmea_gprmc(line)

        if bearing is None:
            return

        # Pitch not available from basic NMEA; default to 0
        pitch = 0.0
        self._publish(bearing, pitch)

    def _publish(self, bearing: float, pitch: float) -> None:
        payload = build_sensor_payload(self._device_id, bearing, pitch)
        if payload is None:
            return
        self.last_bearing = bearing
        self.last_pitch = pitch
        try:
            self._mqtt_client.publish_sensor(payload)
        except Exception as exc:
            logger.warning("SensorReader: publish failed: %s", exc)
