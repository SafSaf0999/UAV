"""
Aggregation service — webhook dispatcher.

Fire-and-forget async webhook delivery with HMAC-SHA256 signing.
Loads webhook configs from the control-center API or directly from
auth.db (when WEBHOOKS_DB_PATH env var is set).

Requirements: 8.1, 8.2, 8.3, 8.4, 8.5, 8.6
"""

import asyncio
import hashlib
import hmac
import json
import logging
import os
from datetime import datetime, timezone
from typing import List, Optional

logger = logging.getLogger(__name__)

WEBHOOKS_DB_PATH = os.environ.get("WEBHOOKS_DB_PATH", "")
CONTROL_CENTER_URL = os.environ.get("CONTROL_CENTER_URL", "http://control-center:8000")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _compute_signature(body_bytes: bytes, secret: str) -> str:
    """Compute HMAC-SHA256 hex digest of body_bytes using secret."""
    mac = hmac.new(secret.encode("utf-8"), body_bytes, hashlib.sha256)
    return "hmac-sha256=" + mac.hexdigest()


class WebhookDispatcher:
    """
    Async webhook dispatcher.

    Loads webhook configs on first dispatch (lazy) and delivers events
    as fire-and-forget asyncio tasks.
    """

    def __init__(self) -> None:
        self._webhooks: Optional[List[dict]] = None

    async def load_webhooks(self) -> List[dict]:
        """
        Load webhooks from auth.db (if WEBHOOKS_DB_PATH set) or control-center API.

        Returns list of dicts with keys: id, url, events (list), secret, enabled.
        """
        if WEBHOOKS_DB_PATH:
            return await self._load_from_db()
        return await self._load_from_api()

    async def _load_from_db(self) -> List[dict]:
        """Read webhooks directly from auth.db using aiosqlite."""
        try:
            import aiosqlite
            async with aiosqlite.connect(WEBHOOKS_DB_PATH) as db:
                db.row_factory = aiosqlite.Row
                cursor = await db.execute(
                    "SELECT id, url, events, secret, enabled FROM webhooks WHERE enabled = 1"
                )
                rows = await cursor.fetchall()
            result = []
            for row in rows:
                result.append({
                    "id": row["id"],
                    "url": row["url"],
                    "events": [e.strip() for e in row["events"].split(",") if e.strip()],
                    "secret": row["secret"] or "",
                    "enabled": bool(row["enabled"]),
                })
            return result
        except Exception as exc:
            logger.warning("webhook_dispatcher: failed to load from DB: %s", exc)
            return []

    async def _load_from_api(self) -> List[dict]:
        """Fetch webhooks from control-center /api/webhooks endpoint."""
        try:
            import httpx
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(f"{CONTROL_CENTER_URL}/api/webhooks")
            if resp.status_code == 200:
                data = resp.json()
                result = []
                for wh in data:
                    events = wh.get("events", "")
                    if isinstance(events, str):
                        events = [e.strip() for e in events.split(",") if e.strip()]
                    result.append({
                        "id": wh.get("id"),
                        "url": wh.get("url", ""),
                        "events": events,
                        "secret": wh.get("secret", ""),
                        "enabled": bool(wh.get("enabled", True)),
                    })
                return result
        except Exception as exc:
            logger.warning("webhook_dispatcher: failed to load from API: %s", exc)
        return []

    def dispatch(self, event: str, device_id: str, data: dict) -> None:
        """
        Fire-and-forget dispatch of a webhook event.

        Creates an asyncio task; does not block the caller.
        """
        asyncio.create_task(self._dispatch_async(event, device_id, data))

    async def _dispatch_async(self, event: str, device_id: str, data: dict) -> None:
        """Reload webhooks and deliver to all matching endpoints."""
        try:
            webhooks = await self.load_webhooks()
        except Exception as exc:
            logger.warning("webhook_dispatcher: load failed: %s", exc)
            return

        payload = {
            "event": event,
            "device_id": device_id,
            "timestamp": _now_iso(),
            "data": data,
        }
        body_bytes = json.dumps(payload, separators=(",", ":")).encode("utf-8")

        import httpx
        for wh in webhooks:
            if not wh.get("enabled", True):
                continue
            if event not in wh.get("events", []):
                continue
            asyncio.create_task(self._deliver(wh, body_bytes))

    async def _deliver(self, webhook: dict, body_bytes: bytes) -> None:
        """Deliver a single webhook POST. Logs on failure, no retry."""
        url = webhook.get("url", "")
        secret = webhook.get("secret", "")
        headers = {"Content-Type": "application/json"}
        if secret:
            headers["X-UAV-Signature"] = _compute_signature(body_bytes, secret)
        try:
            import httpx
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.post(url, content=body_bytes, headers=headers)
            if resp.status_code < 200 or resp.status_code >= 300:
                logger.warning(
                    "webhook_dispatcher: non-2xx from %s (event=%s): %d",
                    url, webhook.get("id"), resp.status_code,
                )
        except Exception as exc:
            logger.warning("webhook_dispatcher: delivery failed to %s: %s", url, exc)


# Singleton instance
_dispatcher = WebhookDispatcher()


def get_webhook_dispatcher() -> WebhookDispatcher:
    """Return the singleton WebhookDispatcher."""
    return _dispatcher
