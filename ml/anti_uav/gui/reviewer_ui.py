"""GUI_Reviewer — ReviewerModel for dataset curation."""
from __future__ import annotations
from pathlib import Path
from anti_uav.inspector import detect_annotation_format, parse_yolo_txt
from anti_uav.models import Annotation, AnnotationFormat, BoundingBox, CanonicalClass, ReviewCounts
from anti_uav.utils import atomic_write, get_logger

try:
    from PyQt5.QtWidgets import (
        QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QScrollArea,
        QGridLayout, QLabel, QListWidget, QComboBox, QStatusBar,
        QPushButton, QMessageBox, QSplitter, QApplication,
    )
    from PyQt5.QtCore import Qt, QTimer
    from PyQt5.QtGui import QPixmap, QPainter, QColor, QPen
    _QT_AVAILABLE = True
except ImportError:
    _QT_AVAILABLE = False

logger = get_logger("reviewer")
_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".tiff"}
_CANONICAL_INDEX = {"Bird": 0, "Drone": 1}

# ── Quality check thresholds ─────────────────────────────────────────────────
_MAX_BBOX_AREA = 0.90   # bbox covering >90% of image → whole-frame annotation error
_EDGE_MARGIN   = 0.01   # center within 1% of border → annotation slipped off edge


def _quality_flags(boxes: list[BoundingBox]) -> list[str]:
    """Return list of issue strings for a set of bboxes. Empty = clean."""
    issues: list[str] = []
    for i, b in enumerate(boxes):
        area = b.width * b.height
        if area > _MAX_BBOX_AREA:
            issues.append(f"box {i}: oversized ({area:.0%} of image)")
        if (b.x_center < _EDGE_MARGIN or b.x_center > 1 - _EDGE_MARGIN or
                b.y_center < _EDGE_MARGIN or b.y_center > 1 - _EDGE_MARGIN):
            issues.append(f"box {i}: center at edge ({b.x_center:.2f},{b.y_center:.2f})")
    # Check for nested boxes
    for i, a in enumerate(boxes):
        for j, b in enumerate(boxes):
            if i >= j:
                continue
            ax1, ay1 = a.x_center - a.width/2, a.y_center - a.height/2
            ax2, ay2 = a.x_center + a.width/2, a.y_center + a.height/2
            bx1, by1 = b.x_center - b.width/2, b.y_center - b.height/2
            bx2, by2 = b.x_center + b.width/2, b.y_center + b.height/2
            if ax1 <= bx1 and ay1 <= by1 and ax2 >= bx2 and ay2 >= by2:
                issues.append(f"box {j} fully inside box {i}")
    return issues


class ReviewerModel:
    """Model layer for the GUI_Reviewer. Holds state; no Qt dependency."""

    def __init__(self) -> None:
        self._dataset_path: Path | None = None
        self._format: AnnotationFormat = AnnotationFormat.UNKNOWN
        self._images: list[Path] = []
        self._annotations: dict[Path, Annotation] = {}
        self._staged: set[Path] = set()
        self._flagged: dict[Path, list[str]] = {}   # img → list of issue strings

    def load_dataset(self, path: Path) -> None:
        """Scan path for images and load annotations using inspector parsers."""
        self._dataset_path = path
        self._format = detect_annotation_format(path)
        self._images = []
        self._annotations = {}
        self._staged = set()
        self._flagged = {}
        for ext in _IMAGE_EXTENSIONS:
            self._images.extend(path.rglob(f"*{ext}"))
            self._images.extend(path.rglob(f"*{ext.upper()}"))
        self._images = sorted(set(self._images))
        raw: list[Annotation] = []
        if self._format == AnnotationFormat.YOLO_TXT:
            labels_dir = path / "labels"
            if labels_dir.is_dir():
                raw = parse_yolo_txt(labels_dir)
            else:
                txt_dirs = {
                    f.parent for f in path.rglob("*.txt")
                    if f.name not in {"classes.txt", "obj.names"}
                }
                for d in sorted(txt_dirs):
                    raw.extend(parse_yolo_txt(d))
        for ann in raw:
            self._annotations[ann.image_path] = ann
        # Run quality check on all loaded annotations
        for img_path, ann in self._annotations.items():
            if not ann.boxes:
                self._flagged[img_path] = ["empty annotation (no bboxes)"]
            else:
                issues = _quality_flags(ann.boxes)
                if issues:
                    self._flagged[img_path] = issues

    def get_flags(self, image_path: Path) -> list[str]:
        """Return quality issues for image_path, or empty list if clean."""
        return self._flagged.get(image_path, [])

    @property
    def flagged(self) -> dict[Path, list[str]]:
        return dict(self._flagged)

    def stage_deletion(self, image_path: Path) -> None:
        self._staged.add(image_path)

    def unstage_deletion(self, image_path: Path) -> None:
        self._staged.discard(image_path)

    def confirm_deletions(self) -> list[Path]:
        deleted: list[Path] = []
        for img_path in list(self._staged):
            if img_path.is_file():
                img_path.unlink()
            deleted.append(img_path)
            ann_path = self._annotation_path(img_path)
            if ann_path is not None and ann_path.is_file():
                ann_path.unlink()
            self._annotations.pop(img_path, None)
            if img_path in self._images:
                self._images.remove(img_path)
        self._staged.clear()
        return deleted

    def remap_label(self, image_path: Path, bbox_idx: int, new_label: CanonicalClass) -> None:
        ann = self._annotations.get(image_path)
        if ann is None:
            return
        if 0 <= bbox_idx < len(ann.boxes):
            b = ann.boxes[bbox_idx]
            ann.boxes[bbox_idx] = BoundingBox(
                class_name=new_label.value,
                x_center=b.x_center, y_center=b.y_center,
                width=b.width, height=b.height,
            )

    def save_changes(self) -> None:
        for img_path, ann in self._annotations.items():
            if ann.source_format != AnnotationFormat.YOLO_TXT:
                continue
            ann_path = self._annotation_path(img_path)
            if ann_path is None:
                continue
            lines: list[str] = []
            for box in ann.boxes:
                try:
                    cls_idx = int(box.class_name)
                except ValueError:
                    cls_idx = _CANONICAL_INDEX.get(box.class_name, 0)
                lines.append(f"{cls_idx} {box.x_center} {box.y_center} {box.width} {box.height}")
            atomic_write(ann_path, "\n".join(lines))

    def get_counts(self) -> ReviewCounts:
        per_class: dict[str, int] = {}
        for img_path, ann in self._annotations.items():
            if img_path not in self._staged:
                for box in ann.boxes:
                    per_class[box.class_name] = per_class.get(box.class_name, 0) + 1
        return ReviewCounts(
            total=len(self._images),
            staged_for_deletion=len(self._staged),
            per_class=per_class,
        )

    def filter_by_class(self, cls: str | None) -> list[Path]:
        if cls is None:
            return list(self._images)
        if cls == "⚠ Flagged":
            return [p for p in self._images if p in self._flagged]
        return [p for p in self._images
                if any(b.class_name == cls for b in (self._annotations.get(p) or Annotation(p, [], self._format)).boxes)]

    @property
    def images(self) -> list[Path]:
        return list(self._images)

    @property
    def staged(self) -> set[Path]:
        return set(self._staged)

    @property
    def format(self) -> AnnotationFormat:
        return self._format

    def get_annotation(self, image_path: Path) -> Annotation | None:
        return self._annotations.get(image_path)

    def _annotation_path(self, image_path: Path) -> Path | None:
        if self._format == AnnotationFormat.YOLO_TXT:
            labels_dir = image_path.parent.parent / "labels"
            if labels_dir.is_dir():
                return labels_dir / (image_path.stem + ".txt")
            return image_path.with_suffix(".txt")
        return None


if _QT_AVAILABLE:
    class _ThumbLabel(QLabel):
        """Thumbnail label with hover-to-preview and shift-click batch selection."""

        def __init__(self, img_path: Path, window: "ReviewerWindow", parent=None) -> None:
            super().__init__(parent)
            self._img_path = img_path
            self._window = window
            self.setFixedSize(120, 120)
            self.setAlignment(Qt.AlignCenter)
            self.setMouseTracking(True)

        def enterEvent(self, event) -> None:  # hover → preview in detail pane
            self._window.preview_image(self._img_path)
            super().enterEvent(event)

        def mousePressEvent(self, event) -> None:
            if event.modifiers() & Qt.ShiftModifier:
                self._window.toggle_batch_select(self._img_path)
            elif self._window._current_image == self._img_path:
                self._window.deselect_image()   # click same image → deselect
            else:
                self._window.select_image(self._img_path)
            super().mousePressEvent(event)

    class ReviewerWindow(QMainWindow):
        """PyQt5 main window for the GUI_Reviewer."""

        def __init__(self, model: "ReviewerModel | None" = None, parent=None,
                     dataset_path: "Path | None" = None) -> None:
            super().__init__(parent)
            self._model = model if model is not None else ReviewerModel()
            if dataset_path is not None:
                self._model.load_dataset(dataset_path)

            self._current_image: Path | None = None
            self._batch_selected: set[Path] = set()   # shift-click selection
            self._page_size = 100
            self._current_page = 0
            self._filtered_images: list[Path] = []
            self._thumb_map: dict[str, _ThumbLabel] = {}

            self.setWindowTitle("Anti-UAV Dataset Reviewer")
            self.resize(1100, 700)

            self._status = QStatusBar()
            self.setStatusBar(self._status)

            splitter = QSplitter(Qt.Horizontal)
            self.setCentralWidget(splitter)

            # ---- Left panel ------------------------------------------------
            left_widget = QWidget()
            left_layout = QVBoxLayout(left_widget)
            left_layout.setContentsMargins(4, 4, 4, 4)

            # Filter bar — Bird / Drone / Flagged
            filter_row = QHBoxLayout()
            filter_row.addWidget(QLabel("Filter:"))
            self._filter_bar = QComboBox()
            self._filter_bar.addItems(["All", "Bird", "Drone", "⚠ Flagged"])
            self._filter_bar.currentTextChanged.connect(self._on_filter_changed)
            filter_row.addWidget(self._filter_bar)
            filter_row.addStretch()
            left_layout.addLayout(filter_row)

            # Pagination
            page_row = QHBoxLayout()
            self._prev_btn = QPushButton("◀ Prev")
            self._prev_btn.clicked.connect(self._on_prev_page)
            self._next_btn = QPushButton("Next ▶")
            self._next_btn.clicked.connect(self._on_next_page)
            self._page_label = QLabel("Page 1")
            page_row.addWidget(self._prev_btn)
            page_row.addWidget(self._page_label)
            page_row.addWidget(self._next_btn)
            page_row.addStretch()
            left_layout.addLayout(page_row)

            # Scroll grid
            self._scroll = QScrollArea()
            self._scroll.setWidgetResizable(True)
            self._grid_container = QWidget()
            self._grid_layout = QGridLayout(self._grid_container)
            self._grid_layout.setSpacing(4)
            self._scroll.setWidget(self._grid_container)
            left_layout.addWidget(self._scroll)

            splitter.addWidget(left_widget)

            # ---- Right panel -----------------------------------------------
            right_widget = QWidget()
            right_layout = QVBoxLayout(right_widget)
            right_layout.setContentsMargins(4, 4, 4, 4)

            self._detail_label = QLabel("Hover over an image to preview")
            self._detail_label.setAlignment(Qt.AlignCenter)
            self._detail_label.setFixedSize(400, 400)
            self._detail_label.setStyleSheet("border: 1px solid #888;")
            right_layout.addWidget(self._detail_label, alignment=Qt.AlignHCenter)

            self._ann_panel = QListWidget()
            self._ann_panel.setMaximumHeight(150)
            right_layout.addWidget(self._ann_panel)

            # Remap row — Bird / Drone only
            remap_row = QHBoxLayout()
            self._remap_combo = QComboBox()
            self._remap_combo.addItems(["Bird", "Drone"])
            remap_row.addWidget(self._remap_combo)
            remap_btn = QPushButton("Remap Selected")
            remap_btn.clicked.connect(self._on_remap_clicked)
            remap_row.addWidget(remap_btn)
            right_layout.addLayout(remap_row)

            # Action buttons
            btn_row = QHBoxLayout()
            stage_btn = QPushButton("Stage for Deletion")
            stage_btn.clicked.connect(self._on_stage_clicked)
            btn_row.addWidget(stage_btn)

            unstage_btn = QPushButton("Unstage")
            unstage_btn.clicked.connect(self._on_unstage_clicked)
            btn_row.addWidget(unstage_btn)

            # Batch stage button — stages all shift-selected thumbnails
            batch_stage_btn = QPushButton("Stage Batch (Shift-selected)")
            batch_stage_btn.clicked.connect(self._on_batch_stage_clicked)
            btn_row.addWidget(batch_stage_btn)

            # Stage all flagged
            flag_stage_btn = QPushButton("⚠ Stage All Flagged")
            flag_stage_btn.setStyleSheet("color: #ffee00;")
            flag_stage_btn.clicked.connect(self._on_stage_all_flagged)
            btn_row.addWidget(flag_stage_btn)

            confirm_btn = QPushButton("Confirm Deletions")
            confirm_btn.clicked.connect(self._on_confirm_clicked)
            btn_row.addWidget(confirm_btn)

            save_btn = QPushButton("Save Changes")
            save_btn.clicked.connect(self._on_save_clicked)
            btn_row.addWidget(save_btn)

            right_layout.addLayout(btn_row)

            # Batch info label
            self._batch_label = QLabel("Shift+click thumbnails to batch-select")
            self._batch_label.setStyleSheet("color: #aaa; font-size: 11px;")
            right_layout.addWidget(self._batch_label)

            right_layout.addStretch()
            splitter.addWidget(right_widget)
            splitter.setSizes([600, 500])

            self.refresh_grid()
            self._update_status_bar()

        # ------------------------------------------------------------------ #
        # Public methods                                                       #
        # ------------------------------------------------------------------ #

        def refresh_grid(self) -> None:
            while self._grid_layout.count():
                item = self._grid_layout.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()
            self._thumb_map.clear()

            current_filter = self._filter_bar.currentText()
            cls_filter = None if current_filter == "All" else current_filter
            self._filtered_images = self._model.filter_by_class(cls_filter)

            total_pages = max(1, (len(self._filtered_images) + self._page_size - 1) // self._page_size)
            self._current_page = min(self._current_page, total_pages - 1)

            start = self._current_page * self._page_size
            end = min(start + self._page_size, len(self._filtered_images))
            page_images = self._filtered_images[start:end]

            self._page_label.setText(
                f"Page {self._current_page + 1}/{total_pages}  ({len(self._filtered_images)} images)"
            )
            self._prev_btn.setEnabled(self._current_page > 0)
            self._next_btn.setEnabled(self._current_page < total_pages - 1)

            self._pending_thumbs = list(enumerate(page_images))
            self._load_next_batch()
            self._update_status_bar()

        def deselect_image(self) -> None:
            """Clear current selection."""
            if self._current_image is not None:
                self._set_thumb_border(self._current_image)
                self._current_image = None
            self._detail_label.setText("Hover over an image to preview")
            self._ann_panel.clear()
            self._update_status_bar()

        def keyPressEvent(self, event) -> None:
            """Escape clears selection and batch selection."""
            if event.key() == Qt.Key_Escape:
                self.deselect_image()
                self._batch_selected.clear()
                self._batch_label.setText("Shift+click thumbnails to batch-select")
                self.refresh_grid()
            super().keyPressEvent(event)

        def preview_image(self, path: Path) -> None:
            """Show image in detail pane on hover (no selection state change)."""
            self._render_detail(path)

        def select_image(self, path: Path) -> None:
            """Click-select: update detail view, annotation list, and highlight."""
            if self._current_image is not None:
                self._set_thumb_border(self._current_image)
            self._current_image = path
            self._set_thumb_border(path)
            self._render_detail(path)
            self._ann_panel.clear()
            # Show quality flags first
            flags = self._model.get_flags(path)
            if flags:
                for issue in flags:
                    item_text = f"⚠ {issue}"
                    self._ann_panel.addItem(item_text)
                    self._ann_panel.item(self._ann_panel.count() - 1).setForeground(
                        QColor("#ffee00")
                    )
            ann = self._model.get_annotation(path)
            if ann:
                for i, box in enumerate(ann.boxes):
                    self._ann_panel.addItem(f"{i}: {box.class_name}")

        def toggle_batch_select(self, path: Path) -> None:
            """Shift+click: add/remove from batch selection set."""
            if path in self._batch_selected:
                self._batch_selected.discard(path)
            else:
                self._batch_selected.add(path)
            self._set_thumb_border(path)
            count = len(self._batch_selected)
            self._batch_label.setText(
                f"{count} image(s) shift-selected  |  Shift+click to toggle"
            )

        # ------------------------------------------------------------------ #
        # Private helpers                                                      #
        # ------------------------------------------------------------------ #

        def _load_next_batch(self) -> None:
            batch = self._pending_thumbs[:20]
            self._pending_thumbs = self._pending_thumbs[20:]
            for idx, img_path in batch:
                row, col = divmod(idx, 4)
                thumb = self._make_thumbnail(img_path)
                self._grid_layout.addWidget(thumb, row, col)
            if self._pending_thumbs:
                QTimer.singleShot(0, self._load_next_batch)

        def _make_thumbnail(self, img_path: Path) -> "_ThumbLabel":
            label = _ThumbLabel(img_path, self)
            pixmap = QPixmap(str(img_path))
            if not pixmap.isNull():
                scaled = pixmap.scaled(116, 116, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                label.setPixmap(scaled)
            else:
                label.setText(img_path.name)
            self._thumb_map[str(img_path)] = label
            self._set_thumb_border(img_path, label=label)
            return label

        def _set_thumb_border(self, img_path: Path, label: "_ThumbLabel | None" = None) -> None:
            """Color: blue=selected, orange=batch-selected, red=staged, yellow=flagged, grey=default."""
            if label is None:
                label = self._thumb_map.get(str(img_path))
            if label is None:
                return
            if img_path == self._current_image:
                color = "#00aaff"
            elif img_path in self._batch_selected:
                color = "#ffaa00"
            elif img_path in self._model.staged:
                color = "#ff4444"
            elif self._model.get_flags(img_path):
                color = "#ffee00"   # yellow = quality issue
            else:
                color = "#555"
            label.setStyleSheet(f"border: 2px solid {color}; background: #222;")

        def _render_detail(self, path: Path) -> None:
            """Render image with bounding boxes into the detail pane."""
            pixmap = QPixmap(str(path))
            if not pixmap.isNull():
                scaled = pixmap.scaled(400, 400, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                ann = self._model.get_annotation(path)
                if ann and ann.boxes:
                    painter = QPainter(scaled)
                    colors = {
                        "Bird": QColor(0, 200, 0),
                        "Drone": QColor(0, 120, 255),
                    }
                    for box in ann.boxes:
                        color = colors.get(box.class_name, QColor(255, 255, 0))
                        pen = QPen(color, 2)
                        painter.setPen(pen)
                        w, h = scaled.width(), scaled.height()
                        x = int((box.x_center - box.width / 2) * w)
                        y = int((box.y_center - box.height / 2) * h)
                        bw = int(box.width * w)
                        bh = int(box.height * h)
                        painter.drawRect(x, y, bw, bh)
                        painter.setPen(QPen(color))
                        painter.drawText(x + 2, y - 4 if y > 12 else y + 12, box.class_name)
                    painter.end()
                self._detail_label.setPixmap(scaled)
            else:
                self._detail_label.setText(path.name)

        def _update_status_bar(self) -> None:
            counts = self._model.get_counts()
            bird = counts.per_class.get("Bird", 0)
            drone = counts.per_class.get("Drone", 0)
            batch = len(self._batch_selected)
            flagged = len(self._model.flagged)
            self._status.showMessage(
                f"Total: {counts.total} | Staged: {counts.staged_for_deletion} "
                f"| Bird: {bird} | Drone: {drone} "
                f"| ⚠ Flagged: {flagged} | Batch-selected: {batch}"
            )

        def _on_filter_changed(self, _text: str) -> None:
            self._current_page = 0
            self.refresh_grid()

        def _on_prev_page(self) -> None:
            if self._current_page > 0:
                self._current_page -= 1
                self.refresh_grid()

        def _on_next_page(self) -> None:
            total_pages = max(1, (len(self._filtered_images) + self._page_size - 1) // self._page_size)
            if self._current_page < total_pages - 1:
                self._current_page += 1
                self.refresh_grid()

        def _on_remap_clicked(self) -> None:
            if self._current_image is None:
                return
            row = self._ann_panel.currentRow()
            if row < 0:
                return
            new_label = CanonicalClass(self._remap_combo.currentText())
            self._model.remap_label(self._current_image, row, new_label)
            self.select_image(self._current_image)
            self._update_status_bar()

        def _on_stage_clicked(self) -> None:
            if self._current_image is not None:
                self._model.stage_deletion(self._current_image)
                self._set_thumb_border(self._current_image)
                self._update_status_bar()

        def _on_unstage_clicked(self) -> None:
            if self._current_image is not None:
                self._model.unstage_deletion(self._current_image)
                self._set_thumb_border(self._current_image)
                self._update_status_bar()

        def _on_stage_all_flagged(self) -> None:
            """Stage all quality-flagged images for deletion."""
            flagged = list(self._model.flagged.keys())
            if not flagged:
                QMessageBox.information(self, "No flagged images",
                                        "No quality issues detected in this dataset.")
                return
            reply = QMessageBox.question(
                self, "Stage All Flagged",
                f"Stage {len(flagged)} flagged image(s) for deletion?\n\n"
                "Review them first with Filter → ⚠ Flagged.",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
            )
            if reply == QMessageBox.Yes:
                for path in flagged:
                    self._model.stage_deletion(path)
                    self._set_thumb_border(path)
                self._update_status_bar()

        def _on_batch_stage_clicked(self) -> None:
            """Stage all shift-selected images for deletion."""
            if not self._batch_selected:
                QMessageBox.information(self, "No batch selection",
                                        "Shift+click thumbnails to select a batch first.")
                return
            count = len(self._batch_selected)
            reply = QMessageBox.question(
                self, "Stage Batch",
                f"Stage {count} selected image(s) for deletion?",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
            )
            if reply == QMessageBox.Yes:
                for path in list(self._batch_selected):
                    self._model.stage_deletion(path)
                    self._set_thumb_border(path)
                self._batch_selected.clear()
                self._batch_label.setText("Shift+click thumbnails to batch-select")
                self._update_status_bar()

        def _on_confirm_clicked(self) -> None:
            staged_count = len(self._model.staged)
            if staged_count == 0:
                QMessageBox.information(self, "Nothing staged", "No images are staged for deletion.")
                return
            reply = QMessageBox.question(
                self, "Confirm Deletions",
                f"Permanently delete {staged_count} image(s) and their annotations?",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
            )
            if reply == QMessageBox.Yes:
                self._model.confirm_deletions()
                self._current_image = None
                self._batch_selected.clear()
                self._current_page = 0
                self._detail_label.setText("Hover over an image to preview")
                self._ann_panel.clear()
                self.refresh_grid()

        def _on_save_clicked(self) -> None:
            self._model.save_changes()
            self._status.showMessage("Changes saved.", 3000)

else:
    class ReviewerWindow:  # type: ignore[no-redef]
        def __init__(self, *args, **kwargs) -> None:
            raise ImportError("PyQt5 is required to use ReviewerWindow.")
