/**
 * CompassRose — SVG compass that rotates to show bearing.
 */

import React from "react";

interface Props {
  bearing: number; // degrees 0–360
  size?: number;
}

export function CompassRose({ bearing, size = 64 }: Props) {
  const cx = size / 2;
  const r = size / 2 - 4;

  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} aria-label={`Bearing: ${bearing}°`}>
      {/* Outer ring */}
      <circle cx={cx} cy={cx} r={r} fill="none" stroke="var(--ha-color-neutral-30)" strokeWidth={2} />
      {/* Cardinal labels */}
      {[["N", 0], ["E", 90], ["S", 180], ["W", 270]].map(([label, deg]) => {
        const rad = ((Number(deg) - 90) * Math.PI) / 180;
        const lx = cx + (r - 10) * Math.cos(rad);
        const ly = cx + (r - 10) * Math.sin(rad);
        return (
          <text key={label} x={lx} y={ly + 4} textAnchor="middle"
            fill="var(--secondary-text-color)" fontSize={9}
            fontFamily="var(--ha-font-family-body)">
            {label}
          </text>
        );
      })}
      {/* Needle — rotates to bearing */}
      <g transform={`rotate(${bearing} ${cx} ${cx})`}>
        {/* North (red) */}
        <polygon
          points={`${cx},${cx - r + 14} ${cx - 5},${cx + 4} ${cx + 5},${cx + 4}`}
          fill="var(--uav-color-alert)"
        />
        {/* South (grey) */}
        <polygon
          points={`${cx},${cx + r - 14} ${cx - 5},${cx - 4} ${cx + 5},${cx - 4}`}
          fill="var(--ha-color-neutral-40)"
        />
      </g>
      {/* Center dot */}
      <circle cx={cx} cy={cx} r={3} fill="var(--primary-text-color)" />
      {/* Bearing label */}
      <text x={cx} y={size - 2} textAnchor="middle"
        fill="var(--secondary-text-color)" fontSize={9}
        fontFamily="var(--ha-font-family-body)">
        {Math.round(bearing)}°
      </text>
    </svg>
  );
}
