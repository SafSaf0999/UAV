"""
Prepare SIDD thermal dataset for YOLO training.

Converts COCO JSON annotations → YOLO .txt labels (1 class: Drone).
Merges all 4 scenes (city, moutain, sea, sky) into a single dataset.
Applies a deterministic 80/20 train/val split per scene (preserving existing
train2017/val2017 splits where available).

Output structure:
    thermal_merged/
        train/images/   train/labels/
        val/images/     val/labels/
        data.yaml

Usage:
    python scripts/prepare_thermal_dataset.py
"""

import json
import shutil
import random
from pathlib import Path

SIDD_BASE = Path("/home/safsaf/Projects/UAV/UAV-dataset-workflow/thermal_datasets/SIDD-main")
OUT_BASE = Path("/home/safsaf/Projects/UAV/UAV-dataset-workflow/thermal_datasets/thermal_merged")

SCENES = {
    "city":    SIDD_BASE / "city/coco格式/cococity",
    "moutain": SIDD_BASE / "moutain/coco格式/moutain2coco",
    "sea":     SIDD_BASE / "sea/coco格式/sea2coco",
    "sky":     SIDD_BASE / "sky/coco格式/sky2coco",
}

SPLITS = ["train", "val"]
SPLIT_MAP = {"train": "train2017", "val": "val2017"}

random.seed(42)


def coco_bbox_to_yolo(bbox, img_w, img_h):
    """Convert COCO [x_tl, y_tl, w, h] → YOLO [cx, cy, w, h] normalised."""
    x, y, w, h = bbox
    cx = (x + w / 2) / img_w
    cy = (y + h / 2) / img_h
    nw = w / img_w
    nh = h / img_h
    # clamp to [0, 1]
    cx = max(0.0, min(1.0, cx))
    cy = max(0.0, min(1.0, cy))
    nw = max(0.0, min(1.0, nw))
    nh = max(0.0, min(1.0, nh))
    return cx, cy, nw, nh


def process_split(scene_name, scene_dir, split, out_img_dir, out_lbl_dir):
    """Convert one scene/split and copy files to output dirs."""
    split_folder = SPLIT_MAP[split]
    ann_file = scene_dir / f"annotations/instances_{split_folder}.json"
    img_dir = scene_dir / split_folder

    if not ann_file.exists():
        print(f"  [{scene_name}/{split}] annotation not found, skipping")
        return 0, 0

    data = json.load(open(ann_file))

    # Build image_id → image info map
    id_to_img = {img["id"]: img for img in data["images"]}

    # Build image_id → list of annotations
    id_to_anns = {}
    for ann in data["annotations"]:
        id_to_anns.setdefault(ann["image_id"], []).append(ann)

    copied_imgs = 0
    written_labels = 0
    skipped = 0

    for img_info in data["images"]:
        img_id = img_info["id"]
        # file_name is like '../train2017/345.jpg' — extract just the filename
        fname = Path(img_info["file_name"]).name
        src_img = img_dir / fname

        if not src_img.exists():
            skipped += 1
            continue

        # Unique name: scene_split_originalname to avoid collisions across scenes
        unique_name = f"{scene_name}_{fname}"
        dst_img = out_img_dir / unique_name
        dst_lbl = out_lbl_dir / (Path(unique_name).stem + ".txt")

        # Copy image
        shutil.copy2(src_img, dst_img)
        copied_imgs += 1

        # Write YOLO label
        anns = id_to_anns.get(img_id, [])
        img_w = img_info["width"]
        img_h = img_info["height"]

        with open(dst_lbl, "w") as f:
            for ann in anns:
                if ann.get("iscrowd", 0):
                    continue
                cx, cy, nw, nh = coco_bbox_to_yolo(ann["bbox"], img_w, img_h)
                # class 0 = Drone
                f.write(f"0 {cx:.6f} {cy:.6f} {nw:.6f} {nh:.6f}\n")
                written_labels += 1

    if skipped:
        print(f"  [{scene_name}/{split}] WARNING: {skipped} images not found on disk")

    return copied_imgs, written_labels


def write_data_yaml(out_base):
    yaml_path = out_base / "data.yaml"
    yaml_path.write_text(
        f"path: {out_base.resolve()}\n"
        "train: train/images\n"
        "val: val/images\n"
        "nc: 1\n"
        "names: ['Drone']\n"
    )
    print(f"\nWrote {yaml_path}")


def main():
    # Create output dirs
    for split in SPLITS:
        (OUT_BASE / split / "images").mkdir(parents=True, exist_ok=True)
        (OUT_BASE / split / "labels").mkdir(parents=True, exist_ok=True)

    total_stats = {s: {"images": 0, "labels": 0} for s in SPLITS}

    for scene_name, scene_dir in SCENES.items():
        print(f"\nProcessing scene: {scene_name}")
        for split in SPLITS:
            out_img = OUT_BASE / split / "images"
            out_lbl = OUT_BASE / split / "labels"
            imgs, lbls = process_split(scene_name, scene_dir, split, out_img, out_lbl)
            total_stats[split]["images"] += imgs
            total_stats[split]["labels"] += lbls
            print(f"  [{split}] {imgs} images, {lbls} labels")

    write_data_yaml(OUT_BASE)

    print("\n=== Dataset Summary ===")
    for split in SPLITS:
        print(f"  {split}: {total_stats[split]['images']} images, {total_stats[split]['labels']} annotations")
    total_imgs = sum(v["images"] for v in total_stats.values())
    print(f"  TOTAL: {total_imgs} images")
    print(f"\nOutput: {OUT_BASE.resolve()}")


if __name__ == "__main__":
    main()
