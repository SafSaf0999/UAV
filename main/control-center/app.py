"""
Control center backend — FastAPI app.

Serves the React frontend static files from dist/.
Proxies REST and WebSocket requests to the aggregation service.
Enforces Bearer token auth when REMOTE_ACCESS_MODE=https.
Logs a startup warning when non-VPN mode is active.

Requirements: 6.1, 15.2, 15.3, 15.5
"""

import logging
import os
from pathlib import Path
from typing import Optional

import httpx
from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles

logger = logging.getLogger(__name__)

REMOTE_ACCESS_MODE = os.environ.get("REMOTE_ACCESS_MODE", "vpn")
HTTPS_TOKEN = os.environ.get("HTTPS_TOKEN", "")
AGGREGATION_URL = os.environ.get("AGGREGATION_URL", "http://aggregation:8000")
AGGREGATION_WS_URL = os.environ.get("AGGREGATION_WS_URL", "ws://aggregation:8000/ws")

DIST_DIR = Path(__file__).parent / "dist"

# ---------------------------------------------------------------------------
# Auth helper
# ---------------------------------------------------------------------------

def _check_auth(request: Request) -> Optional[Response]:
    """Return a 401 Response if auth fails in HTTPS mode, else None."""
    if REMOTE_ACCESS_MODE != "https":
        return None
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer ") or auth_header[7:] != HTTPS_TOKEN:
        return Response(
            content='{"detail":"Unauthorized"}',
            status_code=401,
            media_type="application/json",
        )
    return None


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(title="Anti-UAV Control Center")


@app.on_event("startup")
async def _startup() -> None:
    if REMOTE_ACCESS_MODE != "vpn":
        logger.warning(
            "Control center: REMOTE_ACCESS_MODE=%s — non-VPN mode active. "
            "Ensure HTTPS and token auth are properly configured.",
            REMOTE_ACCESS_MODE,
        )
    else:
        logger.info("Control center: VPN mode active")


# ---------------------------------------------------------------------------
# API proxy endpoints
# ---------------------------------------------------------------------------

@app.get("/api/devices")
async def proxy_devices(request: Request):
    err = _check_auth(request)
    if err:
        return err
    async with httpx.AsyncClient() as client:
        resp = await client.get(f"{AGGREGATION_URL}/devices")
    return JSONResponse(content=resp.json(), status_code=resp.status_code)


@app.get("/api/devices/{device_id}")
async def proxy_device(device_id: str, request: Request):
    err = _check_auth(request)
    if err:
        return err
    async with httpx.AsyncClient() as client:
        resp = await client.get(f"{AGGREGATION_URL}/devices/{device_id}")
    return JSONResponse(content=resp.json(), status_code=resp.status_code)


@app.post("/api/command/{device_id}")
async def proxy_command(device_id: str, request: Request):
    err = _check_auth(request)
    if err:
        return err
    body = await request.json()
    async with httpx.AsyncClient() as client:
        resp = await client.post(f"{AGGREGATION_URL}/command/{device_id}", json=body)
    return JSONResponse(content=resp.json(), status_code=resp.status_code)


@app.post("/api/ptz/{device_id}")
async def proxy_ptz(device_id: str, request: Request):
    err = _check_auth(request)
    if err:
        return err
    body = await request.json()
    async with httpx.AsyncClient() as client:
        resp = await client.post(f"{AGGREGATION_URL}/ptz/{device_id}", json=body)
    return JSONResponse(content=resp.json(), status_code=resp.status_code)


# ---------------------------------------------------------------------------
# WebSocket proxy
# ---------------------------------------------------------------------------

@app.websocket("/ws")
async def proxy_websocket(websocket: WebSocket):
    # Auth check for HTTPS mode
    if REMOTE_ACCESS_MODE == "https":
        token = websocket.query_params.get("token", "")
        if token != HTTPS_TOKEN:
            await websocket.close(code=4001)
            return

    await websocket.accept()
    try:
        import websockets as ws_lib  # type: ignore
        async with ws_lib.connect(AGGREGATION_WS_URL) as agg_ws:
            import asyncio

            async def forward_to_client():
                async for msg in agg_ws:
                    await websocket.send_text(msg)

            async def forward_to_agg():
                while True:
                    data = await websocket.receive_text()
                    await agg_ws.send(data)

            done, pending = await asyncio.wait(
                [
                    asyncio.create_task(forward_to_client()),
                    asyncio.create_task(forward_to_agg()),
                ],
                return_when=asyncio.FIRST_COMPLETED,
            )
            for task in pending:
                task.cancel()
    except WebSocketDisconnect:
        pass
    except Exception as exc:
        logger.warning("Control center WS proxy error: %s", exc)


# ---------------------------------------------------------------------------
# Static file serving (React frontend)
# ---------------------------------------------------------------------------

if DIST_DIR.exists():
    app.mount("/assets", StaticFiles(directory=str(DIST_DIR / "assets")), name="assets")


@app.get("/{full_path:path}")
async def serve_spa(full_path: str, request: Request):
    """Serve index.html for all non-API routes (SPA fallback)."""
    # Skip auth for static assets
    if full_path.startswith("api/"):
        err = _check_auth(request)
        if err:
            return err

    index = DIST_DIR / "index.html"
    if index.exists():
        return FileResponse(str(index))
    return Response(content="Frontend not built. Run: npm run build", status_code=503)
