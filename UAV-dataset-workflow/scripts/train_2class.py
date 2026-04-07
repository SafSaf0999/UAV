"""
Train yolo26s on merged_dataset_2class (Bird vs Drone).
Creates an isolated run folder under training/run_YYYYMMDD_HHMMSS_yolo26s_2class/
"""
from __future__ import annotations
import sys
from pathlib import Path
from datetime import datetime

ROOT = Path("/home/safsaf/Projects/UAV-dataset-workflow")
sys.path.insert(0, str(ROOT))

from ultralytics import YOLO

RUN_ID   = datetime.now().strftime("run_%Y%m%d_%H%M%S_yolo26s_2class")
RUN_DIR  = ROOT / "training" / RUN_ID
DATA     = ROOT / "merged_dataset_2class" / "data.yaml"

RUN_DIR.mkdir(parents=True, exist_ok=True)
print(f"Run ID  : {RUN_ID}")
print(f"Run dir : {RUN_DIR}")
print(f"Data    : {DATA}")

model = YOLO("yolo26s.pt")

model.train(
    data        = str(DATA),
    epochs      = 100,
    imgsz       = 640,
    batch       = 16,
    patience    = 30,
    optimizer   = "SGD",        # MuSGD exposed as SGD in ultralytics
    lr0         = 0.01,
    weight_decay= 0.0005,
    amp         = True,
    workers     = 0,        # Python 3.14 multiprocessing forkserver bug — use main process
    device      = 0,
    project     = str(ROOT / "training"),
    name        = RUN_ID,
    exist_ok    = True,
    # Augmentation
    mosaic      = 1.0,
    copy_paste  = 0.6,
    mixup       = 0.0,
    hsv_h       = 0.02,
    hsv_s       = 0.7,
    hsv_v       = 0.5,
    degrees     = 20.0,
    translate   = 0.15,
    scale       = 0.8,
    flipud      = 0.3,
    fliplr      = 0.5,
    # Logging
    plots       = True,
    save        = True,
    save_period = 10,           # checkpoint every 10 epochs
    verbose     = True,
)

print(f"\nTraining complete. Weights at: {ROOT}/training/{RUN_ID}/weights/")
