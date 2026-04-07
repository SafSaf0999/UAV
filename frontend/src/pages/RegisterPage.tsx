/**
 * Register page — create account using an invite token.
 * Token can be pre-filled via ?token= query param.
 */

import React, { useState } from "react";
import { useNavigate, useSearchParams, Link } from "react-router-dom";
import { setToken } from "../utils/auth";

export function RegisterPage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();

  const [inviteToken, setInviteToken] = useState(searchParams.get("token") ?? "");
  const [displayName, setDisplayName] = useState("");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");

    if (password !== confirmPassword) {
      setError("Passwords do not match.");
      return;
    }
    if (password.length < 8) {
      setError("Password must be at least 8 characters.");
      return;
    }

    setLoading(true);
    try {
      const resp = await fetch("/auth/register", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          invite_token: inviteToken.trim(),
          display_name: displayName.trim(),
          username: username.trim(),
          password,
        }),
      });
      const data = await resp.json();
      if (resp.ok) {
        setToken(data.access_token);
        navigate("/", { replace: true });
      } else {
        setError(data.detail ?? "Registration failed.");
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
        <div style={styles.header}>
          <h1 style={styles.title}>Create Account</h1>
          <p style={styles.subtitle}>Enter your invite token to register</p>
        </div>

        <form onSubmit={handleSubmit} style={styles.form}>
          <Field label="Invite Token" id="invite_token">
            <input
              id="invite_token"
              type="text"
              value={inviteToken}
              onChange={(e) => setInviteToken(e.target.value)}
              style={styles.input}
              placeholder="UAV-XXXX-XXXX"
              required
              aria-label="Invite token"
            />
          </Field>

          <Field label="Display Name" id="display_name">
            <input
              id="display_name"
              type="text"
              value={displayName}
              onChange={(e) => setDisplayName(e.target.value)}
              style={styles.input}
              placeholder="Your full name"
              required
              aria-label="Display name"
            />
          </Field>

          <Field label="Username" id="reg_username">
            <input
              id="reg_username"
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              style={styles.input}
              placeholder="Choose a username"
              required
              autoComplete="username"
              aria-label="Username"
            />
          </Field>

          <Field label="Password" id="reg_password">
            <input
              id="reg_password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              style={styles.input}
              placeholder="At least 8 characters"
              required
              autoComplete="new-password"
              aria-label="Password"
            />
          </Field>

          <Field label="Confirm Password" id="confirm_password">
            <input
              id="confirm_password"
              type="password"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              style={styles.input}
              placeholder="Repeat password"
              required
              autoComplete="new-password"
              aria-label="Confirm password"
            />
          </Field>

          {error && <p style={styles.error} role="alert">{error}</p>}

          <button type="submit" style={styles.button} disabled={loading}>
            {loading ? "Creating account…" : "Create Account"}
          </button>
        </form>

        <p style={styles.loginLink}>
          Already have an account?{" "}
          <Link to="/login" style={styles.link}>Sign in →</Link>
        </p>
      </div>
    </div>
  );
}

function Field({ label, id, children }: { label: string; id: string; children: React.ReactNode }) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
      <label htmlFor={id} style={styles.label}>{label}</label>
      {children}
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
    maxWidth: 420,
  },
  header: {
    textAlign: "center",
    marginBottom: "var(--ha-space-6, 24px)",
  },
  title: {
    color: "var(--primary-text-color, #fff)",
    fontSize: "var(--ha-font-size-xl, 20px)",
    fontWeight: "var(--ha-font-weight-bold, 700)" as any,
    margin: "0 0 var(--ha-space-1, 4px)",
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
    gap: "var(--ha-space-3, 12px)",
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
    marginTop: "var(--ha-space-2, 8px)",
  },
  loginLink: {
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
