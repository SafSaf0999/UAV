"""Property tests for Dataset_Merger — Properties 13-17.

# Feature: anti-uav-dataset-workflow, Property 13: Merge preserves train/val/test split structure
# Feature: anti-uav-dataset-workflow, Property 14: Merged filenames are unique
# Feature: anti-uav-dataset-workflow, Property 15: SHA-256 deduplication keeps exactly one copy
# Feature: anti-uav-dataset-workflow, Property 16: data.yaml contains canonical classes and valid split paths
# Feature: anti-uav-dataset-workflow, Property 17: Class imbalance warning fires at correct threshold
"""
from __future__ import annotations

import tempfile
from pathlib import Path

import yaml
from hypothesis import given, settings
from hypothesis import strategies as st

from anti_uav.merger import detect_imbalance, merge_datasets
from anti_uav.models import CanonicalClass


_PNG_BYTES = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
    b"\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00"
    b"\x00\x0cIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00\x05\x18"
    b"\xd8N\x00\x00\x00\x00IEND\xaeB`\x82"
)

_CANONICAL_CLASSES = [c.value for c in CanonicalClass]


def make_source_dataset(base: Path, name: str, image_count: int) -> Path:
    """Create a simple flat source dataset with unique image content."""
    src = base / name
    images_dir = src / "train" / "images"
    labels_dir = src / "train" / "labels"
    images_dir.mkdir(parents=True)
    labels_dir.mkdir(parents=True)
    for i in range(image_count):
        # Unique content per image
        (images_dir / f"img{i}.jpg").write_bytes(_PNG_BYTES + f"_{name}_{i}".encode())
        (labels_dir / f"img{i}.txt").write_text(f"0 0.5 0.5 0.1 0.1", encoding="utf-8")
    return src


# ---------------------------------------------------------------------------
# Property 13: Merge preserves train/val/test split structure
# Validates: Requirements 5.1
# ---------------------------------------------------------------------------

@settings(max_examples=50)
@given(
    image_count=st.integers(min_value=3, max_value=10),
)
def test_property13_merge_preserves_split_structure(image_count):
    """Property 13: After merge_datasets, output contains train/, val/, test/ subdirs."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        src = make_source_dataset(tmp_path, "src1", image_count)
        output = tmp_path / "merged"

        merge_datasets([src], output)

        for split in ("train", "val", "test"):
            assert (output / split / "images").is_dir(), f"Missing {split}/images"
            assert (output / split / "labels").is_dir(), f"Missing {split}/labels"


# ---------------------------------------------------------------------------
# Property 14: Merged filenames are unique
# Validates: Requirements 5.2
# ---------------------------------------------------------------------------

@settings(max_examples=50)
@given(
    source_count=st.integers(min_value=1, max_value=3),
    images_per_source=st.integers(min_value=1, max_value=5),
)
def test_property14_merged_filenames_are_unique(source_count, images_per_source):
    """Property 14: All image filenames in the output directory are globally unique."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        sources = [
            make_source_dataset(tmp_path, f"src{i}", images_per_source)
            for i in range(source_count)
        ]
        output = tmp_path / "merged"

        merge_datasets(sources, output)

        all_images: list[str] = []
        for split in ("train", "val", "test"):
            all_images.extend(
                p.name for p in (output / split / "images").iterdir()
                if p.suffix.lower() in {".jpg", ".jpeg", ".png", ".bmp", ".tiff"}
            )

        assert len(all_images) == len(set(all_images)), (
            f"Duplicate filenames found: {[x for x in all_images if all_images.count(x) > 1]}"
        )


# ---------------------------------------------------------------------------
# Property 15: SHA-256 deduplication keeps exactly one copy
# Validates: Requirements 5.3
# ---------------------------------------------------------------------------

@settings(max_examples=50)
@given(
    duplicate_count=st.integers(min_value=1, max_value=3),
)
def test_property15_sha256_deduplication(duplicate_count):
    """Property 15: Identical images (same SHA-256) appear exactly once in output."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)

        # Create two sources with the same image content (same SHA-256)
        for i in range(2):
            src = tmp_path / f"src{i}"
            images_dir = src / "train" / "images"
            labels_dir = src / "train" / "labels"
            images_dir.mkdir(parents=True)
            labels_dir.mkdir(parents=True)
            for j in range(duplicate_count):
                # Same content across both sources = same SHA-256
                (images_dir / f"dup{j}.jpg").write_bytes(f"unique_content_{j}".encode())
                (labels_dir / f"dup{j}.txt").write_text("0 0.5 0.5 0.1 0.1", encoding="utf-8")

        sources = [tmp_path / "src0", tmp_path / "src1"]
        output = tmp_path / "merged"
        report = merge_datasets(sources, output)

        # Total images should be duplicate_count (not 2 * duplicate_count)
        assert report.total_images == duplicate_count, (
            f"Expected {duplicate_count} unique images, got {report.total_images}"
        )
        assert report.deduplicated_count == duplicate_count


# ---------------------------------------------------------------------------
# Property 16: data.yaml contains canonical classes and valid split paths
# Validates: Requirements 5.4
# ---------------------------------------------------------------------------

@settings(max_examples=50)
@given(
    image_count=st.integers(min_value=3, max_value=8),
)
def test_property16_data_yaml_canonical_classes(image_count):
    """Property 16: data.yaml lists exactly ['Bird', 'Drone', 'UAV'] and valid split paths."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        src = make_source_dataset(tmp_path, "src1", image_count)
        output = tmp_path / "merged"

        merge_datasets([src], output)

        data_yaml = output / "data.yaml"
        assert data_yaml.is_file(), "data.yaml not found"

        data = yaml.safe_load(data_yaml.read_text(encoding="utf-8"))
        assert data["names"] == ["Bird", "Drone", "UAV"], (
            f"Expected canonical classes, got {data['names']}"
        )
        # Split paths should exist
        for split_key in ("train", "val", "test"):
            split_path = Path(data[split_key])
            assert split_path.is_dir(), f"Split path {split_path} does not exist"


# ---------------------------------------------------------------------------
# Property 17: Class imbalance warning fires at correct threshold
# Validates: Requirements 5.6, 11.2
# ---------------------------------------------------------------------------

@settings(max_examples=50)
@given(
    counts=st.fixed_dictionaries({
        "Bird": st.integers(min_value=1, max_value=100),
        "Drone": st.integers(min_value=1, max_value=100),
        "UAV": st.integers(min_value=1, max_value=100),
    })
)
def test_property17_imbalance_threshold(counts):
    """Property 17: detect_imbalance returns non-empty list iff max/min > 5.0."""
    max_count = max(counts.values())
    min_count = min(counts.values())
    ratio = max_count / min_count

    result = detect_imbalance(counts, threshold=5.0)

    if ratio > 5.0:
        assert len(result) > 0, (
            f"Expected imbalance warning for ratio {ratio:.2f}, got empty list"
        )
    else:
        assert len(result) == 0, (
            f"Expected no imbalance warning for ratio {ratio:.2f}, got {result}"
        )
