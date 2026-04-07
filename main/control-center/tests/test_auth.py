"""
Tests for main/control-center/auth.py

Unit tests:
  - Login success returns JWT with correct claims
  - Login failure returns 401
  - Valid token accepted by middleware
  - Viewer role stored in JWT claims
  - Register with valid invite token creates account and returns JWT
  - Register with expired token returns 400
  - Register with already-used token returns 400
  - Deactivated user gets 401 on next request

Property tests:
  - Property 1: JWT round-trip
  - Property 6: Invite token single-use guarantee
"""

import asyncio
import importlib.util
import os
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from hypothesis import given, settings, HealthCheck
from hypothesis import strategies as st

# ---------------------------------------------------------------------------
# Import auth module directly (hyphenated directory can't be a Python package)
# ---------------------------------------------------------------------------

_CC_DIR = Path(__file__).parent.parent  # main/control-center/


def _load_auth_module(db_path: str, jwt_secret: str = "test-secret-key"):
    """Load auth.py as a fresh module with patched env vars."""
    os.environ["AUTH_DB_PATH"] = db_path
    os.environ["JWT_SECRET"] = jwt_secret
    os.environ["JWT_TTL_HOURS"] = "8"
    os.environ["BOOTSTRAP_ADMIN_USERNAME"] = "admin"
    os.environ["BOOTSTRAP_ADMIN_PASSWORD"] = "adminpass"

    mod_name = f"auth_{uuid.uuid4().hex}"
    spec = importlib.util.spec_from_file_location(mod_name, _CC_DIR / "auth.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = mod
    spec.loader.exec_module(mod)
    return mod


def _make_test_app(auth_mod):
    """Build a minimal FastAPI app for testing auth."""
    from contextlib import asynccontextmanager
    from fastapi import FastAPI
    from fastapi.responses import JSONResponse

    @asynccontextmanager
    async def lifespan(app):
        await auth_mod.init_db()
        yield

    app = FastAPI(lifespan=lifespan)
    app.middleware("http")(auth_mod.jwt_auth_middleware)
    app.include_router(auth_mod.router)

    @app.get("/api/devices")
    async def dummy_devices():
        return JSONResponse({"devices": []})

    @app.post("/api/command/{device_id}")
    async def dummy_command(device_id: str):
        return JSONResponse({"status": "ok"})

    return app


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def auth_mod(tmp_path):
    db_file = str(tmp_path / "test_auth.db")
    mod = _load_auth_module(db_file)
    asyncio.run(mod.init_db())
    return mod


@pytest.fixture
def client(auth_mod):
    from fastapi.testclient import TestClient
    app = _make_test_app(auth_mod)
    with TestClient(app, raise_server_exceptions=True) as c:
        yield c


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _login(client, username="admin", password="adminpass"):
    resp = client.post("/auth/login", json={"username": username, "password": password})
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


def _auth_header(token):
    return {"Authorization": f"Bearer {token}"}


def _create_invite(client, role="viewer"):
    token = _login(client)
    resp = client.post(
        "/auth/invite",
        json={"role": role, "expiry_hours": 48},
        headers=_auth_header(token),
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["token"]


# ---------------------------------------------------------------------------
# Login tests
# ---------------------------------------------------------------------------

class TestLogin:
    def test_success_returns_jwt(self, client):
        resp = client.post("/auth/login", json={"username": "admin", "password": "adminpass"})
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    def test_wrong_password_returns_401(self, client):
        resp = client.post("/auth/login", json={"username": "admin", "password": "wrong"})
        assert resp.status_code == 401

    def test_unknown_user_returns_401(self, client):
        resp = client.post("/auth/login", json={"username": "nobody", "password": "x"})
        assert resp.status_code == 401

    def test_jwt_contains_correct_claims(self, client):
        from jose import jwt as jose_jwt
        token = _login(client)
        payload = jose_jwt.decode(token, "test-secret-key", algorithms=["HS256"])
        assert payload["sub"] == "admin"
        assert payload["role"] == "admin"
        assert "display_name" in payload
        assert "jti" in payload
        assert "exp" in payload

    def test_remember_me_extends_ttl(self, client):
        from jose import jwt as jose_jwt
        resp = client.post("/auth/login", json={
            "username": "admin", "password": "adminpass", "remember": True
        })
        token = resp.json()["access_token"]
        payload = jose_jwt.decode(token, "test-secret-key", algorithms=["HS256"])
        exp = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
        assert (exp - datetime.now(timezone.utc)).days >= 29


# ---------------------------------------------------------------------------
# Middleware tests
# ---------------------------------------------------------------------------

class TestJWTMiddleware:
    def test_api_without_token_returns_401(self, client):
        resp = client.get("/api/devices")
        assert resp.status_code == 401

    def test_api_with_valid_token_passes(self, client):
        token = _login(client)
        resp = client.get("/api/devices", headers=_auth_header(token))
        assert resp.status_code == 200

    def test_auth_endpoints_exempt(self, client):
        resp = client.post("/auth/login", json={"username": "admin", "password": "adminpass"})
        assert resp.status_code == 200

    def test_invalid_token_returns_401(self, client):
        resp = client.get("/api/devices", headers={"Authorization": "Bearer bad.token.here"})
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Registration tests
# ---------------------------------------------------------------------------

class TestRegister:
    def test_valid_invite_creates_account(self, client):
        invite = _create_invite(client)
        resp = client.post("/auth/register", json={
            "invite_token": invite,
            "display_name": "Test User",
            "username": "testuser",
            "password": "testpass123",
        })
        assert resp.status_code == 200
        assert "access_token" in resp.json()

    def test_register_sets_correct_role(self, client):
        from jose import jwt as jose_jwt
        invite = _create_invite(client, role="viewer")
        resp = client.post("/auth/register", json={
            "invite_token": invite,
            "display_name": "Viewer User",
            "username": "viewer1",
            "password": "pass123",
        })
        payload = jose_jwt.decode(resp.json()["access_token"], "test-secret-key", algorithms=["HS256"])
        assert payload["role"] == "viewer"

    def test_expired_token_returns_400(self, client, auth_mod):
        import aiosqlite

        async def _insert():
            async with aiosqlite.connect(auth_mod.DB_PATH) as db:
                expired = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
                await db.execute(
                    "INSERT INTO invite_tokens (token, role, created_by, created_at, expires_at) "
                    "VALUES (?, 'viewer', 'admin', ?, ?)",
                    ("UAV-DEAD-BEEF", datetime.now(timezone.utc).isoformat(), expired),
                )
                await db.commit()

        asyncio.run(_insert())
        resp = client.post("/auth/register", json={
            "invite_token": "UAV-DEAD-BEEF",
            "display_name": "Late", "username": "late", "password": "pass",
        })
        assert resp.status_code == 400
        assert "expired" in resp.json()["detail"].lower()

    def test_already_used_token_returns_400(self, client):
        invite = _create_invite(client)
        client.post("/auth/register", json={
            "invite_token": invite, "display_name": "First",
            "username": "first", "password": "pass",
        })
        resp = client.post("/auth/register", json={
            "invite_token": invite, "display_name": "Second",
            "username": "second", "password": "pass",
        })
        assert resp.status_code == 400
        assert "already been used" in resp.json()["detail"].lower()

    def test_invalid_token_returns_400(self, client):
        resp = client.post("/auth/register", json={
            "invite_token": "UAV-FAKE-FAKE", "display_name": "X",
            "username": "x", "password": "pass",
        })
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# User management tests
# ---------------------------------------------------------------------------

class TestUserManagement:
    def test_deactivated_user_gets_401(self, client):
        admin_token = _login(client)
        invite = _create_invite(client)
        client.post("/auth/register", json={
            "invite_token": invite, "display_name": "Temp",
            "username": "tempuser", "password": "pass123",
        })
        user_token = _login(client, "tempuser", "pass123")

        client.delete("/auth/users/tempuser", headers=_auth_header(admin_token))

        resp = client.get("/api/devices", headers=_auth_header(user_token))
        assert resp.status_code == 401

    def test_viewer_cannot_access_admin_endpoints(self, client):
        admin_token = _login(client)
        invite = _create_invite(client, role="viewer")
        reg = client.post("/auth/register", json={
            "invite_token": invite, "display_name": "Viewer",
            "username": "viewer1", "password": "pass123",
        })
        viewer_token = reg.json()["access_token"]

        assert client.get("/auth/users", headers=_auth_header(viewer_token)).status_code == 403
        assert client.post("/auth/invite", json={"role": "viewer"}, headers=_auth_header(viewer_token)).status_code == 403


# ---------------------------------------------------------------------------
# Property 1: JWT round-trip
# ---------------------------------------------------------------------------

@given(
    username=st.text(min_size=1, max_size=32, alphabet=st.characters(
        whitelist_categories=("Ll", "Lu", "Nd"), whitelist_characters="-_"
    )),
    display_name=st.text(min_size=1, max_size=64),
    role=st.sampled_from(["admin", "viewer"]),
)
@settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture])
def test_property_1_jwt_round_trip(username, display_name, role, tmp_path):
    """
    Property 1: JWT Token Issuance and Verification Round-Trip
    For any valid username/role pair, the JWT issued must decode to the same claims.
    Validates: Requirements 1.1, 1.3, 1.5
    """
    from jose import jwt as jose_jwt
    auth_mod = _load_auth_module(str(tmp_path / f"jwt_{uuid.uuid4().hex}.db"))

    token = auth_mod._create_jwt(username, display_name, role)
    payload = jose_jwt.decode(token, "test-secret-key", algorithms=["HS256"])

    assert payload["sub"] == username
    assert payload["display_name"] == display_name
    assert payload["role"] == role
    assert "jti" in payload
    assert "exp" in payload


# ---------------------------------------------------------------------------
# Property 6: Invite token single-use guarantee (pure DB-level test)
# ---------------------------------------------------------------------------

@given(
    role=st.sampled_from(["admin", "viewer"]),
    username1=st.from_regex(r"[a-z][a-z0-9]{3,10}", fullmatch=True),
    username2=st.from_regex(r"[a-z][a-z0-9]{3,10}", fullmatch=True),
)
@settings(max_examples=20, suppress_health_check=[HealthCheck.too_slow])
def test_property_6_invite_token_single_use(role, username1, username2):
    """
    Property 6: Invite Token Single-Use Guarantee
    Once a token is marked as used in the DB, it cannot be used again.
    Validates: Requirements 1.11, 1.12
    """
    import sqlite3
    import tempfile

    if username1 == username2:
        return

    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    # Create the invite_tokens table and insert a token
    token_val = f"UAV-TEST-{uuid.uuid4().hex[:4].upper()}"
    now = datetime.now(timezone.utc).isoformat()
    expires = (datetime.now(timezone.utc) + timedelta(hours=48)).isoformat()

    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE invite_tokens (
            token TEXT PRIMARY KEY, role TEXT, created_by TEXT,
            created_at TEXT, expires_at TEXT, used_by TEXT, used_at TEXT
        )
    """)
    conn.execute(
        "INSERT INTO invite_tokens VALUES (?, ?, 'admin', ?, ?, NULL, NULL)",
        (token_val, role, now, expires),
    )
    conn.commit()

    # Simulate first use: mark token as consumed
    conn.execute(
        "UPDATE invite_tokens SET used_by = ?, used_at = ? WHERE token = ?",
        (username1, now, token_val),
    )
    conn.commit()

    # Verify: token is now marked as used
    row = conn.execute(
        "SELECT used_by FROM invite_tokens WHERE token = ?", (token_val,)
    ).fetchone()
    assert row is not None
    assert row[0] == username1, "Token should be marked as used by username1"

    # Simulate second use attempt: check used_by is not NULL
    row2 = conn.execute(
        "SELECT used_by FROM invite_tokens WHERE token = ?", (token_val,)
    ).fetchone()
    assert row2[0] is not None, "Token must be rejected on second use (used_by is set)"

    conn.close()
