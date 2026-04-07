"""
Control center backend — FastAPI app.

Serves the React frontend static files from dist/.
Proxies REST and WebSocket requests to the aggregation service.
JWT auth enforced on all /api/* and /ws routes.

Requirements: 6.1, 15.2, 15.3, 15.5, v2-1.x
"""

import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

import httpx
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware import Middleware
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles

from .auth import (
    audit_middleware,
    init_db,
    jwt_auth_middleware,
    router as auth_router,
)

logger = logging.getLogger(__name__)

AGGREGATION_URL = os.environ.get("AGGREGATION_URL", "http://aggregation:8000")
AGGREGATION_WS_URL = os.environ.get("AGGREGATION_WS_URL", "ws://aggregation:8000/ws")

DIST_DIR = Path(__file__).parent / "dist"


# ---------------------------------------------------------------------------
# App lifespan
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


app = FastAPI(title="Anti-UAV Control Center", lifespan=lifespan)

# Middleware (order matters: jwt first, then audit)
app.middleware("http")(jwt_auth_middleware)
app.middleware("http")(audit_middleware)

# Auth routes (exempt from JWT middleware)
app.include_router(auth_router)


# ---------------------------------------------------------------------------
# API proxy endpoints
# ---------------------------------------------------------------------------

@app.get("/api/devices")
async def proxy_devices(request: Request):
    async with httpx.AsyncClient() as client:
        resp = await client.get(f"{AGGREGATION_URL}/devices")
    return JSONResponse(content=resp.json(), status_code=resp.status_code)


@app.get("/api/devices/{device_id}")
async def proxy_device(device_id: str, request: Request):
    async with httpx.AsyncClient() as client:
        resp = await client.get(f"{AGGREGATION_URL}/devices/{device_id}")
    return JSONResponse(content=resp.json(), status_code=resp.status_code)


@app.get("/api/devices/{device_id}/health")
async def proxy_device_health(device_id: str, request: Request):
    async with httpx.AsyncClient() as client:
        resp = await client.get(f"{AGGREGATION_URL}/devices/{device_id}/health")
    return JSONResponse(content=resp.json(), status_code=resp.status_code)


@app.post("/api/command/{device_id}")
async def proxy_command(device_id: str, request: Request):
    body = await request.json()
    async with httpx.AsyncClient() as client:
        resp = await client.post(f"{AGGREGATION_URL}/command/{device_id}", json=body)
    return JSONResponse(content=resp.json(), status_code=resp.status_code)


@app.post("/api/ptz/{device_id}")
async def proxy_ptz(device_id: str, request: Request):
    body = await request.json()
    async with httpx.AsyncClient() as client:
        resp = await client.post(f"{AGGREGATION_URL}/ptz/{device_id}", json=body)
    return JSONResponse(content=resp.json(), status_code=resp.status_code)


@app.get("/api/logs/{device_id}")
async def proxy_logs(device_id: str, request: Request):
    params = dict(request.query_params)
    async with httpx.AsyncClient() as client:
        resp = await client.get(f"{AGGREGATION_URL}/logs/{device_id}", params=params)
    return JSONResponse(content=resp.json(), status_code=resp.status_code)


# ---------------------------------------------------------------------------
# WebSocket proxy
# ---------------------------------------------------------------------------

@app.websocket("/ws")
async def proxy_websocket(websocket: WebSocket):
    await websocket.accept()
    try:
        import websockets as ws_lib  # type: ignore
        import asyncio
        async with ws_lib.connect(AGGREGATION_WS_URL) as agg_ws:
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
    """Serve index.html for all non-API, non-auth routes (SPA fallback)."""
    index = DIST_DIR / "index.html"
    if index.exists():
        return FileResponse(str(index))
    return Response(content="Frontend not built. Run: npm run build", status_code=503)
