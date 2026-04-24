
# Design Document: Report Chapter Expansion

## Overview

This document specifies the exact LaTeX edits required to expand four chapters
of `UAV/UAV-dataset-workflow/documentations/report_full.tex`. For each addition
the design records: (1) the insertion anchor — the exact existing LaTeX text
after which new content is inserted, (2) the full new LaTeX content, and
(3) new `\bibitem` entries. No existing content is modified or removed.

The six reference papers and their assigned citation keys are:

| Citation Key | Paper |
|---|---|
| `coluccia2021sensors` | Coluccia et al., *Sensors* 2021, doi:10.3390/s21082824 |
| `munir2023kfupm` | Munir, KFUPM M.Sc. Thesis, 2023 |
| `reis2024yolov8` | Reis et al., arXiv:2305.09972, 2024 |
| `delleji2025thermal` | Delleji et al., IntechOpen 2025, doi:10.5772/intechopen.1011701 |
| `stacker2021` | Stäcker et al., ICCVW 2021 — **already in bibliography, reuse** |
| `coluccia2023` | Coluccia et al., ICASSP 2023 — **already in bibliography, reuse** |

---

## Architecture

The feature is a pure document-editing operation. There is no runtime
architecture. The "system" is the LaTeX source file; the "components" are
the four chapters and the bibliography environment. All changes are additive:
new paragraphs and sections are inserted at specified anchors; no existing
text is altered.

```
report_full.tex
├── \chapter{Introduction}          ← Chapter 1 additions
├── \chapter{Literature Review}     ← Chapter 2 additions
├── \chapter{Methodology}           ← Chapter 3 additions
├── \chapter{Results}               (unchanged)
├── \chapter{Discussion}            ← Chapter 5 additions
├── \chapter{Conclusion}            (unchanged)
└── \begin{thebibliography}{99}     ← 4 new \bibitem entries
```

---

## Components and Interfaces

### Component 1 — Chapter 1 Additions

Two insertion points in Chapter 1.

#### 1A — New subsection "The UAV Threat Landscape"

**Anchor** (insert immediately after this existing paragraph):

```latex
The chosen production model is \textbf{BirdDrone-2C-FT} --- a YOLO26s model
trained on a curated 2-class (Bird/Drone) dataset and fine-tuned on the
DUT Anti-UAV benchmark. This report documents the full training methodology,
evaluation results, and deployment architecture for this model.
```

**New content to insert:**

```latex
\subsection{The UAV Threat Landscape}

The proliferation of consumer UAVs has transformed the threat landscape for
airspace security. Coluccia et al.~\cite{coluccia2021sensors} document the
scale of the challenge through the Drone vs.\ Bird Detection Grand Challenge
(3rd edition, 2020), which attracted 108 research groups globally and
evaluated detectors against 8 distinct drone types --- fixed-wing and
rotary-wing --- across varying backgrounds, weather conditions, and camera
motion profiles. The challenge dataset reveals that drone bounding boxes
range from as few as 15 px\textsuperscript{2} to over 1,000,000 px\textsuperscript{2},
with the majority below 322 px\textsuperscript{2}, making scale variance
the dominant difficulty factor for any vision-based detector.

A comparable distributed anti-UAV system is described by Munir~\cite{munir2023kfupm},
who develops a vision-based multi-scale UAV detector at KFUPM and provides
the first systematic benchmark of UAV detection under adverse weather
conditions (rain, Gaussian noise, and motion blur). That work identifies
fundamental limitations of vision-based detection: effective range below
350 ft, susceptibility to bird confusion, and sensitivity to illumination
changes. The present system addresses the bird confusion problem directly
through the 2-class BirdDrone-2C-FT architecture, and extends the prior
work by integrating detection into a distributed edge-computing pipeline
with a centralised web-based control center.
```

#### 1B — New paragraph in "Scope and Limitations"

**Anchor** (insert after this existing bullet in the `\section{Scope and Limitations}` itemize):

```latex
  \item Thermal infrared modality is identified as future work.
```

**New content to insert (as an additional sentence appended to that bullet, replacing it):**

> Note: rather than replacing the bullet, insert a new paragraph *after* the
> entire `\end{itemize}` block of the Scope and Limitations section and before
> `\section{Report Structure}`.

**Anchor** (insert after):

```latex
  \item The WOSDETC challenge dataset requires a data usage agreement
        and was not used in this work.
\end{itemize}
```

**New content to insert:**

```latex
The thermal infrared gap deserves specific mention. Delleji et al.~\cite{delleji2025thermal}
demonstrate that existing public thermal datasets are inadequate for aerial
drone detection: the FLIR ADAS dataset targets automotive scenes, the KAIST
Multispectral dataset focuses on pedestrian detection, and available aerial
thermal datasets contain fewer than 2,000 frames with minimal diversity.
Their work further shows that a custom thermal pipeline --- capturing three
DJI UAV types at multiple altitudes with a 640$\times$512 LWIR sensor ---
is necessary to achieve reliable thermal detection. This confirms that
extending BirdDrone-2C-FT to the thermal modality requires a dedicated
dataset acquisition effort beyond the scope of the current work.
```

---

### Component 2 — Chapter 2 Additions

Four insertion points in Chapter 2.

#### 2A — New section "UAV Detection Under Adverse Conditions"

**Anchor** (insert after the entire `\section{Drone vs.\ Bird Detection}` section, i.e., after):

```latex
YOLOBirDrone~\cite{yolobirdrone2025} (arXiv:2601.08319) proposes a
dedicated dataset and enhanced YOLO architecture for bird vs.\ drone
classification, reporting improved discrimination over standard YOLO
baselines. Their work confirms that the Bird/Drone boundary is the
primary challenge in aerial detection systems --- the same challenge
that BirdDrone-2C-FT is specifically designed to address.
```

**New content to insert:**

```latex
\section{UAV Detection Under Adverse Conditions}

Real-world anti-UAV systems must operate in conditions that deviate
significantly from the clean, well-lit imagery used in most benchmark
evaluations. Munir~\cite{munir2023kfupm} provides the first systematic
study of UAV detection under adverse weather, introducing three
weather-affected test sets derived from the Anti-UAV dataset: RTD
(drizzle, heavy, and torrential rain), ANTD (low, medium, and high
additive white Gaussian noise), and MBTD (low, medium, and high motion
blur). The results are striking: YOLOv5m, the strongest baseline on
clean data (mAP@0.5 = 95.6\%), degrades to 47.9\% under torrential rain
and 21.9\% under high motion blur --- performance drops of 50.6 and
77.0 percentage points respectively.

To address this, Munir proposes YOLO-RAW, a multi-scale UAV detector
that extends YOLOv5 with: an additional CBS+C3 block in the CSPDarknet53
backbone, an SPPF-Enhanced module, four SimAM (Simple, Parameter-Free
Attention Module) blocks in the neck, and a fourth prediction head (P6)
for large-scale objects via PANet extension. YOLO-RAW achieves 95.2\%
mAP@0.5 on the Complex Background Dataset and outperforms YOLOv5m on
all weather-affected test sets. Critically, training with weather-augmented
data (33\% noisy + 33\% motion-blurred + 34\% rainy images) improves
YOLOv5m's torrential rain performance from 47.9\% to 83.3\% mAP@0.5
and high-blur performance from 21.9\% to 66.8\%, while clean-data
mAP@0.5 drops only marginally from 95.6\% to 94.6\%. This demonstrates
that weather augmentation is a low-cost, high-impact robustness strategy
directly applicable to YOLO26s training.
```

#### 2B — New section "Transfer Learning for Aerial Object Detection"

**Anchor** (insert after the new section 2A, i.e., after the YOLO-RAW paragraph above, before the existing `\section{DUT Anti-UAV Benchmark}`):

**New content to insert:**

```latex
\section{Transfer Learning for Aerial Object Detection}

Transfer learning from large-scale detection models to domain-specific
aerial datasets has emerged as the dominant training paradigm for UAV
detection. Reis et al.~\cite{reis2024yolov8} demonstrate a two-stage
transfer learning strategy: a generalised YOLOv8 model is first trained
on 15,064 images across 40 flying object classes (mAP@0.5 = 79.2\%,
mAP@0.5:0.95 = 68.5\%, 50 fps on 1080p), then transfer-learned to a
3-class refined model (drone, plane, helicopter) achieving mAP@0.5 = 99.1\%,
mAP@0.5:0.95 = 83.5\%, at 50 fps. The two-stage approach --- learning
abstract flying-object features first, then specialising to a narrow
class set --- is directly analogous to the BirdDrone-2C base training
followed by DUT fine-tuning described in this report.

Reis et al.\ also provide a comparative analysis of model sizes: small
(11.1M parameters), medium (25.9M), and large (43.7M) YOLOv8 variants.
The jump in mAP@0.5:0.95 from small to medium is 0.05, but only 0.002
from medium to large, confirming diminishing returns at larger model
sizes. This analysis supports the selection of YOLO26s (9.9M parameters)
as the deployment model: it occupies the small-model tier while benefiting
from YOLO26's architectural improvements (STAL, NMS-free inference) that
were not available to the YOLOv8 small variant.
```

#### 2C — New section "Data Quality in Aerial Detection Datasets"

**Anchor** (insert after the existing `\section{Transfer Learning and Fine-Tuning for Aerial Detection}` section, i.e., after):

```latex
This work addresses this by using a 10$\times$ reduced
learning rate (lr0 = 0.001 vs 0.01 for base training), short patience
(8 epochs), and copy-paste augmentation to maintain diversity in the
fine-tuning data.
```

**New content to insert:**

```latex
\section{Data Quality in Aerial Detection Datasets}

A recurring finding in aerial detection research is that dataset quality
matters more than dataset size. Delleji et al.~\cite{delleji2025thermal}
validate this principle experimentally in the thermal domain: after
cleaning a 12,600-image thermal dataset down to 10,200 images using
perceptual hashing (phash, hash size 8, Hamming distance threshold),
YOLOv11 precision and recall remained equivalent or improved. Removing
near-duplicates, mislabeled samples, and low-quality frames had no
negative impact on model performance --- a result the authors summarise
as ``good data beats more data.''

This principle directly informs the dataset curation strategy for
BirdDrone-2C. Rather than using all 19,849 available drone images from
the anti-uav Roboflow dataset, the training set was capped at 2,850
images to maintain 50/50 class balance with the 3,404 bird images.
The deliberate choice to prioritise balance and quality over raw volume
is consistent with the findings of Delleji et al.\ and with the
pseudo-labeling confidence threshold of 0.70 applied during DUT
fine-tuning, which excludes uncertain frames rather than accepting
all available annotations.
```

#### 2D — Expand existing "Distributed Edge Inference" section

**Anchor** (replace the existing section content — insert additional paragraph after):

```latex
Stacker et al.~\cite{stacker2021} (ICCVW 2021) demonstrate that runtime
optimisation techniques (quantisation, TensorRT export, batch size tuning)
are critical for achieving acceptable inference throughput on resource-constrained
edge hardware. This informs our model selection (YOLO26s over larger variants)
and configurable frame rate design.
```

**New content to insert (append after the existing paragraph):**

```latex
Stäcker et al.\ provide quantitative benchmarks on NVIDIA Jetson AGX Xavier
that are directly applicable to this system's edge deployment targets.
Using TensorRT with Int8 quantisation and entropy calibration, RetinaNet-18
inference time drops from 104 ms (Float32) to 25 ms --- a 4.2$\times$
speedup with minimal accuracy loss (mAP: 0.361 $\to$ 0.355). Float16
quantisation achieves 38 ms with near-identical accuracy (mAP: 0.356),
making it the preferred option when calibration data is unavailable.
Notably, input resolution has a larger impact on detection performance
than quantisation format: mAP increases from 0.298 (low resolution,
416$\times$736) to 0.393 (high resolution, 832$\times$1472) with Int8,
suggesting that maintaining adequate input resolution is more important
than precision format on constrained hardware.

Power supply mode introduces a further constraint: on Jetson AGX Xavier,
reducing power from 50W (MAXN) to 10W increases the full detection
pipeline latency from 31 ms to 107 ms --- a 3.5$\times$ slowdown for
a 5$\times$ power reduction. For battery-powered or solar-powered
distributed anti-UAV nodes, this trade-off must be explicitly managed
through power budget planning. The Deployment Recommendations in
Chapter~6 reflect these findings by recommending TensorRT INT8 export
for resource-constrained edge hardware.
```

---

### Component 3 — Chapter 3 Additions

Three insertion points in Chapter 3.

#### 3A — Additional paragraph in "Canonical Class Taxonomy"

**Anchor** (insert after):

```latex
The 2-class taxonomy was chosen because bird/drone discrimination is the
primary operational requirement. Collapsing all aerial vehicle types into
a single ``Drone'' class maximises training data for the threat category
and avoids annotation ambiguity between drone subtypes.
```

**New content to insert:**

```latex
This design decision is supported by the broader literature. Coluccia et al.~\cite{coluccia2021sensors}
identify bird/drone confusion as the defining challenge of the Drone vs.\ Bird
Detection Grand Challenge, noting that drones and birds share the same
low-altitude airspace and are visually similar at long range. Their challenge
dataset includes 8 drone types precisely because the community has found that
collapsing drone subtypes into a single class is necessary to accumulate
sufficient training data for robust detection. Munir~\cite{munir2023kfupm}
similarly uses a single-class drone detector in the KFUPM thesis, reporting
that multi-class drone taxonomies reduce per-class training data to the point
where detection performance degrades on the minority drone subtypes. The
2-class Bird/Drone design of BirdDrone-2C-FT is therefore consistent with
the consensus approach in the field.
```

#### 3B — Additional paragraph in "BirdDrone-2C Base Dataset"

**Anchor** (insert after):

```latex
Balanced class representation is critical for the Bird/Drone task: an
imbalanced dataset would bias the model toward the majority class, increasing
either false positives (too many drone detections) or false negatives
(missed drones). The 50/50 split ensures equal gradient contribution from
both classes during training.
```

**New content to insert:**

```latex
The decision to cap the drone training set at 2,850 images rather than
using all available data reflects the data quality principle documented
by Delleji et al.~\cite{delleji2025thermal}: removing near-duplicates
and low-quality samples from a thermal aerial dataset produced equivalent
or improved model performance compared to the uncleaned larger dataset.
Applied to the RGB domain, this principle motivates prioritising a
balanced, curated 6,808-image dataset over a larger but imbalanced
collection. The anti-uav Roboflow dataset contains 19,849 images, but
many frames are near-duplicates from continuous video sequences; using
all of them would introduce implicit temporal correlation into the
training set, effectively reducing the diversity of the training
distribution despite the larger nominal size.
```

#### 3C — Additional paragraph in "Training Configuration" (Base Training subsection)

**Anchor** (insert after the existing augmentation justifications block, i.e., after):

```latex
\textbf{flipud = 0.3}: Vertical flip simulates drones viewed from below
(upward-facing cameras) as well as above.
```

**New content to insert:**

```latex
These augmentation choices are consistent with findings in the aerial
detection literature. Reis et al.~\cite{reis2024yolov8} demonstrate that
multi-scale feature extraction is essential for detecting flying objects
that occupy as little as 0.026\% of image area; their activation map
analysis shows that shallow layers detect broad object shape while deep
layers extract fine-grained textures, motivating the use of geometric
augmentations (rotation, flip) that expose the model to varied object
orientations at all scales. Munir~\cite{munir2023kfupm} provides direct
evidence for weather augmentation: adding 33\% noisy, 33\% motion-blurred,
and 34\% rainy images to the training set improves torrential rain
performance from 47.9\% to 83.3\% mAP@0.5 with only a 1.0 percentage
point drop on clean data. While the current BirdDrone-2C training does
not include explicit weather augmentation (the training data is RGB
imagery without synthetic degradation), the copy\_paste = 0.6 setting
serves an analogous purpose: it synthetically diversifies the background
distribution by pasting drone crops onto varied backgrounds, reducing
the model's sensitivity to specific background textures in a manner
comparable to domain-randomisation augmentation.
```

---

### Component 4 — Chapter 5 Additions

Three insertion points in Chapter 5.

#### 4A — New section "Comparison with Prior Systems"

**Anchor** (insert after the existing `\section{Why BirdDrone-2C-FT is the Recommended Production Model}` section, i.e., after):

```latex
\textbf{4. Significant reduction in operational noise.} The 55\% reduction
in low-confidence false positives (2,549$\to$1,154) and 34\% reduction in
tracking gaps (199$\to$131) directly translate to a cleaner operator
experience: fewer spurious alerts, more continuous tracking, and higher
confidence scores on genuine detections.
```

**New content to insert:**

```latex
\section{Comparison with Prior Systems}

The most directly comparable prior system is the KFUPM multi-scale UAV
detector described by Munir~\cite{munir2023kfupm}. That system uses
YOLOv5m as its primary baseline, achieving 95.6\% mAP@0.5 on clean
Anti-UAV data. BirdDrone-2C-FT achieves 0.929 mAP@0.5 on the Anti-UAV
test set (independent evaluation, not used in training), which is lower
than the KFUPM clean-data result. However, the comparison is not
straightforward: the KFUPM system is a single-class drone detector
trained on the full Anti-UAV dataset, while BirdDrone-2C-FT is a
2-class Bird/Drone detector trained on a curated balanced dataset and
evaluated on a held-out test split. The additional burden of
discriminating birds from drones --- the primary operational requirement
of this system --- is absent from the KFUPM evaluation.

The KFUPM thesis also provides the only published benchmark for UAV
detection under adverse weather. Under torrential rain, YOLOv5m degrades
to 47.9\% mAP@0.5; under high motion blur, to 21.9\%. BirdDrone-2C-FT
has not been evaluated on weather-affected sequences, which represents
a gap in the current evaluation. The KFUPM findings motivate the
inclusion of weather augmentation in future training iterations, as
discussed in the Future Work section of Chapter~6.

In terms of system architecture, both systems share the edge-inference
paradigm: detection runs on local hardware close to the camera, with
results communicated to a central system. The KFUPM system does not
describe a distributed multi-node architecture or a web-based control
center, which are the primary architectural contributions of the present
work beyond the model itself.
```

#### 4B — New section "Edge Deployment Considerations"

**Anchor** (insert after the new section 4A above, before the existing `\section{Effect of DUT Fine-Tuning}`):

**New content to insert:**

```latex
\section{Edge Deployment Considerations}

The deployment of YOLO26s on resource-constrained edge hardware introduces
latency and power constraints that must be explicitly managed. Stäcker et al.~\cite{stacker2021}
provide the most directly applicable benchmarks: on NVIDIA Jetson AGX Xavier,
TensorRT Int8 quantisation reduces inference time from 104 ms to 25 ms
(4.2$\times$ speedup) with a mAP drop of only 0.006 (0.361 $\to$ 0.355).
For YOLO26s, which is a convolutional architecture, TensorRT is the preferred
inference backend: Stäcker et al.\ show that TensorRT outperforms TorchScript
by 2$\times$ for convolutional networks (104 ms vs.\ 210 ms Float32), while
TorchScript is only advantageous for fully-connected layers.

The power-runtime trade-off documented by Stäcker et al.\ is particularly
relevant for distributed anti-UAV nodes that may operate on limited power
budgets. A 5$\times$ reduction in power (50W $\to$ 10W) causes a 3.5$\times$
increase in pipeline latency (31 ms $\to$ 107 ms). At 107 ms per frame, the
effective detection rate drops to approximately 9 fps --- below the 25 fps
of the DUT benchmark sequences and potentially insufficient for tracking
fast-moving UAVs. The configurable frame rate design of the edge inference
engine (described in Chapter~3) directly addresses this constraint: operators
can reduce the inference frame rate on power-limited nodes to maintain
detection quality at the cost of temporal resolution.

The Deployment Recommendations in Chapter~6 reflect these findings by
recommending TensorRT INT8 export for Jetson Nano and Raspberry Pi 4
deployments, where the 3--4$\times$ speedup is necessary to achieve
real-time inference within the hardware's thermal and power envelope.
```

#### 4C — Additional paragraph in "Effect of DUT Fine-Tuning"

**Anchor** (insert after):

```latex
The average confidence of true detections increases from 0.671 to 0.790
(+0.119). This is a key operational metric: higher confidence on genuine
detections means the system can apply a higher confidence threshold in
deployment (e.g., 0.45 instead of 0.35) to further reduce false positives
without missing real threats.
```

**New content to insert:**

```latex
These fine-tuning dynamics are consistent with the domain adaptation
literature. Reis et al.~\cite{reis2024yolov8} observe that their two-stage
transfer learning strategy --- generalised model first, then specialised
refinement --- produces a similar pattern: rapid convergence in the
specialisation stage (the refined model reaches near-peak performance
within a few epochs) followed by a plateau, with the backbone features
remaining largely unchanged while the detection head adapts to the
target domain. The low learning rate (lr0 = 0.001, 10$\times$ below
base training) used in BirdDrone-2C-FT fine-tuning serves the same
purpose as the staged transfer in Reis et al.: it preserves the
generalised Bird/Drone features learned during base training while
allowing the model to adapt its confidence calibration to the DUT
background distribution. The regressions on video16 and video19 are
the expected cost of this adaptation: sequences whose background
statistics differ from the DUT pseudo-label distribution receive
slightly reduced sensitivity, a trade-off that is well-documented in
the domain adaptation literature and is outweighed by the aggregate
improvements across the remaining 18 videos.
```

---

## Data Models

This feature operates on a single LaTeX source file. The relevant data
structures are:

- **LaTeX section hierarchy**: `\chapter` > `\section` > `\subsection`
- **Citation command**: `\cite{key}` — key must match a `\bibitem{key}` in the bibliography
- **Bibliography entry**: `\bibitem{key}` followed by author, title, venue, year, and optionally DOI/URL
- **Itemize environment**: used in Scope and Limitations; new paragraph is inserted *after* the `\end{itemize}`, not inside it

### New Bibliography Entries

All four entries are inserted inside the existing `\begin{thebibliography}{99}` ... `\end{thebibliography}` block, after the last existing `\bibitem`:

```latex
\bibitem{coluccia2021sensors}
A.\ Coluccia, A.\ Fascista, A.\ Schumann, L.\ Sommer, A.\ Dimou,
D.\ Zarpalas, M.\ M\'{e}ndez et al.,
``Drone vs.\ Bird Detection: Deep Learning Algorithms and Results
from a Grand Challenge,''
\textit{Sensors}, MDPI, vol.\ 21, no.\ 8, p.\ 2824, 2021.
\url{https://doi.org/10.3390/s21082824}

\bibitem{munir2023kfupm}
A.\ Munir,
``Vision-Based Multi-Scale UAV Detection,''
M.Sc.\ Thesis, King Fahd University of Petroleum \& Minerals (KFUPM),
Dhahran, Saudi Arabia, December 2023.

\bibitem{reis2024yolov8}
D.\ Reis, J.\ Hong, J.\ Kupec, A.\ Daoudi,
``Real-Time Flying Object Detection with YOLOv8,''
\textit{arXiv:2305.09972v2}, Georgia Institute of Technology, 2024.
\url{https://arxiv.org/abs/2305.09972}

\bibitem{delleji2025thermal}
T.\ Delleji, F.\ Slimeni, A.\ Siala,
``Good Data Beats More Data: Building a Thermal Air-Image Dataset
for Ground-to-Air Surveillance,''
in \textit{Transfer Learning -- Unlocking the Power of Pretrained Models},
IntechOpen, 2025.
\url{https://doi.org/10.5772/intechopen.1011701}
```

---

## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system — essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

This feature is a LaTeX document editing task. The "code under test" is the
resulting LaTeX source file. Three universal properties hold for any
well-formed LaTeX document with citations:

### Property 1: Citation–Bibliography Consistency

*For any* `\cite{key}` command appearing anywhere in the LaTeX source, there
must exist a corresponding `\bibitem{key}` entry within the
`thebibliography` environment.

**Validates: Requirements 2.4, 6.1**

### Property 2: Bibliography Key Uniqueness

*For any* two `\bibitem` entries in the bibliography, their citation keys
must be distinct (no duplicate keys).

**Validates: Requirements 6.4**

### Property 3: New Bibliography Entry Completeness

*For any* new `\bibitem` entry added by this feature, the entry text must
contain: at least one author name, a title string, a venue or journal name,
and a four-digit year.

**Validates: Requirements 6.2**

---

## Error Handling

| Risk | Mitigation |
|---|---|
| New `\cite{key}` used but `\bibitem{key}` not added | Property 1 catches this; all four new keys are listed in the Data Models section |
| Duplicate `\bibitem` key (e.g., adding `coluccia2021sensors` when `coluccia2023` already exists) | The two Coluccia entries have distinct keys; the design explicitly notes they are different papers |
| New content inserted inside an existing `\itemize` environment | All Chapter 1 additions are inserted after `\end{itemize}`, not inside it |
| LaTeX compilation error from unescaped special characters | All `&`, `%`, `$`, `_`, `\` characters in new content are properly escaped in the LaTeX above |
| Factual contradiction with existing report | No new quantitative claims about BirdDrone-2C-FT are introduced; all numbers cited are from the reference papers |

---

## Testing Strategy

This feature does not involve executable code, so property-based testing
libraries are not applicable. The three correctness properties above are
verified by static analysis of the LaTeX source:

**Property 1 — Citation consistency**: After applying all edits, run:
```bash
grep -oP '\\cite\{[^}]+\}' report_full.tex | sort -u
```
and verify every extracted key has a matching `\bibitem{key}` in the
bibliography block.

**Property 2 — Key uniqueness**: Run:
```bash
grep -oP '\\bibitem\{[^}]+\}' report_full.tex | sort | uniq -d
```
The output must be empty (no duplicates).

**Property 3 — Entry completeness**: Manually inspect each of the four new
`\bibitem` entries to confirm author, title, venue, and year are present.

**Compilation test**: Run `pdflatex report_full.tex` twice (to resolve
cross-references) and confirm zero errors in the `.log` file.

**Preservation test**: Verify that the existing section headings
`\section{Objectives}`, `\section{Scope and Limitations}`,
`\section{Report Structure}`, and all existing Chapter 2–5 section
headings are still present and unchanged in the source.
