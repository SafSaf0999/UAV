"""
Aggregation service — detections database.

aiosqlite wrapper for detections.db.
Stores per-device detection events for historical export.

Requirements: 5.1, 5.2, 5.3, 5.4, 5.5
"""

import csv
import io
import logging
import os

import aiosqlite

logger = logging.getLogger(__name__)

DB_PATH = os.environ.get("DETECTIONS_DB_PATH", "/app/data/detections.db")

_CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS detections (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    device_id TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    label TEXT NOT NULL,
    confidence REAL NOT NULL,
    bbox_x REAL NOT NULL,
    bbox_y REAL NOT NULL,
    bbox_w REAL NOT NULL,
    bbox_h REAL NOT NULL,
    track_id INTEGER
);
"""

_CREATE_INDEX = """
CREATE INDEX IF NOT EXISTS idx_detections_device_ts
    ON detections (device_id, timestamp);
"""


async def init_detections_db() -> None:
    """Create detections table and index if they don't exist."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(_CREATE_TABLE)
        await db.execute(_CREATE_INDEX)
        await db.commit()
    logger.info("detections_db: initialized at %s", DB_PATH)


async def insert_detections(device_id: str, timestamp: str, detections_list: list) -> None:
    """
    Insert a list of detection dicts for a given device and timestamp.

    Each detection dict should have: label, confidence, bbox (list of [x, y, w, h]),
    and optionally track_id.
    """
    if not detections_list:
        return
    rows = []
    for det in detections_list:
        bbox = det.get("bbox") or [0.0, 0.0, 0.0, 0.0]
        if isinstance(bbox, (list, tuple)) and len(bbox) >= 4:
            bx, by, bw, bh = float(bbox[0]), float(bbox[1]), float(bbox[2]), float(bbox[3])
        else:
            bx, by, bw, bh = 0.0, 0.0, 0.0, 0.0
        rows.append((
            device_id,
            timestamp,
            det.get("label", "unknown"),
            float(det.get("confidence", 0.0)),
            bx, by, bw, bh,
            det.get("track_id"),
        ))
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executemany(
            "INSERT INTO detections "
            "(device_id, timestamp, label, confidence, bbox_x, bbox_y, bbox_w, bbox_h, track_id) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            rows,
        )
        await db.commit()


async def export_detections_csv(
    device_id: str,
    from_ts: str,
    to_ts: str,
) -> str:
    """
    Export detections for a device within [from_ts, to_ts] as a CSV string.

    Returns a CSV string with columns:
    id, device_id, timestamp, label, confidence, bbox_x, bbox_y, bbox_w, bbox_h, track_id
    """
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT id, device_id, timestamp, label, confidence, "
            "bbox_x, bbox_y, bbox_w, bbox_h, track_id "
            "FROM detections "
            "WHERE device_id = ? AND timestamp >= ? AND timestamp <= ? "
            "ORDER BY timestamp ASC",
            (device_id, from_ts, to_ts),
        )
        rows = await cursor.fetchall()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["id", "device_id", "timestamp", "label", "confidence",
                     "bbox_x", "bbox_y", "bbox_w", "bbox_h", "track_id"])
    for row in rows:
        writer.writerow([
            row["id"], row["device_id"], row["timestamp"], row["label"],
            row["confidence"], row["bbox_x"], row["bbox_y"], row["bbox_w"],
            row["bbox_h"], row["track_id"],
        ])
    return output.getvalue()
