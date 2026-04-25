# Anti-UAV Dataset Management and YOLO26 Training Workflow

A Python-based desktop application and CLI toolkit for managing anti-UAV object detection datasets and training YOLO26 models.

## Overview

This system covers the full ML pipeline:

1. **Dataset Ingestion & Inspection** — scan folders or ZIP archives, detect annotation formats, compute statistics
2. **GUI Image Review** — browse, curate, and remap class labels via a PyQt5 desktop app with hover-preview and batch selection
3. **Class Normalization** — remap all source labels to canonical classes
4. **Dataset Merging** — combine curated datasets, deduplicate by SHA-256, write `data.yaml`
5. **Hardware-Aware Training** — YOLO26 training with profiles for RTX 2070 8 GB and Google Colab T4
6. **Run Management** — isolated run folders, interruption handling, resume support
7. **Documentation & Comparison** — auto-generated per-run Markdown docs and multi-run comparison reports
8. **Remote Training** — offload to Google Colab (semi-automated) or Kaggle (fully automated via API)
9. **DUT Anti-UAV Evaluation** — video-level detection analysis with annotated MP4 output

## Canonical Classes

**2-class models (BirdDrone-2C):**
- **Bird** — birds (confuser class)
- **Drone** — all aerial vehicles (rotary-wing, fixed-wing, UAV)

**3-class models (BirdDrone-3C):**
- **Bird** — birds
- **Drone** — small consumer drones / quadcopters
- **UAV** — large UAVs / fixed-wing

## Quick Start

```bash
pip install -e ".[dev]"

# Launch the unified GUI
anti-uav

# Or use individual subcommands
anti-uav inspect <dataset_path>
anti-uav review <dataset_path>
anti-uav normalize <dataset_path> --mapping mapping.json
anti-uav merge
anti-uav train --profile rtx2070
anti-uav document <run_dir>
anti-uav compare
```

## Project Structure

```
project_root/
├── datasets/                    # Source datasets
│   ├── Birds.v1i.yolov8/        # Bird detection (CC BY 4.0)
│   ├── anti-uav/                # UAV detection (CC BY 4.0)
│   ├── fixed-wing-uav/          # Fixed-wing UAV (CC0)
│   ├── uavs/                    # Drone detection (CC BY 4.0)
│   ├── uavdetector/             # Fixed-wing UAV (CC BY 4.0)
│   ├── DUT Anti-UAV/            # DUT benchmark videos (IEEE-TITS 2022)
│   ├── merged_dataset_2class/   # BirdDrone-2C training dataset (6,808 images)
│   ├── finetune_2class/         # BirdDrone-2C + DUT pseudo-labels (13,984 train)
│   └── finetune_3class/         # BirdDrone-3C + DUT pseudo-labels (30,993 train)
├── merged_dataset/              # 3-class merged dataset (31,551 images)
├── training/
│   ├── run_2class_yolo26s_rtx2070_100ep/   # BirdDrone-2C original
│   ├── run_3class_yolo26s_colab_t4_100ep/  # BirdDrone-3C original
│   └── finetuned/
│       ├── BirdDrone-2C/        # Fine-tuned 2-class model
│       └── BirdDrone-3C/        # Fine-tuned 3-class model
├── comparison/
│   ├── BirdDrone-2C_videos/     # Annotated DUT videos (BirdDrone-2C-FT)
│   ├── BirdDrone-3C_videos/     # Annotated DUT videos (BirdDrone-3C-FT)
│   ├── dut_frame_csv/           # Per-frame detection CSVs
│   ├── regression/              # 2-class regression reports
│   └── regression_3class/       # 3-class regression reports
├── documentations/
│   ├── report.pdf               # Main scientific report
│   ├── report_dut.pdf           # DUT Anti-UAV evaluation report
│   ├── citations.md             # Dataset citation requirements
│   ├── figures/                 # Training graphs (copied)
│   └── run_graphs/              # Per-run graphs and CSVs
├── scripts/                     # Pipeline scripts
├── anti_uav/                    # Python package source
├── mapping.json                 # 3-class label mapping
└── mapping_2class.json          # 2-class label mapping
```

## Trained Models

| Model | Classes | mAP@0.5 | mAP@0.5:0.95 | Hardware | Weights |
|---|---|---|---|---|---|
| BirdDrone-2C | Bird, Drone | 0.926 | 0.554 | RTX 2070 | `training/run_2class_yolo26s_rtx2070_100ep/weights/best.pt` |
| BirdDrone-3C | Bird, Drone, UAV | 0.892 | 0.574 | Colab T4 | `training/run_3class_yolo26s_colab_t4_100ep/weights/best.pt` |
| BirdDrone-2C-FT | Bird, Drone | 0.969* | 0.678* | RTX 2070 | `training/finetuned/BirdDrone-2C/weights/best.pt` |
| BirdDrone-3C-FT | Bird, Drone, UAV | 0.881* | 0.598* | RTX 2070 | `training/finetuned/BirdDrone-3C/weights/best.pt` |

*On combined val set (original + DUT pseudo-labels)

**Recommended production model:** BirdDrone-2C-FT — best bird detection (96.3%), lowest false positive rate, minimal regression.

## Requirements

- Python 3.10+
- PyQt5
- ultralytics >= 8.4.0 (YOLO26 family)
- opencv-python
- gdown (for Google Drive downloads)
- See `pyproject.toml` for full dependency list

## Dataset Citations

All training datasets are CC BY 4.0 or CC0. See `documentations/citations.md` for full citation requirements.

Key citations:
- DUT Anti-UAV: Zhao et al., IEEE TITS 2022. DOI: 10.1109/TITS.2022.3177627
- WOSDETC Challenge: Coluccia et al., IEEE ICASSP 2023. DOI: 10.1109/ICASSP49357.2023.10433921
