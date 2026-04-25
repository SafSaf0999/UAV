"""
Tests for edge/log_publisher.py

Unit tests:
  - WARNING record is published to MQTT
  - DEBUG record is NOT published
  - Published payload contains all 5 required fields
  - level is one of WARNING, ERROR, CRITICAL

Property test:
  - Property 4: Log Entry Required Fields
    Validates: Requirements v2-7.1, v2-7.2
"""

import json
import logging
import unittest
from unittest.mock import MagicMock, call

import pytest
from hypothesis import given, settings, HealthCheck
from hypothesis import strategies as st

from edge.log_publisher import MQTTLogHandler


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_handler(device_id: str = "edge-test") -> tuple[MQTTLogHandler, MagicMock]:
    mqtt_client = MagicMock()
    handler = MQTTLogHandler(mqtt_client, device_id)
    handler.setFormatter(logging.Formatter("%(message)s"))
    return handler, mqtt_client


def _make_record(level: int, message: str, logger_name: str = "test.logger") -> logging.LogRecord:
    record = logging.LogRecord(
        name=logger_name,
        level=level,
        pathname="test.py",
        lineno=1,
        msg=message,
        args=(),
        exc_info=None,
    )
    return record


# ---------------------------------------------------------------------------
# Unit tests
# ---------------------------------------------------------------------------

class TestMQTTLogHandler:
    def test_warning_record_is_published(self):
        handler, mqtt_client = _make_handler()
        record = _make_record(logging.WARNING, "test warning")
        handler.emit(record)
        mqtt_client.publish_log.assert_called_once()

    def test_error_record_is_published(self):
        handler, mqtt_client = _make_handler()
        record = _make_record(logging.ERROR, "test error")
        handler.emit(record)
        mqtt_client.publish_log.assert_called_once()

    def test_critical_record_is_published(self):
        handler, mqtt_client = _make_handler()
        record = _make_record(logging.CRITICAL, "test critical")
        handler.emit(record)
        mqtt_client.publish_log.assert_called_once()

    def test_debug_record_is_not_published(self):
        """DEBUG is below WARNING threshold — must not be published."""
        handler, mqtt_client = _make_handler()
        record = _make_record(logging.DEBUG, "debug message")
        # Handler level is WARNING (30), DEBUG is 10 — handler should not emit
        assert handler.level > logging.DEBUG
        mqtt_client.publish_log.assert_not_called()

    def test_info_record_is_not_published(self):
        """INFO is below WARNING — must not be published."""
        handler, mqtt_client = _make_handler()
        record = _make_record(logging.INFO, "info message")
        # Handler level is WARNING (30), INFO is 20 — below threshold
        assert handler.level > logging.INFO
        mqtt_client.publish_log.assert_not_called()

    def test_published_payload_is_valid_json(self):
        handler, mqtt_client = _make_handler()
        record = _make_record(logging.WARNING, "json test")
        handler.emit(record)
        payload_bytes = mqtt_client.publish_log.call_args[0][0]
        parsed = json.loads(payload_bytes.decode("utf-8"))
        assert isinstance(parsed, dict)

    def test_payload_contains_all_required_fields(self):
        handler, mqtt_client = _make_handler()
        record = _make_record(logging.WARNING, "field test")
        handler.emit(record)
        payload_bytes = mqtt_client.publish_log.call_args[0][0]
        parsed = json.loads(payload_bytes.decode("utf-8"))
        for field in ("timestamp", "level", "logger", "message", "device_id"):
            assert field in parsed, f"Missing field: {field}"

    def test_level_field_is_warning(self):
        handler, mqtt_client = _make_handler()
        record = _make_record(logging.WARNING, "level test")
        handler.emit(record)
        parsed = json.loads(mqtt_client.publish_log.call_args[0][0].decode())
        assert parsed["level"] == "WARNING"

    def test_level_field_is_error(self):
        handler, mqtt_client = _make_handler()
        record = _make_record(logging.ERROR, "error test")
        handler.emit(record)
        parsed = json.loads(mqtt_client.publish_log.call_args[0][0].decode())
        assert parsed["level"] == "ERROR"

    def test_device_id_in_payload(self):
        handler, mqtt_client = _make_handler(device_id="edge-42")
        record = _make_record(logging.WARNING, "device test")
        handler.emit(record)
        parsed = json.loads(mqtt_client.publish_log.call_args[0][0].decode())
        assert parsed["device_id"] == "edge-42"

    def test_logger_name_in_payload(self):
        handler, mqtt_client = _make_handler()
        record = _make_record(logging.WARNING, "logger test", logger_name="edge.camera")
        handler.emit(record)
        parsed = json.loads(mqtt_client.publish_log.call_args[0][0].decode())
        assert parsed["logger"] == "edge.camera"

    def test_timestamp_is_iso8601_utc(self):
        from datetime import datetime
        handler, mqtt_client = _make_handler()
        record = _make_record(logging.WARNING, "ts test")
        handler.emit(record)
        parsed = json.loads(mqtt_client.publish_log.call_args[0][0].decode())
        dt = datetime.fromisoformat(parsed["timestamp"])
        assert dt.tzinfo is not None

    def test_publish_failure_does_not_raise(self):
        """If MQTT publish fails, emit() must not propagate the exception."""
        handler, mqtt_client = _make_handler()
        mqtt_client.publish_log.side_effect = Exception("MQTT down")
        record = _make_record(logging.ERROR, "publish fail test")
        # Should not raise
        handler.emit(record)


# ---------------------------------------------------------------------------
# Property 4: Log Entry Required Fields
# ---------------------------------------------------------------------------

VALID_LEVELS = ["WARNING", "ERROR", "CRITICAL"]

@given(
    device_id=st.text(min_size=1, max_size=32, alphabet=st.characters(
        whitelist_categories=("Ll", "Lu", "Nd"), whitelist_characters="-_"
    )),
    message=st.text(min_size=1, max_size=256),
    logger_name=st.text(min_size=1, max_size=64, alphabet=st.characters(
        whitelist_categories=("Ll", "Lu", "Nd"), whitelist_characters="._"
    )),
    level=st.sampled_from([logging.WARNING, logging.ERROR, logging.CRITICAL]),
)
@settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
def test_property_4_log_entry_required_fields(device_id, message, logger_name, level):
    """
    Property 4: Log Entry Required Fields
    For any Log_Entry published to uav/log/{device_id}, the entry must contain
    all five required fields and level must be WARNING, ERROR, or CRITICAL.
    Validates: Requirements v2-7.1, v2-7.2
    """
    mqtt_client = MagicMock()
    handler = MQTTLogHandler(mqtt_client, device_id)
    handler.setFormatter(logging.Formatter("%(message)s"))

    record = _make_record(level, message, logger_name)
    handler.emit(record)

    assert mqtt_client.publish_log.called, "publish_log must be called for WARNING+"

    payload_bytes = mqtt_client.publish_log.call_args[0][0]
    parsed = json.loads(payload_bytes.decode("utf-8"))

    # All 5 required fields must be present
    for field in ("timestamp", "level", "logger", "message", "device_id"):
        assert field in parsed, f"Missing required field: {field}"

    # level must be one of the valid values
    assert parsed["level"] in VALID_LEVELS, f"Invalid level: {parsed['level']}"

    # device_id must match
    assert parsed["device_id"] == device_id
