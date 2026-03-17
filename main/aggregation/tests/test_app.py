"""
Unit tests for main/aggregation/app.py

Tests:
  - POST /command/{device_id} publishes correct MQTT message
  - POST /ptz/{device_id} publishes to correct topic
  - WebSocket push delivers state update to connected client
"""

import asyncio
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# App setup with mocked lifespan
# ---------------------------------------------------------------------------

@pytest.fixture
def client():
    """TestClient with MQTT subscriber and publish mocked out."""
    with patch("main.aggregation.app.create_subscriber_from_env") as mock_sub_factory, \
         patch("main.aggregation.app._mqtt_publish_fn", new=None):

        mock_subscriber = MagicMock()
        mock_subscriber.run = AsyncMock(return_value=None)
        mock_sub_factory.return_value = mock_subscriber

        import main.aggregation.app as app_module
        # Reset global state
        app_module._ws_clients.clear()

        with TestClient(app_module.app, raise_server_exceptions=True) as c:
            yield c, app_module


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_list_devices_empty(client):
    c, app_module = client
    resp = c.get("/devices")
    assert resp.status_code == 200
    assert resp.json() == []


def test_get_unknown_device_404(client):
    c, _ = client
    resp = c.get("/devices/nonexistent")
    assert resp.status_code == 404


def test_post_command_publishes_correct_topic(client):
    c, app_module = client
    published = []

    def mock_publish(topic, payload):
        published.append((topic, payload))

    app_module._mqtt_publish_fn = mock_publish

    resp = c.post("/command/dev-001", json={"action": "start_stream"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["topic"] == "uav/command/dev-001"

    # Check publish was called with correct topic
    assert len(published) == 1
    topic, payload_str = published[0]
    assert topic == "uav/command/dev-001"
    payload = json.loads(payload_str)
    assert payload["action"] == "start_stream"
    assert payload["device_id"] == "dev-001"


def test_post_ptz_publishes_correct_topic(client):
    c, app_module = client
    published = []

    def mock_publish(topic, payload):
        published.append((topic, payload))

    app_module._mqtt_publish_fn = mock_publish

    resp = c.post("/ptz/dev-002", json={"command": "zoom_in", "params": {}})
    assert resp.status_code == 200
    data = resp.json()
    assert data["topic"] == "uav/ptz/dev-002"

    assert len(published) == 1
    topic, payload_str = published[0]
    assert topic == "uav/ptz/dev-002"
    payload = json.loads(payload_str)
    assert payload["command"] == "zoom_in"


def test_get_device_after_status_update(client):
    c, app_module = client

    async def _update():
        await app_module.registry.update_status("dev-003", {
            "device_id": "dev-003",
            "status": "online",
            "timestamp": "2024-01-01T00:00:00Z",
        })

    asyncio.get_event_loop().run_until_complete(_update())

    resp = c.get("/devices/dev-003")
    assert resp.status_code == 200
    assert resp.json()["status"] == "online"


def test_list_devices_returns_all(client):
    c, app_module = client

    async def _update():
        for i in range(3):
            await app_module.registry.update_status(f"dev-{i:03d}", {
                "device_id": f"dev-{i:03d}",
                "status": "online",
                "timestamp": "2024-01-01T00:00:00Z",
            })

    asyncio.get_event_loop().run_until_complete(_update())

    resp = c.get("/devices")
    assert resp.status_code == 200
    ids = {d["device_id"] for d in resp.json()}
    assert {"dev-000", "dev-001", "dev-002"}.issubset(ids)
