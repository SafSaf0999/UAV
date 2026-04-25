"""
Unit tests for main/control-center/app.py

Tests:
  - Token auth rejects requests without valid token in HTTPS mode
  - Startup warning is logged when REMOTE_ACCESS_MODE=https
  - Static file serving returns 200 for index.html
"""

import os
import logging
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_app_module():
    """Load the control-center app module (handles hyphenated directory name)."""
    import importlib.util
    import sys
    spec = importlib.util.spec_from_file_location(
        "control_center_app",
        os.path.join(os.path.dirname(__file__), "..", "app.py"),
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules["control_center_app"] = module
    spec.loader.exec_module(module)
    return module


# ---------------------------------------------------------------------------
# Auth tests
# ---------------------------------------------------------------------------

def test_https_mode_rejects_missing_token():
    with patch.dict(os.environ, {"REMOTE_ACCESS_MODE": "https", "HTTPS_TOKEN": "secret"}):
        app_module = _load_app_module()
        client = TestClient(app_module.app, raise_server_exceptions=False)
        with patch.object(app_module, "DIST_DIR", Path("/nonexistent")):
            resp = client.get("/api/devices")
        assert resp.status_code == 401


def test_https_mode_accepts_valid_token():
    with patch.dict(os.environ, {"REMOTE_ACCESS_MODE": "https", "HTTPS_TOKEN": "secret"}):
        app_module = _load_app_module()
        client = TestClient(app_module.app, raise_server_exceptions=False)

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_resp = MagicMock()
            mock_resp.json.return_value = []
            mock_resp.status_code = 200
            mock_instance = AsyncMock()
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=False)
            mock_instance.get = AsyncMock(return_value=mock_resp)
            mock_client_cls.return_value = mock_instance

            resp = client.get("/api/devices", headers={"Authorization": "Bearer secret"})
        assert resp.status_code == 200


def test_vpn_mode_no_auth_required():
    with patch.dict(os.environ, {"REMOTE_ACCESS_MODE": "vpn", "HTTPS_TOKEN": ""}):
        app_module = _load_app_module()
        client = TestClient(app_module.app, raise_server_exceptions=False)

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_resp = MagicMock()
            mock_resp.json.return_value = []
            mock_resp.status_code = 200
            mock_instance = AsyncMock()
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=False)
            mock_instance.get = AsyncMock(return_value=mock_resp)
            mock_client_cls.return_value = mock_instance

            resp = client.get("/api/devices")
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Startup warning test
# ---------------------------------------------------------------------------

def test_startup_warning_logged_in_https_mode(caplog):
    with patch.dict(os.environ, {"REMOTE_ACCESS_MODE": "https", "HTTPS_TOKEN": "tok"}):
        app_module = _load_app_module()
        client = TestClient(app_module.app, raise_server_exceptions=False)

        with caplog.at_level(logging.WARNING):
            with client:
                pass  # triggers startup

        warning_msgs = [r.message for r in caplog.records if r.levelno == logging.WARNING]
        assert any("non-VPN" in m or "https" in m.lower() for m in warning_msgs)


# ---------------------------------------------------------------------------
# Static file serving
# ---------------------------------------------------------------------------

def test_static_index_html_served(tmp_path):
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text("<html><body>UAV Control</body></html>")

    with patch.dict(os.environ, {"REMOTE_ACCESS_MODE": "vpn"}):
        app_module = _load_app_module()
        with patch.object(app_module, "DIST_DIR", dist):
            client = TestClient(app_module.app, raise_server_exceptions=False)
            resp = client.get("/")
        assert resp.status_code == 200
        assert "UAV Control" in resp.text


def test_missing_dist_returns_503():
    with patch.dict(os.environ, {"REMOTE_ACCESS_MODE": "vpn"}):
        app_module = _load_app_module()
        with patch.object(app_module, "DIST_DIR", Path("/nonexistent/dist")):
            client = TestClient(app_module.app, raise_server_exceptions=False)
            resp = client.get("/")
        assert resp.status_code == 503
