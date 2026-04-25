"""
Merge 2-class dataset: Bird (0) vs Drone (1)

Sources and their explicit token→class mappings:
  Birds.v1i.yolov8  train/valid  token "0"   → Bird  (0)
  fixed-wing-uav    images/      token "0"   → Drone (1)   ← same token, different class!
  anti-uav          train/valid/test  token "UAV" → Drone (1)

Key fix: out_cls is passed explicitly per-source, NOT derived from the token.
"""
from __future__ import annotations
import random
import shutil
from pathlib import Path
import yaml

ROOT   = Path("/home/safsaf/Projects/UAV-dataset-workflow")
OUTPUT = ROOT / "merged_dataset_2class"
D      = ROOT / "datasets"
SEED   = 42
SPLITS = (0.72, 0.18, 0.10)
EXTS   = {".jpg", ".jpeg", ".png", ".bmp", ".tiff"}


# ── helpers ──────────────────────────────────────────────────────────────────

def is_bbox(line: str) -> bool:
    p = line.strip().split()
    if len(p) != 5:
        return False
    try:
        [float(v) for v in p[1:]]
        return True
    except ValueError:
        return False


def collect_split(base: Path, splits: list[str],
                  token: str, out_cls: int) -> list[tuple[Path, Path, int]]:
    """Collect (img, lbl, out_cls) from base/split/images + base/split/labels."""
    result = []
    for sp in splits:
        img_dir = base / sp / "images"
        lbl_dir = base / sp / "labels"
        if not img_dir.is_dir():
            continue
        for img in sorted(img_dir.iterdir()):
            if img.suffix.lower() not in EXTS:
                continue
            lbl = lbl_dir / (img.stem + ".txt")
            if not lbl.is_file():
                continue
            # Must have at least one valid bbox with the expected token
            if any(is_bbox(l) and l.strip().split()[0] == token
                   for l in lbl.read_text().splitlines()):
                result.append((img, lbl, out_cls))
    return result


def collect_flat(img_dir: Path, token: str,
                 out_cls: int) -> list[tuple[Path, Path, int]]:
    """Flat layout: images and .txt labels in the same folder."""
    result = []
    for img in sorted(img_dir.iterdir()):
        if img.suffix.lower() not in EXTS:
            continue
        lbl = img.with_suffix(".txt")
        if not lbl.is_file():
            continue
        if any(is_bbox(l) and l.strip().split()[0] == token
               for l in lbl.read_text().splitlines()):
            result.append((img, lbl, out_cls))
    return result


def convert_label(lbl: Path, token: str, out_cls: int) -> list[str]:
    """Rewrite label lines: replace token with out_cls integer."""
    lines = []
    for l in lbl.read_text().splitlines():
        if is_bbox(l) and l.strip().split()[0] == token:
            coords = " ".join(l.strip().split()[1:])
            lines.append(f"{out_cls} {coords}")
    return lines


def sha256(path: Path) -> str:
    import hashlib
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


# ── main ─────────────────────────────────────────────────────────────────────

def main() -> None:
    random.seed(SEED)

    # Collect — explicit token per source, explicit out_cls per source
    bird_pairs  = collect_split(D / "Birds.v1i.yolov8",
                                ["train", "valid"], "0", 0)
    drone_fw    = collect_flat(D / "fixed-wing-uav" / "images", "0", 1)
    drone_uav   = collect_split(D / "anti-uav",
                                ["train", "valid", "test"], "UAV", 1)
    drone_pairs = drone_fw + drone_uav

    print(f"Bird  ← Birds.v1i.yolov8 : {len(bird_pairs)}")
    print(f"Drone ← fixed-wing-uav   : {len(drone_fw)}")
    print(f"Drone ← anti-uav         : {len(drone_uav)}")
    print(f"Drone total              : {len(drone_pairs)}")

    # Balance
    n = min(len(bird_pairs), len(drone_pairs))
    random.shuffle(bird_pairs)
    random.shuffle(drone_pairs)
    bird_pairs  = bird_pairs[:n]
    drone_pairs = drone_pairs[:n]
    print(f"Balanced → {n} Bird + {n} Drone = {n*2} total")

    all_pairs = bird_pairs + drone_pairs
    random.shuffle(all_pairs)

    total     = len(all_pairs)
    train_end = int(total * SPLITS[0])
    val_end   = train_end + int(total * SPLITS[1])
    assigned  = (
        [("train", t) for t in all_pairs[:train_end]] +
        [("val",   t) for t in all_pairs[train_end:val_end]] +
        [("test",  t) for t in all_pairs[val_end:]]
    )

    # Create output dirs fresh
    if OUTPUT.exists():
        shutil.rmtree(OUTPUT)
    for sp in ("train", "val", "test"):
        (OUTPUT / sp / "images").mkdir(parents=True, exist_ok=True)
        (OUTPUT / sp / "labels").mkdir(parents=True, exist_ok=True)

    seen: dict[str, str] = {}
    written = dupes = skipped = 0
    counts  = {0: 0, 1: 0}

    for sp, (img, lbl, out_cls) in assigned:
        h = sha256(img)
        if h in seen:
            dupes += 1
            continue
        seen[h] = str(img)

        # Determine the raw token in this label file
        # We know: out_cls==0 → token "0", out_cls==1 from fw → "0", from uav → "UAV"
        # Detect by reading first valid line
        raw_token = None
        for line in lbl.read_text().splitlines():
            if is_bbox(line):
                raw_token = line.strip().split()[0]
                break
        if raw_token is None:
            skipped += 1
            continue

        lines = convert_label(lbl, raw_token, out_cls)
        if not lines:
            skipped += 1
            continue

        # Source name for filename prefix
        src = img.parent.parent.name  # e.g. "Birds.v1i.yolov8", "fixed-wing-uav", "anti-uav"
        stem = f"{src}_{img.stem}"
        shutil.copy2(img, OUTPUT / sp / "images" / (stem + img.suffix))
        with open(OUTPUT / sp / "labels" / (stem + ".txt"), "w") as f:
            f.write("\n".join(lines))

        for line in lines:
            c = int(line.split()[0])
            counts[c] = counts.get(c, 0) + 1
        written += 1

    # data.yaml
    with open(OUTPUT / "data.yaml", "w") as f:
        yaml.dump({
            "path":  str(OUTPUT),
            "train": str(OUTPUT / "train" / "images"),
            "val":   str(OUTPUT / "val"   / "images"),
            "test":  str(OUTPUT / "test"  / "images"),
            "nc": 2,
            "names": ["Bird", "Drone"],
        }, f, default_flow_style=False)

    # Training config
    with open(OUTPUT / "train_config_recommended.yaml", "w") as f:
        yaml.dump({
            "model": "yolo26s",
            "data": str(OUTPUT / "data.yaml"),
            "imgsz": 640,
            "batch_rtx2070": 16,
            "batch_colab_t4": 32,
            "epochs": 100,
            "patience": 30,
            "optimizer": "MuSGD",
            "lr0": 0.01,
            "weight_decay": 0.0005,
            "amp": True,
            "mosaic": 1.0,
            "copy_paste": 0.6,
            "mixup": 0.0,
            "hsv_h": 0.02,
            "hsv_s": 0.7,
            "hsv_v": 0.5,
            "degrees": 20.0,
            "translate": 0.15,
            "scale": 0.8,
            "flipud": 0.3,
            "fliplr": 0.5,
        }, f, default_flow_style=False)

    t = len(list((OUTPUT / "train" / "images").iterdir()))
    v = len(list((OUTPUT / "val"   / "images").iterdir()))
    e = len(list((OUTPUT / "test"  / "images").iterdir()))
    print("─" * 50)
    print(f"Written: {written}  dupes: {dupes}  skipped: {skipped}")
    print(f"Annotation counts — Bird(0): {counts.get(0,0)}  Drone(1): {counts.get(1,0)}")
    print(f"Splits — train: {t}  val: {v}  test: {e}")
    print(f"Output → {OUTPUT}")


if __name__ == "__main__":
    main()
