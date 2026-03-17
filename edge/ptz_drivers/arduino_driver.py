"""
Arduino PTZ driver (optional).

Translates PTZ commands to a simple serial text protocol:
  PAN:<angle>\\n
  TILT:<angle>\\n
  ZOOM:<level>\\n
  HOME\\n
  STOP\\n

Logs error and disables PTZ if serial port is unavailable.

Requirements: 16.1, 16.2, 16.3, 16.5
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)


class ArduinoDriver:
    """
    PTZ driver for an Arduino-based camera mount over serial.

    Args:
        port:     Serial port path (e.g. /dev/ttyUSB0).
        baudrate: Serial baud rate (default 9600).
    """

    def __init__(self, port: str, baudrate: int = 9600) -> None:
        self._port = port
        self._baudrate = baudrate
        self._serial = None
        self._enabled = True
        self._connect()

    def _connect(self) -> None:
        try:
            import serial  # type: ignore
            self._serial = serial.Serial(self._port, self._baudrate, timeout=1)
            logger.info("ArduinoDriver: opened %s at %d baud", self._port, self._baudrate)
        except Exception as exc:
            logger.error(
                "ArduinoDriver: cannot open %s: %s — disabling PTZ for session",
                self._port,
                exc,
            )
            self._serial = None
            self._enabled = False

    def _send(self, command_str: str) -> bool:
        if self._serial is None:
            return False
        try:
            self._serial.write((command_str + "\n").encode("ascii"))
            return True
        except Exception as exc:
            logger.error("ArduinoDriver: write error: %s", exc)
            return False

    def execute(self, command: str, params: dict) -> bool:
        """
        Translate a PTZ command to the Arduino serial protocol.

        Returns True on success, False if serial is unavailable.
        """
        if not self._enabled or self._serial is None:
            return False

        if command == "pan_left":
            angle = -abs(float(params.get("angle", 10)))
            return self._send(f"PAN:{angle:.1f}")
        elif command == "pan_right":
            angle = abs(float(params.get("angle", 10)))
            return self._send(f"PAN:{angle:.1f}")
        elif command == "tilt_up":
            angle = abs(float(params.get("angle", 10)))
            return self._send(f"TILT:{angle:.1f}")
        elif command == "tilt_down":
            angle = -abs(float(params.get("angle", 10)))
            return self._send(f"TILT:{angle:.1f}")
        elif command == "pan_tilt_absolute":
            pan = float(params.get("pan", 0))
            tilt = float(params.get("tilt", 0))
            ok = self._send(f"PAN:{pan:.1f}")
            return ok and self._send(f"TILT:{tilt:.1f}")
        elif command == "zoom_in":
            level = float(params.get("level", 1))
            return self._send(f"ZOOM:{level:.1f}")
        elif command == "zoom_out":
            level = float(params.get("level", -1))
            return self._send(f"ZOOM:{level:.1f}")
        elif command == "zoom_absolute":
            level = float(params.get("zoom", 1.0))
            return self._send(f"ZOOM:{level:.1f}")
        elif command == "stop":
            return self._send("STOP")
        elif command == "home":
            return self._send("HOME")
        else:
            logger.warning("ArduinoDriver: unknown command '%s'", command)
            return False
