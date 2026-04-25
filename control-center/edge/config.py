"""
Edge device configuration loader.

Loads config.yaml from the path specified by the EDGE_CONFIG environment
variable, or defaults to ./config.yaml. Validates required fields and exits
with code 1 if any are missing.
"""

import logging
import os
import sys
from dataclasses import dataclass, field
from typing import Any

import yaml

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

REQUIRED_FIELDS = [
    "device_id",
    "mqtt.host",
    "mqtt.port",
    "camera.source",
    "active_model",
]


@dataclass
class Config:
    """Parsed and validated edge device configuration."""

    raw: dict = field(repr=False)

    # Convenience accessors for required fields
    device_id: str = ""
    active_model: str = ""

    def __post_init__(self) -> None:
        self.device_id = self.raw["device_id"]
        self.active_model = self.raw["active_model"]

    def get(self, key: str, default: Any = None) -> Any:
        """Dot-notation access into the raw config dict."""
        parts = key.split(".")
        node = self.raw
        for part in parts:
            if not isinstance(node, dict) or part not in node:
                return default
            node = node[part]
        return node


def _get_nested(data: dict, dotted_key: str) -> tuple[bool, Any]:
    """Return (found, value) for a dot-notation key in a nested dict."""
    parts = dotted_key.split(".")
    node = data
    for part in parts:
        if not isinstance(node, dict) or part not in node:
            return False, None
        node = node[part]
    return True, node


def _validate(data: dict) -> None:
    """Validate required fields; exit with code 1 on the first missing field."""
    for field_path in REQUIRED_FIELDS:
        found, _ = _get_nested(data, field_path)
        if not found:
            logger.error("Missing required config field: %s", field_path)
            sys.exit(1)

    # Validate active_model matches one of the model_profiles names (if present)
    profiles = data.get("model_profiles")
    if profiles is not None:
        profile_names = {p["name"] for p in profiles if isinstance(p, dict) and "name" in p}
        active = data.get("active_model", "")
        if active not in profile_names:
            logger.error(
                "active_model '%s' does not match any model_profiles name: %s",
                active,
                sorted(profile_names),
            )
            sys.exit(1)


def load_config(path: str | None = None) -> Config:
    """
    Load and validate the edge device configuration.

    Args:
        path: Optional explicit path to the YAML config file.
              Falls back to the EDGE_CONFIG env var, then ./config.yaml.

    Returns:
        A validated Config object.
    """
    if path is None:
        path = os.environ.get("EDGE_CONFIG", "./config.yaml")

    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = yaml.safe_load(fh)
    except FileNotFoundError:
        logger.error("Config file not found: %s", path)
        sys.exit(1)
    except yaml.YAMLError as exc:
        logger.error("Failed to parse config file %s: %s", path, exc)
        sys.exit(1)

    if not isinstance(data, dict):
        logger.error("Config file %s does not contain a YAML mapping", path)
        sys.exit(1)

    _validate(data)

    # Warn when mqtt.username is absent — unauthenticated connections are not recommended
    found_username, _ = _get_nested(data, "mqtt.username")
    if not found_username:
        logger.warning(
            "MQTT: no username configured — connecting unauthenticated (not recommended)"
        )

    return Config(raw=data)
