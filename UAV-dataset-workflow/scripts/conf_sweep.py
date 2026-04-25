"""
Confidence threshold sweep for ThermalDrone model.

Evaluates best.pt at thresholds [0.15, 0.20, 0.25, 0.30] across:
  - Anti-UAV410 test split (frame-level IoU=0.5)
  - Anti-MUAV1 (multi-track matching)
  - SIDD val (model.val())

Selects threshold with highest mean F1 across all three benchmarks.

Usage:
    python scripts/conf_sweep.py [--weights PATH] [--output PATH]
"""

import argparse
import json
import logging
import sys
from pathlib import Path

import cv2
from ultralytics import YOLO

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger(__name__)

BASE = Path("/home/safsaf/Projects/UAV/UAV-dataset-workflow")
MODELS_DIR      = Path("/home/safsaf/Projects/UAV/models")
DEFAULT_WEIGHTS = MODELS_DIR / "ThermalDrone_best.pt"
DEFAULT_OUTPUT  = BASE / "training/thermal_improvement/conf_sweep_results.json"

ANTIUAV410_DATASETS = BASE / "thermal_datasets/Anti-UAV410-main/datasets/Anti-UAV410"
ANTIUAV410_ANNOS    = BASE / "thermal_datasets/Anti-UAV410-main/annos"
MUAV1_DATASET       = BASE / "thermal_datasets/MOT_IR_sequences"
SIDD_DATA_YAML      = BASE / "thermal_datasets/thermal_merged/data.yaml"

THRESHOLDS = [0.15, 0.20, 0.25, 0.30]
IOU_THRESH = 0.5
IMG_SIZE   = 640


# ---------------------------------------------------------------------------
# Shared IoU helper
# ---------------------------------------------------------------------------

def iou(boxA, boxB):
    xA = max(boxA[0], boxB[0])
    yA = max(boxA[1], boxB[1])
    xB = min(boxA[2], boxB[2])
    yB = min(boxA[3], boxB[3])
    inter = max(0, xB - xA) * max(0, yB - yA)
    if inter == 0:
        return 0.0
    areaA = (boxA[2] - boxA[0]) * (boxA[3] - boxA[1])
    areaB = (boxB[2] - boxB[0]) * (boxB[3] - boxB[1])
    return inter / (areaA + areaB - inter)


# ---------------------------------------------------------------------------
# Anti-UAV410 evaluation (inlined from eval_benchmark.py)
# ---------------------------------------------------------------------------

def parse_antiuav410_anno(anno_path):
    boxes = []
    for line in Path(anno_path).read_text().strip().splitlines():
        parts = [float(v) for v in line.strip().split(",")]
        x, y, w, h = parts
        if w == 0 and h == 0:
            boxes.append(None)
        else:
            boxes.append((x, y, x + w, y + h))
    return boxes


def find_frames(video_dir):
    exts = {".jpg", ".jpeg", ".png", ".bmp"}
    return sorted([f for f in Path(video_dir).iterdir() if f.suffix.lower() in exts])


def eval_antiuav410_sequence_multi(model, frames, gt_boxes):
    """Run inference once per frame, collect raw boxes + conf scores for all thresholds."""
    raw = []  # list of (gt, det_boxes_with_conf)
    n = min(len(frames), len(gt_boxes))
    for i in range(n):
        gt = gt_boxes[i]
        img = cv2.imread(str(frames[i]))
        if img is None:
            continue
        # Use very low conf to get all detections; filter per threshold later
        preds = model(img, imgsz=IMG_SIZE, conf=0.01, verbose=False)[0]
        det_boxes = []
        if preds.boxes is not None and len(preds.boxes):
            for box, conf_score in zip(preds.boxes.xyxy.cpu().numpy(),
                                       preds.boxes.conf.cpu().numpy()):
                det_boxes.append((tuple(box[:4]), float(conf_score)))
        raw.append((gt, det_boxes))
    return raw


def threshold_antiuav410(raw, conf):
    results = []
    for gt, det_boxes_conf in raw:
        visible = gt is not None
        det_boxes = [b for b, c in det_boxes_conf if c >= conf]
        if visible:
            matched = any(iou(gt, d) >= IOU_THRESH for d in det_boxes)
            results.append({"visible": True, "tp": int(matched), "fn": int(not matched), "fp": 0})
        else:
            results.append({"visible": False, "tp": 0, "fn": 0, "fp": int(len(det_boxes) > 0)})
    return results


def eval_antiuav410_sequence(model, frames, gt_boxes, conf):
    raw = eval_antiuav410_sequence_multi(model, frames, gt_boxes)
    return threshold_antiuav410(raw, conf)


def aggregate_antiuav410(all_results):
    tp = sum(r["tp"] for r in all_results)
    fp = sum(r["fp"] for r in all_results)
    fn = sum(r["fn"] for r in all_results)
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall    = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1        = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
    return {"precision": round(precision, 4), "recall": round(recall, 4), "f1": round(f1, 4)}


def run_antiuav410_eval_multi(model):
    """Single inference pass over Anti-UAV410 test split; returns raw per-frame data."""
    anno_dir   = ANTIUAV410_ANNOS / "test"
    frames_dir = ANTIUAV410_DATASETS / "test"
    if not anno_dir.exists() or not frames_dir.exists():
        log.warning("Anti-UAV410 test split not found, skipping")
        return None
    all_raw = []
    for anno_file in sorted(anno_dir.glob("*.txt")):
        seq_name = anno_file.stem
        seq_dir  = frames_dir / seq_name
        if not seq_dir.exists():
            continue
        frames   = find_frames(seq_dir)
        gt_boxes = parse_antiuav410_anno(anno_file)
        if not frames:
            continue
        all_raw.extend(eval_antiuav410_sequence_multi(model, frames, gt_boxes))
    return all_raw


def run_antiuav410_eval(model, conf, raw=None):
    if raw is None:
        raw = run_antiuav410_eval_multi(model)
    if not raw:
        return {"precision": 0.0, "recall": 0.0, "f1": 0.0}
    return aggregate_antiuav410(threshold_antiuav410(raw, conf))


# ---------------------------------------------------------------------------
# Anti-MUAV1 evaluation (inlined from eval_muav.py)
# ---------------------------------------------------------------------------

def parse_muav_gt(gt_path):
    result = {}
    for line in Path(gt_path).read_text().strip().splitlines():
        parts = line.strip().split(",")
        fname = parts[0].strip()
        x1, y1, x2, y2 = float(parts[1]), float(parts[2]), float(parts[3]), float(parts[4])
        out_of_view = int(parts[5]) if len(parts) > 5 else 0
        if out_of_view == 1 or (x1 == 0 and y1 == 0 and x2 == 0 and y2 == 0):
            result[fname] = None
        else:
            result[fname] = (x1, y1, x2, y2)
    return result


def eval_muav_sequence_multi(model, seq_dir, gt_files):
    """Single inference pass; returns raw per-frame data for threshold filtering."""
    frames = sorted(seq_dir.glob("*.jpg"))
    tracks = [parse_muav_gt(gt) for gt in gt_files]
    raw = []  # list of (tracks_gt_per_frame, det_boxes_with_conf)
    for frame_path in frames:
        fname = frame_path.name
        img = cv2.imread(str(frame_path))
        if img is None:
            continue
        preds = model(img, imgsz=IMG_SIZE, conf=0.01, verbose=False)[0]
        det_boxes = []
        if preds.boxes is not None and len(preds.boxes):
            for box, conf_score in zip(preds.boxes.xyxy.cpu().numpy(),
                                       preds.boxes.conf.cpu().numpy()):
                det_boxes.append((tuple(box[:4]), float(conf_score)))
        frame_gts = [track.get(fname) for track in tracks]
        raw.append((fname, frame_gts, det_boxes))
    return raw


def threshold_muav(raw, conf):
    n_tracks = len(raw[0][1]) if raw else 0
    obj_stats = [{"tp": 0, "fn": 0} for _ in range(n_tracks)]
    fp_frames = 0
    for fname, frame_gts, det_boxes_conf in raw:
        det_boxes = [b for b, c in det_boxes_conf if c >= conf]
        matched_dets = set()
        for i, gt in enumerate(frame_gts):
            if gt is None:
                continue
            best_iou, best_j = 0, -1
            for j, det in enumerate(det_boxes):
                if j in matched_dets:
                    continue
                v = iou(gt, det)
                if v > best_iou:
                    best_iou, best_j = v, j
            if best_iou >= IOU_THRESH:
                obj_stats[i]["tp"] += 1
                matched_dets.add(best_j)
            else:
                obj_stats[i]["fn"] += 1
        any_visible = any(gt is not None for gt in frame_gts)
        if not any_visible and len(det_boxes) > 0:
            fp_frames += 1
    return obj_stats, fp_frames


def eval_muav_sequence(model, seq_dir, gt_files, conf):
    raw = eval_muav_sequence_multi(model, seq_dir, gt_files)
    return threshold_muav(raw, conf)


def run_muav1_eval_multi(model):
    """Single inference pass over all MUAV1 sequences."""
    if not MUAV1_DATASET.exists():
        log.warning("Anti-MUAV1 dataset not found, skipping")
        return None
    all_raw = []
    for seq in sorted(MUAV1_DATASET.iterdir()):
        gt_files = sorted(seq.glob("groundtruth*.txt"))
        if not gt_files:
            continue
        all_raw.append((seq, gt_files, eval_muav_sequence_multi(model, seq, gt_files)))
    return all_raw


def run_muav1_eval(model, conf, raw=None):
    if raw is None:
        raw = run_muav1_eval_multi(model)
    if raw is None:
        return {"precision": 0.0, "recall": 0.0, "f1": 0.0}
    all_tp = all_fn = all_fp_frames = 0
    for seq, gt_files, seq_raw in raw:
        obj_stats, fp_frames = threshold_muav(seq_raw, conf)
        all_tp        += sum(o["tp"] for o in obj_stats)
        all_fn        += sum(o["fn"] for o in obj_stats)
        all_fp_frames += fp_frames
    precision = all_tp / (all_tp + all_fp_frames) if (all_tp + all_fp_frames) > 0 else 0.0
    recall    = all_tp / (all_tp + all_fn)         if (all_tp + all_fn)         > 0 else 0.0
    f1        = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
    return {"precision": round(precision, 4), "recall": round(recall, 4), "f1": round(f1, 4)}


# ---------------------------------------------------------------------------
# SIDD val evaluation
# ---------------------------------------------------------------------------

def run_sidd_val(model, conf):
    if not SIDD_DATA_YAML.exists():
        log.warning("SIDD data.yaml not found, skipping")
        return {"precision": 0.0, "recall": 0.0, "mAP50": 0.0}
    metrics = model.val(data=str(SIDD_DATA_YAML), conf=conf, workers=0, verbose=False)
    return {
        "precision": round(float(metrics.box.mp), 4),
        "recall":    round(float(metrics.box.mr), 4),
        "mAP50":     round(float(metrics.box.map50), 4),
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Confidence threshold sweep")
    parser.add_argument("--weights", default=str(DEFAULT_WEIGHTS))
    parser.add_argument("--output",  default=str(DEFAULT_OUTPUT))
    args = parser.parse_args()

    weights_path = Path(args.weights)
    if not weights_path.exists():
        log.error(f"Weights file not found: {weights_path}")
        sys.exit(1)

    log.info(f"Loading model: {weights_path}")
    model = YOLO(str(weights_path))

    # Single inference pass over each dataset — reuse raw detections for all thresholds
    log.info("Running single inference pass over Anti-UAV410 test split...")
    antiuav_raw = run_antiuav410_eval_multi(model)
    log.info("Running single inference pass over Anti-MUAV1...")
    muav_raw = run_muav1_eval_multi(model)

    results = {}
    mean_f1s = {}

    for thresh in THRESHOLDS:
        key = str(thresh)
        log.info(f"Scoring threshold={thresh}")

        auav = run_antiuav410_eval(model, thresh, raw=antiuav_raw)
        muav = run_muav1_eval(model, thresh, raw=muav_raw)
        sidd = run_sidd_val(model, thresh)

        # Mean F1: use F1 for Anti-UAV410 and Anti-MUAV1; use mAP50 as proxy for SIDD
        f1_vals = [auav["f1"], muav["f1"], sidd.get("mAP50", sidd.get("f1", 0.0))]
        mean_f1 = sum(f1_vals) / len(f1_vals)

        results[key] = {"antiuav410": auav, "antimuav1": muav, "sidd_val": sidd}
        mean_f1s[key] = round(mean_f1, 4)
        log.info(f"  thresh={thresh}: Anti-UAV410 F1={auav['f1']:.4f}, Anti-MUAV1 F1={muav['f1']:.4f}, SIDD mAP50={sidd.get('mAP50', 0):.4f}, mean={mean_f1:.4f}")

    optimal_key = max(mean_f1s, key=lambda k: mean_f1s[k])
    optimal_threshold = float(optimal_key)

    output = {
        "thresholds": results,
        "optimal_threshold": optimal_threshold,
        "mean_f1_per_threshold": mean_f1s,
    }

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(output, indent=2))
    log.info(f"Results written to {out_path}")

    # Print formatted table
    header = f"{'Thresh':>8} | {'UAV410-P':>10} {'UAV410-R':>10} {'UAV410-F1':>10} | {'MUAV1-P':>8} {'MUAV1-R':>8} {'MUAV1-F1':>9} | {'SIDD-mAP50':>11} | {'MeanF1':>8}"
    print("\n" + header)
    print("-" * len(header))
    for thresh in THRESHOLDS:
        k = str(thresh)
        a = results[k]["antiuav410"]
        m = results[k]["antimuav1"]
        s = results[k]["sidd_val"]
        marker = " <-- optimal" if float(k) == optimal_threshold else ""
        print(
            f"{thresh:>8.2f} | {a['precision']:>10.4f} {a['recall']:>10.4f} {a['f1']:>10.4f} | "
            f"{m['precision']:>8.4f} {m['recall']:>8.4f} {m['f1']:>9.4f} | "
            f"{s.get('mAP50', 0):>11.4f} | {mean_f1s[k]:>8.4f}{marker}"
        )
    print(f"\nOptimal threshold: {optimal_threshold}")


if __name__ == "__main__":
    main()
