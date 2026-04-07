/**
 * Login page — full-screen dark card with username/password fields.
 */

import React, { useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import { setToken } from "../utils/auth";

export function LoginPage() {
  const navigate = useNavigate();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [remember, setRemember] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const resp = await fetch("/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username, password, remember }),
      });
      if (resp.ok) {
        const data = await resp.json();
        setToken(data.access_token);
        navigate("/", { replace: true });
      } else {
        setError("Invalid username or password.");
      }
    } catch {
      setError("Connection error. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={styles.page}>
      <div style={styles.card}>
        {/* Logo / title */}
        <div style={styles.header}>
          <svg width="40" height="40" viewBox="0 0 40 40" fill="none" aria-hidden="true">
            <circle cx="20" cy="20" r="18" stroke="var(--uav-color-alert)" strokeWidth="2" />
            <circle cx="20" cy="20" r="4" fill="var(--uav-color-alert)" />
            <line x1="20" y1="2" x2="20" y2="10" stroke="var(--uav-color-alert)" strokeWidth="2" />
            <line x1="20" y1="30" x2="20" y2="38" stroke="var(--uav-color-alert)" strokeWidth="2" />
            <line x1="2" y1="20" x2="10" y2="20" stroke="var(--uav-color-alert)" strokeWidth="2" />
            <line x1="30" y1="20" x2="38" y2="20" stroke="var(--uav-color-alert)" strokeWidth="2" />
          </svg>
          <h1 style={styles.title}>Anti-UAV Control Center</h1>
          <p style={styles.subtitle}>Sign in to continue</p>
        </div>

        <form onSubmit={handleSubmit} style={styles.form}>
          <div style={styles.field}>
            <label style={styles.label} htmlFor="username">Username</label>
            <input
              id="username"
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              style={styles.input}
              autoComplete="username"
              required
              aria-label="Username"
            />
          </div>

          <div style={styles.field}>
            <label style={styles.label} htmlFor="password">Password</label>
            <input
              id="password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              style={styles.input}
              autoComplete="current-password"
              required
              aria-label="Password"
            />
          </div>

          <div style={styles.rememberRow}>
            <label style={styles.checkLabel}>
              <input
                type="checkbox"
                checked={remember}
                onChange={(e) => setRemember(e.target.checked)}
                style={{ marginRight: 6 }}
              />
              Remember me for 30 days
            </label>
          </div>

          {error && <p style={styles.error} role="alert">{error}</p>}

          <button type="submit" style={styles.button} disabled={loading}>
            {loading ? "Signing in…" : "Sign In"}
          </button>
        </form>

        <p style={styles.registerLink}>
          Have an invite token?{" "}
          <Link to="/register" style={styles.link}>Create account →</Link>
        </p>
      </div>
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  page: {
    minHeight: "100vh",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    background: "var(--primary-background-color, #111111)",
    padding: "var(--ha-space-4, 16px)",
  },
  card: {
    background: "var(--card-background-color, #202020)",
    border: "1px solid var(--ha-card-border-color, #363636)",
    borderRadius: "var(--ha-card-border-radius, 12px)",
    boxShadow: "var(--ha-card-box-shadow, 0 4px 8px rgba(0,0,0,0.4))",
    padding: "var(--ha-space-8, 32px)",
    width: "100%",
    maxWidth: 400,
  },
  header: {
    textAlign: "center",
    marginBottom: "var(--ha-space-6, 24px)",
  },
  title: {
    color: "var(--primary-text-color, #fff)",
    fontSize: "var(--ha-font-size-xl, 20px)",
    fontWeight: "var(--ha-font-weight-bold, 700)" as any,
    margin: "var(--ha-space-3, 12px) 0 var(--ha-space-1, 4px)",
    fontFamily: "var(--ha-font-family-body, Roboto, sans-serif)",
  },
  subtitle: {
    color: "var(--secondary-text-color, #ccc)",
    fontSize: "var(--ha-font-size-s, 12px)",
    margin: 0,
  },
  form: {
    display: "flex",
    flexDirection: "column",
    gap: "var(--ha-space-4, 16px)",
  },
  field: {
    display: "flex",
    flexDirection: "column",
    gap: "var(--ha-space-1, 4px)",
  },
  label: {
    color: "var(--secondary-text-color, #ccc)",
    fontSize: "var(--ha-font-size-s, 12px)",
    fontWeight: "var(--ha-font-weight-medium, 500)" as any,
  },
  input: {
    background: "var(--secondary-background-color, #141414)",
    border: "1px solid var(--divider-color, #363636)",
    borderRadius: "var(--ha-border-radius-md, 8px)",
    color: "var(--primary-text-color, #fff)",
    fontSize: "var(--ha-font-size-m, 14px)",
    padding: "var(--ha-space-2, 8px) var(--ha-space-3, 12px)",
    outline: "none",
    width: "100%",
    boxSizing: "border-box",
  },
  rememberRow: {
    display: "flex",
    alignItems: "center",
  },
  checkLabel: {
    color: "var(--secondary-text-color, #ccc)",
    fontSize: "var(--ha-font-size-s, 12px)",
    cursor: "pointer",
    display: "flex",
    alignItems: "center",
  },
  error: {
    color: "var(--uav-color-alert, #dc3146)",
    fontSize: "var(--ha-font-size-s, 12px)",
    margin: 0,
    padding: "var(--ha-space-2, 8px) var(--ha-space-3, 12px)",
    background: "color-mix(in srgb, var(--uav-color-alert, #dc3146) 10%, transparent)",
    borderRadius: "var(--ha-border-radius-md, 8px)",
  },
  button: {
    background: "var(--primary-color, #18bcf2)",
    color: "#fff",
    border: "none",
    borderRadius: "var(--ha-border-radius-md, 8px)",
    padding: "var(--ha-space-3, 12px)",
    fontSize: "var(--ha-font-size-m, 14px)",
    fontWeight: "var(--ha-font-weight-medium, 500)" as any,
    cursor: "pointer",
    width: "100%",
  },
  registerLink: {
    textAlign: "center",
    color: "var(--secondary-text-color, #ccc)",
    fontSize: "var(--ha-font-size-s, 12px)",
    marginTop: "var(--ha-space-4, 16px)",
    marginBottom: 0,
  },
  link: {
    color: "var(--primary-color, #18bcf2)",
    textDecoration: "none",
  },
};
