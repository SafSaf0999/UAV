/**
 * Device Detail page — full-page view for a single edge device.
 * Shows health, cert info, connection timeline, model info, detection history.
 *
 * Requirements: v2-4.1 through v2-4.7
 */

import React from "react";
import { useParams, useNavigate } from "react-router-dom";
import { useDevice } from "../api/websocket";
import { Card } from "../components/ui/Card";
import { Badge } from "../components/ui/Badge";
import { StatChip } from "../components/ui/StatChip";
import { HealthGauges } from "../components/HealthGauges";
import { formatUptime } from "../utils/formatUptime";
import { getClassColor } from "../utils/classColors";

export function DeviceDetailPage() {
  const { device_id } = useParams<{ device_id: string }>();
  const navigate = useNavigate();
  const device = useDevice(device_id ?? "");

  if (!device) {
    return (
      <div style={{ padding: "var(--ha-space-6)", color: "var(--secondary-text-color)" }}>
        Device <code>{device_id}</code> not found.{" "}
        <button onClick={() => navigate("/")} style={linkBtnStyle}>← Back</button>
      </div>
    );
  }

  const health = device.health;
  const cert = device.cert_info;
  const certExpiringSoon = cert ? isExpiringSoon(cert.expires_at) : false;

  return (
    <div style={{ padding: "var(--ha-space-6)", display: "flex", flexDirection: "column", gap: "var(--ha-space-4)" }}>
      {/* Back button */}
      <button onClick={() => navigate(-1)} style={linkBtnStyle}>← Back</button>

      {/* Header */}
      <Card>
        <div style={{ display: "flex", alignItems: "center", gap: "var(--ha-space-3)" }}>
          <Badge variant={device.status === "online" ? "online" : device.status === "offline" ? "offline" : "unknown"} />
          <h1 style={{ margin: 0, fontFamily: "var(--ha-font-family-code)", fontSize: "var(--ha-font-size-2xl)", fontWeight: "var(--ha-font-weight-bold)" as any }}>
            {device.device_id}
          </h1>
          {health && (
            <span style={{ fontSize: "var(--ha-font-size-s)", color: "var(--secondary-text-color)" }}>
              Uptime: {formatUptime(health.uptime_s)}
            </span>
          )}
        </div>
      </Card>

      {/* Health metrics */}
      {health && (
        <Card>
          <SectionTitle>Health Metrics</SectionTitle>
          <HealthGauges health={health} />
        </Card>
      )}

      {/* Authorization / cert info */}
      <Card>
        <SectionTitle>
          Authorization
          {certExpiringSoon && (
            <StatChip label="Expiring soon" color="var(--uav-color-warning)" style={{ marginLeft: "var(--ha-space-2)" }} />
          )}
        </SectionTitle>
        {cert ? (
          <div style={{ display: "flex", flexDirection: "column", gap: "var(--ha-space-2)" }}>
            <Row label="CN" value={cert.cn} />
            <Row label="Issuer" value={cert.issuer} />
            <Row label="Expires" value={new Date(cert.expires_at).toLocaleDateString()} />
          </div>
        ) : (
          <span style={{ color: "var(--secondary-text-color)", fontSize: "var(--ha-font-size-s)" }}>
            No certificate info available.
          </span>
        )}
        {device.last_status_ts && (
          <Row label="Last Auth" value={new Date(device.last_status_ts).toLocaleString()} />
        )}
      </Card>

      {/* Model info */}
      <Card>
        <SectionTitle>Model</SectionTitle>
        <div style={{ display: "flex", flexDirection: "column", gap: "var(--ha-space-2)" }}>
          <Row label="Active Model" value={device.active_model ?? "—"} />
          {device.last_tracking?.active_model && device.last_tracking.active_model !== device.active_model && (
            <Row label="Last Seen Model" value={device.last_tracking.active_model} />
          )}
        </div>
      </Card>

      {/* Detection history */}
      <Card>
        <SectionTitle>Recent Detections</SectionTitle>
        {device.last_tracking?.detections && device.last_tracking.detections.length > 0 ? (
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "var(--ha-font-size-s)" }}>
            <thead>
              <tr style={{ borderBottom: "1px solid var(--divider-color)", textAlign: "left" }}>
                <th style={thStyle}>Time</th>
                <th style={thStyle}>Label</th>
                <th style={thStyle}>Confidence</th>
                <th style={thStyle}>Track ID</th>
              </tr>
            </thead>
            <tbody>
              {device.last_tracking.detections.slice(0, 50).map((det, i) => (
                <tr key={i} style={{ borderBottom: "1px solid var(--divider-color)" }}>
                  <td style={tdStyle}>{new Date(device.last_tracking!.timestamp).toLocaleTimeString()}</td>
                  <td style={tdStyle}>
                    <StatChip label={det.label} color={getClassColor(det.label)} />
                  </td>
                  <td style={tdStyle}>{(det.confidence * 100).toFixed(0)}%</td>
                  <td style={tdStyle}>#{det.track_id}</td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <span style={{ color: "var(--secondary-text-color)", fontSize: "var(--ha-font-size-s)" }}>No recent detections.</span>
        )}
      </Card>
    </div>
  );
}

function isExpiringSoon(expiresAt: string): boolean {
  try {
    const exp = new Date(expiresAt).getTime();
    const thirtyDays = 30 * 24 * 60 * 60 * 1000;
    return exp - Date.now() < thirtyDays;
  } catch {
    return false;
  }
}

function SectionTitle({ children }: { children: React.ReactNode }) {
  return (
    <div style={{ fontSize: "var(--ha-font-size-s)", fontWeight: "var(--ha-font-weight-medium)" as any, color: "var(--secondary-text-color)", textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: "var(--ha-space-3)" }}>
      {children}
    </div>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div style={{ display: "flex", gap: "var(--ha-space-3)", alignItems: "baseline" }}>
      <span style={{ fontSize: "var(--ha-font-size-xs)", color: "var(--secondary-text-color)", minWidth: 120 }}>{label}</span>
      <span style={{ fontSize: "var(--ha-font-size-m)", fontFamily: "var(--ha-font-family-code)" }}>{value}</span>
    </div>
  );
}

const linkBtnStyle: React.CSSProperties = {
  background: "transparent",
  border: "none",
  color: "var(--primary-color)",
  cursor: "pointer",
  fontSize: "var(--ha-font-size-s)",
  padding: 0,
  fontFamily: "var(--ha-font-family-body)",
};

const thStyle: React.CSSProperties = { padding: "var(--ha-space-2) var(--ha-space-3)", color: "var(--secondary-text-color)" };
const tdStyle: React.CSSProperties = { padding: "var(--ha-space-2) var(--ha-space-3)" };
