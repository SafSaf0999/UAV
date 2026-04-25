"""Unit tests for ReviewerModel (no PyQt5 required)."""
from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from anti_uav.gui.reviewer_ui import ReviewerModel
from anti_uav.models import AnnotationFormat, CanonicalClass


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_PNG_BYTES = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
    b"\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00"
    b"\x00\x0cIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00\x05\x18"
    b"\xd8N\x00\x00\x00\x00IEND\xaeB`\x82"
)


def make_yolo_dataset(tmp_path: Path, images_boxes: dict[str, list[tuple]]) -> Path:
    """Create a YOLO TXT dataset. images_boxes: {img_name: [(cls, x, y, w, h), ...]}"""
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
# Tests
# ---------------------------------------------------------------------------

def test_load_dataset_finds_images():
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        make_yolo_dataset(tmp_path, {"a.jpg": [], "b.jpg": []})
        model = ReviewerModel()
        model.load_dataset(tmp_path)
        assert len(model.images) == 2


def test_load_dataset_detects_yolo_format():
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        make_yolo_dataset(tmp_path, {"a.jpg": [("0", 0.5, 0.5, 0.1, 0.1)]})
        model = ReviewerModel()
        model.load_dataset(tmp_path)
        assert model.format == AnnotationFormat.YOLO_TXT


def test_stage_deletion_does_not_delete():
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        make_yolo_dataset(tmp_path, {"a.jpg": []})
        model = ReviewerModel()
        model.load_dataset(tmp_path)
        img = model.images[0]
        model.stage_deletion(img)
        assert img.is_file()
        assert img in model.staged


def test_unstage_deletion():
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        make_yolo_dataset(tmp_path, {"a.jpg": []})
        model = ReviewerModel()
        model.load_dataset(tmp_path)
        img = model.images[0]
        model.stage_deletion(img)
        model.unstage_deletion(img)
        assert img not in model.staged


def test_confirm_deletions_removes_files():
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        make_yolo_dataset(tmp_path, {"a.jpg": [], "b.jpg": []})
        model = ReviewerModel()
        model.load_dataset(tmp_path)
        img = model.images[0]
        model.stage_deletion(img)
        deleted = model.confirm_deletions()
        assert img in deleted
        assert not img.is_file()


def test_confirm_deletions_removes_annotation():
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        make_yolo_dataset(tmp_path, {"a.jpg": [("0", 0.5, 0.5, 0.1, 0.1)]})
        model = ReviewerModel()
        model.load_dataset(tmp_path)
        img = model.images[0]
        model.stage_deletion(img)
        model.confirm_deletions()
        # Annotation file should also be gone
        ann_file = tmp_path / "labels" / "a.txt"
        assert not ann_file.is_file()


def test_remap_label_changes_class():
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        make_yolo_dataset(tmp_path, {"a.jpg": [("0", 0.5, 0.5, 0.1, 0.1)]})
        model = ReviewerModel()
        model.load_dataset(tmp_path)
        img = model.images[0]
        model.remap_label(img, 0, CanonicalClass.DRONE)
        ann = model.get_annotation(img)
        assert ann is not None
        assert ann.boxes[0].class_name == "Drone"


def test_remap_label_out_of_range_is_noop():
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        make_yolo_dataset(tmp_path, {"a.jpg": [("0", 0.5, 0.5, 0.1, 0.1)]})
        model = ReviewerModel()
        model.load_dataset(tmp_path)
        img = model.images[0]
        # Should not raise
        model.remap_label(img, 99, CanonicalClass.UAV)
        ann = model.get_annotation(img)
        assert ann.boxes[0].class_name == "0"  # unchanged


def test_save_changes_writes_file():
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        make_yolo_dataset(tmp_path, {"a.jpg": [("0", 0.5, 0.5, 0.1, 0.1)]})
        model = ReviewerModel()
        model.load_dataset(tmp_path)
        img = model.images[0]
        model.remap_label(img, 0, CanonicalClass.BIRD)
        model.save_changes()
        label_file = tmp_path / "labels" / "a.txt"
        content = label_file.read_text(encoding="utf-8")
        # Bird maps to index 0
        assert content.startswith("0 ")


def test_filter_by_class_none_returns_all():
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        make_yolo_dataset(tmp_path, {"a.jpg": [("0", 0.5, 0.5, 0.1, 0.1)], "b.jpg": []})
        model = ReviewerModel()
        model.load_dataset(tmp_path)
        result = model.filter_by_class(None)
        assert len(result) == 2


def test_filter_by_class_returns_matching():
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        # YOLO TXT uses integer class indices; remap after loading
        make_yolo_dataset(tmp_path, {
            "bird.jpg": [("0", 0.5, 0.5, 0.1, 0.1)],
            "drone.jpg": [("1", 0.5, 0.5, 0.1, 0.1)],
        })
        model = ReviewerModel()
        model.load_dataset(tmp_path)
        # Remap class "0" -> Bird for bird.jpg
        bird_img = next(p for p in model.images if p.name == "bird.jpg")
        model.remap_label(bird_img, 0, CanonicalClass.BIRD)
        result = model.filter_by_class("Bird")
        assert len(result) == 1
        assert result[0].name == "bird.jpg"


def test_get_counts_total():
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        make_yolo_dataset(tmp_path, {"a.jpg": [], "b.jpg": [], "c.jpg": []})
        model = ReviewerModel()
        model.load_dataset(tmp_path)
        counts = model.get_counts()
        assert counts.total == 3


def test_get_counts_staged():
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        make_yolo_dataset(tmp_path, {"a.jpg": [], "b.jpg": []})
        model = ReviewerModel()
        model.load_dataset(tmp_path)
        model.stage_deletion(model.images[0])
        counts = model.get_counts()
        assert counts.staged_for_deletion == 1


def test_get_counts_per_class():
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        make_yolo_dataset(tmp_path, {
            "a.jpg": [("0", 0.5, 0.5, 0.1, 0.1)],
            "b.jpg": [("1", 0.5, 0.5, 0.1, 0.1)],
        })
        model = ReviewerModel()
        model.load_dataset(tmp_path)
        # Remap to canonical names
        img_a = next(p for p in model.images if p.name == "a.jpg")
        img_b = next(p for p in model.images if p.name == "b.jpg")
        model.remap_label(img_a, 0, CanonicalClass.BIRD)
        model.remap_label(img_b, 0, CanonicalClass.DRONE)
        counts = model.get_counts()
        assert counts.per_class.get("Bird", 0) == 1
        assert counts.per_class.get("Drone", 0) == 1


def test_empty_dataset():
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        tmp_path.mkdir(exist_ok=True)
        model = ReviewerModel()
        model.load_dataset(tmp_path)
        assert model.images == []
        counts = model.get_counts()
        assert counts.total == 0
        assert counts.staged_for_deletion == 0


# ===========================================================================
# Property-based tests (Properties 4-9) — hypothesis, no PyQt5 needed
# ===========================================================================

import tempfile

from hypothesis import given, settings, HealthCheck
from hypothesis import strategies as st


_PNG_BYTES_PROP = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
    b"\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00"
    b"\x00\x0cIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00\x05\x18"
    b"\xd8N\x00\x00\x00\x00IEND\xaeB`\x82"
)

_safe_name = (
    st.text(
        alphabet=st.characters(whitelist_categories=("Ll", "Lu", "Nd")),
        min_size=1, max_size=8,
    ).map(lambda s: s + ".jpg")
)


def _make_prop_dataset(root: Path, names: list[str],
                       boxes: dict | None = None) -> None:
    """Create a minimal YOLO dataset for property tests."""
    (root / "images").mkdir(parents=True, exist_ok=True)
    (root / "labels").mkdir(parents=True, exist_ok=True)
    for name in names:
        (root / "images" / name).write_bytes(_PNG_BYTES_PROP)
        stem = Path(name).stem
        img_boxes = (boxes or {}).get(name, [])
        lines = [f"{cls} {x} {y} {w} {h}" for cls, x, y, w, h in img_boxes]
        (root / "labels" / f"{stem}.txt").write_text(
            "\n".join(lines), encoding="utf-8"
        )


# ---------------------------------------------------------------------------
# Property 4: Staging does not delete files from disk
# Validates: Requirements 2.3
# ---------------------------------------------------------------------------

@settings(max_examples=30)
@given(
    image_names=st.lists(_safe_name, min_size=1, max_size=5, unique=True)
)
def test_property4_staging_does_not_remove_files(image_names):
    """**Validates: Requirements 2.3**"""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _make_prop_dataset(root, image_names)
        model = ReviewerModel()
        model.load_dataset(root)
        for img in model.images:
            model.stage_deletion(img)
        for img in model.images:
            assert img.is_file()


# ---------------------------------------------------------------------------
# Property 5: Confirmed deletion removes all staged files
# Validates: Requirements 2.4
# ---------------------------------------------------------------------------

@settings(max_examples=30)
@given(
    image_names=st.lists(_safe_name, min_size=1, max_size=5, unique=True)
)
def test_property5_confirmed_deletion_removes_files(image_names):
    """**Validates: Requirements 2.4**"""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _make_prop_dataset(root, image_names)
        model = ReviewerModel()
        model.load_dataset(root)
        for img in model.images:
            model.stage_deletion(img)
        deleted = model.confirm_deletions()
        for img in deleted:
            assert not img.is_file()


# ---------------------------------------------------------------------------
# Property 6: remap_label produces canonical class
# Validates: Requirements 2.5
# ---------------------------------------------------------------------------

@settings(max_examples=30)
@given(new_label=st.sampled_from(list(CanonicalClass)))
def test_property6_remap_produces_canonical_class(new_label):
    """**Validates: Requirements 2.5**"""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _make_prop_dataset(root, ["img.jpg"],
                           {"img.jpg": [("0", 0.5, 0.5, 0.1, 0.1)]})
        model = ReviewerModel()
        model.load_dataset(root)
        img = model.images[0]
        model.remap_label(img, 0, new_label)
        ann = model.get_annotation(img)
        assert ann is not None
        assert ann.boxes[0].class_name == new_label.value


# ---------------------------------------------------------------------------
# Property 7: filter_by_class returns only matching images
# Validates: Requirements 2.6
# ---------------------------------------------------------------------------

@settings(max_examples=30)
@given(filter_cls=st.sampled_from(["Bird", "Drone", "UAV"]))
def test_property7_filter_returns_only_matching(filter_cls):
    """**Validates: Requirements 2.6**"""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        boxes = {
            "bird.jpg": [("Bird", 0.5, 0.5, 0.1, 0.1)],
            "drone.jpg": [("Drone", 0.5, 0.5, 0.1, 0.1)],
            "uav.jpg": [("UAV", 0.5, 0.5, 0.1, 0.1)],
        }
        _make_prop_dataset(root, list(boxes.keys()), boxes)
        model = ReviewerModel()
        model.load_dataset(root)
        filtered = model.filter_by_class(filter_cls)
        for img_path in filtered:
            ann = model.get_annotation(img_path)
            assert ann is not None
            assert any(b.class_name == filter_cls for b in ann.boxes)


# ---------------------------------------------------------------------------
# Property 8: save-then-reload preserves annotations
# Validates: Requirements 2.7
# ---------------------------------------------------------------------------

@settings(max_examples=30)
@given(new_label=st.sampled_from(list(CanonicalClass)))
def test_property8_save_reload_preserves_annotations(new_label):
    """**Validates: Requirements 2.7**"""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _make_prop_dataset(root, ["img.jpg"],
                           {"img.jpg": [("0", 0.5, 0.5, 0.1, 0.1)]})
        model = ReviewerModel()
        model.load_dataset(root)
        img = model.images[0]
        model.remap_label(img, 0, new_label)
        model.save_changes()

        model2 = ReviewerModel()
        model2.load_dataset(root)
        img2 = next(p for p in model2.images if p.name == img.name)
        ann2 = model2.get_annotation(img2)
        assert ann2 is not None and len(ann2.boxes) > 0
        _idx = {"Bird": "0", "Drone": "1", "UAV": "2"}[new_label.value]
        assert ann2.boxes[0].class_name in (new_label.value, _idx)


# ---------------------------------------------------------------------------
# Property 9: get_counts matches actual file counts
# Validates: Requirements 2.8
# ---------------------------------------------------------------------------

@settings(max_examples=30)
@given(
    image_names=st.lists(_safe_name, min_size=1, max_size=6, unique=True),
    num_to_stage=st.integers(min_value=0, max_value=3),
)
def test_property9_counts_match_actual(image_names, num_to_stage):
    """**Validates: Requirements 2.8**"""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _make_prop_dataset(root, image_names)
        model = ReviewerModel()
        model.load_dataset(root)
        images = model.images
        n = min(num_to_stage, len(images))
        for img in images[:n]:
            model.stage_deletion(img)
        counts = model.get_counts()
        assert counts.total == len(images)
        assert counts.staged_for_deletion == n
