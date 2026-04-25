#!/usr/bin/env python3
"""
Anti-UAV Workflow Launcher
--------------------------
Run directly:   python launch.py
Pick dataset:   python launch.py uavs
Full launcher:  python launch.py --gui

Uses the local .venv automatically if present.
"""
import os
import sys
import subprocess
from pathlib import Path

ROOT = Path(__file__).parent
VENV_PYTHON = ROOT / ".venv" / "bin" / "python"
DATASETS_DIR = ROOT / "datasets"
MERGED_DIRS = [ROOT / "merged_dataset_2class", ROOT / "merged_dataset"]


def get_python() -> str:
    """Return path to venv python if available, else current interpreter."""
    if VENV_PYTHON.is_file():
        return str(VENV_PYTHON)
    return sys.executable


def list_datasets() -> list[Path]:
    if not DATASETS_DIR.is_dir():
        return []
    return sorted(p for p in DATASETS_DIR.iterdir() if p.is_dir())


def open_reviewer(dataset_path: Path, python: str) -> None:
    print(f"Opening reviewer for: {dataset_path.name}")
    subprocess.run([python, "-m", "anti_uav", "review", str(dataset_path)])


def open_launcher(python: str) -> None:
    print("Opening full launcher GUI...")
    subprocess.run([python, "-m", "anti_uav"])


def main() -> None:
    python = get_python()

    # Check venv exists
    if not VENV_PYTHON.is_file():
        print("Warning: .venv not found. Using system Python.")
        print("To set up the venv run:")
        print("  python -m venv .venv")
        print("  source .venv/bin/activate.fish")
        print("  pip install -e '.[dev]'")
        print()

    args = sys.argv[1:]

    # --gui flag → open full launcher
    if "--gui" in args:
        open_launcher(python)
        return

    # Dataset name passed directly
    if args:
        name = args[0]
        dataset = DATASETS_DIR / name
        if dataset.is_dir():
            open_reviewer(dataset, python)
        else:
            print(f"Dataset '{name}' not found in {DATASETS_DIR}")
            print("Available datasets:")
            for d in list_datasets():
                print(f"  {d.name}")
            sys.exit(1)
        return

    # Interactive menu
    datasets = list_datasets()
    # Add merged datasets to the list
    for m in MERGED_DIRS:
        if m.is_dir():
            datasets.append(m)

    if not datasets:
        print("No datasets found in datasets/. Opening full launcher...")
        open_launcher(python)
        return

    print("Anti-UAV Workflow Launcher")
    print("-" * 30)
    print("Available datasets:")
    for i, d in enumerate(datasets, 1):
        # Count images quickly
        n = sum(1 for _ in (d / "train" / "images").glob("*") if _.is_file()) if (d / "train" / "images").is_dir() else 0
        print(f"  {i}) {d.name}  ({n} train images)")
    print(f"  0) Open full launcher GUI")
    print()

    try:
        choice = input("Select [0-{}]: ".format(len(datasets))).strip()
    except (KeyboardInterrupt, EOFError):
        print("\nCancelled.")
        return

    if choice == "0":
        open_launcher(python)
    elif choice.isdigit() and 1 <= int(choice) <= len(datasets):
        open_reviewer(datasets[int(choice) - 1], python)
    else:
        print("Invalid selection.")
        sys.exit(1)


if __name__ == "__main__":
    main()
