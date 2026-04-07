"""
Step 1: Build pseudo-label dataset from DUT Anti-UAV frames.

For each video:
  - Frame 0: use hard GT from gt_first.txt (always included)
  - Remaining frames: use model predictions at conf >= 0.70

Outputs two datasets:
  datasets/dut_pseudolabels_2class/   ← for BirdDrone-Local (Bird=0, Drone=1)
  datasets/dut_pseudolabels_3class/   ← for TriClass-Cloud  (Bird=0, Drone=1, UAV=2)

Structure: flat images/ + labels/ (no train/val split yet — done in next script)
"""
from __future__ import annotations
import shutil
from pathlib import Path

ROOT     = Path("/home/safsaf/Projects/UAV-dataset-workflow")
DUT_ROOT = ROOT / "datasets" / "DUT Anti-UAV" / "Anti-UAV-Tracking-V0"
CONF     = 0.70
BATCH    = 32

CONFIGS = [
    {
        "name":    "2class",
        "weights": ROOT / "training" / "run_2class_yolo26s_rtx2070_100ep" / "weights" / "best.pt",
        "out":     ROOT / "datasets" / "dut_pseudolabels_2class",
        "nc":      2,
        "names":   ["Bird", "Drone"],
        # Map model class IDs to output class IDs (identity for 2class)
        "cls_map": {0: 0, 1: 1},
    },
    {
        "name":    "3class",
        "weights": ROOT / "training" / "run_3class_yolo26s_colab_t4_100ep" / "weights" / "best.pt",
        "out":     ROOT / "datasets" / "dut_pseudolabels_3class",
        "nc":      3,
        "names":   ["Bird", "Drone", "UAV"],
        # Merge Drone(1) and UAV(2) → both become Drone(1) for consistency
        "cls_map": {0: 0, 1: 1, 2: 1},
    },
]


def parse_gt(txt: Path, img_w: int, img_h: int) -> str | None:
    """Convert gt_first.txt (x y w h pixels) to YOLO line (cls cx cy w h norm)."""
    try:
        x, y, w, h = map(float, txt.read_text().strip().split()[:4])
        cx = (x + w/2) / img_w
        cy = (y + h/2) / img_h
        wn = w / img_w
        hn = h / img_h
        # GT is always Drone class (1 for 2class, 1 for 3class after merge)
        return f"1 {cx:.6f} {cy:.6f} {wn:.6f} {hn:.6f}"
    except Exception:
        return None


def main():
    from ultralytics import YOLO
    from PIL import Image

    video_dirs = sorted(d for d in DUT_ROOT.iterdir() if d.is_dir())

    for cfg in CONFIGS:
        out = cfg["out"]
        if out.exists():
            shutil.rmtree(out)
        (out / "images").mkdir(parents=True)
        (out / "labels").mkdir(parents=True)

        model = YOLO(str(cfg["weights"]))
        written = skipped = 0
        print(f"\n{'='*55}\nBuilding {cfg['name']} pseudo-labels → {out.name}")

        for vdir in video_dirs:
            frames = sorted(vdir.glob("*.jpg"))
            if not frames:
                continue
            gt_file = vdir / f"{vdir.name}_gt_first.txt"

            # Get image size from first frame
            img = Image.open(frames[0])
            W, H = img.size

            for i in range(0, len(frames), BATCH):
                batch = frames[i:i+BATCH]
                # Frame 0 gets hard GT label
                if i == 0:
                    gt_line = parse_gt(gt_file, W, H) if gt_file.is_file() else None
                    if gt_line:
                        stem = f"{vdir.name}_{frames[0].stem}"
                        shutil.copy2(frames[0], out / "images" / (stem + frames[0].suffix))
                        (out / "labels" / (stem + ".txt")).write_text(gt_line)
                        written += 1
                    batch = batch[1:]  # skip frame 0 from inference
                    if not batch:
                        continue

                results = model([str(p) for p in batch], conf=CONF, iou=0.45,
                                verbose=False, device=0, stream=False)

                for j, r in enumerate(results):
                    frame = batch[j]
                    boxes = r.boxes
                    if boxes is None or len(boxes) == 0:
                        skipped += 1
                        continue
                    # Only keep if max confidence >= threshold
                    if float(boxes.conf.max()) < CONF:
                        skipped += 1
                        continue

                    lines = []
                    for box in boxes:
                        cls_id = int(box.cls.item())
                        out_cls = cfg["cls_map"].get(cls_id, cls_id)
                        cx, cy, w, h = box.xywhn[0].tolist()
                        lines.append(f"{out_cls} {cx:.6f} {cy:.6f} {w:.6f} {h:.6f}")

                    stem = f"{vdir.name}_{frame.stem}"
                    shutil.copy2(frame, out / "images" / (stem + frame.suffix))
                    (out / "labels" / (stem + ".txt")).write_text("\n".join(lines))
                    written += 1

            print(f"  {vdir.name}: done")

        print(f"Written: {written:,}  Skipped: {skipped:,}")
        print(f"Output: {out}")


if __name__ == "__main__":
    main()
