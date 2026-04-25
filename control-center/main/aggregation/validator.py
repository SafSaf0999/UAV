"""
Aggregation service — JSON schema validator.

Loads tracking_payload.schema.json and validates incoming payloads.
Rejects payloads with confidence values outside [0.0, 1.0].

Requirements: 4.4, 9.2, 9.4
"""

import json
import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

# Path to the shared schema file
_SCHEMA_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..", "shared", "schemas", "tracking_payload.schema.json"
)


def _load_schema() -> dict:
    path = os.path.abspath(_SCHEMA_PATH)
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


# Load schema once at module import
try:
    _SCHEMA = _load_schema()
except Exception as exc:  # pragma: no cover
    logger.warning("validator: could not load schema: %s — validation disabled", exc)
    _SCHEMA = None


def validate_payload(data: Any) -> bool:
    """
    Validate a tracking payload dict against the JSON schema.

    Also rejects any detection with confidence outside [0.0, 1.0].

    Args:
        data: Parsed payload dict (already deserialized from JSON).

    Returns:
        True if valid, False otherwise.
    """
    if not isinstance(data, dict):
        logger.warning("validator: payload is not a dict")
        return False

    # JSON Schema validation
    if _SCHEMA is not None:
        try:
            import jsonschema  # type: ignore
            jsonschema.validate(instance=data, schema=_SCHEMA)
        except jsonschema.ValidationError as exc:
            device_id = data.get("device_id", "<unknown>")
            logger.warning(
                "validator: schema validation failed for device '%s': %s",
                device_id,
                exc.message,
            )
            return False
        except Exception as exc:
            logger.warning("validator: unexpected validation error: %s", exc)
            return False

    # Extra: confidence range check
    for detection in data.get("detections", []):
        conf = detection.get("confidence")
        if conf is not None and not (0.0 <= float(conf) <= 1.0):
            device_id = data.get("device_id", "<unknown>")
            logger.warning(
                "validator: confidence %.4f out of [0.0, 1.0] for device '%s'",
                conf,
                device_id,
            )
            return False

    return True
