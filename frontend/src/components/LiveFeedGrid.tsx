/**
 * Live feed grid — up to 4 WebRTC video streams.
 *
 * Each video connects to the signaling server to exchange SDP/ICE.
 * Shows a reconnect indicator on stream interruption.
 * Overlays PTZ controls when device has PTZ enabled.
 *
 * Requirements: 5.2, 5.3, 5.4, 5.5, 6.3, 6.4
 */

import React, { useEffect, useRef, useState } from "react";
import { useDevices } from "../api/websocket";
import type { DeviceState } from "../types";
import { TrackingOverlay } from "./TrackingOverlay";
import { PtzControls } from "./PtzControls";

declare const __SIGNALING_URL__: string;
const SIGNALING_URL = __SIGNALING_URL__;

const MAX_FEEDS = 4;

// ---------------------------------------------------------------------------
// WebRTC peer connection per device
// ---------------------------------------------------------------------------

function useWebRTCStream(device_id: string, videoRef: React.RefObject<HTMLVideoElement>) {
  const [connected, setConnected] = useState(false);
  const [error, setError] = useState(false);
  const pcRef = useRef<RTCPeerConnection | null>(null);
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    let cancelled = false;

    function connect() {
      const ws = new WebSocket(SIGNALING_URL);
      wsRef.current = ws;

      const pc = new RTCPeerConnection({
        iceServers: [{ urls: "stun:stun.l.google.com:19302" }],
      });
      pcRef.current = pc;

      pc.ontrack = (event) => {
        if (videoRef.current && event.streams[0]) {
          videoRef.current.srcObject = event.streams[0];
          setConnected(true);
          setError(false);
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
          setConnected(false);
          setError(true);
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
        setConnected(false);
        if (!cancelled) {
          setError(true);
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

  return { connected, error };
}

// ---------------------------------------------------------------------------
// Single feed cell
// ---------------------------------------------------------------------------

function FeedCell({ device }: { device: DeviceState }) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const { connected, error } = useWebRTCStream(device.device_id, videoRef);
  const hasPtz = device.last_ptz_status !== null || device.active_model !== null;

  return (
    <div style={{ position: "relative", background: "#000", borderRadius: 6, overflow: "hidden", aspectRatio: "16/9" }}>
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
          containerRef={videoRef as React.RefObject<HTMLElement>}
        />
      )}

      {/* Reconnect indicator */}
      {error && !connected && (
        <div style={{
          position: "absolute", inset: 0, display: "flex", alignItems: "center",
          justifyContent: "center", background: "rgba(0,0,0,0.7)", color: "#ef4444",
          fontSize: 14,
        }}>
          ⚠ Stream interrupted — reconnecting…
        </div>
      )}

      {/* Device label */}
      <div style={{
        position: "absolute", top: 8, left: 8, background: "rgba(0,0,0,0.6)",
        color: "#f9fafb", fontSize: 12, padding: "2px 8px", borderRadius: 4,
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

// ---------------------------------------------------------------------------
// LiveFeedGrid
// ---------------------------------------------------------------------------

export function LiveFeedGrid() {
  const devices = useDevices();
  const onlineDevices = Object.values(devices)
    .filter((d) => d.status === "online")
    .slice(0, MAX_FEEDS);

  if (onlineDevices.length === 0) {
    return (
      <div style={{ color: "#9ca3af", padding: 24 }}>No online devices to stream.</div>
    );
  }

  return (
    <div style={{
      display: "grid",
      gridTemplateColumns: onlineDevices.length === 1 ? "1fr" : "repeat(2, 1fr)",
      gap: 8,
    }}>
      {onlineDevices.map((device) => (
        <FeedCell key={device.device_id} device={device} />
      ))}
    </div>
  );
}
