/**
 * MapPanel — slide-in right panel shown when clicking a device marker.
 * Shows live feed, detection summary, health snapshot, sensor data,
 * PTZ mini-controls, and quick action buttons.
 *
 * Requirements: v2-6.1 through v2-6.10
 */

import React, { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import type { DeviceState } from "../types";
import { StatChip } from "./ui/StatChip";
import { Badge } from "./ui/Badge";
import { CompassRose } from "./CompassRose";
import { TrackingOverlay } from "./TrackingOverlay";
import { getClassColor } from "../utils/classColors";
import { formatUptime } from "../utils/formatUptime";
import { sendCommand, sendPtzCommand } from "../api/commands";

declare const __SIGNALING_URL__: string;

interface Props {
  device: DeviceState;
  onClose: () => void;
}

// Minimal inline WebRTC feed for the panel
function PanelFeed({ device_id }: { device_id: string }) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const [state, setState] = useState<"waiting" | "connected" | "error">("waiting");

  useEffect(() => {
    let cancelled = false;
    const ws = new WebSocket(__SIGNALING_URL__);
    const pc = new RTCPeerConnection({ iceServers: [{ urls: "stun:stun.l.google.com:19302" }] });

    pc.ontrack = (e) => {
      if (videoRef.current && e.streams[0]) {
        videoRef.current.srcObject = e.streams[0];
        setState("connected");
      }
    };
    pc.onicecandidate = (e) => {
      if (e.candidate && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ type: "ice_candidate", device_id, candidate: e.candidate.toJSON() }));
      }
    };
    pc.onconnectionstatechange = () => {
      if (pc.connectionState === "failed") setState("error");
    };
    ws.onopen = () => ws.send(JSON.stringify({ type: "register", device_id, role: "subscriber" }));
    ws.onmessage = async (e) => {
      const msg = JSON.parse(e.data);
      if (msg.type === "offer") {
        await pc.setRemoteDescription(new RTCSessionDescription({ type: msg.sdpType, sdp: msg.sdp }));
        const answer = await pc.createAnswer();
        await pc.setLocalDescription(answer);
        ws.send(JSON.stringify({ type: "answer", device_id, sdp: answer.sdp, sdpType: answer.type }));
      } else if (msg.type === "ice_candidate" && msg.candidate) {
        await pc.addIceCandidate(new RTCIceCandidate(msg.candidate));
      }
    };
    ws.onclose = () => { if (!cancelled) setState("error"); };

    // Request stream
    sendCommand(device_id, { action: "start_stream" });

    return () => {
      cancelled = true;
      pc.close();
      ws.close();
    };
  }, [device_id]);

  return (
    <div style={{ position: "relative", background: "#000", borderRadius: "var(--ha-border-radius-md)", overflow: "hidden", aspectRatio: "16/9" }}>
      <video ref={videoRef} autoPlay playsInline muted style={{ width: "100%", height: "100%", objectFit: "cover" }} />
      {state === "waiting" && (
        <div style={{ position: "absolute", inset: 0, display: "flex", alignItems: "center", justifyContent: "center", color: "var(--secondary-text-color)", fontSize: "var(--ha-font-size-xs)" }}>
          Waiting for stream…
        </div>
      )}
    </div>
  );
}

export function MapPanel({ device, onClose }: Props) {
  const navigate = useNavigate();
  const classCounts = device.class_counts ?? {};
  const health = device.health;
  const sensor = device.last_sensor;
  const hasPtz = Boolean(device.last_ptz_status);

  const copyLatLon = () => {
    if (device.lat !== null && device.lon !== null) {
      navigator.clipboard.writeText(`${device.lat}, ${device.lon}`);
    }
  };

  return (
    <div style={{
      position: "absolute",
      top: 0,
      right: 0,
      bottom: 0,
      width: "var(--map-panel-width, 360px)",
      maxWidth: "100vw",
      background: "var(--card-background-color)",
      borderLeft: "1px solid var(--divider-color)",
      overflowY: "auto",
      zIndex: 1000,
      display: "flex",
      flexDirection: "column",
      boxShadow: "var(--ha-box-shadow-l)",
    }}>
      {/* Header */}
      <div style={{ display: "flex", alignItems: "center", padding: "var(--ha-space-4)", borderBottom: "1px solid var(--divider-color)", gap: "var(--ha-space-2)", flexShrink: 0 }}>
        <Badge variant={device.status === "online" ? "online" : "offline"} />
        <span style={{ flex: 1, fontWeight: "var(--ha-font-weight-bold)" as any, fontFamily: "var(--ha-font-family-code)", fontSize: "var(--ha-font-size-m)" }}>
          {device.device_id}
        </span>
        {health && (
          <span style={{ fontSize: "var(--ha-font-size-xs)", color: "var(--secondary-text-color)" }}>
            ↑ {formatUptime(health.uptime_s)}
          </span>
        )}
        <button onClick={onClose} aria-label="Close panel" style={closeBtnStyle}>✕</button>
      </div>

      <div style={{ padding: "var(--ha-space-4)", display: "flex", flexDirection: "column", gap: "var(--ha-space-4)" }}>
        {/* Lat/lon */}
        {device.lat !== null && device.lon !== null && (
          <div style={{ display: "flex", alignItems: "center", gap: "var(--ha-space-2)" }}>
            <span style={{ fontSize: "var(--ha-font-size-xs)", color: "var(--secondary-text-color)", fontFamily: "var(--ha-font-family-code)" }}>
              {device.lat.toFixed(4)}, {device.lon.toFixed(4)}
            </span>
            <button onClick={copyLatLon} style={smallBtnStyle} aria-label="Copy coordinates">Copy</button>
          </div>
        )}

        {/* Live feed */}
        {device.status === "online" && <PanelFeed device_id={device.device_id} />}

        {/* Detection summary */}
        <Section title="Detections">
          {Object.keys(classCounts).length > 0 ? (
            <div style={{ display: "flex", flexWrap: "wrap", gap: "var(--ha-space-1)" }}>
              {Object.entries(classCounts).map(([label, count]) => (
                <StatChip key={label} label={label} count={count} color={getClassColor(label)} />
              ))}
            </div>
          ) : (
            <span style={{ fontSize: "var(--ha-font-size-xs)", color: "var(--disabled-text-color)" }}>No detections</span>
          )}
          {device.last_tracking?.timestamp && (
            <div style={{ fontSize: "var(--ha-font-size-xs)", color: "var(--secondary-text-color)", marginTop: "var(--ha-space-1)" }}>
              Last: {new Date(device.last_tracking.timestamp).toUTCString()}
            </div>
          )}
        </Section>

        {/* Health snapshot */}
        {health && (
          <Section title="Health">
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: "var(--ha-space-2)" }}>
              <Metric label="CPU" value={`${health.cpu_percent.toFixed(0)}%`} />
              <Metric label="Memory" value={`${health.memory_percent.toFixed(0)}%`} />
              <Metric label="FPS" value={health.inference_fps.toFixed(1)} />
            </div>
          </Section>
        )}

        {/* Sensor data */}
        {sensor && (
          <Section title="Sensor">
            <div style={{ display: "flex", alignItems: "center", gap: "var(--ha-space-4)" }}>
              <CompassRose bearing={sensor.compass_bearing_deg} size={72} />
              <div>
                <Metric label="Bearing" value={`${sensor.compass_bearing_deg.toFixed(1)}°`} />
                <Metric label="Pitch" value={`${sensor.pitch_deg.toFixed(1)}°`} />
              </div>
            </div>
          </Section>
        )}

        {/* PTZ mini-controls */}
        {hasPtz && (
          <Section title="PTZ">
            <div style={{ display: "flex", gap: "var(--ha-space-2)" }}>
              <button style={smallBtnStyle} onClick={() => sendPtzCommand(device.device_id, { command: "zoom_in", params: { step: 0.5 } })} aria-label="Zoom in">Zoom +</button>
              <button style={smallBtnStyle} onClick={() => sendPtzCommand(device.device_id, { command: "zoom_out", params: { step: 0.5 } })} aria-label="Zoom out">Zoom −</button>
              <button style={smallBtnStyle} onClick={() => sendPtzCommand(device.device_id, { command: "home" })} aria-label="Home">Home</button>
            </div>
          </Section>
        )}

        {/* Quick actions */}
        <Section title="Actions">
          <div style={{ display: "flex", flexWrap: "wrap", gap: "var(--ha-space-2)" }}>
            <button style={actionBtnStyle} onClick={() => sendCommand(device.device_id, { action: "start_stream" })}>Start Stream</button>
            <button style={actionBtnStyle} onClick={() => sendCommand(device.device_id, { action: "stop_stream" })}>Stop Stream</button>
            <button style={{ ...actionBtnStyle, background: "color-mix(in srgb, var(--primary-color) 15%, transparent)", color: "var(--primary-color)" }}
              onClick={() => navigate(`/devices/${device.device_id}`)}>
              View Full Detail →
            </button>
          </div>
        </Section>
      </div>
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div>
      <div style={{ fontSize: "var(--ha-font-size-xs)", color: "var(--secondary-text-color)", textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: "var(--ha-space-2)" }}>
        {title}
      </div>
      {children}
    </div>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 2 }}>
      <span style={{ fontSize: "var(--ha-font-size-xs)", color: "var(--secondary-text-color)" }}>{label}</span>
      <span style={{ fontSize: "var(--ha-font-size-m)", fontWeight: "var(--ha-font-weight-medium)" as any }}>{value}</span>
    </div>
  );
}

const closeBtnStyle: React.CSSProperties = {
  background: "transparent",
  border: "none",
  color: "var(--secondary-text-color)",
  cursor: "pointer",
  fontSize: "var(--ha-font-size-l)",
  padding: "var(--ha-space-1)",
  lineHeight: 1,
};

const smallBtnStyle: React.CSSProperties = {
  background: "var(--secondary-background-color)",
  border: "1px solid var(--divider-color)",
  borderRadius: "var(--ha-border-radius-sm)",
  color: "var(--secondary-text-color)",
  cursor: "pointer",
  fontSize: "var(--ha-font-size-xs)",
  padding: "2px var(--ha-space-2)",
  fontFamily: "var(--ha-font-family-body)",
};

const actionBtnStyle: React.CSSProperties = {
  background: "var(--secondary-background-color)",
  border: "1px solid var(--divider-color)",
  borderRadius: "var(--ha-border-radius-md)",
  color: "var(--secondary-text-color)",
  cursor: "pointer",
  fontSize: "var(--ha-font-size-s)",
  padding: "var(--ha-space-1) var(--ha-space-3)",
  fontFamily: "var(--ha-font-family-body)",
};
