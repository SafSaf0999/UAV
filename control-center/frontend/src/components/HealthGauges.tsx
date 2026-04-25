/**
 * HealthGauges — CPU and memory circular gauges + FPS and frame count.
 */

import React from "react";
import { Gauge } from "./ui/Gauge";
import type { HealthPayload } from "../types";

interface Props {
  health: HealthPayload;
}

export function HealthGauges({ health }: Props) {
  return (
    <div style={{ display: "flex", flexWrap: "wrap", gap: "var(--ha-space-6)", alignItems: "flex-start" }}>
      <Gauge value={health.cpu_percent} label="CPU" size={80} />
      <Gauge value={health.memory_percent} label="Memory" size={80} color="var(--uav-color-warning)" />
      <div style={{ display: "flex", flexDirection: "column", gap: "var(--ha-space-3)" }}>
        <Metric label="Inference FPS" value={health.inference_fps.toFixed(1)} />
        <Metric label="Frames Processed" value={health.frames_processed.toLocaleString()} />
        <Metric label="MQTT Reconnects" value={String(health.mqtt_reconnects)} />
        <Metric label="Camera Reconnects" value={String(health.camera_reconnects)} />
      </div>
    </div>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div style={{ fontSize: "var(--ha-font-size-xs)", color: "var(--secondary-text-color)" }}>{label}</div>
      <div style={{ fontSize: "var(--ha-font-size-l)", fontWeight: "var(--ha-font-weight-medium)" as any }}>{value}</div>
    </div>
  );
}
