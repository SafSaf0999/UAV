"""
Fine-tune ThermalDrone (YOLO26s) on the Combined_Dataset.

Settings: lr0=0.001, epochs=20, patience=8, imgsz=640, batch=8, amp=True
Output:   training/thermal_ft_combined_640/

After training, invokes benchmark_runner.py with the new best.pt and the
optimal confidence threshold from conf_sweep_results.json.

Usage:
    python scripts/finetune_train.py [--data PATH] [--weights PATH]
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
MODELS_DIR      = Path("/home/safsaf/Projects/UAV/models")

DEFAULT_DATA    = BASE / "thermal_datasets/combined_finetune/data.yaml"
DEFAULT_WEIGHTS = MODELS_DIR / "ThermalDrone_best.pt"
CONF_SWEEP_JSON = BASE / "training/thermal_improvement/conf_sweep_results.json"
OUTPUT_DIR      = BASE / "training/thermal_ft_combined_640"
BENCHMARK_SCRIPT = BASE / "scripts/benchmark_runner.py"
VENV_PY = BASE / ".venv/bin/python"
PYTHON  = str(VENV_PY) if VENV_PY.exists() else sys.executable


def load_optimal_conf() -> float:
    if CONF_SWEEP_JSON.exists():
        data = json.loads(CONF_SWEEP_JSON.read_text())
        return float(data.get("optimal_threshold", 0.25))
    log.warning("conf_sweep_results.json not found, using default conf=0.25")
    return 0.25


def main():
    parser = argparse.ArgumentParser(description="Fine-tune ThermalDrone on Combined_Dataset")
    parser.add_argument("--data",    default=str(DEFAULT_DATA))
    parser.add_argument("--weights", default=str(DEFAULT_WEIGHTS))
    args = parser.parse_args()

    data_path    = Path(args.data)
    weights_path = Path(args.weights)

    if not data_path.exists():
        log.error(f"data.yaml not found: {data_path}")
        sys.exit(1)

    if not weights_path.exists():
        log.error(f"Weights file not found: {weights_path}")
        sys.exit(1)

    from ultralytics import YOLO

    log.info(f"Loading model: {weights_path}")
    model = YOLO(str(weights_path))

    log.info("Starting fine-tune training...")
    model.train(
        data       = str(data_path),
        project    = str(OUTPUT_DIR.parent),
        name       = OUTPUT_DIR.name,
        exist_ok   = True,
        epochs     = 20,
        imgsz      = 640,
        batch      = 8,
        patience   = 8,
        lr0        = 0.001,
        amp        = True,
        workers    = 4,
        # thermal augmentation profile
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

    best_pt = OUTPUT_DIR / "weights/best.pt"
    if not best_pt.exists():
        log.error(f"Training completed but best.pt not found at {best_pt}")
        sys.exit(1)

    # Task 6.5: invoke benchmark_runner with new best.pt and optimal conf
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

    log.info(f"Fine-tune complete. Results: {benchmark_output}")


if __name__ == "__main__":
    main()
