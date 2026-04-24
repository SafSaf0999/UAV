# Implementation Plan: Report Chapter Expansion

## Overview

Apply 10 insertion points to `report_full.tex`, add 4 bibliography entries,
compile the PDF twice, and verify citation consistency.

## Tasks

- [x] 1. Apply Chapter 1 insertions (Insertion Points 1A and 1B)
  - Insert the `\subsection{The UAV Threat Landscape}` block immediately after the
    "BirdDrone-2C-FT" closing paragraph in `\chapter{Introduction}`
    (Design §Component 1 — 1A)
  - Insert the thermal-gap paragraph after `\end{itemize}` in
    `\section{Scope and Limitations}` and before `\section{Report Structure}`
    (Design §Component 1 — 1B)
  - _Requirements: 2.1, 2.2, 2.3, 2.4_

- [x] 2. Apply Chapter 2 insertions (Insertion Points 2A, 2B, 2C, 2D)
  - Insert `\section{UAV Detection Under Adverse Conditions}` after the
    `\section{Drone vs.\ Bird Detection}` section (Design §Component 2 — 2A)
  - Insert `\section{Transfer Learning for Aerial Object Detection}` after
    section 2A (Design §Component 2 — 2B)
  - Insert `\section{Data Quality in Aerial Detection Datasets}` after the
    existing `\section{Transfer Learning and Fine-Tuning for Aerial Detection}`
    section (Design §Component 2 — 2C)
  - Append the Stäcker quantitative benchmarks paragraph to the existing
    `\section{Distributed Edge Inference}` section (Design §Component 2 — 2D)
  - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6_

- [x] 3. Apply Chapter 3 insertions (Insertion Points 3A, 3B, 3C)
  - Insert the Bird/Drone taxonomy justification paragraph after the
    "2-class taxonomy was chosen" paragraph in `\section{Canonical Class Taxonomy}`
    (Design §Component 3 — 3A)
  - Insert the data-quality/capping paragraph after the "50/50 split ensures"
    paragraph in `\section{BirdDrone-2C Base Dataset}` (Design §Component 3 — 3B)
  - Insert the augmentation literature paragraph after the `flipud = 0.3`
    justification block in `\subsection{Base Training}` (Design §Component 3 — 3C)
  - _Requirements: 4.1, 4.3, 4.4, 4.6_

- [x] 4. Apply Chapter 5 insertions (Insertion Points 4A, 4B, 4C)
  - Insert `\section{Comparison with Prior Systems}` after
    `\section{Why BirdDrone-2C-FT is the Recommended Production Model}`
    (Design §Component 4 — 4A)
  - Insert `\section{Edge Deployment Considerations}` after section 4A and
    before `\section{Effect of DUT Fine-Tuning}` (Design §Component 4 — 4B)
  - Append the fine-tuning domain-adaptation paragraph after the
    "average confidence of true detections" paragraph in
    `\section{Effect of DUT Fine-Tuning}` (Design §Component 4 — 4C)
  - _Requirements: 5.1, 5.2, 5.3, 5.5, 5.6_

- [x] 5. Add 4 new bibliography entries
  - Append `\bibitem{coluccia2021sensors}`, `\bibitem{munir2023kfupm}`,
    `\bibitem{reis2024yolov8}`, and `\bibitem{delleji2025thermal}` inside
    the existing `\begin{thebibliography}{99}` block, after the last
    existing `\bibitem` (Design §Data Models — New Bibliography Entries)
  - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5_

- [x] 6. Verify citation consistency and key uniqueness
  - Run `grep -oP '\\cite\{[^}]+\}' report_full.tex | sort -u` and confirm
    every extracted key has a matching `\bibitem{key}` (Property 1)
  - Run `grep -oP '\\bibitem\{[^}]+\}' report_full.tex | sort | uniq -d`
    and confirm the output is empty — no duplicate keys (Property 2)
  - Manually inspect each of the 4 new `\bibitem` entries to confirm
    author, title, venue, and year are present (Property 3)
  - _Requirements: 6.1, 6.4_

- [x] 7. Compile the LaTeX document and copy the PDF
  - Run `pdflatex report_full.tex` from
    `UAV/UAV-dataset-workflow/documentations/` (first pass — builds TOC
    and cross-reference aux files)
  - Run `pdflatex report_full.tex` a second time (second pass — populates
    TOC and resolves all `\ref` / `\cite` forward references)
  - Confirm zero errors in the `.log` file (warnings are acceptable)
  - Copy the compiled `report_full.pdf` to `UAV/report_full.pdf`
  - _Requirements: 2.4, 3.6, 4.6, 5.6_

- [x] 8. Final checkpoint — Ensure all tests pass
  - Confirm all existing section headings are still present and unchanged
    (Preservation test from Design §Testing Strategy)
  - Confirm `UAV/report_full.pdf` exists and is non-empty
  - Ask the user if any questions arise before closing.
