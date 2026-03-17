/**
 * Tracking overlay — canvas element over video feed.
 *
 * Draws bounding boxes, track IDs, distance, and trajectory vectors
 * from the latest TrackingPayload.
 *
 * Requirements: 5.3, 5.4, 17.6
 */

import React, { useEffect, useRef } from "react";
import type { TrackingPayload, Detection } from "../types";

interface Props {
  tracking: TrackingPayload;
  containerRef: React.RefObject<HTMLElement>;
}

function drawDetection(
  ctx: CanvasRenderingContext2D,
  det: Detection,
  scaleX: number,
  scaleY: number
) {
  const [x, y, w, h] = det.bbox;
  const sx = x * scaleX;
  const sy = y * scaleY;
  const sw = w * scaleX;
  const sh = h * scaleY;

  // Bounding box
  ctx.strokeStyle = "#22c55e";
  ctx.lineWidth = 2;
  ctx.strokeRect(sx, sy, sw, sh);

  // Label background
  const label = `#${det.track_id} ${det.label} ${(det.confidence * 100).toFixed(0)}%`;
  ctx.font = "12px monospace";
  const textW = ctx.measureText(label).width;
  ctx.fillStyle = "rgba(34,197,94,0.8)";
  ctx.fillRect(sx, sy - 18, textW + 8, 18);

  // Label text
  ctx.fillStyle = "#000";
  ctx.fillText(label, sx + 4, sy - 4);

  // Distance
  if (det.estimated_distance_m !== undefined) {
    const distLabel = `${det.estimated_distance_m.toFixed(1)}m`;
    ctx.fillStyle = "rgba(0,0,0,0.6)";
    ctx.fillRect(sx, sy + sh, ctx.measureText(distLabel).width + 8, 18);
    ctx.fillStyle = "#fbbf24";
    ctx.fillText(distLabel, sx + 4, sy + sh + 13);
  }

  // Trajectory arrow
  if (det.trajectory_vector) {
    const cx = sx + sw / 2;
    const cy = sy + sh / 2;
    const dx = det.trajectory_vector.dx * scaleX * 5;
    const dy = det.trajectory_vector.dy * scaleY * 5;
    ctx.beginPath();
    ctx.moveTo(cx, cy);
    ctx.lineTo(cx + dx, cy + dy);
    ctx.strokeStyle = "#60a5fa";
    ctx.lineWidth = 2;
    ctx.stroke();
    // Arrowhead
    const angle = Math.atan2(dy, dx);
    ctx.beginPath();
    ctx.moveTo(cx + dx, cy + dy);
    ctx.lineTo(cx + dx - 8 * Math.cos(angle - 0.4), cy + dy - 8 * Math.sin(angle - 0.4));
    ctx.lineTo(cx + dx - 8 * Math.cos(angle + 0.4), cy + dy - 8 * Math.sin(angle + 0.4));
    ctx.closePath();
    ctx.fillStyle = "#60a5fa";
    ctx.fill();
  }
}

export function TrackingOverlay({ tracking, containerRef }: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    const container = containerRef.current;
    if (!canvas || !container) return;

    const rect = container.getBoundingClientRect();
    canvas.width = rect.width;
    canvas.height = rect.height;

    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    ctx.clearRect(0, 0, canvas.width, canvas.height);

    // Scale factors: bbox coords are in original frame pixels
    // We assume 640x480 default; ideally the payload would include frame dims
    const frameW = 640;
    const frameH = 480;
    const scaleX = canvas.width / frameW;
    const scaleY = canvas.height / frameH;

    for (const det of tracking.detections) {
      drawDetection(ctx, det, scaleX, scaleY);
    }
  }, [tracking]);

  return (
    <canvas
      ref={canvasRef}
      style={{
        position: "absolute",
        inset: 0,
        pointerEvents: "none",
        width: "100%",
        height: "100%",
      }}
      aria-hidden="true"
    />
  );
}
