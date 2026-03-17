"""
Edge device — PTZ controller.

Dispatches PTZ commands to the correct driver based on ptz.hardware_type in
config. Supports: digital, visca_serial, visca_ip, onvif, arduino.

Implements all 10 command types (Req 13.3):
  pan_left, pan_right, tilt_up, tilt_down, zoom_in, zoom_out,
  pan_tilt_absolute, zoom_absolute, stop, home

Publishes PTZ status to uav/ptz/status/{device_id} after each command.
Silently ignores commands when PTZ is disabled.
Logs error and disables PTZ for session if serial port unavailable.

Requirements: 13.2, 13.3, 13.4, 13.5, 13.6, 13.7, 13.8
"""

import logging
import threading
from typing import Any, Optional

logger = logging.getLogger(__name__)

VALID_COMMANDS = frozenset([
    "pan_left", "pan_right", "tilt_up", "tilt_down",
    "zoom_in", "zoom_out", "pan_tilt_absolute", "zoom_absolute",
    "stop", "home",
])


# ---------------------------------------------------------------------------
# Base driver
# ---------------------------------------------------------------------------

class BasePtzDriver:
    """Abstract base for PTZ hardware drivers."""

    def execute(self, command: str, params: dict) -> bool:
        """Execute a PTZ command. Returns True on success."""
        raise NotImplementedError


# ---------------------------------------------------------------------------
# Digital zoom driver
# ---------------------------------------------------------------------------

class DigitalZoomDriver(BasePtzDriver):
    """
    Software crop/zoom driver.

    Maintains a zoom level and pan/tilt offset; the InferenceEngine reads
    these to crop the frame before inference.
    """

    def __init__(self) -> None:
        self.zoom_level: float = 1.0   # 1.0 = no zoom
        self.pan_offset: float = 0.0   # normalised -1..1
        self.tilt_offset: float = 0.0  # normalised -1..1
        self._lock = threading.Lock()

    def execute(self, command: str, params: dict) -> bool:
        step = float(params.get("step", 0.1))
        with self._lock:
            if command == "zoom_in":
                self.zoom_level = min(self.zoom_level + step, 8.0)
            elif command == "zoom_out":
                self.zoom_level = max(self.zoom_level - step, 1.0)
            elif command == "zoom_absolute":
                self.zoom_level = max(1.0, min(float(params.get("zoom", 1.0)), 8.0))
            elif command == "pan_left":
                self.pan_offset = max(self.pan_offset - step, -1.0)
            elif command == "pan_right":
                self.pan_offset = min(self.pan_offset + step, 1.0)
            elif command == "tilt_up":
                self.tilt_offset = min(self.tilt_offset + step, 1.0)
            elif command == "tilt_down":
                self.tilt_offset = max(self.tilt_offset - step, -1.0)
            elif command == "pan_tilt_absolute":
                self.pan_offset = float(params.get("pan", 0.0))
                self.tilt_offset = float(params.get("tilt", 0.0))
            elif command in ("stop", "home"):
                self.zoom_level = 1.0
                self.pan_offset = 0.0
                self.tilt_offset = 0.0
        return True


# ---------------------------------------------------------------------------
# VISCA serial driver
# ---------------------------------------------------------------------------

class ViscaSerialDriver(BasePtzDriver):
    """VISCA over RS-232/RS-485 serial port."""

    # VISCA command bytes (simplified subset)
    _HEADER = 0x81
    _TERMINATOR = 0xFF

    def __init__(self, port: str, baudrate: int = 9600) -> None:
        self._port = port
        self._baudrate = baudrate
        self._serial = None
        self._connect()

    def _connect(self) -> None:
        try:
            import serial  # type: ignore
            self._serial = serial.Serial(self._port, self._baudrate, timeout=1)
            logger.info("ViscaSerialDriver: opened %s at %d baud", self._port, self._baudrate)
        except Exception as exc:
            logger.error("ViscaSerialDriver: cannot open %s: %s", self._port, exc)
            self._serial = None

    def _send(self, data: bytes) -> bool:
        if self._serial is None:
            return False
        try:
            self._serial.write(data)
            return True
        except Exception as exc:
            logger.error("ViscaSerialDriver: write error: %s", exc)
            return False

    def _build_pan_tilt(self, command: str, params: dict) -> bytes:
        speed = int(params.get("speed", 5)) & 0x0F
        if command == "pan_left":
            return bytes([self._HEADER, 0x01, 0x06, 0x01, speed, speed, 0x01, 0x03, self._TERMINATOR])
        elif command == "pan_right":
            return bytes([self._HEADER, 0x01, 0x06, 0x01, speed, speed, 0x02, 0x03, self._TERMINATOR])
        elif command == "tilt_up":
            return bytes([self._HEADER, 0x01, 0x06, 0x01, speed, speed, 0x03, 0x01, self._TERMINATOR])
        elif command == "tilt_down":
            return bytes([self._HEADER, 0x01, 0x06, 0x01, speed, speed, 0x03, 0x02, self._TERMINATOR])
        elif command == "stop":
            return bytes([self._HEADER, 0x01, 0x06, 0x01, 0x00, 0x00, 0x03, 0x03, self._TERMINATOR])
        elif command == "home":
            return bytes([self._HEADER, 0x01, 0x06, 0x04, self._TERMINATOR])
        return b""

    def execute(self, command: str, params: dict) -> bool:
        if command in ("pan_left", "pan_right", "tilt_up", "tilt_down", "stop", "home"):
            data = self._build_pan_tilt(command, params)
        elif command == "zoom_in":
            data = bytes([self._HEADER, 0x01, 0x04, 0x07, 0x02, self._TERMINATOR])
        elif command == "zoom_out":
            data = bytes([self._HEADER, 0x01, 0x04, 0x07, 0x03, self._TERMINATOR])
        elif command == "zoom_absolute":
            zoom = int(params.get("zoom", 0)) & 0xFFFF
            p = [(zoom >> 12) & 0xF, (zoom >> 8) & 0xF, (zoom >> 4) & 0xF, zoom & 0xF]
            data = bytes([self._HEADER, 0x01, 0x04, 0x47] + p + [self._TERMINATOR])
        elif command == "pan_tilt_absolute":
            pan = int(params.get("pan", 0)) & 0xFFFF
            tilt = int(params.get("tilt", 0)) & 0xFFFF
            speed = int(params.get("speed", 5)) & 0x0F
            pp = [(pan >> 12) & 0xF, (pan >> 8) & 0xF, (pan >> 4) & 0xF, pan & 0xF]
            tp = [(tilt >> 12) & 0xF, (tilt >> 8) & 0xF, (tilt >> 4) & 0xF, tilt & 0xF]
            data = bytes([self._HEADER, 0x01, 0x06, 0x02, speed, speed] + pp + tp + [self._TERMINATOR])
        else:
            return False
        return self._send(data)


# ---------------------------------------------------------------------------
# VISCA IP driver
# ---------------------------------------------------------------------------

class ViscaIpDriver(BasePtzDriver):
    """VISCA over UDP/IP (Sony VISCA-over-IP protocol)."""

    def __init__(self, host: str, port: int = 52381) -> None:
        self._host = host
        self._port = port
        self._seq = 1
        self._sock = None
        self._connect()

    def _connect(self) -> None:
        import socket
        try:
            self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self._sock.settimeout(1.0)
            logger.info("ViscaIpDriver: targeting %s:%d", self._host, self._port)
        except Exception as exc:
            logger.error("ViscaIpDriver: socket error: %s", exc)
            self._sock = None

    def _send(self, visca_payload: bytes) -> bool:
        if self._sock is None:
            return False
        # VISCA-over-IP header: type=0x0100, length, sequence number
        length = len(visca_payload)
        header = bytes([
            0x01, 0x00,
            (length >> 8) & 0xFF, length & 0xFF,
            (self._seq >> 24) & 0xFF, (self._seq >> 16) & 0xFF,
            (self._seq >> 8) & 0xFF, self._seq & 0xFF,
        ])
        self._seq += 1
        try:
            self._sock.sendto(header + visca_payload, (self._host, self._port))
            return True
        except Exception as exc:
            logger.error("ViscaIpDriver: send error: %s", exc)
            return False

    def execute(self, command: str, params: dict) -> bool:
        # Reuse serial driver's byte-building logic (same VISCA bytes, different transport)
        _serial = ViscaSerialDriver.__new__(ViscaSerialDriver)
        _serial._serial = None
        data = _serial._build_pan_tilt(command, params) if command in (
            "pan_left", "pan_right", "tilt_up", "tilt_down", "stop", "home"
        ) else b""
        if not data:
            # Delegate zoom commands
            if command == "zoom_in":
                data = bytes([0x81, 0x01, 0x04, 0x07, 0x02, 0xFF])
            elif command == "zoom_out":
                data = bytes([0x81, 0x01, 0x04, 0x07, 0x03, 0xFF])
            elif command == "zoom_absolute":
                zoom = int(params.get("zoom", 0)) & 0xFFFF
                p = [(zoom >> 12) & 0xF, (zoom >> 8) & 0xF, (zoom >> 4) & 0xF, zoom & 0xF]
                data = bytes([0x81, 0x01, 0x04, 0x47] + p + [0xFF])
            elif command == "pan_tilt_absolute":
                pan = int(params.get("pan", 0)) & 0xFFFF
                tilt = int(params.get("tilt", 0)) & 0xFFFF
                speed = int(params.get("speed", 5)) & 0x0F
                pp = [(pan >> 12) & 0xF, (pan >> 8) & 0xF, (pan >> 4) & 0xF, pan & 0xF]
                tp = [(tilt >> 12) & 0xF, (tilt >> 8) & 0xF, (tilt >> 4) & 0xF, tilt & 0xF]
                data = bytes([0x81, 0x01, 0x06, 0x02, speed, speed] + pp + tp + [0xFF])
            else:
                return False
        return self._send(data)


# ---------------------------------------------------------------------------
# ONVIF driver
# ---------------------------------------------------------------------------

class OnvifDriver(BasePtzDriver):
    """PTZ control via ONVIF using onvif-zeep."""

    def __init__(self, host: str, port: int, username: str, password: str) -> None:
        self._host = host
        self._port = port
        self._username = username
        self._password = password
        self._ptz = None
        self._profile_token = None
        self._connect()

    def _connect(self) -> None:
        try:
            from onvif import ONVIFCamera  # type: ignore
            cam = ONVIFCamera(self._host, self._port, self._username, self._password)
            media = cam.create_media_service()
            profiles = media.GetProfiles()
            self._profile_token = profiles[0].token if profiles else None
            self._ptz = cam.create_ptz_service()
            logger.info("OnvifDriver: connected to %s:%d", self._host, self._port)
        except Exception as exc:
            logger.error("OnvifDriver: connection failed: %s", exc)
            self._ptz = None

    def execute(self, command: str, params: dict) -> bool:
        if self._ptz is None or self._profile_token is None:
            return False
        try:
            speed = float(params.get("speed", 0.5))
            if command == "pan_left":
                req = self._ptz.create_type("ContinuousMove")
                req.ProfileToken = self._profile_token
                req.Velocity = {"PanTilt": {"x": -speed, "y": 0}, "Zoom": {"x": 0}}
                self._ptz.ContinuousMove(req)
            elif command == "pan_right":
                req = self._ptz.create_type("ContinuousMove")
                req.ProfileToken = self._profile_token
                req.Velocity = {"PanTilt": {"x": speed, "y": 0}, "Zoom": {"x": 0}}
                self._ptz.ContinuousMove(req)
            elif command == "tilt_up":
                req = self._ptz.create_type("ContinuousMove")
                req.ProfileToken = self._profile_token
                req.Velocity = {"PanTilt": {"x": 0, "y": speed}, "Zoom": {"x": 0}}
                self._ptz.ContinuousMove(req)
            elif command == "tilt_down":
                req = self._ptz.create_type("ContinuousMove")
                req.ProfileToken = self._profile_token
                req.Velocity = {"PanTilt": {"x": 0, "y": -speed}, "Zoom": {"x": 0}}
                self._ptz.ContinuousMove(req)
            elif command == "zoom_in":
                req = self._ptz.create_type("ContinuousMove")
                req.ProfileToken = self._profile_token
                req.Velocity = {"PanTilt": {"x": 0, "y": 0}, "Zoom": {"x": speed}}
                self._ptz.ContinuousMove(req)
            elif command == "zoom_out":
                req = self._ptz.create_type("ContinuousMove")
                req.ProfileToken = self._profile_token
                req.Velocity = {"PanTilt": {"x": 0, "y": 0}, "Zoom": {"x": -speed}}
                self._ptz.ContinuousMove(req)
            elif command == "stop":
                req = self._ptz.create_type("Stop")
                req.ProfileToken = self._profile_token
                req.PanTilt = True
                req.Zoom = True
                self._ptz.Stop(req)
            elif command == "home":
                req = self._ptz.create_type("GotoHomePosition")
                req.ProfileToken = self._profile_token
                self._ptz.GotoHomePosition(req)
            elif command == "pan_tilt_absolute":
                req = self._ptz.create_type("AbsoluteMove")
                req.ProfileToken = self._profile_token
                req.Position = {
                    "PanTilt": {"x": float(params.get("pan", 0)), "y": float(params.get("tilt", 0))},
                    "Zoom": {"x": 0},
                }
                self._ptz.AbsoluteMove(req)
            elif command == "zoom_absolute":
                req = self._ptz.create_type("AbsoluteMove")
                req.ProfileToken = self._profile_token
                req.Position = {
                    "PanTilt": {"x": 0, "y": 0},
                    "Zoom": {"x": float(params.get("zoom", 0))},
                }
                self._ptz.AbsoluteMove(req)
            else:
                return False
            return True
        except Exception as exc:
            logger.error("OnvifDriver: command '%s' failed: %s", command, exc)
            return False


# ---------------------------------------------------------------------------
# PTZ Controller
# ---------------------------------------------------------------------------

class PTZController:
    """
    Dispatches PTZ commands to the correct hardware driver.

    Args:
        config:      Loaded Config object.
        mqtt_client: MQTTClient for publishing PTZ status.
    """

    def __init__(self, config: Any, mqtt_client: Any) -> None:
        self._config = config
        self._mqtt_client = mqtt_client
        self._enabled: bool = bool(config.get("ptz.enabled", False))
        self._device_id: str = config.device_id
        self._driver: Optional[BasePtzDriver] = None

        if self._enabled:
            self._driver = self._init_driver()

    def _init_driver(self) -> Optional[BasePtzDriver]:
        hw_type = self._config.get("ptz.hardware_type", "digital")
        try:
            if hw_type == "digital":
                return DigitalZoomDriver()
            elif hw_type == "visca_serial":
                port = self._config.get("ptz.serial_port", "/dev/ttyUSB0")
                baud = int(self._config.get("ptz.baudrate", 9600))
                driver = ViscaSerialDriver(port, baud)
                if driver._serial is None:
                    logger.error("PTZController: serial port unavailable — disabling PTZ for session")
                    self._enabled = False
                    return None
                return driver
            elif hw_type == "visca_ip":
                host = self._config.get("ptz.host", "")
                port = int(self._config.get("ptz.port", 52381))
                return ViscaIpDriver(host, port)
            elif hw_type == "onvif":
                host = self._config.get("ptz.host", "")
                port = int(self._config.get("ptz.port", 80))
                user = self._config.get("ptz.username", "admin")
                pwd = self._config.get("ptz.password", "")
                return OnvifDriver(host, port, user, pwd)
            elif hw_type == "arduino":
                # ArduinoDriver is optional — imported lazily
                from edge.ptz_drivers.arduino_driver import ArduinoDriver  # type: ignore
                port = self._config.get("ptz.serial_port", "/dev/ttyUSB0")
                baud = int(self._config.get("ptz.baudrate", 9600))
                return ArduinoDriver(port, baud)
            else:
                logger.warning("PTZController: unknown hardware_type '%s', using digital", hw_type)
                return DigitalZoomDriver()
        except Exception as exc:
            logger.error("PTZController: driver init failed: %s — disabling PTZ", exc)
            self._enabled = False
            return None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def handle(self, topic: str, payload_bytes: bytes) -> None:
        """
        Parse a PTZ command JSON payload and dispatch to the driver.

        Silently ignores commands when PTZ is disabled (Req 13.6).
        """
        if not self._enabled:
            return

        import json
        try:
            data = json.loads(payload_bytes.decode("utf-8"))
        except Exception as exc:
            logger.warning("PTZController: failed to parse payload: %s", exc)
            return

        command = data.get("command", "")
        params = data.get("params", {})

        if command not in VALID_COMMANDS:
            logger.warning("PTZController: unknown command '%s' — ignoring", command)
            return

        success = False
        if self._driver is not None:
            success = self._driver.execute(command, params)

        self._publish_status(command, success)

    def _publish_status(self, command: str, success: bool) -> None:
        """Publish PTZ status after each command (Req 13.7)."""
        from datetime import datetime, timezone
        status = {
            "device_id": self._device_id,
            "last_command": command,
            "success": success,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        if self._driver and isinstance(self._driver, DigitalZoomDriver):
            status["zoom_level"] = self._driver.zoom_level
            status["pan_offset"] = self._driver.pan_offset
            status["tilt_offset"] = self._driver.tilt_offset
        try:
            self._mqtt_client.publish_ptz_status(status)
        except Exception as exc:
            logger.warning("PTZController: failed to publish status: %s", exc)

    @property
    def digital_driver(self) -> Optional[DigitalZoomDriver]:
        """Return the DigitalZoomDriver if active, else None."""
        if isinstance(self._driver, DigitalZoomDriver):
            return self._driver
        return None
