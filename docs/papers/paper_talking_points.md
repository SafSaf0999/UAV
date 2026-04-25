# Paper Talking Points for Anti-UAV Detection System Report (YOLO26s)

> Structured extraction of key talking points from 6 papers, mapped to report chapters:
> **Introduction** | **Literature Review** | **Methodology** | **Discussion**

---

## Paper 1 — Drone vs. Bird Detection: Deep Learning Algorithms and Results from a Grand Challenge

**Authors:** Angelo Coluccia, Alessio Fascista, Arne Schumann, Lars Sommer, Anastasios Dimou, Dimitrios Zarpalas, Miguel Méndez, et al.
**Venue/Year:** *Sensors*, MDPI — 2021 (doi: 10.3390/s21082824)

---

### Talking Points

**1. The drone-bird discrimination problem is a core unsolved challenge in visual UAV detection**
→ Chapter: **Introduction / Literature Review**

Drones and birds share the same low-altitude airspace and are visually similar at long range, making automated discrimination a hard open problem. The paper frames this as a grand challenge (Drone vs. Bird Detection Challenge, 3rd edition 2020), attracting 108 research groups globally. The dataset includes 8 drone types (fixed-wing and rotary) across varying backgrounds, weather, and camera motion — directly motivating the need for robust, generalizable detectors like YOLO26s.

---

**2. Small object size is the dominant difficulty factor — drones range from 15 to >1,000,000 pixels**
→ Chapter: **Introduction / Methodology**

The challenge dataset shows drone bounding boxes ranging from 15 px² to over 1,000,000 px², with the majority below 322 px². This extreme scale variance is the primary reason standard object detectors fail. The paper explicitly notes that "the small size and fast maneuvers make drones a difficult category of targets to be detected." This directly justifies multi-scale detection heads and anchor tuning in YOLO-based architectures.

---

**3. Custom anchor design for small drones significantly outperforms COCO-default anchors**
→ Chapter: **Methodology / Literature Review**

The Gradiant team (1st place, 80% AP) used Cascade R-CNN with ResNeXt-101 backbone and dynamically generated anchors fitted to the training bounding box distribution. Their custom anchors ensured >90% of ground-truth boxes had IoU > 0.5 with at least one anchor. The default COCO anchors model had the worst precision-recall performance. This validates the importance of domain-specific anchor tuning when adapting YOLO26s to UAV detection.

---

**4. Image tiling is an effective strategy for detecting small drones in high-resolution frames**
→ Chapter: **Methodology**

The Alexis team (2nd place, 79.8% AP) used YOLOv3-SPP with a 480 px image tiling strategy. Tiling at 480 px achieved 92.9% AP on known sequences vs. 89.1% at 640 px, while also reducing processing time (169 ms vs. 125 ms). The approach avoids the information loss from downscaling full HD frames, which is critical when drones occupy only 10–20 pixels. This technique is directly applicable to distributed camera nodes in an anti-UAV system.

---

**5. Multi-team performance comparison reveals complementary strengths across architectures**
→ Chapter: **Discussion**

Final challenge results: Gradiant (Cascade R-CNN) = 80.0% AP, Alexis (YOLOv3) = 79.8% AP, EagleDrone (Faster R-CNN) = 66.8% AP. The paper notes that the approaches perform "somewhat complementary" in terms of correct detection rate, false alarm rate, and average precision across different sequences. Moving-camera sequences and very distant drones were the hardest cases for all teams. This benchmarking context is useful for positioning YOLO26s performance in the Discussion chapter.

---

## Paper 2 — Radar-Based Target Tracking Using Deep Learning Approaches with Unscented Kalman Filter

**Authors:** Uwigize Patrick, S. Koteswara Rao, B. Omkar Lakshmi Jagan, Hari Mohan Rai, Saurabh Agarwal, Wooguil Pak
**Venue/Year:** *Applied Sciences*, MDPI — 2024, Vol. 14, No. 18332 (doi: 10.3390/app14188332)

---

### Talking Points

**1. Deep learning significantly improves noise covariance estimation in radar-based 3D tracking**
→ Chapter: **Literature Review**

The paper proposes replacing the traditional assumption of a known noise covariance matrix with a deep learning estimator. CNN, GRU, MLP, and LSTM are combined with the Unscented Kalman Filter (UKF) for 3D airborne target tracking. CNN outperformed all other approaches in Monte Carlo simulations, offering higher accuracy and faster convergence than conventional methods. This is relevant as a complementary sensor modality to vision-based detection in a distributed anti-UAV system.

**2. Radar tracking in aerial environments is inherently nonlinear and challenging**
→ Chapter: **Introduction / Literature Review**

The paper identifies key challenges: target size, speed, stealth materials, altitude, and shape all affect radar tracking accuracy. Small, fast-moving objects at high altitudes are harder to track than larger, slower ones. Stealth aircraft are more complex to track than non-stealth. This motivates the use of multi-modal sensing (radar + vision) in anti-UAV systems, where radar handles range/velocity and vision handles classification.

**3. The UKF outperforms EKF for nonlinear state estimation in aerial tracking**
→ Chapter: **Literature Review / Methodology**

The paper reviews EKF, UKF, Particle Filters, and Cubature Kalman Filter for nonlinear estimation. UKF is selected for its better handling of nonlinear measurement models (range, bearing, elevation from radar). When combined with CNN for noise estimation, the system achieves superior tracking accuracy. This is relevant context for any Kalman-filter-based tracking module that might complement YOLO26s detections in the distributed system.

**4. CNN-UKF fusion achieves the best 3D tracking performance among all tested architectures**
→ Chapter: **Discussion**

Among GRU-UKF, MLP-UKF, CNN-UKF, and LSTM-UKF, the CNN-UKF combination demonstrated the best performance in Monte Carlo simulations. The system was validated in Python with simulated radar measurements in range, bearing, and elevation. This result supports the use of CNN-based feature extraction as a general-purpose component in aerial surveillance pipelines, including the detection backbone of YOLO26s.

---

## Paper 3 — Real-Time Flying Object Detection with YOLOv8

**Authors:** Dillon Reis, Jacqueline Hong, Jordan Kupec, Ahmad Daoudi
**Venue/Year:** *arXiv:2305.09972v2* — Georgia Institute of Technology, 2024

---

### Talking Points

**1. A two-stage transfer learning strategy (generalized → refined) achieves state-of-the-art flying object detection**
→ Chapter: **Methodology / Literature Review**

The paper trains a generalized YOLOv8 model on 15,064 images across 40 flying object classes (mAP50 = 79.2%, mAP50-95 = 68.5%, 50 fps on 1080p), then transfer-learns to a 3-class refined model (drone, plane, helicopter) achieving mAP50 = 99.1%, mAP50-95 = 83.5%, 50 fps. This two-stage approach — learning abstract flying-object features first, then specializing — is directly applicable to training YOLO26s on a UAV-specific dataset.

**2. YOLOv8 medium model provides the best inference speed / accuracy trade-off for real-time 1080p detection**
→ Chapter: **Methodology**

Small, medium, and large YOLOv8 models have 11.1M, 25.9M, and 43.7M parameters respectively. The medium model achieves 50 fps on 1080p (total pipeline: 0.5 ms pre-process + 17.25 ms inference + 2 ms post-process = 19.75 ms). The jump in mAP50-95 from small to medium is 0.05, but only 0.002 from medium to large. This analysis directly informs the model size selection for YOLO26s deployment on edge nodes.

**3. YOLOv8's CSPDarknet53 backbone with c2f modules enables multi-scale feature extraction for small aerial objects**
→ Chapter: **Methodology**

YOLOv8 uses CSPDarknet53 with four c2f (cross-stage partial with 2 feature maps) modules. Activation map analysis shows: shallow layers detect broad object shape (wings), middle layers localize components (cockpit, body), deep layers extract fine-grained textures. The model successfully detects a drone occupying only 0.026% of image area and a passenger airplane at 0.063% of image area. This architecture analysis supports the choice of YOLO-family models for small UAV detection.

**4. The refined model surpasses prior YOLO-based flying object detectors by a significant margin**
→ Chapter: **Discussion**

Comparison: Aydin et al. YOLOv5 = 90.40% mAP50, 91.8% Precision, 87.5% Recall at 31 fps. Al-Qubaydhi et al. YOLOv5 = 94.1% mAP50, 94.7% Precision, 92.5% Recall (single drone class). Rozantsev et al. = 84.9% AP (UAVs only). This paper's refined YOLOv8 = 99.1% mAP50, 98.7% Precision, 98.8% Recall at 50 fps. This positions YOLO26s within the broader YOLO evolution and provides concrete benchmarks for Discussion.

**5. Low inter-class variance between visually similar flying objects (e.g., F-14 vs. F-18, drone vs. bird) is a key failure mode**
→ Chapter: **Discussion / Methodology**

The confusion matrix shows the model most frequently misclassifies F-14 as F-18 due to similar wing shapes, rudders, and cockpit features. Activation maps confirm that the same fine-grained features are activated for both. For anti-UAV systems, the analogous problem is drone-vs-bird confusion. This motivates training on multi-class datasets that include birds as a negative class, which is a design decision relevant to YOLO26s dataset curation.

---

## Paper 4 — Good Data Beats More Data: Building a Thermal Air-Image Dataset for Ground-to-Air Surveillance

**Authors:** Tijeni Delleji, Feten Slimeni, Ahmed Siala
**Venue/Year:** Book chapter in *Transfer Learning – Unlocking the Power of Pretrained Models*, IntechOpen — 2025 (doi: 10.5772/intechopen.1011701)

---

### Talking Points

**1. Thermal imaging is essential for 24/7 drone detection in low-visibility conditions**
→ Chapter: **Introduction / Methodology**

Unlike RGB cameras, thermal cameras capture infrared radiation, enabling drone detection by heat signature regardless of lighting. The paper uses a dual-lens EO/IR PTZ camera (DH-TPC-PT8621C) with a 640×512 thermal sensor, ≤40 mK sensitivity, 8–14 µm LWIR spectral range, and 25 fps. This directly motivates the inclusion of a thermal imaging channel in the distributed anti-UAV system alongside visible-spectrum YOLO26s detection.

**2. Dataset quality — not quantity — is the primary determinant of YOLO model performance on thermal data**
→ Chapter: **Methodology / Discussion**

The paper's central thesis ("Good Data Beats More Data") is validated experimentally: after cleaning a 12,600-image dataset down to 10,200 images using perceptual hashing (phash, hash size 8, Hamming distance threshold), YOLOv11 precision and recall remained equivalent or improved. Removing near-duplicates, mislabeled samples, and low-quality images had no negative impact on model performance. This principle directly applies to the dataset curation strategy for YOLO26s training.

**3. Thermal-specific augmentation strategies are necessary to bridge the domain gap**
→ Chapter: **Methodology**

Standard RGB augmentations are insufficient for thermal data. The paper introduces four thermal-specific augmentations: (1) Thermal Blur (Gaussian convolution, σ-controlled), (2) Temperature Brightness Variability (pixel intensity ± ΔT·k), (3) Thermal Noise (Gaussian N(0, σn²)), and (4) Thermal CutMix (region replacement with λ mixing parameter). These augmentations simulate sensor imperfections, environmental temperature variation, and camera focus changes — all relevant to real-world deployment of the anti-UAV system.

**4. Existing public thermal datasets are inadequate for aerial drone detection**
→ Chapter: **Literature Review**

A survey of public thermal datasets reveals critical gaps: FLIR ADAS (automotive, no drone annotations), KAIST Multispectral (pedestrian detection), VAP thermal aerial dataset (<2000 frames, minimal diversity), ARL thermal dataset (no multi-altitude drone perspectives). None systematically address diurnal/seasonal variation, multi-altitude perspectives, or adversarial conditions (solar glare, precipitation). This gap justifies building a custom thermal dataset for the anti-UAV system.

**5. The dataset pipeline covers acquisition, augmentation, annotation, cleaning, and splitting**
→ Chapter: **Methodology**

The paper presents a reproducible 5-stage pipeline: (1) raw thermal video capture of 3 DJI UAVs (Phantom 4 Pro+, Matrice 600, Mavic 3) at 25 fps, (2) thermal augmentation via Roboflow, (3) bounding box annotation, (4) perceptual hash-based deduplication, (5) 80/20 train/validation split (4800/1200 from 6000 "seen" images) + 600 "unseen" test images. This structured pipeline is a direct reference for the data preparation methodology of YOLO26s.

---

## Paper 5 — Vision-Based Multi-Scale UAV Detection (KFUPM Master's Thesis)

**Authors:** Adnan Munir (Supervisor: Dr. Abdul Jabbar Siddiqui)
**Venue/Year:** M.Sc. Thesis, King Fahd University of Petroleum & Minerals (KFUPM), Dhahran, Saudi Arabia — December 2023

---

### Talking Points

**1. UAV detection under adverse weather (rain, noise, motion blur) is an understudied but critical problem**
→ Chapter: **Introduction / Literature Review**

The thesis is the first work to systematically benchmark UAV detection under adverse weather conditions. All prior work focused on clean images. The thesis introduces three weather-affected test sets: RTD (drizzle/heavy/torrential rain), ANTD (low/medium/high AWGN noise), and MBTD (low/medium/high motion blur), all derived from the Anti-UAV dataset. This directly motivates robustness requirements for YOLO26s deployed in outdoor anti-UAV systems.

**2. YOLOv5m consistently outperforms YOLOv8m, YOLO-NASs, Faster-RCNN, and RetinaNet under all adverse conditions**
→ Chapter: **Discussion / Literature Review**

On clean data: YOLOv5m = 95.6% mAP50, YOLOv8m = 91.8%, YOLO-NASs = 88.17%, Faster-RCNN = 82.41%, RetinaNet = 84.39%. Under torrential rain: YOLOv5m = 47.9% (−50.6%), YOLOv8m = 42.7% (−53.2%). Under high motion blur: YOLOv5m = 21.9% (−77.0%), YOLOv8m = 18.6% (−79.6%). YOLOv5m's consistent lead across all conditions makes it a strong baseline for comparison with YOLO26s.

**3. YOLO-RAW: a novel multi-scale UAV detector with SimAM attention and 4-head prediction**
→ Chapter: **Literature Review / Methodology**

YOLO-RAW extends YOLOv5 with: (1) an extra CBS+C3 block in the CSPDarknet53 backbone, (2) SPPF-Enhanced (SPP-Extended) module, (3) four SimAM (Simple, Parameter-Free Attention Module) blocks in the neck, (4) a fourth prediction head (P6) for large-scale objects via PANet extension. The model achieves 95.2% mAP50 on the Complex Background Dataset (CBD) and outperforms YOLOv5m on all weather-affected test sets, especially under motion blur where YOLOv5m fails to detect. This architecture is a direct reference point for YOLO26s design decisions.

**4. Training with weather-augmented data substantially improves robustness without sacrificing clean-data performance**
→ Chapter: **Methodology / Discussion**

Adding 33% noisy + 33% motion-blurred + 34% rainy images to the training set (Augmented CBD, 19,446 images) improved YOLOv5m's torrential rain performance from 47.9% to 83.3% mAP50, and high-blur performance from 21.9% to 66.8% — while clean-data mAP50 dropped only marginally from 95.6% to 94.6%. This demonstrates that weather augmentation is a low-cost, high-impact strategy for YOLO26s training.

**5. Vision-based detection has fundamental limitations vs. radar and RF: range <350 ft, bird confusion, illumination sensitivity**
→ Chapter: **Introduction / Discussion**

The thesis provides a comparative table of detection modalities: Acoustic (fails in noisy urban areas, range 25–30 ft), RF (range <1400 ft, requires line-of-sight), Radar (cannot detect small UAVs), Vision (range <350 ft, hard to distinguish UAVs from birds). Vision-based detection is preferred for its accuracy, lower cost, and ability to gather visual evidence, but its limitations motivate the multi-sensor fusion approach of the distributed anti-UAV system.

---

## Paper 6 — Deployment of Deep Neural Networks for Object Detection on Edge AI Devices with Runtime Optimization

**Authors:** Lukas Stäcker, Juncong Fei, Philipp Heidenreich, Frank Bonarens, Jason Rambach, Didier Stricker, Christoph Stiller
**Venue/Year:** *ICCV Workshops 2021* (Stellantis / DFKI / KIT)

---

### Talking Points

**1. TensorRT with Int8 quantization achieves ~4× inference speedup with minimal accuracy loss on edge AI hardware**
→ Chapter: **Methodology / Discussion**

On NVIDIA Jetson AGX Xavier (MAXN mode, ~50W), RetinaNet-18 inference times: Float32 = 104 ms, Float16 = 38 ms, Int8 = 25 ms (TensorRT). Float16 quantization has minimal impact on mAP (0.361 → 0.356 at mid resolution). Int8 with entropy calibration: mAP = 0.355, runtime = 25 ms. This quantization analysis directly informs the deployment strategy for YOLO26s on edge nodes (e.g., Jetson devices) in the distributed anti-UAV system.

**2. Input resolution has a larger impact on detection performance than quantization**
→ Chapter: **Methodology**

RetinaNet at low (416×736), mid (576×1024), and high (832×1472) resolution with Int8: mAP = 0.298, 0.355, 0.393 respectively. Runtime scales proportionally with pixel count. The paper recommends mid resolution + Int8 as the optimal trade-off. For YOLO26s, this suggests that maintaining adequate input resolution is more important than precision format when deploying on constrained edge hardware.

**3. Power supply mode significantly affects runtime on embedded systems**
→ Chapter: **Methodology / Discussion**

On Jetson AGX Xavier, the full detection pipeline (pre-process + inference + post-process) at mid resolution + Int8: MAXN (50W) = 31 ms, 30W = 44 ms, 15W = 56 ms, 10W = 107 ms. A 5× power reduction causes a 3.5× runtime increase. This is critical for battery-powered or solar-powered distributed anti-UAV nodes where power budget directly constrains detection latency.

**4. PyTorch → ONNX → TensorRT conversion pipeline enables C++ deployment of trained models**
→ Chapter: **Methodology**

The paper details the full deployment pipeline: train in PyTorch → export to ONNX (network tracing) → parse to TensorRT engine in C++ → deploy with ROS for sensor streaming. Data-dependent control-flow operations (NMS, thresholding) must be implemented separately in C++. TorchScript is an alternative but shows advantages only for fully-connected layers (e.g., PointPillars PFN). This pipeline is directly applicable to deploying YOLO26s on Jetson-based edge nodes in the distributed system.

**5. TensorRT outperforms TorchScript for convolutional layers; TorchScript is better for fully-connected layers**
→ Chapter: **Discussion**

For RetinaNet (conv-heavy): TensorRT Float32 = 104 ms vs. TorchScript Float32 = 210 ms (2× faster). For PointPillars PFN (FC-heavy): TorchScript outperforms TensorRT. This architectural insight is relevant when choosing the inference backend for YOLO26s, which is predominantly convolutional — making TensorRT the preferred deployment framework.

---

## Cross-Paper Summary Table

| Paper | Primary Contribution | Most Relevant Chapter |
|---|---|---|
| Coluccia et al. (Sensors 2021) | Drone vs. Bird challenge benchmark; custom anchors; image tiling | Intro, Lit Review, Methodology |
| Patrick et al. (Appl. Sci. 2024) | CNN-UKF fusion for radar 3D tracking | Lit Review, Discussion |
| Reis et al. (arXiv 2024) | YOLOv8 two-stage transfer learning; 99.1% mAP50 on drones | Methodology, Discussion |
| Delleji et al. (IntechOpen 2025) | Thermal dataset pipeline; data quality > data quantity | Methodology, Lit Review |
| Munir (KFUPM Thesis 2023) | YOLO-RAW; adverse weather benchmarking; YOLOv5m baseline | Lit Review, Methodology, Discussion |
| Stäcker et al. (ICCVW 2021) | Edge deployment; TensorRT Int8; power-runtime trade-off | Methodology, Discussion |
