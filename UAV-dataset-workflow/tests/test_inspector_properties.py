"""Property-based tests for anti_uav/inspector.py.

# Feature: anti-uav-dataset-workflow, Property 1: Dataset inspection round-trip correctness
# Feature: anti-uav-dataset-workflow, Property 2: ZIP extraction preserves original archive
# Feature: anti-uav-dataset-workflow, Property 3: Annotation format detection is correct
"""
from __future__ import annotations

import json
import shutil
import tempfile
import zipfile
from pathlib import Path

from hypothesis import given, settings
from hypothesis import strategies as st

from anti_uav.inspector import detect_annotation_format, inspect_dataset
from anti_uav.models import AnnotationFormat
from anti_uav.utils import sha256_hash


# ---------------------------------------------------------------------------
# Minimal PNG bytes (1×1 white pixel) — used as a stand-in image
# ---------------------------------------------------------------------------
_PNG_1x1 = (
    b"\x89PNG\r\n\x1a\n"
    b"\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x02\x00\x00\x00\x90wS\xde"
    b"\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00\x05\x18\xd8N"
    b"\x00\x00\x00\x00IEND\xaeB`\x82"
)

_bbox_coord_st = st.floats(min_value=0.01, max_value=0.99, allow_nan=False, allow_infinity=False)


def _build_yolo_dataset(root: Path, n_classes: int, n_images: int, boxes_per_image: list[list[tuple]]) -> int:
    """Build a YOLO TXT dataset; return total annotation count."""
    images_dir = root / "images"
    labels_dir = root / "labels"
    images_dir.mkdir(parents=True, exist_ok=True)
    labels_dir.mkdir(parents=True, exist_ok=True)

    total = 0
    for i, boxes in enumerate(boxes_per_image):
        stem = f"img_{i:04d}"
        (images_dir / f"{stem}.png").write_bytes(_PNG_1x1)
        lines = [f"{cls_idx} {x} {y} {w} {h}" for cls_idx, x, y, w, h in boxes]
        (labels_dir / f"{stem}.txt").write_text("\n".join(lines), encoding="utf-8")
        total += len(boxes)
    return total


# ---------------------------------------------------------------------------
# Property 1: Dataset inspection round-trip correctness
# **Validates: Requirements 1.1, 1.4**
# ---------------------------------------------------------------------------

@settings(max_examples=50)
@given(
    n_classes=st.integers(min_value=1, max_value=3),
    n_images=st.integers(min_value=1, max_value=5),
    data=st.data(),
)
def test_property1_inspection_round_trip_correctness(n_classes, n_images, data):
    """For any synthetic YOLO dataset, inspect_dataset writes a JSON report whose
    stats.class_counts values sum to the actual total annotation count.

    # Feature: anti-uav-dataset-workflow, Property 1: Dataset inspection round-trip correctness
    **Validates: Requirements 1.1, 1.4**
    """
    tmp_dir = Path(tempfile.mkdtemp())
    try:
        ds_dir = tmp_dir / "dataset"
        ds_dir.mkdir()

        # Generate boxes for each image
        boxes_per_image = []
        for _ in range(n_images):
            n_boxes = data.draw(st.integers(min_value=0, max_value=3))
            boxes = []
            for _ in range(n_boxes):
                cls_idx = data.draw(st.integers(min_value=0, max_value=n_classes - 1))
                x = data.draw(_bbox_coord_st)
                y = data.draw(_bbox_coord_st)
                w = data.draw(_bbox_coord_st)
                h = data.draw(_bbox_coord_st)
                boxes.append((cls_idx, x, y, w, h))
            boxes_per_image.append(boxes)

        expected_total = _build_yolo_dataset(ds_dir, n_classes, n_images, boxes_per_image)

        report = inspect_dataset(ds_dir)

        # In-memory report: class_counts sum == total annotations
        assert sum(report.stats.class_counts.values()) == expected_total

        # JSON report written and consistent
        report_file = ds_dir / "inspection_report.json"
        assert report_file.exists(), "inspection_report.json must be written"
        loaded = json.loads(report_file.read_text())
        assert sum(loaded["stats"]["class_counts"].values()) == expected_total
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


# ---------------------------------------------------------------------------
# Property 2: ZIP extraction preserves original archive
# **Validates: Requirements 1.2**
# ---------------------------------------------------------------------------

@settings(max_examples=50)
@given(
    n_images=st.integers(min_value=1, max_value=4),
    data=st.data(),
)
def test_property2_zip_extraction_preserves_original(n_images, data):
    """For any ZIP archive, the SHA-256 hash before and after inspect_dataset must match.

    # Feature: anti-uav-dataset-workflow, Property 2: ZIP extraction preserves original archive
    **Validates: Requirements 1.2**
    """
    tmp_dir = Path(tempfile.mkdtemp())
    try:
        ds_dir = tmp_dir / "dataset"
        ds_dir.mkdir()

        boxes_per_image = []
        for _ in range(n_images):
            n_boxes = data.draw(st.integers(min_value=0, max_value=2))
            boxes = [(0, 0.5, 0.5, 0.1, 0.1)] * n_boxes
            boxes_per_image.append(boxes)
        _build_yolo_dataset(ds_dir, 1, n_images, boxes_per_image)

        zip_path = tmp_dir / "archive.zip"
        with zipfile.ZipFile(zip_path, "w") as zf:
            for f in ds_dir.rglob("*"):
                if f.is_file():
                    zf.write(f, f.relative_to(ds_dir))

        hash_before = sha256_hash(zip_path)
        inspect_dataset(zip_path)
        hash_after = sha256_hash(zip_path)

        assert hash_before == hash_after, (
            "inspect_dataset must not modify the original ZIP archive"
        )
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


# ---------------------------------------------------------------------------
# Property 3: Annotation format detection is correct
# **Validates: Requirements 1.5**
# ---------------------------------------------------------------------------

def _make_yolo_dataset(root: Path) -> Path:
    ds = root / "yolo_ds"
    (ds / "images").mkdir(parents=True, exist_ok=True)
    (ds / "labels").mkdir(parents=True, exist_ok=True)
    (ds / "images" / "img.png").write_bytes(_PNG_1x1)
    (ds / "labels" / "img.txt").write_text("0 0.5 0.5 0.1 0.1\n", encoding="utf-8")
    return ds


def _make_coco_dataset(root: Path) -> Path:
    ds = root / "coco_ds"
    ds.mkdir(parents=True, exist_ok=True)
    (ds / "img.png").write_bytes(_PNG_1x1)
    coco = {
        "images": [{"id": 1, "file_name": "img.png", "width": 640, "height": 480}],
        "categories": [{"id": 1, "name": "drone"}],
        "annotations": [
            {"id": 1, "image_id": 1, "category_id": 1, "bbox": [10, 10, 50, 50]}
        ],
    }
    (ds / "_annotations.coco.json").write_text(json.dumps(coco), encoding="utf-8")
    return ds


def _make_voc_dataset(root: Path) -> Path:
    ds = root / "voc_ds"
    ds.mkdir(parents=True, exist_ok=True)
    (ds / "img.png").write_bytes(_PNG_1x1)
    xml_content = (
        "<annotation>"
        "<folder>voc_ds</folder>"
        "<filename>img.png</filename>"
        "<size><width>640</width><height>480</height><depth>3</depth></size>"
        "<object>"
        "<name>drone</name>"
        "<bndbox><xmin>10</xmin><ymin>10</ymin><xmax>60</xmax><ymax>60</ymax></bndbox>"
        "</object>"
        "</annotation>"
    )
    (ds / "img.xml").write_text(xml_content, encoding="utf-8")
    return ds


@settings(max_examples=50)
@given(fmt_name=st.sampled_from(["yolo", "coco", "voc"]))
def test_property3_annotation_format_detection_correct(fmt_name):
    """For each of the 3 supported formats, detect_annotation_format returns the correct enum.

    # Feature: anti-uav-dataset-workflow, Property 3: Annotation format detection is correct
    **Validates: Requirements 1.5**
    """
    tmp_dir = Path(tempfile.mkdtemp())
    try:
        if fmt_name == "yolo":
            ds = _make_yolo_dataset(tmp_dir)
            expected = AnnotationFormat.YOLO_TXT
        elif fmt_name == "coco":
            ds = _make_coco_dataset(tmp_dir)
            expected = AnnotationFormat.COCO_JSON
        else:
            ds = _make_voc_dataset(tmp_dir)
            expected = AnnotationFormat.PASCAL_VOC

        result = detect_annotation_format(ds)
        assert result == expected, f"Expected {expected} for {fmt_name} dataset, got {result}"
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)
