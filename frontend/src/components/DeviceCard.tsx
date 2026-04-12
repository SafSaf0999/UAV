/**
 * DeviceCard — HA-style card summarizing a single edge device.
 * Shows status, uptime, active model, per-class detection counts,
 * last detection timestamp, and quick-action buttons.
 */

import React from "react";
import { useNavigate } from "react-router-dom";
import { Card } from "./ui/Card";
import { Badge } from "./ui/Badge";
import { StatChip } from "./ui/StatChip";
import { getClassColor } from "../utils/classColors";
import { formatUptime } from "../utils/formatUptime";
import { sendCommand } from "../api/commands";
import type { DeviceState } from "../types";

interface Props {
  device: DeviceState;
}

export function DeviceCard({ device }: Props) {
  const navigate = useNavigate();
  const uptime = device.health?.uptime_s;
  const classCounts = device.class_counts ?? {};
  const hasDetections = Object.keys(classCounts).length > 0;

  const handleStream = (e: React.MouseEvent) => {
    e.stopPropagation();
    sendCommand(device.device_id, { action: "start_stream" });
  };

  const handleView = (e: React.MouseEvent) => {
    e.stopPropagation();
    navigate(`/devices/${device.device_id}`);
  };

  return (
    <Card
      style={{ cursor: "pointer", transition: "background 0.15s" }}
      onClick={() => navigate(`/devices/${device.device_id}`)}
    >
      {/* Header row */}
      <div style={{ display: "flex", alignItems: "center", gap: "var(--ha-space-2)", marginBottom: "var(--ha-space-3)" }}>
        <Badge
          variant={
            device.status === "online" ? "online"
            : device.status === "offline" ? "offline"
            : device.status === "health_timeout" ? "health_timeout"
            : "unknown"
          }
          label={device.status === "health_timeout" ? "Health Timeout" : undefined}
        />
        <span style={{
          flex: 1,
          fontWeight: "var(--ha-font-weight-bold)" as any,
          fontSize: "var(--ha-font-size-m)",
          fontFamily: "var(--ha-font-family-code)",
          overflow: "hidden",
          textOverflow: "ellipsis",
          whiteSpace: "nowrap",
        }}>
          {device.device_id}
        </span>
        {uptime !== undefined && (
          <span style={{ fontSize: "var(--ha-font-size-xs)", color: "var(--secondary-text-color)" }}>
            ↑ {formatUptime(uptime)}
          </span>
        )}
      </div>

      {/* Active model */}
      {device.active_model && (
        <div style={{ marginBottom: "var(--ha-space-2)" }}>
          <StatChip
            label={device.active_model}
            color="var(--primary-color)"
          />
        </div>
      )}

      {/* Detection counts */}
      <div style={{ display: "flex", flexWrap: "wrap", gap: "var(--ha-space-1)", marginBottom: "var(--ha-space-3)", minHeight: 22 }}>
        {hasDetections ? (
          Object.entries(classCounts).map(([label, count]) => (
            <StatChip
              key={label}
              label={label}
              count={count}
              color={getClassColor(label)}
            />
          ))
        ) : (
          <span style={{ fontSize: "var(--ha-font-size-xs)", color: "var(--disabled-text-color)" }}>
            No detections
          </span>
        )}
      </div>

      {/* Last detection timestamp */}
      {device.last_tracking?.timestamp && (
        <div style={{ fontSize: "var(--ha-font-size-xs)", color: "var(--secondary-text-color)", marginBottom: "var(--ha-space-3)" }}>
          Last: {new Date(device.last_tracking.timestamp).toLocaleTimeString()}
        </div>
      )}

      {/* Action buttons */}
      <div style={{ display: "flex", gap: "var(--ha-space-2)" }} onClick={(e) => e.stopPropagation()}>
        <button
          onClick={handleView}
          style={btnStyle}
          aria-label={`View details for ${device.device_id}`}
        >
          View
        </button>
        {device.status === "online" && (
          <button
            onClick={handleStream}
            style={{ ...btnStyle, background: "color-mix(in srgb, var(--primary-color) 15%, transparent)", color: "var(--primary-color)" }}
            aria-label={`Start stream for ${device.device_id}`}
          >
            Stream
          </button>
        )}
      </div>
    </Card>
  );
}

const btnStyle: React.CSSProperties = {
  background: "var(--secondary-background-color)",
  border: "1px solid var(--divider-color)",
  borderRadius: "var(--ha-border-radius-md)",
  color: "var(--secondary-text-color)",
  cursor: "pointer",
  fontSize: "var(--ha-font-size-s)",
  padding: "var(--ha-space-1) var(--ha-space-3)",
  fontFamily: "var(--ha-font-family-body)",
};
