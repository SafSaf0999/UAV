"""Tests for Colab_Bridge — unit tests and Property 30.

# Feature: anti-uav-dataset-workflow, Property 30: Generated notebook is valid and contains required cells
"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import nbformat
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from anti_uav.colab_bridge import (
    AuthenticationError,
    authenticate_kaggle,
    download_kaggle_output,
    generate_notebook,
    poll_kaggle_kernel,
    push_kaggle_kernel,
    retry_failed_uploads,
    upload_to_drive,
)
from anti_uav.models import (
    HardwareProfile,
    KernelStatus,
    RemoteBackend,
    TrainingConfig,
    UploadManifest,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_AUGMENTATION = {
    "mosaic": 1.0, "mixup": 0.15, "copy_paste": 0.3,
    "hsv_h": 0.015, "hsv_s": 0.7, "hsv_v": 0.4,
    "degrees": 10.0, "translate": 0.1, "scale": 0.5,
    "flipud": 0.1, "fliplr": 0.5,
}


def _make_config(profile: HardwareProfile = HardwareProfile.COLAB_T4) -> TrainingConfig:
    return TrainingConfig(
        model_variant="yolo26m",
        imgsz=640,
        batch=32,
        epochs=100,
        optimizer="MuSGD",
        lr0=0.01,
        weight_decay=0.0005,
        amp=True,
        augmentation=_AUGMENTATION.copy(),
        hardware_profile=profile,
        data_yaml=Path("data.yaml"),
    )


_COLAB_REQUIRED_KEYWORDS = [
    "Mount Google Drive",
    "Install dependencies",
    "Extract dataset",
    "Run training",
    "Archive results",
]

_KAGGLE_REQUIRED_KEYWORDS = [
    "Mount dataset",
    "Install dependencies",
    "Run training",
    "Save outputs",
]


def _all_cell_sources(nb: nbformat.NotebookNode) -> str:
    """Concatenate all cell sources into one string for keyword searching."""
    return "\n".join(cell.source for cell in nb.cells)


# ---------------------------------------------------------------------------
# test_generate_notebook_colab_valid
# ---------------------------------------------------------------------------

def test_generate_notebook_colab_valid():
    """nbformat.validate must pass for a Colab notebook."""
    config = _make_config(HardwareProfile.COLAB_T4)
    nb = generate_notebook(config, RemoteBackend.COLAB, "folder123")
    nbformat.validate(nb)


# ---------------------------------------------------------------------------
# test_generate_notebook_kaggle_valid
# ---------------------------------------------------------------------------

def test_generate_notebook_kaggle_valid():
    """nbformat.validate must pass for a Kaggle notebook."""
    config = _make_config(HardwareProfile.COLAB_T4)
    nb = generate_notebook(config, RemoteBackend.KAGGLE, "user/dataset")
    nbformat.validate(nb)


# ---------------------------------------------------------------------------
# test_generate_notebook_colab_has_required_cells
# ---------------------------------------------------------------------------

def test_generate_notebook_colab_has_required_cells():
    """All 5 required Colab cell keywords must be present."""
    config = _make_config(HardwareProfile.COLAB_T4)
    nb = generate_notebook(config, RemoteBackend.COLAB, "folder123")
    sources = _all_cell_sources(nb)
    for keyword in _COLAB_REQUIRED_KEYWORDS:
        assert keyword in sources, f"Missing required Colab cell keyword: '{keyword}'"


# ---------------------------------------------------------------------------
# test_generate_notebook_kaggle_has_required_cells
# ---------------------------------------------------------------------------

def test_generate_notebook_kaggle_has_required_cells():
    """All 4 required Kaggle cell keywords must be present."""
    config = _make_config(HardwareProfile.COLAB_T4)
    nb = generate_notebook(config, RemoteBackend.KAGGLE, "user/dataset")
    sources = _all_cell_sources(nb)
    for keyword in _KAGGLE_REQUIRED_KEYWORDS:
        assert keyword in sources, f"Missing required Kaggle cell keyword: '{keyword}'"


# ---------------------------------------------------------------------------
# test_generate_notebook_kaggle_dual_t4_has_device
# ---------------------------------------------------------------------------

def test_generate_notebook_kaggle_dual_t4_has_device():
    """KAGGLE_DUAL_T4 profile must include device=\"0,1\" in the training cell."""
    config = _make_config(HardwareProfile.KAGGLE_DUAL_T4)
    nb = generate_notebook(config, RemoteBackend.KAGGLE, "user/dataset")
    sources = _all_cell_sources(nb)
    assert "0,1" in sources, "KAGGLE_DUAL_T4 notebook must contain device=\"0,1\""


# ---------------------------------------------------------------------------
# test_upload_to_drive_returns_manifest
# ---------------------------------------------------------------------------

def test_upload_to_drive_returns_manifest():
    """upload_to_drive must return an UploadManifest."""
    with tempfile.TemporaryDirectory() as tmp:
        local_file = Path(tmp) / "dataset.zip"
        local_file.write_bytes(b"fake zip content")

        mock_service = MagicMock()
        mock_create = MagicMock()
        mock_create.execute.return_value = {"id": "drive_file_id_123"}
        mock_service.files.return_value.create.return_value = mock_create

        with patch("anti_uav.colab_bridge._MediaFileUpload") as mock_media:
            mock_media.return_value = MagicMock()
            manifest = upload_to_drive(mock_service, local_file, "folder_abc")

        assert isinstance(manifest, UploadManifest)
        assert str(local_file) in manifest.uploaded
        assert manifest.uploaded[str(local_file)] == "drive_file_id_123"
        assert manifest.failed == []


# ---------------------------------------------------------------------------
# test_retry_failed_uploads_skips_uploaded
# ---------------------------------------------------------------------------

def test_retry_failed_uploads_skips_uploaded():
    """retry_failed_uploads must only re-upload files in manifest.failed."""
    with tempfile.TemporaryDirectory() as tmp:
        already_uploaded = Path(tmp) / "already.zip"
        already_uploaded.write_bytes(b"uploaded")
        failed_file = Path(tmp) / "failed.zip"
        failed_file.write_bytes(b"failed content")

        manifest = UploadManifest(
            uploaded={str(already_uploaded): "existing_id"},
            failed=[str(failed_file)],
        )

        mock_service = MagicMock()
        mock_create = MagicMock()
        mock_create.execute.return_value = {"id": "new_file_id"}
        mock_service.files.return_value.create.return_value = mock_create

        with patch("anti_uav.colab_bridge._MediaFileUpload") as mock_media:
            mock_media.return_value = MagicMock()
            retry_failed_uploads(mock_service, manifest)

        # The previously-uploaded file must still be in uploaded (unchanged)
        assert str(already_uploaded) in manifest.uploaded
        assert manifest.uploaded[str(already_uploaded)] == "existing_id"

        # The failed file should now be uploaded
        assert str(failed_file) in manifest.uploaded
        assert manifest.failed == []

        # create() should have been called exactly once (for the failed file only)
        assert mock_service.files.return_value.create.call_count == 1


# ---------------------------------------------------------------------------
# test_authenticate_kaggle_raises_on_missing_file
# ---------------------------------------------------------------------------

def test_authenticate_kaggle_raises_on_missing_file():
    """authenticate_kaggle must raise AuthenticationError when file is missing."""
    with pytest.raises(AuthenticationError):
        authenticate_kaggle(Path("/nonexistent/path/kaggle.json"))


def test_authenticate_kaggle_raises_on_invalid_json():
    """authenticate_kaggle must raise AuthenticationError when JSON is missing keys."""
    with tempfile.TemporaryDirectory() as tmp:
        creds = Path(tmp) / "kaggle.json"
        creds.write_text(json.dumps({"username": "user"}), encoding="utf-8")  # missing 'key'
        with pytest.raises(AuthenticationError):
            authenticate_kaggle(creds)


def test_authenticate_kaggle_succeeds_with_valid_credentials():
    """authenticate_kaggle must succeed and set env vars with valid kaggle.json."""
    import os
    with tempfile.TemporaryDirectory() as tmp:
        creds = Path(tmp) / "kaggle.json"
        creds.write_text(
            json.dumps({"username": "testuser", "key": "abc123"}),
            encoding="utf-8",
        )
        authenticate_kaggle(creds)
        assert os.environ.get("KAGGLE_USERNAME") == "testuser"
        assert os.environ.get("KAGGLE_KEY") == "abc123"


# ---------------------------------------------------------------------------
# test_poll_kaggle_kernel_returns_complete
# ---------------------------------------------------------------------------

def test_poll_kaggle_kernel_returns_complete():
    """poll_kaggle_kernel must return KernelStatus.COMPLETE when status output contains 'complete'."""
    mock_result = MagicMock()
    mock_result.stdout = "Status: complete"
    mock_result.stderr = ""

    with patch("anti_uav.colab_bridge.subprocess.run", return_value=mock_result):
        status = poll_kaggle_kernel("user/kernel", poll_interval=0, timeout=60)

    assert status == KernelStatus.COMPLETE


def test_poll_kaggle_kernel_returns_error():
    """poll_kaggle_kernel must return KernelStatus.ERROR when status output contains 'error'."""
    mock_result = MagicMock()
    mock_result.stdout = "Status: error"
    mock_result.stderr = ""

    with patch("anti_uav.colab_bridge.subprocess.run", return_value=mock_result):
        status = poll_kaggle_kernel("user/kernel", poll_interval=0, timeout=60)

    assert status == KernelStatus.ERROR


def test_poll_kaggle_kernel_timeout_returns_error():
    """poll_kaggle_kernel must return KernelStatus.ERROR on timeout."""
    mock_result = MagicMock()
    mock_result.stdout = "Status: running"
    mock_result.stderr = ""

    with patch("anti_uav.colab_bridge.subprocess.run", return_value=mock_result):
        with patch("anti_uav.colab_bridge.time.sleep"):
            status = poll_kaggle_kernel("user/kernel", poll_interval=1, timeout=2)

    assert status == KernelStatus.ERROR


# ---------------------------------------------------------------------------
# Property 30: Generated notebook is valid and contains required cells
# Validates: Requirements 10.1-10.5
# ---------------------------------------------------------------------------

_ALL_BACKENDS = list(RemoteBackend)
_ALL_PROFILES = list(HardwareProfile)


@settings(max_examples=20, deadline=None)
@given(
    backend=st.sampled_from(_ALL_BACKENDS),
    profile=st.sampled_from(_ALL_PROFILES),
    folder_id=st.text(min_size=1, max_size=50, alphabet=st.characters(
        whitelist_categories=("Lu", "Ll", "Nd"), whitelist_characters="-_/"
    )),
)
def test_property30_generated_notebook_valid_with_required_cells(
    backend: RemoteBackend,
    profile: HardwareProfile,
    folder_id: str,
):
    """**Validates: Requirements 10.2, 10.3**

    Property 30: For any TrainingConfig and RemoteBackend, generate_notebook returns
    a valid nbformat.NotebookNode with all required cells present.
    """
    config = _make_config(profile)
    nb = generate_notebook(config, backend, folder_id)

    # Must be a valid notebook
    nbformat.validate(nb)

    sources = _all_cell_sources(nb)

    if backend == RemoteBackend.COLAB:
        required = _COLAB_REQUIRED_KEYWORDS
    else:
        required = _KAGGLE_REQUIRED_KEYWORDS

    for keyword in required:
        assert keyword in sources, (
            f"backend={backend}, profile={profile}: "
            f"Missing required cell keyword: '{keyword}'"
        )

    # Dual T4 must have device="0,1"
    if profile == HardwareProfile.KAGGLE_DUAL_T4 and backend == RemoteBackend.KAGGLE:
        assert "0,1" in sources, (
            "KAGGLE_DUAL_T4 + KAGGLE backend must include device=\"0,1\""
        )
