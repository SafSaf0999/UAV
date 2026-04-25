"""
Step 3: Fine-tune both models on the merged datasets.

Conservative settings:
  - Resume from best.pt (not from scratch)
  - lr0=0.001 (10x lower than original)
  - 20 epochs with patience=8 (early stop if val mAP drops)
  - Saves to training/finetuned/run_*

Original training/ folder is NOT modified.
"""
from __future__ import annotations
from pathlib import Path
from datetime import datetime

ROOT     = Path("/home/safsaf/Projects/UAV-dataset-workflow")
FT_BASE  = ROOT / "training" / "finetuned"
FT_BASE.mkdir(parents=True, exist_ok=True)

RUNS = [
    # 2-class already done
    # {
    #     "name":    f"run_2class_dut_finetune_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
    #     "weights": ROOT / "training" / "run_2class_yolo26s_rtx2070_100ep" / "weights" / "best.pt",
    #     "data":    ROOT / "datasets" / "finetune_2class" / "data.yaml",
    #     "device":  0,
    #     "batch":   16,
    # },
    {
        "name":    f"run_3class_dut_finetune_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
        "weights": ROOT / "training" / "run_3class_yolo26s_colab_t4_100ep" / "weights" / "best.pt",
        "data":    ROOT / "datasets" / "finetune_3class" / "data.yaml",
        "device":  0,
        "batch":   16,
    },
]


def main():
    from ultralytics import YOLO

    for run in RUNS:
        print(f"\n{'='*60}")
        print(f"Fine-tuning: {run['name']}")
        print(f"Weights    : {run['weights']}")
        print(f"Data       : {run['data']}")
        print(f"{'='*60}")

        model = YOLO(str(run["weights"]))
        model.train(
            data         = str(run["data"]),
            epochs       = 20,
            imgsz        = 640,
            batch        = run["batch"],
            patience     = 8,           # early stop if no improvement for 8 epochs
            optimizer    = "SGD",
            lr0          = 0.001,       # 10x lower than original — conservative
            lrf          = 0.01,
            weight_decay = 0.0005,
            amp          = True,
            workers      = 0,
            device       = run["device"],
            project      = str(FT_BASE),
            name         = run["name"],
            exist_ok     = True,
            # Same augmentation as original
            mosaic       = 1.0,
            copy_paste   = 0.6,
            mixup        = 0.0,
            hsv_h        = 0.02,
            hsv_s        = 0.7,
            hsv_v        = 0.5,
            degrees      = 20.0,
            translate    = 0.15,
            scale        = 0.8,
            flipud       = 0.3,
            fliplr       = 0.5,
            plots        = True,
            save         = True,
            verbose      = True,
        )
        print(f"\nDone. Weights: {FT_BASE / run['name'] / 'weights'}")


if __name__ == "__main__":
    main()
