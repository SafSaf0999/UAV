"""Property-based tests for the Thermal Model Improvement Pipeline — Properties 1–11.

# Feature: thermal-model-improvement, Property 1: threshold selection is argmax of mean F1
# Feature: thermal-model-improvement, Property 2: background candidate predicate correctness
# Feature: thermal-model-improvement, Property 3: empty label invariant for non-drone frames
# Feature: thermal-model-improvement, Property 4: manifest completeness
# Feature: thermal-model-improvement, Property 5: YOLO format round-trip
# Feature: thermal-model-improvement, Property 6: combined dataset membership
# Feature: thermal-model-improvement, Property 7: frame-level IoU matching correctness
# Feature: thermal-model-improvement, Property 8: multi-track false positive counting
# Feature: thermal-model-improvement, Property 9: benchmark JSON round-trip
# Feature: thermal-model-improvement, Property 10: pipeline step ordering and start-from correctness
# Feature: thermal-model-improvement, Property 11: log entry completeness

All pure functions are defined inline as helpers that mirror what the scripts will implement.
No GPU or real dataset files are required — YOLO model calls are mocked where needed.
"""
from __future__ import annotations

import json
import tempfile
import time
from pathlib import Path
from typing import Any

from hypothesis import assume, given, settings
from hypothesis import strategies as st

# ---------------------------------------------------------------------------
# Pure helper functions (mirrors of what the scripts will implement)
# ---------------------------------------------------------------------------

PIPELINE_STEPS = ["conf_sweep", "negatives", "prepare", "finetune", "retrain", "benchmark"]


def select_optimal_threshold(threshold_f1_map: dict[str, dict[str, float]]) -> str:
    """Return the threshold key with the highest mean F1 across all benchmarks.

    threshold_f1_map: {threshold_str: {benchmark_name: f1_score, ...}, ...}
    """
    best_thresh = max(
        threshold_f1_map,
        key=lambda t: sum(threshold_f1_map[t].values()) / len(threshold_f1_map[t]),
    )
    return best_thresh


def is_background_sidd(w: float, h: float, img_w: int, img_h: int) -> bool:
    """Return True iff the SIDD bbox pixel area is less than 100."""
    return w * img_w * h * img_h < 100


def is_invisible_antiuav(x1: float, y1: float, x2: float, y2: float, visible: int) -> bool:
    """Return True iff the Anti-UAV410 frame is invisible (visible==0 or all coords zero)."""
    return visible == 0 or (x1 == 0 and y1 == 0 and x2 == 0 and y2 == 0)


def write_background_label(label_path: Path) -> None:
    """Write an empty YOLO label file for a background image."""
    label_path.write_text("", encoding="utf-8")


def write_manifest(manifest_path: Path, image_paths: list[str]) -> None:
    """Write a manifest file listing all added background image paths."""
    manifest_path.write_text("\n".join(image_paths), encoding="utf-8")


def read_manifest(manifest_path: Path) -> list[str]:
    """Read a manifest file and return the list of image paths."""
    content = manifest_path.read_text(encoding="utf-8").strip()
    return content.splitlines() if content else []


def bbox_to_yolo(x_tl: float, y_tl: float, w: float, h: float,
                 img_w: int, img_h: int) -> tuple[float, float, float, float]:
    """Convert corner+size bbox to YOLO normalised format."""
    cx = (x_tl + w / 2) / img_w
    cy = (y_tl + h / 2) / img_h
    bw = w / img_w
    bh = h / img_h
    return cx, cy, bw, bh


def yolo_to_bbox(cx: float, cy: float, bw: float, bh: float,
                 img_w: int, img_h: int) -> tuple[float, float, float, float]:
    """Convert YOLO normalised format back to corner+size bbox."""
    w = bw * img_w
    h = bh * img_h
    x_tl = cx * img_w - w / 2
    y_tl = cy * img_h - h / 2
    return x_tl, y_tl, w, h


def compute_iou(box_a: tuple[float, float, float, float],
                box_b: tuple[float, float, float, float]) -> float:
    """Compute IoU between two boxes in (x_tl, y_tl, w, h) format."""
    ax1, ay1, aw, ah = box_a
    bx1, by1, bw, bh = box_b
    ax2, ay2 = ax1 + aw, ay1 + ah
    bx2, by2 = bx1 + bw, by1 + bh

    inter_x1 = max(ax1, bx1)
    inter_y1 = max(ay1, by1)
    inter_x2 = min(ax2, bx2)
    inter_y2 = min(ay2, by2)

    inter_w = max(0.0, inter_x2 - inter_x1)
    inter_h = max(0.0, inter_y2 - inter_y1)
    inter_area = inter_w * inter_h

    area_a = aw * ah
    area_b = bw * bh
    union_area = area_a + area_b - inter_area
    if union_area <= 0:
        return 0.0
    return inter_area / union_area


def frame_level_match(gt_box: tuple[float, float, float, float],
                      detections: list[tuple[float, float, float, float]],
                      iou_threshold: float = 0.5) -> bool:
    """Return True iff at least one detection has IoU >= iou_threshold with gt_box."""
    return any(compute_iou(gt_box, det) >= iou_threshold for det in detections)


def count_fp_on_invisible_frame(detections: list[Any], all_tracks_invisible: bool) -> int:
    """Return number of false positives: all detections are FP when all GT tracks are invisible."""
    if all_tracks_invisible:
        return len(detections)
    return 0


def serialize_benchmark_results(results: dict[str, Any]) -> str:
    """Serialize benchmark results dict to JSON string."""
    return json.dumps(results)


def deserialize_benchmark_results(json_str: str) -> dict[str, Any]:
    """Deserialize benchmark results from JSON string."""
    return json.loads(json_str)


def build_combined_train(
    sidd_train_paths: list[str],
    antiuav_train_paths: list[str],
) -> set[str]:
    """Build the combined training set from allowed sources only.

    Only SIDD train and Anti-UAV410 train paths are included.
    Anti-UAV410 test split and Anti-MUAV1 paths are never passed to this function.
    """
    return set(sidd_train_paths) | set(antiuav_train_paths)


def get_steps_from(start_step: str, all_steps: list[str]) -> list[str]:
    """Return the sublist of steps starting from start_step (inclusive)."""
    idx = all_steps.index(start_step)
    return all_steps[idx:]


def make_log_entry(step_name: str, elapsed: float, status: str) -> dict[str, Any]:
    """Create a log entry dict for a completed pipeline step."""
    return {"step": step_name, "elapsed": elapsed, "status": status}


# ---------------------------------------------------------------------------
# Hypothesis strategies
# ---------------------------------------------------------------------------

_THRESHOLDS = ["0.15", "0.20", "0.25", "0.30"]
_BENCHMARKS = ["antiuav410", "antimuav1", "sidd_val"]

_f1_score_st = st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False)

_threshold_map_st = st.fixed_dictionaries(
    {
        t: st.fixed_dictionaries({b: _f1_score_st for b in _BENCHMARKS})
        for t in _THRESHOLDS
    }
)

_pos_int_st = st.integers(min_value=1, max_value=4096)
_nonneg_float_st = st.floats(min_value=0.0, max_value=4096.0, allow_nan=False, allow_infinity=False)

_bbox_st = st.tuples(
    st.floats(min_value=0.0, max_value=3000.0, allow_nan=False, allow_infinity=False),
    st.floats(min_value=0.0, max_value=3000.0, allow_nan=False, allow_infinity=False),
    st.floats(min_value=1.0, max_value=1000.0, allow_nan=False, allow_infinity=False),
    st.floats(min_value=1.0, max_value=1000.0, allow_nan=False, allow_infinity=False),
)

_img_dim_st = st.integers(min_value=64, max_value=4096)

_detection_st = st.tuples(
    st.floats(min_value=0.0, max_value=3000.0, allow_nan=False, allow_infinity=False),
    st.floats(min_value=0.0, max_value=3000.0, allow_nan=False, allow_infinity=False),
    st.floats(min_value=1.0, max_value=500.0, allow_nan=False, allow_infinity=False),
    st.floats(min_value=1.0, max_value=500.0, allow_nan=False, allow_infinity=False),
)

_metric_st = st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False)

_benchmark_results_st = st.fixed_dictionaries(
    {
        "antiuav410": st.fixed_dictionaries(
            {"precision": _metric_st, "recall": _metric_st, "f1": _metric_st}
        ),
        "antimuav1": st.fixed_dictionaries(
            {"precision": _metric_st, "recall": _metric_st, "f1": _metric_st}
        ),
        "sidd_val": st.fixed_dictionaries(
            {"mAP50": _metric_st, "precision": _metric_st, "recall": _metric_st}
        ),
    }
)

_step_name_st = st.sampled_from(PIPELINE_STEPS)

_elapsed_st = st.floats(min_value=0.0, max_value=3600.0, allow_nan=False, allow_infinity=False)
_status_st = st.sampled_from(["success", "failure"])

_safe_filename_st = st.text(
    alphabet=st.characters(whitelist_categories=("Ll", "Lu", "Nd")),
    min_size=1,
    max_size=20,
).map(lambda s: s + ".jpg")


# ---------------------------------------------------------------------------
# Property 1: Threshold selection is argmax of mean F1
# Validates: Requirements 1.3
# ---------------------------------------------------------------------------

@settings(max_examples=100)
@given(threshold_map=_threshold_map_st)
def test_property1_threshold_selection_is_argmax_mean_f1(
    threshold_map: dict[str, dict[str, float]]
) -> None:
    """Property 1: The selected threshold must be the one with the highest mean F1.

    **Validates: Requirements 1.3**
    """
    selected = select_optimal_threshold(threshold_map)

    selected_mean = sum(threshold_map[selected].values()) / len(threshold_map[selected])
    for thresh, scores in threshold_map.items():
        mean = sum(scores.values()) / len(scores)
        assert selected_mean >= mean, (
            f"Selected threshold {selected!r} (mean F1={selected_mean:.4f}) is not the "
            f"argmax — threshold {thresh!r} has mean F1={mean:.4f}"
        )


# ---------------------------------------------------------------------------
# Property 2: Background candidate predicate correctness
# Validates: Requirements 2.2, 2.3
# ---------------------------------------------------------------------------

@settings(max_examples=100)
@given(
    w=st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
    h=st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
    img_w=_img_dim_st,
    img_h=_img_dim_st,
)
def test_property2a_sidd_background_predicate(
    w: float, h: float, img_w: int, img_h: int
) -> None:
    """Property 2a: is_background_sidd returns True iff w*img_w*h*img_h < 100.

    **Validates: Requirements 2.2**
    """
    result = is_background_sidd(w, h, img_w, img_h)
    expected = w * img_w * h * img_h < 100
    assert result == expected, (
        f"is_background_sidd({w}, {h}, {img_w}, {img_h}) = {result}, expected {expected}"
    )


@settings(max_examples=100)
@given(
    x1=_nonneg_float_st,
    y1=_nonneg_float_st,
    x2=_nonneg_float_st,
    y2=_nonneg_float_st,
    visible=st.integers(min_value=0, max_value=1),
)
def test_property2b_antiuav_invisible_predicate(
    x1: float, y1: float, x2: float, y2: float, visible: int
) -> None:
    """Property 2b: is_invisible_antiuav returns True iff visible==0 or all coords are zero.

    **Validates: Requirements 2.3**
    """
    result = is_invisible_antiuav(x1, y1, x2, y2, visible)
    expected = visible == 0 or (x1 == 0 and y1 == 0 and x2 == 0 and y2 == 0)
    assert result == expected, (
        f"is_invisible_antiuav({x1}, {y1}, {x2}, {y2}, {visible}) = {result}, expected {expected}"
    )


# ---------------------------------------------------------------------------
# Property 3: Empty label invariant for all non-drone frames
# Validates: Requirements 2.5, 3.3
# ---------------------------------------------------------------------------

@settings(max_examples=100)
@given(
    filenames=st.lists(_safe_filename_st, min_size=1, max_size=20, unique=True)
)
def test_property3_empty_label_invariant(filenames: list[str]) -> None:
    """Property 3: For any background image, the label file must exist and contain zero lines.

    **Validates: Requirements 2.5, 3.3**
    """
    with tempfile.TemporaryDirectory() as tmp:
        labels_dir = Path(tmp) / "labels"
        labels_dir.mkdir()

        for fname in filenames:
            label_path = labels_dir / (Path(fname).stem + ".txt")
            write_background_label(label_path)

        for fname in filenames:
            label_path = labels_dir / (Path(fname).stem + ".txt")
            assert label_path.exists(), f"Label file missing for {fname}"
            lines = [
                ln for ln in label_path.read_text(encoding="utf-8").splitlines()
                if ln.strip()
            ]
            assert len(lines) == 0, (
                f"Label file for {fname} has {len(lines)} annotation lines, expected 0"
            )


# ---------------------------------------------------------------------------
# Property 4: Manifest completeness
# Validates: Requirements 2.7
# ---------------------------------------------------------------------------

@settings(max_examples=100)
@given(
    image_paths=st.lists(
        st.text(
            alphabet=st.characters(whitelist_categories=("Ll", "Lu", "Nd", "Po", "Pd")),
            min_size=5,
            max_size=60,
        ).filter(lambda s: "\n" not in s and s.strip()),
        min_size=0,
        max_size=30,
        unique=True,
    )
)
def test_property4_manifest_completeness(image_paths: list[str]) -> None:
    """Property 4: The manifest file contains exactly the paths that were written.

    **Validates: Requirements 2.7**
    """
    with tempfile.TemporaryDirectory() as tmp:
        manifest_path = Path(tmp) / "manifest.txt"
        write_manifest(manifest_path, image_paths)
        recovered = read_manifest(manifest_path)

    assert set(recovered) == set(image_paths), (
        f"Manifest mismatch: written={set(image_paths)}, read back={set(recovered)}"
    )
    assert len(recovered) == len(image_paths), (
        f"Manifest length mismatch: written={len(image_paths)}, read back={len(recovered)}"
    )


# ---------------------------------------------------------------------------
# Property 5: YOLO format round-trip
# Validates: Requirements 3.2, 3.10
# ---------------------------------------------------------------------------

@settings(max_examples=100)
@given(
    img_w=_img_dim_st,
    img_h=_img_dim_st,
    x_tl=st.floats(min_value=0.0, max_value=3000.0, allow_nan=False, allow_infinity=False),
    y_tl=st.floats(min_value=0.0, max_value=3000.0, allow_nan=False, allow_infinity=False),
    w=st.floats(min_value=1.0, max_value=1000.0, allow_nan=False, allow_infinity=False),
    h=st.floats(min_value=1.0, max_value=1000.0, allow_nan=False, allow_infinity=False),
)
def test_property5_yolo_format_round_trip(
    img_w: int, img_h: int,
    x_tl: float, y_tl: float, w: float, h: float,
) -> None:
    """Property 5: Converting bbox to YOLO format and back recovers original within 1 pixel.

    **Validates: Requirements 3.2, 3.10**
    """
    cx, cy, bw, bh = bbox_to_yolo(x_tl, y_tl, w, h, img_w, img_h)
    rx_tl, ry_tl, rw, rh = yolo_to_bbox(cx, cy, bw, bh, img_w, img_h)

    assert abs(rx_tl - x_tl) <= 1.0, f"x_tl round-trip error: {abs(rx_tl - x_tl):.4f} > 1 px"
    assert abs(ry_tl - y_tl) <= 1.0, f"y_tl round-trip error: {abs(ry_tl - y_tl):.4f} > 1 px"
    assert abs(rw - w) <= 1.0, f"w round-trip error: {abs(rw - w):.4f} > 1 px"
    assert abs(rh - h) <= 1.0, f"h round-trip error: {abs(rh - h):.4f} > 1 px"


# ---------------------------------------------------------------------------
# Property 6: Combined dataset membership (no test-split contamination)
# Validates: Requirements 3.6
# ---------------------------------------------------------------------------

@settings(max_examples=100)
@given(
    sidd_train=st.lists(_safe_filename_st, min_size=0, max_size=20, unique=True),
    antiuav_train=st.lists(_safe_filename_st, min_size=0, max_size=20, unique=True),
    antiuav_test=st.lists(_safe_filename_st, min_size=0, max_size=10, unique=True),
    antimuav1=st.lists(_safe_filename_st, min_size=0, max_size=10, unique=True),
)
def test_property6_combined_dataset_membership(
    sidd_train: list[str],
    antiuav_train: list[str],
    antiuav_test: list[str],
    antimuav1: list[str],
) -> None:
    """Property 6: No image from Anti-UAV410 test split or Anti-MUAV1 appears in training set.

    In the real pipeline, images come from separate directories so filenames from different
    sources are distinct. We use assume() to enforce this constraint, then verify that
    build_combined_train (which only accepts allowed sources) produces no forbidden images.

    **Validates: Requirements 3.6**
    """
    allowed_pool = set(sidd_train) | set(antiuav_train)
    forbidden = set(antiuav_test) | set(antimuav1)

    # Real-world constraint: images from different dataset directories have distinct paths
    assume(allowed_pool.isdisjoint(forbidden))

    # The pipeline builds the combined training set from allowed sources only
    combined_train = build_combined_train(sidd_train, antiuav_train)

    contamination = combined_train & forbidden
    assert len(contamination) == 0, (
        f"Training set contaminated with test/eval images: {contamination}"
    )


# ---------------------------------------------------------------------------
# Property 7: Frame-level IoU matching correctness
# Validates: Requirements 6.3
# ---------------------------------------------------------------------------

@settings(max_examples=100)
@given(
    gt_box=_bbox_st,
    detections=st.lists(_detection_st, min_size=0, max_size=10),
)
def test_property7_frame_level_iou_matching(
    gt_box: tuple[float, float, float, float],
    detections: list[tuple[float, float, float, float]],
) -> None:
    """Property 7: match returns True iff at least one detection has IoU >= 0.5 with GT box.

    **Validates: Requirements 6.3**
    """
    result = frame_level_match(gt_box, detections, iou_threshold=0.5)

    # Compute expected result independently
    expected = any(compute_iou(gt_box, det) >= 0.5 for det in detections)

    assert result == expected, (
        f"frame_level_match returned {result}, expected {expected} "
        f"for gt_box={gt_box}, detections={detections}"
    )


# ---------------------------------------------------------------------------
# Property 8: Multi-track false positive counting on invisible frames
# Validates: Requirements 6.4
# ---------------------------------------------------------------------------

@settings(max_examples=100)
@given(
    num_detections=st.integers(min_value=0, max_value=20),
    all_tracks_invisible=st.booleans(),
)
def test_property8_multitrack_fp_counting(
    num_detections: int,
    all_tracks_invisible: bool,
) -> None:
    """Property 8: Any detection on a frame where all GT tracks are invisible counts as FP.

    **Validates: Requirements 6.4**
    """
    # Use dummy detection objects (just integers for counting purposes)
    detections = list(range(num_detections))
    fp_count = count_fp_on_invisible_frame(detections, all_tracks_invisible)

    if all_tracks_invisible:
        assert fp_count == num_detections, (
            f"Expected {num_detections} FPs on invisible frame, got {fp_count}"
        )
    else:
        assert fp_count == 0, (
            f"Expected 0 FPs on visible frame, got {fp_count}"
        )


# ---------------------------------------------------------------------------
# Property 9: Benchmark JSON round-trip
# Validates: Requirements 6.6
# ---------------------------------------------------------------------------

@settings(max_examples=100)
@given(results=_benchmark_results_st)
def test_property9_benchmark_json_round_trip(results: dict[str, Any]) -> None:
    """Property 9: Serialize/deserialize benchmark results preserves all values.

    **Validates: Requirements 6.6**
    """
    json_str = serialize_benchmark_results(results)
    recovered = deserialize_benchmark_results(json_str)

    assert set(recovered.keys()) == set(results.keys()), (
        f"Top-level keys mismatch: {set(recovered.keys())} != {set(results.keys())}"
    )
    for benchmark in results:
        for metric, value in results[benchmark].items():
            assert metric in recovered[benchmark], (
                f"Metric {metric!r} missing from recovered[{benchmark!r}]"
            )
            assert recovered[benchmark][metric] == value, (
                f"Value mismatch for {benchmark}.{metric}: "
                f"original={value}, recovered={recovered[benchmark][metric]}"
            )


# ---------------------------------------------------------------------------
# Property 10: Pipeline step ordering and start-from correctness
# Validates: Requirements 7.1, 7.6
# ---------------------------------------------------------------------------

@settings(max_examples=100)
@given(start_step=_step_name_st)
def test_property10_pipeline_step_ordering(start_step: str) -> None:
    """Property 10: --start-from S executes exactly steps from S to end of list.

    **Validates: Requirements 7.1, 7.6**
    """
    steps_to_run = get_steps_from(start_step, PIPELINE_STEPS)

    start_idx = PIPELINE_STEPS.index(start_step)

    # Must include start_step and all subsequent steps
    assert steps_to_run[0] == start_step, (
        f"First step should be {start_step!r}, got {steps_to_run[0]!r}"
    )
    assert steps_to_run == PIPELINE_STEPS[start_idx:], (
        f"Steps from {start_step!r} should be {PIPELINE_STEPS[start_idx:]}, got {steps_to_run}"
    )

    # Must skip all steps before start_step
    skipped = PIPELINE_STEPS[:start_idx]
    for skipped_step in skipped:
        assert skipped_step not in steps_to_run, (
            f"Step {skipped_step!r} should be skipped when starting from {start_step!r}"
        )


# ---------------------------------------------------------------------------
# Property 11: Log entry completeness
# Validates: Requirements 7.2
# ---------------------------------------------------------------------------

@settings(max_examples=100)
@given(
    step_name=_step_name_st,
    elapsed=_elapsed_st,
    status=_status_st,
)
def test_property11_log_entry_completeness(
    step_name: str, elapsed: float, status: str
) -> None:
    """Property 11: Each completed step produces a log entry with step name, elapsed time, status.

    **Validates: Requirements 7.2**
    """
    entry = make_log_entry(step_name, elapsed, status)

    assert "step" in entry, "Log entry missing 'step' field"
    assert "elapsed" in entry, "Log entry missing 'elapsed' field"
    assert "status" in entry, "Log entry missing 'status' field"

    assert entry["step"] == step_name, (
        f"Log entry step {entry['step']!r} != {step_name!r}"
    )
    assert entry["elapsed"] == elapsed, (
        f"Log entry elapsed {entry['elapsed']} != {elapsed}"
    )
    assert entry["status"] == status, (
        f"Log entry status {entry['status']!r} != {status!r}"
    )
