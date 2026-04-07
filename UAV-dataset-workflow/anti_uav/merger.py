"""Dataset_Merger — merges multiple curated datasets into merged_dataset/."""
from __future__ import annotations

import random
import shutil
from pathlib import Path

import yaml

from anti_uav.models import CanonicalClass, MergeReport
from anti_uav.utils import atomic_write, get_logger, sha256_hash

logger = get_logger("merger")

_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".tiff"}
_CANONICAL_CLASSES = [c.value for c in CanonicalClass]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def detect_imbalance(class_counts: dict[str, int], threshold: float = 5.0) -> list[str]:
    """Return list of minority class names if max/min ratio exceeds threshold."""
    if len(class_counts) < 2:
        return []
    max_count = max(class_counts.values())
    min_count = min(class_counts.values())
    if min_count == 0:
        return [cls for cls, cnt in class_counts.items() if cnt == 0]
    if max_count / min_count > threshold:
        # Minority = any class whose count is less than max_count / threshold
        cutoff = max_count / threshold
        return [cls for cls, cnt in class_counts.items() if cnt < cutoff]
    return []


def write_data_yaml(
    output_dir: Path,
    classes: list[str],
    splits: dict[str, Path],
) -> None:
    """Write data.yaml to output_dir with class names and split paths."""
    data = {
        "path": str(output_dir),
        "train": str(splits.get("train", output_dir / "train" / "images")),
        "val": str(splits.get("val", output_dir / "val" / "images")),
        "test": str(splits.get("test", output_dir / "test" / "images")),
        "nc": len(classes),
        "names": classes,
    }
    atomic_write(output_dir / "data.yaml", yaml.dump(data, default_flow_style=False))


def merge_datasets(
    source_dirs: list[Path],
    output_dir: Path,
    splits: tuple[float, float, float] = (0.7, 0.2, 0.1),
) -> MergeReport:
    """Merge source datasets into output_dir.

    - Copy images with {source_dataset_name}_{original_stem}{ext} naming
    - Deduplicate by SHA-256, log to merge_duplicates.log
    - Preserve train/val/test structure
    - Write data.yaml
    - Report per-class counts and imbalance warnings
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    # Create output split directories
    for split in ("train", "val", "test"):
        (output_dir / split / "images").mkdir(parents=True, exist_ok=True)
        (output_dir / split / "labels").mkdir(parents=True, exist_ok=True)

    seen_hashes: dict[str, str] = {}  # hash -> dest_path
    duplicates: list[str] = []
    total_images = 0
    class_counts: dict[str, int] = {}

    # Collect all images from all sources
    all_items: list[tuple[Path, Path, str]] = []  # (img_path, label_path, source_name)

    for src_dir in source_dirs:
        source_name = src_dir.name
        found_split = False
        for split in ("train", "val", "test"):
            split_images_dir = src_dir / split / "images"
            split_labels_dir = src_dir / split / "labels"
            if split_images_dir.is_dir():
                found_split = True
                for img_path in sorted(split_images_dir.iterdir()):
                    if img_path.suffix.lower() in _IMAGE_EXTENSIONS:
                        label_path = split_labels_dir / (img_path.stem + ".txt")
                        all_items.append((img_path, label_path, source_name))
        if not found_split:
            # Flat structure — scan all images recursively
            for img_path in sorted(src_dir.rglob("*")):
                if img_path.suffix.lower() in _IMAGE_EXTENSIONS:
                    label_path = img_path.with_suffix(".txt")
                    if not label_path.is_file():
                        labels_dir = img_path.parent.parent / "labels"
                        label_path = labels_dir / (img_path.stem + ".txt")
                    all_items.append((img_path, label_path, source_name))

    # Shuffle and split
    random.shuffle(all_items)
    n = len(all_items)
    train_end = int(n * splits[0])
    val_end = train_end + int(n * splits[1])

    split_assignments: list[str] = (
        ["train"] * train_end
        + ["val"] * (val_end - train_end)
        + ["test"] * (n - val_end)
    )

    duplicates_log_lines: list[str] = []

    for (img_path, label_path, source_name), split_name in zip(all_items, split_assignments):
        if not img_path.is_file():
            continue

        # Deduplication
        img_hash = sha256_hash(img_path)
        if img_hash in seen_hashes:
            msg = f"Duplicate: {img_path} (same as {seen_hashes[img_hash]})"
            duplicates.append(msg)
            duplicates_log_lines.append(msg)
            continue

        seen_hashes[img_hash] = str(img_path)

        # New filename: {source_name}_{original_stem}{ext}
        new_stem = f"{source_name}_{img_path.stem}"
        new_img_name = new_stem + img_path.suffix
        dest_img = output_dir / split_name / "images" / new_img_name
        dest_label = output_dir / split_name / "labels" / (new_stem + ".txt")

        shutil.copy2(img_path, dest_img)
        total_images += 1

        # Copy label file — convert string class names to integer indices
        if label_path.is_file():
            lines = label_path.read_text(encoding="utf-8").splitlines()
            new_lines: list[str] = []
            for line in lines:
                parts = line.strip().split()
                if not parts or len(parts) != 5:
                    continue
                cls_token = parts[0]
                # Convert string canonical name to integer index
                if cls_token in _CANONICAL_CLASSES:
                    cls_idx = str(_CANONICAL_CLASSES.index(cls_token))
                else:
                    cls_idx = cls_token  # already an integer string
                new_lines.append(f"{cls_idx} " + " ".join(parts[1:]))
                class_counts[cls_token] = class_counts.get(cls_token, 0) + 1
            atomic_write(dest_label, "\n".join(new_lines))
        else:
            dest_label.write_text("", encoding="utf-8")

    # Write duplicates log
    if duplicates_log_lines:
        dup_log = output_dir / "merge_duplicates.log"
        atomic_write(dup_log, "\n".join(duplicates_log_lines))

    # Write data.yaml
    split_paths = {
        "train": output_dir / "train" / "images",
        "val": output_dir / "val" / "images",
        "test": output_dir / "test" / "images",
    }
    write_data_yaml(output_dir, _CANONICAL_CLASSES, split_paths)

    # Detect imbalance
    imbalance_warnings: list[str] = []
    minority_classes = detect_imbalance(class_counts)
    if minority_classes:
        imbalance_warnings.append(
            f"Class imbalance detected. Minority classes: {minority_classes}. "
            "Consider oversampling or copy-paste augmentation."
        )

    return MergeReport(
        total_images=total_images,
        deduplicated_count=len(duplicates),  # number of duplicate images skipped
        class_counts=class_counts,
        imbalance_warnings=imbalance_warnings,
        output_path=output_dir,
    )
