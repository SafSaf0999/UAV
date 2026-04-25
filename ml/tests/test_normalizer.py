"""Unit tests for Class_Normalizer."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from anti_uav.models import CanonicalClass
from anti_uav.normalizer import (
    UnmappedClassError,
    find_unmapped_classes,
    load_mapping,
    normalize_dataset,
)

_PNG_BYTES = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
    b"\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00"
    b"\x00\x0cIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00\x05\x18"
    b"\xd8N\x00\x00\x00\x00IEND\xaeB`\x82"
)


def make_yolo_dataset(tmp_path: Path, images_boxes: dict) -> Path:
    """Create a minimal YOLO TXT dataset. images_boxes: {filename: [(cls, x, y, w, h), ...]}"""
    images_dir = tmp_path / "images"
    labels_dir = tmp_path / "labels"
    images_dir.mkdir(parents=True)
    labels_dir.mkdir(parents=True)
    for name, boxes in images_boxes.items():
        (images_dir / name).write_bytes(_PNG_BYTES)
        stem = Path(name).stem
        lines = [f"{cls} {x} {y} {w} {h}" for cls, x, y, w, h in boxes]
        (labels_dir / f"{stem}.txt").write_text("\n".join(lines), encoding="utf-8")
    return tmp_path


# ---------------------------------------------------------------------------
# load_mapping tests
# ---------------------------------------------------------------------------

def test_load_mapping_valid(tmp_path):
    mapping_file = tmp_path / "mapping.json"
    mapping_file.write_text(
        json.dumps({"bird": "Bird", "drone": "Drone", "uav": "UAV"}),
        encoding="utf-8",
    )
    mapping = load_mapping(mapping_file)
    assert mapping["bird"] == CanonicalClass.BIRD
    assert mapping["drone"] == CanonicalClass.DRONE
    assert mapping["uav"] == CanonicalClass.UAV


def test_load_mapping_invalid_class(tmp_path):
    mapping_file = tmp_path / "mapping.json"
    mapping_file.write_text(
        json.dumps({"bird": "NotAClass"}),
        encoding="utf-8",
    )
    with pytest.raises(ValueError):
        load_mapping(mapping_file)


# ---------------------------------------------------------------------------
# find_unmapped_classes tests
# ---------------------------------------------------------------------------

def test_find_unmapped_classes_all_mapped(tmp_path):
    make_yolo_dataset(tmp_path, {
        "a.jpg": [("bird", 0.5, 0.5, 0.1, 0.1)],
        "b.jpg": [("drone", 0.5, 0.5, 0.1, 0.1)],
    })
    mapping = {"bird": CanonicalClass.BIRD, "drone": CanonicalClass.DRONE}
    result = find_unmapped_classes(tmp_path, mapping)
    assert result == []


def test_find_unmapped_classes_missing(tmp_path):
    make_yolo_dataset(tmp_path, {
        "a.jpg": [("bird", 0.5, 0.5, 0.1, 0.1)],
        "b.jpg": [("unknown_class", 0.5, 0.5, 0.1, 0.1)],
    })
    mapping = {"bird": CanonicalClass.BIRD}
    result = find_unmapped_classes(tmp_path, mapping)
    assert "unknown_class" in result


# ---------------------------------------------------------------------------
# normalize_dataset tests
# ---------------------------------------------------------------------------

def test_normalize_raises_before_modifying(tmp_path):
    make_yolo_dataset(tmp_path, {
        "a.jpg": [("bird", 0.5, 0.5, 0.1, 0.1)],
        "b.jpg": [("unknown", 0.5, 0.5, 0.1, 0.1)],
    })
    mapping = {"bird": CanonicalClass.BIRD}
    label_a_before = (tmp_path / "labels" / "a.txt").read_text()
    label_b_before = (tmp_path / "labels" / "b.txt").read_text()

    with pytest.raises(UnmappedClassError) as exc_info:
        normalize_dataset(tmp_path, mapping)

    assert "unknown" in exc_info.value.unmapped
    # Files must be unchanged
    assert (tmp_path / "labels" / "a.txt").read_text() == label_a_before
    assert (tmp_path / "labels" / "b.txt").read_text() == label_b_before


def test_normalize_rewrites_labels(tmp_path):
    make_yolo_dataset(tmp_path, {
        "a.jpg": [("bird", 0.5, 0.5, 0.1, 0.1)],
    })
    mapping = {"bird": CanonicalClass.BIRD}
    log = normalize_dataset(tmp_path, mapping)

    label_content = (tmp_path / "labels" / "a.txt").read_text()
    # After normalization, class name should be canonical string "Bird"
    assert label_content.startswith("Bird ")
    assert log.total_files_modified == 1


def test_normalize_renames_images(tmp_path):
    # Image filename contains source class name as substring
    make_yolo_dataset(tmp_path, {
        "bird_001.jpg": [("bird", 0.5, 0.5, 0.1, 0.1)],
    })
    mapping = {"bird": CanonicalClass.BIRD}
    normalize_dataset(tmp_path, mapping)

    images_dir = tmp_path / "images"
    image_files = list(images_dir.iterdir())
    names = [f.name for f in image_files]
    # "bird" in stem should be replaced with "Bird"
    assert any("Bird" in n for n in names), f"Expected renamed image, got: {names}"
    assert not any(n == "bird_001.jpg" for n in names), "Original filename should be gone"


def test_normalize_log_written(tmp_path):
    make_yolo_dataset(tmp_path, {
        "a.jpg": [("bird", 0.5, 0.5, 0.1, 0.1)],
        "b.jpg": [("drone", 0.5, 0.5, 0.1, 0.1)],
    })
    mapping = {"bird": CanonicalClass.BIRD, "drone": CanonicalClass.DRONE}
    log = normalize_dataset(tmp_path, mapping)

    log_file = tmp_path / "normalization_log.json"
    assert log_file.is_file()
    data = json.loads(log_file.read_text())
    assert "substitutions" in data
    assert "total_files_modified" in data
    assert data["total_files_modified"] == log.total_files_modified
    # 2 substitution entries (bird->Bird in a.txt, drone->Drone in b.txt), each file_count=1
    assert data["total_files_modified"] == 2


def test_normalize_backend_fallback(tmp_path):
    """When backend_url is unreachable, normalization still completes successfully."""
    make_yolo_dataset(tmp_path, {
        "a.jpg": [("bird", 0.5, 0.5, 0.1, 0.1)],
    })
    mapping = {"bird": CanonicalClass.BIRD}
    # Should not raise even with unreachable backend
    log = normalize_dataset(tmp_path, mapping, backend_url="http://localhost:19999")
    assert log.total_files_modified == 1
    assert (tmp_path / "normalization_log.json").is_file()


# ---------------------------------------------------------------------------
# UnmappedClassError structure
# ---------------------------------------------------------------------------

def test_unmapped_class_error_has_list():
    err = UnmappedClassError(["mystery", "other"])
    assert err.unmapped == ["mystery", "other"]
    assert "mystery" in str(err)
