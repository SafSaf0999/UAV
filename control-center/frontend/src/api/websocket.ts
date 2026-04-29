/**
 * WebSocket client for aggregation service state updates.
 *
 * Connects to /ws, parses incoming DeviceState updates, and exposes
 * a simple event emitter interface + React context.
 */

import React, { createContext, useContext, useEffect, useRef, useState } from "react";
import type { DeviceState, WebSocketMessage } from "../types";
import { getToken, clearToken } from "../utils/auth";

declare const __AGGREGATION_WS_URL__: string;

function _wsUrl(): string {
  // If built with an explicit URL, use it. Otherwise derive from window.location
  // so the frontend works on any host (local, remote, different port).
  const configured = __AGGREGATION_WS_URL__;
  const base = configured
    ? configured
    : `${window.location.protocol === "https:" ? "wss" : "ws"}://${window.location.host}/ws`;
  const token = getToken();
  return token ? `${base}?token=${encodeURIComponent(token)}` : base;
}

type Listener = (devices: Record<string, DeviceState>) => void;

class DeviceStateStore {
  private devices: Record<string, DeviceState> = {};
  private listeners: Set<Listener> = new Set();
  private ws: WebSocket | null = null;
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;

  connect(): void {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) return;
    this.ws = new WebSocket(_wsUrl());

    this.ws.onmessage = (event) => {
      try {
        const msg: WebSocketMessage = JSON.parse(event.data);
        if (msg.type === "snapshot" && msg.devices) {
          this.devices = {};
          for (const d of msg.devices) {
            this.devices[d.device_id] = d;
          }
        } else if (msg.device_id && msg.state) {
          this.devices[msg.device_id] = msg.state;
        }
        this._notify();
      } catch {
        // ignore parse errors
      }
    };

    this.ws.onclose = () => {
      this.reconnectTimer = setTimeout(() => this.connect(), 3000);
    };

    this.ws.onerror = () => {
      this.ws?.close();
    };
  }

  disconnect(): void {
    if (this.reconnectTimer) clearTimeout(this.reconnectTimer);
    this.ws?.close();
    this.ws = null;
  }

  subscribe(listener: Listener): () => void {
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  }

  getDevices(): Record<string, DeviceState> {
    return { ...this.devices };
  }

  private _notify(): void {
    const snapshot = this.getDevices();
    for (const l of this.listeners) l(snapshot);
  }
}

export const deviceStore = new DeviceStateStore();

// ---------------------------------------------------------------------------
// React context
// ---------------------------------------------------------------------------

const DeviceContext = createContext<Record<string, DeviceState>>({});

export function DeviceProvider({ children }: { children: React.ReactNode }) {
  const [devices, setDevices] = useState<Record<string, DeviceState>>({});

  useEffect(() => {
    deviceStore.connect();
    const unsub = deviceStore.subscribe(setDevices);
    return () => {
      unsub();
      deviceStore.disconnect();
    };
  }, []);

  return React.createElement(DeviceContext.Provider, { value: devices }, children);
}

export function useDevices(): Record<string, DeviceState> {
  return useContext(DeviceContext);
}

export function useDevice(device_id: string): DeviceState | undefined {
  const devices = useDevices();
  return devices[device_id];
}
