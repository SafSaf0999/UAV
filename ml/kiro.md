# Anti-UAV Project — Full Context

## Project Goal

Build a multi-class object detection system for anti-UAV applications using YOLO26.
Detects three canonical classes: **Bird** (confuser), **Drone** (small UAV), **UAV** (large/fixed-wing).
Supports both RGB and thermal infrared modalities.

---

## Project Structure

```
/home/safsaf/Projects/UAV-dataset-workflow/
│
├── anti_uav/                    # Python package — core pipeline
│   ├── __init__.py
│   ├── cli.py                   # CLI entry points (anti-uav subcommands)
│   ├── __main__.py              # Entry point → launches GUI or CLI
│   ├── inspector.py             # Dataset inspection (ZIP/folder, YOLO/COCO/VOC)
│   ├── normalizer.py            # Class label normalization → Bird/Drone/UAV
│   ├── merger.py                # Dataset merging, SHA-256 dedup, data.yaml
│   ├── trainer.py               # YOLO26 training, hardware profiles, validation
│   ├── documenter.py            # Per-run Markdown documentation + CHANGELOG
│   ├── comparator.py            # Multi-run comparison reports + IoU plots
│   ├── colab_bridge.py          # Colab (semi-auto) + Kaggle (fully auto) training
│   ├── manual_generator.py      # MANUAL.md generator
│   ├── models.py                # Shared dataclasses and enums
│   ├── utils.py                 # Logging, atomic_write, sha256_hash
│   └── gui/
│       ├── launcher.py          # Unified PyQt5 launcher (10-tab GUI)
│       └── reviewer_ui.py       # Image reviewer with bbox overlay, pagination
│
├── datasets/                    # Raw source datasets (RGB)
│   ├── uavs/                    # 9,262 images — class: drone → Drone
│   ├── yolo-exp/                # 7,291 images — classes: Bird, drone
│   ├── anti-uav/                # 19,849 images — class: UAV
│   ├── uavdetector/             # 2,536 images — class: fixed wing UAV → UAV
│   ├── backup_raw_datasets.tar.gz    # 1.4GB backup of all 4 raw datasets
│   └── backup_merged_dataset.tar.gz  # 1.1GB backup of merged dataset
│
├── merged_dataset/              # Merged RGB dataset (31,551 images)
│   ├── train/images/ labels/    # 22,293 images
│   ├── val/images/ labels/      # 6,189 images
│   ├── test/images/ labels/     # 3,069 images
│   └── data.yaml                # names: [Bird, Drone, UAV], nc: 3
│
├── thermal_datasets/            # Thermal/IR datasets (in progress)
│   ├── anti_uav_thermal/        # Anti-UAV RGB+Thermal (ZhaoJ9014) — PRIMARY
│   ├── anti_uav_410/            # Anti-UAV410 thermal benchmark — PRIMARY
│   ├── merged_thermal/          # Merged thermal dataset (future)
│   └── README.md                # Download instructions + training config
│
├── training/                    # Training run outputs
│   └── run_old_2nd_iteration_yolov12n/   # Old baseline run (yolov12n, 100 epochs)
│       ├── weights/best.pt last.pt
│       ├── results.json         # mAP@0.5: 0.987, mAP@0.5:0.95: 0.764
│       └── train_config.yaml
│
├── documentations/              # Auto-generated per-run docs
│   └── run_old_2nd_iteration_yolov12n.md
│
├── comparison/                  # Comparison reports
│
├── old_training/                # Previous training runs (reference)
│   └── 2nd_itiration_with_uav_dataset/
│       ├── weights/best.pt last.pt
│       ├── 2nd_itiration_results.csv   # Full 100-epoch results
│       └── args.yaml
│
├── runs/                        # Validation results
│   └── 60epochs/val_results.zip
│
├── notebooks/                   # Colab training notebooks
│   ├── colab_resume_full_run.ipynb       # Resume 3-class run from checkpoint
│   ├── colab_yolo26s_run1_fast.ipynb     # Fast validation (30% data)
│   ├── colab_yolo26s_run2_full.ipynb     # Full 3-class run
│   ├── colab_yolo26s_2class_birdvsdrone.ipynb  # 2-class Bird vs Drone run
│   ├── colab_validate_best.ipynb         # Validate best.pt on CPU
│   └── colab_yolo26m_run2.ipynb          # yolo26m run (unused)
│
├── scripts/                     # Utility scripts
│   ├── download_datasets.py     # Roboflow RGB dataset downloader
│   ├── download_thermal_datasets.py  # Thermal dataset downloader
│   ├── prepare_2class_run.py    # Re-normalize + merge for 2-class run
│   ├── generate_notebook.py     # Kaggle notebook generator
│   └── pull_results.py          # Pull Kaggle results locally
│
│   ├── notebook.ipynb           # Current training kernel (v6)
│   ├── dataset-metadata.json
│   └── kernel-metadata.json
│
├── mapping.json                 # RGB class mapping
├── thermal_mapping.json         # Thermal class mapping (Bird/Drone/UAV only)
├── download_datasets.py         # Roboflow dataset downloader
├── download_thermal_datasets.py # Thermal dataset downloader
├── launch.py                    # GUI launcher script
├── generate_notebook.py         # Kaggle notebook generator
├── pull_results.py              # Pull Kaggle results to local
├── pyproject.toml               # Package config (ultralytics>=8.4.0)
├── README.md                    # Project overview
├── MANUAL.md                    # Auto-generated user manual
└── kiro.md                      # This file — full project context
```

---

## Canonical Classes

| Class | Description | Index |
|---|---|---|
| Bird | Birds — confuser class, not a threat | 0 |
| Drone | Small consumer/commercial drones, quadcopters | 1 |
| UAV | Large UAVs, fixed-wing, military-grade | 2 |

---

## Class Distribution (merged_dataset — training set)

| Class | Index | Annotations | % |
|---|---|---|---|
| Bird | 0 | 8,679 | 29% |
| Drone | 1 | 7,524 | 25% |
| UAV | 2 | 13,799 | 46% |
| **Total** | | **30,002** | |

Ratio: UAV:Drone:Bird = 1.8:1:1.2 — within acceptable range (no class > 5x another).

**For 2-class run (Bird vs Drone):**
- Bird: 8,679 (29%)
- Drone (Drone+UAV merged): 21,323 (71%)
- Ratio: 2.5:1 — healthy balance

| Dataset | Source | Images | Class |
|---|---|---|---|
| uavs | universe.roboflow.com/uavs-7l7kv/uavs-vqpqt | 9,262 | drone→Drone |
| yolo-exp | universe.roboflow.com/dronesbird/yolo-exp | 7,291 | Bird, drone→Drone |
| anti-uav | universe.roboflow.com/yogith-nams8/anti-uav-s8wri | 19,849 | UAV |
| uavdetector | universe.roboflow.com/sihadenemeler/uavdetector | 2,536 | fixed wing→UAV |
| **Total merged** | | **31,551** | Bird, Drone, UAV |

Kaggle dataset: `mustafamubarak99/anti-uav-merged-dataset`

---

## Training Runs

### BirdDrone-2C (COMPLETED)
- Model: yolo26s, 2-class (Bird/Drone)
- Dataset: merged_dataset_2class — 6,808 images, perfectly balanced 50/50
- Hardware: RTX 2070 8GB (local)
- Epochs: 100 | Batch: 16 | lr0: 0.01
- **mAP@0.5: 0.926** | mAP@0.5:0.95: 0.554 | P: 0.942 | R: 0.873
- Weights: `training/run_2class_yolo26s_rtx2070_100ep/weights/best.pt`

### BirdDrone-3C (COMPLETED)
- Model: yolo26s, 3-class (Bird/Drone/UAV)
- Dataset: merged_dataset — 31,551 images (4 sources)
- Hardware: Google Colab T4 (multiple sessions, interrupted/resumed)
- Epochs: 100 | Batch: 32 | lr0: 0.01
- **mAP@0.5: 0.892** | mAP@0.5:0.95: 0.574 | P: 0.862 | R: 0.833
- Note: results.csv only has epochs 76-100 due to Colab session interruptions
- Weights: `training/run_3class_yolo26s_colab_t4_100ep/weights/best.pt`

### BirdDrone-2C-FT (COMPLETED)
- Model: yolo26s fine-tuned from BirdDrone-2C
- Dataset: finetune_2class — 13,984 train (original + DUT pseudo-labels)
- Hardware: RTX 2070 8GB (local)
- Epochs: 11 (early stopping) | Batch: 16 | lr0: 0.001
- **mAP@0.5: 0.969*** | mAP@0.5:0.95: 0.678* (*combined val set)
- DUT improvements: -55% low-conf FP, -34% tracking gaps
- Weights: `training/finetuned/BirdDrone-2C/weights/best.pt`

### BirdDrone-3C-FT (COMPLETED)
- Model: yolo26s fine-tuned from BirdDrone-3C
- Dataset: finetune_3class — 30,993 train (original + DUT pseudo-labels)
- Hardware: RTX 2070 8GB (local)
- Epochs: 20 | Batch: 16 | lr0: 0.001
- **mAP@0.5: 0.881*** | mAP@0.5:0.95: 0.598* (*combined val set)
- DUT improvements: -69% low-conf FP, -28% tracking gaps
- Weights: `training/finetuned/BirdDrone-3C/weights/best.pt`

---

## Training Parameters

### BirdDrone-2C (2-class, local RTX 2070)
```yaml
model: yolo26s
imgsz: 640
batch: 16
epochs: 100
patience: 30
optimizer: SGD
lr0: 0.01
weight_decay: 0.0005
amp: true
augmentation:
  mosaic: 1.0
  copy_paste: 0.6
  mixup: 0.0
  hsv_h: 0.02
  hsv_s: 0.7
  hsv_v: 0.5
  degrees: 20.0
  translate: 0.15
  scale: 0.8
  flipud: 0.3
  fliplr: 0.5
```

### BirdDrone-3C (3-class, Colab T4)
```yaml
model: yolo26s
imgsz: 640
batch: 32
epochs: 100
patience: 30
optimizer: MuSGD
lr0: 0.01
weight_decay: 0.0005
amp: true
augmentation:
  mosaic: 1.0
  copy_paste: 0.5
  mixup: 0.05
  degrees: 20.0
  flipud: 0.3
  fliplr: 0.5
```

### Fine-tuning (both models, local RTX 2070)
```yaml
epochs: 20
patience: 8
lr0: 0.001   # 10x lower — conservative fine-tune
batch: 16
# Same augmentation as base model
```

---

## Hardware Profiles

| Profile | Model | Batch | VRAM | Notes |
|---|---|---|---|---|
| rtx2070 | yolo26s | 16 | 4.7GB peak | Local training — confirmed working |
| colab_t4 | yolo26s | 32 | <14GB | Colab T4 |

---

## Thermal Training Plan (COMPLETED)

Datasets used:
1. SIDD (Shandong Infrared Drone Dataset) — 4 scenes (city, mountain, sea, sky), 4,737 images, COCO format
2. Anti-UAV410 — thermal IR benchmark, 410 sequences (evaluation only, NOT training)
3. CST-Anti-UAV — thermal IR benchmark, 220 sequences (evaluation pending)

Key differences from RGB:
- No HSV augmentation (thermal is grayscale)
- Higher copy_paste (0.7) for tiny targets
- erasing=0.3 to simulate CCTV text overlays
- No mixup
- Classes: Drone only (1-class)

### ThermalDrone (COMPLETED)
- Model: yolo26s, 1-class (Drone)
- Dataset: SIDD thermal — 3,788 train / 949 val (4 scenes)
- Hardware: RTX 2070 8GB (local)
- Epochs: 100 | Batch: 8 | lr0: 0.005
- **mAP@0.5: 0.958** | mAP@0.5:0.95: 0.654 | P: 0.983 | R: 0.908
- Anti-UAV410 benchmark: Precision=0.993, Recall=0.730, F1=0.842 (129,691 frames)
- Weights: `training/thermal_drone_yolo26s_rtx2070_100ep/weights/best.pt`
- Production copy: `models/ThermalDrone_best.pt`

---

## CLI Commands

```fish
# Activate venv
source .venv/bin/activate.fish

# Launch GUI (opens reviewer, inspector, trainer etc.)
python launch.py --gui

# Inspect dataset
python -m anti_uav inspect datasets/Birds.v1i.yolov8

# Merge 2-class dataset
python scripts/merge_2class.py

# Train 2-class model
python scripts/train_2class.py

# Fine-tune on DUT data
python scripts/build_dut_pseudolabels.py
python scripts/build_finetune_datasets.py
python scripts/finetune_models.py

# Run regression evaluation
python scripts/eval_regression.py

# Generate DUT annotated videos
python scripts/generate_dut_videos.py

# Compare models
python -m anti_uav compare
```

---

## Results Summary

| Model | mAP@0.5 | mAP@0.5:0.95 | Bird FA Rate | Notes |
|---|---|---|---|---|
| BirdDrone-2C | 0.926 | 0.554 | 0.3% | Base model |
| BirdDrone-3C | 0.892 | 0.574 | 6.9% | Base model |
| BirdDrone-2C-FT | 0.969* | 0.678* | 0.3% | **Recommended RGB** |
| BirdDrone-3C-FT | 0.881* | 0.598* | 4.5% | Fine-tuned |
| ThermalDrone | 0.958 | 0.654 | N/A | **Recommended thermal** |

*On combined val set (original + DUT annotations)

**Recommended production models:**
- RGB: BirdDrone-2C-FT → `models/BirdDrone-2C-FT_best.pt`
- Thermal: ThermalDrone → `models/ThermalDrone_best.pt`

---

## Validation Benchmarks

- DUT Anti-UAV (IEEE-TITS 2022) — RGB daytime, 20 videos, evaluated ✅
- Anti-UAV410 thermal benchmark — 128 test sequences, 129,691 frames, evaluated ✅ (F1=0.842)
- WOSDETC Drone-vs-Bird Challenge — data usage agreement pending
- CST-Anti-UAV thermal benchmark — frames not yet downloaded
