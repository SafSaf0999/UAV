# Anti-UAV Detection System — Paper Summary
> Structured extraction from 6 provided PDFs. Each entry includes: full title, authors, venue/year, 2–3 key talking points with chapter mapping, and a suggested BibTeX key.

---

## UAV-report.pdf — Special Analysis

**Is this a partner's version of the same anti-UAV report?**

No. `UAV-report.pdf` is **not** a partner's version of the same project report. It is a standalone 2005 academic/policy paper by Eugene Miasnikov from the Center for Arms Control, Energy and Environmental Studies at the Moscow Institute of Physics and Technology (MIPT). It is a **threat-analysis document**, not a technical detection system report.

**Chapters / Structure:**
- Introduction
- Terms and Definitions
- Potential Terrorist Targets and Possible Damage
- How May Terrorists Acquire UAVs and What Types Represent the Highest Danger?
  - Military UAVs
  - UAVs for Civilian Applications
  - Conversion of Private Airplanes into UAVs
  - Self-made and Commercial Model Airplanes
  - Assessment of Technical Characteristics of a Mini-UAV
  - Mini-UAV Control and Desired Accuracy of Payload Delivery
  - Manual Remote Control at a Distance of Direct Vision
  - Automatic Control Regime
  - Principle Schemes of Mini-UAV Flight Control Systems
- Existing Air Defenses Against Terrorist Mini-UAVs
- Conclusions
- Appendix: Media Reports of Terrorist Attempts to Employ UAVs

**Useful content for the anti-UAV detection report:**
- Establishes the threat motivation (Ch1 Introduction): why anti-UAV systems are needed, with documented real-world terrorist UAV incidents (Aum Shinrikyo, al-Qaeda, FARC, Palestinian groups).
- Characterizes the adversarial UAV profile (Ch2 Literature Review): small propeller-driven mini-UAVs, low-altitude flight, GPS-guided or RC-controlled, covert launch, 1–15 kg payload capacity — directly defining the detection target.
- Highlights the weakness of existing air defenses against low-flying mini-UAVs (Ch1/Ch2): conventional radar and SAM systems are ineffective against small, slow, low-altitude UAVs, motivating vision-based detection approaches.

---

## Paper 1 — A Multifaceted Look at Starlink Performance

**Full Title:** A Multifaceted Look at Starlink Performance  
**Authors:** Nitinder Mohan, Andrew E. Ferguson, Hendrik Cech  
**Venue/Year:** Technical University of Munich / University of Edinburgh — (~2022–2023)  
**BibTeX Key:** `mohan2023starlink`

### Talking Points

**1. LEO satellite networks introduce globally synchronized latency spikes that affect real-time applications**
→ Chapter: **Ch1 — Introduction**

Starlink's "15-second reconfiguration intervals" cause substantial, predictable latency and throughput variations across all users simultaneously. For a distributed anti-UAV system relying on satellite backhaul to relay detection alerts, these periodic disruptions could delay time-critical notifications. This motivates designing the system with local edge processing (on-node inference) rather than depending on remote connectivity for real-time decisions.

**2. Starlink performance is comparable to 5G cellular for latency-sensitive applications**
→ Chapter: **Ch2 — Literature Review**

The paper benchmarks Starlink against 5G and fiber for Zoom conferencing and cloud gaming, finding comparable real-time performance. For anti-UAV systems deployed in remote or rural areas where 5G is unavailable, Starlink represents a viable backhaul option for transmitting detection events, video streams, or model updates to a central control server.

**3. Inter-satellite links give remote users better performance than terrestrial networks**
→ Chapter: **Ch1 — Introduction**

Starlink's inter-satellite connections allow remote users to achieve better Internet service than terrestrial alternatives. Anti-UAV deployments in border regions, military perimeters, or rural infrastructure are precisely the environments where terrestrial connectivity is weakest, positioning LEO satellite connectivity as a practical communication layer for geographically distributed sensor nodes.

---

## Paper 2 — NB-IoT vs. LoRaWAN: An Experimental Evaluation for Industrial Applications

**Full Title:** NB-IoT Versus LoRaWAN: An Experimental Evaluation for Industrial Applications  
**Authors:** Massimo Ballerini, Tommaso Polonelli, Davide Brunelli, Michele Magno, Luca Benini  
**Venue/Year:** *IEEE Transactions on Industrial Informatics*, Vol. 16, No. 12, pp. 7802–7811, 2020 (doi: 10.1109/TII.2020.2987423)  
**BibTeX Key:** `ballerini2020nbiot`

### Talking Points

**1. LoRaWAN outperforms NB-IoT in energy consumption for low-throughput sensor nodes**
→ Chapter: **Ch2 — Literature Review**

For a 36-byte payload at DR2/Medium coverage, LoRaWAN's energy per byte is 10× lower than NB-IoT. Anti-UAV sensor nodes that transmit small detection alerts (bounding box coordinates, confidence scores, timestamps) match this low-throughput profile exactly. LoRaWAN is therefore the preferred LPWAN technology for battery-powered distributed detection nodes where energy budget is constrained.

**2. NB-IoT is superior when guaranteed delivery is required or payloads are large**
→ Chapter: **Ch2 — Literature Review**

NB-IoT provides QoS guarantees that LoRaWAN lacks, and for 396-byte payloads its energy per byte is 11× lower than LoRaWAN. For anti-UAV nodes that must transmit compressed video thumbnails or larger detection metadata, NB-IoT becomes the better choice — and its guaranteed delivery is critical for security-critical alert systems where missed messages are unacceptable.

**3. NB-IoT active time grows up to 3× with degrading signal coverage — must be factored into node placement**
→ Chapter: **Ch3 — Methodology**

NB-IoT's active transmission time increases dramatically from good coverage (−80 dBm RSSI) to bad coverage (−130 dBm RSSI), directly increasing energy consumption. For anti-UAV nodes deployed in areas with variable cellular coverage, this variability must be factored into power budget calculations and node placement methodology.

---

## Paper 3 — Vision-Based UAV Detection under Adverse Weather Conditions

**Full Title:** Vision-Based UAV Detection under Adverse Weather Conditions  
**Authors:** Adnan Munir, Abdul Jabbar Siddiqui, Saeed Anwar, Aiman El-Maleh, Ayaz H. Khan, Aqsa Rehman  
**Venue/Year:** KFUPM / Australian National University — (~2023–2024)  
**BibTeX Key:** `munir2024adverse`

### Talking Points

**1. Adverse weather causes catastrophic performance degradation in all tested YOLO-family detectors**
→ Chapter: **Ch1 — Introduction**

YOLOv5m mAP50 drops from 95.6% (clean) to 47.9% under torrential rain and to 21.9% under high motion blur. These numbers establish that standard YOLO models trained only on clean data are not deployment-ready for outdoor anti-UAV systems, directly motivating weather-robust training strategies.

**2. YOLOv5m is the top-performing model across all conditions — clean and adverse**
→ Chapter: **Ch2 — Literature Review**

On the Complex-Background Dataset (10,000 images with urban/natural backgrounds and flying birds): YOLOv5m = 95.6% mAP50, YOLOv8m = 91.8%, YOLO-NASs = 88.17%, RetinaNet = 84.39%, Faster-RCNN = 82.41%. YOLOv5m is also the fastest at 7.1 ms/image. This benchmark provides a concrete baseline for comparing YOLO-based anti-UAV detectors.

**3. Training on an Augmented Complex-Background Dataset (ACBD) dramatically recovers adverse-weather performance**
→ Chapter: **Ch3 — Methodology**

The ACBD mixes clean images with 33% noisy + 33% motion-blurred + 34% rainy samples. Enhanced YOLOv5m improves torrential rain mAP50 from 47.9% to 83.3% (+35.4 pp) while clean-data mAP50 drops only marginally (95.6% → 94.6%). This augmentation strategy is directly applicable to training a robust anti-UAV detector for real-world outdoor deployment.

---

## Paper 4 — Vision-Based UAV Detection Models for Small-Edge Devices

**Full Title:** Vision-Based UAV Detection Models for Small-Edge Devices  
**Authors:** Iryna Yurchuk, Taras Semenchenko  
**Venue/Year:** Taras Shevchenko National University of Kyiv — (~2024)  
**BibTeX Key:** `yurchuk2024edge`

### Talking Points

**1. Small UAV targets (average area ratio 0.013) in ground-to-sky perspectives are the primary detection challenge**
→ Chapter: **Ch1 — Introduction**

The authors annotated ~2,000 images capturing small UAV targets with an average area ratio of 0.013 (drone occupies only 1.3% of the image area), viewed from ground-to-sky angles. This is the exact scenario for a fixed ground-based anti-UAV detection system, motivating specialized architectures and training data that standard benchmarks do not address.

**2. RT-DETR achieves the highest precision (0.971 mAP) but lightweight YOLO variants are more practical for edge deployment**
→ Chapter: **Ch2 — Literature Review**

RT-DETR achieves 0.971 mAP@50 using its transformer-based multi-scale feature processing. However, lightweight YOLO-based models provide higher throughput (FPS) on low-power hardware. For a distributed anti-UAV system with many edge nodes, the YOLO family's inference speed advantage outweighs RT-DETR's marginal accuracy gain.

**3. Freezing ~80% of YOLO layers and fine-tuning only the detection head yields the best transfer learning results**
→ Chapter: **Ch3 — Methodology**

For YOLO-family models, freezing approximately 80% of the backbone layers and fine-tuning only the final detection layers produced the best accuracy-efficiency trade-off on their small UAV dataset. This is a critical finding for adapting pre-trained YOLO models to domain-specific anti-UAV datasets with limited labeled data.

---

## Paper 5 — Vision-Based Drone Detection in Complex Environments: A Survey

**Full Title:** Vision-Based Drone Detection in Complex Environments: A Survey  
**Authors:** Ziyi Liu, Pei An, You Yang, Shaohua Qiu, Qiong Liu, Xinghua Xu  
**Venue/Year:** (~2024)  
**BibTeX Key:** `liu2024survey`

### Talking Points

**1. Four core challenge categories define the drone detection problem: data acquisition, background complexity, imaging environment, and algorithm efficiency**
→ Chapter: **Ch1 — Introduction**

The survey organizes the field around four systematic challenge areas: data acquisition difficulties, background and drone characteristics (small size, motion blur), imaging environment factors (weather, lighting, sensor modality), and algorithm efficiency constraints (real-time requirements, edge hardware). This taxonomy provides a structured framework for the Introduction chapter.

**2. Deep learning methods (UIU-Net, DNA-Net, RepISD-Net) dramatically outperform traditional methods on infrared small-target datasets**
→ Chapter: **Ch2 — Literature Review**

On SIRST: UIU-Net achieves the highest IoU (78.25) and perfect Pd (100). On NUDT-SIRST: RepISD-Net achieves the best IoU (89.44). DNA-Net achieves the lowest false alarm rates across both datasets (Fa = 2.51 on SIRST). These benchmarks establish the state-of-the-art for infrared drone detection, relevant to the thermal imaging channel of an anti-UAV system.

**3. Multi-modal fusion (visible + infrared) is the recommended solution for weather-robust drone detection**
→ Chapter: **Ch1 — Introduction / Ch3 — Methodology**

The survey identifies multi-modal fusion as the primary solution to imaging environment challenges (fog, rain, low light). Visible cameras fail in adverse weather; infrared cameras are unaffected by lighting but struggle with thermal clutter. Fusing both modalities provides complementary coverage, directly motivating a dual-channel (RGB + thermal) architecture.

---

## Paper 6 — Threat of Terrorism Using Unmanned Aerial Vehicles: Technical Aspects

**Full Title:** Threat of Terrorism Using Unmanned Aerial Vehicles: Technical Aspects  
**Authors:** Eugene Miasnikov  
**Venue/Year:** Center for Arms Control, Energy and Environmental Studies, Moscow Institute of Physics and Technology (MIPT), 2005 (translated to English March 2005; supported by Ploughshares Fund and MacArthur Foundation)  
**BibTeX Key:** `miasnikov2005uav`

### Talking Points

**1. Existing air defenses are largely ineffective against small, low-flying mini-UAVs — motivating dedicated detection systems**
→ Chapter: **Ch1 — Introduction**

The paper's section "Existing Air Defenses Against Terrorist Mini-UAVs" explicitly documents that conventional radar systems and surface-to-air missiles (SAMs) are poorly suited to detecting and intercepting small, slow, low-altitude propeller-driven UAVs. This gap in traditional air defense directly motivates the need for dedicated vision-based and multi-sensor anti-UAV detection systems — the core justification for the project.

**2. The adversarial UAV profile is well-defined: small (1–15 kg), GPS/RC-guided, low-altitude, covert**
→ Chapter: **Ch2 — Literature Review**

The paper characterizes the threat UAV as a small propeller-driven model airplane (1–15 kg payload capacity), capable of GPS-guided or manual RC flight, operating at low altitude (100–300 m), and easily assembled from commercial components. This profile defines the detection target for the anti-UAV system: small cross-section, low radar signature, low thermal signature, requiring visual/optical detection methods.

**3. Documented real-world terrorist UAV incidents (1995–2004) establish the operational threat context**
→ Chapter: **Ch1 — Introduction**

The appendix catalogs verified incidents: Aum Shinrikyo's 1995 RC helicopter chemical dispersal attempt, al-Qaeda's 2001 explosive drone plot at the G-8 summit, FARC's 2002 RC aircraft cache, and a 2004 Israeli-foiled UAV explosive attack. These cases provide concrete historical evidence that the anti-UAV threat is not theoretical, strengthening the motivation section of the report.

---

## Cross-Paper Summary Table

| # | Paper | Authors | Venue/Year | BibTeX Key | Most Relevant Chapter |
|---|---|---|---|---|---|
| UAV-report | Threat of Terrorism Using UAVs: Technical Aspects | Miasnikov | MIPT, 2005 | `miasnikov2005uav` | Ch1 (Introduction), Ch2 (Lit Review) |
| 1 | A Multifaceted Look at Starlink Performance | Mohan, Ferguson, Cech | TUM/UoE, ~2023 | `mohan2023starlink` | Ch1 (Introduction) |
| 2 | NB-IoT vs. LoRaWAN: Experimental Evaluation | Ballerini et al. | IEEE Trans. Ind. Informatics, 2020 | `ballerini2020nbiot` | Ch2 (Lit Review), Ch3 (Methodology) |
| 3 | Vision-Based UAV Detection under Adverse Weather | Munir et al. | KFUPM/ANU, ~2024 | `munir2024adverse` | Ch1 (Intro), Ch2 (Lit Review), Ch3 (Methodology) |
| 4 | Vision-Based UAV Detection for Small-Edge Devices | Yurchuk, Semenchenko | Kyiv Univ., ~2024 | `yurchuk2024edge` | Ch1 (Intro), Ch3 (Methodology) |
| 5 | Vision-Based Drone Detection: A Survey | Liu et al. | ~2024 | `liu2024survey` | Ch1 (Intro), Ch2 (Lit Review), Ch3 (Methodology) |

---

## Suggested BibTeX Entries

```bibtex
@techreport{miasnikov2005uav,
  title       = {Threat of Terrorism Using Unmanned Aerial Vehicles: Technical Aspects},
  author      = {Miasnikov, Eugene},
  institution = {Center for Arms Control, Energy and Environmental Studies, Moscow Institute of Physics and Technology},
  year        = {2005},
  note        = {Translated into English, March 2005. Supported by the Ploughshares Fund and MacArthur Foundation.}
}

@article{mohan2023starlink,
  title       = {A Multifaceted Look at Starlink Performance},
  author      = {Mohan, Nitinder and Ferguson, Andrew E. and Cech, Hendrik},
  year        = {2023},
  institution = {Technical University of Munich and University of Edinburgh}
}

@article{ballerini2020nbiot,
  title   = {{NB-IoT} Versus {LoRaWAN}: An Experimental Evaluation for Industrial Applications},
  author  = {Ballerini, Massimo and Polonelli, Tommaso and Brunelli, Davide and Magno, Michele and Benini, Luca},
  journal = {IEEE Transactions on Industrial Informatics},
  volume  = {16},
  number  = {12},
  pages   = {7802--7811},
  year    = {2020},
  doi     = {10.1109/TII.2020.2987423}
}

@article{munir2024adverse,
  title       = {Vision-Based {UAV} Detection under Adverse Weather Conditions},
  author      = {Munir, Adnan and Siddiqui, Abdul Jabbar and Anwar, Saeed and El-Maleh, Aiman and Khan, Ayaz H. and Rehman, Aqsa},
  year        = {2024},
  institution = {King Fahd University of Petroleum and Minerals}
}

@article{yurchuk2024edge,
  title       = {Vision-Based {UAV} Detection Models for Small-Edge Devices},
  author      = {Yurchuk, Iryna and Semenchenko, Taras},
  year        = {2024},
  institution = {Taras Shevchenko National University of Kyiv}
}

@article{liu2024survey,
  title  = {Vision-Based Drone Detection in Complex Environments: A Survey},
  author = {Liu, Ziyi and An, Pei and Yang, You and Qiu, Shaohua and Liu, Qiong and Xu, Xinghua},
  year   = {2024}
}
```
