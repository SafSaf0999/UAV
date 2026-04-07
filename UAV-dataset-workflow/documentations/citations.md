# Dataset & Challenge Citations

All datasets, benchmarks, and challenges referenced in this project and report.

**Citation requirements summary:**
- CC BY 4.0 (all Roboflow datasets): attribution required — name + source URL
- CC0 (fixed-wing-uav Kaggle): no attribution required, credited for reproducibility
- DUT Anti-UAV: academic use, cite the IEEE-TITS paper
- WOSDETC: non-commercial research, cite the ICASSP paper

---

---

## Datasets Used for Training

### Birds.v1i.yolov8
- **Source:** Roboflow Universe
- **URL:** https://universe.roboflow.com/datasets-gjngu/birds-wnak6-pqzrv/dataset/1
- **License:** CC BY 4.0
- **Images:** 3,404 (train + valid)
- **Class:** bird
- **Citation:**
  ```
  @dataset{birds_v1_yolov8,
    title   = {Birds Dataset},
    author  = {Roboflow User},
    year    = {2025},
    url     = {https://universe.roboflow.com/datasets-gjngu/birds-wnak6-pqzrv},
    license = {CC BY 4.0}
  }
  ```

### fixed-wing-uav (nyahmet)
- **Source:** Kaggle
- **URL:** https://www.kaggle.com/datasets/nyahmet/fixed-wing-uav-dataset
- **License:** CC0 (Public Domain)
- **Images:** 554
- **Class:** fixed-wing UAV
- **Citation:**
  ```
  @dataset{fixed_wing_uav_nyahmet,
    title   = {Fixed Wing UAV Dataset},
    author  = {nyahmet},
    year    = {2022},
    url     = {https://www.kaggle.com/datasets/nyahmet/fixed-wing-uav-dataset},
    license = {CC0}
  }
  ```

### anti-uav (yogith-nams8)
- **Source:** Roboflow Universe
- **URL:** https://universe.roboflow.com/yogith-nams8/anti-uav-s8wri/dataset/1
- **License:** CC BY 4.0
- **Images:** 19,849 (2,850 used, capped)
- **Class:** UAV
- **Citation:**
  ```
  @dataset{anti_uav_roboflow,
    title   = {Anti-UAV Dataset},
    author  = {yogith-nams8},
    year    = {2023},
    url     = {https://universe.roboflow.com/yogith-nams8/anti-uav-s8wri},
    license = {CC BY 4.0}
  }
  ```

### uavs (uavs-7l7kv)
- **Source:** Roboflow Universe
- **URL:** https://universe.roboflow.com/uavs-7l7kv/uavs-vqpqt/dataset/2
- **License:** CC BY 4.0
- **Images:** 9,262
- **Class:** drone
- **Citation:**
  ```
  @dataset{uavs_roboflow,
    title   = {UAVs Dataset},
    author  = {uavs-7l7kv},
    year    = {2023},
    url     = {https://universe.roboflow.com/uavs-7l7kv/uavs-vqpqt},
    license = {CC BY 4.0}
  }
  ```

### yolo-exp / dronesbird
- **Source:** Roboflow Universe
- **URL:** https://universe.roboflow.com/dronesbird/yolo-exp/dataset/5
- **License:** CC BY 4.0
- **Images:** 7,291
- **Classes:** Bird, drone
- **Citation:**
  ```
  @dataset{yolo_exp_dronesbird,
    title   = {YOLO-exp Drones and Birds Dataset},
    author  = {dronesbird},
    year    = {2023},
    url     = {https://universe.roboflow.com/dronesbird/yolo-exp},
    license = {CC BY 4.0}
  }
  ```

### uavdetector (sihadenemeler)
- **Source:** Roboflow Universe
- **URL:** https://universe.roboflow.com/sihadenemeler/uavdetector/dataset/1
- **License:** CC BY 4.0
- **Images:** 2,536
- **Class:** fixed wing UAV
- **Citation:**
  ```
  @dataset{uavdetector_roboflow,
    title   = {UAV Detector Dataset},
    author  = {sihadenemeler},
    year    = {2023},
    url     = {https://universe.roboflow.com/sihadenemeler/uavdetector},
    license = {CC BY 4.0}
  }
  ```

### Drone vs Bird v3 (old training reference)
- **Source:** Roboflow Universe
- **URL:** https://universe.roboflow.com/datasets-gjngu/drone-vs-bird-v3-qymly/dataset/1
- **License:** CC BY 4.0
- **Images:** 2,528
- **Classes:** Bird, Drone
- **Citation:**
  ```
  @dataset{drone_vs_bird_v3,
    title   = {Drone vs Bird v3},
    author  = {Roboflow User},
    year    = {2026},
    url     = {https://universe.roboflow.com/datasets-gjngu/drone-vs-bird-v3-qymly},
    license = {CC BY 4.0}
  }
  ```

---

## Benchmark Datasets & Challenges

### DUT Anti-UAV (Detection Benchmark)
- **Paper:** Jie Zhao, Jingshu Zhang, Dongdong Li, Dong Wang. "Vision-based Anti-UAV Detection and Tracking." *IEEE Transactions on Intelligent Transportation Systems*, 2022.
- **arXiv:** https://arxiv.org/abs/2205.10851
- **GitHub:** https://github.com/wangdongdut/DUT-Anti-UAV
- **Modality:** RGB daytime video
- **Task:** UAV detection + tracking
- **Published baselines:** YOLOX 0.720, Cascade-RCNN 0.680, ATSS 0.665, Faster R-CNN 0.621, SSD 0.487
- **Citation:**
  ```
  @article{zhao2022dutantiuav,
    title   = {Vision-based Anti-UAV Detection and Tracking},
    author  = {Zhao, Jie and Zhang, Jingshu and Li, Dongdong and Wang, Dong},
    journal = {IEEE Transactions on Intelligent Transportation Systems},
    year    = {2022},
    doi     = {10.1109/TITS.2022.3177627}
  }
  ```

### Anti-UAV Workshop & Challenge (CVPR)
- **Website:** https://anti-uav.github.io
- **Editions:** CVPR 2020 (1st), ICCV 2021 (2nd), CVPR 2023 (3rd), CVPR 2025 (4th)
- **Modality:** Thermal infrared video (NOT RGB)
- **Task:** Single UAV tracking, detection+tracking, multi-UAV tracking
- **Dataset:** 410 high-quality thermal IR video sequences
- **Note:** Not directly applicable to our RGB detection models
- **Citation:**
  ```
  @inproceedings{antiuav_cvpr2023,
    title     = {Anti-UAV410: A Thermal Infrared Benchmark and Customized Scheme
                 for Tracking Drones in the Wild},
    author    = {Huang, Bo and Li, Jianan and Chen, Junjie and Wang, Gang and
                 Zhao, Jian and Xu, Tingfa},
    booktitle = {IEEE/CVF Conference on Computer Vision and Pattern Recognition},
    year      = {2023}
  }
  ```

### Drone-vs-Bird Detection Grand Challenge (WOSDETC)
- **Website:** https://github.com/wosdetc/challenge
- **Editions:** AVSS 2017, 2019, 2020, 2021; ICIAP 2022; ICASSP 2023; IJCNN 2025
- **Modality:** RGB video
- **Task:** Small drone detection, bird/drone discrimination
- **Access:** Email wosdetc@googlegroups.com (data usage agreement required)
- **Published top results:**
  - OBSS (1st, ICIAP 2021): F1 ≈ 0.91
  - YOLOv8 multi-scale (top-3, IJCNN 2025): F1 ≈ 0.88
- **Citation:**
  ```
  @inproceedings{coluccia2023wosdetc,
    title     = {Drone-vs-Bird Detection Grand Challenge at ICASSP 2023},
    author    = {Coluccia, Angelo and Fascista, Alessio and Sommer, Lars and
                 Schumann, Arne and Dimou, Anastasios and Zarpalas, Dimitrios
                 and Sharma, Nabin},
    booktitle = {IEEE International Conference on Acoustics, Speech and
                 Signal Processing (ICASSP)},
    year      = {2023},
    doi       = {10.1109/ICASSP49357.2023.10433921}
  }
  ```

---

## Model & Architecture References

### YOLO26 (Ultralytics)
- **Release:** September 2025
- **Features:** NMS-free end-to-end inference, MuSGD optimizer, STAL (Small-Target-Aware Label Assignment), DFL removal
- **URL:** https://github.com/ultralytics/ultralytics
- **Citation:**
  ```
  @software{ultralytics_yolo26,
    title   = {YOLO26: NMS-Free End-to-End Detection},
    author  = {Ultralytics},
    year    = {2025},
    url     = {https://github.com/ultralytics/ultralytics}
  }
  ```

### YOLOv12n (Ultralytics)
- **Used in:** Baseline run (run_1class_yolov12n_rtx2070_100ep)
- **URL:** https://github.com/ultralytics/ultralytics
- **Citation:** Same as above.

### YOLOBirDrone
- **Paper:** Dapinder Kaur, Neeraj Battish, Arnav Bhavsar, Shashi Poddar. "YOLOBirDrone: Dataset for Bird vs Drone Detection and Classification and a YOLO based enhanced learning architecture." *arXiv:2601.08319*, 2025.
- **arXiv:** https://arxiv.org/abs/2601.08319
- **Citation:**
  ```
  @article{kaur2025yolobirdrone,
    title   = {YOLOBirDrone: Dataset for Bird vs Drone Detection and
               Classification and a YOLO based enhanced learning architecture},
    author  = {Kaur, Dapinder and Battish, Neeraj and Bhavsar, Arnav
               and Poddar, Shashi},
    journal = {arXiv preprint arXiv:2601.08319},
    year    = {2025}
  }
  ```

### SimD3 (Synthetic Drone Dataset)
- **Paper:** "A Synthetic drone Dataset with Payload and Bird Distractor Modeling for Robust Detection." *arXiv:2601.14742*, 2025.
- **arXiv:** https://arxiv.org/abs/2601.14742
- **Citation:**
  ```
  @article{simd3_2025,
    title   = {A Synthetic drone Dataset with Payload and Bird Distractor
               Modeling for Robust Detection},
    journal = {arXiv preprint arXiv:2601.14742},
    year    = {2025}
  }
  ```

### Multi-Scale YOLOv8 (IJCNN 2025 top-3)
- **Paper:** "Improving Small Drone Detection Through Multi-Scale Processing and Data Augmentation." *arXiv:2504.19347*, 2025.
- **arXiv:** https://arxiv.org/abs/2504.19347
- **Citation:**
  ```
  @article{multiscale_drone_2025,
    title   = {Improving Small Drone Detection Through Multi-Scale Processing
               and Data Augmentation},
    journal = {arXiv preprint arXiv:2504.19347},
    year    = {2025}
  }
  ```

---

## Notes on Dataset Licensing

All training datasets used in this project are licensed under CC BY 4.0 or CC0,
permitting use, redistribution, and adaptation with attribution.
The fixed-wing-uav dataset (CC0) requires no attribution but is credited above
for reproducibility. The DUT Anti-UAV dataset is available for research purposes
via Google Drive (no formal license stated — academic use implied by publication).
The WOSDETC challenge dataset requires a signed data usage agreement for
non-commercial research use.
