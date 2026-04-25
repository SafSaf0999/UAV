"""
Evaluate models on DUT Anti-UAV dataset.

The downloaded dataset is the TRACKING split — each video has only a first-frame
bounding box annotation (gt_first.txt: x y w h in pixel coords).

Since per-frame detection annotations are not available in this split, we run
inference on ALL frames of each video and compute:
  - Detection Rate (DR): fraction of frames where the model detects at least one object
  - Mean confidence of detections
  - Per-video summary

This is a proxy metric for detection capability, not mAP.
For proper mAP we would need the detection split (separate download).

Annotation format: x_topleft y_topleft width height (pixels, absolute)
"""
from __future__ import annotations
import csv
import shutil
import tempfile
from pathlib import Path
from datetime import datetime

ROOT     = Path("/home/safsaf/Projects/UAV-dataset-workflow")
DUT_ROOT = ROOT / "datasets" / "DUT Anti-UAV" / "Anti-UAV-Tracking-V0"
COMP_DIR = ROOT / "comparison"
TIMESTAMP = datetime.now().strftime("%Y%m%d_%H%M%S")

MODELS = [
    {
        "name":    "BirdDrone-Local",
        "weights": ROOT / "training" / "run_2class_yolo26s_rtx2070_100ep" / "weights" / "best.pt",
        "nc": 2, "names": ["Bird", "Drone"],
    },
    {
        "name":    "TriClass-Cloud",
        "weights": ROOT / "training" / "run_3class_yolo26s_colab_t4_100ep" / "weights" / "best.pt",
        "nc": 3, "names": ["Bird", "Drone", "UAV"],
    },
    {
        "name":    "BirdDrone-Cloud-Old",
        "weights": ROOT / "training" / "run_2class_yolo26s_colab_t4_160ep_old" / "weights" / "best.pt",
        "nc": 2, "names": ["Bird", "Drone"],
    },
]

CONF_THRESH = 0.25
IOU_THRESH  = 0.45


def parse_gt(txt_path: Path, img_w: int, img_h: int) -> tuple[float, float, float, float]:
    """Parse gt_first.txt (x y w h pixels) → YOLO normalized (cx cy w h)."""
    x, y, w, h = map(float, txt_path.read_text().strip().split())
    cx = (x + w / 2) / img_w
    cy = (y + h / 2) / img_h
    wn = w / img_w
    hn = h / img_h
    return cx, cy, wn, hn


def iou(box1, box2) -> float:
    """Compute IoU between two (cx,cy,w,h) normalized boxes."""
    def to_xyxy(b):
        return b[0]-b[2]/2, b[1]-b[3]/2, b[0]+b[2]/2, b[1]+b[3]/2
    ax1,ay1,ax2,ay2 = to_xyxy(box1)
    bx1,by1,bx2,by2 = to_xyxy(box2)
    ix1,iy1 = max(ax1,bx1), max(ay1,by1)
    ix2,iy2 = min(ax2,bx2), min(ay2,by2)
    inter = max(0, ix2-ix1) * max(0, iy2-iy1)
    union = (ax2-ax1)*(ay2-ay1) + (bx2-bx1)*(by2-by1) - inter
    return inter / union if union > 0 else 0.0


def run_inference_on_video(model, video_dir: Path, gt_box_norm) -> dict:
    """Run model on all frames in video_dir using batched inference."""
    frames = sorted(video_dir.glob("*.jpg"))
    if not frames:
        return {}

    BATCH = 32
    detected = 0
    tp_first = 0
    confidences = []

    for i in range(0, len(frames), BATCH):
        batch = frames[i:i+BATCH]
        batch_paths = [str(p) for p in batch]
        results = model(batch_paths, conf=CONF_THRESH, iou=IOU_THRESH,
                        verbose=False, device=0, stream=False)
        for j, r in enumerate(results):
            boxes = r.boxes
            if boxes is not None and len(boxes) > 0:
                detected += 1
                confidences.extend(boxes.conf.cpu().numpy().tolist())
                # Check IoU on first frame (global index i+j == 0)
                if i + j == 0 and gt_box_norm is not None:
                    for box in boxes.xywhn.cpu().numpy():
                        if iou(tuple(box[:4]), gt_box_norm) > 0.5:
                            tp_first = 1
                            break

    n = len(frames)
    return {
        "frames":         n,
        "detected":       detected,
        "detection_rate": round(detected / n, 4) if n > 0 else 0,
        "mean_conf":      round(sum(confidences) / len(confidences), 4) if confidences else 0,
        "tp_first_frame": tp_first,
    }


def main():
    from ultralytics import YOLO
    from PIL import Image

    video_dirs = sorted(DUT_ROOT.iterdir())
    print(f"Found {len(video_dirs)} videos in DUT Anti-UAV")

    all_results = []

    for model_cfg in MODELS:
        if not model_cfg["weights"].is_file():
            print(f"SKIP {model_cfg['name']} — weights not found")
            continue

        print(f"\n{'='*60}")
        print(f"Model: {model_cfg['name']}")
        print(f"{'='*60}")

        model = YOLO(str(model_cfg["weights"]))

        video_results = []
        for vdir in video_dirs:
            if not vdir.is_dir():
                continue
            gt_file = vdir / f"{vdir.name}_gt_first.txt"
            if not gt_file.is_file():
                continue

            # Get image dimensions from first frame
            first_frame = sorted(vdir.glob("*.jpg"))[0]
            img = Image.open(first_frame)
            w, h = img.size

            gt_norm = parse_gt(gt_file, w, h)
            metrics = run_inference_on_video(model, vdir, gt_norm)
            metrics["video"] = vdir.name
            metrics["model"] = model_cfg["name"]
            video_results.append(metrics)
            print(f"  {vdir.name}: DR={metrics['detection_rate']:.3f}  "
                  f"conf={metrics['mean_conf']:.3f}  "
                  f"TP_first={metrics['tp_first_frame']}")

        # Aggregate
        if video_results:
            avg_dr   = sum(r["detection_rate"] for r in video_results) / len(video_results)
            avg_conf = sum(r["mean_conf"] for r in video_results) / len(video_results)
            tp_rate  = sum(r["tp_first_frame"] for r in video_results) / len(video_results)
            print(f"\n  AGGREGATE — Avg DR: {avg_dr:.3f}  Avg Conf: {avg_conf:.3f}  "
                  f"First-frame IoU>0.5: {tp_rate:.3f}")
            all_results.extend(video_results)
            all_results.append({
                "model": model_cfg["name"], "video": "AGGREGATE",
                "frames": sum(r["frames"] for r in video_results),
                "detected": sum(r["detected"] for r in video_results),
                "detection_rate": round(avg_dr, 4),
                "mean_conf": round(avg_conf, 4),
                "tp_first_frame": round(tp_rate, 4),
            })

    # Write CSV
    out_csv = COMP_DIR / f"dut_eval_{TIMESTAMP}.csv"
    fields = ["model","video","frames","detected","detection_rate","mean_conf","tp_first_frame"]
    with open(out_csv, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        for r in all_results:
            w.writerow(r)

    # Write MD summary
    out_md = COMP_DIR / f"dut_eval_{TIMESTAMP}.md"
    with open(out_md, "w") as f:
        f.write("# DUT Anti-UAV Evaluation Results\n\n")
        f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n")
        f.write("> **Note:** This dataset is the tracking split of DUT Anti-UAV.\n")
        f.write("> Only first-frame bounding box annotations are available.\n")
        f.write("> Metrics reported: Detection Rate (DR) = fraction of frames with at least one detection,\n")
        f.write("> and First-Frame IoU>0.5 (TP rate on the annotated first frame).\n\n")
        f.write("## Aggregate Results\n\n")
        f.write("| Model | Avg Detection Rate | Avg Confidence | First-Frame TP Rate |\n")
        f.write("|---|---|---|---|\n")
        for r in all_results:
            if r["video"] == "AGGREGATE":
                f.write(f"| {r['model']} | {r['detection_rate']:.3f} | "
                        f"{r['mean_conf']:.3f} | {r['tp_first_frame']:.3f} |\n")
        f.write("\n## Per-Video Results\n\n")
        f.write("| Model | Video | Frames | Detected | DR | Conf | TP_first |\n")
        f.write("|---|---|---|---|---|---|---|\n")
        for r in all_results:
            if r["video"] != "AGGREGATE":
                f.write(f"| {r['model']} | {r['video']} | {r['frames']} | "
                        f"{r['detected']} | {r['detection_rate']:.3f} | "
                        f"{r['mean_conf']:.3f} | {r['tp_first_frame']} |\n")

    print(f"\nCSV: {out_csv}")
    print(f"MD:  {out_md}")


if __name__ == "__main__":
    main()
