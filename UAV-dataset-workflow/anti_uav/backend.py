"""Annotation_Backend — manages a local Label Studio instance."""
from __future__ import annotations

import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

try:
    import requests
except ImportError:
    requests = None  # type: ignore[assignment]

from anti_uav.models import CanonicalClass
from anti_uav.utils import get_logger

logger = get_logger("backend")

_CANONICAL_CLASSES = [c.value for c in CanonicalClass]

# Label config XML with exactly 3 <Label> elements: Bird, Drone, UAV
_LABEL_CONFIG_XML = (
    "<View>\n"
    '  <Image name="image" value="$image"/>\n'
    '  <RectangleLabels name="label" toName="image">\n'
    '    <Label value="Bird"/>\n'
    '    <Label value="Drone"/>\n'
    '    <Label value="UAV"/>\n'
    "  </RectangleLabels>\n"
    "</View>"
)


# ---------------------------------------------------------------------------
# Process management
# ---------------------------------------------------------------------------

def start_label_studio(port: int = 8080) -> subprocess.Popen:
    """Start Label Studio as a subprocess on the given port. Returns the process."""
    proc = subprocess.Popen(
        ["label-studio", "start", "--port", str(port), "--no-browser"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    logger.info("Started Label Studio on port %d (pid=%d)", port, proc.pid)
    return proc


def stop_label_studio(proc: subprocess.Popen) -> None:
    """Terminate the Label Studio process."""
    if proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
    logger.info("Label Studio process stopped")


def is_running(url: str) -> bool:
    """Check if Label Studio is running at url by making a GET request to /health."""
    try:
        if requests is None:
            raise ImportError("requests is not installed")
        resp = requests.get(f"{url.rstrip('/')}/health", timeout=3)
        return resp.status_code == 200
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Project management
# ---------------------------------------------------------------------------

def create_project(client: Any, name: str) -> Any:
    """Create a Label Studio project pre-configured with Bird/Drone/UAV labels only.
    Returns the project object."""
    try:
        project = client.projects.create(
            title=name,
            label_config=_LABEL_CONFIG_XML,
        )
    except ImportError as exc:
        raise ImportError(
            "label-studio-sdk is required to create projects. "
            "Install it with: pip install label-studio-sdk"
        ) from exc
    logger.info("Created Label Studio project '%s'", name)
    return project


def import_dataset(project: Any, dataset_path: Path) -> None:
    """Import images from dataset_path into the Label Studio project.
    Preserves original image filenames."""
    _image_exts = {".jpg", ".jpeg", ".png", ".bmp", ".tiff"}
    image_files = [
        p for p in dataset_path.rglob("*")
        if p.suffix.lower() in _image_exts
    ]
    if not image_files:
        logger.warning("No images found in %s", dataset_path)
        return

    try:
        project.import_tasks([{"image": str(p)} for p in image_files])
    except ImportError as exc:
        raise ImportError(
            "label-studio-sdk is required to import tasks. "
            "Install it with: pip install label-studio-sdk"
        ) from exc
    logger.info("Imported %d images into project", len(image_files))


def export_yolo(project: Any, output_path: Path) -> None:
    """Export annotations from project in YOLO TXT format to output_path."""
    output_path.mkdir(parents=True, exist_ok=True)
    try:
        data = project.export_tasks(export_type="YOLO")
    except ImportError as exc:
        raise ImportError(
            "label-studio-sdk is required to export tasks. "
            "Install it with: pip install label-studio-sdk"
        ) from exc

    if isinstance(data, (bytes, bytearray)):
        (output_path / "annotations.zip").write_bytes(data)
        return

    # data is a list of task dicts
    for task in data:
        task_data = task.get("data", {})
        # Prefer explicit filename, fall back to image path stem
        filename = task_data.get("filename") or task_data.get("image", "unknown.jpg")
        stem = Path(filename).stem
        annotations = task.get("annotations", [])
        lines: list[str] = []
        for ann in annotations:
            for result in ann.get("result", []):
                value = result.get("value", {})
                labels = value.get("rectanglelabels", [])
                if not labels:
                    continue
                label = labels[0]
                cls_idx = (
                    _CANONICAL_CLASSES.index(label)
                    if label in _CANONICAL_CLASSES
                    else 0
                )
                x = value.get("x", 0) / 100
                y = value.get("y", 0) / 100
                w = value.get("width", 0) / 100
                h = value.get("height", 0) / 100
                x_center = x + w / 2
                y_center = y + h / 2
                lines.append(
                    f"{cls_idx} {x_center:.6f} {y_center:.6f} {w:.6f} {h:.6f}"
                )
        (output_path / f"{stem}.txt").write_text("\n".join(lines), encoding="utf-8")

    logger.info("Exported %d tasks to %s", len(data), output_path)


# ---------------------------------------------------------------------------
# Label config validation helper
# ---------------------------------------------------------------------------

def get_label_count(label_config: str) -> int:
    """Return the number of <Label> elements in a label config XML string."""
    try:
        root = ET.fromstring(label_config)
        return len(root.findall(".//Label"))
    except ET.ParseError:
        return 0
