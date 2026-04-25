# Requirements Document

## Introduction

The ThermalDrone model (YOLO26s, trained on the SIDD dataset) achieves strong precision on the Anti-UAV410 benchmark (P=0.993) but suffers from low recall on Anti-MUAV1 (R=0.233, F1=0.378), indicating the model misses many small or fast-moving thermal drones in challenging sequences. This feature automates a five-step improvement pipeline: confidence threshold optimisation, negative-example augmentation, Anti-UAV410 dataset integration, fine-tuning, and high-resolution retraining — with benchmarking after each training step to track progress across all three evaluation sets.

All scripts must be fish-shell compatible (no bash heredocs, no `&&` chaining). Multi-line logic must be written to `.py` files and executed separately.

---

## Glossary

- **Pipeline**: The ordered sequence of improvement steps defined in this document.
- **ThermalDrone**: The current YOLO26s 1-class drone detector trained on the SIDD thermal dataset.
- **SIDD**: Shandong Infrared Drone Dataset — 4,737 images across 4 scenes (city, mountain, sea, sky), COCO format.
- **Anti-UAV410**: Thermal IR benchmark with 410 sequences; annotations use `(x_tl, y_tl, w, h)` corner+size format.
- **Anti-MUAV1**: MOT_IR_sequences benchmark with multiple simultaneous drone tracks per sequence.
- **YOLO_Format**: Normalised bounding box format `(class_id cx cy w h)` with values in `[0, 1]`.
- **Background_Image**: An image with an empty YOLO label file (zero annotations), used to suppress false positives.
- **Conf_Sweep**: Evaluation of the model at multiple confidence thresholds to find the threshold maximising F1.
- **Combined_Dataset**: The merged training set of SIDD thermal_merged and Anti-UAV410 train split.
- **Benchmark_Runner**: The script that evaluates a given weights file on all three benchmarks and writes a JSON results file.
- **Invisible_Frame**: A frame in Anti-UAV410 where the drone is marked as not visible (`visible=0` or bbox is `0,0,0,0`).
- **Weights_File**: A `.pt` file produced by YOLO26s training, located under `training/<run_name>/weights/best.pt`.

---

## Requirements

### Requirement 1: Confidence Threshold Sweep

**User Story:** As a researcher, I want to evaluate the current ThermalDrone model at multiple confidence thresholds, so that I can identify the threshold that maximises F1 across all three benchmarks before making any training changes.

#### Acceptance Criteria

1. THE Conf_Sweep SHALL evaluate the current Weights_File at confidence thresholds 0.15, 0.20, 0.25, and 0.30.
2. WHEN a confidence threshold evaluation completes, THE Conf_Sweep SHALL record Precision, Recall, and F1 for each of the three benchmarks (Anti-UAV410, Anti-MUAV1, SIDD val).
3. WHEN all four thresholds have been evaluated, THE Conf_Sweep SHALL select the threshold that produces the highest mean F1 across all three benchmarks.
4. THE Conf_Sweep SHALL write a JSON results file to `training/thermal_drone_yolo26s_rtx2070_100ep/conf_sweep_results.json` containing per-threshold metrics for all three benchmarks and the selected optimal threshold.
5. THE Conf_Sweep SHALL print a formatted summary table to stdout showing threshold, Precision, Recall, and F1 for each benchmark.
6. IF the Weights_File does not exist at the expected path, THEN THE Conf_Sweep SHALL raise a descriptive error and exit with a non-zero status code.

---

### Requirement 2: Negative Example Collection

**User Story:** As a researcher, I want to add drone-free thermal frames to the training set as background images, so that the model learns to suppress false positives in empty scenes.

#### Acceptance Criteria

1. THE Pipeline SHALL collect background images from two sources: SIDD frames where the drone bounding box occupies fewer than 100 pixels of area, and Anti-UAV410 Invisible_Frames.
2. WHEN collecting SIDD background candidates, THE Pipeline SHALL select frames from the SIDD dataset where the corresponding YOLO label file contains a bounding box with `w * img_width * h * img_height < 100` pixels.
3. WHEN collecting Anti-UAV410 background candidates, THE Pipeline SHALL select Invisible_Frames (frames where `visible=0` or bbox is `0,0,0,0`).
4. THE Pipeline SHALL collect a total of approximately 500 background images, sampling evenly across available source sequences to avoid scene bias.
5. FOR each collected background image, THE Pipeline SHALL create an empty YOLO label file (zero bytes or empty text) at the corresponding label path.
6. THE Pipeline SHALL copy collected background images and their empty label files into the SIDD `thermal_merged/train/images/` and `thermal_merged/train/labels/` directories respectively.
7. THE Pipeline SHALL write a manifest file listing all added background image paths to `training/background_negatives_manifest.txt`.
8. IF a candidate image file cannot be read, THEN THE Pipeline SHALL log a warning and skip that file without aborting the collection process.

---

### Requirement 3: Anti-UAV410 Fine-Tune Dataset Preparation

**User Story:** As a researcher, I want to convert Anti-UAV410 **train-split** annotations to YOLO format and merge them with the SIDD dataset, so that I have a combined dataset for fine-tuning while keeping the test split and Anti-MUAV1 as clean evaluation sets.

> **Note on benchmark integrity:** Only the Anti-UAV410 **train split** is used for training. The Anti-UAV410 **test split** and all Anti-MUAV1 sequences are never included in any training or fine-tuning dataset. This ensures that benchmark results on these sets remain valid and comparable to published baselines.

#### Acceptance Criteria

1. THE Pipeline SHALL read Anti-UAV410 train-split annotations in `(x_tl, y_tl, w, h)` corner+size format from the Anti-UAV410 annotation JSON files.
2. WHEN converting annotations, THE Pipeline SHALL transform each bounding box to YOLO_Format using the formula: `cx = (x_tl + w/2) / img_width`, `cy = (y_tl + h/2) / img_height`, `bw = w / img_width`, `bh = h / img_height`.
3. WHEN a frame is an Invisible_Frame (bbox `0,0,0,0` or `visible=0`), THE Pipeline SHALL create an empty YOLO label file for that frame rather than writing a bounding box.
4. THE Pipeline SHALL write converted YOLO label files to `thermal_datasets/Anti-UAV410-main/yolo_labels/train/`.
5. THE Pipeline SHALL create a Combined_Dataset directory at `thermal_datasets/combined_finetune/` with `train/images/`, `train/labels/`, `val/images/`, and `val/labels/` subdirectories.
6. THE Pipeline SHALL populate the Combined_Dataset by symlinking or copying images and labels from both SIDD `thermal_merged` and Anti-UAV410 train split.
7. THE Pipeline SHALL write a `data.yaml` file to `thermal_datasets/combined_finetune/data.yaml` with `nc: 1`, `names: [Drone]`, and correct `train` and `val` paths.
8. THE Pipeline SHALL print a dataset summary showing total image counts for train and val splits.
9. IF an Anti-UAV410 annotation file is missing or malformed, THEN THE Pipeline SHALL log the file path and skip that sequence without aborting the preparation process.
10. FOR ALL valid Anti-UAV410 bounding boxes, converting to YOLO_Format and back to corner format SHALL recover the original `(x_tl, y_tl, w, h)` values within a rounding error of 1 pixel (round-trip property).

---

### Requirement 4: Fine-Tune on Combined Dataset

**User Story:** As a researcher, I want to fine-tune the ThermalDrone model on the Combined_Dataset, so that the model learns Anti-UAV410 appearance patterns while retaining SIDD performance.

#### Acceptance Criteria

1. THE Pipeline SHALL fine-tune the current Weights_File on the Combined_Dataset using YOLO26s with `lr0=0.001`, `epochs=20`, and `patience=8`.
2. THE Pipeline SHALL use `imgsz=640`, `batch=8`, and `amp=true` during fine-tuning to fit within the RTX 2070 8 GB VRAM budget.
3. THE Pipeline SHALL save fine-tuning output to `training/thermal_ft_combined_640/`.
4. WHEN fine-tuning completes, THE Benchmark_Runner SHALL evaluate the resulting `best.pt` on all three benchmarks (Anti-UAV410, Anti-MUAV1, SIDD val) using the optimal confidence threshold identified in Requirement 1.
5. THE Benchmark_Runner SHALL write evaluation results to `training/thermal_ft_combined_640/benchmark_results.json`.
6. IF the Combined_Dataset `data.yaml` is not found, THEN THE Pipeline SHALL raise a descriptive error and exit before starting training.

---

### Requirement 5: High-Resolution Retraining

**User Story:** As a researcher, I want to retrain ThermalDrone from scratch at imgsz=1280 on the Combined_Dataset, so that the model can resolve tiny drone targets that are missed at 640-pixel resolution.

#### Acceptance Criteria

1. THE Pipeline SHALL retrain YOLO26s from scratch (no pretrained weights transfer from ThermalDrone) on the Combined_Dataset with `imgsz=1280`, `epochs=100`, `patience=30`, `lr0=0.005`, and `batch=4`.
2. THE Pipeline SHALL use `amp=true` and the same thermal augmentation profile as the original ThermalDrone training (no HSV, `copy_paste=0.7`, `erasing=0.3`, `flipud=0.3`, `fliplr=0.5`).
3. THE Pipeline SHALL save retraining output to `training/thermal_retrain_combined_1280/`.
4. WHEN retraining completes, THE Benchmark_Runner SHALL evaluate the resulting `best.pt` on all three benchmarks using the optimal confidence threshold identified in Requirement 1.
5. THE Benchmark_Runner SHALL write evaluation results to `training/thermal_retrain_combined_1280/benchmark_results.json`.
6. IF available GPU VRAM is insufficient for `batch=4` at `imgsz=1280`, THEN THE Pipeline SHALL log a warning and reduce batch size to 2 before retrying.

---

### Requirement 6: Benchmark Runner

**User Story:** As a researcher, I want a single reusable script that benchmarks any Weights_File on all three datasets, so that I can track improvement consistently across pipeline steps.

#### Acceptance Criteria

1. THE Benchmark_Runner SHALL accept a Weights_File path and a confidence threshold as command-line arguments.
2. THE Benchmark_Runner SHALL evaluate the Weights_File on Anti-UAV410 test split, Anti-MUAV1, and SIDD val using the provided confidence threshold.
3. WHEN evaluating Anti-UAV410, THE Benchmark_Runner SHALL compute Precision, Recall, and F1 using the same IoU threshold (0.5) and frame-level matching logic as the existing evaluation scripts.
4. WHEN evaluating Anti-MUAV1, THE Benchmark_Runner SHALL use the multi-track matching logic from `scripts/eval_muav.py`, counting unmatched detections on invisible frames as false positives.
5. WHEN evaluating SIDD val, THE Benchmark_Runner SHALL use the YOLO26s built-in `model.val()` method and report `mAP@0.5`, Precision, and Recall.
6. THE Benchmark_Runner SHALL write all three benchmark results to a single JSON file at the path specified by a `--output` argument.
7. THE Benchmark_Runner SHALL print a formatted summary table to stdout after all evaluations complete.
8. IF a benchmark dataset directory does not exist, THEN THE Benchmark_Runner SHALL skip that benchmark, log a warning, and continue evaluating the remaining benchmarks.

---

### Requirement 7: Pipeline Orchestration

**User Story:** As a researcher, I want a single orchestration script that runs all pipeline steps in order, so that I can execute the full improvement workflow with one command.

#### Acceptance Criteria

1. THE Pipeline SHALL execute steps in the following fixed order: Conf_Sweep → Negative Example Collection → Dataset Preparation → Fine-Tune → High-Resolution Retrain → final Benchmark_Runner.
2. WHEN a pipeline step completes successfully, THE Pipeline SHALL log the step name, elapsed time, and a success status to stdout.
3. IF a pipeline step exits with a non-zero status code, THEN THE Pipeline SHALL log the failure, print the step's stderr output, and halt execution without proceeding to subsequent steps.
4. THE Pipeline SHALL write a pipeline run log to `training/thermal_improvement_pipeline.log` containing timestamps and status for each step.
5. THE Pipeline SHALL support a `--dry-run` flag that prints the commands for each step without executing them.
6. THE Pipeline SHALL support a `--start-from <step>` argument accepting values `conf_sweep`, `negatives`, `prepare`, `finetune`, `retrain`, `benchmark` to resume from a specific step.
7. WHEN a training step (finetune or retrain) completes, THE Pipeline SHALL compare the mean F1 across all three benchmarks against the best mean F1 seen so far. IF the new mean F1 does not improve by at least 0.01 over the previous best, THEN THE Pipeline SHALL log a "no improvement" message and halt without executing subsequent training steps. The final benchmark step SHALL always run regardless.
