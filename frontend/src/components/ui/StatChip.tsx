import React from "react";

interface StatChipProps {
  label: string;
  count?: number;
  color?: string;
  style?: React.CSSProperties;
}

export function StatChip({ label, count, color = "var(--ha-color-neutral-60)", style }: StatChipProps) {
  return (
    <span
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: 4,
        borderRadius: "var(--ha-border-radius-pill)",
        padding: "2px var(--ha-space-2)",
        fontSize: "var(--ha-font-size-xs)",
        fontWeight: "var(--ha-font-weight-medium)" as any,
        color,
        background: `color-mix(in srgb, ${color} 15%, transparent)`,
        border: `1px solid color-mix(in srgb, ${color} 30%, transparent)`,
        whiteSpace: "nowrap",
        ...style,
      }}
    >
      {label}{count !== undefined ? ` ×${count}` : ""}
    </span>
  );
}
