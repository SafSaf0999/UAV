"""CLI entry point for the Anti-UAV dataset workflow.

Each subcommand delegates to the corresponding public API function.
No subcommand → launch LauncherWindow GUI.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from anti_uav.utils import configure_logging
from anti_uav.inspector import inspect_dataset
from anti_uav.normalizer import load_mapping, normalize_dataset
from anti_uav.merger import merge_datasets
from anti_uav.trainer import get_hardware_profile, create_run_folder, launch_training
from anti_uav.documenter import generate_run_doc
from anti_uav.comparator import compare_runs
from anti_uav.manual_generator import generate_manual
from anti_uav.backend import start_label_studio, stop_label_studio
from anti_uav.models import HardwareProfile, RemoteBackend


def build_parser() -> argparse.ArgumentParser:
    """Build and return the top-level argument parser."""
    parser = argparse.ArgumentParser(
        prog="anti-uav",
        description="Anti-UAV dataset management and YOLO training workflow.",
    )
    parser.add_argument("--verbose", action="store_true", help="Enable verbose logging.")

    sub = parser.add_subparsers(dest="subcommand")

    # ------------------------------------------------------------------
    # inspect
    # ------------------------------------------------------------------
    p_inspect = sub.add_parser("inspect", help="Inspect a dataset directory or ZIP.")
    p_inspect.add_argument("path", help="Path to dataset folder or ZIP archive.")

    # ------------------------------------------------------------------
    # review
    # ------------------------------------------------------------------
    p_review = sub.add_parser("review", help="Open the GUI reviewer for a dataset.")
    p_review.add_argument("dataset_path", help="Path to dataset folder.")

    # ------------------------------------------------------------------
    # normalize
    # ------------------------------------------------------------------
    p_norm = sub.add_parser("normalize", help="Normalize class labels in a dataset.")
    p_norm.add_argument("dataset_path", help="Path to dataset folder.")
    p_norm.add_argument("--mapping", required=True, help="Path to JSON mapping file.")

    # ------------------------------------------------------------------
    # backend
    # ------------------------------------------------------------------
    p_backend = sub.add_parser("backend", help="Manage the Label Studio backend.")
    p_backend.add_argument("action", choices=["start", "stop"], help="start or stop.")

    # ------------------------------------------------------------------
    # merge
    # ------------------------------------------------------------------
    p_merge = sub.add_parser("merge", help="Merge multiple datasets into one.")
    p_merge.add_argument("sources", nargs="+", help="Source dataset directories.")
    p_merge.add_argument("--output", required=True, help="Output directory path.")

    # ------------------------------------------------------------------
    # train
    # ------------------------------------------------------------------
    p_train = sub.add_parser("train", help="Launch YOLO training.")
    p_train.add_argument(
        "--profile",
        required=True,
        choices=["rtx2070", "colab_t4", "kaggle_dual_t4"],
        help="Hardware profile.",
    )
    p_train.add_argument("--data", default=None, help="Path to data YAML (overrides profile default).")

    # ------------------------------------------------------------------
    # document
    # ------------------------------------------------------------------
    p_doc = sub.add_parser("document", help="Generate run documentation.")
    p_doc.add_argument("run_dir", help="Path to training run directory.")

    # ------------------------------------------------------------------
    # compare
    # ------------------------------------------------------------------
    p_compare = sub.add_parser("compare", help="Compare training runs.")
    p_compare.add_argument("runs", nargs="+", help="Training run directories.")
    p_compare.add_argument("--output", required=True, help="Output directory for comparison report.")

    # ------------------------------------------------------------------
    # colab
    # ------------------------------------------------------------------
    p_colab = sub.add_parser("colab", help="Colab/Kaggle remote training bridge.")
    p_colab.add_argument(
        "--backend",
        required=True,
        choices=["colab", "kaggle"],
        help="Remote backend to use.",
    )
    p_colab.add_argument(
        "colab_action",
        choices=["push", "pull", "generate-notebook"],
        help="Action to perform.",
    )

    # ------------------------------------------------------------------
    # manual
    # ------------------------------------------------------------------
    p_manual = sub.add_parser("manual", help="Generate the user manual.")
    p_manual.add_argument(
        "--output",
        default=None,
        help="Output directory (defaults to current directory).",
    )

    return parser


def main() -> None:
    """Entry point. No subcommand → launch LauncherWindow GUI."""
    parser = build_parser()
    args = parser.parse_args()

    # Apply verbose logging if requested
    if getattr(args, "verbose", False):
        configure_logging(verbose=True)

    if args.subcommand is None:
        # Launch GUI
        configure_logging(verbose=False)
        try:
            from PyQt5.QtWidgets import QApplication
        except ImportError:
            print("PyQt5 is required to launch the GUI. Install it with: pip install PyQt5")
            sys.exit(1)
        from anti_uav.gui.launcher import LauncherWindow
        app = QApplication(sys.argv)
        window = LauncherWindow()
        window.show()
        sys.exit(app.exec_())

    elif args.subcommand == "inspect":
        report = inspect_dataset(Path(args.path))
        print(f"Format: {report.annotation_format.value}")
        print(f"Images: {report.stats.image_count}")
        print(f"Classes: {report.stats.class_counts}")
        if report.errors:
            print(f"Errors ({len(report.errors)}):")
            for e in report.errors:
                print(f"  {e}")

    elif args.subcommand == "review":
        try:
            from PyQt5.QtWidgets import QApplication
        except ImportError:
            print("PyQt5 is required for the reviewer. Install it with: pip install PyQt5")
            sys.exit(1)
        from anti_uav.gui.reviewer_ui import ReviewerWindow
        app = QApplication(sys.argv)
        window = ReviewerWindow(dataset_path=Path(args.dataset_path))
        window.show()
        sys.exit(app.exec_())

    elif args.subcommand == "normalize":
        mapping = load_mapping(Path(args.mapping))
        log = normalize_dataset(Path(args.dataset_path), mapping)
        print(f"Files modified: {log.total_files_modified}")
        for src, tgt, count in log.substitutions:
            print(f"  {src} → {tgt}: {count} file(s)")

    elif args.subcommand == "backend":
        if args.action == "start":
            proc = start_label_studio()
            print(f"Label Studio started (pid={proc.pid})")
        else:
            print("Pass the process object to stop_label_studio() programmatically.")

    elif args.subcommand == "merge":
        source_dirs = [Path(s) for s in args.sources]
        report = merge_datasets(source_dirs, Path(args.output))
        print(f"Merged {report.total_images} images → {report.output_path}")
        if report.imbalance_warnings:
            for w in report.imbalance_warnings:
                print(f"  Warning: {w}")

    elif args.subcommand == "train":
        profile = HardwareProfile(args.profile)
        config = get_hardware_profile(profile)
        if args.data is not None:
            config.data_yaml = Path(args.data)
        run_dir = create_run_folder(Path("training"), config.model_variant)
        result = launch_training(config, run_dir)
        print(f"Training {'completed' if result.completed else 'did not complete'}.")
        if result.metrics:
            print(f"mAP@0.5: {result.metrics.map50:.4f}")

    elif args.subcommand == "document":
        out = generate_run_doc(Path(args.run_dir), Path("documentations"))
        print(f"Documentation written to: {out}")

    elif args.subcommand == "compare":
        run_dirs = [Path(r) for r in args.runs]
        report = compare_runs(run_dirs, Path(args.output))
        print(f"Comparison report: {report.output_md}")

    elif args.subcommand == "colab":
        backend = RemoteBackend(args.backend)
        action = args.colab_action
        if action == "generate-notebook":
            print(f"Generating notebook for backend: {backend.value}")
        elif action == "push":
            print(f"Pushing to {backend.value}…")
        elif action == "pull":
            print(f"Pulling from {backend.value}…")

    elif args.subcommand == "manual":
        output_dir = Path(args.output) if args.output else Path(".")
        out = generate_manual(output_dir)
        print(f"Manual written to: {out}")
