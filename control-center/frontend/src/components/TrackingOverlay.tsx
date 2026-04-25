/**
 * Tracking overlay — canvas element over video feed.
 *
 * Draws bounding boxes (color-coded by class), track IDs, distance,
 * and trajectory vectors from the latest TrackingPayload.
 * Uses actual video dimensions via loadedmetadata event.
 * Attaches ResizeObserver to keep canvas in sync with video element size.
 *
 * Requirements: 5.3, 5.4, 17.6, v2-5.1, v2-5.2, v2-8.3, v2-8.4, v2-8.5
 */

import React, { useEffect, useRef, useState } from "react";
import type { TrackingPayload, Detection } from "../types";
import { getClassColor } from "../utils/classColors";

interface Props {
  tracking: TrackingPayload;
  containerRef: React.RefObject<HTMLElement>;
  videoRef?: React.RefObject<HTMLVideoElement>;
  profileColors?: Record<string, string>;
}

function drawDetection(
  ctx: CanvasRenderingContext2D,
  det: Detection,
  scaleX: number,
  scaleY: number,
  color: string,
) {
  const [x, y, w, h] = det.bbox;
  const sx = x * scaleX;
  const sy = y * scaleY;
  const sw = w * scaleX;
  const sh = h * scaleY;

  // Bounding box
  ctx.strokeStyle = color;
  ctx.lineWidth = 2;
  ctx.strokeRect(sx, sy, sw, sh);

  // Label background
  const label = `#${det.track_id} ${det.label} ${(det.confidence * 100).toFixed(0)}%`;
  ctx.font = "12px monospace";
  const textW = ctx.measureText(label).width;
  ctx.fillStyle = color + "cc";
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

interface LegendEntry {
  label: string;
  color: string;
}

function buildLegendEntries(
  classes: Set<string>,
  profileColors?: Record<string, string>,
): LegendEntry[] {
  const entries: LegendEntry[] = [];
  const hasBird = classes.has("bird");
  const hasDrone = classes.has("drone");

  for (const cls of classes) {
    if (cls === "bird" || cls === "drone") continue;
    entries.push({ label: cls, color: getClassColor(cls, undefined, profileColors) });
  }

  if (hasBird) {
    entries.push({ label: "bird (green)", color: "#22c55e" });
  }
  if (hasDrone) {
    entries.push({ label: "drone ≥50% (red)", color: "#ef4444" });
    entries.push({ label: "drone <50% (orange)", color: "#f97316" });
  }

  return entries;
}

function drawLegend(
  ctx: CanvasRenderingContext2D,
  classes: Set<string>,
  profileColors?: Record<string, string>,
) {
  const entries = buildLegendEntries(classes, profileColors);
  if (entries.length === 0) return;

  const padding = 6;
  const lineH = 18;
  const boxW = 12;
  ctx.font = "11px monospace";
  const maxLabelW = Math.max(...entries.map((e) => ctx.measureText(e.label).width));
  const legendW = boxW + padding + maxLabelW + padding * 2;
  const legendH = entries.length * lineH + padding * 2;
  const x = ctx.canvas.width - legendW - 8;
  const y = 8;

  ctx.fillStyle = "rgba(0,0,0,0.6)";
  ctx.fillRect(x, y, legendW, legendH);

  entries.forEach((entry, i) => {
    const cy = y + padding + i * lineH;
    ctx.fillStyle = entry.color;
    ctx.fillRect(x + padding, cy + 3, boxW, boxW);
    ctx.fillStyle = "#fff";
    ctx.font = "11px monospace";
    ctx.fillText(entry.label, x + padding + boxW + 4, cy + 13);
  });
}

export function TrackingOverlay({ tracking, containerRef, videoRef, profileColors }: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [videoDims, setVideoDims] = useState({ w: 640, h: 480 });

  // Listen to video loadedmetadata to get real frame dimensions
  useEffect(() => {
    const video = videoRef?.current ?? (containerRef.current as HTMLVideoElement | null);
    if (!video || video.tagName !== "VIDEO") return;
    const onMeta = () => {
      if (video.videoWidth && video.videoHeight) {
        setVideoDims({ w: video.videoWidth, h: video.videoHeight });
      }
    };
    video.addEventListener("loadedmetadata", onMeta);
    if (video.videoWidth) onMeta();
    return () => video.removeEventListener("loadedmetadata", onMeta);
  }, [videoRef, containerRef]);

  // ResizeObserver to keep canvas size in sync
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ro = new ResizeObserver(() => {
      canvas.width = canvas.offsetWidth;
      canvas.height = canvas.offsetHeight;
    });
    ro.observe(canvas);
    return () => ro.disconnect();
  }, []);

  // Draw on every tracking update
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

    const scaleX = canvas.width / videoDims.w;
    const scaleY = canvas.height / videoDims.h;

    const classesInFrame = new Set<string>();
    for (const det of tracking.detections) {
      const color = getClassColor(det.label, det.confidence, profileColors);
      drawDetection(ctx, det, scaleX, scaleY, color);
      classesInFrame.add(det.label);
    }

    // Class legend
    drawLegend(ctx, classesInFrame, profileColors);
  }, [tracking, videoDims, profileColors]);

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
