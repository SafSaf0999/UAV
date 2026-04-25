"""
Retrain YOLO26s from scratch at imgsz=1280 on the Combined_Dataset.

Settings: epochs=100, patience=30, lr0=0.005, batch=4 (fallback to 2 on OOM), amp=True
Output:   training/thermal_retrain_combined_1280/

After training, invokes benchmark_runner.py with the new best.pt and the
optimal confidence threshold from conf_sweep_results.json.

Usage:
    python scripts/retrain_hires.py [--data PATH]
"""

import argparse
import json
import logging
import subprocess
import sys
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger(__name__)

BASE = Path("/home/safsaf/Projects/UAV/UAV-dataset-workflow")

DEFAULT_DATA     = BASE / "thermal_datasets/combined_finetune/data.yaml"
CONF_SWEEP_JSON  = BASE / "training/thermal_improvement/conf_sweep_results.json"
OUTPUT_DIR       = BASE / "training/thermal_retrain_combined_1280"
BENCHMARK_SCRIPT = BASE / "scripts/benchmark_runner.py"
VENV_PY = BASE / ".venv/bin/python"
PYTHON  = str(VENV_PY) if VENV_PY.exists() else sys.executable


def load_optimal_conf() -> float:
    if CONF_SWEEP_JSON.exists():
        data = json.loads(CONF_SWEEP_JSON.read_text())
        return float(data.get("optimal_threshold", 0.25))
    log.warning("conf_sweep_results.json not found, using default conf=0.25")
    return 0.25


def run_training(data_path: Path, batch: int) -> None:
    from ultralytics import YOLO

    log.info(f"Loading YOLO26s base weights (no ThermalDrone transfer)")
    model = YOLO("yolo26s.pt")

    log.info(f"Starting high-resolution retraining (imgsz=1280, batch={batch})...")
    model.train(
        data       = str(data_path),
        project    = str(OUTPUT_DIR.parent),
        name       = OUTPUT_DIR.name,
        exist_ok   = True,
        epochs     = 100,
        imgsz      = 1280,
        batch      = batch,
        patience   = 30,
        lr0        = 0.005,
        amp        = True,
        workers    = 4,
        # thermal augmentation profile (no HSV, thermal-specific)
        hsv_h      = 0.0,
        hsv_s      = 0.0,
        copy_paste = 0.7,
        erasing    = 0.3,
        flipud     = 0.3,
        fliplr     = 0.5,
        save       = True,
        plots      = True,
        verbose    = True,
    )


def main():
    parser = argparse.ArgumentParser(description="Retrain YOLO26s at imgsz=1280 on Combined_Dataset")
    parser.add_argument("--data", default=str(DEFAULT_DATA))
    args = parser.parse_args()

    data_path = Path(args.data)
    if not data_path.exists():
        log.error(f"data.yaml not found: {data_path}")
        sys.exit(1)

    # Task 7.3 + 7.5: try batch=4, fall back to batch=2 on OOM
    try:
        run_training(data_path, batch=4)
    except RuntimeError as exc:
        if "out of memory" in str(exc).lower() or "cuda" in str(exc).lower():
            log.warning(f"GPU OOM at batch=4: {exc}. Retrying with batch=2...")
            run_training(data_path, batch=2)
        else:
            log.error(f"Training failed: {exc}")
            sys.exit(1)

    best_pt = OUTPUT_DIR / "weights/best.pt"
    if not best_pt.exists():
        log.error(f"Training completed but best.pt not found at {best_pt}")
        sys.exit(1)

    # Task 7.7: invoke benchmark_runner with new best.pt and optimal conf
    conf = load_optimal_conf()
    benchmark_output = OUTPUT_DIR / "benchmark_results.json"

    log.info(f"Running benchmark on {best_pt} with conf={conf}")
    result = subprocess.run(
        [
            PYTHON, str(BENCHMARK_SCRIPT),
            "--weights", str(best_pt),
            "--conf",    str(conf),
            "--output",  str(benchmark_output),
        ],
        check=False,
    )
    if result.returncode != 0:
        log.error("benchmark_runner.py failed")
        sys.exit(result.returncode)

    log.info(f"High-res retrain complete. Results: {benchmark_output}")


if __name__ == "__main__":
    main()
