"""Quick stats on DUT frame CSVs to estimate pseudo-label yield and training time."""
import csv
from pathlib import Path

FRAME_DIR = Path("/home/safsaf/Projects/UAV-dataset-workflow/comparison/dut_frame_csv")
CONF_THRESH = 0.70

for model in ["BirdDrone-Local", "TriClass-Cloud"]:
    total = confident = 0
    for f in sorted(FRAME_DIR.glob(f"*_{model}.csv")):
        for row in csv.DictReader(open(f)):
            total += 1
            if float(row["max_conf"]) >= CONF_THRESH:
                confident += 1
    skipped = total - confident
    print(f"\n=== {model} ===")
    print(f"Total frames      : {total:,}")
    print(f"Usable (conf≥0.70): {confident:,}  ({confident/total*100:.1f}%)")
    print(f"Skipped           : {skipped:,}  ({skipped/total*100:.1f}%)")

    # Training time estimate
    # Original dataset sizes
    orig = 4901 if "2class" in model.lower() or "Local" in model else 22293
    new_total = orig + confident
    # ~2.2 it/s at batch 16 on RTX 2070, ~307 iters/epoch for 4901 images
    iters_per_epoch = new_total / 16
    secs_per_epoch = iters_per_epoch / 2.2
    epochs = 30  # fine-tune, not full retrain
    total_hours = (secs_per_epoch * epochs) / 3600
    print(f"\nFine-tune estimate (30 epochs, RTX 2070, batch 16):")
    print(f"  New dataset size  : {new_total:,} images")
    print(f"  Iters/epoch       : {iters_per_epoch:.0f}")
    print(f"  Time/epoch        : {secs_per_epoch/60:.1f} min")
    print(f"  Total (30 epochs) : {total_hours:.1f} hours")
    if "Cloud" in model:
        # Colab T4 batch 32 ~2.5 it/s
        iters_t4 = new_total / 32
        secs_t4 = iters_t4 / 2.5
        print(f"\nFine-tune estimate (30 epochs, Colab T4, batch 32):")
        print(f"  Time/epoch        : {secs_t4/60:.1f} min")
        print(f"  Total (30 epochs) : {secs_t4*30/3600:.1f} hours")
