"""LauncherWindow — unified GUI launcher for the Anti-UAV dataset workflow."""
from __future__ import annotations

try:
    from PyQt5.QtWidgets import (
        QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
        QTabWidget, QLabel, QPushButton, QLineEdit,
        QComboBox, QTextEdit, QApplication, QFileDialog,
    )
    from PyQt5.QtCore import Qt
    _QT_AVAILABLE = True
except ImportError:
    _QT_AVAILABLE = False


if _QT_AVAILABLE:
    from anti_uav.gui.reviewer_ui import ReviewerWindow

    class LauncherWindow(QMainWindow):
        """Unified launcher window with one tab per pipeline component."""

        def __init__(self, parent=None) -> None:
            super().__init__(parent)
            self.setWindowTitle("Anti-UAV Dataset Workflow Launcher")
            self.resize(900, 600)

            self._tabs = QTabWidget()
            self.setCentralWidget(self._tabs)

            # Keep a reference to each tab's log area keyed by tab index
            self._log_areas: list[QTextEdit] = []

            self._build_inspector_tab()
            self._build_reviewer_tab()
            self._build_normalizer_tab()
            self._build_backend_tab()
            self._build_merger_tab()
            self._build_trainer_tab()
            self._build_documenter_tab()
            self._build_comparator_tab()
            self._build_colab_tab()
            self._build_manual_tab()

        # ------------------------------------------------------------------ #
        # Public API                                                           #
        # ------------------------------------------------------------------ #

        def log(self, message: str) -> None:
            """Append *message* to the current tab's log area."""
            idx = self._tabs.currentIndex()
            if 0 <= idx < len(self._log_areas):
                self._log_areas[idx].append(message)

        # ------------------------------------------------------------------ #
        # Tab builders                                                         #
        # ------------------------------------------------------------------ #

        def _make_tab(self, title: str) -> tuple[QWidget, QVBoxLayout, QTextEdit]:
            """Return (widget, layout, log_area) and register the tab."""
            widget = QWidget()
            layout = QVBoxLayout(widget)
            log_area = QTextEdit()
            log_area.setReadOnly(True)
            log_area.setMaximumHeight(120)
            self._tabs.addTab(widget, title)
            self._log_areas.append(log_area)
            return widget, layout, log_area

        def _build_inspector_tab(self) -> None:
            _w, layout, log = self._make_tab("Inspector")
            layout.addWidget(QLabel("Inspect a dataset directory for annotation format and statistics."))
            self._inspector_path = QLineEdit()
            self._inspector_path.setPlaceholderText("Dataset path…")
            layout.addWidget(self._inspector_path)
            btn = QPushButton("Run Inspector")
            btn.clicked.connect(lambda: self.log("Inspector: running…"))
            layout.addWidget(btn)
            layout.addWidget(log)

        def _build_reviewer_tab(self) -> None:
            _w, layout, log = self._make_tab("Reviewer")

            # Path row
            path_row = QHBoxLayout()
            self._reviewer_path = QLineEdit()
            self._reviewer_path.setPlaceholderText("Dataset split path (e.g. merged_dataset_2class/train)…")
            self._reviewer_path.setText("/home/safsaf/Projects/UAV-dataset-workflow/merged_dataset_2class/train")
            path_row.addWidget(self._reviewer_path)
            browse_btn = QPushButton("Browse…")
            browse_btn.setFixedWidth(80)
            browse_btn.clicked.connect(self._on_reviewer_browse)
            path_row.addWidget(browse_btn)
            load_btn = QPushButton("Load Dataset")
            load_btn.setFixedWidth(100)
            load_btn.clicked.connect(self._on_reviewer_load)
            path_row.addWidget(load_btn)
            layout.addLayout(path_row)

            # Reviewer widget placeholder — replaced on load
            self._reviewer_container = QWidget()
            self._reviewer_container_layout = QVBoxLayout(self._reviewer_container)
            self._reviewer_container_layout.setContentsMargins(0, 0, 0, 0)
            self._reviewer_widget: "ReviewerWindow | None" = None
            placeholder = QLabel("Enter a dataset split path above and click Load Dataset.")
            placeholder.setAlignment(Qt.AlignCenter)
            placeholder.setStyleSheet("color: #888; font-size: 13px;")
            self._reviewer_container_layout.addWidget(placeholder)
            layout.addWidget(self._reviewer_container, stretch=1)
            layout.addWidget(log)

        def _on_reviewer_browse(self) -> None:
            from PyQt5.QtWidgets import QFileDialog
            path = QFileDialog.getExistingDirectory(self, "Select dataset split folder",
                                                    self._reviewer_path.text())
            if path:
                self._reviewer_path.setText(path)

        def _on_reviewer_load(self) -> None:
            from pathlib import Path
            path = Path(self._reviewer_path.text().strip())
            if not path.is_dir():
                self.log(f"Reviewer: path not found — {path}")
                return
            # Clear container
            while self._reviewer_container_layout.count():
                item = self._reviewer_container_layout.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()
            self._reviewer_widget = ReviewerWindow(dataset_path=path)
            self._reviewer_container_layout.addWidget(self._reviewer_widget)
            self.log(f"Reviewer: loaded {path}")

        def _build_normalizer_tab(self) -> None:
            _w, layout, log = self._make_tab("Normalizer")
            layout.addWidget(QLabel("Normalize class labels across a dataset."))
            self._normalizer_path = QLineEdit()
            self._normalizer_path.setPlaceholderText("Dataset path…")
            layout.addWidget(self._normalizer_path)
            self._normalizer_mapping = QLineEdit()
            self._normalizer_mapping.setPlaceholderText("Mapping JSON path…")
            layout.addWidget(self._normalizer_mapping)
            btn = QPushButton("Run Normalizer")
            btn.clicked.connect(lambda: self.log("Normalizer: running…"))
            layout.addWidget(btn)
            layout.addWidget(log)

        def _build_backend_tab(self) -> None:
            _w, layout, log = self._make_tab("Backend")
            layout.addWidget(QLabel("Manage the Label Studio backend server."))
            row = QHBoxLayout()
            start_btn = QPushButton("Start Label Studio")
            start_btn.clicked.connect(lambda: self.log("Backend: starting Label Studio…"))
            row.addWidget(start_btn)
            stop_btn = QPushButton("Stop Label Studio")
            stop_btn.clicked.connect(lambda: self.log("Backend: stopping Label Studio…"))
            row.addWidget(stop_btn)
            layout.addLayout(row)
            layout.addWidget(log)

        def _build_merger_tab(self) -> None:
            _w, layout, log = self._make_tab("Merger")
            layout.addWidget(QLabel("Merge multiple datasets into one canonical dataset."))
            btn = QPushButton("Merge Datasets")
            btn.clicked.connect(lambda: self.log("Merger: merging datasets…"))
            layout.addWidget(btn)
            layout.addWidget(log)

        def _build_trainer_tab(self) -> None:
            _w, layout, log = self._make_tab("Trainer")
            layout.addWidget(QLabel("Train a YOLO model on the prepared dataset."))
            self._profile_combo = QComboBox()
            self._profile_combo.addItems(["rtx2070", "colab_t4", "kaggle_dual_t4"])
            layout.addWidget(self._profile_combo)
            btn = QPushButton("Start Training")
            btn.clicked.connect(lambda: self.log(
                f"Trainer: starting with profile '{self._profile_combo.currentText()}'…"
            ))
            layout.addWidget(btn)
            layout.addWidget(log)

        def _build_documenter_tab(self) -> None:
            _w, layout, log = self._make_tab("Documenter")
            layout.addWidget(QLabel("Generate dataset documentation and reports."))
            btn = QPushButton("Generate Documentation")
            btn.clicked.connect(lambda: self.log("Documenter: generating documentation…"))
            layout.addWidget(btn)
            layout.addWidget(log)

        def _build_comparator_tab(self) -> None:
            _w, layout, log = self._make_tab("Comparator")
            layout.addWidget(QLabel("Compare training runs and select the best model."))
            btn = QPushButton("Compare Runs")
            btn.clicked.connect(lambda: self.log("Comparator: comparing runs…"))
            layout.addWidget(btn)
            layout.addWidget(log)

        def _build_colab_tab(self) -> None:
            _w, layout, log = self._make_tab("Colab Bridge")
            layout.addWidget(QLabel("Push datasets or notebooks to a remote training backend."))
            self._backend_combo = QComboBox()
            self._backend_combo.addItems(["Colab", "Kaggle"])
            layout.addWidget(self._backend_combo)
            btn = QPushButton("Push to Remote")
            btn.clicked.connect(lambda: self.log(
                f"Colab Bridge: pushing to {self._backend_combo.currentText()}…"
            ))
            layout.addWidget(btn)
            layout.addWidget(log)

        def _build_manual_tab(self) -> None:
            _w, layout, log = self._make_tab("Manual")
            layout.addWidget(QLabel("Generate the user manual for the Anti-UAV workflow."))
            btn = QPushButton("Generate Manual")
            btn.clicked.connect(lambda: self.log("Manual: generating manual…"))
            layout.addWidget(btn)
            layout.addWidget(log)

else:
    class LauncherWindow:  # type: ignore[no-redef]
        """Stub — PyQt5 not available."""
        def __init__(self, *args, **kwargs) -> None:
            raise ImportError("PyQt5 is required to use LauncherWindow.")
