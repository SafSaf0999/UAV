/**
 * UAV Control Center — main app shell.
 *
 * Tabs: Dashboard | Map | Live Feeds | PTZ
 */

import React, { useState } from "react";
import { DeviceProvider } from "./api/websocket";
import { DeviceDashboard } from "./components/DeviceDashboard";
import { MapView } from "./components/MapView";
import { LiveFeedGrid } from "./components/LiveFeedGrid";
import { PtzControls } from "./components/PtzControls";
import { useDevices } from "./api/websocket";

type Tab = "dashboard" | "map" | "feeds" | "ptz";

function PtzTab() {
  const devices = useDevices();
  const onlineIds = Object.keys(devices).filter((id) => devices[id].status === "online");
  const [selected, setSelected] = useState<string>(onlineIds[0] ?? "");

  if (onlineIds.length === 0) {
    return <p style={{ color: "#9ca3af" }}>No online devices.</p>;
  }

  return (
    <div>
      <div style={{ marginBottom: 12 }}>
        <label style={{ color: "#9ca3af", marginRight: 8 }}>Device:</label>
        <select
          value={selected}
          onChange={(e) => setSelected(e.target.value)}
          style={{ background: "#1f2937", border: "1px solid #374151", color: "#f9fafb", padding: "4px 8px", borderRadius: 4 }}
        >
          {onlineIds.map((id) => <option key={id} value={id}>{id}</option>)}
        </select>
      </div>
      {selected && <PtzControls device_id={selected} />}
    </div>
  );
}

function AppContent() {
  const [tab, setTab] = useState<Tab>("dashboard");

  const tabs: { id: Tab; label: string }[] = [
    { id: "dashboard", label: "Dashboard" },
    { id: "map", label: "Map" },
    { id: "feeds", label: "Live Feeds" },
    { id: "ptz", label: "PTZ" },
  ];

  return (
    <div style={{ minHeight: "100vh", background: "#0f172a", color: "#f9fafb", fontFamily: "system-ui, sans-serif" }}>
      {/* Header */}
      <header style={{ background: "#1e293b", padding: "12px 24px", display: "flex", alignItems: "center", gap: 24, borderBottom: "1px solid #334155" }}>
        <span style={{ fontWeight: 700, fontSize: 18, letterSpacing: 1 }}>Anti-UAV Control Center</span>
        <nav style={{ display: "flex", gap: 4 }}>
          {tabs.map((t) => (
            <button
              key={t.id}
              onClick={() => setTab(t.id)}
              style={{
                background: tab === t.id ? "#3b82f6" : "transparent",
                color: tab === t.id ? "#fff" : "#94a3b8",
                border: "none",
                padding: "6px 16px",
                borderRadius: 6,
                cursor: "pointer",
                fontSize: 14,
              }}
            >
              {t.label}
            </button>
          ))}
        </nav>
      </header>

      {/* Content */}
      <main style={{ padding: tab === "map" ? 0 : 24 }}>
        {tab === "dashboard" && <DeviceDashboard />}
        {tab === "map" && <MapView />}
        {tab === "feeds" && <LiveFeedGrid />}
        {tab === "ptz" && <PtzTab />}
      </main>
    </div>
  );
}

export default function App() {
  return (
    <DeviceProvider>
      <AppContent />
    </DeviceProvider>
  );
}
