/**
 * Map view — Leaflet.js map with device markers and detection alerts.
 *
 * Requirements: 12.1–12.8, 12.10, 14.3
 */

import React, { useEffect, useRef, useState } from "react";
import { MapContainer, TileLayer, Marker, Popup } from "react-leaflet";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import { useDevices } from "../api/websocket";
import type { DeviceState } from "../types";
const ALERT_CLEAR_MS = 10_000; // auto-clear alert after 10s

// ---------------------------------------------------------------------------
// Custom marker icons
// ---------------------------------------------------------------------------

function makeIcon(color: string, shape: "circle" | "diamond" = "circle") {
  const svg =
    shape === "diamond"
      ? `<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 20 20">
           <polygon points="10,1 19,10 10,19 1,10" fill="${color}" stroke="#fff" stroke-width="1.5"/>
         </svg>`
      : `<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 20 20">
           <circle cx="10" cy="10" r="8" fill="${color}" stroke="#fff" stroke-width="1.5"/>
         </svg>`;
  return L.divIcon({
    html: svg,
    className: "",
    iconSize: [20, 20],
    iconAnchor: [10, 10],
  });
}

const ICON_ONLINE = makeIcon("#22c55e");
const ICON_OFFLINE = makeIcon("#9ca3af");
const ICON_ALERT = makeIcon("#ef4444");
const ICON_RADAR = makeIcon("#f59e0b", "diamond");

// ---------------------------------------------------------------------------
// Alert state per device
// ---------------------------------------------------------------------------

interface AlertState {
  device_id: string;
  timestamp: string;
  detection_count: number;
  timer: ReturnType<typeof setTimeout>;
}

// ---------------------------------------------------------------------------
// MapView component
// ---------------------------------------------------------------------------

export function MapView() {
  const devices = useDevices();
  const [alerts, setAlerts] = useState<Record<string, AlertState>>({});
  const alertsRef = useRef(alerts);
  alertsRef.current = alerts;

  // Detect new detections and set alerts
  useEffect(() => {
    for (const device of Object.values(devices)) {
      if (device.detection_count > 0 && device.last_tracking) {
        const existing = alertsRef.current[device.device_id];
        const ts = device.last_tracking.timestamp;

        if (!existing || existing.timestamp !== ts) {
          if (existing) clearTimeout(existing.timer);

          const timer = setTimeout(() => {
            setAlerts((prev) => {
              const next = { ...prev };
              delete next[device.device_id];
              return next;
            });
          }, ALERT_CLEAR_MS);

          setAlerts((prev) => ({
            ...prev,
            [device.device_id]: {
              device_id: device.device_id,
              timestamp: ts,
              detection_count: device.detection_count,
              timer,
            },
          }));
        }
      }
    }
  }, [devices]);

  const allDevices = Object.values(devices);
  const located = allDevices.filter((d) => d.lat !== null && d.lon !== null);
  const unlocated = allDevices.filter((d) => d.lat === null || d.lon === null);

  const center: [number, number] =
    located.length > 0 ? [located[0].lat!, located[0].lon!] : [20, 0];
  const zoom = located.length > 0 ? 13 : 2;

  return (
    <div style={{ position: "relative", height: "calc(100vh - 60px)" }}>
      <MapContainer
        center={center}
        zoom={zoom}
        style={{ height: "100%", width: "100%", borderRadius: 8 }}
      >
        <TileLayer
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
          subdomains={["a", "b", "c"]}
        />
        {located.map((device) => (
          <DeviceMarker
            key={device.device_id}
            device={device}
            alert={alerts[device.device_id]}
            onDismiss={() =>
              setAlerts((prev: Record<string, AlertState>) => {
                const next = { ...prev };
                if (next[device.device_id]) clearTimeout(next[device.device_id].timer);
                delete next[device.device_id];
                return next;
              })
            }
          />
        ))}
        {allDevices.length === 0 && <NoDevicesOverlay />}
      </MapContainer>

      {/* Unlocated devices panel */}
      {unlocated.length > 0 && (
        <div style={{
          position: "absolute", bottom: 24, left: 12, zIndex: 1000,
          background: "rgba(15,23,42,0.88)", backdropFilter: "blur(6px)",
          border: "1px solid #334155", borderRadius: 8,
          padding: "10px 14px", minWidth: 200, maxWidth: 260,
        }}>
          <div style={{ color: "#94a3b8", fontSize: 11, marginBottom: 6, textTransform: "uppercase", letterSpacing: 1 }}>
            No GPS — {unlocated.length} device{unlocated.length > 1 ? "s" : ""}
          </div>
          {unlocated.map((d) => (
            <div key={d.device_id} style={{
              display: "flex", alignItems: "center", gap: 8,
              padding: "4px 0", borderTop: "1px solid #1e293b",
            }}>
              <span style={{
                width: 8, height: 8, borderRadius: "50%", flexShrink: 0,
                background: d.status === "online" ? "#22c55e" : "#9ca3af",
              }} />
              <span style={{ color: "#f1f5f9", fontSize: 13, flex: 1 }}>{d.device_id}</span>
              <span style={{ color: "#64748b", fontSize: 11 }}>{d.status}</span>
            </div>
          ))}
          <div style={{ color: "#475569", fontSize: 10, marginTop: 6 }}>
            Set lat/lon in edge config.yaml
          </div>
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// No-devices overlay (auto-hides after 3s)
// ---------------------------------------------------------------------------

function NoDevicesOverlay() {
  const [visible, setVisible] = useState(true);
  useEffect(() => {
    const t = setTimeout(() => setVisible(false), 3000);
    return () => clearTimeout(t);
  }, []);

  if (!visible) return null;
  return (
    <div style={{
      position: "absolute", top: 0, left: 0, right: 0, bottom: 0,
      display: "flex", alignItems: "center", justifyContent: "center",
      pointerEvents: "none", zIndex: 1000,
      transition: "opacity 0.5s",
    }}>
      <div style={{
        background: "rgba(15,23,42,0.75)", color: "#94a3b8",
        padding: "8px 18px", borderRadius: 8, fontSize: 13,
        backdropFilter: "blur(4px)",
      }}>
        No devices connected — map ready
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Individual device marker
// ---------------------------------------------------------------------------

function DeviceMarker({
  device,
  alert,
  onDismiss,
}: {
  device: DeviceState;
  alert?: AlertState;
  onDismiss: () => void;
}) {
  const isRadar = device.last_tracking?.source === "radar";
  let icon = isRadar ? ICON_RADAR : device.status === "online" ? ICON_ONLINE : ICON_OFFLINE;
  if (alert) icon = ICON_ALERT;

  return (
    <Marker position={[device.lat!, device.lon!]} icon={icon}>
      <Popup eventHandlers={{ remove: onDismiss }}>
        <div style={{ minWidth: 160 }}>
          <strong>{device.device_id}</strong>
          {alert && (
            <div style={{ marginTop: 6, color: "#ef4444" }}>
              <div>⚠ Detection Alert</div>
              <div style={{ fontSize: 12, color: "#6b7280" }}>
                {new Date(alert.timestamp).toUTCString()}
              </div>
              <div>Detections: {alert.detection_count}</div>
            </div>
          )}
          {!alert && (
            <div style={{ marginTop: 4, color: "#9ca3af", fontSize: 12 }}>
              Status: {device.status}
            </div>
          )}
        </div>
      </Popup>
    </Marker>
  );
}
