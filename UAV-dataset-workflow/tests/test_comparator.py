"""Tests for comparator — unit tests and property tests 26-29.

# Feature: anti-uav-dataset-workflow, Property 26: Comparison report includes all completed runs
# Feature: anti-uav-dataset-workflow, Property 27: Comparison runs sorted by mAP@0.5:0.95 descending
# Feature: anti-uav-dataset-workflow, Property 28: Comparison report produces both Markdown and CSV
# Feature: anti-uav-dataset-workflow, Property 29: Comparison report includes small_object_map50 and FPR columns
"""
from __future__ import annotations

import csv
import json
import tempfile
from pathlib import Path

from hypothesis import given, settings
from hypothesis import strategies as st

from anti_uav.comparator import compare_runs, highlight_param_diffs, plot_iou_sensitivity


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _make_run_dir(
    tmp: Path,
    run_name: str,
    map50_95: float,
    completed: bool = True,
    map50: float | None = None,
    precision: float = 0.8,
    recall: float = 0.75,
    model_variant: str = "yolo26s",
) -> Path:
    """Write a minimal results.json and return the run directory."""
    run_dir = tmp / run_name
    run_dir.mkdir(parents=True, exist_ok=True)

    if map50 is None:
        map50 = min(map50_95 + 0.05, 1.0)

    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0

    data = {
        "run_id": run_name,
        "model_variant": model_variant,
        "completed": completed,
        "duration_seconds": 10.0,
        "map50": map50 if completed else None,
        "map50_95": map50_95 if completed else None,
        "precision": precision if completed else None,
        "recall": recall if completed else None,
        "f1": f1 if completed else None,
        "per_class_map50": {"Bird": 0.7, "Drone": 0.65, "UAV": 0.6} if completed else {},
        "small_object_map50": {"Bird": 0.5, "Drone": 0.45, "UAV": 0.4} if completed else {},
        "false_positive_rate": 0.1 if completed else None,
        "passed_gate": (map50 >= 0.75) if completed else False,
        "stal_recommendations": [],
        "hardware_profile": "rtx2070",
        "data_yaml": "merged_dataset/data.yaml",
    }
    (run_dir / "results.json").write_text(json.dumps(data, indent=2), encoding="utf-8")
    return run_dir


# ---------------------------------------------------------------------------
# Unit tests
# ---------------------------------------------------------------------------

def test_compare_runs_ranks_by_map50_95():
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        out = base / "comparison"
        r1 = _make_run_dir(base, "run_a", map50_95=0.60)
        r2 = _make_run_dir(base, "run_b", map50_95=0.80)
        r3 = _make_run_dir(base, "run_c", map50_95=0.70)

        report = compare_runs([r1, r2, r3], out)

        map_values = [r.metrics.map50_95 for r in report.runs]
        assert map_values == sorted(map_values, reverse=True), (
            f"Runs not sorted descending: {map_values}"
        )


def test_compare_runs_writes_md_and_csv():
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        out = base / "comparison"
        r1 = _make_run_dir(base, "run_a", map50_95=0.70)

        report = compare_runs([r1], out)

        assert report.output_md.exists(), "Markdown file not created"
        assert report.output_csv.exists(), "CSV file not created"
        assert report.output_md.suffix == ".md"
        assert report.output_csv.suffix == ".csv"


def test_compare_runs_csv_has_required_columns():
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        out = base / "comparison"
        r1 = _make_run_dir(base, "run_a", map50_95=0.70)

        report = compare_runs([r1], out)

        with report.output_csv.open(encoding="utf-8") as f:
            reader = csv.DictReader(f)
            columns = reader.fieldnames or []

        assert "small_object_map50_Bird" in columns
        assert "small_object_map50_Drone" in columns
        assert "small_object_map50_UAV" in columns
        assert "false_positive_rate" in columns


def test_compare_runs_skips_incomplete():
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        out = base / "comparison"
        r1 = _make_run_dir(base, "run_complete", map50_95=0.70, completed=True)
        r2 = _make_run_dir(base, "run_incomplete", map50_95=0.90, completed=False)

        report = compare_runs([r1, r2], out)

        run_ids = [r.run_id for r in report.runs]
        assert "run_complete" in run_ids
        assert "run_incomplete" not in run_ids


def test_compare_runs_best_run_identified():
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        out = base / "comparison"
        r1 = _make_run_dir(base, "run_low", map50_95=0.55)
        r2 = _make_run_dir(base, "run_high", map50_95=0.85)
        r3 = _make_run_dir(base, "run_mid", map50_95=0.70)

        report = compare_runs([r1, r2, r3], out)

        assert report.best_run_id == "run_high", (
            f"Expected best_run_id='run_high', got '{report.best_run_id}'"
        )


def test_plot_iou_sensitivity_creates_file():
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        out = base / "comparison"
        run_dir = _make_run_dir(base, "run_best", map50_95=0.72, map50=0.80)

        result_path = plot_iou_sensitivity(run_dir, out)

        assert result_path.exists(), "iou_sensitivity.png not created"
        assert result_path.name == "iou_sensitivity.png"


def test_highlight_param_diffs_finds_differences():
    runs = [
        {"model_variant": "yolo26s", "batch": 16, "lr0": 0.01},
        {"model_variant": "yolo26m", "batch": 16, "lr0": 0.01},
    ]
    diffs = highlight_param_diffs(runs)

    assert "model_variant" in diffs, "Expected model_variant to be in diffs"
    assert "batch" not in diffs, "batch should not be in diffs (same value)"
    assert diffs["model_variant"] == ["yolo26s", "yolo26m"]


def test_highlight_param_diffs_empty():
    assert highlight_param_diffs([]) == {}


def test_highlight_param_diffs_no_diffs():
    runs = [{"a": 1, "b": 2}, {"a": 1, "b": 2}]
    assert highlight_param_diffs(runs) == {}


# ---------------------------------------------------------------------------
# Property 26: Comparison report includes all completed runs
# Validates: Requirements 9.1, 9.2
# ---------------------------------------------------------------------------

@settings(max_examples=20)
@given(
    n_complete=st.integers(min_value=1, max_value=6),
    n_incomplete=st.integers(min_value=0, max_value=3),
)
def test_property26_all_completed_runs_included(n_complete, n_incomplete):
    """**Validates: Requirements 9.1, 9.2**

    Property 26: ComparisonReport.runs contains exactly the completed runs.
    """
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        out = base / "comparison"

        run_dirs = []
        for i in range(n_complete):
            rd = _make_run_dir(base, f"complete_{i}", map50_95=0.5 + i * 0.05, completed=True)
            run_dirs.append(rd)
        for i in range(n_incomplete):
            rd = _make_run_dir(base, f"incomplete_{i}", map50_95=0.9, completed=False)
            run_dirs.append(rd)

        report = compare_runs(run_dirs, out)

        assert len(report.runs) == n_complete, (
            f"Expected {n_complete} completed runs, got {len(report.runs)}"
        )
        for r in report.runs:
            assert r.completed is True


# ---------------------------------------------------------------------------
# Property 27: Comparison runs sorted by mAP@0.5:0.95 descending
# Validates: Requirements 9.3
# ---------------------------------------------------------------------------

@settings(max_examples=20)
@given(
    map_values=st.lists(
        st.floats(min_value=0.0, max_value=1.0, allow_nan=False),
        min_size=2,
        max_size=6,
    )
)
def test_property27_runs_sorted_descending(map_values):
    """**Validates: Requirements 9.3**

    Property 27: report.runs are sorted by map50_95 descending for any input ordering.
    """
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        out = base / "comparison"

        run_dirs = [
            _make_run_dir(base, f"run_{i}", map50_95=v)
            for i, v in enumerate(map_values)
        ]

        report = compare_runs(run_dirs, out)

        result_maps = [r.metrics.map50_95 for r in report.runs]
        assert result_maps == sorted(result_maps, reverse=True), (
            f"Runs not sorted descending: {result_maps}"
        )


# ---------------------------------------------------------------------------
# Property 28: Comparison report produces both Markdown and CSV
# Validates: Requirements 9.4, 13.5
# ---------------------------------------------------------------------------

@settings(max_examples=20)
@given(n_runs=st.integers(min_value=1, max_value=5))
def test_property28_produces_md_and_csv(n_runs):
    """**Validates: Requirements 9.4, 13.5**

    Property 28: compare_runs always writes both a .md and a .csv file.
    """
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        out = base / "comparison"

        run_dirs = [
            _make_run_dir(base, f"run_{i}", map50_95=0.5 + i * 0.05)
            for i in range(n_runs)
        ]

        report = compare_runs(run_dirs, out)

        assert report.output_md.exists(), "Markdown file missing"
        assert report.output_csv.exists(), "CSV file missing"
        assert report.output_md.suffix == ".md"
        assert report.output_csv.suffix == ".csv"


# ---------------------------------------------------------------------------
# Property 29: Comparison report includes small_object_map50 and FPR columns
# Validates: Requirements 9.5, 13.7
# ---------------------------------------------------------------------------

@settings(max_examples=20)
@given(n_runs=st.integers(min_value=1, max_value=5))
def test_property29_csv_has_small_object_and_fpr_columns(n_runs):
    """**Validates: Requirements 9.5, 13.7**

    Property 29: CSV always contains small_object_map50_* and false_positive_rate columns.
    """
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        out = base / "comparison"

        run_dirs = [
            _make_run_dir(base, f"run_{i}", map50_95=0.5 + i * 0.05)
            for i in range(n_runs)
        ]

        report = compare_runs(run_dirs, out)

        with report.output_csv.open(encoding="utf-8") as f:
            reader = csv.DictReader(f)
            columns = set(reader.fieldnames or [])

        for cls in ["Bird", "Drone", "UAV"]:
            col = f"small_object_map50_{cls}"
            assert col in columns, f"Missing column: {col}"
        assert "false_positive_rate" in columns, "Missing column: false_positive_rate"
