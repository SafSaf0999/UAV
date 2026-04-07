/**
 * Live feed grid — up to 4 WebRTC video streams.
 *
 * Auto-starts streams when the page opens or when a feed thumbnail
 * becomes visible (Intersection Observer).
 * Shows distinct "Waiting for stream…" vs "Stream interrupted" states.
 * Supports TURN server fallback via TURN_SERVER_URL env var.
 *
 * Requirements: 5.2, 5.3, 5.4, 5.5, 6.3, 6.4, v2-8.1–8.8
 */

import React, { useEffect, useRef, useState } from "react";
import { useDevices } from "../api/websocket";
import { sendCommand } from "../api/commands";
import type { DeviceState } from "../types";
import { TrackingOverlay } from "./TrackingOverlay";
import { PtzControls } from "./PtzControls";

declare const __SIGNALING_URL__: string;
const SIGNALING_URL = __SIGNALING_URL__;

// Optional TURN server — injected at build time or falls back to STUN only
declare const __TURN_SERVER_URL__: string | undefined;

const MAX_FEEDS = 4;

// Track which devices have had start_stream sent this session
const _activeStreams = new Set<string>();

function getIceServers(): RTCIceServer[] {
  const servers: RTCIceServer[] = [{ urls: "stun:stun.l.google.com:19302" }];
  try {
    if (typeof __TURN_SERVER_URL__ !== "undefined" && __TURN_SERVER_URL__) {
      servers.push({ urls: __TURN_SERVER_URL__ });
    }
  } catch {
    // __TURN_SERVER_URL__ not defined — STUN only
  }
  return servers;
}

// ---------------------------------------------------------------------------
// WebRTC peer connection per device
// ---------------------------------------------------------------------------

type StreamState = "waiting" | "connected" | "interrupted";

function useWebRTCStream(device_id: string, videoRef: React.RefObject<HTMLVideoElement>) {
  const [streamState, setStreamState] = useState<StreamState>("waiting");
  const pcRef = useRef<RTCPeerConnection | null>(null);
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    let cancelled = false;

    function connect() {
      const ws = new WebSocket(SIGNALING_URL);
      wsRef.current = ws;

      const pc = new RTCPeerConnection({ iceServers: getIceServers() });
      pcRef.current = pc;

      pc.ontrack = (event) => {
        if (videoRef.current && event.streams[0]) {
          videoRef.current.srcObject = event.streams[0];
          setStreamState("connected");
        }
      };

      pc.onicecandidate = (event) => {
        if (event.candidate && ws.readyState === WebSocket.OPEN) {
          ws.send(JSON.stringify({
            type: "ice_candidate",
            device_id,
            candidate: event.candidate.toJSON(),
          }));
        }
      };

      pc.onconnectionstatechange = () => {
        if (pc.connectionState === "failed" || pc.connectionState === "disconnected") {
          setStreamState("interrupted");
          if (!cancelled) setTimeout(connect, 3000);
        }
      };

      ws.onopen = () => {
        ws.send(JSON.stringify({ type: "register", device_id, role: "subscriber" }));
      };

      ws.onmessage = async (event) => {
        const msg = JSON.parse(event.data);
        if (msg.type === "offer") {
          await pc.setRemoteDescription(new RTCSessionDescription({ type: msg.sdpType, sdp: msg.sdp }));
          const answer = await pc.createAnswer();
          await pc.setLocalDescription(answer);
          ws.send(JSON.stringify({
            type: "answer",
            device_id,
            sdp: answer.sdp,
            sdpType: answer.type,
          }));
        } else if (msg.type === "ice_candidate" && msg.candidate) {
          await pc.addIceCandidate(new RTCIceCandidate(msg.candidate));
        }
      };

      ws.onclose = () => {
        if (!cancelled) {
          setStreamState("interrupted");
          setTimeout(connect, 3000);
        }
      };
    }

    connect();

    return () => {
      cancelled = true;
      pcRef.current?.close();
      wsRef.current?.close();
    };
  }, [device_id]);

  return { streamState };
}

// ---------------------------------------------------------------------------
// Single feed cell
// ---------------------------------------------------------------------------

function FeedCell({ device }: { device: DeviceState }) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const thumbRef = useRef<HTMLDivElement>(null);
  const { streamState } = useWebRTCStream(device.device_id, videoRef);
  const hasPtz = device.last_ptz_status !== null || device.active_model !== null;

  // Intersection Observer — auto-start when thumbnail becomes visible
  useEffect(() => {
    const el = thumbRef.current;
    if (!el || device.status !== "online") return;
    const observer = new IntersectionObserver(([entry]) => {
      if (entry.isIntersecting && !_activeStreams.has(device.device_id)) {
        _activeStreams.add(device.device_id);
        sendCommand(device.device_id, { action: "start_stream" });
      }
    }, { threshold: 0.1 });
    observer.observe(el);
    return () => observer.disconnect();
  }, [device.device_id, device.status]);

  return (
    <div
      ref={thumbRef}
      style={{ position: "relative", background: "#000", borderRadius: "var(--ha-border-radius-md)", overflow: "hidden", aspectRatio: "16/9" }}
    >
      <video
        ref={videoRef}
        autoPlay
        playsInline
        muted
        style={{ width: "100%", height: "100%", objectFit: "cover" }}
        aria-label={`Live feed from ${device.device_id}`}
      />

      {/* Tracking overlay */}
      {device.last_tracking && (
        <TrackingOverlay
          tracking={device.last_tracking}
          containerRef={thumbRef as React.RefObject<HTMLElement>}
          videoRef={videoRef}
        />
      )}

      {/* Waiting for stream */}
      {streamState === "waiting" && (
        <div style={overlayStyle}>
          <div style={spinnerStyle} aria-label="Waiting for stream" />
          <span style={{ color: "var(--secondary-text-color)", fontSize: "var(--ha-font-size-s)" }}>
            Waiting for stream…
          </span>
        </div>
      )}

      {/* Stream interrupted */}
      {streamState === "interrupted" && (
        <div style={{ ...overlayStyle, background: "rgba(0,0,0,0.7)" }}>
          <span style={{ color: "var(--uav-color-alert)", fontSize: "var(--ha-font-size-s)" }}>
            ⚠ Stream interrupted — reconnecting…
          </span>
        </div>
      )}

      {/* Device label */}
      <div style={{
        position: "absolute", top: 8, left: 8,
        background: "rgba(0,0,0,0.6)", color: "#f9fafb",
        fontSize: "var(--ha-font-size-xs)", padding: "2px 8px",
        borderRadius: "var(--ha-border-radius-sm)",
      }}>
        {device.device_id}
      </div>

      {/* PTZ controls overlay */}
      {hasPtz && (
        <div style={{ position: "absolute", bottom: 8, right: 8 }}>
          <PtzControls device_id={device.device_id} compact />
        </div>
      )}
    </div>
  );
}

const overlayStyle: React.CSSProperties = {
  position: "absolute", inset: 0,
  display: "flex", flexDirection: "column",
  alignItems: "center", justifyContent: "center",
  gap: "var(--ha-space-2)",
  background: "rgba(0,0,0,0.5)",
};

const spinnerStyle: React.CSSProperties = {
  width: 24, height: 24,
  border: "3px solid var(--ha-color-neutral-30)",
  borderTopColor: "var(--primary-color)",
  borderRadius: "50%",
  animation: "spin 0.8s linear infinite",
};

// ---------------------------------------------------------------------------
// LiveFeedGrid
// ---------------------------------------------------------------------------

export function LiveFeedGrid() {
  const devices = useDevices();
  const onlineDevices = Object.values(devices)
    .filter((d) => d.status === "online")
    .slice(0, MAX_FEEDS);

  // Auto-start streams for all online devices on mount
  useEffect(() => {
    for (const device of onlineDevices) {
      if (!_activeStreams.has(device.device_id)) {
        _activeStreams.add(device.device_id);
        sendCommand(device.device_id, { action: "start_stream" });
      }
    }
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  if (onlineDevices.length === 0) {
    return (
      <div style={{ color: "var(--secondary-text-color)", padding: "var(--ha-space-6)" }}>
        No online devices to stream.
      </div>
    );
  }

  return (
    <>
      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
      <div style={{
        display: "grid",
        gridTemplateColumns: onlineDevices.length === 1 ? "1fr" : "repeat(2, 1fr)",
        gap: "var(--ha-space-2)",
      }}>
        {onlineDevices.map((device) => (
          <FeedCell key={device.device_id} device={device} />
        ))}
      </div>
    </>
  );
}
