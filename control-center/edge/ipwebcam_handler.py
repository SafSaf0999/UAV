"""
Edge device — IP Webcam HTTP API handler.

Proxies control commands from MQTT to the IP Webcam Android app HTTP API.
Capabilities are fetched on startup and cached for 5 minutes.

Requirements: 14.1–14.40
"""

import logging
import time
import urllib.request

logger = logging.getLogger(__name__)

_CACHE_TTL_S = 300.0  # 5 minutes
_HTTP_TIMEOUT_S = 5


class IPWebcamHandler:
    """
    Handles communication with the IP Webcam Android app HTTP API.

    Args:
        base_url: Base URL of the IP Webcam app, e.g. "http://192.168.1.100:8080".
    """

    def __init__(self, base_url: str) -> None:
        self._base_url = base_url.rstrip("/")
        self._capabilities_cache = None
        self._cache_ts: float = 0.0

    # ------------------------------------------------------------------
    # Capabilities
    # ------------------------------------------------------------------

    def fetch_capabilities(self) -> dict:
        """
        Fetch device capabilities from /status.json?show_avail=1.
        Result is cached for 5 minutes.
        """
        now = time.monotonic()
        if self._capabilities_cache is not None and (now - self._cache_ts) < _CACHE_TTL_S:
            return self._capabilities_cache

        url = f"{self._base_url}/status.json?show_avail=1"
        try:
            import json
            with urllib.request.urlopen(url, timeout=_HTTP_TIMEOUT_S) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            self._capabilities_cache = data
            self._cache_ts = time.monotonic()
            logger.info("IPWebcamHandler: capabilities fetched and cached")
            return data
        except Exception as exc:
            logger.warning("IPWebcamHandler: failed to fetch capabilities: %s", exc)
            return {}

    # ------------------------------------------------------------------
    # Control
    # ------------------------------------------------------------------

    def handle_control(self, setting: str, value=None) -> bool:
        """
        Send a control command to the IP Webcam HTTP API.

        Returns True on success, False on any error.
        """
        url = self._build_control_url(setting, value)
        if url is None:
            return False
        try:
            with urllib.request.urlopen(url, timeout=_HTTP_TIMEOUT_S) as resp:
                resp.read()
            logger.info("IPWebcamHandler: control '%s'=%s applied", setting, value)
            return True
        except Exception as exc:
            logger.warning("IPWebcamHandler: control '%s'=%s failed: %s", setting, value, exc)
            return False

    def _build_control_url(self, setting: str, value=None) -> str | None:
        """Build the HTTP URL for a given setting/value pair."""
        base = self._base_url

        if setting == "zoom":
            return f"{base}/zoom?level={value}"
        elif setting == "focus":
            return f"{base}/focus"
        elif setting in ("snapshot", "snapshot_af"):
            # These are handled by fetch_snapshot(); not a control URL
            return None
        elif setting == "crop_x":
            return f"{base}/settings/crop?set={value},0"
        elif setting == "crop_y":
            return f"{base}/settings/crop?set=0,{value}"
        elif setting == "focus_mode":
            return f"{base}/settings/focus_mode?set={value}"
        elif setting == "manual_sensor":
            return f"{base}/settings/camera2_manual_sensor?set={value}"
        elif setting == "iso":
            return f"{base}/settings/camera2_sensor_sensitivity?set={value}"
        elif setting == "exposure_time":
            return f"{base}/settings/camera2_sensor_exposure_time?set={value}"
        elif setting == "frame_duration":
            return f"{base}/settings/camera2_sensor_frame_duration?set={value}"
        elif setting == "aperture":
            return f"{base}/settings/camera2_lens_aperture?set={value}"
        elif setting == "video_size":
            return f"{base}/settings/video_size?set={value}"
        else:
            return f"{base}/settings/{setting}?set={value}"

    # ------------------------------------------------------------------
    # Snapshot
    # ------------------------------------------------------------------

    def fetch_snapshot(self, af: bool = False) -> bytes:
        """
        Fetch a JPEG snapshot from the camera.

        Args:
            af: If True, trigger autofocus before capture (/photoaf.jpg).
        """
        endpoint = "photoaf.jpg" if af else "photo.jpg"
        url = f"{self._base_url}/{endpoint}"
        with urllib.request.urlopen(url, timeout=_HTTP_TIMEOUT_S) as resp:
            return resp.read()

    # ------------------------------------------------------------------
    # Sensors
    # ------------------------------------------------------------------

    def fetch_sensors(self) -> dict:
        """Fetch sensor data from /sensors.json."""
        import json
        url = f"{self._base_url}/sensors.json"
        with urllib.request.urlopen(url, timeout=_HTTP_TIMEOUT_S) as resp:
            return json.loads(resp.read().decode("utf-8"))
