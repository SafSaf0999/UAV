/**
 * Device Dashboard — table of all edge devices with status, model, detections.
 *
 * Requirements: 6.2, 6.5, 18.7, 18.8, 18.9
 */

import React from "react";
import { useDevices } from "../api/websocket";
import type { DeviceState } from "../types";

interface Props {
  onSelectDevice?: (device_id: string) => void;
}

async function switchModel(device_id: string, model_name: string): Promise<void> {
  await fetch(`/api/command/${device_id}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ action: "switch_model", model_name }),
  });
}

function StatusBadge({ status }: { status: DeviceState["status"] }) {
  const color = status === "online" ? "#22c55e" : "#9ca3af";
  return (
    <span
      style={{
        display: "inline-block",
        width: 10,
        height: 10,
        borderRadius: "50%",
        backgroundColor: color,
        marginRight: 6,
      }}
      aria-label={status}
    />
  );
}

export function DeviceDashboard({ onSelectDevice }: Props) {
  const devices = useDevices();
  const deviceList = Object.values(devices);

  if (deviceList.length === 0) {
    return <p style={{ color: "#9ca3af" }}>No devices connected.</p>;
  }

  return (
    <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 14 }}>
      <thead>
        <tr style={{ borderBottom: "1px solid #374151", textAlign: "left" }}>
          <th style={{ padding: "8px 12px" }}>Device</th>
          <th style={{ padding: "8px 12px" }}>Status</th>
          <th style={{ padding: "8px 12px" }}>Active Model</th>
          <th style={{ padding: "8px 12px" }}>Detections</th>
          <th style={{ padding: "8px 12px" }}>Switch Model</th>
        </tr>
      </thead>
      <tbody>
        {deviceList.map((device) => (
          <DeviceRow
            key={device.device_id}
            device={device}
            onSelect={onSelectDevice}
          />
        ))}
      </tbody>
    </table>
  );
}

function DeviceRow({
  device,
  onSelect,
}: {
  device: DeviceState;
  onSelect?: (id: string) => void;
}) {
  const [modelInput, setModelInput] = React.useState(device.active_model ?? "");

  const handleSwitch = async () => {
    if (modelInput && modelInput !== device.active_model) {
      await switchModel(device.device_id, modelInput);
    }
  };

  return (
    <tr
      style={{ borderBottom: "1px solid #1f2937", cursor: onSelect ? "pointer" : "default" }}
      onClick={() => onSelect?.(device.device_id)}
    >
      <td style={{ padding: "8px 12px", fontFamily: "monospace" }}>{device.device_id}</td>
      <td style={{ padding: "8px 12px" }}>
        <StatusBadge status={device.status} />
        {device.status}
      </td>
      <td style={{ padding: "8px 12px" }}>{device.active_model ?? "—"}</td>
      <td style={{ padding: "8px 12px" }}>{device.detection_count}</td>
      <td style={{ padding: "8px 12px" }} onClick={(e) => e.stopPropagation()}>
        <input
          type="text"
          value={modelInput}
          onChange={(e) => setModelInput(e.target.value)}
          placeholder="model name"
          style={{
            background: "#1f2937",
            border: "1px solid #374151",
            color: "#f9fafb",
            padding: "4px 8px",
            borderRadius: 4,
            marginRight: 6,
            width: 140,
          }}
          aria-label={`Switch model for ${device.device_id}`}
        />
        <button
          onClick={handleSwitch}
          disabled={!modelInput || modelInput === device.active_model}
          style={{
            background: "#3b82f6",
            color: "#fff",
            border: "none",
            padding: "4px 10px",
            borderRadius: 4,
            cursor: "pointer",
          }}
        >
          Switch
        </button>
      </td>
    </tr>
  );
}
