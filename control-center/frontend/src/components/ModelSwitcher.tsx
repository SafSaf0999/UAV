/**
 * Model switcher — per-device dropdown for switching active model profile.
 *
 * Requirements: 18.8, 18.9
 */

import React, { useEffect, useState } from "react";
import { useDevice } from "../api/websocket";
import type { ModelProfile } from "../types";

interface Props {
  device_id: string;
}

async function fetchProfiles(device_id: string): Promise<ModelProfile[]> {
  try {
    const resp = await fetch(`/api/devices/${device_id}`);
    if (!resp.ok) return [];
    const state = await resp.json();
    // Model profiles are embedded in the device state if the aggregation
    // service exposes them; otherwise fall back to the active model name only.
    return state.model_profiles ?? [];
  } catch {
    return [];
  }
}

async function switchModel(device_id: string, model_name: string): Promise<void> {
  await fetch(`/api/command/${device_id}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ action: "switch_model", model_name }),
  });
}

export function ModelSwitcher({ device_id }: Props) {
  const device = useDevice(device_id);
  const [profiles, setProfiles] = useState<ModelProfile[]>([]);
  const [selected, setSelected] = useState<string>("");
  const [switching, setSwitching] = useState(false);

  useEffect(() => {
    fetchProfiles(device_id).then((p) => {
      setProfiles(p);
    });
  }, [device_id]);

  useEffect(() => {
    if (device?.active_model) {
      setSelected(device.active_model);
    }
  }, [device?.active_model]);

  const handleSwitch = async () => {
    if (!selected || selected === device?.active_model) return;
    setSwitching(true);
    await switchModel(device_id, selected);
    setSwitching(false);
  };

  if (!device) return null;

  return (
    <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
      <span style={{ fontSize: 13, color: "#9ca3af" }}>Model:</span>

      {profiles.length > 0 ? (
        <select
          value={selected}
          onChange={(e) => setSelected(e.target.value)}
          style={{
            background: "#1f2937",
            border: "1px solid #374151",
            color: "#f9fafb",
            padding: "4px 8px",
            borderRadius: 4,
            fontSize: 13,
          }}
          aria-label={`Select model for ${device_id}`}
        >
          {profiles.map((p) => (
            <option key={p.name} value={p.name}>
              {p.name} ({p.camera_mode})
            </option>
          ))}
        </select>
      ) : (
        <input
          type="text"
          value={selected}
          onChange={(e) => setSelected(e.target.value)}
          placeholder="model name"
          style={{
            background: "#1f2937",
            border: "1px solid #374151",
            color: "#f9fafb",
            padding: "4px 8px",
            borderRadius: 4,
            fontSize: 13,
            width: 140,
          }}
          aria-label={`Model name for ${device_id}`}
        />
      )}

      <button
        onClick={handleSwitch}
        disabled={switching || !selected || selected === device.active_model}
        style={{
          background: "#3b82f6",
          color: "#fff",
          border: "none",
          padding: "4px 12px",
          borderRadius: 4,
          cursor: "pointer",
          fontSize: 13,
          opacity: switching ? 0.6 : 1,
        }}
      >
        {switching ? "Switching…" : "Apply"}
      </button>

      <span style={{ fontSize: 12, color: "#6b7280" }}>
        Active: {device.active_model ?? "—"}
      </span>
    </div>
  );
}
