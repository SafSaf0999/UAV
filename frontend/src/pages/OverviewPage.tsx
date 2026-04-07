/**
 * Overview page — 4 summary stat cards + grid of DeviceCards.
 */

import React from "react";
import { useDevices } from "../api/websocket";
import { Card } from "../components/ui/Card";
import { DeviceCard } from "../components/DeviceCard";

interface StatCardProps {
  label: string;
  value: number | string;
  color?: string;
}

function StatCard({ label, value, color = "var(--primary-color)" }: StatCardProps) {
  return (
    <Card>
      <div style={{ fontSize: "var(--ha-font-size-3xl)", fontWeight: "var(--ha-font-weight-bold)" as any, color }}>
        {value}
      </div>
      <div style={{ fontSize: "var(--ha-font-size-s)", color: "var(--secondary-text-color)", marginTop: "var(--ha-space-1)" }}>
        {label}
      </div>
    </Card>
  );
}

export function OverviewPage() {
  const devices = useDevices();
  const deviceList = Object.values(devices);

  const totalDevices = deviceList.length;
  const onlineNow = deviceList.filter((d) => d.status === "online").length;
  const activeDetections = deviceList.reduce((sum, d) => sum + d.detection_count, 0);
  const alertsToday = deviceList.filter((d) => d.detection_count > 0).length;

  return (
    <div style={{ padding: "var(--ha-space-6)" }}>
      {/* Summary stat cards */}
      <div style={{
        display: "grid",
        gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))",
        gap: "var(--ha-space-4)",
        marginBottom: "var(--ha-space-6)",
      }}>
        <StatCard label="Total Devices" value={totalDevices} color="var(--secondary-text-color)" />
        <StatCard label="Online Now" value={onlineNow} color="var(--uav-color-online)" />
        <StatCard label="Active Detections" value={activeDetections} color="var(--uav-color-alert)" />
        <StatCard label="Devices Alerting" value={alertsToday} color="var(--uav-color-warning)" />
      </div>

      {/* Device grid */}
      {deviceList.length === 0 ? (
        <p style={{ color: "var(--secondary-text-color)" }}>No devices connected.</p>
      ) : (
        <div style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fill, minmax(280px, 1fr))",
          gap: "var(--ha-space-4)",
        }}>
          {deviceList.map((device) => (
            <DeviceCard key={device.device_id} device={device} />
          ))}
        </div>
      )}
    </div>
  );
}
