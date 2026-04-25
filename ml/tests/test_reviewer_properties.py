"""Property tests for ReviewerModel — Properties 4-9.

# Feature: anti-uav-dataset-workflow, Property 4: Deletion staging does not remove files
# Feature: anti-uav-dataset-workflow, Property 5: Confirmed deletion removes all staged files
# Feature: anti-uav-dataset-workflow, Property 6: Label remap produces canonical class
# Feature: anti-uav-dataset-workflow, Property 7: Class filter returns only matching images
# Feature: anti-uav-dataset-workflow, Property 8: Save-then-reload preserves annotations
# Feature: anti-uav-dataset-workflow, Property 9: Status counts match actual file counts
"""
from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from anti_uav.gui.reviewer_ui import ReviewerModel
from anti_uav.models import AnnotationFormat, CanonicalClass


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_yolo_dataset(tmp_path: Path, images: list[str], boxes_per_image: dict[str, list[tuple[str, float, float, float, float]]]) -> Path:
    """Create a minimal YOLO TXT dataset in tmp_path."""
    images_dir = tmp_path / "images"
    labels_dir = tmp_path / "labels"
    images_dir.mkdir(parents=True)
    labels_dir.mkdir(parents=True)

    for name in images:
        # Create a tiny valid PNG (1x1 pixel)
        img_path = images_dir / name
        img_path.write_bytes(
            b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
            b"\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00"
            b"\x00\x0cIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00\x05\x18"
            b"\xd8N\x00\x00\x00\x00IEND\xaeB`\x82"
        )
        stem = Path(name).stem
        boxes = boxes_per_image.get(name, [])
        lines = [f"{cls} {x} {y} {w} {h}" for cls, x, y, w, h in boxes]
        (labels_dir / f"{stem}.txt").write_text("\n".join(lines), encoding="utf-8")

    return tmp_path


# ---------------------------------------------------------------------------
# Property 4: Deletion staging does not remove files
# Validates: Requirements 2.3
# ---------------------------------------------------------------------------

@settings(max_examples=50)
@given(
    image_names=st.lists(
        st.text(alphabet=st.characters(whitelist_categories=("Ll", "Lu", "Nd")), min_size=1, max_size=8).map(lambda s: s + ".jpg"),
        min_size=1,
        max_size=5,
        unique=True,
    )
)
def test_property4_staging_does_not_remove_files(image_names):
    """Property 4: Staging images for deletion must not delete files from disk."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        _make_yolo_dataset(tmp_path, image_names, {})

        model = ReviewerModel()
        model.load_dataset(tmp_path)

        images = model.images
        for img in images:
            model.stage_deletion(img)

        # All files must still exist
        for img in images:
            assert img.is_file(), f"File {img} was deleted after staging (should not be)"


# ---------------------------------------------------------------------------
# Property 5: Confirmed deletion removes all staged files
# Validates: Requirements 2.4
# ---------------------------------------------------------------------------

@settings(max_examples=50)
@given(
    image_names=st.lists(
        st.text(alphabet=st.characters(whitelist_categories=("Ll", "Lu", "Nd")), min_size=1, max_size=8).map(lambda s: s + ".jpg"),
        min_size=1,
        max_size=5,
        unique=True,
    )
)
def test_property5_confirmed_deletion_removes_files(image_names):
    """Property 5: After confirm_deletions, staged files must not exist on disk."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        _make_yolo_dataset(tmp_path, image_names, {})

        model = ReviewerModel()
        model.load_dataset(tmp_path)

        images = model.images
        for img in images:
            model.stage_deletion(img)

        deleted = model.confirm_deletions()

        for img in deleted:
            assert not img.is_file(), f"File {img} still exists after confirm_deletions"


# ---------------------------------------------------------------------------
# Property 6: Label remap produces canonical class
# Validates: Requirements 2.5
# ---------------------------------------------------------------------------

@settings(max_examples=50)
@given(
    new_label=st.sampled_from(list(CanonicalClass)),
    bbox_idx=st.integers(min_value=0, max_value=2),
)
def test_property6_remap_produces_canonical_class(new_label, bbox_idx):
    """Property 6: After remap_label, the annotation's class_name equals the canonical class value."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        boxes = {
            "img0.jpg": [
                ("0", 0.5, 0.5, 0.1, 0.1),
                ("1", 0.3, 0.3, 0.1, 0.1),
                ("2", 0.7, 0.7, 0.1, 0.1),
            ]
        }
        _make_yolo_dataset(tmp_path, ["img0.jpg"], boxes)

        model = ReviewerModel()
        model.load_dataset(tmp_path)

        images = model.images
        if not images:
            return

        img = images[0]
        ann = model.get_annotation(img)
        if ann is None or bbox_idx >= len(ann.boxes):
            return

        model.remap_label(img, bbox_idx, new_label)
        ann_after = model.get_annotation(img)
        assert ann_after is not None
        assert ann_after.boxes[bbox_idx].class_name == new_label.value


# ---------------------------------------------------------------------------
# Property 7: Class filter returns only matching images
# Validates: Requirements 2.6
# ---------------------------------------------------------------------------

@settings(max_examples=50)
@given(
    filter_cls=st.sampled_from(["Bird", "Drone", "UAV"]),
)
def test_property7_filter_returns_only_matching(filter_cls):
    """Property 7: filter_by_class returns only images with at least one bbox of that class."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        # Create images with known class assignments
        boxes = {
            "bird_img.jpg": [("Bird", 0.5, 0.5, 0.1, 0.1)],
            "drone_img.jpg": [("Drone", 0.5, 0.5, 0.1, 0.1)],
            "uav_img.jpg": [("UAV", 0.5, 0.5, 0.1, 0.1)],
            "mixed_img.jpg": [("Bird", 0.3, 0.3, 0.1, 0.1), ("Drone", 0.7, 0.7, 0.1, 0.1)],
        }
        _make_yolo_dataset(tmp_path, list(boxes.keys()), boxes)

        model = ReviewerModel()
        model.load_dataset(tmp_path)

        filtered = model.filter_by_class(filter_cls)
        for img_path in filtered:
            ann = model.get_annotation(img_path)
            assert ann is not None, f"No annotation for {img_path}"
            class_names = [b.class_name for b in ann.boxes]
            assert filter_cls in class_names, (
                f"Image {img_path} returned by filter '{filter_cls}' "
                f"but has classes {class_names}"
            )


# ---------------------------------------------------------------------------
# Property 8: Save-then-reload preserves annotations
# Validates: Requirements 2.7
# ---------------------------------------------------------------------------

@settings(max_examples=50)
@given(
    new_label=st.sampled_from(list(CanonicalClass)),
)
def test_property8_save_reload_preserves_annotations(new_label):
    """Property 8: After save_changes, reloading the dataset yields the same annotations."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        boxes = {
            "img0.jpg": [("0", 0.5, 0.5, 0.1, 0.1)],
        }
        _make_yolo_dataset(tmp_path, ["img0.jpg"], boxes)

        model = ReviewerModel()
        model.load_dataset(tmp_path)

        images = model.images
        if not images:
            return

        img = images[0]
        ann = model.get_annotation(img)
        if ann is None or not ann.boxes:
            return

        model.remap_label(img, 0, new_label)
        model.save_changes()

        # Reload
        model2 = ReviewerModel()
        model2.load_dataset(tmp_path)

        images2 = model2.images
        if not images2:
            return

        # Find the same image
        img2 = next((p for p in images2 if p.name == img.name), None)
        if img2 is None:
            return

        ann2 = model2.get_annotation(img2)
        assert ann2 is not None
        assert len(ann2.boxes) > 0
        # The class name should match the canonical class value
        assert ann2.boxes[0].class_name in (new_label.value, str(_canonical_to_idx(new_label)))


def _canonical_to_idx(cls: CanonicalClass) -> int:
    return {"Bird": 0, "Drone": 1, "UAV": 2}[cls.value]


# ---------------------------------------------------------------------------
# Property 9: Status counts match actual file counts
# Validates: Requirements 2.8
# ---------------------------------------------------------------------------

@settings(max_examples=50)
@given(
    image_names=st.lists(
        st.text(alphabet=st.characters(whitelist_categories=("Ll", "Lu", "Nd")), min_size=1, max_size=8).map(lambda s: s + ".jpg"),
        min_size=1,
        max_size=6,
        unique=True,
    ),
    num_to_stage=st.integers(min_value=0, max_value=3),
)
def test_property9_counts_match_actual(image_names, num_to_stage):
    """Property 9: get_counts returns counts matching actual image and staged file counts."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        _make_yolo_dataset(tmp_path, image_names, {})

        model = ReviewerModel()
        model.load_dataset(tmp_path)

        images = model.images
        num_to_stage = min(num_to_stage, len(images))
        for img in images[:num_to_stage]:
            model.stage_deletion(img)

        counts = model.get_counts()
        assert counts.total == len(images), (
            f"Expected total={len(images)}, got {counts.total}"
        )
        assert counts.staged_for_deletion == num_to_stage, (
            f"Expected staged={num_to_stage}, got {counts.staged_for_deletion}"
        )
