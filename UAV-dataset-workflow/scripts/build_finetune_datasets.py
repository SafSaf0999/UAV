"""
Step 2: Merge pseudo-label data with original training data.

Creates:
  datasets/finetune_2class/   ← merged_dataset_2class + dut_pseudolabels_2class
  datasets/finetune_3class/   ← merged_dataset (3class) + dut_pseudolabels_3class

Splits: 80% train, 15% val, 5% test (pseudo-label portion only)
Original splits are preserved as-is.
"""
from __future__ import annotations
import random
import shutil
from pathlib import Path
import yaml

ROOT = Path("/home/safsaf/Projects/UAV-dataset-workflow")
SEED = 42

CONFIGS = [
    {
        "name":       "finetune_2class",
        "orig":       ROOT / "merged_dataset_2class",
        "pseudo":     ROOT / "datasets" / "dut_pseudolabels_2class",
        "out":        ROOT / "datasets" / "finetune_2class",
        "nc":         2,
        "names":      ["Bird", "Drone"],
    },
    {
        "name":       "finetune_3class",
        "orig":       ROOT / "merged_dataset",
        "pseudo":     ROOT / "datasets" / "dut_pseudolabels_3class",
        "out":        ROOT / "datasets" / "finetune_3class",
        "nc":         3,
        "names":      ["Bird", "Drone", "UAV"],
    },
]

EXTS = {".jpg", ".jpeg", ".png", ".bmp"}


def main():
    random.seed(SEED)

    for cfg in CONFIGS:
        out = cfg["out"]
        if out.exists():
            shutil.rmtree(out)
        for sp in ("train", "val", "test"):
            (out / sp / "images").mkdir(parents=True)
            (out / sp / "labels").mkdir(parents=True)

        print(f"\n{'='*55}\nBuilding {cfg['name']}")

        # ── Copy original splits as-is ────────────────────────────────────
        orig_counts = {}
        for sp in ("train", "val", "test"):
            img_dir = cfg["orig"] / sp / "images"
            lbl_dir = cfg["orig"] / sp / "labels"
            if not img_dir.is_dir():
                continue
            n = 0
            for img in img_dir.iterdir():
                if img.suffix.lower() not in EXTS:
                    continue
                lbl = lbl_dir / (img.stem + ".txt")
                if not lbl.is_file():
                    continue
                shutil.copy2(img, out / sp / "images" / img.name)
                shutil.copy2(lbl, out / sp / "labels" / lbl.name)
                n += 1
            orig_counts[sp] = n
            print(f"  orig {sp}: {n:,}")

        # ── Split pseudo-labels 80/15/5 ───────────────────────────────────
        pseudo_imgs = sorted(
            p for p in (cfg["pseudo"] / "images").iterdir()
            if p.suffix.lower() in EXTS
        )
        random.shuffle(pseudo_imgs)
        n = len(pseudo_imgs)
        t_end = int(n * 0.80)
        v_end = t_end + int(n * 0.15)
        splits = (
            [("train", p) for p in pseudo_imgs[:t_end]] +
            [("val",   p) for p in pseudo_imgs[t_end:v_end]] +
            [("test",  p) for p in pseudo_imgs[v_end:]]
        )

        pseudo_counts = {"train": 0, "val": 0, "test": 0}
        for sp, img in splits:
            lbl = cfg["pseudo"] / "labels" / (img.stem + ".txt")
            if not lbl.is_file():
                continue
            # Prefix with "dut_" to avoid filename collisions
            new_stem = "dut_" + img.stem
            shutil.copy2(img, out / sp / "images" / (new_stem + img.suffix))
            shutil.copy2(lbl, out / sp / "labels" / (new_stem + ".txt"))
            pseudo_counts[sp] += 1

        for sp, n in pseudo_counts.items():
            print(f"  pseudo {sp}: {n:,}")

        # ── Totals ────────────────────────────────────────────────────────
        for sp in ("train", "val", "test"):
            total = len(list((out / sp / "images").iterdir()))
            print(f"  TOTAL {sp}: {total:,}")

        # ── data.yaml ─────────────────────────────────────────────────────
        with open(out / "data.yaml", "w") as f:
            yaml.dump({
                "path":  str(out),
                "train": str(out / "train" / "images"),
                "val":   str(out / "val"   / "images"),
                "test":  str(out / "test"  / "images"),
                "nc":    cfg["nc"],
                "names": cfg["names"],
            }, f, default_flow_style=False)

        print(f"  data.yaml → {out / 'data.yaml'}")


if __name__ == "__main__":
    main()
