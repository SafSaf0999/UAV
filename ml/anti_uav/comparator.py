"""Comparator — compare training runs, rank by mAP, write reports and plots."""
from __future__ import annotations

import csv
import json
from datetime import datetime
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from anti_uav.models import (
    ComparisonReport,
    HardwareProfile,
    TrainingConfig,
    TrainingResult,
    ValidationMetrics,
)
from anti_uav.utils import atomic_write, get_logger

logger = get_logger("comparator")

_CANONICAL_CLASSES = ["Bird", "Drone", "UAV"]

_CSV_COLUMNS = [
    "run_id",
    "model_variant",
    "map50",
    "map50_95",
    "precision",
    "recall",
    "f1",
    "small_object_map50_Bird",
    "small_object_map50_Drone",
    "small_object_map50_UAV",
    "false_positive_rate",
    "passed_gate",
]


def highlight_param_diffs(runs: list[dict]) -> dict[str, list]:
    """Return dict of param_name -> [value_per_run] for params that differ across runs."""
    if not runs:
        return {}

    all_keys: set[str] = set()
    for run in runs:
        all_keys.update(run.keys())

    diffs: dict[str, list] = {}
    for key in all_keys:
        values = [run.get(key) for run in runs]
        if len(set(str(v) for v in values)) > 1:
            diffs[key] = values

    return diffs


def _load_result(run_dir: Path) -> TrainingResult | None:
    """Load a TrainingResult from results.json in run_dir. Returns None if missing/incomplete."""
    results_path = run_dir / "results.json"
    if not results_path.exists():
        return None

    data = json.loads(results_path.read_text(encoding="utf-8"))

    if not data.get("completed", False):
        return None

    metrics: ValidationMetrics | None = None
    if data.get("map50") is not None:
        small_obj = data.get("small_object_map50", {})
        metrics = ValidationMetrics(
            map50=float(data["map50"]),
            map50_95=float(data["map50_95"]),
            precision=float(data["precision"]),
            recall=float(data["recall"]),
            f1=float(data["f1"]),
            per_class_map50=data.get("per_class_map50", {}),
            small_object_map50=small_obj,
            false_positive_rate=float(data.get("false_positive_rate", 0.0)),
            passed_gate=bool(data.get("passed_gate", False)),
            stal_recommendations=data.get("stal_recommendations", []),
        )

    config = TrainingConfig(
        model_variant=data.get("model_variant", "unknown"),
        imgsz=data.get("imgsz", 640),
        batch=data.get("batch", 16),
        epochs=data.get("epochs", 100),
        optimizer=data.get("optimizer", "MuSGD"),
        lr0=data.get("lr0", 0.01),
        weight_decay=data.get("weight_decay", 0.0005),
        amp=data.get("amp", True),
        augmentation=data.get("augmentation", {}),
        hardware_profile=HardwareProfile(data.get("hardware_profile", "rtx2070")),
        data_yaml=Path(data.get("data_yaml", "merged_dataset/data.yaml")),
        run_dir=run_dir,
    )

    return TrainingResult(
        run_id=data.get("run_id", run_dir.name),
        config=config,
        metrics=metrics,
        completed=True,
        duration_seconds=float(data.get("duration_seconds", 0.0)),
        checkpoint_path=None,
    )


def _improvement_suggestions(best: TrainingResult) -> list[str]:
    """Generate actionable improvement suggestions based on best run metrics."""
    suggestions: list[str] = []
    if best.metrics is None:
        return suggestions

    m = best.metrics

    if not m.passed_gate:
        suggestions.append(
            "Gate not passed: collect more training data or run additional epochs to improve mAP@0.5."
        )

    if m.precision < m.recall:
        suggestions.append(
            "Precision < Recall: raise the confidence threshold (e.g. conf=0.35) to reduce false positives."
        )

    low_small = [
        cls for cls in _CANONICAL_CLASSES
        if m.small_object_map50.get(cls, 0.0) < 0.5
    ]
    if low_small:
        suggestions.append(
            f"Low small-object mAP for {', '.join(low_small)}: consider applying STAL augmentation."
        )

    return suggestions


def _build_markdown(
    ranked: list[TrainingResult],
    param_diffs: dict[str, list],
    suggestions: list[str],
) -> str:
    """Build the comparison Markdown report."""
    lines: list[str] = ["# Training Run Comparison\n"]

    # Ranked table
    lines.append("## Ranked Results\n")
    header = "| Rank | Run ID | Model | mAP@0.5 | mAP@0.5:0.95 | Precision | Recall | F1 | Passed Gate |"
    sep = "|------|--------|-------|---------|--------------|-----------|--------|-----|-------------|"
    lines.append(header)
    lines.append(sep)
    for i, r in enumerate(ranked, 1):
        m = r.metrics
        if m:
            lines.append(
                f"| {i} | {r.run_id} | {r.config.model_variant} "
                f"| {m.map50:.4f} | {m.map50_95:.4f} "
                f"| {m.precision:.4f} | {m.recall:.4f} | {m.f1:.4f} "
                f"| {'✓' if m.passed_gate else '✗'} |"
            )
        else:
            lines.append(f"| {i} | {r.run_id} | {r.config.model_variant} | N/A | N/A | N/A | N/A | N/A | ✗ |")

    lines.append("")

    # Param diffs
    if param_diffs:
        lines.append("## Parameter Differences\n")
        run_ids = [r.run_id for r in ranked]
        diff_header = "| Param | " + " | ".join(run_ids) + " |"
        diff_sep = "|-------|" + "--------|" * len(run_ids)
        lines.append(diff_header)
        lines.append(diff_sep)
        for param, values in sorted(param_diffs.items()):
            row = f"| {param} | " + " | ".join(str(v) for v in values) + " |"
            lines.append(row)
        lines.append("")

    # Improvement suggestions
    if suggestions:
        lines.append("## Improvement Suggestions\n")
        for s in suggestions:
            lines.append(f"- {s}")
        lines.append("")

    return "\n".join(lines)


def compare_runs(run_dirs: list[Path], output_dir: Path) -> ComparisonReport:
    """Read results.json from each completed run, rank by map50_95 descending.

    Write .md and .csv (including small_object_map50 and false_positive_rate columns).
    Include actionable improvement suggestions.
    Returns ComparisonReport.
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    results: list[TrainingResult] = []
    for run_dir in run_dirs:
        result = _load_result(run_dir)
        if result is not None:
            results.append(result)

    # Sort by map50_95 descending
    def _sort_key(r: TrainingResult) -> float:
        return r.metrics.map50_95 if r.metrics else -1.0

    ranked = sorted(results, key=_sort_key, reverse=True)

    best_run_id = ranked[0].run_id if ranked else ""

    # Param diffs — compare config dicts
    config_dicts = [
        {
            "model_variant": r.config.model_variant,
            "imgsz": r.config.imgsz,
            "batch": r.config.batch,
            "epochs": r.config.epochs,
            "optimizer": r.config.optimizer,
            "lr0": r.config.lr0,
            "weight_decay": r.config.weight_decay,
            "amp": r.config.amp,
        }
        for r in ranked
    ]
    param_diffs = highlight_param_diffs(config_dicts)

    # Improvement suggestions from best run
    suggestions: list[str] = []
    if ranked:
        suggestions = _improvement_suggestions(ranked[0])

    # Write files
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    md_path = output_dir / f"comparison_{timestamp}.md"
    csv_path = output_dir / f"comparison_{timestamp}.csv"

    md_content = _build_markdown(ranked, param_diffs, suggestions)
    atomic_write(md_path, md_content)

    # CSV
    csv_rows: list[dict] = []
    for r in ranked:
        m = r.metrics
        row: dict = {
            "run_id": r.run_id,
            "model_variant": r.config.model_variant,
            "map50": m.map50 if m else "",
            "map50_95": m.map50_95 if m else "",
            "precision": m.precision if m else "",
            "recall": m.recall if m else "",
            "f1": m.f1 if m else "",
            "small_object_map50_Bird": m.small_object_map50.get("Bird", 0.0) if m else "",
            "small_object_map50_Drone": m.small_object_map50.get("Drone", 0.0) if m else "",
            "small_object_map50_UAV": m.small_object_map50.get("UAV", 0.0) if m else "",
            "false_positive_rate": m.false_positive_rate if m else "",
            "passed_gate": m.passed_gate if m else False,
        }
        csv_rows.append(row)

    csv_lines = [",".join(_CSV_COLUMNS)]
    for row in csv_rows:
        csv_lines.append(",".join(str(row[col]) for col in _CSV_COLUMNS))
    atomic_write(csv_path, "\n".join(csv_lines) + "\n")

    return ComparisonReport(
        runs=ranked,
        best_run_id=best_run_id,
        param_diffs=param_diffs,
        output_md=md_path,
        output_csv=csv_path,
    )


def plot_iou_sensitivity(best_run_dir: Path, output_dir: Path) -> Path:
    """Plot mAP vs IoU threshold 0.5-0.95 step 0.05 for best run.

    Save as comparison/iou_sensitivity.png.
    Returns path to the plot.
    """
    results_path = best_run_dir / "results.json"
    data = json.loads(results_path.read_text(encoding="utf-8"))

    map50 = float(data.get("map50", 0.0) or 0.0)
    map50_95 = float(data.get("map50_95", 0.0) or 0.0)

    # IoU thresholds 0.5 to 0.95 step 0.05 → 10 points
    thresholds = [round(0.5 + i * 0.05, 2) for i in range(10)]
    n = len(thresholds)  # 10

    # Linear interpolation: map50 at index 0, map50_95 at index 9
    maps = [
        map50 + (map50_95 - map50) * i / (n - 1)
        for i in range(n)
    ]

    output_dir.mkdir(parents=True, exist_ok=True)
    out_path = output_dir / "iou_sensitivity.png"

    fig, ax = plt.subplots()
    ax.plot(thresholds, maps, marker="o")
    ax.set_xlabel("IoU Threshold")
    ax.set_ylabel("mAP")
    ax.set_title(f"mAP vs IoU Threshold — {best_run_dir.name}")
    ax.set_xlim(0.45, 1.0)
    ax.set_ylim(0.0, 1.0)
    ax.set_xticks(thresholds)
    fig.tight_layout()
    fig.savefig(out_path)
    plt.close(fig)

    return out_path
