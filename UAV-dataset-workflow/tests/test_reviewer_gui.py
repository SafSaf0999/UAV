"""Unit tests for ReviewerWindow (PyQt5 GUI).

Uses QApplication directly since pytest-qt may not be installed.
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

import pytest

pytest.importorskip("PyQt5")

from PyQt5.QtWidgets import QApplication

from anti_uav.gui.reviewer_ui import ReviewerWindow, ReviewerModel
from anti_uav.models import CanonicalClass

_PNG_BYTES = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
    b"\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00"
    b"\x00\x0cIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00\x05\x18"
    b"\xd8N\x00\x00\x00\x00IEND\xaeB`\x82"
)


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication(sys.argv)
    yield app


def make_yolo_dataset(tmp_path: Path, images_boxes: dict) -> Path:
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


def test_reviewer_window_opens(qapp):
    """ReviewerWindow should open without errors."""
    win = ReviewerWindow()
    assert win is not None
    win.close()


def test_reviewer_window_loads_dataset(qapp):
    """ReviewerWindow should load a dataset and show images."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        make_yolo_dataset(tmp_path, {"a.jpg": [("0", 0.5, 0.5, 0.1, 0.1)]})
        win = ReviewerWindow(dataset_path=tmp_path)
        assert win._model.images  # images loaded
        win.close()


def test_reviewer_window_status_bar(qapp):
    """Status bar should show image count after loading."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        make_yolo_dataset(tmp_path, {"a.jpg": [], "b.jpg": []})
        win = ReviewerWindow(dataset_path=tmp_path)
        status_text = win._status.currentMessage()
        assert "Total: 2" in status_text
        win.close()


def test_reviewer_window_stage_updates_status(qapp):
    """Staging an image should update the status bar staged count."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        make_yolo_dataset(tmp_path, {"a.jpg": []})
        win = ReviewerWindow(dataset_path=tmp_path)
        img = win._model.images[0]
        win._current_image = img
        win._stage_current()
        status_text = win._status.currentMessage()
        assert "Staged: 1" in status_text
        win.close()


def test_reviewer_window_filter_bar_present(qapp):
    """FilterBar should be present in the window."""
    win = ReviewerWindow()
    assert win._filter_bar is not None
    win.close()


def test_reviewer_window_annotation_panel_present(qapp):
    """AnnotationPanel should be present in the window."""
    win = ReviewerWindow()
    assert win._ann_panel is not None
    win.close()
