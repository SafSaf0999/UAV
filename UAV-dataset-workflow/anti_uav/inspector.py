"""Dataset_Inspector — scans annotation folders and computes dataset statistics."""
from __future__ import annotations

import dataclasses
import json
import logging
import shutil
import tempfile
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

from anti_uav.models import (
    Annotation,
    AnnotationFormat,
    BoundingBox,
    DatasetStats,
    InspectionReport,
)
from anti_uav.utils import atomic_write, get_logger

logger = get_logger("inspector")

_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".tiff"}


# ---------------------------------------------------------------------------
# Format detection
# ---------------------------------------------------------------------------

def detect_annotation_format(folder: Path) -> AnnotationFormat:
    """Detect YOLO TXT, COCO JSON, Pascal VOC XML, or UNKNOWN."""
    # YOLO TXT: labels/ subdirectory or .txt files alongside images
    if (folder / "labels").is_dir():
        return AnnotationFormat.YOLO_TXT
    txt_files = list(folder.rglob("*.txt"))
    if txt_files:
        return AnnotationFormat.YOLO_TXT

    # COCO JSON: _annotations.coco.json or any *.json with "categories" key
    coco_candidate = folder / "_annotations.coco.json"
    if coco_candidate.is_file():
        return AnnotationFormat.COCO_JSON
    for json_file in folder.rglob("*.json"):
        try:
            data = json.loads(json_file.read_text(encoding="utf-8"))
            if "categories" in data:
                return AnnotationFormat.COCO_JSON
        except Exception:
            pass

    # Pascal VOC XML: .xml files with <annotation> root
    for xml_file in folder.rglob("*.xml"):
        try:
            tree = ET.parse(xml_file)
            if tree.getroot().tag == "annotation":
                return AnnotationFormat.PASCAL_VOC
        except Exception:
            pass

    return AnnotationFormat.UNKNOWN


# ---------------------------------------------------------------------------
# YOLO TXT parser
# ---------------------------------------------------------------------------

def parse_yolo_txt(label_dir: Path) -> list[Annotation]:
    """Parse all .txt label files in label_dir, returning Annotation objects."""
    annotations: list[Annotation] = []
    skip_names = {"classes.txt", "obj.names"}

    for txt_file in sorted(label_dir.glob("*.txt")):
        if txt_file.name in skip_names:
            continue

        # Find corresponding image
        image_path: Path | None = None
        for ext in _IMAGE_EXTENSIONS:
            candidate = txt_file.with_suffix(ext)
            if candidate.is_file():
                image_path = candidate
                break
        # Also search sibling images/ directory
        if image_path is None:
            images_dir = label_dir.parent / "images"
            if images_dir.is_dir():
                for ext in _IMAGE_EXTENSIONS:
                    candidate = images_dir / (txt_file.stem + ext)
                    if candidate.is_file():
                        image_path = candidate
                        break
        if image_path is None:
            image_path = txt_file  # fallback: use label path as placeholder

        boxes: list[BoundingBox] = []
        for lineno, line in enumerate(txt_file.read_text(encoding="utf-8").splitlines(), 1):
            line = line.strip()
            if not line:
                continue
            parts = line.split()
            if len(parts) != 5:
                logger.warning("Skipping malformed line %d in %s", lineno, txt_file)
                continue
            try:
                class_idx = int(parts[0])
                x_center, y_center, width, height = (float(p) for p in parts[1:])
            except ValueError:
                logger.warning("Unparseable values on line %d in %s", lineno, txt_file)
                continue
            boxes.append(BoundingBox(
                class_name=str(class_idx),
                x_center=x_center,
                y_center=y_center,
                width=width,
                height=height,
            ))

        annotations.append(Annotation(
            image_path=image_path,
            boxes=boxes,
            source_format=AnnotationFormat.YOLO_TXT,
        ))

    return annotations


# ---------------------------------------------------------------------------
# COCO JSON parser
# ---------------------------------------------------------------------------

def parse_coco_json(json_path: Path) -> list[Annotation]:
    """Parse a COCO-format JSON file, returning Annotation objects."""
    data = json.loads(json_path.read_text(encoding="utf-8"))

    # Build lookup tables
    id_to_image: dict[int, dict] = {img["id"]: img for img in data.get("images", [])}
    id_to_category: dict[int, str] = {
        cat["id"]: cat["name"] for cat in data.get("categories", [])
    }

    # Group annotations by image_id
    image_boxes: dict[int, list[BoundingBox]] = {}
    for ann in data.get("annotations", []):
        img_id = ann["image_id"]
        img_info = id_to_image.get(img_id)
        if img_info is None:
            logger.warning("Annotation references unknown image_id %s", img_id)
            continue
        img_w = img_info.get("width", 0)
        img_h = img_info.get("height", 0)
        if img_w <= 0 or img_h <= 0:
            logger.warning("Image id %s has invalid dimensions, skipping bbox", img_id)
            continue

        x, y, w, h = ann["bbox"]
        x_center = (x + w / 2) / img_w
        y_center = (y + h / 2) / img_h
        norm_w = w / img_w
        norm_h = h / img_h

        class_name = id_to_category.get(ann.get("category_id", -1), str(ann.get("category_id")))
        box = BoundingBox(
            class_name=class_name,
            x_center=x_center,
            y_center=y_center,
            width=norm_w,
            height=norm_h,
        )
        image_boxes.setdefault(img_id, []).append(box)

    annotations: list[Annotation] = []
    for img_id, img_info in id_to_image.items():
        image_path = json_path.parent / img_info.get("file_name", "")
        annotations.append(Annotation(
            image_path=image_path,
            boxes=image_boxes.get(img_id, []),
            source_format=AnnotationFormat.COCO_JSON,
        ))

    return annotations


# ---------------------------------------------------------------------------
# Pascal VOC XML parser
# ---------------------------------------------------------------------------

def parse_voc_xml(xml_dir: Path) -> list[Annotation]:
    """Parse all .xml files in xml_dir, returning Annotation objects."""
    annotations: list[Annotation] = []

    for xml_file in sorted(xml_dir.glob("*.xml")):
        try:
            tree = ET.parse(xml_file)
        except ET.ParseError as exc:
            logger.warning("Failed to parse %s: %s", xml_file, exc)
            continue

        root = tree.getroot()
        if root.tag != "annotation":
            continue

        # Image path
        folder_el = root.find("folder")
        filename_el = root.find("filename")
        filename = filename_el.text if filename_el is not None else xml_file.stem
        folder_name = folder_el.text if folder_el is not None else ""
        if folder_name:
            image_path = xml_dir / folder_name / filename
        else:
            image_path = xml_dir / filename
        if not image_path.is_file():
            # Try same directory as XML
            image_path = xml_dir / filename

        # Image dimensions
        size_el = root.find("size")
        img_w = img_h = 0
        if size_el is not None:
            try:
                img_w = int(size_el.findtext("width", "0"))
                img_h = int(size_el.findtext("height", "0"))
            except ValueError:
                pass

        boxes: list[BoundingBox] = []
        for obj in root.findall("object"):
            name_el = obj.find("name")
            bndbox_el = obj.find("bndbox")
            if name_el is None or bndbox_el is None:
                continue
            try:
                xmin = float(bndbox_el.findtext("xmin", "0"))
                ymin = float(bndbox_el.findtext("ymin", "0"))
                xmax = float(bndbox_el.findtext("xmax", "0"))
                ymax = float(bndbox_el.findtext("ymax", "0"))
            except ValueError:
                logger.warning("Unparseable bndbox in %s", xml_file)
                continue

            if img_w > 0 and img_h > 0:
                x_center = ((xmin + xmax) / 2) / img_w
                y_center = ((ymin + ymax) / 2) / img_h
                width = (xmax - xmin) / img_w
                height = (ymax - ymin) / img_h
            else:
                # Cannot normalize without dimensions; store absolute as-is
                x_center = (xmin + xmax) / 2
                y_center = (ymin + ymax) / 2
                width = xmax - xmin
                height = ymax - ymin

            boxes.append(BoundingBox(
                class_name=name_el.text or "",
                x_center=x_center,
                y_center=y_center,
                width=width,
                height=height,
            ))

        annotations.append(Annotation(
            image_path=image_path,
            boxes=boxes,
            source_format=AnnotationFormat.PASCAL_VOC,
        ))

    return annotations


# ---------------------------------------------------------------------------
# Statistics computation
# ---------------------------------------------------------------------------

_ASSUMED_SIZE = 640  # pixels, used for bbox area estimation with normalized coords


def compute_statistics(annotations: list[Annotation], images: list[Path]) -> DatasetStats:
    """Compute dataset statistics from annotations and image paths."""
    class_counts: dict[str, int] = {}
    bbox_size_distribution: dict[str, int] = {"small": 0, "medium": 0, "large": 0}
    resolution_distribution: dict[str, int] = {}
    aspect_ratio_distribution: dict[str, int] = {"portrait": 0, "square": 0, "landscape": 0}

    # Try to import PIL for real image dimensions
    try:
        from PIL import Image as PILImage
        pil_available = True
    except ImportError:
        pil_available = False
        logger.warning("Pillow not available; resolution distribution will not include dimensions")

    for img_path in images:
        if pil_available:
            try:
                with PILImage.open(img_path) as im:
                    w, h = im.size
                key = f"{w}x{h}"
                resolution_distribution[key] = resolution_distribution.get(key, 0) + 1
                ratio = w / h if h > 0 else 1.0
                if ratio < 0.9:
                    aspect_ratio_distribution["portrait"] += 1
                elif ratio <= 1.1:
                    aspect_ratio_distribution["square"] += 1
                else:
                    aspect_ratio_distribution["landscape"] += 1
            except Exception as exc:
                logger.warning("Could not read image %s: %s", img_path, exc)
                resolution_distribution["unknown"] = resolution_distribution.get("unknown", 0) + 1
        else:
            resolution_distribution["unknown"] = resolution_distribution.get("unknown", 0) + 1

    for ann in annotations:
        for box in ann.boxes:
            class_counts[box.class_name] = class_counts.get(box.class_name, 0) + 1
            # Estimate pixel area using assumed 640x640
            pixel_w = box.width * _ASSUMED_SIZE
            pixel_h = box.height * _ASSUMED_SIZE
            area = pixel_w * pixel_h
            if area < 32 * 32:
                bbox_size_distribution["small"] += 1
            elif area < 96 * 96:
                bbox_size_distribution["medium"] += 1
            else:
                bbox_size_distribution["large"] += 1

    if len(class_counts) > 1:
        class_balance_ratio = max(class_counts.values()) / min(class_counts.values())
    else:
        class_balance_ratio = 1.0

    # Augmentation recommendations
    augmentation_recommendations: list[str] = []
    if class_balance_ratio > 5.0:
        augmentation_recommendations.append(
            f"Class imbalance detected (ratio {class_balance_ratio:.1f}:1). "
            "Consider oversampling minority classes or using copy-paste augmentation."
        )
    small_count = bbox_size_distribution["small"]
    if small_count > 0:
        # Estimate median bbox area: if most bboxes are small, median is likely small
        total_boxes = sum(bbox_size_distribution.values())
        # Median is in the "small" bucket when small_count > total_boxes / 2
        if small_count > total_boxes / 2:
            augmentation_recommendations.append(
                "Many small objects detected. Enable copy_paste augmentation and "
                "consider increasing imgsz to 1280."
            )

    return DatasetStats(
        image_count=len(images),
        class_counts=class_counts,
        resolution_distribution=resolution_distribution,
        aspect_ratio_distribution=aspect_ratio_distribution,
        bbox_size_distribution=bbox_size_distribution,
        class_balance_ratio=class_balance_ratio,
        augmentation_recommendations=augmentation_recommendations,
    )


# ---------------------------------------------------------------------------
# Main inspection entry point
# ---------------------------------------------------------------------------

def _report_to_dict(report: InspectionReport) -> dict:
    """Serialize InspectionReport to a JSON-compatible dict."""
    return {
        "dataset_path": report.dataset_path,
        "annotation_format": report.annotation_format.value,
        "stats": {
            "image_count": report.stats.image_count,
            "class_counts": report.stats.class_counts,
            "resolution_distribution": report.stats.resolution_distribution,
            "aspect_ratio_distribution": report.stats.aspect_ratio_distribution,
            "bbox_size_distribution": report.stats.bbox_size_distribution,
            "class_balance_ratio": report.stats.class_balance_ratio,
            "augmentation_recommendations": report.stats.augmentation_recommendations,
        },
        "errors": report.errors,
    }


def inspect_dataset(path: str | Path) -> InspectionReport:
    """Scan a folder or ZIP archive and return a structured InspectionReport.

    - ZIP archives are extracted to a temp dir; the original ZIP is never modified.
    - Per-file parse errors are logged to ``inspection_errors.log`` alongside the
      dataset folder and do not abort the scan.
    - The JSON report is written atomically to
      ``{original_dataset_folder}/inspection_report.json``.
    """
    path = Path(path)
    errors: list[str] = []

    # Determine the "original" folder for output files and the working folder
    if zipfile.is_zipfile(path):
        original_folder = path.parent
        tmp_dir = Path(tempfile.mkdtemp())
        try:
            with zipfile.ZipFile(path, "r") as zf:
                zf.extractall(tmp_dir)
        except Exception as exc:
            raise RuntimeError(f"Failed to extract ZIP {path}: {exc}") from exc
        working_folder = tmp_dir
    else:
        original_folder = path
        working_folder = path

    # Detect annotation format
    fmt = detect_annotation_format(working_folder)

    # Find all image files recursively
    images: list[Path] = []
    for ext in _IMAGE_EXTENSIONS:
        images.extend(working_folder.rglob(f"*{ext}"))
        images.extend(working_folder.rglob(f"*{ext.upper()}"))
    images = sorted(set(images))

    # Parse annotations
    annotations: list[Annotation] = []
    if fmt == AnnotationFormat.YOLO_TXT:
        labels_dir = working_folder / "labels"
        if labels_dir.is_dir():
            parse_dirs = [labels_dir]
        else:
            # Collect all directories that contain .txt files
            txt_dirs = {f.parent for f in working_folder.rglob("*.txt")
                        if f.name not in {"classes.txt", "obj.names"}}
            parse_dirs = sorted(txt_dirs)
        for d in parse_dirs:
            try:
                annotations.extend(parse_yolo_txt(d))
            except Exception as exc:
                msg = f"Error parsing YOLO TXT in {d}: {exc}"
                logger.error(msg)
                errors.append(msg)

    elif fmt == AnnotationFormat.COCO_JSON:
        coco_candidate = working_folder / "_annotations.coco.json"
        if coco_candidate.is_file():
            json_files = [coco_candidate]
        else:
            json_files = list(working_folder.rglob("*.json"))
        for jf in json_files:
            try:
                annotations.extend(parse_coco_json(jf))
            except Exception as exc:
                msg = f"Error parsing COCO JSON {jf}: {exc}"
                logger.error(msg)
                errors.append(msg)

    elif fmt == AnnotationFormat.PASCAL_VOC:
        xml_dirs = {f.parent for f in working_folder.rglob("*.xml")}
        for d in sorted(xml_dirs):
            try:
                annotations.extend(parse_voc_xml(d))
            except Exception as exc:
                msg = f"Error parsing VOC XML in {d}: {exc}"
                logger.error(msg)
                errors.append(msg)

    # Compute statistics (augmentation recommendations included)
    stats = compute_statistics(annotations, images)

    report = InspectionReport(
        dataset_path=str(path),
        annotation_format=fmt,
        stats=stats,
        errors=errors,
    )

    # Write JSON report atomically to original folder
    report_path = original_folder / "inspection_report.json"
    atomic_write(report_path, json.dumps(_report_to_dict(report), indent=2))

    # Write per-file errors to log (append mode)
    if errors:
        errors_log = original_folder / "inspection_errors.log"
        errors_log.parent.mkdir(parents=True, exist_ok=True)
        with errors_log.open("a", encoding="utf-8") as fh:
            for err in errors:
                fh.write(err + "\n")

    return report
