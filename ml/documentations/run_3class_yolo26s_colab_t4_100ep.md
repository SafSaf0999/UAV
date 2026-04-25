# Run Documentation: YOLO26s TriClass-T4 (Bird/Drone/UAV)

**Run ID:** `TriClass-T4`

## Training Configuration

| Parameter | Value |
|---|---|
| model | yolo26s |
| classes | 3 |
| dataset | Merged RGB ~31,551 images (4 sources) |
| train_images | 22293 |
| val_images | 6189 |
| hardware | Google Colab T4 16GB |
| epochs | 100 |
| batch | 32 |
| imgsz | 640 |
| optimizer | MuSGD |
| lr0 | 0.01 |

**Augmentation:** mosaic=1.0, copy_paste=0.5, degrees=20, flipud=0.3

## Dataset Distribution

Bird: 8,679 ann (29%), Drone: 7,524 ann (25%), UAV: 13,799 ann (46%). Ratio 1.8:1:1.2.

## Results

| Metric | Value |
|---|---|
| mAP@0.5 | 0.892 |
| mAP@0.5:0.95 | 0.574 |
| Precision | 0.852 |
| Recall | 0.837 |
| Best Epoch | 92.000 |
| Duration (h) | 3.190 |

**Pass gate (mAP@0.5 ≥ 0.75):** ✅ PASS

## Notes

Largest dataset. 3-class taxonomy. Resumed from checkpoint.
