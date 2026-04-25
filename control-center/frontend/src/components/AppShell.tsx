/**
 * AppShell — wraps Sidebar + TopBar + page content area.
 */

import React from "react";
import { Routes, Route } from "react-router-dom";
import { Sidebar } from "./Sidebar";
import { TopBar } from "./TopBar";
import { DeviceDashboard } from "./DeviceDashboard";
import { MapView } from "./MapView";
import { LiveFeedGrid } from "./LiveFeedGrid";
import { PtzControls } from "./PtzControls";
import { useDevices } from "../api/websocket";
import { OverviewPage } from "../pages/OverviewPage";
import { DeviceDetailPage } from "../pages/DeviceDetailPage";
import { LogsPage } from "../pages/LogsPage";
import { SettingsPage } from "../pages/SettingsPage";

// Placeholder pages — will be replaced by full implementations in later tasks
function PlaceholderPage({ title }: { title: string }) {
  return (
    <div style={{ padding: "var(--ha-space-6)", color: "var(--primary-text-color)" }}>
      <h2 style={{ margin: 0, fontFamily: "var(--ha-font-family-body)" }}>{title}</h2>
      <p style={{ color: "var(--secondary-text-color)" }}>Coming soon.</p>
    </div>
  );
}

function PtzPage() {
  const devices = useDevices();
  const onlineIds = Object.keys(devices).filter((id) => devices[id].status === "online");
  const [selected, setSelected] = React.useState<string>(onlineIds[0] ?? "");

  if (onlineIds.length === 0) {
    return (
      <div style={{ padding: "var(--ha-space-6)", color: "var(--secondary-text-color)" }}>
        No online devices.
      </div>
    );
  }

  return (
    <div style={{ padding: "var(--ha-space-6)" }}>
      <div style={{ marginBottom: "var(--ha-space-3)" }}>
        <label style={{ color: "var(--secondary-text-color)", marginRight: "var(--ha-space-2)" }}>
          Device:
        </label>
        <select
          value={selected}
          onChange={(e) => setSelected(e.target.value)}
          style={{
            background: "var(--secondary-background-color)",
            border: "1px solid var(--divider-color)",
            color: "var(--primary-text-color)",
            padding: "4px 8px",
            borderRadius: "var(--ha-border-radius-md)",
          }}
        >
          {onlineIds.map((id) => <option key={id} value={id}>{id}</option>)}
        </select>
      </div>
      {selected && <PtzControls device_id={selected} />}
    </div>
  );
}

interface AppShellProps {
  wsConnected: boolean;
}

export function AppShell({ wsConnected }: AppShellProps) {
  return (
    <div style={{ display: "flex", height: "100vh", overflow: "hidden" }}>
      <Sidebar />
      <div style={{ flex: 1, display: "flex", flexDirection: "column", overflow: "hidden" }}>
        <TopBar wsConnected={wsConnected} />
        <main style={{ flex: 1, overflowY: "auto" }}>
          <Routes>
            <Route path="/" element={<OverviewPage />} />
            <Route path="/map" element={<MapView />} />
            <Route path="/feeds" element={<div style={{ padding: "var(--ha-space-4)" }}><LiveFeedGrid /></div>} />
            <Route path="/devices" element={<OverviewPage />} />
            <Route path="/devices/:device_id" element={<DeviceDetailPage />} />
            <Route path="/ptz" element={<PtzPage />} />
            <Route path="/logs" element={<LogsPage />} />
            <Route path="/settings" element={<SettingsPage />} />
          </Routes>
        </main>
      </div>
    </div>
  );
}
