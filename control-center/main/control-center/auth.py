"""
Auth service for Anti-UAV Control Center.

Provides JWT-based authentication with invite-token registration,
role-based access control, and a full audit trail.

Database: SQLite (auth.db) via aiosqlite — persists across restarts.
Tables: users, invite_tokens, audit_log

Bootstrap: on first startup, creates an admin account from
  BOOTSTRAP_ADMIN_USERNAME + BOOTSTRAP_ADMIN_PASSWORD env vars.
"""

import logging
import os
import secrets
import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

import aiosqlite
from fastapi import Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse
from fastapi.routing import APIRouter
from jose import JWTError, jwt

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

JWT_SECRET = os.environ.get("JWT_SECRET", "change-me-in-production")
JWT_ALGORITHM = "HS256"
JWT_TTL_HOURS = int(os.environ.get("JWT_TTL_HOURS", "8"))
JWT_REMEMBER_DAYS = 30

BOOTSTRAP_ADMIN_USERNAME = os.environ.get("BOOTSTRAP_ADMIN_USERNAME", "admin")
BOOTSTRAP_ADMIN_PASSWORD = os.environ.get("BOOTSTRAP_ADMIN_PASSWORD", "changeme")

DB_PATH = os.environ.get("AUTH_DB_PATH", "/app/auth.db")

import hashlib

import bcrypt as _bcrypt_lib


def _hash_password(password: str) -> str:
    """Hash password using bcrypt. Pre-hash with SHA256 to avoid 72-byte limit."""
    digest = hashlib.sha256(password.encode("utf-8")).digest()
    return _bcrypt_lib.hashpw(digest, _bcrypt_lib.gensalt()).decode("utf-8")


def _verify_password(password: str, hashed: str) -> bool:
    digest = hashlib.sha256(password.encode("utf-8")).digest()
    return _bcrypt_lib.checkpw(digest, hashed.encode("utf-8"))

# In-memory JTI blocklist (cleared on restart — acceptable for short TTLs)
_jti_blocklist: set[str] = set()

# Throttle dict for last_seen updates: jti -> monotonic timestamp of last DB write
_session_last_seen: dict[str, float] = {}

# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------

async def get_db() -> aiosqlite.Connection:
    db = await aiosqlite.connect(DB_PATH)
    db.row_factory = aiosqlite.Row
    return db


async def init_db() -> None:
    """Create tables and bootstrap admin if no users exist."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        await db.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                username TEXT PRIMARY KEY,
                display_name TEXT NOT NULL,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL CHECK(role IN ('admin', 'viewer')),
                created_at TEXT NOT NULL,
                last_login TEXT,
                active INTEGER NOT NULL DEFAULT 1
            );

            CREATE TABLE IF NOT EXISTS invite_tokens (
                token TEXT PRIMARY KEY,
                role TEXT NOT NULL,
                created_by TEXT NOT NULL,
                created_at TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                used_by TEXT,
                used_at TEXT
            );

            CREATE TABLE IF NOT EXISTS audit_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL,
                display_name TEXT NOT NULL,
                action TEXT NOT NULL,
                device_id TEXT,
                payload TEXT,
                timestamp TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS sessions (
                jti TEXT PRIMARY KEY,
                username TEXT NOT NULL,
                display_name TEXT NOT NULL,
                login_time TEXT NOT NULL,
                last_seen TEXT NOT NULL,
                user_agent TEXT,
                expires_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS webhooks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                url TEXT NOT NULL,
                events TEXT NOT NULL,
                secret TEXT NOT NULL DEFAULT '',
                enabled INTEGER NOT NULL DEFAULT 1
            );
        """)
        await db.commit()

        # Bootstrap admin if no users exist
        cursor = await db.execute("SELECT COUNT(*) FROM users")
        row = await cursor.fetchone()
        if row[0] == 0:
            now = _now_iso()
            hashed = _hash_password(BOOTSTRAP_ADMIN_PASSWORD)
            await db.execute(
                "INSERT INTO users (username, display_name, password_hash, role, created_at) "
                "VALUES (?, ?, ?, 'admin', ?)",
                (BOOTSTRAP_ADMIN_USERNAME, BOOTSTRAP_ADMIN_USERNAME, hashed, now),
            )
            await db.commit()
            logger.info("Auth: bootstrapped admin account '%s'", BOOTSTRAP_ADMIN_USERNAME)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# JWT helpers
# ---------------------------------------------------------------------------

def _create_jwt(username: str, display_name: str, role: str, remember: bool = False) -> str:
    jti = str(uuid.uuid4())
    ttl = timedelta(days=JWT_REMEMBER_DAYS) if remember else timedelta(hours=JWT_TTL_HOURS)
    exp = datetime.now(timezone.utc) + ttl
    payload = {
        "sub": username,
        "display_name": display_name,
        "role": role,
        "jti": jti,
        "exp": exp,
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def _decode_jwt(token: str) -> dict:
    """Decode and validate JWT. Raises HTTPException on failure."""
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except JWTError as exc:
        raise HTTPException(status_code=401, detail="Invalid or expired token") from exc
    if payload.get("jti") in _jti_blocklist:
        raise HTTPException(status_code=401, detail="Token has been revoked")
    return payload


async def _get_current_user(request: Request) -> dict:
    """Extract and validate JWT from Authorization header or ?token= query param."""
    token = None
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[7:]
    if not token:
        token = request.query_params.get("token")
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")

    payload = _decode_jwt(token)

    # Check user is still active in DB
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT active FROM users WHERE username = ?", (payload["sub"],)
        )
        row = await cursor.fetchone()
    if not row or not row["active"]:
        raise HTTPException(status_code=401, detail="Account deactivated")

    return payload


async def _require_admin(user: dict = Depends(_get_current_user)) -> dict:
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return user


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login")
async def login(request: Request):
    body = await request.json()
    username = body.get("username", "").strip()
    password = body.get("password", "")
    remember = bool(body.get("remember", False))

    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT username, display_name, password_hash, role, active FROM users WHERE username = ?",
            (username,),
        )
        row = await cursor.fetchone()

    if not row or not row["active"] or not _verify_password(password, row["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    # Update last_login
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE users SET last_login = ? WHERE username = ?", (_now_iso(), username)
        )
        await db.commit()

    token = _create_jwt(row["username"], row["display_name"], row["role"], remember)

    # Insert session row
    claims = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    jti = claims["jti"]
    exp_iso = datetime.fromtimestamp(claims["exp"], tz=timezone.utc).isoformat()
    now_iso = _now_iso()
    user_agent = request.headers.get("User-Agent", "")
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR REPLACE INTO sessions "
            "(jti, username, display_name, login_time, last_seen, user_agent, expires_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (jti, row["username"], row["display_name"], now_iso, now_iso, user_agent, exp_iso),
        )
        await db.commit()

    return {"access_token": token, "token_type": "bearer"}


@router.post("/register")
async def register(request: Request):
    body = await request.json()
    invite_token = body.get("invite_token", "").strip()
    display_name = body.get("display_name", "").strip()
    username = body.get("username", "").strip()
    password = body.get("password", "")

    if not all([invite_token, display_name, username, password]):
        raise HTTPException(status_code=400, detail="All fields are required")

    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row

        # Validate invite token
        cursor = await db.execute(
            "SELECT token, role, expires_at, used_by FROM invite_tokens WHERE token = ?",
            (invite_token,),
        )
        token_row = await cursor.fetchone()

        if not token_row:
            raise HTTPException(status_code=400, detail="Invalid invite token")
        if token_row["used_by"] is not None:
            raise HTTPException(status_code=400, detail="Invite token has already been used")
        if token_row["expires_at"] < _now_iso():
            raise HTTPException(status_code=400, detail="Invite token has expired")

        # Check username not taken
        cursor = await db.execute("SELECT username FROM users WHERE username = ?", (username,))
        if await cursor.fetchone():
            raise HTTPException(status_code=400, detail="Username already taken")

        now = _now_iso()
        hashed = _hash_password(password)
        role = token_row["role"]

        await db.execute(
            "INSERT INTO users (username, display_name, password_hash, role, created_at) VALUES (?, ?, ?, ?, ?)",
            (username, display_name, hashed, role, now),
        )
        await db.execute(
            "UPDATE invite_tokens SET used_by = ?, used_at = ? WHERE token = ?",
            (username, now, invite_token),
        )
        await db.commit()

    token = _create_jwt(username, display_name, role)
    return {"access_token": token, "token_type": "bearer"}


@router.post("/logout")
async def logout(user: dict = Depends(_get_current_user)):
    jti = user["jti"]
    _jti_blocklist.add(jti)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM sessions WHERE jti = ?", (jti,))
        await db.commit()
    _session_last_seen.pop(jti, None)
    return {"status": "logged out"}


@router.get("/me")
async def me(user: dict = Depends(_get_current_user)):
    return {
        "username": user["sub"],
        "display_name": user["display_name"],
        "role": user["role"],
    }


@router.post("/invite")
async def create_invite(request: Request, admin: dict = Depends(_require_admin)):
    body = await request.json()
    role = body.get("role", "viewer")
    expiry_hours = int(body.get("expiry_hours", 48))

    if role not in ("admin", "viewer"):
        raise HTTPException(status_code=400, detail="Role must be 'admin' or 'viewer'")

    # Cap at 30 days (720 hours)
    expiry_hours = min(expiry_hours, 720)

    # Generate UAV-XXXX-XXXX format token
    part1 = secrets.token_hex(2).upper()
    part2 = secrets.token_hex(2).upper()
    token = f"UAV-{part1}-{part2}"

    now = _now_iso()
    expires_at = (datetime.now(timezone.utc) + timedelta(hours=expiry_hours)).isoformat()

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO invite_tokens (token, role, created_by, created_at, expires_at) VALUES (?, ?, ?, ?, ?)",
            (token, role, admin["sub"], now, expires_at),
        )
        await db.commit()

    return {"token": token, "role": role, "expires_at": expires_at}


@router.get("/users")
async def list_users(admin: dict = Depends(_require_admin)):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT username, display_name, role, created_at, last_login, active FROM users ORDER BY created_at"
        )
        rows = await cursor.fetchall()
    return [dict(r) for r in rows]


@router.delete("/users/{username}")
async def deactivate_user(username: str, admin: dict = Depends(_require_admin)):
    if username == admin["sub"]:
        raise HTTPException(status_code=400, detail="Cannot deactivate your own account")
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET active = 0 WHERE username = ?", (username,))
        await db.commit()
    return {"status": "deactivated", "username": username}


@router.get("/audit")
async def get_audit(
    limit: int = 100,
    username: Optional[str] = None,
    device_id: Optional[str] = None,
    admin: dict = Depends(_require_admin),
):
    query = "SELECT username, display_name, action, device_id, payload, timestamp FROM audit_log"
    params = []
    conditions = []
    if username:
        conditions.append("username = ?")
        params.append(username)
    if device_id:
        conditions.append("device_id = ?")
        params.append(device_id)
    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    query += " ORDER BY id DESC LIMIT ?"
    params.append(limit)

    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(query, params)
        rows = await cursor.fetchall()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Token status helper
# ---------------------------------------------------------------------------

def _compute_token_status(row: dict) -> str:
    """Compute status for an invite token row."""
    if row["used_by"] is not None:
        return "used"
    if row["expires_at"] < _now_iso():
        return "expired"
    return "pending"


# ---------------------------------------------------------------------------
# API router — mounted at /api in app.py
# ---------------------------------------------------------------------------

api_router = APIRouter(prefix="/api", tags=["api"])


@api_router.get("/tokens")
async def list_tokens(admin: dict = Depends(_require_admin)):
    """Return all invite tokens with computed status. Admin only."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT token, role, created_by, created_at, expires_at, used_by, used_at "
            "FROM invite_tokens ORDER BY created_at DESC"
        )
        rows = await cursor.fetchall()
    result = []
    for row in rows:
        entry = dict(row)
        entry["status"] = _compute_token_status(entry)
        result.append(entry)
    return result


@api_router.delete("/tokens/{token}")
async def delete_token(token: str, admin: dict = Depends(_require_admin)):
    """Delete (revoke) a pending invite token. Rejects used or expired tokens."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT token, used_by, expires_at FROM invite_tokens WHERE token = ?", (token,)
        )
        row = await cursor.fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="Token not found")

    status = _compute_token_status(dict(row))
    if status in ("used", "expired"):
        raise HTTPException(status_code=400, detail="Cannot revoke a used or expired token")

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM invite_tokens WHERE token = ?", (token,))
        await db.commit()

    return {"status": "revoked", "token": token}


# ---------------------------------------------------------------------------
# Session management endpoints
# ---------------------------------------------------------------------------

@api_router.get("/sessions")
async def list_sessions(admin: dict = Depends(_require_admin)):
    """Return all active sessions ordered by login_time DESC. Admin only."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT jti, username, display_name, login_time, last_seen, user_agent, expires_at "
            "FROM sessions ORDER BY login_time DESC"
        )
        rows = await cursor.fetchall()
    return [dict(r) for r in rows]


@api_router.delete("/sessions/{jti}")
async def revoke_session(jti: str, admin: dict = Depends(_require_admin)):
    """Revoke a session: add jti to blocklist and delete from sessions table. Admin only."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT jti FROM sessions WHERE jti = ?", (jti,))
        row = await cursor.fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="Session not found")

    _jti_blocklist.add(jti)
    _session_last_seen.pop(jti, None)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM sessions WHERE jti = ?", (jti,))
        await db.commit()

    return {"status": "revoked", "jti": jti}


# ---------------------------------------------------------------------------
# Webhook management endpoints (Task 9.4)
# ---------------------------------------------------------------------------

@api_router.get("/webhooks")
async def list_webhooks(admin: dict = Depends(_require_admin)):
    """Return all webhooks. Admin only."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT id, url, events, secret, enabled FROM webhooks ORDER BY id"
        )
        rows = await cursor.fetchall()
    return [dict(r) for r in rows]


@api_router.post("/webhooks")
async def create_webhook(request: Request, admin: dict = Depends(_require_admin)):
    """Create a new webhook. Admin only. Body: {url, events, secret}."""
    body = await request.json()
    url = body.get("url", "").strip()
    events = body.get("events", "")
    secret = body.get("secret", "")
    enabled = int(body.get("enabled", 1))

    if not url:
        raise HTTPException(status_code=400, detail="url is required")

    # Normalize events to comma-separated string
    if isinstance(events, list):
        events = ",".join(events)

    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "INSERT INTO webhooks (url, events, secret, enabled) VALUES (?, ?, ?, ?)",
            (url, events, secret, enabled),
        )
        await db.commit()
        webhook_id = cursor.lastrowid

    return {"id": webhook_id, "url": url, "events": events, "secret": secret, "enabled": enabled}


@api_router.put("/webhooks/{webhook_id}")
async def update_webhook(
    webhook_id: int, request: Request, admin: dict = Depends(_require_admin)
):
    """Update a webhook. Admin only."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT id FROM webhooks WHERE id = ?", (webhook_id,))
        row = await cursor.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Webhook not found")

    body = await request.json()
    fields = []
    params = []
    for key in ("url", "events", "secret", "enabled"):
        if key in body:
            val = body[key]
            if key == "events" and isinstance(val, list):
                val = ",".join(val)
            if key == "enabled":
                val = int(val)
            fields.append(f"{key} = ?")
            params.append(val)

    if not fields:
        raise HTTPException(status_code=400, detail="No fields to update")

    params.append(webhook_id)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            f"UPDATE webhooks SET {', '.join(fields)} WHERE id = ?", params
        )
        await db.commit()

    return {"status": "updated", "id": webhook_id}


@api_router.delete("/webhooks/{webhook_id}")
async def delete_webhook(webhook_id: int, admin: dict = Depends(_require_admin)):
    """Delete a webhook. Admin only."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT id FROM webhooks WHERE id = ?", (webhook_id,))
        row = await cursor.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Webhook not found")

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM webhooks WHERE id = ?", (webhook_id,))
        await db.commit()

    return {"status": "deleted", "id": webhook_id}


@api_router.post("/webhooks/{webhook_id}/test")
async def test_webhook(webhook_id: int, admin: dict = Depends(_require_admin)):
    """POST a test payload to the webhook URL and return the HTTP status code. Admin only."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT id, url, events, secret, enabled FROM webhooks WHERE id = ?", (webhook_id,)
        )
        row = await cursor.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Webhook not found")

    import hashlib
    import hmac as _hmac
    import json as _json

    url = row["url"]
    secret = row["secret"] or ""
    test_payload = {
        "event": "test",
        "device_id": "test-device",
        "timestamp": _now_iso(),
        "data": {"message": "This is a test webhook delivery"},
    }
    body_bytes = _json.dumps(test_payload, separators=(",", ":")).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if secret:
        mac = _hmac.new(secret.encode("utf-8"), body_bytes, hashlib.sha256)
        headers["X-UAV-Signature"] = "hmac-sha256=" + mac.hexdigest()

    try:
        import httpx
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.post(url, content=body_bytes, headers=headers)
        return {"status_code": resp.status_code, "url": url}
    except Exception as exc:
        return {"status_code": None, "url": url, "error": str(exc)}


# ---------------------------------------------------------------------------
# Middleware helpers (used by app.py)
# ---------------------------------------------------------------------------

async def jwt_auth_middleware(request: Request, call_next):
    """
    Validate JWT on all /api/* routes and /ws.
    Exempt: /auth/*, static files, root.
    """
    path = request.url.path

    # Exempt paths
    if (
        path.startswith("/auth/")
        or path == "/"
        or path.startswith("/assets/")
        or not (path.startswith("/api/") or path == "/ws")
    ):
        return await call_next(request)

    # WebSocket: token in query param
    if path == "/ws":
        token = request.query_params.get("token")
        if not token:
            from fastapi.responses import Response as FR
            return FR(status_code=401, content="Not authenticated")
        try:
            _decode_jwt(token)
        except HTTPException:
            from fastapi.responses import Response as FR
            return FR(status_code=401, content="Invalid token")
        # Check active
        try:
            payload = _decode_jwt(token)
            async with aiosqlite.connect(DB_PATH) as db:
                db.row_factory = aiosqlite.Row
                cursor = await db.execute(
                    "SELECT active FROM users WHERE username = ?", (payload["sub"],)
                )
                row = await cursor.fetchone()
            if not row or not row["active"]:
                from fastapi.responses import Response as FR
                return FR(status_code=401, content="Account deactivated")
        except Exception:
            from fastapi.responses import Response as FR
            return FR(status_code=401, content="Invalid token")
        return await call_next(request)

    # REST: Bearer token
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return JSONResponse(status_code=401, content={"detail": "Not authenticated"})
    token = auth_header[7:]
    try:
        payload = _decode_jwt(token)
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT active FROM users WHERE username = ?", (payload["sub"],)
            )
            row = await cursor.fetchone()
        if not row or not row["active"]:
            return JSONResponse(status_code=401, content={"detail": "Account deactivated"})
        # Attach user to request state for audit middleware
        request.state.user = payload

        # Update last_seen with 60-second throttle
        jti = payload.get("jti")
        if jti:
            now_mono = time.monotonic()
            last_update = _session_last_seen.get(jti, 0.0)
            if now_mono - last_update > 60:
                _session_last_seen[jti] = now_mono
                try:
                    async with aiosqlite.connect(DB_PATH) as db2:
                        await db2.execute(
                            "UPDATE sessions SET last_seen = ? WHERE jti = ?",
                            (_now_iso(), jti),
                        )
                        await db2.commit()
                except Exception as exc:
                    logger.warning("last_seen update failed: %s", exc)
    except HTTPException as exc:
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})

    return await call_next(request)


async def audit_middleware(request: Request, call_next):
    """
    Write audit log entry for POST /api/command/* and POST /api/ptz/*.
    Must run after jwt_auth_middleware so request.state.user is set.
    """
    response = await call_next(request)

    path = request.url.path
    method = request.method
    if method == "POST" and (
        path.startswith("/api/command/") or path.startswith("/api/ptz/")
    ):
        user = getattr(request.state, "user", None)
        if user:
            # Extract device_id from path
            parts = path.strip("/").split("/")
            device_id = parts[-1] if len(parts) >= 3 else None
            action = "/".join(parts[1:3]) if len(parts) >= 3 else path

            try:
                async with aiosqlite.connect(DB_PATH) as db:
                    await db.execute(
                        "INSERT INTO audit_log (username, display_name, action, device_id, timestamp) "
                        "VALUES (?, ?, ?, ?, ?)",
                        (
                            user.get("sub", "unknown"),
                            user.get("display_name", "unknown"),
                            action,
                            device_id,
                            _now_iso(),
                        ),
                    )
                    await db.commit()
            except Exception as exc:
                logger.warning("Audit log write failed: %s", exc)

    return response
