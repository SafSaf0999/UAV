import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/api": "http://localhost:8080",
      "/ws": { target: "ws://localhost:8080", ws: true },
      "/signaling": { target: "ws://localhost:8765", ws: true },
    },
  },
  define: {
    // Env vars injected at build time
    __TILE_SERVER_URL__: JSON.stringify(
      process.env.VITE_TILE_SERVER_URL || "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
    ),
    __AGGREGATION_WS_URL__: JSON.stringify(
      process.env.VITE_AGGREGATION_WS_URL || "ws://localhost:8080/ws"
    ),
    __SIGNALING_URL__: JSON.stringify(
      process.env.VITE_SIGNALING_URL || "ws://localhost:8765"
    ),
    __TURN_SERVER_URL__: JSON.stringify(
      process.env.VITE_TURN_SERVER_URL || ""
    ),
  },
});
