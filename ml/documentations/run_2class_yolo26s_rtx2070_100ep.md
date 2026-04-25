# Run Documentation: BirdDrone-RTX

**Run ID:** `BirdDrone-RTX`

## Training Configuration

| Parameter | Value |
|---|---|
| model | yolo26s |
| classes | 2 |
| dataset | Curated 2-class ~6,808 images (3 sources) |
| train_images | 4901 |
| val_images | 1225 |
| hardware | RTX 2070 8GB |
| epochs | 100 |
| batch | 16 |
| imgsz | 640 |
| optimizer | SGD (MuSGD) |
| lr0 | 0.01 |

**Augmentation:** mosaic=1.0, copy_paste=0.6, degrees=20, flipud=0.3, mixup=0.0

## Dataset Distribution

Bird: 3,404 images (50%), Drone: 3,404 images (50%). Perfectly balanced. Drone class includes 554 fixed-wing UAV images + 2,850 anti-UAV images.

## Results

| Metric | Value |
|---|---|
| mAP@0.5 | 0.926 |
| mAP@0.5:0.95 | 0.553 |
| Precision | 0.942 |
| Recall | 0.873 |
| Best Epoch | 99.000 |
| Duration (h) | 4.170 |

**Pass gate (mAP@0.5 ≥ 0.75):** ✅ PASS

## Notes

Focused 2-class. Balanced Bird/Drone. Fixed-wing UAV included in Drone class.
