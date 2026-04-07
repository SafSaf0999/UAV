"""Unit tests for anti_uav/inspector.py — inspect_dataset and helpers."""
from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pytest

from anti_uav.inspector import inspect_dataset
from anti_uav.models import AnnotationFormat
from anti_uav.utils import sha256_hash


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_tiny_image(path: Path) -> None:
    """Write a minimal 1×1 white PNG to *path*."""
    # Minimal valid PNG bytes (1×1 white pixel)
    PNG_1x1 = (
        b"\x89PNG\r\n\x1a\n"
        b"\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
        b"\x08\x02\x00\x00\x00\x90wS\xde"
        b"\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00\x05\x18\xd8N"
        b"\x00\x00\x00\x00IEND\xaeB`\x82"
    )
    path.write_bytes(PNG_1x1)


def _make_yolo_dataset(root: Path, class_counts: dict[str, int] | None = None) -> None:
    """Create a minimal YOLO TXT dataset under *root*."""
    if class_counts is None:
        class_counts = {"0": 3, "1": 1}
    images_dir = root / "images"
    labels_dir = root / "labels"
    images_dir.mkdir(parents=True)
    labels_dir.mkdir(parents=True)

    idx = 0
    for cls_idx, count in class_counts.items():
        for _ in range(count):
            stem = f"img_{idx:04d}"
            _make_tiny_image(images_dir / f"{stem}.jpg")
            (labels_dir / f"{stem}.txt").write_text(
                f"{cls_idx} 0.5 0.5 0.1 0.1\n", encoding="utf-8"
            )
            idx += 1


# ---------------------------------------------------------------------------
# test_inspect_dataset_yolo_txt
# ---------------------------------------------------------------------------

def test_inspect_dataset_yolo_txt(tmp_path):
    ds = tmp_path / "my_dataset"
    ds.mkdir()
    _make_yolo_dataset(ds, {"0": 2, "1": 1})

    report = inspect_dataset(ds)

    assert report.annotation_format == AnnotationFormat.YOLO_TXT
    assert report.stats.image_count == 3
    assert sum(report.stats.class_counts.values()) == 3
    assert report.errors == []

    # JSON report written alongside dataset
    report_file = ds / "inspection_report.json"
    assert report_file.exists()
    data = json.loads(report_file.read_text())
    assert data["annotation_format"] == "yolo_txt"
    assert data["stats"]["image_count"] == 3


# ---------------------------------------------------------------------------
# test_inspect_dataset_zip
# ---------------------------------------------------------------------------

def test_inspect_dataset_zip(tmp_path):
    ds = tmp_path / "ds"
    ds.mkdir()
    _make_yolo_dataset(ds, {"0": 2})

    zip_path = tmp_path / "ds.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        for f in ds.rglob("*"):
            zf.write(f, f.relative_to(ds))

    hash_before = sha256_hash(zip_path)
    report = inspect_dataset(zip_path)
    hash_after = sha256_hash(zip_path)

    # Original ZIP must be unchanged
    assert hash_before == hash_after

    # Report written next to the ZIP (in tmp_path)
    report_file = tmp_path / "inspection_report.json"
    assert report_file.exists()

    assert report.annotation_format == AnnotationFormat.YOLO_TXT
    assert report.stats.image_count == 2


# ---------------------------------------------------------------------------
# test_inspect_dataset_empty
# ---------------------------------------------------------------------------

def test_inspect_dataset_empty(tmp_path):
    ds = tmp_path / "empty_ds"
    ds.mkdir()

    report = inspect_dataset(ds)

    assert report.stats.image_count == 0
    assert report.stats.class_counts == {}


# ---------------------------------------------------------------------------
# test_inspect_dataset_malformed_annotation
# ---------------------------------------------------------------------------

def test_inspect_dataset_malformed_annotation(tmp_path):
    ds = tmp_path / "bad_ds"
    images_dir = ds / "images"
    labels_dir = ds / "labels"
    images_dir.mkdir(parents=True)
    labels_dir.mkdir(parents=True)

    # One valid annotation
    _make_tiny_image(images_dir / "good.jpg")
    (labels_dir / "good.txt").write_text("0 0.5 0.5 0.1 0.1\n", encoding="utf-8")

    # One malformed annotation (wrong number of fields — will be skipped per-line,
    # but the file itself is parsed without raising)
    _make_tiny_image(images_dir / "bad.jpg")
    (labels_dir / "bad.txt").write_text("NOT_VALID_YOLO_LINE\n", encoding="utf-8")

    report = inspect_dataset(ds)

    # Scan continues; both images found
    assert report.stats.image_count == 2
    # Good annotation counted
    assert sum(report.stats.class_counts.values()) >= 1


# ---------------------------------------------------------------------------
# test_augmentation_recommendation_imbalance
# ---------------------------------------------------------------------------

def test_augmentation_recommendation_imbalance(tmp_path):
    ds = tmp_path / "imbalanced"
    ds.mkdir()
    # class 0: 10 images, class 1: 1 image → ratio = 10:1 > 5:1
    _make_yolo_dataset(ds, {"0": 10, "1": 1})

    report = inspect_dataset(ds)

    recs = report.stats.augmentation_recommendations
    assert any("imbalance" in r.lower() or "ratio" in r.lower() for r in recs), (
        f"Expected imbalance recommendation, got: {recs}"
    )


# ---------------------------------------------------------------------------
# test_augmentation_recommendation_small_objects
# ---------------------------------------------------------------------------

def test_augmentation_recommendation_small_objects(tmp_path):
    ds = tmp_path / "small_objs"
    images_dir = ds / "images"
    labels_dir = ds / "labels"
    images_dir.mkdir(parents=True)
    labels_dir.mkdir(parents=True)

    # Create many annotations with very small bboxes (< 32/640 ≈ 0.05 normalized)
    for i in range(10):
        stem = f"img_{i:04d}"
        _make_tiny_image(images_dir / f"{stem}.jpg")
        # width=height=0.02 → pixel area = (0.02*640)^2 = 12.8^2 ≈ 164 < 32*32=1024
        (labels_dir / f"{stem}.txt").write_text(
            "0 0.5 0.5 0.02 0.02\n", encoding="utf-8"
        )

    report = inspect_dataset(ds)

    recs = report.stats.augmentation_recommendations
    assert any("small" in r.lower() for r in recs), (
        f"Expected small-object recommendation, got: {recs}"
    )
