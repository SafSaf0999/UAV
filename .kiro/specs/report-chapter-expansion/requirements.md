# Requirements Document

## Introduction

This feature expands four chapters of the academic report at
`UAV/UAV-dataset-workflow/documentations/report_full.tex`. The report
describes an AI-powered distributed anti-UAV detection system using
YOLO26s (BirdDrone-2C-FT) trained on curated aerial imagery.

The expansion targets Chapters 1 (Introduction), 2 (Literature Review),
3 (Methodology), and 5 (Discussion) by incorporating relevant talking
points drawn from six reference papers. Each paper contributes specific
content to specific chapters. New citations must be added to the
bibliography. All additions must preserve the existing academic tone,
LaTeX formatting conventions, and factual consistency with the rest of
the report.

## Glossary

- **Report**: The LaTeX document at `UAV/UAV-dataset-workflow/documentations/report_full.tex`.
- **Reference Papers**: The six PDF files in `UAV/Papers/` listed below.
- **sensors paper**: `sensors-21-02824-v2.pdf` — a Sensors (MDPI) journal article on UAV detection systems; described as "quite good, focus on it".
- **applsci paper**: `applsci-14-08332.pdf` — an Applied Sciences (MDPI) journal article on UAV detection.
- **arXiv paper**: `2305.09972v2.pdf` — an arXiv preprint on deep learning for UAV detection.
- **thermal paper**: `Good_Data_Beats_More_Data_Building_a_Thermal_Air-I.pdf` — a paper on thermal aerial imagery datasets.
- **KFUPM thesis**: `KFUPM_Thesis_Final_To_DGS_Eprint.pdf` — a thesis on an anti-UAV system described as "a similar project to ours".
- **stacker2021**: `Stacker_Deployment_of_Deep_Neural_Networks_for_Object_Detection_on_Edge_ICCVW_2021_paper.pdf` — already cited in the report as `\cite{stacker2021}`; about edge deployment of DNNs.
- **Chapter 1**: The Introduction chapter of the report.
- **Chapter 2**: The Literature Review chapter of the report.
- **Chapter 3**: The Methodology chapter of the report.
- **Chapter 5**: The Discussion chapter of the report.
- **BirdDrone-2C-FT**: The production YOLO26s model described in the report.
- **DUT Anti-UAV**: The DUT Anti-UAV benchmark dataset used for fine-tuning and evaluation.
- **WOSDETC**: The Drone-vs-Bird Detection Grand Challenge benchmark.
- **Talking_Point**: A self-contained paragraph or subsection added to a chapter that introduces a new idea, comparison, or context drawn from a reference paper.
- **Citation_Key**: A BibTeX key used in `\cite{}` commands within the LaTeX source.

---

## Requirements

### Requirement 1: Extract and Catalogue Relevant Content from Reference Papers

**User Story:** As a report author, I want the relevant content from each
reference paper identified and mapped to specific chapters, so that I know
exactly what to add and where.

#### Acceptance Criteria

1. THE Content_Extractor SHALL identify at least three distinct Talking_Points
   from the sensors paper that are relevant to Chapters 1, 2, or 3.
2. THE Content_Extractor SHALL identify at least two distinct Talking_Points
   from the applsci paper that are relevant to Chapters 2 or 5.
3. THE Content_Extractor SHALL identify at least two distinct Talking_Points
   from the arXiv paper that are relevant to Chapters 2 or 3.
4. THE Content_Extractor SHALL identify at least two distinct Talking_Points
   from the thermal paper that are relevant to Chapters 1, 2, or 3.
5. THE Content_Extractor SHALL identify at least three distinct Talking_Points
   from the KFUPM thesis that are relevant to Chapters 1, 2, 3, or 5.
6. THE Content_Extractor SHALL produce a mapping document that lists each
   Talking_Point with its source paper, target chapter, and a one-sentence
   summary of the content.

---

### Requirement 2: Expand Chapter 1 (Introduction)

**User Story:** As a report author, I want Chapter 1 expanded with additional
context and motivation, so that readers understand the broader significance
of the anti-UAV detection problem and the novelty of this work.

#### Acceptance Criteria

1. WHEN Chapter 1 is expanded, THE Report SHALL include at least two new
   paragraphs or subsections that contextualise the UAV threat landscape
   using content from the sensors paper or KFUPM thesis.
2. WHEN Chapter 1 is expanded, THE Report SHALL reference the KFUPM thesis
   as a comparable prior system and explain how this work differs or extends it.
3. WHEN Chapter 1 is expanded, THE Report SHALL mention the thermal infrared
   modality gap using content from the thermal paper, framing it as a
   limitation and future work direction.
4. WHEN new content is added to Chapter 1, THE Report SHALL cite each source
   paper using a new Citation_Key added to the bibliography.
5. WHEN Chapter 1 is expanded, THE Report SHALL preserve all existing
   Objectives, Scope and Limitations, and Report Structure subsections
   without modification.
6. IF any new content in Chapter 1 contradicts a factual claim already
   present in the report, THEN THE Author SHALL flag the contradiction
   rather than silently overwrite it.

---

### Requirement 3: Expand Chapter 2 (Literature Review)

**User Story:** As a report author, I want Chapter 2 expanded with additional
related work sections, so that the literature review is comprehensive and
positions this work within the current state of the art.

#### Acceptance Criteria

1. WHEN Chapter 2 is expanded, THE Report SHALL include a new section or
   subsection covering sensor fusion and multi-modal detection approaches,
   drawing primarily from the sensors paper.
2. WHEN Chapter 2 is expanded, THE Report SHALL include a new section or
   subsection covering recent deep learning architectures for small UAV
   detection, drawing from the arXiv paper and applsci paper.
3. WHEN Chapter 2 is expanded, THE Report SHALL include a new section or
   subsection on dataset curation and the role of data quality in aerial
   detection, drawing from the thermal paper.
4. WHEN Chapter 2 is expanded, THE Report SHALL include a new section or
   subsection comparing this work to the KFUPM thesis as a similar
   distributed anti-UAV system.
5. WHEN new sections are added to Chapter 2, THE Report SHALL assign each
   new section a `\section{}` or `\subsection{}` heading consistent with
   the existing LaTeX formatting style.
6. WHEN new sections are added to Chapter 2, THE Report SHALL cite each
   source paper using a Citation_Key added to the bibliography.
7. THE Report SHALL preserve all existing Chapter 2 sections (YOLO Model
   Family, Drone vs. Bird Detection, DUT Anti-UAV Benchmark, Transfer
   Learning and Fine-Tuning, Distributed Edge Inference, Distance and
   Trajectory Estimation) without modification.

---

### Requirement 4: Expand Chapter 3 (Methodology)

**User Story:** As a report author, I want Chapter 3 expanded with additional
methodological context, so that design decisions are better justified by
reference to prior work.

#### Acceptance Criteria

1. WHEN Chapter 3 is expanded, THE Report SHALL include additional
   justification for the 2-class taxonomy decision, referencing how
   comparable systems (sensors paper, KFUPM thesis) handle class design.
2. WHEN Chapter 3 is expanded, THE Report SHALL include a discussion of
   pseudo-labeling methodology in the context of prior work, citing the
   arXiv paper or applsci paper if they address semi-supervised or
   self-supervised labeling for aerial detection.
3. WHEN Chapter 3 is expanded, THE Report SHALL include a discussion of
   why RGB-only training was chosen over thermal, referencing the thermal
   paper to acknowledge the trade-off.
4. WHEN Chapter 3 is expanded, THE Report SHALL include additional
   justification for the augmentation strategy (copy_paste, degrees,
   flipud) by referencing how similar augmentations are used in the
   sensors paper or arXiv paper.
5. WHEN new content is added to Chapter 3, THE Report SHALL integrate it
   as additional paragraphs within existing sections rather than creating
   new top-level sections, unless the content is substantial enough to
   warrant a new subsection.
6. WHEN new content is added to Chapter 3, THE Report SHALL cite each
   source paper using a Citation_Key added to the bibliography.
7. THE Report SHALL preserve all existing Chapter 3 sections and tables
   without modification.

---

### Requirement 5: Expand Chapter 5 (Discussion)

**User Story:** As a report author, I want Chapter 5 expanded with deeper
analysis and comparison to related work, so that the discussion situates
the results within the broader literature.

#### Acceptance Criteria

1. WHEN Chapter 5 is expanded, THE Report SHALL include a comparison of
   BirdDrone-2C-FT's performance metrics against the KFUPM thesis system,
   identifying similarities and differences in approach and results.
2. WHEN Chapter 5 is expanded, THE Report SHALL include a discussion of
   how the observed fine-tuning trade-offs (video16, video19 regressions)
   relate to findings in the sensors paper or applsci paper on domain
   adaptation challenges.
3. WHEN Chapter 5 is expanded, THE Report SHALL include a discussion of
   the edge deployment constraints and how they compare to the stacker2021
   findings already cited in Chapter 2.
4. WHEN Chapter 5 is expanded, THE Report SHALL include a discussion of
   the thermal modality gap as a limitation, referencing the thermal paper.
5. WHEN new content is added to Chapter 5, THE Report SHALL integrate it
   as additional paragraphs within existing sections or as new subsections
   where appropriate.
6. WHEN new content is added to Chapter 5, THE Report SHALL cite each
   source paper using a Citation_Key added to the bibliography.
7. THE Report SHALL preserve all existing Chapter 5 sections without
   modification.

---

### Requirement 6: Bibliography Management

**User Story:** As a report author, I want all new citations properly added
to the bibliography, so that the report is academically complete and
references are verifiable.

#### Acceptance Criteria

1. THE Report SHALL add a new `\bibitem` entry for each reference paper
   that is cited in the expanded chapters, using a unique Citation_Key.
2. WHEN a `\bibitem` entry is added, THE Report SHALL include at minimum:
   author(s), title, venue or journal, and year.
3. WHERE a DOI or URL is available for a reference paper, THE Report SHALL
   include it in the `\bibitem` entry.
4. THE Report SHALL not duplicate existing bibliography entries; the
   stacker2021 entry already present SHALL be reused for any new citations
   of that paper.
5. THE Report SHALL place all new `\bibitem` entries within the existing
   `thebibliography` environment in the LaTeX source.

---

### Requirement 7: Academic Tone and Consistency

**User Story:** As a report author, I want all new content to match the
existing academic style, so that the expanded report reads as a coherent
whole.

#### Acceptance Criteria

1. THE Report SHALL use the same LaTeX formatting conventions as the
   existing document (section headings, table environments, figure
   environments, equation environments).
2. WHEN new content is added, THE Report SHALL use the same terminology
   as the existing report (e.g., "BirdDrone-2C-FT", "DUT Anti-UAV",
   "YOLO26s", "edge device", "control center").
3. WHEN new content is added, THE Report SHALL maintain the same level
   of technical precision as the existing text — quantitative claims
   must be supported by citations or the report's own experimental data.
4. THE Report SHALL not introduce new claims about BirdDrone-2C-FT
   performance that are not supported by the experimental results already
   documented in Chapter 4.
5. IF a reference paper uses different terminology for the same concept,
   THEN THE Report SHALL use the report's existing terminology and note
   the correspondence in parentheses if necessary.
