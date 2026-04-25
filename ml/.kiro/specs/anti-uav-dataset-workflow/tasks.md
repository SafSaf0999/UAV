# Implementation Plan: Anti-UAV Dataset Management and YOLO26 Training Workflow

## Status Note (April 2026)

The core pipeline (tasks 1–24) is implemented and operational. The project has
evolved beyond the original spec to include:

- **2-class dataset** (BirdDrone-2C): 6,808 balanced images, Bird/Drone
- **3-class dataset** (BirdDrone-3C): 31,551 images, Bird/Drone/UAV (4 sources)
- **4 trained models**: BirdDrone-2C, BirdDrone-3C, BirdDrone-2C-FT, BirdDrone-3C-FT
- **DUT Anti-UAV evaluation**: 20 videos, annotated MP4 output, per-frame CSVs
- **Fine-tuning pipeline**: model-generated annotations from DUT, regression testing
- **Scientific reports**: `documentations/report.pdf`, `documentations/report_dut.pdf`
- **Recommended production model**: BirdDrone-2C-FT (mAP@0.5=0.969*, bird FA rate=0.3%)

**Key results:**

| Model | mAP@0.5 | mAP@0.5:0.95 | DUT Avg DR | Bird FA Rate |
|---|---|---|---|---|
| BirdDrone-2C | 0.926 | 0.554 | 0.808 | 0.3% |
| BirdDrone-3C | 0.892 | 0.574 | 0.842 | 6.9% |
| BirdDrone-2C-FT | 0.969* | 0.678* | 0.818 | 0.3% |
| BirdDrone-3C-FT | 0.881* | 0.598* | 0.883 | 4.5% |

*On combined val set (original + DUT pseudo-labels)

Integration tests (task 25) and smoke tests (task 26) remain pending.

---

## Overview

Incremental implementation starting from project scaffolding and shared models, then building each component in dependency order, finishing with tests and CLI wiring. Each task builds directly on the previous ones so there is no orphaned code.

## Tasks

- [x] 1. Project scaffolding and package structure
  - Create `pyproject.toml` (or `setup.py`) with package metadata, dependencies (`PyQt5`, `ultralytics>=8.4.0`, `label-studio-sdk`, `google-api-python-client`, `google-auth-oauthlib`, `kaggle`, `nbformat`, `PyYAML`, `matplotlib`, `hypothesis`, `pytest`, `pytest-qt`), and `console_scripts` entry points for every `anti-uav` subcommand
  - Create `anti_uav/__init__.py`, `anti_uav/gui/__init__.py`
  - Create top-level `tests/__init__.py`, `tests/integration/__init__.py`, `tests/smoke/__init__.py`
  - Create stub `README.md` at project root
  - _Requirements: 12.1, 12.2_

- [x] 2. Shared data models (`anti_uav/models.py`)
  - Implement all enums: `AnnotationFormat`, `CanonicalClass`, `HardwareProfile`, `AuthMethod`
  - Implement all dataclasses: `BoundingBox`, `Annotation`, `DatasetStats`, `InspectionReport`, `NormalizationLog`, `MergeReport`, `TrainingConfig`, `ValidationMetrics`, `TrainingResult`, `ReviewCounts`, `ComparisonReport`, `UploadManifest`
  - _Requirements: 1.1, 2.8, 3.5, 5.5, 6.1, 7.3, 9.1, 10.1, 13.1_

- [x] 3. Shared utilities (`anti_uav/utils.py`)
  - Implement shared `logging` setup: `get_logger(name)` returning a logger under the `anti_uav` namespace; support `--verbose` flag via `configure_logging(verbose: bool)`
  - Implement `atomic_write(path, content)`: write to `.tmp` then `os.replace`
  - Implement `sha256_hash(path: Path) -> str` using `hashlib`
  - _Requirements: 5.3, 7.4_

- [x] 4. Dataset_Inspector — core scanning (`anti_uav/inspector.py`)
  - Implement `detect_annotation_format(folder: Path) -> AnnotationFormat`
  - Implement `parse_yolo_txt(label_dir: Path) -> list[Annotation]`
  - Implement `parse_coco_json(json_path: Path) -> list[Annotation]`
  - Implement `parse_voc_xml(xml_dir: Path) -> list[Annotation]`
  - Implement `compute_statistics(annotations, images) -> DatasetStats` (resolution distribution, aspect ratios, bbox size buckets small/medium/large, class balance ratio)
  - _Requirements: 1.1, 1.3, 1.5, 11.1_

- [x] 5. Dataset_Inspector — ZIP handling and report output
  - Implement `inspect_dataset(path: str | Path) -> InspectionReport`: extract ZIP to `tempfile.mkdtemp()` without modifying original, call parsers, catch per-file errors and log to `inspection_errors.log`, write `inspection_report.json` atomically
  - Implement augmentation advisor logic inside `compute_statistics`: emit recommendations when class balance > 5:1 or median bbox area < 32×32
  - _Requirements: 1.2, 1.3, 1.4, 11.2, 11.3_

  - [ ] 5.1 Write property test — Property 1: inspection round-trip correctness
    - **Property 1: Dataset inspection round-trip correctness**
    - **Validates: Requirements 1.1, 1.4**

  - [ ] 5.2 Write property test — Property 2: ZIP extraction preserves original archive
    - **Property 2: ZIP extraction preserves original archive**
    - **Validates: Requirements 1.2**

  - [ ] 5.3 Write property test — Property 3: annotation format detection is correct
    - **Property 3: Annotation format detection is correct**
    - **Validates: Requirements 1.5**

  - [ ] 5.4 Write unit tests for Dataset_Inspector (`tests/test_inspector.py`)
    - Test each parser with valid and malformed input
    - Test empty dataset returns `image_count=0`
    - Test ZIP extraction leaves original unchanged
    - _Requirements: 1.1–1.5, 11.1–11.3_

- [x] 6. Checkpoint — ensure all inspector tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 7. GUI_Reviewer — ReviewerModel (`anti_uav/gui/reviewer_ui.py`)
  - Implement `ReviewerModel` with: `load_dataset`, `stage_deletion`, `unstage_deletion`, `confirm_deletions`, `remap_label`, `save_changes`, `get_counts`, `filter_by_class`
  - `save_changes` writes annotation files in source format using `atomic_write`
  - `confirm_deletions` deletes image + annotation file pairs
  - _Requirements: 2.1–2.8_

  - [x] 7.1 Write property test — Property 4: deletion staging does not remove files
    - **Property 4: Deletion staging does not remove files**
    - **Validates: Requirements 2.3**

  - [x] 7.2 Write property test — Property 5: confirmed deletion removes all staged files
    - **Property 5: Confirmed deletion removes all staged files**
    - **Validates: Requirements 2.4**

  - [x] 7.3 Write property test — Property 6: label remap produces canonical class
    - **Property 6: Label remap produces canonical class**
    - **Validates: Requirements 2.5**

  - [x] 7.4 Write property test — Property 7: class filter returns only matching images
    - **Property 7: Class filter returns only matching images**
    - **Validates: Requirements 2.6**

  - [x] 7.5 Write property test — Property 8: save-then-reload preserves annotations
    - **Property 8: Save-then-reload preserves annotations**
    - **Validates: Requirements 2.7**

  - [x] 7.6 Write property test — Property 9: status counts match actual file counts
    - **Property 9: Status counts match actual file counts**
    - **Validates: Requirements 2.8**

- [x] 8. GUI_Reviewer — PyQt5 window (`anti_uav/gui/reviewer_ui.py`)
  - Implement `ReviewerWindow(QMainWindow)` with `ImageGridWidget`, `DetailWidget` (bbox overlay painter), `AnnotationPanel` (QListWidget + QComboBox for remap), `FilterBar`, `QStatusBar` live counts
  - Wire all widgets to `ReviewerModel`; deletion confirmation dialog before `confirm_deletions`
  - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7, 2.8_

  - [x] 8.1 Write unit tests for GUI_Reviewer (`tests/test_reviewer.py`)
    - Use `pytest-qt` to test widget interactions, staging, remap, filter, status bar counts
    - _Requirements: 2.1–2.8_

- [x] 9. Class_Normalizer (`anti_uav/normalizer.py`)
  - Implement `load_mapping(path: Path) -> dict[str, CanonicalClass]`
  - Implement `find_unmapped_classes(dataset_path, mapping) -> list[str]`
  - Implement `normalize_dataset(dataset_path, mapping, backend_url=None) -> NormalizationLog`: rewrite annotation files atomically, rename image files containing source class name, sync to Label Studio if `backend_url` provided, produce `normalization_log.json`
  - Raise `UnmappedClassError` before modifying any files if unmapped classes exist
  - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6_

  - [x] 9.1 Write property test — Property 10: normalization produces only canonical labels
    - **Property 10: Normalization produces only canonical labels**
    - **Validates: Requirements 3.2**

  - [x] 9.2 Write property test — Property 11: normalization log entry count matches substitutions
    - **Property 11: Normalization log entry count matches substitutions**
    - **Validates: Requirements 3.5**

  - [x] 9.3 Write unit tests for Class_Normalizer (`tests/test_normalizer.py`)
    - Test unmapped class raises before any file modification
    - Test Label Studio fallback when backend unreachable
    - _Requirements: 3.1–3.6_

- [x] 10. Annotation_Backend (`anti_uav/backend.py`)
  - Implement `start_label_studio(port)`, `stop_label_studio(proc)`, `is_running(url)`
  - Implement `create_project(client, name) -> Project`: generate label config XML with exactly three `<Label>` elements (Bird, Drone, UAV)
  - Implement `import_dataset(project, dataset_path)`, `export_yolo(project, output_path)`
  - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5_

  - [x] 10.1 Write property test — Property 12: Label Studio export preserves filenames
    - **Property 12: Label Studio export preserves filenames**
    - **Validates: Requirements 4.5**

  - [x] 10.2 Write unit tests for Annotation_Backend (`tests/test_backend.py`)
    - Mock `label_studio_sdk`; test project creation XML, import/export, fallback when not running
    - _Requirements: 4.1–4.5_

- [x] 11. Checkpoint — ensure all normalizer and backend tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 12. Dataset_Merger (`anti_uav/merger.py`)
  - Implement `sha256_hash` (delegate to `utils.sha256_hash`)
  - Implement `detect_imbalance(class_counts, threshold=5.0) -> list[str]`
  - Implement `write_data_yaml(output_dir, classes, splits)`
  - Implement `merge_datasets(source_dirs, output_dir, splits=(0.7,0.2,0.1)) -> MergeReport`: copy images with `{source_dataset_name}_{original_stem}{ext}` naming, deduplicate by SHA-256 (log to `merge_duplicates.log`), preserve train/val/test structure, write `data.yaml`, report per-class counts and imbalance warnings
  - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6_

  - [x] 12.1 Write property test — Property 13: merge preserves train/val/test split structure
    - **Property 13: Merge preserves train/val/test split structure**
    - **Validates: Requirements 5.1**

  - [x] 12.2 Write property test — Property 14: merged filenames are unique
    - **Property 14: Merged filenames are unique**
    - **Validates: Requirements 5.2**

  - [x] 12.3 Write property test — Property 15: SHA-256 deduplication keeps exactly one copy
    - **Property 15: SHA-256 deduplication keeps exactly one copy**
    - **Validates: Requirements 5.3**

  - [x] 12.4 Write property test — Property 16: data.yaml contains canonical classes and valid split paths
    - **Property 16: data.yaml contains canonical classes and valid split paths**
    - **Validates: Requirements 5.4**

  - [x] 12.5 Write property test — Property 17: class imbalance warning fires at correct threshold
    - **Property 17: Class imbalance warning fires at correct threshold**
    - **Validates: Requirements 5.6, 11.2**

  - [x] 12.6 Write unit tests for Dataset_Merger (`tests/test_merger.py`)
    - Test duplicate detection, re-indexing, data.yaml content, imbalance warning
    - _Requirements: 5.1–5.6_

- [x] 13. Training_Manager — project init and hardware profiles (`anti_uav/trainer.py`)
  - Implement `initialize_project_dirs(root: Path)`: create `datasets/`, `merged_dataset/`, `training/`, `documentations/`, `comparison/` if absent; place `README.md` in each; leave existing dirs unchanged
  - Implement `get_hardware_profile(profile: HardwareProfile) -> TrainingConfig` with RTX 2070 and Colab T4 profiles including all augmentation defaults
  - Implement `create_run_folder(base, model_variant) -> Path` using `run_{YYYYMMDD}_{HHMMSS}_{model_variant}/` pattern
  - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 7.1, 12.1, 12.2, 12.3_

  - [x] 13.1 Write property test — Property 18: hardware profile suggestions are complete
    - **Property 18: Hardware profile suggestions are complete**
    - **Validates: Requirements 6.1, 6.5**

  - [x] 13.2 Write property test — Property 19: training config round-trip via YAML
    - **Property 19: Training config round-trip via YAML**
    - **Validates: Requirements 6.6**

  - [x] 13.3 Write property test — Property 20: run folder name matches required pattern
    - **Property 20: Run folder name matches required pattern**
    - **Validates: Requirements 7.1**

  - [x]* 13.4 Write property test — Property 31: project initialization is idempotent
    - **Property 31: Project initialization is idempotent**
    - **Validates: Requirements 12.3**

- [x] 14. Training_Manager — training launch, interruption, and resume (`anti_uav/trainer.py`)
  - Implement `launch_training(config, run_dir) -> TrainingResult`: save `train_config.yaml` atomically, call `ultralytics YOLO(model).train(...)`, catch `KeyboardInterrupt` and PyTorch OOM `RuntimeError`, write `results.json` with `completed=False` on interruption
  - Implement `resume_training(run_dir) -> TrainingResult`: load last checkpoint, re-launch with `resume=True`
  - Save final weights, training curves, confusion matrix to run subfolder
  - _Requirements: 7.2, 7.3, 7.4, 7.5_

  - [x] 14.1 Write unit tests for Training_Manager (`tests/test_trainer.py`)
    - Mock `ultralytics.YOLO`; test run folder creation, config YAML save, interruption handling, resume logic
    - _Requirements: 6.1–6.6, 7.1–7.5_

- [x] 15. Validation (`anti_uav/trainer.py`)
  - Implement `evaluate_model(weights_path, data_yaml, run_dir) -> ValidationMetrics`: run YOLO validation, extract per-class mAP@0.5, small-object mAP (bbox area < 32×32), precision, recall, F1, false positive rate on background patches
  - Set `passed_gate = map50 >= 0.75`; flag STAL recommendation when `small_object_map50[cls] < per_class_map50[cls] - 0.15`
  - Generate PR curve images per canonical class, save to `run_dir/plots/`
  - _Requirements: 13.1, 13.2, 13.3, 13.4_

  - [x] 15.1 Write property test — Property 21: results.json contains all required metric fields
    - **Property 21: results.json contains all required metric fields**
    - **Validates: Requirements 7.3, 13.1**

  - [x] 15.2 Write property test — Property 22: pass gate status is correct
    - **Property 22: Pass gate status is correct**
    - **Validates: Requirements 13.3**

  - [x] 15.3 Write property test — Property 23: small-object mAP flag fires at correct threshold
    - **Property 23: Small-object mAP flag fires at correct threshold**
    - **Validates: Requirements 13.4**

  - [x] 15.4 Write property test — Property 32: PR curve files exist for each canonical class after training
    - **Property 32: PR curve files exist for each canonical class after training**
    - **Validates: Requirements 13.2**

- [x] 16. Checkpoint — ensure all training and validation tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 17. Run_Documenter (`anti_uav/documenter.py`)
  - Implement `generate_run_doc(run_dir, output_dir) -> Path`: read `results.json` and `train_config.yaml`, render Markdown with all required sections (dataset used, model variant, training parameters, hardware profile, final metrics, training duration, warnings/anomalies, plain-language justification, Validation Summary referencing DUT Anti-UAV and VisDrone benchmarks, pass/fail gate result, STAL flag if applicable, augmentation deviation note if applicable)
  - Implement `append_changelog_entry(root, run_id, metrics, passed)`: append one-line summary to `CHANGELOG.md` atomically
  - _Requirements: 8.1, 8.2, 8.3, 8.4, 13.6, 14.3_

  - [x] 17.1 Write property test — Property 24: run documentation contains all required sections
    - **Property 24: Run documentation contains all required sections**
    - **Validates: Requirements 8.2, 13.6**

  - [x] 17.2 Write property test — Property 25: non-default augmentation deviation is noted in docs
    - **Property 25: Non-default augmentation deviation is noted in docs**
    - **Validates: Requirements 8.4**

  - [x] 17.3 Write property test — Property 34: CHANGELOG.md contains entry for every completed run
    - **Property 34: CHANGELOG.md contains entry for every completed run**
    - **Validates: Requirements 14.3**

  - [x] 17.4 Write unit tests for Run_Documenter (`tests/test_documenter.py`)
    - Test section presence, STAL flag, augmentation deviation note, CHANGELOG append
    - _Requirements: 8.1–8.4, 13.6, 14.3_

- [x] 18. Run_Comparator (`anti_uav/comparator.py`)
  - Implement `highlight_param_diffs(runs) -> dict[str, list]`
  - Implement `compare_runs(run_dirs, output_dir) -> ComparisonReport`: read `results.json` from each completed run, rank by `map50_95` descending, write `.md` and `.csv` (including `small_object_map50` and `false_positive_rate` columns), include actionable improvement suggestions
  - Implement `plot_iou_sensitivity(best_run_dir, output_dir) -> Path`: plot mAP vs IoU threshold 0.5–0.95 step 0.05, save as image
  - _Requirements: 9.1, 9.2, 9.3, 9.4, 9.5, 13.5, 13.7_

  - [x] 18.1 Write property test — Property 26: comparison report includes all completed runs
    - **Property 26: Comparison report includes all completed runs**
    - **Validates: Requirements 9.1**

  - [x] 18.2 Write property test — Property 27: comparison runs are sorted by mAP@0.5:0.95 descending
    - **Property 27: Comparison runs are sorted by mAP@0.5:0.95 descending**
    - **Validates: Requirements 9.2**

  - [x] 18.3 Write property test — Property 28: comparison report produces both Markdown and CSV
    - **Property 28: Comparison report produces both Markdown and CSV**
    - **Validates: Requirements 9.4**

  - [x] 18.4 Write property test — Property 29: comparison report includes small-object mAP and FPR columns
    - **Property 29: Comparison report includes small-object mAP and FPR columns**
    - **Validates: Requirements 13.5**

  - [x] 18.5 Write unit tests for Run_Comparator (`tests/test_comparator.py`)
    - Test ranking, param diff highlighting, CSV column presence, IoU sensitivity plot file creation
    - _Requirements: 9.1–9.5, 13.5, 13.7_

- [x] 19. Checkpoint — ensure all documenter and comparator tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 20. Colab_Bridge (`anti_uav/colab_bridge.py`)
  - Add `RemoteBackend` and `KernelStatus` enums to `anti_uav/models.py`
  - Add `KAGGLE_DUAL_T4` to `HardwareProfile` enum in `anti_uav/models.py`
  - **Colab backend:** Implement `authenticate_google`, `upload_to_drive` (resume support, `UploadManifest`), `retry_failed_uploads`, `download_from_drive`
  - **Kaggle backend:** Implement `authenticate_kaggle` (loads `kaggle.json`), `upload_dataset_to_kaggle` (`kaggle datasets push`), `push_kaggle_kernel` (`kaggle kernels push`, fully automated), `poll_kaggle_kernel` (polls status every 30s, 9h timeout), `download_kaggle_output` (`kaggle kernels output`)
  - **Shared:** Implement `generate_notebook(config, backend, remote_folder_id)` — generates Drive-mounted `.ipynb` for Colab or Kaggle-dataset-mounted `.ipynb` for Kaggle; Kaggle variant sets `device: "0,1"` when profile is `KAGGLE_DUAL_T4`
  - Implement Kaggle timeout handling: on 9h timeout, download partial outputs, write `results.json` with `completed=False`
  - Add `--backend colab|kaggle` flag to CLI
  - _Requirements: 10.1–10.5_

  - [x] 20.1 Write property test — Property 30: generated notebook is valid and contains required cells (both backends)
    - **Property 30: Generated notebook is valid and contains required cells**
    - **Validates: Requirements 10.2, 10.3**

  - [x] 20.2 Write unit tests for Colab_Bridge (`tests/test_colab_bridge.py`)
    - Mock Google Drive API; test upload manifest, retry logic, download, auth failure
    - Mock Kaggle API (`kaggle` CLI calls via `subprocess`); test kernel push, status polling, timeout handling, output download
    - _Requirements: 10.1–10.5_

- [x] 21. Manual_Generator (`anti_uav/manual_generator.py`)
  - Implement `generate_manual(root: Path) -> Path`: write `MANUAL.md` at project root with all eight required sections (Project Overview, Folder Structure, Step-by-Step Procedure, Trained Weights Guide, Results Interpretation, Run Comparison Guide, Troubleshooting, Glossary); include dedicated Colab subsection in Step-by-Step Procedure
  - _Requirements: 14.1, 14.2, 14.4, 14.5_

  - [x] 21.1 Write property test — Property 33: MANUAL.md contains all required sections
    - **Property 33: MANUAL.md contains all required sections**
    - **Validates: Requirements 14.2**

  - [x] 21.2 Write unit tests for Manual_Generator (`tests/test_manual_generator.py`)
    - Test all eight section headings present, Colab subsection present
    - _Requirements: 14.1–14.5_

- [x] 22. Unified Launcher GUI (`anti_uav/gui/launcher.py`)
  - Implement `LauncherWindow(QMainWindow)` with sidebar or tab widget containing one panel per component: Inspector, Reviewer (embed `ReviewerWindow`), Normalizer, Backend, Merger, Trainer, Documenter, Comparator, Colab Bridge, Manual Generator
  - Each panel exposes buttons that invoke the corresponding public API functions and display output/status in a `QTextEdit` log area
  - _Requirements: 4.1, 12.1_

  - [x] 22.1 Write unit tests for Launcher GUI (`tests/test_launcher.py`)
    - Use `pytest-qt` to verify window opens, all tabs/panels present, no startup errors
    - _Requirements: 4.1_

- [x] 23. CLI entry points (`anti_uav/__main__.py` and `anti_uav/cli.py`)
  - Implement `argparse` top-level parser with subcommands: `inspect`, `review`, `normalize`, `backend`, `merge`, `train`, `document`, `compare`, `colab`, `manual`
  - Wire each subcommand to the corresponding public API function
  - `anti-uav` with no subcommand launches `LauncherWindow`
  - Add `--verbose` flag to all subcommands, calling `configure_logging(verbose=True)`
  - _Requirements: 1.1, 3.1, 4.1, 5.1, 6.1, 7.1, 8.1, 9.1, 10.1, 14.1_

  - [x] 23.1 Write unit tests for CLI (`tests/test_cli.py`)
    - Test each subcommand routes to the correct function with correct arguments (mock all API functions)
    - _Requirements: all CLI-facing requirements_

- [x] 24. Checkpoint — ensure all component and CLI tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 25. Integration tests
  - [ ] 25.1 Write integration test — Label Studio sync (`tests/integration/test_label_studio_sync.py`)
    - Verify Label Studio SDK sync call is made after normalization (mocked SDK)
    - _Requirements: 3.6, 4.2, 4.3_

  - [ ] 25.2 Write integration test — Colab Bridge (`tests/integration/test_colab_bridge.py`)
    - Verify Drive API upload/download calls with mocked Drive service; test retry skips already-uploaded files
    - _Requirements: 10.1–10.6_

  - [ ] 25.3 Write integration test — end-to-end training pipeline (`tests/integration/test_training_pipeline.py`)
    - Synthetic dataset (10 images, 5 epochs); run inspect → normalize → merge → train → document → compare
    - _Requirements: 7.1–7.5, 8.1, 9.1, 13.1–13.4_

- [ ] 26. Smoke tests
  - [ ] 26.1 Write smoke test — project initialization (`tests/smoke/test_init.py`)
    - Verify `initialize_project_dirs` creates all required folders and READMEs
    - _Requirements: 12.1, 12.2_

  - [ ] 26.2 Write smoke test — launcher start (`tests/smoke/test_launcher.py`)
    - Verify `LauncherWindow` instantiates without error using `pytest-qt`
    - _Requirements: 4.1_

  - [ ] 26.3 Write smoke test — manual generation (`tests/smoke/test_manual_generation.py`)
    - Verify `generate_manual` creates `MANUAL.md` with non-zero size
    - _Requirements: 14.1_

- [x] 27. Final checkpoint — ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for a faster MVP
- Property tests use `hypothesis` with `settings(max_examples=100)` and the tag format `# Feature: anti-uav-dataset-workflow, Property {N}: {property_text}`
- All file writes use `atomic_write` from `anti_uav/utils.py` (write to `.tmp` then `os.replace`)
- External services (Label Studio, Google Drive) are always mocked in unit tests
- The `anti-uav` CLI entry point with no subcommand launches the unified PyQt5 GUI
