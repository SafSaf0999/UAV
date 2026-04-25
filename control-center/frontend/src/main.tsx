import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import "./styles/design-tokens.css";
import "./styles/uav-tokens.css";

// Register service worker for PWA offline support
if ("serviceWorker" in navigator) {
  window.addEventListener("load", () => {
    navigator.serviceWorker.register("/sw.js").catch(() => {
      // SW registration is best-effort
    });
  });
}
ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
