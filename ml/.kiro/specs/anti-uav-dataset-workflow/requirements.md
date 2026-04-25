# Requirements Document

## Introduction

A comprehensive anti-UAV dataset management and YOLO training workflow system. The system allows users to ingest datasets from Roboflow Universe (folders or ZIP archives), inspect their contents, review and curate images via a GUI, normalize all class labels to a fixed taxonomy (Bird / Drone / UAV), merge curated datasets, train YOLO models with hardware-aware parameters for an RTX 2070 8 GB or Google Colab T4, manage training runs, generate per-run documentation, compare runs, and optionally offload training to Google Colab with automated file push/pull.

## Glossary

- **Dataset_Inspector**: Component that scans a folder or ZIP archive and reports its structure, annotation format, image count, and class list.
- **GUI_Reviewer**: Desktop GUI application for browsing dataset images, deleting unwanted images, and remapping class labels.
- **Class_Normalizer**: Component that remaps any source label to exactly one of the three canonical classes: Bird, Drone, or UAV.
- **Annotation_Backend**: Label Studio instance used as the authoritative annotation store when conflicts or ambiguous labels are detected.
- **Dataset_Merger**: Component that combines multiple curated datasets into the `merged_dataset/` folder, resolving duplicates and re-indexing files.
- **Training_Manager**: Component that configures and launches YOLO training runs with hardware-aware parameters.
- **Run_Documenter**: Component that auto-generates a documentation file per training run under `documentations/`.
- **Run_Comparator**: Component that reads results from multiple runs and produces a comparison report under `comparison/`.
- **Colab_Bridge**: Component that pushes files to a remote training backend (Google Colab or Kaggle), triggers remote training, and pulls results back.
- **Kaggle_Backend**: Kaggle Notebooks used as a fully automated remote training backend via the Kaggle API (`kaggle kernels push`). Provides two T4 GPUs simultaneously, 9-hour session limit, and 30 GPU hours/week free quota.
- **Colab_Backend**: Google Colab used as a semi-automated remote training backend. Provides one T4 GPU, 12-hour session limit, but requires manual "Run All" in the browser (no public execution API on free tier).
- **Canonical_Classes**: The three allowed class labels: `Bird`, `Drone` (small drones), `UAV` (large drones).
- **Roboflow_Universe**: External dataset source; datasets may be downloaded as ZIP archives or folder exports.
- **YOLO_Model**: Object detection model from the Ultralytics YOLO26 family (yolo26s, yolo26m, or larger). YOLO26 is the latest Ultralytics release (September 2025), featuring native NMS-free end-to-end inference, MuSGD optimizer, ProgLoss + STAL for improved small-object detection, and DFL removal for simplified deployment — making it well-suited for aerial UAV/drone imagery.

---

## Requirements

### Requirement 1: Dataset Ingestion and Inspection

**User Story:** As a dataset engineer, I want to point the system at a folder or ZIP file and immediately see what is inside, so that I can understand the data before doing any work on it.

#### Acceptance Criteria

1. WHEN the user provides a path to a folder or ZIP archive under `datasets/`, THE Dataset_Inspector SHALL scan the archive or folder and report: total image count, annotation format (YOLO TXT, COCO JSON, Pascal VOC XML, or unknown), list of unique class names found, and per-class image count.
2. WHEN the Dataset_Inspector encounters a ZIP archive, THE Dataset_Inspector SHALL extract it to a temporary working directory before scanning, without modifying the original ZIP.
3. IF the Dataset_Inspector cannot parse an annotation file, THEN THE Dataset_Inspector SHALL log the unparseable file path and continue scanning remaining files.
4. WHEN the scan is complete, THE Dataset_Inspector SHALL write a summary report as a JSON file alongside the dataset folder.
5. THE Dataset_Inspector SHALL support at minimum YOLO TXT, COCO JSON, and Pascal VOC XML annotation formats.

---

### Requirement 2: GUI Image Reviewer

**User Story:** As a dataset engineer, I want a graphical interface to browse dataset images one by one (or in a grid), mark images for deletion, and reassign class labels, so that I can curate the dataset without writing scripts.

#### Acceptance Criteria

1. THE GUI_Reviewer SHALL display images from a selected dataset folder in a scrollable grid view and a single-image detail view.
2. WHEN the user selects an image in the GUI_Reviewer, THE GUI_Reviewer SHALL display the image alongside its current bounding box annotations and class labels.
3. WHEN the user marks an image for deletion in the GUI_Reviewer, THE GUI_Reviewer SHALL stage the image for removal without immediately deleting it from disk.
4. WHEN the user confirms a deletion batch, THE GUI_Reviewer SHALL permanently delete the staged images and their corresponding annotation files.
5. WHEN the user selects a bounding box annotation in the GUI_Reviewer, THE GUI_Reviewer SHALL allow the user to remap the label to one of the Canonical_Classes (Bird, Drone, UAV).
6. THE GUI_Reviewer SHALL provide a filter control to show only images belonging to a selected class label.
7. WHEN the user saves changes in the GUI_Reviewer, THE GUI_Reviewer SHALL write updated annotation files in the same format as the source annotations.
8. THE GUI_Reviewer SHALL display a running count of total images, deleted images, and per-class image counts in a status bar.

---

### Requirement 3: Class Normalization

**User Story:** As a dataset engineer, I want all class labels across every dataset to be remapped to exactly Bird, Drone, or UAV, so that merged datasets have a consistent taxonomy.

#### Acceptance Criteria

1. THE Class_Normalizer SHALL accept a user-defined mapping table that maps source class names to one of the Canonical_Classes.
2. WHEN the Class_Normalizer processes a dataset, THE Class_Normalizer SHALL replace every source class name with its mapped Canonical_Class in all annotation files.
3. IF a source class name has no entry in the mapping table, THEN THE Class_Normalizer SHALL flag the unmapped class and prompt the user to assign it to a Canonical_Class before proceeding.
4. WHEN class normalization is complete, THE Class_Normalizer SHALL rename image files that contain the original class name in their filename to use the mapped Canonical_Class name.
5. THE Class_Normalizer SHALL produce a normalization log listing every substitution made, including source label, target label, and affected file count.
6. WHERE Label Studio is configured as the Annotation_Backend, THE Class_Normalizer SHALL sync the updated annotations to the Annotation_Backend after normalization.

---

### Requirement 4: Label Studio Annotation Backend Integration

**User Story:** As a dataset engineer, I want Label Studio available as an annotation backend so that I can resolve ambiguous labels and perform fine-grained annotation corrections in a web UI.

#### Acceptance Criteria

1. THE Annotation_Backend SHALL be launchable from the workflow system via a single CLI command or GUI button.
2. WHEN the user imports a dataset into the Annotation_Backend, THE Annotation_Backend SHALL create a project pre-configured with the three Canonical_Classes as the only allowed labels.
3. WHEN the user exports annotations from the Annotation_Backend, THE Annotation_Backend SHALL export in YOLO TXT format compatible with the rest of the pipeline.
4. IF the Annotation_Backend is not running when an export is requested, THEN THE Class_Normalizer SHALL fall back to the local mapping table without blocking the pipeline.
5. THE Annotation_Backend SHALL preserve the original image filenames during import and export.

---

### Requirement 5: Dataset Merging

**User Story:** As a dataset engineer, I want to merge multiple curated datasets into a single unified dataset, so that I can train on all available data at once.

#### Acceptance Criteria

1. WHEN the user triggers a merge operation, THE Dataset_Merger SHALL combine all curated datasets from `datasets/` into `merged_dataset/`, preserving the train/val/test split structure.
2. THE Dataset_Merger SHALL re-index all image filenames to avoid collisions across source datasets using a deterministic naming scheme (e.g., `{source_dataset}_{original_name}`).
3. IF a duplicate image is detected (by SHA-256 hash), THEN THE Dataset_Merger SHALL keep one copy and log the duplicate.
4. WHEN the merge is complete, THE Dataset_Merger SHALL write a `data.yaml` file in `merged_dataset/` listing the Canonical_Classes and the paths to train/val/test splits.
5. THE Dataset_Merger SHALL report per-class image counts and overall dataset statistics after merging.
6. WHEN the merged dataset contains a class imbalance where the largest class has more than 5 times the images of the smallest class, THE Dataset_Merger SHALL warn the user and suggest augmentation strategies.

---

### Requirement 6: Hardware-Aware YOLO Training Parameter Suggestions

**User Story:** As an ML engineer, I want the system to suggest YOLO training parameters optimized for my hardware (RTX 2070 8 GB or Google Colab T4), so that I can train without manually tuning batch size, image size, and mixed precision settings.

#### Acceptance Criteria

1. WHEN the user selects a hardware profile (RTX 2070 8 GB or Google Colab T4), THE Training_Manager SHALL suggest a complete set of training parameters including: model variant (yolo26s or yolo26m), image size, batch size, number of epochs, optimizer (MuSGD or AdamW), learning rate, weight decay, and mixed precision (AMP) setting.
2. THE Training_Manager SHALL default to yolo26s for the RTX 2070 8 GB profile and yolo26m for the Google Colab T4 profile, with the option to override to yolo26l or yolo26x if VRAM headroom allows.
3. WHEN the user selects the RTX 2070 8 GB profile, THE Training_Manager SHALL suggest parameters that keep peak GPU memory usage below 7.5 GB.
4. WHEN the user selects the Google Colab T4 profile, THE Training_Manager SHALL suggest parameters that keep peak GPU memory usage below 14 GB.
5. THE Training_Manager SHALL include augmentation parameters (mosaic, mixup, copy-paste, hsv adjustments) tuned for aerial/UAV imagery in its suggestions.
6. WHEN the user accepts the suggested parameters, THE Training_Manager SHALL save them to a YAML configuration file under the run's output folder.

---

### Requirement 7: Training Run Management

**User Story:** As an ML engineer, I want each training run to be isolated in its own folder with a unique identifier, so that I can reproduce and compare runs without overwriting previous results.

#### Acceptance Criteria

1. WHEN a training run is started, THE Training_Manager SHALL create a uniquely named subfolder under `training/` using the pattern `run_{YYYYMMDD}_{HHMMSS}_{model_variant}/` (e.g., `run_20260405_143022_yolo26s/`).
2. THE Training_Manager SHALL save the final trained weights, training curves (loss, mAP), and confusion matrix to the run's subfolder.
3. WHEN a training run completes, THE Training_Manager SHALL record the final mAP@0.5, mAP@0.5:0.95, precision, recall, and training duration in a `results.json` file inside the run's subfolder.
4. IF a training run is interrupted, THEN THE Training_Manager SHALL save the last checkpoint and mark the run as incomplete in `results.json`.
5. THE Training_Manager SHALL support resuming an incomplete run from the last saved checkpoint.

---

### Requirement 8: Per-Run Documentation Generation

**User Story:** As an ML engineer, I want the system to automatically generate a documentation file for each training run, so that I have a record of what was done and why.

#### Acceptance Criteria

1. WHEN a training run completes or is interrupted, THE Run_Documenter SHALL generate a Markdown file under `documentations/` named `run_{YYYYMMDD}_{HHMMSS}_{model_variant}.md`.
2. THE Run_Documenter SHALL include in the documentation: dataset used (name, image count, class distribution), model variant, all training parameters, hardware profile used, final metrics (mAP@0.5, mAP@0.5:0.95, precision, recall), training duration, and any warnings or anomalies detected during training.
3. THE Run_Documenter SHALL include a plain-language justification section explaining why the chosen parameters are appropriate for the hardware and dataset.
4. WHEN augmentation parameters differ from the defaults, THE Run_Documenter SHALL note the deviation and the reason provided by the user or system.

---

### Requirement 9: Run Comparison Reports

**User Story:** As an ML engineer, I want to compare the results of multiple training runs side by side, so that I can identify the best model and understand what changes improved performance.

#### Acceptance Criteria

1. WHEN the user triggers a comparison, THE Run_Comparator SHALL read `results.json` from all completed runs under `training/` and produce a comparison report under `comparison/`.
2. THE Run_Comparator SHALL rank runs by mAP@0.5:0.95 in descending order and identify the best-performing run.
3. THE Run_Comparator SHALL highlight differences in training parameters between runs and correlate parameter changes with metric changes.
4. THE Run_Comparator SHALL generate a comparison report as both a Markdown file and a CSV file under `comparison/`.
5. WHEN the best run is identified, THE Run_Comparator SHALL include actionable improvement suggestions based on the metric trends observed across runs.

---

### Requirement 10: Remote Training Backend Integration (Google Colab and Kaggle)

**User Story:** As an ML engineer, I want to offload training to a remote GPU backend (Google Colab or Kaggle), with as much automation as each platform allows, so that I can leverage free cloud T4 compute without manual file transfers.

#### Acceptance Criteria

1. THE Colab_Bridge SHALL support two selectable remote backends: `colab` and `kaggle`. The user selects the backend via a CLI flag (`--backend colab|kaggle`) or a GUI dropdown.

2. **Colab backend** — WHEN the user selects the `colab` backend:
   - THE Colab_Bridge SHALL upload `merged_dataset/` and the run's YAML config to a user-specified Google Drive folder via the Google Drive API.
   - THE Colab_Bridge SHALL generate a ready-to-execute `.ipynb` notebook that mounts Google Drive, installs dependencies (`ultralytics`, `label-studio-sdk`), extracts the dataset, runs training, and archives results back to Drive.
   - THE Colab_Bridge SHALL notify the user that they must open the notebook in a browser and click "Run All" (Colab free tier has no programmatic execution API).
   - WHEN the user confirms training is complete, THE Colab_Bridge SHALL download the run output folder from Google Drive into the local `training/` directory.
   - IF the Google Drive upload fails, THEN THE Colab_Bridge SHALL report the error with the failed file path and allow retry without re-uploading already-transferred files.
   - THE Colab_Bridge SHALL support authentication via Google service account key file or OAuth2 device flow.

3. **Kaggle backend** — WHEN the user selects the `kaggle` backend:
   - THE Colab_Bridge SHALL upload `merged_dataset/` as a Kaggle dataset using the Kaggle API (`kaggle datasets push`).
   - THE Colab_Bridge SHALL generate a Kaggle kernel script (`.ipynb`) that installs dependencies, mounts the uploaded dataset, runs YOLO26 training with the provided config, and saves outputs to `/kaggle/working/`.
   - THE Colab_Bridge SHALL push and trigger the kernel automatically using `kaggle kernels push`, requiring no browser interaction.
   - THE Colab_Bridge SHALL poll the kernel status via `kaggle kernels status` until completion or timeout, reporting progress to the user.
   - WHEN the kernel completes, THE Colab_Bridge SHALL download the output files using `kaggle kernels output` into the local `training/` directory.
   - THE Colab_Bridge SHALL support dual-T4 distributed training on Kaggle by setting `device: 0,1` in the training config when two GPUs are available.
   - THE Colab_Bridge SHALL authenticate via a `kaggle.json` API token file (standard Kaggle API credentials).
   - IF the Kaggle kernel exceeds the 9-hour session limit, THE Colab_Bridge SHALL detect the timeout, download any partial outputs, and offer to resume from the last checkpoint in a new kernel push.

4. WHEN either backend completes, THE Colab_Bridge SHALL integrate the downloaded results into the standard run folder structure under `training/` so that Run_Documenter and Run_Comparator work identically regardless of where training ran.

5. THE manual (Requirement 14) SHALL include dedicated subsections for both Colab and Kaggle workflows, including authentication setup, quota limits, and step-by-step instructions.

---

### Requirement 11: Dataset Statistics and Augmentation Advisor

**User Story:** As a dataset engineer, I want the system to analyze my dataset and suggest augmentation strategies, so that I can improve model generalization without collecting more data.

#### Acceptance Criteria

1. THE Dataset_Inspector SHALL compute and report: image resolution distribution, aspect ratio distribution, bounding box size distribution (small/medium/large per COCO thresholds), and class balance ratio.
2. WHEN the class balance ratio exceeds 5:1 between any two classes, THE Dataset_Inspector SHALL recommend oversampling, undersampling, or synthetic augmentation for the minority class.
3. WHEN the median bounding box area is below 32×32 pixels, THE Dataset_Inspector SHALL recommend enabling the `copy-paste` augmentation and increasing image resolution during training.
4. THE Training_Manager SHALL apply recommended augmentation parameters automatically when the user accepts the advisor's suggestions.

---

### Requirement 12: Folder Structure Initialization

**User Story:** As a user, I want the system to create the required folder structure on first run, so that I don't have to set it up manually.

#### Acceptance Criteria

1. WHEN the system is launched for the first time, THE Training_Manager SHALL create the following directories if they do not exist: `datasets/`, `merged_dataset/`, `training/`, `documentations/`, `comparison/`.
2. THE Training_Manager SHALL place a `README.md` in each created directory explaining its purpose.
3. IF any required directory already exists, THEN THE Training_Manager SHALL leave it unchanged.

---

### Requirement 13: Model Validation Protocol

**User Story:** As an ML engineer, I want the system to evaluate trained models against domain-standard anti-UAV validation metrics, so that I can objectively measure model quality and compare runs against published benchmarks.

#### Acceptance Criteria

1. WHEN a training run completes, THE Training_Manager SHALL evaluate the final model on the held-out test split and report the following metrics:
   - mAP@0.5 and mAP@0.5:0.95 (overall)
   - mAP@0.5 broken down per Canonical_Class (Bird, Drone, UAV)
   - mAP@0.5 for small objects only (bounding box area < 32×32 px, per COCO small-object threshold)
   - Precision, Recall, and F1-score per class and overall
   - False Positive Rate on background patches (images with no UAV/drone/bird present)

2. WHEN the validation run completes, THE Training_Manager SHALL generate a precision-recall curve for each Canonical_Class and save it as an image in the run's output folder, to allow the user to select an optimal confidence threshold for their deployment use case.

3. THE Training_Manager SHALL apply a minimum performance gate: a run is marked as **passing** only if overall mAP@0.5 ≥ 0.75 on the test split. Runs below this threshold SHALL be marked as **failing** in `results.json` with a note recommending next steps (e.g., more data, augmentation, larger model variant).

4. WHEN reporting small-object mAP, THE Training_Manager SHALL flag any Canonical_Class where small-object mAP falls more than 15 percentage points below that class's overall mAP, and recommend enabling YOLO26's STAL (Small-Target-Aware Label Assignment) if not already active.

5. THE Run_Comparator SHALL include the small-object mAP and per-class false positive rate in all comparison reports, in addition to the standard mAP@0.5:0.95 ranking.

6. THE Run_Documenter SHALL include a **Validation Summary** section in each run's documentation file that references the DUT Anti-UAV and VisDrone benchmark standards, states the achieved metrics, and notes whether the run passed or failed the minimum performance gate.

7. WHEN the user triggers a comparison, THE Run_Comparator SHALL plot an IoU threshold sensitivity curve (mAP vs. IoU threshold from 0.5 to 0.95 in steps of 0.05) for the best-performing run, saved as an image under `comparison/`.

---

### Requirement 14: Instructions Manual Generation

**User Story:** As a user, I want the system to produce a comprehensive instructions manual at the end of the workflow, so that I or anyone else can reproduce the full pipeline, understand the trained weights, and interpret the results without prior knowledge of the system.

#### Acceptance Criteria

1. WHEN the user triggers manual generation, THE system SHALL produce a single Markdown file `MANUAL.md` at the project root covering the complete end-to-end workflow.

2. THE manual SHALL include the following sections:
   - **Project Overview** — purpose of the anti-UAV detection system, the three Canonical_Classes, and the overall pipeline summary.
   - **Folder Structure** — description of every directory (`datasets/`, `merged_dataset/`, `training/`, `documentations/`, `comparison/`) and what belongs in each.
   - **Step-by-Step Procedure** — numbered instructions for: adding a dataset, running the inspector, using the GUI reviewer, normalizing classes, merging datasets, selecting a hardware profile, launching a training run locally or via Google Colab, and pulling results back.
   - **Trained Weights Guide** — explanation of where weights are saved (`training/run_*/weights/best.pt` and `last.pt`), what each file represents, how to load them with the Ultralytics API, and how to run inference on a new image or video.
   - **Results Interpretation** — plain-language explanation of each metric (mAP@0.5, mAP@0.5:0.95, precision, recall, F1, small-object mAP, false positive rate), what good values look like for anti-UAV detection, and how to read the precision-recall curves and IoU sensitivity plots.
   - **Run Comparison Guide** — how to trigger a comparison, how to read the comparison report, and how to identify the best model for deployment.
   - **Troubleshooting** — common issues (VRAM OOM, class imbalance warnings, failed Colab uploads, unmapped classes) and their recommended fixes.
   - **Glossary** — definitions of all technical terms used throughout the system.

3. WHEN a new training run completes, THE system SHALL append a summary entry for that run to a `CHANGELOG.md` file at the project root, recording the run ID, model variant, key metrics, and whether it passed the validation gate.

4. THE manual SHALL be written in plain language accessible to a user with basic Python knowledge, avoiding unexplained jargon.

5. THE manual SHALL include dedicated subsections for both the Google Colab and Kaggle remote training workflows, covering: authentication setup for each platform, quota limits and session timeout behaviour, step-by-step instructions, and how to retrieve results.
