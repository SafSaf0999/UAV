"""Colab_Bridge — remote training offload to Google Colab or Kaggle.

Supports both backends via RemoteBackend enum. All Google Drive and Kaggle
API imports are wrapped in try/except ImportError so the module loads even
when optional dependencies are absent.
"""
from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path

import nbformat
import nbformat.v4

from anti_uav.models import (
    AuthMethod,
    HardwareProfile,
    KernelStatus,
    RemoteBackend,
    TrainingConfig,
    UploadManifest,
)

try:
    from googleapiclient.discovery import build as _gdrive_build
    from googleapiclient.http import MediaFileUpload as _MediaFileUpload
    from googleapiclient.http import MediaIoBaseDownload as _MediaIoBaseDownload
except ImportError:
    _gdrive_build = None  # type: ignore[assignment]
    _MediaFileUpload = None  # type: ignore[assignment]
    _MediaIoBaseDownload = None  # type: ignore[assignment]

try:
    from google.oauth2 import service_account as _service_account
    from google_auth_oauthlib.flow import InstalledAppFlow as _InstalledAppFlow
except ImportError:
    _service_account = None  # type: ignore[assignment]
    _InstalledAppFlow = None  # type: ignore[assignment]

try:
    import kaggle as _kaggle_module  # noqa: F401 — imported for side-effects (auth)
except ImportError:
    _kaggle_module = None  # type: ignore[assignment]


class AuthenticationError(Exception):
    """Raised when authentication with Google Drive or Kaggle fails."""


# ---------------------------------------------------------------------------
# Notebook generation
# ---------------------------------------------------------------------------

def generate_notebook(
    config: TrainingConfig,
    backend: RemoteBackend,
    remote_folder_id: str,
) -> "nbformat.NotebookNode":
    """Generate a .ipynb notebook for the selected backend.

    Colab: cells for Drive mounting, dep install, dataset extraction,
           training, result archiving.
    Kaggle: cells for dataset mounting, dep install, training, output saving.
    Kaggle with KAGGLE_DUAL_T4: sets device="0,1" in training cell.

    Returns a valid nbformat.NotebookNode (passes nbformat.validate).
    """
    nb = nbformat.v4.new_notebook()

    if backend == RemoteBackend.COLAB:
        nb.cells = _colab_cells(config, remote_folder_id)
    else:
        nb.cells = _kaggle_cells(config, remote_folder_id)

    return nb


def _colab_cells(config: TrainingConfig, folder_id: str) -> list:
    """Return the five required cells for a Colab notebook."""
    mount_cell = nbformat.v4.new_code_cell(
        "# Mount Google Drive\n"
        "from google.colab import drive\n"
        "drive.mount('/content/drive')\n"
        f"DRIVE_FOLDER_ID = '{folder_id}'\n"
    )

    install_cell = nbformat.v4.new_code_cell(
        "# Install dependencies\n"
        "import subprocess\n"
        f"subprocess.run(['pip', 'install', '-q', 'ultralytics>={8}'], check=True)\n"
    )

    extract_cell = nbformat.v4.new_code_cell(
        "# Extract dataset\n"
        "import zipfile, pathlib\n"
        "dataset_zip = '/content/drive/MyDrive/dataset.zip'\n"
        "extract_dir = '/content/dataset'\n"
        "with zipfile.ZipFile(dataset_zip) as zf:\n"
        "    zf.extractall(extract_dir)\n"
    )

    device_arg = '"0,1"' if config.hardware_profile == HardwareProfile.KAGGLE_DUAL_T4 else '"0"'
    train_cell = nbformat.v4.new_code_cell(
        "# Run training\n"
        "from ultralytics import YOLO\n"
        f"model = YOLO('{config.model_variant}.pt')\n"
        "model.train(\n"
        "    data='/content/dataset/data.yaml',\n"
        f"    imgsz={config.imgsz},\n"
        f"    batch={config.batch},\n"
        f"    epochs={config.epochs},\n"
        f"    device={device_arg},\n"
        ")\n"
    )

    archive_cell = nbformat.v4.new_code_cell(
        "# Archive results\n"
        "import shutil, pathlib\n"
        "results_dir = pathlib.Path('runs')\n"
        "archive_path = '/content/drive/MyDrive/training_results.zip'\n"
        "shutil.make_archive('/content/drive/MyDrive/training_results', 'zip', results_dir)\n"
        "print(f'Results archived to {archive_path}')\n"
    )

    return [mount_cell, install_cell, extract_cell, train_cell, archive_cell]


def _kaggle_cells(config: TrainingConfig, dataset_slug: str) -> list:
    """Return the four required cells for a Kaggle notebook."""
    mount_cell = nbformat.v4.new_code_cell(
        "# Mount dataset\n"
        "import os\n"
        f"DATASET_SLUG = '{dataset_slug}'\n"
        "dataset_path = f'/kaggle/input/{DATASET_SLUG.split(\"/\")[-1]}'\n"
        "print(f'Dataset available at: {dataset_path}')\n"
    )

    install_cell = nbformat.v4.new_code_cell(
        "# Install dependencies\n"
        "import subprocess\n"
        "subprocess.run(['pip', 'install', '-q', 'ultralytics'], check=True)\n"
    )

    dual_t4 = config.hardware_profile == HardwareProfile.KAGGLE_DUAL_T4
    device_line = '    device="0,1",\n' if dual_t4 else '    device="0",\n'
    train_cell = nbformat.v4.new_code_cell(
        "# Run training\n"
        "from ultralytics import YOLO\n"
        f"model = YOLO('{config.model_variant}.pt')\n"
        "model.train(\n"
        f"    data=dataset_path + '/data.yaml',\n"
        f"    imgsz={config.imgsz},\n"
        f"    batch={config.batch},\n"
        f"    epochs={config.epochs},\n"
        + device_line +
        ")\n"
    )

    save_cell = nbformat.v4.new_code_cell(
        "# Save outputs\n"
        "import shutil, pathlib\n"
        "output_dir = pathlib.Path('/kaggle/working')\n"
        "runs_dir = pathlib.Path('runs')\n"
        "if runs_dir.exists():\n"
        "    shutil.copytree(runs_dir, output_dir / 'runs', dirs_exist_ok=True)\n"
        "print('Outputs saved to /kaggle/working')\n"
    )

    return [mount_cell, install_cell, train_cell, save_cell]


# ---------------------------------------------------------------------------
# Google Drive / Colab backend
# ---------------------------------------------------------------------------

_DRIVE_SCOPES = ["https://www.googleapis.com/auth/drive"]


def authenticate_google(method: AuthMethod, credentials_path: Path | None = None):
    """Authenticate with Google Drive. Returns a Drive service object.

    OAuth2 device flow or service account key file.
    Raises AuthenticationError with instructions on failure.
    """
    if _gdrive_build is None or _service_account is None or _InstalledAppFlow is None:
        raise AuthenticationError(
            "Google API libraries not installed. "
            "Run: pip install google-api-python-client google-auth-oauthlib"
        )

    try:
        if method == AuthMethod.SERVICE_ACCOUNT:
            if credentials_path is None:
                raise AuthenticationError(
                    "credentials_path is required for SERVICE_ACCOUNT authentication."
                )
            creds = _service_account.Credentials.from_service_account_file(
                str(credentials_path), scopes=_DRIVE_SCOPES
            )
        else:
            # OAuth2 device flow
            if credentials_path is None:
                raise AuthenticationError(
                    "credentials_path (OAuth2 client secrets JSON) is required for OAUTH2 authentication."
                )
            flow = _InstalledAppFlow.from_client_secrets_file(
                str(credentials_path), scopes=_DRIVE_SCOPES
            )
            creds = flow.run_local_server(port=0)

        service = _gdrive_build("drive", "v3", credentials=creds)
        return service
    except AuthenticationError:
        raise
    except Exception as exc:
        raise AuthenticationError(
            f"Google Drive authentication failed: {exc}\n"
            "For OAuth2: provide a valid client_secrets.json downloaded from Google Cloud Console.\n"
            "For service account: provide a valid service_account_key.json."
        ) from exc


def upload_to_drive(service, local_path: Path, drive_folder_id: str) -> UploadManifest:
    """Upload local_path to Google Drive folder.

    Returns UploadManifest with uploaded (local_path -> file_id) and failed (list of paths).
    """
    manifest = UploadManifest(uploaded={}, failed=[])

    files_to_upload: list[Path] = []
    if local_path.is_file():
        files_to_upload = [local_path]
    elif local_path.is_dir():
        files_to_upload = [p for p in local_path.rglob("*") if p.is_file()]
    else:
        manifest.failed.append(str(local_path))
        return manifest

    for file_path in files_to_upload:
        try:
            file_metadata = {
                "name": file_path.name,
                "parents": [drive_folder_id],
            }
            media = _MediaFileUpload(str(file_path), resumable=True)
            result = (
                service.files()
                .create(body=file_metadata, media_body=media, fields="id")
                .execute()
            )
            manifest.uploaded[str(file_path)] = result["id"]
        except Exception:
            manifest.failed.append(str(file_path))

    return manifest


def download_from_drive(service, drive_folder_id: str, local_path: Path) -> None:
    """Download all files from a Google Drive folder to local_path."""
    import io

    local_path.mkdir(parents=True, exist_ok=True)

    results = (
        service.files()
        .list(
            q=f"'{drive_folder_id}' in parents and trashed=false",
            fields="files(id, name)",
        )
        .execute()
    )
    files = results.get("files", [])

    for file_info in files:
        file_id = file_info["id"]
        file_name = file_info["name"]
        dest = local_path / file_name

        request = service.files().get_media(fileId=file_id)
        buf = io.BytesIO()
        downloader = _MediaIoBaseDownload(buf, request)
        done = False
        while not done:
            _, done = downloader.next_chunk()
        dest.write_bytes(buf.getvalue())


def retry_failed_uploads(service, manifest: UploadManifest) -> None:
    """Re-upload only files in manifest.failed."""
    still_failed: list[str] = []

    for path_str in list(manifest.failed):
        file_path = Path(path_str)
        # Determine parent folder from already-uploaded entries or use root
        # We need a folder id — derive from the first uploaded entry's parent or skip
        try:
            file_metadata = {"name": file_path.name}
            media = _MediaFileUpload(str(file_path), resumable=True)
            result = (
                service.files()
                .create(body=file_metadata, media_body=media, fields="id")
                .execute()
            )
            manifest.uploaded[path_str] = result["id"]
        except Exception:
            still_failed.append(path_str)

    manifest.failed = still_failed


# ---------------------------------------------------------------------------
# Kaggle backend
# ---------------------------------------------------------------------------

def authenticate_kaggle(credentials_path: Path) -> None:
    """Load kaggle.json API token. Raises AuthenticationError on failure."""
    if not credentials_path.exists():
        raise AuthenticationError(
            f"Kaggle credentials file not found: {credentials_path}\n"
            "Download kaggle.json from https://www.kaggle.com/settings/account "
            "and place it at the specified path."
        )

    try:
        data = json.loads(credentials_path.read_text(encoding="utf-8"))
        if "username" not in data or "key" not in data:
            raise AuthenticationError(
                f"Invalid kaggle.json: missing 'username' or 'key' fields in {credentials_path}"
            )
        # Set environment variables so the kaggle CLI picks them up
        import os
        os.environ["KAGGLE_USERNAME"] = data["username"]
        os.environ["KAGGLE_KEY"] = data["key"]
    except AuthenticationError:
        raise
    except Exception as exc:
        raise AuthenticationError(
            f"Failed to load Kaggle credentials from {credentials_path}: {exc}"
        ) from exc


def upload_dataset_to_kaggle(local_path: Path, dataset_slug: str) -> None:
    """Push dataset via kaggle datasets push subprocess call."""
    subprocess.run(
        ["kaggle", "datasets", "push", "-p", str(local_path), "--slug", dataset_slug],
        check=True,
    )


def push_kaggle_kernel(notebook, kernel_slug: str, dataset_slug: str) -> None:
    """Push and trigger kernel via kaggle kernels push subprocess call."""
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        nb_path = tmp_dir / "notebook.ipynb"
        nb_path.write_text(nbformat.writes(notebook), encoding="utf-8")

        kernel_meta = {
            "id": kernel_slug,
            "title": kernel_slug.split("/")[-1],
            "code_file": "notebook.ipynb",
            "language": "python",
            "kernel_type": "notebook",
            "is_private": True,
            "enable_gpu": True,
            "enable_internet": True,
            "dataset_sources": [dataset_slug],
            "competition_sources": [],
            "kernel_sources": [],
        }
        meta_path = tmp_dir / "kernel-metadata.json"
        meta_path.write_text(json.dumps(kernel_meta, indent=2), encoding="utf-8")

        subprocess.run(
            ["kaggle", "kernels", "push", "-p", str(tmp_dir)],
            check=True,
        )


def poll_kaggle_kernel(
    kernel_slug: str, poll_interval: int = 30, timeout: int = 32400
) -> "KernelStatus":
    """Poll kaggle kernels status until complete, failed, or timeout.

    Returns KernelStatus enum value.
    """
    elapsed = 0

    while elapsed < timeout:
        result = subprocess.run(
            ["kaggle", "kernels", "status", kernel_slug],
            capture_output=True,
            text=True,
            check=False,
        )
        output = (result.stdout + result.stderr).lower()

        if "complete" in output:
            return KernelStatus.COMPLETE
        if "error" in output:
            return KernelStatus.ERROR
        if "running" in output:
            pass  # still running
        elif "queued" in output:
            pass  # still queued

        time.sleep(poll_interval)
        elapsed += poll_interval

    # Timeout reached
    return KernelStatus.ERROR


def download_kaggle_output(kernel_slug: str, local_path: Path) -> None:
    """Download kernel outputs via kaggle kernels output subprocess call."""
    local_path.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["kaggle", "kernels", "output", kernel_slug, "-p", str(local_path)],
        check=True,
    )
