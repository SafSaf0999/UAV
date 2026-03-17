/**
 * Command API with 5-second timeout warning.
 *
 * After issuing any command, if no acknowledgement status update is received
 * via WebSocket within 5s, displays a timeout warning toast.
 *
 * Requirements: 7.5
 */

import type { CommandPayload, PtzCommand } from "../types";
import { deviceStore } from "./websocket";

const COMMAND_TIMEOUT_MS = 5_000;

// ---------------------------------------------------------------------------
// Toast notification (minimal, no external dependency)
// ---------------------------------------------------------------------------

function showToast(message: string, type: "warning" | "error" = "warning") {
  const toast = document.createElement("div");
  toast.textContent = message;
  toast.style.cssText = `
    position: fixed; bottom: 24px; right: 24px; z-index: 9999;
    background: ${type === "warning" ? "#f59e0b" : "#ef4444"};
    color: #000; padding: 12px 20px; border-radius: 8px;
    font-size: 14px; font-family: sans-serif; box-shadow: 0 4px 12px rgba(0,0,0,0.3);
    animation: fadeIn 0.2s ease;
  `;
  document.body.appendChild(toast);
  setTimeout(() => toast.remove(), 5000);
}

// ---------------------------------------------------------------------------
// Command with ack timeout
// ---------------------------------------------------------------------------

async function sendCommandWithTimeout(
  device_id: string,
  endpoint: string,
  body: object,
  ackCheck: (device_id: string) => boolean
): Promise<void> {
  // Send the command
  const resp = await fetch(endpoint, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });

  if (!resp.ok) {
    showToast(`Command failed: HTTP ${resp.status}`, "error");
    return;
  }

  // Wait for acknowledgement via WebSocket state update
  const startTs = Date.now();
  const checkInterval = 200;

  await new Promise<void>((resolve) => {
    const interval = setInterval(() => {
      if (ackCheck(device_id)) {
        clearInterval(interval);
        resolve();
        return;
      }
      if (Date.now() - startTs >= COMMAND_TIMEOUT_MS) {
        clearInterval(interval);
        showToast(
          `⚠ Command timeout: no acknowledgement from ${device_id} within 5s`,
          "warning"
        );
        resolve();
      }
    }, checkInterval);
  });
}

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

export async function sendCommand(device_id: string, payload: CommandPayload): Promise<void> {
  const prevModel = deviceStore.getDevices()[device_id]?.active_model;

  await sendCommandWithTimeout(
    device_id,
    `/api/command/${device_id}`,
    payload,
    (id) => {
      const device = deviceStore.getDevices()[id];
      if (!device) return false;
      // For switch_model: ack when active_model changes
      if (payload.action === "switch_model" && payload.model_name) {
        return device.active_model === payload.model_name;
      }
      // For start/stop_stream: ack when status is still online (device responded)
      return device.status === "online";
    }
  );
}

export async function sendPtzCommand(device_id: string, cmd: PtzCommand): Promise<void> {
  await sendCommandWithTimeout(
    device_id,
    `/api/ptz/${device_id}`,
    cmd,
    (id) => {
      const device = deviceStore.getDevices()[id];
      return device?.last_ptz_status?.last_command === cmd.command;
    }
  );
}
