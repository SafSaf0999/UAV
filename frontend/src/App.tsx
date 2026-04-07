/**
 * UAV Control Center — main app shell.
 *
 * Routes:
 *   /login    — LoginPage (public)
 *   /register — RegisterPage (public, requires invite token)
 *   /*        — AuthGuard → AppShell (protected)
 */

import React, { useState, useEffect } from "react";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import { DeviceProvider, deviceStore } from "./api/websocket";
import { AuthGuard } from "./components/AuthGuard";
import { AppShell } from "./components/AppShell";
import { LoginPage } from "./pages/LoginPage";
import { RegisterPage } from "./pages/RegisterPage";

function ProtectedApp() {
  const [wsConnected, setWsConnected] = useState(false);

  useEffect(() => {
    // Poll WS connection state
    const interval = setInterval(() => {
      const ws = (deviceStore as any).ws as WebSocket | null;
      setWsConnected(ws?.readyState === WebSocket.OPEN);
    }, 1000);
    return () => clearInterval(interval);
  }, []);

  return (
    <AuthGuard>
      <DeviceProvider>
        <AppShell wsConnected={wsConnected} />
      </DeviceProvider>
    </AuthGuard>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/register" element={<RegisterPage />} />
        <Route path="/*" element={<ProtectedApp />} />
      </Routes>
    </BrowserRouter>
  );
}
