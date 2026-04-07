"""Unit tests for Annotation_Backend (mock label_studio_sdk)."""
from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from anti_uav.backend import (
    _LABEL_CONFIG_XML,
    create_project,
    export_yolo,
    get_label_count,
    import_dataset,
    is_running,
    start_label_studio,
    stop_label_studio,
)


_PNG_BYTES = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
    b"\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00"
    b"\x00\x0cIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00\x05\x18"
    b"\xd8N\x00\x00\x00\x00IEND\xaeB`\x82"
)


# ---------------------------------------------------------------------------
# is_running tests
# ---------------------------------------------------------------------------

def test_is_running_true():
    """Mock requests.get returning 200, assert is_running returns True."""
    with patch("anti_uav.backend.requests.get") as mock_get:
        mock_get.return_value.status_code = 200
        assert is_running("http://localhost:8080") is True


def test_is_running_false():
    """Mock requests.get raising ConnectionError, assert returns False."""
    with patch("anti_uav.backend.requests.get", side_effect=ConnectionError("refused")):
        assert is_running("http://localhost:8080") is False


def test_is_running_returns_false_on_non_200():
    with patch("anti_uav.backend.requests.get") as mock_get:
        mock_get.return_value.status_code = 503
        assert is_running("http://localhost:8080") is False


# ---------------------------------------------------------------------------
# create_project tests
# ---------------------------------------------------------------------------

def test_create_project_label_config_has_three_labels():
    """Verify label config XML passed to create contains Bird, Drone, UAV."""
    client = MagicMock()
    mock_project = MagicMock()
    client.projects.create.return_value = mock_project

    create_project(client, "test-project")

    client.projects.create.assert_called_once()
    call_kwargs = client.projects.create.call_args
    label_config = call_kwargs.kwargs.get("label_config", "")
    assert "Bird" in label_config
    assert "Drone" in label_config
    assert "UAV" in label_config
    assert get_label_count(label_config) == 3


def test_create_project_preserves_name():
    """Verify project title is set to the provided name."""
    client = MagicMock()
    client.projects.create.return_value = MagicMock()

    create_project(client, "my-dataset-project")

    call_kwargs = client.projects.create.call_args
    assert call_kwargs.kwargs.get("title") == "my-dataset-project"


# ---------------------------------------------------------------------------
# start_label_studio tests
# ---------------------------------------------------------------------------

def test_start_label_studio_calls_subprocess():
    """Mock subprocess.Popen, verify called with correct args."""
    with patch("anti_uav.backend.subprocess.Popen") as mock_popen:
        mock_proc = MagicMock()
        mock_popen.return_value = mock_proc

        proc = start_label_studio(port=9090)

        assert proc is mock_proc
        mock_popen.assert_called_once()
        args = mock_popen.call_args[0][0]
        assert args[0] == "label-studio"
        assert "--port" in args
        assert "9090" in args
        assert "--no-browser" in args


# ---------------------------------------------------------------------------
# stop_label_studio tests
# ---------------------------------------------------------------------------

def test_stop_label_studio_terminates_process():
    """Mock proc, verify terminate() called."""
    mock_proc = MagicMock()
    mock_proc.poll.return_value = None  # still running

    stop_label_studio(mock_proc)

    mock_proc.terminate.assert_called_once()


# ---------------------------------------------------------------------------
# import_dataset tests
# ---------------------------------------------------------------------------

def test_import_dataset_imports_images():
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        (tmp_path / "a.jpg").write_bytes(_PNG_BYTES)
        (tmp_path / "b.jpg").write_bytes(_PNG_BYTES)

        project = MagicMock()
        import_dataset(project, tmp_path)

        project.import_tasks.assert_called_once()
        tasks = project.import_tasks.call_args[0][0]
        assert len(tasks) == 2


def test_import_dataset_preserves_filenames():
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        (tmp_path / "my_image.jpg").write_bytes(_PNG_BYTES)

        project = MagicMock()
        import_dataset(project, tmp_path)

        tasks = project.import_tasks.call_args[0][0]
        # Each task has {"image": str(path)}; the path should contain the filename
        assert any("my_image.jpg" in t["image"] for t in tasks)


def test_import_dataset_empty_dir():
    with tempfile.TemporaryDirectory() as tmp:
        project = MagicMock()
        import_dataset(project, Path(tmp))
        project.import_tasks.assert_not_called()


# ---------------------------------------------------------------------------
# export_yolo tests
# ---------------------------------------------------------------------------

def test_export_yolo_writes_file():
    """Mock project.export_tasks returning bytes, verify file written to output_path."""
    with tempfile.TemporaryDirectory() as tmp:
        output_path = Path(tmp) / "labels"
        project = MagicMock()
        project.export_tasks.return_value = b"PK\x03\x04fake zip content"

        export_yolo(project, output_path)

        project.export_tasks.assert_called_once_with(export_type="YOLO")
        assert (output_path / "annotations.zip").is_file()


def test_export_yolo_creates_label_files_from_tasks():
    with tempfile.TemporaryDirectory() as tmp:
        output_path = Path(tmp) / "labels"
        project = MagicMock()
        project.export_tasks.return_value = [
            {
                "data": {"image": "/path/img1.jpg", "filename": "img1.jpg"},
                "annotations": [
                    {
                        "result": [
                            {
                                "value": {
                                    "x": 10.0, "y": 10.0,
                                    "width": 20.0, "height": 20.0,
                                    "rectanglelabels": ["Bird"],
                                }
                            }
                        ]
                    }
                ],
            }
        ]
        export_yolo(project, output_path)
        assert (output_path / "img1.txt").is_file()


# ---------------------------------------------------------------------------
# Label config XML sanity checks
# ---------------------------------------------------------------------------

def test_label_config_has_exactly_3_labels():
    assert get_label_count(_LABEL_CONFIG_XML) == 3


def test_label_config_contains_canonical_classes():
    assert "Bird" in _LABEL_CONFIG_XML
    assert "Drone" in _LABEL_CONFIG_XML
    assert "UAV" in _LABEL_CONFIG_XML
