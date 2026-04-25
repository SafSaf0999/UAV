"""
Train yolo26s on the merged SIDD thermal dataset (1-class: Drone).
Hardware: RTX 2070 8GB

Usage:
    python scripts/train_thermal.py
"""

from pathlib import Path
from ultralytics import YOLO

DATA_YAML = Path("/home/safsaf/Projects/UAV/UAV-dataset-workflow/thermal_datasets/thermal_merged/data.yaml")
RUN_NAME = "thermal_drone_yolo26s_rtx2070_100ep"
PROJECT = Path("/home/safsaf/Projects/UAV/UAV-dataset-workflow/training")


def main():
    model = YOLO("yolo26s.pt")

    model.train(
        data=str(DATA_YAML),
        project=str(PROJECT),
        name=RUN_NAME,
        exist_ok=False,

        # --- core ---
        epochs=100,
        imgsz=640,
        batch=8,           # RTX 2070 8GB — thermal 640x512, conservative
        workers=4,

        # --- optimiser ---
        optimizer="SGD",
        lr0=0.005,         # lower than RGB runs — smaller dataset
        lrf=0.01,
        momentum=0.937,
        weight_decay=0.0005,
        warmup_epochs=5,
        warmup_momentum=0.8,

        # --- regularisation ---
        patience=20,
        dropout=0.0,
        amp=True,

        # --- augmentation (thermal-specific) ---
        mosaic=1.0,
        copy_paste=0.7,    # high — helps with tiny drone targets
        mixup=0.0,         # disabled — thermal images don't blend well
        hsv_h=0.0,         # disabled — grayscale thermal
        hsv_s=0.0,         # disabled
        hsv_v=0.15,        # slight brightness variation only
        degrees=15.0,
        translate=0.1,
        scale=0.7,         # drones appear at very different scales
        shear=0.0,
        perspective=0.0,
        flipud=0.3,
        fliplr=0.5,
        erasing=0.3,       # simulate CCTV text/overlay occlusion

        # --- misc ---
        save=True,
        save_period=10,
        plots=True,
        verbose=True,
        seed=42,
    )


if __name__ == "__main__":
    main()
