# Dataset References and Download Instructions

This file documents all datasets used in the project, their licenses, citations,
and how to re-acquire them if needed.

---

## RGB Datasets (currently on disk)

### Birds.v1i.yolov8 — 3,404 images
- **License:** CC BY 4.0
- **Source:** Roboflow Universe
- **URL:** https://universe.roboflow.com/birds-detection/birds-v1i
- **Citation:**
  ```
  Roboflow User, "Birds Dataset," Roboflow Universe, 2022.
  https://universe.roboflow.com/birds-detection/birds-v1i
  ```
- **Download:**
  ```
  python scripts/download_datasets.py  # or via Roboflow API
  ```

---

### anti-uav — 19,849 images (2,850 used, capped for balance)
- **License:** CC BY 4.0
- **Source:** Roboflow Universe (yogith-nams8)
- **URL:** https://universe.roboflow.com/yogith-nams8/anti-uav-s8wri
- **Citation:**
  ```
  yogith-nams8, "Anti-UAV Dataset," Roboflow Universe, 2022.
  https://universe.roboflow.com/yogith-nams8/anti-uav-s8wri
  ```

---

### fixed-wing-uav — 554 images
- **License:** CC0 (Public Domain)
- **Source:** Kaggle (nyahmet)
- **URL:** https://www.kaggle.com/datasets/nyahmet/fixed-wing-uav
- **Citation:**
  ```
  nyahmet, "Fixed Wing UAV Dataset," Kaggle, 2022.
  https://www.kaggle.com/datasets/nyahmet/fixed-wing-uav
  ```

---

### uavs — 9,262 images
- **License:** CC BY 4.0
- **Source:** Roboflow Universe (uavs-7l7kv)
- **URL:** https://universe.roboflow.com/uavs-7l7kv/uavs-vqpqt
- **Citation:**
  ```
  uavs-7l7kv, "UAVs Dataset," Roboflow Universe, 2022.
  https://universe.roboflow.com/uavs-7l7kv/uavs-vqpqt
  ```

---

### yolo-exp — 7,291 images
- **License:** CC BY 4.0
- **Source:** Roboflow Universe (dronesbird)
- **URL:** https://universe.roboflow.com/dronesbird/yolo-exp
- **Citation:**
  ```
  dronesbird, "Drone vs Bird Dataset," Roboflow Universe, 2022.
  https://universe.roboflow.com/dronesbird/yolo-exp
  ```

---

### uavdetector — 2,536 images
- **License:** CC BY 4.0
- **Source:** Roboflow Universe (sihadenemeler)
- **URL:** https://universe.roboflow.com/sihadenemeler/uavdetector
- **Citation:**
  ```
  sihadenemeler, "UAV Detector Dataset," Roboflow Universe, 2022.
  https://universe.roboflow.com/sihadenemeler/uavdetector
  ```

---

## RGB Datasets (deleted — re-downloadable)

### DUT Anti-UAV — 3.7 GB, 20 videos, 24,804 frames
- **License:** Research use only (IEEE-TITS 2022)
- **Paper:** Zhao et al., "Vision-Based Anti-UAV Detection and Tracking," IEEE TITS, 2022.
  DOI: https://doi.org/10.1109/TITS.2022.3177627
- **Download:** https://github.com/wangdongdut/DUT-Anti-UAV
- **Citation:**
  ```bibtex
  @article{zhao2022dutantiuav,
    title   = {Vision-Based Anti-UAV Detection and Tracking},
    author  = {Zhao, Jian and others},
    journal = {IEEE Transactions on Intelligent Transportation Systems},
    year    = {2022},
    doi     = {10.1109/TITS.2022.3177627}
  }
  ```

---

## Thermal Datasets (currently on disk)

### SIDD — Shandong Infrared Drone Dataset — 4,737 images
- **Location:** `thermal_datasets/SIDD-main/`
- **License:** Research use
- **Scenes:** city, mountain, sea, sky (640×512 LWIR)
- **Format:** COCO JSON annotations
- **Paper:** Referenced in Delleji et al. (2025)
- **Citation:**
  ```bibtex
  @dataset{sidd2023,
    title  = {Shandong Infrared Drone Dataset (SIDD)},
    year   = {2023},
    note   = {4,737 annotated thermal infrared drone images across 4 scenes}
  }
  ```

---

### MOT_IR_sequences — Anti-MUAV1 — 1.3 GB, 15 sequences
- **Location:** `thermal_datasets/MOT_IR_sequences/`
- **License:** Research use
- **Description:** Multi-object thermal IR tracking sequences with multiple simultaneous drone tracks per sequence
- **Format:** Per-frame JPEG + `groundtruth_N.txt` (x1,y1,x2,y2,out_of_view)
- **Used for:** Evaluation only (never trained on)

---

### CST-Anti-UAV-main — 16 MB
- **Location:** `thermal_datasets/CST-Anti-UAV-main/`
- **License:** Research use
- **Description:** 220 thermal IR sequences (annotations only, frames not downloaded)
- **Status:** Pending full download

---

## Thermal Datasets (deleted — have zip / re-downloadable)

### Anti-UAV410 — 9.9 GB, 410 sequences, 438K+ frames
- **Status:** ZIP file retained locally. Re-extract when needed.
- **License:** Research use
- **Paper:** "Anti-UAV410: A Thermal Infrared Benchmark and Customized Scheme for Tracking Drones in the Wild," 2023.
- **URL:** https://github.com/ZhaoJingjing713/Anti-UAV410
- **Citation:**
  ```bibtex
  @inproceedings{antiuav410_2023,
    title     = {Anti-UAV410: A Thermal Infrared Benchmark and Customized Scheme
                 for Tracking Drones in the Wild},
    year      = {2023},
    note      = {410 sequences, 438K+ manually annotated bounding boxes,
                 10 challenge attributes}
  }
  ```
- **Re-extract:**
  ```fish
  cd thermal_datasets
  unzip /path/to/Anti-UAV410.zip
  ```

---

## Derived Datasets (deleted — regenerate with scripts)

These were generated from the source datasets above and can be fully recreated:

| Folder | Source | Script |
|---|---|---|
| `finetune_2class/` | BirdDrone-2C + DUT pseudo-labels | `scripts/build_finetune_datasets.py` |
| `finetune_3class/` | BirdDrone-3C + DUT pseudo-labels | `scripts/build_finetune_datasets.py` |
| `dut_pseudolabels_2class/` | DUT Anti-UAV + BirdDrone-2C model | `scripts/build_dut_pseudolabels.py` |
| `dut_pseudolabels_3class/` | DUT Anti-UAV + BirdDrone-3C model | `scripts/build_dut_pseudolabels.py` |
| `thermal_merged/` | SIDD-main (processed) | `scripts/prepare_thermal_dataset.py` |
| `combined_finetune/` | SIDD + Anti-UAV410 train split | `scripts/prepare_combined_dataset.py` |

To regenerate all derived datasets:
```fish
source .venv/bin/activate.fish
python scripts/prepare_thermal_dataset.py   # thermal_merged
python scripts/build_dut_pseudolabels.py    # dut_pseudolabels_*
python scripts/build_finetune_datasets.py   # finetune_*
```
