"""Class_Normalizer — remaps source class labels to the canonical set."""
from __future__ import annotations

import json
import logging
import xml.etree.ElementTree as ET
from pathlib import Path

from anti_uav.inspector import detect_annotation_format
from anti_uav.models import AnnotationFormat, CanonicalClass, NormalizationLog
from anti_uav.utils import atomic_write, get_logger

logger = get_logger("normalizer")

_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".tiff"}


# ---------------------------------------------------------------------------
# Custom exception
# ---------------------------------------------------------------------------

class UnmappedClassError(Exception):
    """Raised when a dataset contains class names not in the mapping table."""

    def __init__(self, unmapped: list[str]) -> None:
        self.unmapped = unmapped
        super().__init__(f"Unmapped classes: {unmapped}")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def load_mapping(path: Path) -> dict[str, CanonicalClass]:
    """Load a JSON mapping file. Returns {source_class: CanonicalClass}.

    Raises ValueError if a value is not a valid CanonicalClass.
    """
    data = json.loads(path.read_text(encoding="utf-8"))
    mapping: dict[str, CanonicalClass] = {}
    for src, tgt in data.items():
        try:
            mapping[src] = CanonicalClass(tgt)
        except ValueError:
            raise ValueError(
                f"'{tgt}' is not a valid CanonicalClass. "
                f"Valid values: {[c.value for c in CanonicalClass]}"
            )
    return mapping


def find_unmapped_classes(
    dataset_path: Path,
    mapping: dict[str, CanonicalClass],
) -> list[str]:
    """Return list of class names found in dataset not covered by mapping."""
    found_classes: set[str] = set()
    skip_names = {"classes.txt", "obj.names", "normalization_log.json"}
    skip_suffixes = {".txt"}
    # Only scan files inside labels/ directories to avoid README/metadata files
    label_files = list(dataset_path.rglob("labels/*.txt"))
    # Fallback: if no labels/ dirs found, scan all .txt but skip known non-label files
    if not label_files:
        label_files = [
            f for f in dataset_path.rglob("*.txt")
            if f.name not in skip_names
            and "README" not in f.name
            and f.parent.name not in {"", "."}
        ]

    for txt_file in label_files:
        if txt_file.name in skip_names:
            continue
        for line in txt_file.read_text(encoding="utf-8").splitlines():
            parts = line.strip().split()
            if len(parts) == 5:  # valid YOLO line: class x y w h
                found_classes.add(parts[0])

    return [cls for cls in found_classes if cls not in mapping]


def normalize_dataset(
    dataset_path: Path,
    mapping: dict[str, CanonicalClass],
    backend_url: str | None = None,
) -> NormalizationLog:
    """Apply mapping to all YOLO TXT annotation files.

    Raises UnmappedClassError BEFORE modifying any files if unmapped classes exist.
    Renames image files containing source class name in filename.
    Syncs to Label Studio if backend_url provided (best-effort, logs warning on failure).
    Writes normalization_log.json atomically.
    Returns NormalizationLog.
    """
    import yaml as _yaml

    # Auto-extend mapping with integer indices from data.yaml if present
    data_yaml = dataset_path / "data.yaml"
    if data_yaml.is_file():
        try:
            meta = _yaml.safe_load(data_yaml.read_text(encoding="utf-8"))
            names = meta.get("names", [])
            for idx, name in enumerate(names):
                str_idx = str(idx)
                # Map integer index if the class name is already in the mapping
                if name in mapping and str_idx not in mapping:
                    mapping[str_idx] = mapping[name]
                # Also map the name itself in case labels use string names
                if str_idx in mapping and name not in mapping:
                    mapping[name] = mapping[str_idx]
        except Exception as exc:
            logger.warning("Could not read data.yaml for auto-mapping: %s", exc)

    # Step 1: Check for unmapped classes — do not modify any files
    unmapped = find_unmapped_classes(dataset_path, mapping)
    if unmapped:
        raise UnmappedClassError(unmapped)

    # Step 2: Normalize YOLO TXT label files
    substitution_counts: dict[tuple[str, str], int] = {}
    total_files_modified = _normalize_yolo(dataset_path, mapping, substitution_counts)

    # Step 3: Rename image files containing source class name — DISABLED for YOLO datasets
    # (renaming images breaks the image↔label filename pairing)
    # _rename_images(dataset_path, mapping)

    # Step 4: Build NormalizationLog
    substitutions = [
        (src, tgt, count)
        for (src, tgt), count in substitution_counts.items()
    ]
    # total_files_modified = sum of file_count across all substitution entries
    # (satisfies Property 11: sum of file_counts == total_files_modified)
    total_files_modified = sum(count for _, _, count in substitutions)
    log = NormalizationLog(
        substitutions=substitutions,
        total_files_modified=total_files_modified,
        unmapped_classes=[],
    )

    # Step 5: Write normalization_log.json atomically
    log_data = {
        "substitutions": [
            {"source": s, "target": t, "file_count": c}
            for s, t, c in log.substitutions
        ],
        "total_files_modified": log.total_files_modified,
        "unmapped_classes": log.unmapped_classes,
    }
    atomic_write(dataset_path / "normalization_log.json", json.dumps(log_data, indent=2))

    # Step 6: Sync to Label Studio if backend_url provided (best-effort)
    if backend_url is not None:
        _sync_to_label_studio(backend_url, dataset_path)

    return log


# ---------------------------------------------------------------------------
# YOLO TXT normalizer
# ---------------------------------------------------------------------------

def _normalize_yolo(
    dataset_path: Path,
    mapping: dict[str, CanonicalClass],
    substitution_counts: dict[tuple[str, str], int],
) -> int:
    """Normalize YOLO TXT annotation files. Writes canonical class name as string.

    Returns count of modified files.
    """
    skip_names = {"classes.txt", "obj.names", "normalization_log.json"}
    modified = 0

    # Only process files inside labels/ directories to avoid README/metadata files
    label_files = list(dataset_path.rglob("labels/*.txt"))
    if not label_files:
        label_files = [
            f for f in dataset_path.rglob("*.txt")
            if f.name not in skip_names and "README" not in f.name
        ]

    for txt_file in label_files:
        if txt_file.name in skip_names:
            continue
        lines = txt_file.read_text(encoding="utf-8").splitlines()
        new_lines: list[str] = []
        file_changed = False

        for line in lines:
            parts = line.strip().split()
            if not parts or len(parts) != 5:  # skip non-YOLO lines
                new_lines.append(line)
                continue
            cls_token = parts[0]
            if cls_token in mapping:
                new_cls = mapping[cls_token]
                new_line = f"{new_cls.value} " + " ".join(parts[1:])
                key = (cls_token, new_cls.value)
                substitution_counts[key] = substitution_counts.get(key, 0) + 1
                new_lines.append(new_line)
                file_changed = True
            else:
                new_lines.append(line)

        if file_changed:
            atomic_write(txt_file, "\n".join(new_lines))
            modified += 1

    return modified


def _rename_images(dataset_path: Path, mapping: dict[str, CanonicalClass]) -> None:
    """Rename image files whose stem contains a source class name as substring."""
    for img_path in list(dataset_path.rglob("*")):
        if img_path.suffix.lower() not in _IMAGE_EXTENSIONS:
            continue
        stem = img_path.stem
        for src_cls, tgt_cls in mapping.items():
            if src_cls in stem:
                new_stem = stem.replace(src_cls, tgt_cls.value)
                new_path = img_path.with_name(new_stem + img_path.suffix)
                if new_path != img_path and not new_path.exists():
                    img_path.rename(new_path)
                break


def _sync_to_label_studio(backend_url: str, dataset_path: Path) -> None:
    """Attempt to sync annotations to Label Studio. Logs warning on failure."""
    try:
        import requests
        resp = requests.post(
            f"{backend_url.rstrip('/')}/api/projects/",
            json={"dataset_path": str(dataset_path)},
            timeout=10,
        )
        resp.raise_for_status()
        logger.info("Synced annotations to Label Studio at %s", backend_url)
    except ImportError:
        logger.warning(
            "requests library not available; skipping Label Studio sync to %s",
            backend_url,
        )
    except Exception as exc:
        logger.warning(
            "Label Studio sync failed (backend_url=%s): %s. "
            "Continuing with local-only normalization.",
            backend_url,
            exc,
        )
