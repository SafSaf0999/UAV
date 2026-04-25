"""Unit tests for anti_uav/cli.py — verify subcommand routing via mocked API functions."""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch, call

import pytest

from anti_uav.cli import build_parser, main


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _run_main(argv: list[str]) -> None:
    """Invoke main() with the given argv list."""
    with patch.object(sys, "argv", ["anti-uav"] + argv):
        main()


# ---------------------------------------------------------------------------
# inspect
# ---------------------------------------------------------------------------

def test_cli_inspect_routes_to_inspect_dataset(tmp_path):
    """inspect <path> must call inspect_dataset with Path(args.path)."""
    mock_report = MagicMock()
    mock_report.annotation_format.value = "yolo_txt"
    mock_report.stats.image_count = 10
    mock_report.stats.class_counts = {}
    mock_report.errors = []

    with patch("anti_uav.cli.inspect_dataset", return_value=mock_report) as mock_fn:
        _run_main(["inspect", str(tmp_path)])
        mock_fn.assert_called_once_with(tmp_path)


# ---------------------------------------------------------------------------
# normalize
# ---------------------------------------------------------------------------

def test_cli_normalize_routes_to_normalize_dataset(tmp_path):
    """normalize <dataset_path> --mapping <path> must call normalize_dataset."""
    mapping_file = tmp_path / "mapping.json"
    mapping_file.write_text('{"drone": "Drone"}', encoding="utf-8")
    dataset_dir = tmp_path / "dataset"
    dataset_dir.mkdir()

    mock_mapping = {"drone": MagicMock()}
    mock_log = MagicMock()
    mock_log.total_files_modified = 1
    mock_log.substitutions = []

    with patch("anti_uav.cli.load_mapping", return_value=mock_mapping) as mock_load, \
         patch("anti_uav.cli.normalize_dataset", return_value=mock_log) as mock_fn:
        _run_main(["normalize", str(dataset_dir), "--mapping", str(mapping_file)])
        mock_load.assert_called_once_with(mapping_file)
        mock_fn.assert_called_once_with(dataset_dir, mock_mapping)


# ---------------------------------------------------------------------------
# merge
# ---------------------------------------------------------------------------

def test_cli_merge_routes_to_merge_datasets(tmp_path):
    """merge <src1> [src2 ...] --output <path> must call merge_datasets."""
    src1 = tmp_path / "src1"
    src2 = tmp_path / "src2"
    out = tmp_path / "out"
    src1.mkdir()
    src2.mkdir()

    mock_report = MagicMock()
    mock_report.total_images = 5
    mock_report.output_path = out
    mock_report.imbalance_warnings = []

    with patch("anti_uav.cli.merge_datasets", return_value=mock_report) as mock_fn:
        _run_main(["merge", str(src1), str(src2), "--output", str(out)])
        mock_fn.assert_called_once_with([src1, src2], out)


# ---------------------------------------------------------------------------
# train
# ---------------------------------------------------------------------------

def test_cli_train_routes_to_launch_training(tmp_path):
    """train --profile rtx2070 must call launch_training with the correct profile config."""
    from anti_uav.models import HardwareProfile

    mock_config = MagicMock()
    mock_result = MagicMock()
    mock_result.completed = True
    mock_result.metrics = None

    with patch("anti_uav.cli.get_hardware_profile", return_value=mock_config) as mock_profile, \
         patch("anti_uav.cli.create_run_folder", return_value=tmp_path) as mock_folder, \
         patch("anti_uav.cli.launch_training", return_value=mock_result) as mock_fn:
        _run_main(["train", "--profile", "rtx2070"])
        mock_profile.assert_called_once_with(HardwareProfile.RTX2070)
        mock_fn.assert_called_once_with(mock_config, tmp_path)


# ---------------------------------------------------------------------------
# document
# ---------------------------------------------------------------------------

def test_cli_document_routes_to_generate_run_doc(tmp_path):
    """document <run_dir> must call generate_run_doc with the run directory."""
    run_dir = tmp_path / "run_20260101_120000_yolo26s"
    run_dir.mkdir()
    mock_out = tmp_path / "doc.md"

    with patch("anti_uav.cli.generate_run_doc", return_value=mock_out) as mock_fn:
        _run_main(["document", str(run_dir)])
        mock_fn.assert_called_once_with(run_dir, Path("documentations"))


# ---------------------------------------------------------------------------
# compare
# ---------------------------------------------------------------------------

def test_cli_compare_routes_to_compare_runs(tmp_path):
    """compare <run1> [run2 ...] --output <path> must call compare_runs."""
    run1 = tmp_path / "run1"
    run2 = tmp_path / "run2"
    out = tmp_path / "comparison"
    run1.mkdir()
    run2.mkdir()

    mock_report = MagicMock()
    mock_report.output_md = out / "report.md"

    with patch("anti_uav.cli.compare_runs", return_value=mock_report) as mock_fn:
        _run_main(["compare", str(run1), str(run2), "--output", str(out)])
        mock_fn.assert_called_once_with([run1, run2], out)


# ---------------------------------------------------------------------------
# manual
# ---------------------------------------------------------------------------

def test_cli_manual_routes_to_generate_manual(tmp_path):
    """manual --output <path> must call generate_manual with the output path."""
    mock_out = tmp_path / "MANUAL.md"

    with patch("anti_uav.cli.generate_manual", return_value=mock_out) as mock_fn:
        _run_main(["manual", "--output", str(tmp_path)])
        mock_fn.assert_called_once_with(tmp_path)


def test_cli_manual_default_output():
    """manual with no --output must call generate_manual with Path('.')."""
    mock_out = Path(".") / "MANUAL.md"

    with patch("anti_uav.cli.generate_manual", return_value=mock_out) as mock_fn:
        _run_main(["manual"])
        mock_fn.assert_called_once_with(Path("."))


# ---------------------------------------------------------------------------
# verbose flag
# ---------------------------------------------------------------------------

def test_cli_verbose_flag_configures_logging(tmp_path):
    """--verbose flag must call configure_logging(verbose=True)."""
    mock_report = MagicMock()
    mock_report.annotation_format.value = "yolo_txt"
    mock_report.stats.image_count = 0
    mock_report.stats.class_counts = {}
    mock_report.errors = []

    with patch("anti_uav.cli.inspect_dataset", return_value=mock_report), \
         patch("anti_uav.cli.configure_logging") as mock_log:
        _run_main(["--verbose", "inspect", str(tmp_path)])
        mock_log.assert_called_once_with(verbose=True)


# ---------------------------------------------------------------------------
# no subcommand → GUI
# ---------------------------------------------------------------------------

def test_cli_no_subcommand_launches_gui():
    """No subcommand must instantiate LauncherWindow (QApplication mocked)."""
    mock_app_instance = MagicMock()
    mock_app_instance.exec_.return_value = 0
    mock_app_cls = MagicMock(return_value=mock_app_instance)

    mock_window = MagicMock()
    mock_launcher_cls = MagicMock(return_value=mock_window)

    mock_qt_widgets = MagicMock()
    mock_qt_widgets.QApplication = mock_app_cls

    mock_launcher_module = MagicMock()
    mock_launcher_module.LauncherWindow = mock_launcher_cls

    with patch.dict("sys.modules", {
            "PyQt5": MagicMock(),
            "PyQt5.QtWidgets": mock_qt_widgets,
            "anti_uav.gui.launcher": mock_launcher_module,
        }), \
         patch("anti_uav.cli.configure_logging"), \
         pytest.raises(SystemExit):
        _run_main([])

    mock_launcher_cls.assert_called_once()
    mock_window.show.assert_called_once()
