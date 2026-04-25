# Run Documentation: ThermalDrone-RTX

**Run ID:** `thermal_drone_yolo26s_rtx2070_100ep`

## Training Configuration

| Parameter | Value |
|---|---|
| model | yolo26s |
| classes | 1 (Drone) |
| dataset | SIDD thermal — 4 scenes (city, moutain, sea, sky) |
| train_images | 3,788 |
| val_images | 949 |
| hardware | RTX 2070 8GB |
| epochs | 100 |
| batch | 8 |
| imgsz | 640 |
| optimizer | SGD |
| lr0 | 0.005 |
| patience | 20 |

**Augmentation (thermal-specific):**
- mosaic=1.0, copy_paste=0.7, mixup=0.0
- hsv_h=0.0, hsv_s=0.0, hsv_v=0.15 (grayscale — HSV disabled)
- degrees=15, scale=0.7, flipud=0.3, fliplr=0.5
- erasing=0.3 (simulates CCTV text overlays)

## Dataset

| Source | Scene | Train | Val |
|---|---|---|---|
| SIDD | city | 874 | 219 |
| SIDD | moutain | 1,720 | 431 |
| SIDD | sea | 570 | 143 |
| SIDD | sky | 624 | 156 |
| **Total** | | **3,788** | **949** |

- Format: COCO JSON → converted to YOLO
- Image size: 640×512 px
- Single class: Drone (remapped from UAV)
- No pre-augmentation in source data

## Benchmark Datasets (evaluation only, not training)

- **Anti-UAV410** — 410 thermal sequences, 438K annotated frames. Tracking benchmark.
- **CST-Anti-UAV** — 220 thermal sequences, 240K annotated frames. Tracking benchmark.

## Results

| Metric | Value |
|---|---|
| mAP@0.5 | TBD |
| mAP@0.5:0.95 | TBD |
| Precision | TBD |
| Recall | TBD |
| Best Epoch | TBD |
| Duration (h) | TBD |

## Notes

- Thermal-only model, separate from RGB pipeline
- SIDD is the only dataset with actual image frames available locally
- Anti-UAV410 and CST are tracking benchmarks — use for post-training evaluation
