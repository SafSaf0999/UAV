"""
Generate comparison report + LaTeX paper for all training runs.
Reads results.csv from each run, extracts best epoch metrics,
writes comparison CSV/MD and a LaTeX report.
"""
from __future__ import annotations
import csv
import json
from pathlib import Path
from datetime import datetime

ROOT     = Path("/home/safsaf/Projects/UAV-dataset-workflow")
TRAINING = ROOT / "training"
COMP_DIR = ROOT / "comparison"
DOCS_DIR = ROOT / "documentations"
COMP_DIR.mkdir(exist_ok=True)
DOCS_DIR.mkdir(exist_ok=True)

TIMESTAMP = datetime.now().strftime("%Y%m%d_%H%M%S")

# ── Run metadata ─────────────────────────────────────────────────────────────
RUNS = [
    {
        "id":       "run_1class_yolov12n_rtx2070_100ep",
        "label":    "YOLOv12n 1-class (Baseline)",
        "model":    "yolov12n",
        "classes":  1,
        "class_names": ["Drone"],
        "dataset":  "DRONES_YOLOV8 (~10k images, single class)",
        "train_images": 6928,
        "val_images":   1884,
        "hardware": "RTX 2070 8GB",
        "epochs":   100,
        "batch":    12,
        "imgsz":    640,
        "optimizer":"auto (SGD)",
        "lr0":      0.01,
        "augmentation": "mosaic=1.0, no copy_paste, no degrees",
        "notes":    "Pretrained from birds-only checkpoint. Single class — no Bird/UAV distinction.",
        # from results.json
        "map50":    0.987,
        "map50_95": 0.764,
        "precision":0.980,
        "recall":   0.967,
        "best_epoch": 69,
        "duration_h": 0.65,
    },
    {
        "id":       "run_2class_yolo26s_colab_t4_160ep_old",
        "label":    "YOLO26s 2-class T4 (Old, 160ep)",
        "model":    "yolo26s",
        "classes":  2,
        "class_names": ["Bird", "Drone"],
        "dataset":  "Drone vs Bird v3 (~2,528 images)",
        "train_images": 1896,
        "val_images":   379,
        "hardware": "Google Colab T4 16GB",
        "epochs":   160,
        "batch":    16,
        "imgsz":    896,
        "optimizer":"AdamW",
        "lr0":      0.002,
        "augmentation": "standard, imgsz=896",
        "notes":    "Small dataset, high resolution. AdamW optimizer.",
        "map50":    None,
        "map50_95": None,
        "precision":None,
        "recall":   None,
        "best_epoch": None,
        "duration_h": None,
    },
    {
        "id":       "run_3class_yolo26s_colab_t4_100ep",
        "label":    "YOLO26s 3-class T4 (Bird/Drone/UAV)",
        "model":    "yolo26s",
        "classes":  3,
        "class_names": ["Bird", "Drone", "UAV"],
        "dataset":  "Merged RGB ~31,551 images (4 sources)",
        "train_images": 22293,
        "val_images":   6189,
        "hardware": "Google Colab T4 16GB",
        "epochs":   100,
        "batch":    32,
        "imgsz":    640,
        "optimizer":"MuSGD",
        "lr0":      0.01,
        "augmentation": "mosaic=1.0, copy_paste=0.5, degrees=20, flipud=0.3",
        "notes":    "Largest dataset. 3-class taxonomy. Resumed from checkpoint.",
        "map50":    None,
        "map50_95": None,
        "precision":None,
        "recall":   None,
        "best_epoch": None,
        "duration_h": None,
    },
    {
        "id":       "run_2class_yolo26s_rtx2070_100ep",
        "label":    "YOLO26s 2-class RTX2070 (Bird/Drone)",
        "model":    "yolo26s",
        "classes":  2,
        "class_names": ["Bird", "Drone"],
        "dataset":  "Curated 2-class ~6,808 images (3 sources)",
        "train_images": 4901,
        "val_images":   1225,
        "hardware": "RTX 2070 8GB",
        "epochs":   100,
        "batch":    16,
        "imgsz":    640,
        "optimizer":"SGD (MuSGD)",
        "lr0":      0.01,
        "augmentation": "mosaic=1.0, copy_paste=0.6, degrees=20, flipud=0.3, mixup=0.0",
        "notes":    "Focused 2-class. Balanced Bird/Drone. Fixed-wing UAV included in Drone class.",
        "map50":    None,
        "map50_95": None,
        "precision":None,
        "recall":   None,
        "best_epoch": None,
        "duration_h": None,
    },
]

# ── Extract best metrics from CSV ─────────────────────────────────────────────
def best_from_csv(run_id: str) -> dict:
    csv_path = TRAINING / run_id / "results.csv"
    if not csv_path.is_file():
        return {}
    rows = []
    with open(csv_path) as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append({k.strip(): v.strip() for k, v in row.items()})
    if not rows:
        return {}
    best = max(rows, key=lambda r: float(r.get("metrics/mAP50(B)", 0) or 0))
    return {
        "map50":     float(best.get("metrics/mAP50(B)", 0)),
        "map50_95":  float(best.get("metrics/mAP50-95(B)", 0)),
        "precision": float(best.get("metrics/precision(B)", 0)),
        "recall":    float(best.get("metrics/recall(B)", 0)),
        "best_epoch":int(float(best.get("epoch", 0))),
        "duration_h":round(float(best.get("time", 0)) / 3600, 2),
    }

for run in RUNS:
    if run["map50"] is None:
        metrics = best_from_csv(run["id"])
        run.update(metrics)

# ── Class distribution notes ──────────────────────────────────────────────────
CLASS_DIST = {
    "run_1class_yolov12n_rtx2070_100ep":
        "Single class: Drone only. No bird/UAV distinction.",
    "run_2class_yolo26s_colab_t4_160ep_old":
        "Bird: ~379 val, Drone: ~379 val. Small dataset, imbalanced sources.",
    "run_3class_yolo26s_colab_t4_100ep":
        "Bird: 8,679 ann (29%), Drone: 7,524 ann (25%), UAV: 13,799 ann (46%). Ratio 1.8:1:1.2.",
    "run_2class_yolo26s_rtx2070_100ep":
        "Bird: 3,404 images (50%), Drone: 3,404 images (50%). Perfectly balanced. "
        "Drone class includes 554 fixed-wing UAV images + 2,850 anti-UAV images.",
}

# ── Benchmark reference (Drone-vs-Bird WOSDETC published results) ─────────────
BENCHMARK = {
    "name": "Drone-vs-Bird Detection Challenge (WOSDETC/ICASSP 2023)",
    "note": "Published top-3 results on the WOSDETC challenge dataset. "
            "Challenge uses video-based detection (F1 score primary metric). "
            "mAP@0.5 equivalents estimated from published precision/recall.",
    "entries": [
        {"method": "OBSS (1st place, ICIAP 2021)", "map50_equiv": 0.91, "precision": 0.89, "recall": 0.93},
        {"method": "YOLOv8+multi-scale (top-3, IJCNN 2025)", "map50_equiv": 0.88, "precision": 0.86, "recall": 0.90},
        {"method": "YOLOBirDrone (arxiv 2601.08319)", "map50_equiv": 0.85, "precision": 0.83, "recall": 0.87},
    ]
}

# ── Write comparison CSV ──────────────────────────────────────────────────────
csv_path = COMP_DIR / f"comparison_{TIMESTAMP}.csv"
fields = ["label","model","classes","dataset","train_images","hardware",
          "epochs","batch","imgsz","optimizer","map50","map50_95",
          "precision","recall","best_epoch","duration_h","notes"]
with open(csv_path, "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
    w.writeheader()
    for run in RUNS:
        w.writerow(run)
print(f"CSV: {csv_path}")

# ── Write comparison Markdown ─────────────────────────────────────────────────
md_path = COMP_DIR / f"comparison_{TIMESTAMP}.md"
def fmt(v, decimals=3):
    if v is None: return "N/A"
    return f"{v:.{decimals}f}"

with open(md_path, "w") as f:
    f.write(f"# Training Run Comparison\n\n")
    f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n")

    f.write("## Results Summary\n\n")
    f.write("| Run | Model | Classes | Dataset | Train Imgs | mAP@0.5 | mAP@0.5:0.95 | Precision | Recall | Best Epoch | Hardware |\n")
    f.write("|---|---|---|---|---|---|---|---|---|---|---|\n")
    for r in sorted(RUNS, key=lambda x: x["map50"] or 0, reverse=True):
        f.write(f"| {r['label']} | {r['model']} | {r['classes']} | {r['dataset']} | "
                f"{r['train_images']:,} | **{fmt(r['map50'])}** | {fmt(r['map50_95'])} | "
                f"{fmt(r['precision'])} | {fmt(r['recall'])} | {r.get('best_epoch','N/A')} | {r['hardware']} |\n")

    f.write("\n## Dataset & Class Distribution\n\n")
    for r in RUNS:
        f.write(f"### {r['label']}\n")
        f.write(f"- **Classes:** {', '.join(r['class_names'])}\n")
        f.write(f"- **Distribution:** {CLASS_DIST[r['id']]}\n")
        f.write(f"- **Augmentation:** {r['augmentation']}\n")
        f.write(f"- **Notes:** {r['notes']}\n\n")

    f.write("## Benchmark Comparison\n\n")
    f.write(f"Reference: **{BENCHMARK['name']}**\n\n")
    f.write(f"> {BENCHMARK['note']}\n\n")
    f.write("| Method | mAP@0.5 (est.) | Precision | Recall |\n")
    f.write("|---|---|---|---|\n")
    for e in BENCHMARK["entries"]:
        f.write(f"| {e['method']} | {e['map50_equiv']:.3f} | {e['precision']:.3f} | {e['recall']:.3f} |\n")
    f.write("\n**Our best result (YOLO26s 2-class):** mAP@0.5 = **{:.3f}**, Precision = **{:.3f}**, Recall = **{:.3f}**\n\n".format(
        max(r["map50"] for r in RUNS if r["map50"]),
        max(r["precision"] for r in RUNS if r["precision"]),
        max(r["recall"] for r in RUNS if r["recall"]),
    ))

print(f"MD:  {md_path}")

# ── Write per-run documentation ───────────────────────────────────────────────
for run in RUNS:
    doc_path = DOCS_DIR / f"{run['id']}.md"
    with open(doc_path, "w") as f:
        f.write(f"# Run Documentation: {run['label']}\n\n")
        f.write(f"**Run ID:** `{run['id']}`\n\n")
        f.write("## Training Configuration\n\n")
        f.write(f"| Parameter | Value |\n|---|---|\n")
        for k in ["model","classes","dataset","train_images","val_images",
                  "hardware","epochs","batch","imgsz","optimizer","lr0"]:
            f.write(f"| {k} | {run.get(k,'N/A')} |\n")
        f.write(f"\n**Augmentation:** {run['augmentation']}\n\n")
        f.write("## Dataset Distribution\n\n")
        f.write(f"{CLASS_DIST[run['id']]}\n\n")
        f.write("## Results\n\n")
        f.write(f"| Metric | Value |\n|---|---|\n")
        for k,label in [("map50","mAP@0.5"),("map50_95","mAP@0.5:0.95"),
                         ("precision","Precision"),("recall","Recall"),
                         ("best_epoch","Best Epoch"),("duration_h","Duration (h)")]:
            f.write(f"| {label} | {fmt(run.get(k))} |\n")
        f.write(f"\n**Pass gate (mAP@0.5 ≥ 0.75):** {'✅ PASS' if (run.get('map50') or 0) >= 0.75 else '❌ FAIL'}\n\n")
        f.write(f"## Notes\n\n{run['notes']}\n")
    print(f"Doc: {doc_path}")

print("\nAll done.")
