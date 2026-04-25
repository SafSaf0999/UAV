"""Run_Documenter — generates per-run Markdown documentation and CHANGELOG entries."""
from __future__ import annotations

import json
from pathlib import Path

import yaml

from anti_uav.models import ValidationMetrics
from anti_uav.utils import atomic_write, get_logger

logger = get_logger("documenter")

_DEFAULT_AUGMENTATION: dict[str, float] = {
    "mosaic": 1.0,
    "mixup": 0.15,
    "copy_paste": 0.3,
    "hsv_h": 0.015,
    "hsv_s": 0.7,
    "hsv_v": 0.4,
    "degrees": 10.0,
    "translate": 0.1,
    "scale": 0.5,
    "flipud": 0.1,
    "fliplr": 0.5,
}

_CHANGELOG_HEADER = (
    "| Run ID | Model Variant | mAP@0.5 | Passed |\n"
    "|--------|---------------|---------|--------|\n"
)


def generate_run_doc(run_dir: Path, output_dir: Path) -> Path:
    """Read results.json and train_config.yaml from run_dir, write Markdown doc to output_dir.

    Required sections (must appear as ## headings):
    - Dataset Used
    - Model Variant
    - Training Parameters
    - Hardware Profile
    - Final Metrics
    - Training Duration
    - Warnings and Anomalies
    - Justification
    - Validation Summary

    Also include:
    - STAL flag section if stal_recommendations non-empty
    - Augmentation Deviation section if any augmentation param differs from defaults
    - Pass/fail gate result in Validation Summary
    - Reference DUT Anti-UAV and VisDrone benchmarks in Validation Summary

    Returns path to the generated .md file.
    """
    results_path = run_dir / "results.json"
    config_path = run_dir / "train_config.yaml"

    results: dict = {}
    if results_path.exists():
        results = json.loads(results_path.read_text(encoding="utf-8"))

    config: dict = {}
    if config_path.exists():
        config = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}

    run_id = results.get("run_id", run_dir.name)
    model_variant = results.get("model_variant") or config.get("model_variant", "unknown")
    hardware_profile = config.get("hardware_profile", "unknown")
    augmentation: dict[str, float] = config.get("augmentation") or {}

    map50 = results.get("map50")
    map50_95 = results.get("map50_95")
    precision = results.get("precision")
    recall = results.get("recall")
    f1 = results.get("f1")
    per_class_map50: dict = results.get("per_class_map50") or {}
    small_object_map50: dict = results.get("small_object_map50") or {}
    false_positive_rate = results.get("false_positive_rate")
    passed_gate: bool = bool(results.get("passed_gate", False))
    completed: bool = bool(results.get("completed", False))
    duration_seconds: float = float(results.get("duration_seconds", 0.0))
    stal_recommendations: list[str] = results.get("stal_recommendations") or []

    # Detect augmentation deviations
    aug_deviations: list[str] = []
    for key, default_val in _DEFAULT_AUGMENTATION.items():
        actual = augmentation.get(key)
        if actual is not None and abs(actual - default_val) > 1e-9:
            aug_deviations.append(
                f"- `{key}`: default={default_val}, used={actual}"
            )

    lines: list[str] = []
    lines.append(f"# Run Documentation: {run_id}\n")

    # --- Dataset Used ---
    lines.append("## Dataset Used\n")
    data_yaml = config.get("data_yaml", "merged_dataset/data.yaml")
    lines.append(f"- Data YAML: `{data_yaml}`\n")
    lines.append("")

    # --- Model Variant ---
    lines.append("## Model Variant\n")
    lines.append(f"- Model: `{model_variant}`\n")
    lines.append("")

    # --- Training Parameters ---
    lines.append("## Training Parameters\n")
    param_keys = ["imgsz", "batch", "epochs", "optimizer", "lr0", "weight_decay", "amp"]
    for key in param_keys:
        val = config.get(key)
        if val is not None:
            lines.append(f"- {key}: `{val}`")
    lines.append("")
    if augmentation:
        lines.append("### Augmentation\n")
        for k, v in augmentation.items():
            lines.append(f"- {k}: `{v}`")
        lines.append("")

    # --- Hardware Profile ---
    lines.append("## Hardware Profile\n")
    lines.append(f"- Profile: `{hardware_profile}`\n")
    lines.append("")

    # --- Final Metrics ---
    lines.append("## Final Metrics\n")
    lines.append(f"- mAP@0.5: `{map50}`")
    lines.append(f"- mAP@0.5:0.95: `{map50_95}`")
    lines.append(f"- Precision: `{precision}`")
    lines.append(f"- Recall: `{recall}`")
    lines.append(f"- F1: `{f1}`")
    lines.append(f"- False Positive Rate: `{false_positive_rate}`")
    if per_class_map50:
        lines.append("\n### Per-Class mAP@0.5\n")
        for cls, val in per_class_map50.items():
            lines.append(f"- {cls}: `{val}`")
    if small_object_map50:
        lines.append("\n### Small-Object mAP@0.5\n")
        for cls, val in small_object_map50.items():
            lines.append(f"- {cls}: `{val}`")
    lines.append("")

    # --- Training Duration ---
    lines.append("## Training Duration\n")
    lines.append(f"- Duration: `{duration_seconds:.1f}` seconds\n")
    lines.append(f"- Completed: `{completed}`\n")
    lines.append("")

    # --- Warnings and Anomalies ---
    lines.append("## Warnings and Anomalies\n")
    if not completed:
        lines.append("- **Warning:** Training run did not complete successfully.\n")
    if not stal_recommendations and not aug_deviations and completed:
        lines.append("- No anomalies detected.\n")
    lines.append("")

    # --- STAL Flag (conditional) ---
    if stal_recommendations:
        lines.append("## STAL Recommendations\n")
        for rec in stal_recommendations:
            lines.append(f"- {rec}")
        lines.append("")

    # --- Augmentation Deviation (conditional) ---
    if aug_deviations:
        lines.append("## Augmentation Deviation\n")
        lines.append(
            "The following augmentation parameters differ from system defaults:\n"
        )
        for dev in aug_deviations:
            lines.append(dev)
        lines.append("")

    # --- Justification ---
    lines.append("## Justification\n")
    lines.append(
        f"The `{model_variant}` model was selected for the `{hardware_profile}` hardware profile "
        "to balance detection accuracy and GPU memory usage. "
        "The augmentation parameters are tuned for aerial/UAV imagery, with elevated `copy_paste` "
        "to improve small-object detection performance. "
        "MuSGD optimizer and AMP (mixed precision) are used to maximize training throughput "
        "within the available VRAM budget.\n"
    )
    lines.append("")

    # --- Validation Summary ---
    lines.append("## Validation Summary\n")
    gate_str = "**PASS**" if passed_gate else "**FAIL**"
    lines.append(f"- Validation gate result: {gate_str}\n")
    lines.append(f"- Overall mAP@0.5: `{map50}`\n")
    lines.append(
        "- Benchmarks referenced: "
        "[DUT Anti-UAV](https://github.com/wangdongdut/DUT-Anti-UAV) and "
        "[VisDrone](https://github.com/VisDrone/VisDrone-Dataset).\n"
    )
    if not passed_gate:
        lines.append(
            "- The run did not meet the minimum mAP@0.5 ≥ 0.75 threshold. "
            "Consider collecting more data, adjusting augmentation, or using a larger model variant.\n"
        )
    lines.append("")

    content = "\n".join(lines)
    output_dir.mkdir(parents=True, exist_ok=True)
    out_path = output_dir / f"{run_dir.name}.md"
    atomic_write(out_path, content)
    logger.info("Generated run documentation: %s", out_path)
    return out_path


def append_changelog_entry(
    root: Path, run_id: str, metrics: ValidationMetrics, passed: bool
) -> None:
    """Append one-line summary to CHANGELOG.md atomically.

    Format: | {run_id} | {model_variant} | {map50:.3f} | {passed} |
    Create CHANGELOG.md with header if it doesn't exist.
    """
    changelog_path = root / "CHANGELOG.md"

    # Read existing content or start fresh
    if changelog_path.exists():
        existing = changelog_path.read_text(encoding="utf-8")
        if not existing.startswith("| Run ID"):
            # Prepend header if missing
            existing = _CHANGELOG_HEADER + existing
    else:
        existing = _CHANGELOG_HEADER

    # Determine model_variant from run_id (best effort: last segment after final _)
    # The run_id is typically run_{date}_{time}_{model_variant}
    parts = run_id.rsplit("_", 1)
    model_variant = parts[-1] if len(parts) > 1 else "unknown"

    pass_str = "PASS" if passed else "FAIL"
    new_line = f"| {run_id} | {model_variant} | {metrics.map50:.3f} | {pass_str} |\n"

    atomic_write(changelog_path, existing + new_line)
    logger.info("Appended changelog entry for run: %s", run_id)
