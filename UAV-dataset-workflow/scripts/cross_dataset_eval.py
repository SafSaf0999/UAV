"""
Cross-dataset evaluation of all 3 trained models against:
  Section A: Available datasets in datasets/ folder (held-out test splits)
  Section B: DUT Anti-UAV (if downloaded, else skip with note)

Run names (unique):
  - BirdDrone-RTX   : run_2class_yolo26s_rtx2070_100ep   (2-class, Bird/Drone)
  - TriClass-T4     : run_3class_yolo26s_colab_t4_100ep  (3-class, Bird/Drone/UAV)
  - BirdDrone-T4old : run_2class_yolo26s_colab_t4_160ep_old (2-class old, Bird/Drone)

For each model we build a temporary data.yaml pointing at the test split,
run YOLO val, and collect mAP50, mAP50-95, precision, recall.
"""
from __future__ import annotations
import shutil
import tempfile
from pathlib import Path
from datetime import datetime
import yaml
import csv

ROOT     = Path("/home/safsaf/Projects/UAV-dataset-workflow")
TRAINING = ROOT / "training"
DATASETS = ROOT / "datasets"
COMP_DIR = ROOT / "comparison"
COMP_DIR.mkdir(exist_ok=True)

TIMESTAMP = datetime.now().strftime("%Y%m%d_%H%M%S")

# ── Model registry ────────────────────────────────────────────────────────────
MODELS = [
    {
        "name":    "BirdDrone-RTX",
        "label":   "YOLO26s 2-class BirdDrone-RTX (Bird/Drone, RTX 2070, 100ep)",
        "weights": TRAINING / "run_2class_yolo26s_rtx2070_100ep" / "weights" / "best.pt",
        "classes": {0: "Bird", 1: "Drone"},
        "nc":      2,
    },
    {
        "name":    "TriClass-T4",
        "label":   "YOLO26s 3-class TriClass-T4 (Bird/Drone/UAV, T4, 100ep)",
        "weights": TRAINING / "run_3class_yolo26s_colab_t4_100ep" / "weights" / "best.pt",
        "classes": {0: "Bird", 1: "Drone", 2: "UAV"},
        "nc":      3,
    },
    {
        "name":    "BirdDrone-T4old",
        "label":   "YOLO26s 2-class BirdDrone-T4old (Bird/Drone, T4, 160ep)",
        "weights": TRAINING / "run_2class_yolo26s_colab_t4_160ep_old" / "weights" / "best.pt",
        "classes": {0: "Bird", 1: "Drone"},
        "nc":      2,
    },
]

# ── Test datasets (Section A) ─────────────────────────────────────────────────
# Each entry: name, images dir, labels dir, class token→canonical
TEST_SETS_A = [
    {
        "name":    "anti-uav-test",
        "desc":    "Anti-UAV test split (1,659 images, UAV class)",
        "img_dir": DATASETS / "anti-uav" / "test" / "images",
        "lbl_dir": DATASETS / "anti-uav" / "test" / "labels",
        "token":   "UAV",   # raw token in labels
        "canonical": "Drone",  # maps to Drone in 2-class, UAV in 3-class
    },
    {
        "name":    "uavdetector-test",
        "desc":    "UAVDetector test split (165 images, fixed-wing UAV)",
        "img_dir": DATASETS / "uavdetector" / "test" / "images",
        "lbl_dir": DATASETS / "uavdetector" / "test" / "labels",
        "token":   "UAV",
        "canonical": "Drone",
    },
    {
        "name":    "yolo-exp-test",
        "desc":    "YOLO-exp test split (762 images, Bird+Drone)",
        "img_dir": DATASETS / "yolo-exp" / "test" / "images",
        "lbl_dir": DATASETS / "yolo-exp" / "test" / "labels",
        "token":   None,   # mixed: 0=Bird, 1=drone
        "canonical": "mixed",
    },
    {
        "name":    "birds-valid",
        "desc":    "Birds.v1i valid split (378 images, Bird only)",
        "img_dir": DATASETS / "Birds.v1i.yolov8" / "valid" / "images",
        "lbl_dir": DATASETS / "Birds.v1i.yolov8" / "valid" / "labels",
        "token":   "0",
        "canonical": "Bird",
    },
]

# ── DUT Anti-UAV (Section B) ──────────────────────────────────────────────────
DUT_TEST = ROOT / "datasets" / "thermal" / "DUT-Anti-UAV" / "test"


def make_temp_yaml(img_dir: Path, lbl_dir: Path,
                   nc: int, names: list[str],
                   token_remap: dict[str, int]) -> Path:
    """
    Build a temporary dataset with remapped integer labels.
    Copies images (no symlink) so YOLO resolves labels from temp dir.
    """
    tmp = Path(tempfile.mkdtemp())
    img_out = tmp / "images"
    lbl_out = tmp / "labels"
    img_out.mkdir()
    lbl_out.mkdir()

    for img in img_dir.iterdir():
        if img.suffix.lower() not in {".jpg",".jpeg",".png",".bmp"}:
            continue
        # Find matching label
        lbl = lbl_dir / (img.stem + ".txt")
        if not lbl.is_file():
            continue
        lines_out = []
        for line in lbl.read_text().splitlines():
            parts = line.strip().split()
            if len(parts) != 5:
                continue
            try:
                [float(v) for v in parts[1:]]
            except ValueError:
                continue
            token = parts[0]
            if token in token_remap:
                new_cls = token_remap[token]
                lines_out.append(f"{new_cls} " + " ".join(parts[1:]))
        if lines_out:
            shutil.copy2(img, img_out / img.name)
            (lbl_out / (img.stem + ".txt")).write_text("\n".join(lines_out))

    n_imgs = len(list(img_out.iterdir()))
    print(f"    Prepared {n_imgs} images with remapped labels")

    data = {
        "path":  str(tmp),
        "train": "images",
        "val":   "images",
        "test":  "images",
        "nc":    nc,
        "names": names,
    }
    (tmp / "data.yaml").write_text(yaml.dump(data))
    return tmp


def run_val(weights: Path, data_yaml: Path, name: str) -> dict:
    """Run YOLO val and return metrics dict."""
    from ultralytics import YOLO
    model = YOLO(str(weights))
    results = model.val(
        data=str(data_yaml),
        split="test",
        imgsz=640,
        batch=16,
        device=0,
        workers=0,
        verbose=False,
        plots=False,
        save_json=False,
        name=f"eval_{name}",
        project=str(COMP_DIR / "val_runs"),
        exist_ok=True,
    )
    box = results.box
    return {
        "map50":     round(float(box.map50),   4),
        "map50_95":  round(float(box.map),     4),
        "precision": round(float(box.mp),      4),
        "recall":    round(float(box.mr),      4),
    }


def build_token_remap(test_set: dict, model: dict) -> dict[str, int]:
    """Map raw label tokens to model class indices."""
    names = list(model["classes"].values())  # e.g. ["Bird","Drone"]
    remap = {}

    if test_set["canonical"] == "Bird":
        # All annotations are Bird
        idx = names.index("Bird") if "Bird" in names else None
        if idx is not None:
            remap[test_set["token"]] = idx
            remap["0"] = idx

    elif test_set["canonical"] == "Drone":
        # All annotations are Drone (or UAV→Drone)
        idx = names.index("Drone") if "Drone" in names else (
              names.index("UAV")   if "UAV"   in names else None)
        if idx is not None:
            remap[test_set["token"]] = idx
            remap["UAV"] = idx
            remap["0"] = idx

    elif test_set["canonical"] == "mixed":
        # yolo-exp: 0=Bird, 1=drone
        if "Bird" in names:
            remap["0"] = names.index("Bird")
        if "Drone" in names:
            remap["1"] = names.index("Drone")
            remap["drone"] = names.index("Drone")

    return remap


# ── Run Section A ─────────────────────────────────────────────────────────────
print("\n" + "="*60)
print("SECTION A: Evaluation on datasets/ test splits")
print("="*60)

results_a: list[dict] = []

for model in MODELS:
    if not model["weights"].is_file():
        print(f"  SKIP {model['name']} — weights not found")
        continue
    names = list(model["classes"].values())
    for ts in TEST_SETS_A:
        if not ts["img_dir"].is_dir():
            print(f"  SKIP {ts['name']} — not found")
            continue
        remap = build_token_remap(ts, model)
        if not remap:
            print(f"  SKIP {model['name']} x {ts['name']} — no valid class mapping")
            continue

        print(f"  Evaluating {model['name']} on {ts['name']}...")
        tmp_dir = make_temp_yaml(ts["img_dir"], ts["lbl_dir"],
                                 model["nc"], names, remap)
        try:
            metrics = run_val(model["weights"], tmp_dir / "data.yaml",
                              f"{model['name']}_{ts['name']}")
            if metrics["map50"] == 0.0 and metrics["recall"] == 0.0:
                metrics["note"] = "zero detections — domain mismatch or label format issue"
            row = {"model": model["name"], "test_set": ts["name"],
                   "desc": ts["desc"], **metrics}
            results_a.append(row)
            print(f"    mAP50={metrics['map50']:.3f}  P={metrics['precision']:.3f}  R={metrics['recall']:.3f}")
        except Exception as e:
            print(f"    ERROR: {e}")
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

# ── Run Section B ─────────────────────────────────────────────────────────────
print("\n" + "="*60)
print("SECTION B: DUT Anti-UAV dataset")
print("="*60)

results_b: list[dict] = []

if not DUT_TEST.is_dir():
    print("  DUT Anti-UAV not downloaded yet.")
    print("  Download from: https://github.com/wangdongdut/DUT-Anti-UAV")
    print("  Place at: datasets/thermal/DUT-Anti-UAV/")
    results_b = [{"note": "DUT Anti-UAV not available — requires Google Drive download"}]
else:
    dut_img = DUT_TEST / "images"
    dut_lbl = DUT_TEST / "labels"
    for model in MODELS:
        if not model["weights"].is_file():
            continue
        names = list(model["classes"].values())
        # DUT labels use integer 0 for UAV
        remap = {}
        if "Drone" in names:
            remap["0"] = names.index("Drone")
        elif "UAV" in names:
            remap["0"] = names.index("UAV")
        if not remap:
            continue
        print(f"  Evaluating {model['name']} on DUT Anti-UAV...")
        tmp_dir = make_temp_yaml(dut_img, dut_lbl, model["nc"], names, remap)
        try:
            metrics = run_val(model["weights"], tmp_dir / "data.yaml",
                              f"{model['name']}_DUT")
            row = {"model": model["name"], "test_set": "DUT-Anti-UAV",
                   "desc": "DUT Anti-UAV test (RGB daytime, UAV only)", **metrics}
            results_b.append(row)
            print(f"    mAP50={metrics['map50']:.3f}  P={metrics['precision']:.3f}  R={metrics['recall']:.3f}")
        except Exception as e:
            print(f"    ERROR: {e}")
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

# ── Write results ─────────────────────────────────────────────────────────────
out_csv = COMP_DIR / f"cross_eval_{TIMESTAMP}.csv"
out_md  = COMP_DIR / f"cross_eval_{TIMESTAMP}.md"

fields = ["model","test_set","desc","map50","map50_95","precision","recall"]
with open(out_csv, "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
    w.writeheader()
    for r in results_a + (results_b if isinstance(results_b[0], dict) and "map50" in results_b[0] else []):
        w.writerow(r)

def fmt(v): return f"{v:.3f}" if isinstance(v, float) else str(v)

with open(out_md, "w") as f:
    f.write("# Cross-Dataset Evaluation Report\n\n")
    f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n")
    f.write("## Model Registry\n\n")
    for m in MODELS:
        f.write(f"- **{m['name']}**: {m['label']}\n")
    f.write("\n---\n\n")

    f.write("## Section A: Evaluation on Internal Test Splits\n\n")
    f.write("> Models evaluated on held-out test splits from the `datasets/` folder. "
            "None of these images were seen during training.\n\n")
    f.write("| Model | Test Set | Description | mAP@0.5 | mAP@0.5:0.95 | Precision | Recall |\n")
    f.write("|---|---|---|---|---|---|---|\n")
    for r in results_a:
        f.write(f"| {r['model']} | {r['test_set']} | {r['desc']} | "
                f"**{fmt(r['map50'])}** | {fmt(r['map50_95'])} | "
                f"{fmt(r['precision'])} | {fmt(r['recall'])} |\n")

    f.write("\n---\n\n")
    f.write("## Section B: DUT Anti-UAV Challenge Dataset\n\n")
    f.write("> DUT Anti-UAV (IEEE-TITS 2022) — RGB daytime UAV detection benchmark. "
            "Published results: YOLOX mAP@0.5 ≈ 0.72, Cascade-RCNN ≈ 0.68.\n\n")
    if results_b and "map50" in results_b[0]:
        f.write("| Model | Test Set | mAP@0.5 | mAP@0.5:0.95 | Precision | Recall |\n")
        f.write("|---|---|---|---|---|---|\n")
        for r in results_b:
            f.write(f"| {r['model']} | {r['test_set']} | "
                    f"**{fmt(r['map50'])}** | {fmt(r['map50_95'])} | "
                    f"{fmt(r['precision'])} | {fmt(r['recall'])} |\n")
        f.write("\n**Published DUT baselines:** YOLOX 0.720 | Cascade-RCNN 0.680 | ATSS 0.665\n")
    else:
        f.write("DUT Anti-UAV dataset not yet downloaded. "
                "Download from https://github.com/wangdongdut/DUT-Anti-UAV "
                "and place at `datasets/thermal/DUT-Anti-UAV/`.\n")

print(f"\nCSV: {out_csv}")
print(f"MD:  {out_md}")
