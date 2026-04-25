"""
Edge device — MQTT log publisher.

MQTTLogHandler: a logging.Handler subclass that publishes WARNING+ log
records to uav/log/{device_id} as structured JSON Log_Entry messages.

Log_Entry fields: timestamp, level, logger, message, device_id

Requirements: v2-7.1, v2-7.2, v2-7.3
"""

import json
import logging
from datetime import datetime, timezone
from typing import Any


class MQTTLogHandler(logging.Handler):
    """
    Publishes WARNING-level and above log records to MQTT.

    Args:
        mqtt_client: MQTTClient instance with publish_log() method.
        device_id:   Edge device identifier.
    """

    def __init__(self, mqtt_client: Any, device_id: str) -> None:
        super().__init__(level=logging.WARNING)
        self._mqtt_client = mqtt_client
        self._device_id = device_id

    def emit(self, record: logging.LogRecord) -> None:
        try:
            entry = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "level": record.levelname,
                "logger": record.name,
                "message": self.format(record),
                "device_id": self._device_id,
            }
            payload = json.dumps(entry, ensure_ascii=False).encode("utf-8")
            self._mqtt_client.publish_log(payload)
        except Exception:
            self.handleError(record)
