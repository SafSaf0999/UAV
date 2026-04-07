"""Property tests for Annotation_Backend — Property 12.

# Feature: anti-uav-dataset-workflow, Property 12: Label Studio export preserves filenames
"""
from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import MagicMock

from hypothesis import given, settings
from hypothesis import strategies as st

from anti_uav.backend import export_yolo


# ---------------------------------------------------------------------------
# Property 12: Label Studio export preserves filenames
# Validates: Requirements 4.5
# ---------------------------------------------------------------------------

def _make_mock_project(image_names: list[str]) -> MagicMock:
    """Create a mock Label Studio project that returns tasks for given image names."""
    project = MagicMock()
    tasks = [
        {
            "data": {"image": f"/path/to/{name}", "filename": name},
            "annotations": [],
        }
        for name in image_names
    ]
    project.export_tasks.return_value = tasks
    return project


@settings(max_examples=20)
@given(
    image_names=st.lists(
        st.text(
            alphabet=st.characters(whitelist_categories=("Ll", "Lu", "Nd")),
            min_size=1,
            max_size=10,
        ).map(lambda s: s + ".jpg"),
        min_size=1,
        max_size=5,
        unique=True,
    )
)
def test_property12_export_preserves_filenames(image_names: list[str]) -> None:
    """Property 12: Exported annotation filenames (stems) match original image filenames (stems).

    **Validates: Requirements 4.5**
    """
    with tempfile.TemporaryDirectory() as tmp:
        output_path = Path(tmp) / "labels"
        project = _make_mock_project(image_names)
        export_yolo(project, output_path)

        expected_stems = {Path(name).stem for name in image_names}
        exported_stems = {p.stem for p in output_path.glob("*.txt")}
        assert expected_stems == exported_stems, (
            f"Expected stems {expected_stems}, got {exported_stems}"
        )
