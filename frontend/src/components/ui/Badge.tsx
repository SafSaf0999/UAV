import React from "react";

type BadgeVariant = "online" | "offline" | "error" | "warning" | "unknown" | "health_timeout";

interface BadgeProps {
  variant: BadgeVariant;
  label?: string;
}

const VARIANT_COLORS: Record<BadgeVariant, string> = {
  online: "var(--uav-color-online)",
  offline: "var(--uav-color-offline)",
  error: "var(--uav-color-alert)",
  warning: "var(--uav-color-warning)",
  unknown: "var(--ha-color-neutral-50)",
  health_timeout: "#f59e0b",
};

export function Badge({ variant, label }: BadgeProps) {
  const color = VARIANT_COLORS[variant];
  return (
    <span
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: 6,
        fontSize: "var(--ha-font-size-s)",
        color,
      }}
      aria-label={label ?? variant}
    >
      <span
        style={{
          width: 8,
          height: 8,
          borderRadius: "50%",
          background: color,
          flexShrink: 0,
        }}
      />
      {label}
    </span>
  );
}
