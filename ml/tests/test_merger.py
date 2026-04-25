"""Unit tests for Dataset_Merger."""
from __future__ import annotations

import tempfile
from pathlib import Path

import yaml
import pytest

from anti_uav.merger import detect_imbalance, merge_datasets, write_data_yaml
from anti_uav.models import CanonicalClass


_PNG_BYTES = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
    b"\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00"
    b"\x00\x0cIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00\x05\x18"
    b"\xd8N\x00\x00\x00\x00IEND\xaeB`\x82"
)


def make_source(base: Path, name: str, images: list[str]) -> Path:
    src = base / name
    images_dir = src / "train" / "images"
    labels_dir = src / "train" / "labels"
    images_dir.mkdir(parents=True)
    labels_dir.mkdir(parents=True)
    for i, img in enumerate(images):
        # Use unique content per image to avoid SHA-256 deduplication
        unique_bytes = _PNG_BYTES + f"_{name}_{i}".encode()
        (images_dir / img).write_bytes(unique_bytes)
        (labels_dir / Path(img).with_suffix(".txt").name).write_text(
            "0 0.5 0.5 0.1 0.1", encoding="utf-8"
        )
    return src


# ---------------------------------------------------------------------------
# detect_imbalance tests
# ---------------------------------------------------------------------------

def test_detect_imbalance_returns_minority_when_above_threshold():
    counts = {"Bird": 100, "Drone": 10, "UAV": 5}
    result = detect_imbalance(counts, threshold=5.0)
    assert len(result) > 0


def test_detect_imbalance_empty_when_below_threshold():
    counts = {"Bird": 10, "Drone": 8, "UAV": 9}
    result = detect_imbalance(counts, threshold=5.0)
    assert result == []


def test_detect_imbalance_single_class():
    counts = {"Bird": 100}
    result = detect_imbalance(counts)
    assert result == []


def test_detect_imbalance_exact_threshold():
    counts = {"Bird": 50, "Drone": 10}
    # ratio = 5.0, not > 5.0
    result = detect_imbalance(counts, threshold=5.0)
    assert result == []


# ---------------------------------------------------------------------------
# write_data_yaml tests
# ---------------------------------------------------------------------------

def test_write_data_yaml_creates_file():
    with tempfile.TemporaryDirectory() as tmp:
        output = Path(tmp)
        splits = {
            "train": output / "train" / "images",
            "val": output / "val" / "images",
            "test": output / "test" / "images",
        }
        write_data_yaml(output, ["Bird", "Drone", "UAV"], splits)
        assert (output / "data.yaml").is_file()


def test_write_data_yaml_canonical_classes():
    with tempfile.TemporaryDirectory() as tmp:
        output = Path(tmp)
        splits = {
            "train": output / "train" / "images",
            "val": output / "val" / "images",
            "test": output / "test" / "images",
        }
        write_data_yaml(output, ["Bird", "Drone", "UAV"], splits)
        data = yaml.safe_load((output / "data.yaml").read_text())
        assert data["names"] == ["Bird", "Drone", "UAV"]
        assert data["nc"] == 3


# ---------------------------------------------------------------------------
# merge_datasets tests
# ---------------------------------------------------------------------------

def test_merge_creates_output_structure():
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        src = make_source(tmp_path, "src1", ["a.jpg", "b.jpg", "c.jpg"])
        output = tmp_path / "merged"
        merge_datasets([src], output)
        for split in ("train", "val", "test"):
            assert (output / split / "images").is_dir()
            assert (output / split / "labels").is_dir()


def test_merge_renames_with_source_prefix():
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        src = make_source(tmp_path, "mydataset", ["img1.jpg"])
        output = tmp_path / "merged"
        merge_datasets([src], output)
        all_images = list(output.rglob("*.jpg"))
        assert any("mydataset_" in p.name for p in all_images)


def test_merge_deduplicates_identical_images():
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        # Both sources have the same image content (same SHA-256)
        for src_name in ("src1", "src2"):
            src = tmp_path / src_name
            images_dir = src / "train" / "images"
            labels_dir = src / "train" / "labels"
            images_dir.mkdir(parents=True)
            labels_dir.mkdir(parents=True)
            (images_dir / "dup.jpg").write_bytes(_PNG_BYTES)  # same content
            (labels_dir / "dup.txt").write_text("0 0.5 0.5 0.1 0.1", encoding="utf-8")
        output = tmp_path / "merged"
        report = merge_datasets([tmp_path / "src1", tmp_path / "src2"], output)
        assert report.total_images == 1
        assert report.deduplicated_count == 1


def test_merge_writes_data_yaml():
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        src = make_source(tmp_path, "src1", ["a.jpg", "b.jpg", "c.jpg"])
        output = tmp_path / "merged"
        merge_datasets([src], output)
        assert (output / "data.yaml").is_file()


def test_merge_report_total_images():
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        src = make_source(tmp_path, "src1", ["a.jpg", "b.jpg", "c.jpg"])
        output = tmp_path / "merged"
        report = merge_datasets([src], output)
        assert report.total_images == 3


def test_merge_imbalance_warning():
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        src = tmp_path / "src1"
        images_dir = src / "train" / "images"
        labels_dir = src / "train" / "labels"
        images_dir.mkdir(parents=True)
        labels_dir.mkdir(parents=True)
        # Create images with different class labels to trigger imbalance
        for i in range(10):
            # Use unique content per image to avoid SHA-256 deduplication
            (images_dir / f"bird{i}.jpg").write_bytes(f"unique_bird_{i}_".encode() + _PNG_BYTES)
            (labels_dir / f"bird{i}.txt").write_text("0 0.5 0.5 0.1 0.1", encoding="utf-8")
        (images_dir / "drone.jpg").write_bytes(b"different_content_" + _PNG_BYTES)
        (labels_dir / "drone.txt").write_text("1 0.5 0.5 0.1 0.1", encoding="utf-8")

        output = tmp_path / "merged"
        report = merge_datasets([src], output)
        # 10:1 ratio should trigger imbalance warning
        assert len(report.imbalance_warnings) > 0


def test_merge_duplicates_log_created():
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        # Both sources have the same image content
        for src_name in ("src1", "src2"):
            src = tmp_path / src_name
            images_dir = src / "train" / "images"
            labels_dir = src / "train" / "labels"
            images_dir.mkdir(parents=True)
            labels_dir.mkdir(parents=True)
            (images_dir / "dup.jpg").write_bytes(_PNG_BYTES)
            (labels_dir / "dup.txt").write_text("0 0.5 0.5 0.1 0.1", encoding="utf-8")
        output = tmp_path / "merged"
        merge_datasets([tmp_path / "src1", tmp_path / "src2"], output)
        assert (output / "merge_duplicates.log").is_file()
