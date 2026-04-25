# Thermal Report Update — Requirements

## Goal
Update `report_full.tex` to fully document the ThermalDrone model and Anti-UAV410 benchmark results, compliant with the FYP thesis guidelines (Ch1-5 PDFs).

## Requirements

### REQ-1: Copy thermal figures to run_graphs
Copy all result images from the thermal training run into `documentations/run_graphs/ThermalDrone/` so LaTeX can reference them.
Files: results.png, confusion_matrix.png, confusion_matrix_normalized.png, BoxF1_curve.png, BoxP_curve.png, BoxPR_curve.png, BoxR_curve.png, labels.jpg, val_batch0_labels.jpg, val_batch0_pred.jpg, val_batch1_labels.jpg, val_batch1_pred.jpg, val_batch2_labels.jpg, val_batch2_pred.jpg

### REQ-2: Ch1 — Add 5th objective for thermal model
Add a 5th specific objective to Section 1.4 covering the thermal modality.

### REQ-3: Ch2 — Add thermal literature review subsection
Add a subsection reviewing thermal UAV detection literature: SIDD dataset paper and Anti-UAV410 benchmark paper, with context on why thermal detection is a distinct problem from RGB.

### REQ-4: Ch3 — Expand thermal dataset description
Expand the SIDD dataset description to comply with Ch3 guidelines: data type, source URL, description, size, modifications made (COCO→YOLO conversion, class remapping UAV→Drone, scene breakdown).

### REQ-5: Ch3 — Add thermal implementation details prose
Add prose under the thermal training config table explaining the implementation flow (script, library version, hardware profile, how augmentation differs from RGB).

### REQ-6: Ch4 — Add figures to thermal results section
Add \includegraphics calls for: training curves (results.png), confusion matrix (normalized), PR curve (BoxPR_curve.png), val prediction samples (val_batch0_pred.jpg). Each with self-contained captions per guidelines.

### REQ-7: Ch4 — Add "Actual Contributions of This Work" paragraph
Add a separate numbered paragraph titled exactly "Actual Contributions of This Work" listing verifiable empirical contributions of the thermal work, per Ch4-5 guidelines (mandatory for excellence).

### REQ-8: Ch4 — Expand FAR/recall anomaly discussion
Add honest discussion of the 0.236 FAR and 0.730 recall gap, distinguishing method limitations from validation limitations, per Ch4 guidelines section 4.3.3.

### REQ-9: Ch4 — Update chapter summary bullets
Add thermal findings to the Chapter 4 summary bullet list.

### REQ-10: Ch5 — Update limitations and future work
Update limitations section to include thermal-specific limitations. Update short-term future work with thermal fine-tuning on Anti-UAV410.

### REQ-11: Add TikZ thermal pipeline diagram
Add a TikZ diagram showing the full thermal pipeline: SIDD dataset → COCO-to-YOLO conversion → ThermalDrone training → SIDD validation → Anti-UAV410 benchmark evaluation.

### REQ-12: Compile PDF
Run pdflatex on report_full.tex twice (for TOC/refs) and confirm successful compilation.
