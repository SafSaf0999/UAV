"""Property tests for Class_Normalizer — Properties 10-11.

# Feature: anti-uav-dataset-workflow, Property 10: Normalization produces only canonical labels
# Feature: anti-uav-dataset-workflow, Property 11: Normalization log entry count matches substitutions
"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

from hypothesis import given, settings
from hypothesis import strategies as st

from anti_uav.models import CanonicalClass
from anti_uav.normalizer import normalize_dataset


_CANONICAL_VALUES = {c.value for c in CanonicalClass}
_CLASS_IDX = {c.value: i for i, c in enumerate(CanonicalClass)}

# Strategy: source class names that are not canonical
_source_class_st = st.text(
    alphabet=st.characters(whitelist_categories=("Ll", "Lu")),
    min_size=1,
    max_size=10,
).filter(lambda s: s not in _CANONICAL_VALUES)


def _make_yolo_dataset(tmp_path: Path, images: list[str], class_names: list[str]) -> dict[str, CanonicalClass]:
    """Create a YOLO TXT dataset with given source class names. Returns a full mapping."""
    images_dir = tmp_path / "images"
    labels_dir = tmp_path / "labels"
    images_dir.mkdir(parents=True)
    labels_dir.mkdir(parents=True)

    _png = (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
        b"\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00"
        b"\x00\x0cIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00\x05\x18"
        b"\xd8N\x00\x00\x00\x00IEND\xaeB`\x82"
    )

    canonical_list = list(CanonicalClass)
    mapping: dict[str, CanonicalClass] = {}
    for i, cls in enumerate(class_names):
        mapping[cls] = canonical_list[i % len(canonical_list)]

    for img_name in images:
        (images_dir / img_name).write_bytes(_png)
        stem = Path(img_name).stem
        lines = [f"{cls} 0.5 0.5 0.1 0.1" for cls in class_names]
        (labels_dir / f"{stem}.txt").write_text("\n".join(lines), encoding="utf-8")

    return mapping


# ---------------------------------------------------------------------------
# Property 10: Normalization produces only canonical labels
# Validates: Requirements 3.2
# ---------------------------------------------------------------------------

@settings(max_examples=50)
@given(
    source_classes=st.lists(
        _source_class_st,
        min_size=1,
        max_size=4,
        unique=True,
    ),
    image_count=st.integers(min_value=1, max_value=3),
)
def test_property10_normalization_produces_canonical_labels(source_classes, image_count):
    """Property 10: After normalize_dataset, every class label in every annotation file
    should be one of Bird, Drone, or UAV.

    **Validates: Requirements 3.2**
    """
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        images = [f"img{i}.jpg" for i in range(image_count)]
        mapping = _make_yolo_dataset(tmp_path, images, source_classes)

        normalize_dataset(tmp_path, mapping)

        # After normalization, class token should be a canonical class name string
        for txt_file in (tmp_path / "labels").glob("*.txt"):
            for line in txt_file.read_text(encoding="utf-8").splitlines():
                parts = line.strip().split()
                if parts:
                    assert parts[0] in _CANONICAL_VALUES, (
                        f"Non-canonical class '{parts[0]}' found in {txt_file}"
                    )


# ---------------------------------------------------------------------------
# Property 11: Normalization log entry count matches substitutions
# Validates: Requirements 3.5
# ---------------------------------------------------------------------------

@settings(max_examples=50)
@given(
    source_classes=st.lists(
        _source_class_st,
        min_size=1,
        max_size=4,
        unique=True,
    ),
    image_count=st.integers(min_value=1, max_value=3),
)
def test_property11_log_entry_count_matches_substitutions(source_classes, image_count):
    """Property 11: sum of file_count values in NormalizationLog.substitutions
    should equal total_files_modified.

    **Validates: Requirements 3.5**
    """
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        images = [f"img{i}.jpg" for i in range(image_count)]
        mapping = _make_yolo_dataset(tmp_path, images, source_classes)

        log = normalize_dataset(tmp_path, mapping)

        total_from_subs = sum(count for _, _, count in log.substitutions)
        assert total_from_subs == log.total_files_modified, (
            f"Sum of substitution file_counts ({total_from_subs}) != "
            f"total_files_modified ({log.total_files_modified})"
        )
