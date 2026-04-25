"""Tests for Run_Documenter — unit tests and property tests 24, 25, 34.

# Feature: anti-uav-dataset-workflow, Property 24: Run documentation contains all required sections
# Feature: anti-uav-dataset-workflow, Property 25: Non-default augmentation deviation is noted
# Feature: anti-uav-dataset-workflow, Property 34: CHANGELOG.md contains entry for every completed run
"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

import yaml
from hypothesis import given, settings
from hypothesis import strategies as st

from anti_uav.documenter import _DEFAULT_AUGMENTATION, append_changelog_entry, generate_run_doc
from anti_uav.models import ValidationMetrics

# ---------------------------------------------------------------------------
# Required section headings
# ---------------------------------------------------------------------------

_REQUIRED_SECTIONS = [
    "## Dataset Used",
    "## Model Variant",
    "## Training Parameters",
    "## Hardware Profile",
    "## Final Metrics",
    "## Training Duration",
    "## Warnings and Anomalies",
    "## Justification",
    "## Validation Summary",
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_run_dir(
    tmp: Path,
    run_name: str = "run_20260101_120000_yolo26s",
    map50: float = 0.8,
    passed_gate: bool = True,
    stal_recommendations: list[str] | None = None,
    augmentation: dict[str, float] | None = None,
) -> Path:
    """Write minimal results.json and train_config.yaml into a run directory."""
    run_dir = tmp / run_name
    run_dir.mkdir(parents=True, exist_ok=True)

    aug = augmentation if augmentation is not None else dict(_DEFAULT_AUGMENTATION)

    results = {
        "run_id": run_name,
        "model_variant": "yolo26s",
        "completed": True,
        "duration_seconds": 3600.0,
        "map50": map50,
        "map50_95": map50 - 0.05,
        "precision": 0.85,
        "recall": 0.80,
        "f1": 0.82,
        "per_class_map50": {"Bird": map50, "Drone": map50, "UAV": map50},
        "small_object_map50": {"Bird": 0.5, "Drone": 0.5, "UAV": 0.5},
        "false_positive_rate": 0.05,
        "passed_gate": passed_gate,
        "stal_recommendations": stal_recommendations or [],
    }
    (run_dir / "results.json").write_text(json.dumps(results), encoding="utf-8")

    config = {
        "model_variant": "yolo26s",
        "imgsz": 640,
        "batch": 16,
        "epochs": 100,
        "optimizer": "MuSGD",
        "lr0": 0.01,
        "weight_decay": 0.0005,
        "amp": True,
        "augmentation": aug,
        "hardware_profile": "rtx2070",
        "data_yaml": "merged_dataset/data.yaml",
    }
    (run_dir / "train_config.yaml").write_text(
        yaml.dump(config, default_flow_style=False), encoding="utf-8"
    )
    return run_dir


def _make_metrics(map50: float = 0.8, passed: bool = True) -> ValidationMetrics:
    return ValidationMetrics(
        map50=map50,
        map50_95=map50 - 0.05,
        precision=0.85,
        recall=0.80,
        f1=0.82,
        per_class_map50={"Bird": map50, "Drone": map50, "UAV": map50},
        small_object_map50={"Bird": 0.5, "Drone": 0.5, "UAV": 0.5},
        false_positive_rate=0.05,
        passed_gate=passed,
        stal_recommendations=[],
    )


# ---------------------------------------------------------------------------
# Unit tests — generate_run_doc
# ---------------------------------------------------------------------------

def test_generate_run_doc_creates_file():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        run_dir = _make_run_dir(root)
        output_dir = root / "documentations"
        out_path = generate_run_doc(run_dir, output_dir)
        assert out_path.exists(), "Expected .md file to be created"
        assert out_path.suffix == ".md"
        assert out_path.name == f"{run_dir.name}.md"


def test_generate_run_doc_has_required_sections():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        run_dir = _make_run_dir(root)
        output_dir = root / "documentations"
        out_path = generate_run_doc(run_dir, output_dir)
        content = out_path.read_text(encoding="utf-8")
        for section in _REQUIRED_SECTIONS:
            assert section in content, f"Missing required section: {section!r}"


def test_generate_run_doc_stal_flag():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        run_dir = _make_run_dir(
            root,
            stal_recommendations=["STAL: Drone small-object mAP is >0.15 below per-class mAP."],
        )
        output_dir = root / "documentations"
        out_path = generate_run_doc(run_dir, output_dir)
        content = out_path.read_text(encoding="utf-8")
        assert "STAL" in content, "Expected STAL mention when stal_recommendations non-empty"


def test_generate_run_doc_augmentation_deviation():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        aug = dict(_DEFAULT_AUGMENTATION)
        aug["mosaic"] = 0.5  # differs from default 1.0
        run_dir = _make_run_dir(root, augmentation=aug)
        output_dir = root / "documentations"
        out_path = generate_run_doc(run_dir, output_dir)
        content = out_path.read_text(encoding="utf-8")
        assert "Augmentation Deviation" in content or "deviation" in content.lower(), (
            "Expected augmentation deviation note when params differ from defaults"
        )
        assert "mosaic" in content


def test_generate_run_doc_pass_gate_pass():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        run_dir = _make_run_dir(root, map50=0.8, passed_gate=True)
        output_dir = root / "documentations"
        out_path = generate_run_doc(run_dir, output_dir)
        content = out_path.read_text(encoding="utf-8")
        assert "PASS" in content, "Expected PASS in doc for passing run"


def test_generate_run_doc_pass_gate_fail():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        run_dir = _make_run_dir(root, map50=0.6, passed_gate=False)
        output_dir = root / "documentations"
        out_path = generate_run_doc(run_dir, output_dir)
        content = out_path.read_text(encoding="utf-8")
        assert "FAIL" in content, "Expected FAIL in doc for failing run"


# ---------------------------------------------------------------------------
# Unit tests — append_changelog_entry
# ---------------------------------------------------------------------------

def test_append_changelog_creates_file():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        metrics = _make_metrics(0.8, True)
        append_changelog_entry(root, "run_20260101_120000_yolo26s", metrics, True)
        assert (root / "CHANGELOG.md").exists(), "CHANGELOG.md should be created"


def test_append_changelog_contains_run_id():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        run_id = "run_20260101_120000_yolo26s"
        metrics = _make_metrics(0.8, True)
        append_changelog_entry(root, run_id, metrics, True)
        content = (root / "CHANGELOG.md").read_text(encoding="utf-8")
        assert run_id in content, "run_id should appear in CHANGELOG.md"


def test_append_changelog_idempotent_header():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        metrics = _make_metrics(0.8, True)
        append_changelog_entry(root, "run_20260101_120000_yolo26s", metrics, True)
        append_changelog_entry(root, "run_20260101_130000_yolo26m", metrics, False)
        content = (root / "CHANGELOG.md").read_text(encoding="utf-8")
        # Header line should appear exactly once
        header_count = content.count("| Run ID |")
        assert header_count == 1, (
            f"CHANGELOG.md header duplicated: found {header_count} occurrences"
        )


# ---------------------------------------------------------------------------
# Property 24: Run documentation contains all required sections
# Validates: Requirements 8.2, 13.6
# ---------------------------------------------------------------------------

_AUG_KEYS = list(_DEFAULT_AUGMENTATION.keys())


@settings(max_examples=20, deadline=None)
@given(
    map50=st.floats(min_value=0.0, max_value=1.0, allow_nan=False),
    passed=st.booleans(),
)
def test_property24_doc_has_required_sections(map50, passed):
    """**Validates: Requirements 8.2, 13.6**

    Property 24: For any valid results.json + train_config.yaml, generated doc contains
    all 9 required section headings.
    """
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        run_dir = _make_run_dir(root, map50=map50, passed_gate=passed)
        output_dir = root / "documentations"
        out_path = generate_run_doc(run_dir, output_dir)
        content = out_path.read_text(encoding="utf-8")
        for section in _REQUIRED_SECTIONS:
            assert section in content, (
                f"Missing section {section!r} (map50={map50:.3f}, passed={passed})"
            )


# ---------------------------------------------------------------------------
# Property 25: Non-default augmentation deviation is noted
# Validates: Requirements 8.4
# ---------------------------------------------------------------------------

@settings(max_examples=20, deadline=None)
@given(
    key=st.sampled_from(_AUG_KEYS),
    delta=st.floats(min_value=0.01, max_value=0.5, allow_nan=False),
)
def test_property25_augmentation_deviation_noted(key, delta):
    """**Validates: Requirements 8.4**

    Property 25: When any augmentation param differs from defaults, doc contains deviation note.
    """
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        aug = dict(_DEFAULT_AUGMENTATION)
        # Clamp to [0, 1] to keep values valid
        aug[key] = max(0.0, min(1.0, _DEFAULT_AUGMENTATION[key] + delta))
        # Ensure it actually differs
        if abs(aug[key] - _DEFAULT_AUGMENTATION[key]) < 1e-9:
            aug[key] = max(0.0, _DEFAULT_AUGMENTATION[key] - 0.01)

        run_dir = _make_run_dir(root, augmentation=aug)
        output_dir = root / "documentations"
        out_path = generate_run_doc(run_dir, output_dir)
        content = out_path.read_text(encoding="utf-8")

        assert "Augmentation Deviation" in content or "deviation" in content.lower(), (
            f"Expected deviation note for key={key!r} (aug={aug[key]}, "
            f"default={_DEFAULT_AUGMENTATION[key]})"
        )
        assert key in content, f"Expected key {key!r} mentioned in deviation section"


# ---------------------------------------------------------------------------
# Property 34: CHANGELOG.md contains entry for every completed run
# Validates: Requirements 14.3
# ---------------------------------------------------------------------------

@settings(max_examples=20, deadline=None)
@given(
    map50=st.floats(min_value=0.0, max_value=1.0, allow_nan=False),
    passed=st.booleans(),
    run_suffix=st.text(
        alphabet=st.characters(whitelist_categories=("Ll", "Lu", "Nd"), whitelist_characters="_"),
        min_size=1,
        max_size=20,
    ),
)
def test_property34_changelog_contains_run_entry(map50, passed, run_suffix):
    """**Validates: Requirements 14.3**

    Property 34: After append_changelog_entry, CHANGELOG.md contains run_id,
    model_variant, map50, and pass/fail status.
    """
    run_id = f"run_20260101_120000_{run_suffix}"
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        metrics = _make_metrics(map50, passed)
        append_changelog_entry(root, run_id, metrics, passed)
        content = (root / "CHANGELOG.md").read_text(encoding="utf-8")

        assert run_id in content, f"run_id {run_id!r} not found in CHANGELOG.md"
        assert f"{map50:.3f}" in content, f"map50 {map50:.3f} not found in CHANGELOG.md"
        pass_str = "PASS" if passed else "FAIL"
        assert pass_str in content, f"{pass_str!r} not found in CHANGELOG.md"
