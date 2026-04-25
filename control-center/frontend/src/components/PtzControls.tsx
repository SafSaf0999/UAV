/**
 * PTZ controls — joystick + discrete buttons for pan/tilt/zoom.
 *
 * Requirements: 13.1, 13.2, 13.3
 */

import React, { useState } from "react";
import { Joystick } from "react-joystick-component";
import type { JoystickShape } from "react-joystick-component";

type IJoystickUpdateEvent = {
  type: string;
  x: number | null;
  y: number | null;
  direction: string | null;
  distance: number | null;
};
import type { PtzCommand } from "../types";

interface Props {
  device_id: string;
  compact?: boolean;
}

async function sendPtz(device_id: string, cmd: PtzCommand): Promise<void> {
  await fetch(`/api/ptz/${device_id}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(cmd),
  });
}

export function PtzControls({ device_id, compact = false }: Props) {
  const [zoomInput, setZoomInput] = useState("1.0");
  const [panInput, setPanInput] = useState("0");
  const [tiltInput, setTiltInput] = useState("0");

  const handleJoystick = (event: IJoystickUpdateEvent) => {
    if (!event.x || !event.y) return;
    const threshold = 0.3;
    const ax = event.x / 50; // normalise to -1..1
    const ay = event.y / 50;

    if (Math.abs(ax) > Math.abs(ay)) {
      sendPtz(device_id, {
        command: ax > threshold ? "pan_right" : "pan_left",
        params: { speed: Math.abs(ax) },
      });
    } else {
      sendPtz(device_id, {
        command: ay > threshold ? "tilt_up" : "tilt_down",
        params: { speed: Math.abs(ay) },
      });
    }
  };

  const handleStop = () => sendPtz(device_id, { command: "stop" });
  const handleHome = () => sendPtz(device_id, { command: "home" });
  const handleZoomIn = () => sendPtz(device_id, { command: "zoom_in", params: { step: 0.5 } });
  const handleZoomOut = () => sendPtz(device_id, { command: "zoom_out", params: { step: 0.5 } });

  const handleAbsolutePanTilt = () => {
    sendPtz(device_id, {
      command: "pan_tilt_absolute",
      params: { pan: parseFloat(panInput), tilt: parseFloat(tiltInput) },
    });
  };

  const handleAbsoluteZoom = () => {
    sendPtz(device_id, {
      command: "zoom_absolute",
      params: { zoom: parseFloat(zoomInput) },
    });
  };

  if (compact) {
    return (
      <div style={{ display: "flex", gap: 4 }}>
        <button onClick={handleZoomIn} style={btnStyle} title="Zoom In" aria-label="Zoom in">+</button>
        <button onClick={handleZoomOut} style={btnStyle} title="Zoom Out" aria-label="Zoom out">−</button>
        <button onClick={handleHome} style={btnStyle} title="Home" aria-label="Home">⌂</button>
      </div>
    );
  }

  return (
    <div style={{ padding: 16, background: "#1f2937", borderRadius: 8, color: "#f9fafb" }}>
      <div style={{ fontWeight: 600, marginBottom: 12 }}>PTZ Controls — {device_id}</div>

      {/* Joystick */}
      <div style={{ display: "flex", justifyContent: "center", marginBottom: 12 }}>
        <Joystick
          size={100}
          baseColor="#374151"
          stickColor="#3b82f6"
          move={handleJoystick}
          stop={handleStop}
          throttle={100}
        />
      </div>

      {/* Zoom buttons */}
      <div style={{ display: "flex", gap: 8, justifyContent: "center", marginBottom: 12 }}>
        <button onClick={handleZoomOut} style={btnStyle} aria-label="Zoom out">Zoom −</button>
        <button onClick={handleZoomIn} style={btnStyle} aria-label="Zoom in">Zoom +</button>
        <button onClick={handleStop} style={btnStyle} aria-label="Stop">Stop</button>
        <button onClick={handleHome} style={btnStyle} aria-label="Home">Home</button>
      </div>

      {/* Absolute zoom */}
      <div style={{ display: "flex", gap: 8, alignItems: "center", marginBottom: 8 }}>
        <label style={{ fontSize: 12, width: 80 }}>Zoom abs:</label>
        <input
          type="number"
          value={zoomInput}
          onChange={(e) => setZoomInput(e.target.value)}
          min={1}
          max={8}
          step={0.5}
          style={inputStyle}
          aria-label="Absolute zoom level"
        />
        <button onClick={handleAbsoluteZoom} style={btnStyle}>Set</button>
      </div>

      {/* Absolute pan/tilt */}
      <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
        <label style={{ fontSize: 12, width: 80 }}>Pan/Tilt:</label>
        <input
          type="number"
          value={panInput}
          onChange={(e) => setPanInput(e.target.value)}
          placeholder="pan"
          style={{ ...inputStyle, width: 60 }}
          aria-label="Absolute pan angle"
        />
        <input
          type="number"
          value={tiltInput}
          onChange={(e) => setTiltInput(e.target.value)}
          placeholder="tilt"
          style={{ ...inputStyle, width: 60 }}
          aria-label="Absolute tilt angle"
        />
        <button onClick={handleAbsolutePanTilt} style={btnStyle}>Set</button>
      </div>
    </div>
  );
}

const btnStyle: React.CSSProperties = {
  background: "#374151",
  color: "#f9fafb",
  border: "1px solid #4b5563",
  padding: "6px 12px",
  borderRadius: 4,
  cursor: "pointer",
  fontSize: 13,
};

const inputStyle: React.CSSProperties = {
  background: "#111827",
  border: "1px solid #374151",
  color: "#f9fafb",
  padding: "4px 8px",
  borderRadius: 4,
  width: 80,
};
