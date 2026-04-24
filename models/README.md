# Production Models

All models use YOLO26s architecture (9.9M parameters, 22.5 GFLOPs).

## BirdDrone-2C-FT (Recommended RGB model)
- **File:** `BirdDrone-2C-FT_best.pt`
- **Modality:** RGB
- **Classes:** 2 — Bird (0), Drone (1)
- **mAP@0.5:** 0.969 | mAP@0.5:0.95: 0.678
- **Bird false alarm rate:** 0.3%
- **Training:** 6,808 images (balanced 50/50) + DUT pseudo-label fine-tuning
- **Source:** `/home/safsaf/Projects/UAV/UAV-dataset-workflow/training/finetuned/BirdDrone-2C/weights/best.pt`

## ThermalDrone (Recommended thermal model)
- **File:** `ThermalDrone_best.pt`
- **Modality:** Thermal infrared (LWIR)
- **Classes:** 1 — Drone (0)
- **mAP@0.5:** 0.958 | mAP@0.5:0.95: 0.654 (SIDD val)
- **Anti-UAV410 benchmark:** Precision=0.993, Recall=0.730, F1=0.842
- **Training:** SIDD thermal dataset, 3,788 images, 4 scenes
- **Source:** `/home/safsaf/Projects/UAV/UAV-dataset-workflow/training/thermal_drone_yolo26s_rtx2070_100ep/weights/best.pt`

## Usage

```python
from ultralytics import YOLO

# RGB detection (Bird/Drone)
model = YOLO("models/BirdDrone-2C-FT_best.pt")
results = model("image.jpg", conf=0.40)

# Thermal detection (Drone only)
model = YOLO("models/ThermalDrone_best.pt")
results = model("thermal_frame.jpg", conf=0.25)
```
