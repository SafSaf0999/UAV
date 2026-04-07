"""
Run BirdDrone-Local on DUT Anti-UAV videos and produce annotated MP4 output.

For each video:
  - Runs inference in batches on all frames
  - Draws bounding boxes + confidence + class label
  - Draws ground-truth box (first frame only) in green
  - Writes annotated MP4 to comparison/dut_videos/

Also collects per-video detection metrics and writes a summary CSV/MD.
"""
from __future__ import annotations
import csv
from pathlib import Path
from datetime import datetime

import cv2
import numpy as np

ROOT     = Path("/home/safsaf/Projects/UAV-dataset-workflow")
DUT_ROOT = ROOT / "datasets" / "DUT Anti-UAV" / "Anti-UAV-Tracking-V0"
OUT_DIR  = ROOT / "comparison" / "dut_videos"
OUT_DIR.mkdir(parents=True, exist_ok=True)

WEIGHTS   = ROOT / "training" / "run_2class_yolo26s_rtx2070_100ep" / "weights" / "best.pt"
MODEL_NAME = "BirdDrone-Local"
CONF      = 0.25
IOU       = 0.45
BATCH     = 32
FPS       = 25
TIMESTAMP = datetime.now().strftime("%Y%m%d_%H%M%S")

# Colours (BGR)
COL_DRONE = (0,  120, 255)   # orange
COL_BIRD  = (0,  200,  0)    # green
COL_GT    = (0,  255, 255)   # yellow — ground truth first frame
COL_TEXT  = (255, 255, 255)
CLASSES   = {0: ("Bird",  COL_BIRD), 1: ("Drone", COL_DRONE)}


def parse_gt(txt_path: Path) -> tuple[int,int,int,int] | None:
    """Return (x, y, w, h) pixel coords from gt_first.txt."""
    try:
        vals = list(map(int, txt_path.read_text().strip().split()))
        return tuple(vals[:4])
    except Exception:
        return None


def draw_box(frame: np.ndarray, x1: int, y1: int, x2: int, y2: int,
             label: str, conf: float, color: tuple) -> None:
    cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
    text = f"{label} {conf:.2f}"
    (tw, th), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 0.55, 1)
    ty = max(y1 - 4, th + 4)
    cv2.rectangle(frame, (x1, ty - th - 4), (x1 + tw + 4, ty), color, -1)
    cv2.putText(frame, text, (x1 + 2, ty - 2),
                cv2.FONT_HERSHEY_SIMPLEX, 0.55, COL_TEXT, 1, cv2.LINE_AA)


def main() -> None:
    from ultralytics import YOLO
    model = YOLO(str(WEIGHTS))

    video_dirs = sorted(d for d in DUT_ROOT.iterdir() if d.is_dir())
    print(f"Found {len(video_dirs)} videos")

    summary: list[dict] = []

    for vdir in video_dirs:
        frames = sorted(vdir.glob("*.jpg"))
        if not frames:
            continue

        gt_file = vdir / f"{vdir.name}_gt_first.txt"
        gt_box  = parse_gt(gt_file) if gt_file.is_file() else None

        # Read first frame to get dimensions
        first = cv2.imread(str(frames[0]))
        h, w  = first.shape[:2]

        out_path = OUT_DIR / f"{vdir.name}_{MODEL_NAME}.mp4"
        writer   = cv2.VideoWriter(
            str(out_path),
            cv2.VideoWriter_fourcc(*"mp4v"),
            FPS, (w, h)
        )

        detected = 0
        confidences: list[float] = []
        tp_first = 0

        print(f"  {vdir.name}: {len(frames)} frames → {out_path.name}")

        for i in range(0, len(frames), BATCH):
            batch_paths = [str(p) for p in frames[i:i+BATCH]]
            results = model(batch_paths, conf=CONF, iou=IOU,
                            verbose=False, device=0, stream=False)

            for j, r in enumerate(results):
                frame_idx = i + j
                img = cv2.imread(str(frames[frame_idx]))

                # Draw GT box on first frame
                if frame_idx == 0 and gt_box is not None:
                    gx, gy, gw, gh = gt_box
                    cv2.rectangle(img, (gx, gy), (gx+gw, gy+gh), COL_GT, 2)
                    cv2.putText(img, "GT", (gx, gy - 6),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.55, COL_GT, 1)

                # Draw predictions
                boxes = r.boxes
                if boxes is not None and len(boxes) > 0:
                    detected += 1
                    for box in boxes:
                        cls_id = int(box.cls.item())
                        conf_v = float(box.conf.item())
                        x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
                        label, color = CLASSES.get(cls_id, ("UAV", (0,0,255)))
                        draw_box(img, x1, y1, x2, y2, label, conf_v, color)
                        confidences.append(conf_v)

                    # Check first-frame IoU
                    if frame_idx == 0 and gt_box is not None:
                        gx, gy, gw, gh = gt_box
                        gt_cx = (gx + gw/2) / w
                        gt_cy = (gy + gh/2) / h
                        gt_wn = gw / w
                        gt_hn = gh / h
                        for box in boxes.xywhn.cpu().numpy():
                            px,py,pw,ph = box[:4]
                            ix1 = max(gt_cx-gt_wn/2, px-pw/2)
                            iy1 = max(gt_cy-gt_hn/2, py-ph/2)
                            ix2 = min(gt_cx+gt_wn/2, px+pw/2)
                            iy2 = min(gt_cy+gt_hn/2, py+ph/2)
                            inter = max(0,ix2-ix1)*max(0,iy2-iy1)
                            union = gt_wn*gt_hn + pw*ph - inter
                            if union > 0 and inter/union > 0.5:
                                tp_first = 1
                                break

                # Frame counter overlay
                cv2.putText(img, f"{vdir.name}  frame {frame_idx+1}/{len(frames)}",
                            (8, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (200,200,200), 1)
                writer.write(img)

        writer.release()
        n = len(frames)
        dr = round(detected / n, 4) if n > 0 else 0
        mc = round(sum(confidences)/len(confidences), 4) if confidences else 0
        summary.append({
            "video": vdir.name, "frames": n, "detected": detected,
            "detection_rate": dr, "mean_conf": mc, "tp_first_frame": tp_first,
            "output": out_path.name,
        })
        print(f"    DR={dr:.3f}  conf={mc:.3f}  TP_first={tp_first}  → {out_path.name}")

    # Write summary
    csv_path = ROOT / "comparison" / f"dut_video_eval_{TIMESTAMP}.csv"
    md_path  = ROOT / "comparison" / f"dut_video_eval_{TIMESTAMP}.md"

    with open(csv_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(summary[0].keys()))
        w.writeheader()
        w.writerows(summary)

    avg_dr = sum(r["detection_rate"] for r in summary) / len(summary)
    avg_mc = sum(r["mean_conf"] for r in summary) / len(summary)
    tp_rate = sum(r["tp_first_frame"] for r in summary) / len(summary)

    with open(md_path, "w") as f:
        f.write(f"# DUT Anti-UAV Video Evaluation — {MODEL_NAME}\n\n")
        f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n")
        f.write("> Annotated videos saved to `comparison/dut_videos/`\n")
        f.write("> Yellow box = ground truth (first frame only). "
                "Orange = Drone prediction. Green = Bird prediction.\n\n")
        f.write("## Aggregate\n\n")
        f.write(f"| Metric | Value |\n|---|---|\n")
        f.write(f"| Avg Detection Rate | {avg_dr:.3f} |\n")
        f.write(f"| Avg Confidence | {avg_mc:.3f} |\n")
        f.write(f"| First-frame IoU>0.5 rate | {tp_rate:.3f} |\n\n")
        f.write("## Per-Video\n\n")
        f.write("| Video | Frames | Detected | DR | Conf | TP_first | Output |\n")
        f.write("|---|---|---|---|---|---|---|\n")
        for r in summary:
            f.write(f"| {r['video']} | {r['frames']} | {r['detected']} | "
                    f"{r['detection_rate']:.3f} | {r['mean_conf']:.3f} | "
                    f"{r['tp_first_frame']} | {r['output']} |\n")

    print(f"\nCSV: {csv_path}")
    print(f"MD:  {md_path}")
    print(f"Videos: {OUT_DIR}")


if __name__ == "__main__":
    main()
