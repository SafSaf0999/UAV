"""
Aggregation service — per-device alert thresholds.

ThresholdConfig dataclass and ThresholdStore for loading/saving
threshold configs to /app/data/thresholds.json.

Requirements: 6.1, 6.2, 6.3, 6.4
"""

import json
import logging
import os
from dataclasses import dataclass, field, asdict
from typing import List, Optional

logger = logging.getLogger(__name__)

THRESHOLDS_PATH = os.environ.get("THRESHOLDS_PATH", "/app/data/thresholds.json")


@dataclass
class ThresholdConfig:
    """Per-device alert threshold configuration."""

    device_id: str
    min_confidence: float = 0.5
    consecutive_frames: int = 1
    alert_classes: List[str] = field(default_factory=lambda: ["drone"])

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "ThresholdConfig":
        return cls(
            device_id=data["device_id"],
            min_confidence=float(data.get("min_confidence", 0.5)),
            consecutive_frames=int(data.get("consecutive_frames", 1)),
            alert_classes=list(data.get("alert_classes", ["drone"])),
        )


class ThresholdStore:
    """
    In-memory store for per-device threshold configs, persisted to JSON.

    Loads from THRESHOLDS_PATH on first access; saves on every set().
    """

    def __init__(self, path: str = THRESHOLDS_PATH) -> None:
        self._path = path
        self._configs: dict[str, ThresholdConfig] = {}
        self._loaded = False

    def _load(self) -> None:
        if self._loaded:
            return
        self._loaded = True
        if not os.path.exists(self._path):
            return
        try:
            with open(self._path, "r", encoding="utf-8") as f:
                data = json.load(f)
            for entry in data:
                cfg = ThresholdConfig.from_dict(entry)
                self._configs[cfg.device_id] = cfg
            logger.info("thresholds: loaded %d configs from %s", len(self._configs), self._path)
        except Exception as exc:
            logger.warning("thresholds: failed to load %s: %s", self._path, exc)

    def _save(self) -> None:
        try:
            os.makedirs(os.path.dirname(self._path), exist_ok=True)
            with open(self._path, "w", encoding="utf-8") as f:
                json.dump([cfg.to_dict() for cfg in self._configs.values()], f, indent=2)
        except Exception as exc:
            logger.warning("thresholds: failed to save %s: %s", self._path, exc)

    def get(self, device_id: str) -> ThresholdConfig:
        """Return threshold config for device_id, creating default if absent."""
        self._load()
        if device_id not in self._configs:
            self._configs[device_id] = ThresholdConfig(device_id=device_id)
        return self._configs[device_id]

    def set(self, device_id: str, config: ThresholdConfig) -> None:
        """Update threshold config for device_id and persist to JSON."""
        self._load()
        self._configs[device_id] = config
        self._save()


# Singleton instance
_store = ThresholdStore()


def get_threshold_store() -> ThresholdStore:
    """Return the singleton ThresholdStore."""
    return _store
