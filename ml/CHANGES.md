# Project Restructure — April 2026

## Summary

The repository was reorganized from a flat mixed structure into three clear
top-level modules. The original structure is preserved at `/mnt/Lonix/UAV`.

---

## New Structure

```
UAV/
├── docs/                        ← all written work and references
│   ├── report/                  ← updated report (April 2026)
│   │   ├── report_full.tex      ← LaTeX source (148KB, 77 pages)
│   │   ├── report_full.pdf      ← compiled PDF (2MB)
│   │   ├── figures/             ← control center screenshots
│   │   └── run_graphs/          ← training curve images (all models)
│   ├── papers/                  ← referenced academic papers (PDFs)
│   ├── guidelines/              ← thesis chapter guidelines (PDFs)
│   ├── DATASETS.md              ← dataset citations and download instructions
│   └── citations.md             ← full bibliography
│
├── control-center/              ← full working distributed detection system
│   ├── edge/                    ← edge device inference (YOLO26s + ByteTrack)
│   ├── main/                    ← FastAPI aggregation + WebSocket push
│   ├── frontend/                ← React/TypeScript control center UI
│   ├── electron/                ← desktop app (AppImage)
│   ├── docker/                  ← Docker Compose stack
│   ├── certs/                   ← TLS certificate generation
│   ├── shared/                  ← JSON schemas for MQTT payloads
│   ├── launcher_main.py         ← main device GUI launcher
│   ├── launcher_edge.py         ← edge device GUI launcher
│   └── PROJECT.md               ← full system reference document
│
├── ml/                          ← all ML training work (was: UAV-dataset-workflow)
│   ├── scripts/                 ← training, evaluation, pipeline scripts
│   ├── tests/                   ← unit + property-based tests
│   ├── anti_uav/                ← Python package (GUI, CLI, training pipeline)
│   ├── models/                  ← production model weights (.pt files)
│   ├── training/                ← training run outputs
│   ├── thermal_datasets/        ← thermal IR datasets
│   ├── datasets/                ← RGB datasets
│   ├── notebooks/               ← Colab training notebooks
│   ├── .kiro/specs/             ← feature specs (thermal improvement pipeline)
│   ├── DATASETS.md              ← dataset references
│   └── kiro.md                  ← ML project context
│
└── README.md
```

---

## What Changed

### Report
- `UAV-dataset-workflow/documentations/report_full.tex` → `docs/report/report_full.tex`
- `UAV-dataset-workflow/documentations/report_full.pdf` → `docs/report/report_full.pdf`
- All image assets (`run_graphs/`, `figures/`) moved alongside the tex file so it compiles in-place
- Old report at root (`report_full.pdf`) is the **updated April 2026 version** — same file
- The old `documentations/` folder in the original structure had an outdated 577KB PDF; the new one is 2MB (77 pages)

### ML / Training
- `UAV-dataset-workflow/` renamed to `ml/`
- `models/` (production weights) merged into `ml/models/`
- All scripts, tests, specs, and datasets remain intact

### Control Center
- `edge/`, `main/`, `frontend/`, `electron/`, `docker/` grouped under `control-center/`
- No code changes — pure reorganization

### Removed
- `UAV/UAV/` subfolder — was a partial duplicate of `frontend/` and `main/ha_bridge/` only
- `Papers/`, `paper/`, `report/` at root — merged into `docs/papers/`
- Derived ML datasets (21.5 GB freed):
  - `finetune_2class/`, `finetune_3class/` — regenerate with `scripts/build_finetune_datasets.py`
  - `dut_pseudolabels_2class/`, `dut_pseudolabels_3class/` — regenerate with `scripts/build_dut_pseudolabels.py`
  - `DUT Anti-UAV/` — re-download from https://github.com/wangdongdut/DUT-Anti-UAV
  - `Anti-UAV410-main/` — ZIP retained at `/mnt/Lonix/UAV`

---

## To Compile the Report

```fish
cd docs/report
pdflatex -interaction=nonstopmode report_full.tex
pdflatex -interaction=nonstopmode report_full.tex  # second pass for TOC
```

## To Run the Pipeline

```fish
cd ml
source .venv/bin/activate.fish
python scripts/run_pipeline.py --skip retrain
```

## Original Structure

Preserved at `/mnt/Lonix/UAV` — untouched backup of the pre-reorganization state.
