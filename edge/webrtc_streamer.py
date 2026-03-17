"""
Edge device — WebRTC streamer.

Uses aiortc to create an RTCPeerConnection and stream camera frames to a
browser subscriber via the signaling server.

Signaling protocol (WebSocket JSON messages):
  → {"type": "register",       "device_id": "...", "role": "publisher"}
  ← {"type": "request_offer",  "device_id": "..."}
  → {"type": "offer",          "device_id": "...", "sdp": "...", "sdpType": "offer"}
  ← {"type": "answer",         "device_id": "...", "sdp": "...", "sdpType": "answer"}
  ↔ {"type": "ice_candidate",  "device_id": "...", "candidate": {...}}

DTLS-SRTP is enforced by aiortc automatically.

Requirements: 5.1, 7.3, 7.4, 11.2
"""

import asyncio
import json
import logging
import queue
import threading
from typing import Any, Optional

import numpy as np

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# VideoStreamTrack
# ---------------------------------------------------------------------------

class CameraVideoTrack:
    """
    aiortc VideoStreamTrack that reads frames from a queue.Queue.

    Lazily imports aiortc so the module can be imported without aiortc
    installed (e.g. in unit tests that mock it).
    """

    def __new__(cls, frame_queue: queue.Queue, fps: int = 15):
        from aiortc.mediastreams import VideoStreamTrack  # type: ignore
        import av  # type: ignore

        class _Track(VideoStreamTrack):
            kind = "video"

            def __init__(self, fq: queue.Queue, target_fps: int) -> None:
                super().__init__()
                self._queue = fq
                self._fps = target_fps
                self._pts = 0

            async def recv(self):
                # Block until a frame is available (with timeout to allow stop)
                loop = asyncio.get_event_loop()
                frame_array = await loop.run_in_executor(
                    None, self._get_frame
                )
                video_frame = av.VideoFrame.from_ndarray(frame_array, format="bgr24")
                video_frame.pts = self._pts
                video_frame.time_base = __import__("fractions").Fraction(1, self._fps)
                self._pts += 1
                return video_frame

            def _get_frame(self) -> np.ndarray:
                while True:
                    try:
                        return self._queue.get(timeout=0.1)
                    except Exception:
                        # Return a black frame if queue is empty
                        return np.zeros((480, 640, 3), dtype=np.uint8)

        return _Track(frame_queue, fps)


# ---------------------------------------------------------------------------
# WebRTCStreamer
# ---------------------------------------------------------------------------

class WebRTCStreamer:
    """
    Manages a WebRTC peer connection and signaling for one edge device.

    Args:
        config:      Loaded Config object.
        frame_queue: queue.Queue that camera frames are pushed into.
    """

    def __init__(self, config: Any, frame_queue: queue.Queue) -> None:
        self._config = config
        self._frame_queue = frame_queue
        self._device_id: str = config.device_id
        self._signaling_url: str = config.get("signaling.url", "ws://localhost:8765")
        self._fps: int = int(config.get("camera.fps", 15))

        self._running = False
        self._pc = None          # RTCPeerConnection
        self._ws = None          # websockets connection
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._thread: Optional[threading.Thread] = None

    # ------------------------------------------------------------------
    # Public API (called from sync context by CommandHandler)
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Start the WebRTC streamer in a background asyncio thread."""
        if self._running:
            logger.info("WebRTCStreamer: already running")
            return
        self._running = True
        self._thread = threading.Thread(
            target=self._run_event_loop, daemon=True, name="webrtc-streamer"
        )
        self._thread.start()
        logger.info("WebRTCStreamer: started")

    def stop(self) -> None:
        """Stop the WebRTC streamer and close the peer connection."""
        if not self._running:
            return
        self._running = False
        if self._loop and not self._loop.is_closed():
            asyncio.run_coroutine_threadsafe(self._shutdown(), self._loop)
        if self._thread:
            self._thread.join(timeout=3)
        logger.info("WebRTCStreamer: stopped")

    # ------------------------------------------------------------------
    # Internal — event loop thread
    # ------------------------------------------------------------------

    def _run_event_loop(self) -> None:
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_until_complete(self._signaling_loop())
        except Exception as exc:
            logger.error("WebRTCStreamer: event loop error: %s", exc)
        finally:
            self._loop.close()

    async def _signaling_loop(self) -> None:
        """Connect to signaling server and handle messages."""
        try:
            import websockets  # type: ignore
        except ImportError:
            logger.error("WebRTCStreamer: websockets package not installed")
            return

        while self._running:
            try:
                async with websockets.connect(self._signaling_url) as ws:
                    self._ws = ws
                    logger.info("WebRTCStreamer: connected to signaling server %s", self._signaling_url)

                    # Register as publisher
                    await ws.send(json.dumps({
                        "type": "register",
                        "device_id": self._device_id,
                        "role": "publisher",
                    }))

                    async for raw in ws:
                        if not self._running:
                            break
                        try:
                            msg = json.loads(raw)
                        except json.JSONDecodeError:
                            continue
                        await self._handle_message(ws, msg)

            except Exception as exc:
                if self._running:
                    logger.warning("WebRTCStreamer: signaling disconnected: %s — retrying in 5s", exc)
                    await asyncio.sleep(5)
                else:
                    break

    async def _handle_message(self, ws, msg: dict) -> None:
        msg_type = msg.get("type")

        if msg_type == "request_offer":
            await self._create_offer(ws)

        elif msg_type == "answer":
            if self._pc is None:
                return
            from aiortc import RTCSessionDescription  # type: ignore
            answer = RTCSessionDescription(sdp=msg["sdp"], type=msg["sdpType"])
            await self._pc.setRemoteDescription(answer)
            logger.info("WebRTCStreamer: remote description set")

        elif msg_type == "ice_candidate":
            if self._pc is None:
                return
            from aiortc import RTCIceCandidate  # type: ignore
            cand_data = msg.get("candidate", {})
            if cand_data:
                candidate = RTCIceCandidate(
                    component=cand_data.get("component", 1),
                    foundation=cand_data.get("foundation", ""),
                    ip=cand_data.get("ip", ""),
                    port=cand_data.get("port", 0),
                    priority=cand_data.get("priority", 0),
                    protocol=cand_data.get("protocol", "udp"),
                    type=cand_data.get("type", "host"),
                    sdpMid=cand_data.get("sdpMid"),
                    sdpMLineIndex=cand_data.get("sdpMLineIndex"),
                )
                await self._pc.addIceCandidate(candidate)

    async def _create_offer(self, ws) -> None:
        """Create RTCPeerConnection, add video track, send offer."""
        from aiortc import RTCPeerConnection  # type: ignore

        # Close any existing connection
        if self._pc is not None:
            await self._pc.close()

        self._pc = RTCPeerConnection()

        # Add video track
        track = CameraVideoTrack(self._frame_queue, self._fps)
        self._pc.addTrack(track)

        # ICE candidate handler
        @self._pc.on("icecandidate")
        async def on_ice_candidate(candidate):
            if candidate and self._ws:
                await ws.send(json.dumps({
                    "type": "ice_candidate",
                    "device_id": self._device_id,
                    "candidate": {
                        "component": candidate.component,
                        "foundation": candidate.foundation,
                        "ip": candidate.ip,
                        "port": candidate.port,
                        "priority": candidate.priority,
                        "protocol": candidate.protocol,
                        "type": candidate.type,
                        "sdpMid": candidate.sdpMid,
                        "sdpMLineIndex": candidate.sdpMLineIndex,
                    },
                }))

        offer = await self._pc.createOffer()
        await self._pc.setLocalDescription(offer)

        await ws.send(json.dumps({
            "type": "offer",
            "device_id": self._device_id,
            "sdp": self._pc.localDescription.sdp,
            "sdpType": self._pc.localDescription.type,
        }))
        logger.info("WebRTCStreamer: offer sent")

    async def _shutdown(self) -> None:
        if self._pc is not None:
            await self._pc.close()
            self._pc = None
        if self._ws is not None:
            await self._ws.close()
            self._ws = None
