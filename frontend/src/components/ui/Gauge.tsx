import React from "react";

interface GaugeProps {
  value: number;      // 0–100
  label: string;
  size?: number;      // px, default 64
  color?: string;
}

export function Gauge({ value, label, size = 64, color = "var(--primary-color)" }: GaugeProps) {
  const clamped = Math.max(0, Math.min(100, value));
  const r = (size - 8) / 2;
  const circumference = 2 * Math.PI * r;
  const offset = circumference * (1 - clamped / 100);
  const cx = size / 2;

  return (
    <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 4 }}>
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} aria-label={`${label}: ${clamped}%`}>
        {/* Track */}
        <circle
          cx={cx} cy={cx} r={r}
          fill="none"
          stroke="var(--ha-color-neutral-20)"
          strokeWidth={6}
        />
        {/* Progress */}
        <circle
          cx={cx} cy={cx} r={r}
          fill="none"
          stroke={color}
          strokeWidth={6}
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          strokeLinecap="round"
          transform={`rotate(-90 ${cx} ${cx})`}
          style={{ transition: "stroke-dashoffset 0.4s ease" }}
        />
        <text
          x={cx} y={cx + 1}
          textAnchor="middle"
          dominantBaseline="middle"
          fill="var(--primary-text-color)"
          fontSize={size * 0.22}
          fontFamily="var(--ha-font-family-body)"
          fontWeight="500"
        >
          {Math.round(clamped)}%
        </text>
      </svg>
      <span style={{ fontSize: "var(--ha-font-size-xs)", color: "var(--secondary-text-color)" }}>
        {label}
      </span>
    </div>
  );
}
