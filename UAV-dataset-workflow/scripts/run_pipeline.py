"""
Pipeline orchestrator for the Thermal Model Improvement workflow.

Steps (in order):
  conf_sweep → negatives → prepare → finetune → retrain → benchmark

Usage:
    python scripts/run_pipeline.py [--dry-run] [--start-from STEP]

STEP values: conf_sweep, negatives, prepare, finetune, retrain, benchmark
"""

import argparse
import json
import logging
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger(__name__)

BASE    = Path("/home/safsaf/Projects/UAV/UAV-dataset-workflow")
SCRIPTS = BASE / "scripts"
VENV_PY = BASE / ".venv/bin/python"
LOG_FILE = BASE / "training/thermal_improvement_pipeline.log"

# Use venv python if available, fall back to sys.executable
PYTHON = str(VENV_PY) if VENV_PY.exists() else sys.executable

CONF_SWEEP_JSON = BASE / "training/thermal_improvement/conf_sweep_results.json"
FT_BENCHMARK    = BASE / "training/thermal_ft_combined_640/benchmark_results.json"
RT_BENCHMARK    = BASE / "training/thermal_retrain_combined_1280/benchmark_results.json"
FINAL_BENCHMARK = BASE / "training/thermal_final_benchmark_results.json"

PIPELINE_STEPS = ["conf_sweep", "negatives", "prepare", "finetune", "retrain", "benchmark"]

STEP_COMMANDS = {
    "conf_sweep": [PYTHON, str(SCRIPTS / "conf_sweep.py")],
    "negatives":  [PYTHON, str(SCRIPTS / "collect_negatives.py")],
    "prepare":    [PYTHON, str(SCRIPTS / "prepare_combined_dataset.py")],
    "finetune":   [PYTHON, str(SCRIPTS / "finetune_train.py")],
    "retrain":    [PYTHON, str(SCRIPTS / "retrain_hires.py")],
    "benchmark":  [
        PYTHON, str(SCRIPTS / "benchmark_runner.py"),
        "--output", str(FINAL_BENCHMARK),
    ],
}


def get_steps_from(start_step: str) -> list[str]:
    idx = PIPELINE_STEPS.index(start_step)
    return PIPELINE_STEPS[idx:]


def load_mean_f1(benchmark_json: Path) -> float | None:
    """Load mean F1 across all three benchmarks from a benchmark_results.json."""
    if not benchmark_json.exists():
        return None
    try:
        data = json.loads(benchmark_json.read_text())
        f1s = []
        for key in ("antiuav410", "antimuav1"):
            if key in data:
                f1s.append(float(data[key].get("f1", 0.0)))
        if "sidd_val" in data:
            # use mAP50 as proxy for SIDD (same as conf_sweep)
            f1s.append(float(data["sidd_val"].get("mAP50", data["sidd_val"].get("f1", 0.0))))
        return sum(f1s) / len(f1s) if f1s else None
    except Exception as exc:
        log.warning(f"Could not parse {benchmark_json}: {exc}")
        return None


def load_optimal_conf() -> str:
    if CONF_SWEEP_JSON.exists():
        data = json.loads(CONF_SWEEP_JSON.read_text())
        return str(data.get("optimal_threshold", 0.25))
    return "0.25"


def append_log(entry: dict) -> None:
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with LOG_FILE.open("a") as f:
        f.write(json.dumps(entry) + "\n")


def run_step(step: str, dry_run: bool) -> bool:
    """Run a single pipeline step. Returns True on success."""
    cmd = list(STEP_COMMANDS[step])

    # For the final benchmark step, inject --weights and --conf if available
    if step == "benchmark":
        # Use the best model from retrain if available, else finetune
        for candidate in (
            BASE / "training/thermal_retrain_combined_1280/weights/best.pt",
            BASE / "training/thermal_ft_combined_640/weights/best.pt",
        ):
            if candidate.exists():
                cmd += ["--weights", str(candidate)]
                break
        cmd += ["--conf", load_optimal_conf()]

    if dry_run:
        print(f"[dry-run] {' '.join(str(c) for c in cmd)}")
        return True

    log.info(f"Running step: {step}")
    start = time.monotonic()
    result = subprocess.run(cmd, check=False, capture_output=False)
    elapsed = round(time.monotonic() - start, 2)
    status = "success" if result.returncode == 0 else "failure"

    entry = {
        "timestamp": datetime.utcnow().isoformat(),
        "step":      step,
        "elapsed":   elapsed,
        "status":    status,
        "returncode": result.returncode,
    }
    append_log(entry)

    if result.returncode != 0:
        log.error(f"Step '{step}' failed (exit {result.returncode}) after {elapsed}s")
        return False

    log.info(f"Step '{step}' succeeded in {elapsed}s")
    return True


def check_improvement(step: str, best_f1: float) -> tuple[bool, float]:
    """After a training step, check if mean F1 improved by >= 0.01.

    Returns (should_continue, new_best_f1).
    """
    result_map = {
        "finetune": FT_BENCHMARK,
        "retrain":  RT_BENCHMARK,
    }
    json_path = result_map.get(step)
    if json_path is None:
        return True, best_f1

    new_f1 = load_mean_f1(json_path)
    if new_f1 is None:
        log.warning(f"Could not read benchmark results for step '{step}', continuing anyway")
        return True, best_f1

    delta = new_f1 - best_f1
    log.info(f"Step '{step}': mean F1 = {new_f1:.4f} (prev best = {best_f1:.4f}, delta = {delta:+.4f})")

    if delta < 0.01:
        log.warning(
            f"No improvement after '{step}' (delta={delta:+.4f} < 0.01). "
            "Halting further training steps."
        )
        return False, best_f1

    return True, new_f1


def main():
    parser = argparse.ArgumentParser(description="Thermal model improvement pipeline orchestrator")
    parser.add_argument("--dry-run",    action="store_true", help="Print commands without executing")
    parser.add_argument("--start-from", choices=PIPELINE_STEPS, default="conf_sweep",
                        metavar="STEP", help=f"Resume from step: {', '.join(PIPELINE_STEPS)}")
    parser.add_argument("--skip", nargs="*", choices=PIPELINE_STEPS, default=[],
                        metavar="STEP", help="Steps to skip")
    args = parser.parse_args()

    steps = [s for s in get_steps_from(args.start_from) if s not in args.skip]

    if args.dry_run:
        print(f"[dry-run] Pipeline steps to execute: {steps}")
        for step in steps:
            run_step(step, dry_run=True)
        return

    log.info(f"Starting pipeline from step '{args.start_from}'. Steps: {steps}")
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

    best_f1 = 0.0
    training_steps = {"finetune", "retrain"}

    for step in steps:
        ok = run_step(step, dry_run=False)
        if not ok:
            log.error(f"Pipeline halted at step '{step}'")
            sys.exit(1)

        # Task 8.9: after each training step, check improvement
        if step in training_steps:
            should_continue, best_f1 = check_improvement(step, best_f1)
            if not should_continue:
                # Always run the final benchmark regardless
                if "benchmark" not in steps[steps.index(step):]:
                    break
                remaining = steps[steps.index(step) + 1:]
                non_benchmark = [s for s in remaining if s != "benchmark"]
                if non_benchmark:
                    log.info("Skipping remaining training steps, running final benchmark only.")
                    run_step("benchmark", dry_run=False)
                    break

    log.info("Pipeline complete.")


if __name__ == "__main__":
    main()
