# Tasks

## Task List

- [x] 1. Write property-based tests for pure functions
  - [x] 1.1 Write Property 1 test: threshold selection is argmax of mean F1
  - [x] 1.2 Write Property 2 test: background candidate predicate correctness (SIDD tiny-bbox and Anti-UAV410 invisible)
  - [x] 1.3 Write Property 3 test: empty label invariant for all non-drone frames
  - [x] 1.4 Write Property 4 test: manifest completeness
  - [x] 1.5 Write Property 5 test: YOLO format round-trip (bbox conversion within 1 pixel)
  - [x] 1.6 Write Property 6 test: combined dataset membership (no test-split contamination)
  - [x] 1.7 Write Property 7 test: frame-level IoU matching correctness
  - [x] 1.8 Write Property 8 test: multi-track false positive counting on invisible frames
  - [x] 1.9 Write Property 9 test: benchmark JSON round-trip
  - [x] 1.10 Write Property 10 test: pipeline step ordering and start-from correctness
  - [x] 1.11 Write Property 11 test: log entry completeness

- [x] 2. Implement `scripts/conf_sweep.py`
  - [x] 2.1 Add CLI argument parsing (`--weights`, `--output`) with defaults
  - [x] 2.2 Implement weights-file existence check with descriptive error and sys.exit(1)
  - [x] 2.3 Implement Anti-UAV410 evaluation loop (reuse frame-level IoU logic from eval_benchmark.py)
  - [x] 2.4 Implement Anti-MUAV1 evaluation loop (reuse multi-track logic from eval_muav.py)
  - [x] 2.5 Implement SIDD val evaluation via model.val()
  - [x] 2.6 Implement mean-F1 argmax to select optimal threshold
  - [x] 2.7 Write conf_sweep_results.json with per-threshold metrics and optimal threshold
  - [x] 2.8 Print formatted summary table to stdout

- [x] 3. Implement `scripts/collect_negatives.py`
  - [x] 3.1 Add CLI argument parsing (`--target-count`, `--manifest`)
  - [x] 3.2 Implement SIDD tiny-bbox scanner (pixel area < 100 predicate)
  - [x] 3.3 Implement Anti-UAV410 invisible-frame scanner (visible=0 or bbox 0,0,0,0)
  - [x] 3.4 Implement even-sampling across sequences up to target count
  - [x] 3.5 Copy images and write empty label files to SIDD train directories
  - [x] 3.6 Write manifest file listing all added image paths
  - [x] 3.7 Log warning and skip on unreadable image files

- [x] 4. Implement `scripts/prepare_combined_dataset.py`
  - [x] 4.1 Add CLI argument parsing (`--output-dir`)
  - [x] 4.2 Implement Anti-UAV410 JSON annotation parser (x_tl, y_tl, w, h corner format)
  - [x] 4.3 Implement bbox-to-YOLO conversion: cx=(x+w/2)/W, cy=(y+h/2)/H, bw=w/W, bh=h/H
  - [x] 4.4 Write YOLO label files to `Anti-UAV410-main/yolo_labels/train/` (empty file for invisible frames)
  - [x] 4.5 Create `combined_finetune/{train,val}/{images,labels}/` directory structure
  - [x] 4.6 Symlink SIDD train and Anti-UAV410 train images/labels into combined_finetune/train/
  - [x] 4.7 Symlink SIDD val images/labels into combined_finetune/val/
  - [x] 4.8 Write data.yaml with nc:1, names:[Drone], and correct absolute paths
  - [x] 4.9 Print dataset summary with image counts per split
  - [x] 4.10 Log and skip malformed or missing annotation files without aborting

- [x] 5. Implement `scripts/benchmark_runner.py`
  - [x] 5.1 Add CLI argument parsing (`--weights`, `--conf`, `--output`)
  - [x] 5.2 Implement weights-file existence check with sys.exit(1)
  - [x] 5.3 Implement Anti-UAV410 test-split evaluation (frame-level IoU=0.5 matching)
  - [x] 5.4 Implement Anti-MUAV1 evaluation (multi-track matching, FP on invisible frames)
  - [x] 5.5 Implement SIDD val evaluation via model.val(conf=conf)
  - [x] 5.6 Skip missing benchmark directories with logged warning, continue with remaining
  - [x] 5.7 Write combined JSON results to --output path
  - [x] 5.8 Print formatted summary table to stdout

- [x] 6. Implement `scripts/finetune_train.py`
  - [x] 6.1 Add CLI argument parsing (`--data`, `--weights`)
  - [x] 6.2 Implement data.yaml existence check with descriptive error and sys.exit(1)
  - [x] 6.3 Load model from weights path and call model.train() with lr0=0.001, epochs=20, patience=8, imgsz=640, batch=8, amp=True
  - [x] 6.4 Save output to training/thermal_ft_combined_640/
  - [x] 6.5 After training, invoke benchmark_runner.py with the new best.pt and optimal conf threshold

- [x] 7. Implement `scripts/retrain_hires.py`
  - [x] 7.1 Add CLI argument parsing (`--data`)
  - [x] 7.2 Implement data.yaml existence check with sys.exit(1)
  - [x] 7.3 Load YOLO("yolo26s.pt") (no ThermalDrone weights transfer) and call model.train() with imgsz=1280, epochs=100, patience=30, lr0=0.005, batch=4, amp=True
  - [x] 7.4 Apply thermal augmentation profile: hsv_h=0, hsv_s=0, copy_paste=0.7, erasing=0.3, flipud=0.3, fliplr=0.5
  - [x] 7.5 Catch OOM exception, log warning, retry with batch=2
  - [x] 7.6 Save output to training/thermal_retrain_combined_1280/
  - [x] 7.7 After training, invoke benchmark_runner.py with the new best.pt and optimal conf threshold

- [x] 8. Implement `scripts/run_pipeline.py`
  - [x] 8.1 Add CLI argument parsing (`--dry-run`, `--start-from`)
  - [x] 8.2 Define ordered step list: conf_sweep → negatives → prepare → finetune → retrain → benchmark
  - [x] 8.3 Implement --start-from filtering to skip steps before the named step
  - [x] 8.4 Implement --dry-run mode that prints commands without executing
  - [x] 8.5 Implement subprocess execution with stdout streaming and stderr capture
  - [x] 8.6 On non-zero exit: log step name + stderr, halt pipeline with sys.exit(1)
  - [x] 8.7 Log step name, elapsed time, and success/failure status after each step
  - [x] 8.8 Write timestamped log to training/thermal_improvement_pipeline.log
  - [x] 8.9 After each training step, compare new mean F1 (across all 3 benchmarks) against best seen so far; halt with "no improvement" log if delta < 0.01
