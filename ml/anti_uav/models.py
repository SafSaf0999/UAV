from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


class AnnotationFormat(Enum):
    YOLO_TXT = "yolo_txt"
    COCO_JSON = "coco_json"
    PASCAL_VOC = "pascal_voc"
    UNKNOWN = "unknown"


class CanonicalClass(str, Enum):
    BIRD = "Bird"
    DRONE = "Drone"


class HardwareProfile(str, Enum):
    RTX2070 = "rtx2070"
    COLAB_T4 = "colab_t4"
    KAGGLE_DUAL_T4 = "kaggle_dual_t4"


class AuthMethod(str, Enum):
    OAUTH2 = "oauth2"
    SERVICE_ACCOUNT = "service_account"


class RemoteBackend(str, Enum):
    COLAB = "colab"
    KAGGLE = "kaggle"


class KernelStatus(str, Enum):
    RUNNING = "running"
    COMPLETE = "complete"
    ERROR = "error"
    QUEUED = "queued"


@dataclass
class BoundingBox:
    class_name: str
    x_center: float
    y_center: float
    width: float
    height: float


@dataclass
class Annotation:
    image_path: Path
    boxes: list[BoundingBox]
    source_format: AnnotationFormat


@dataclass
class DatasetStats:
    image_count: int
    class_counts: dict[str, int]
    resolution_distribution: dict[str, int]
    aspect_ratio_distribution: dict[str, int]
    bbox_size_distribution: dict[str, int]
    class_balance_ratio: float
    augmentation_recommendations: list[str] = field(default_factory=list)


@dataclass
class InspectionReport:
    dataset_path: str
    annotation_format: AnnotationFormat
    stats: DatasetStats
    errors: list[str]


@dataclass
class NormalizationLog:
    substitutions: list[tuple[str, str, int]]
    total_files_modified: int
    unmapped_classes: list[str]


@dataclass
class MergeReport:
    total_images: int
    deduplicated_count: int
    class_counts: dict[str, int]
    imbalance_warnings: list[str]
    output_path: Path


@dataclass
class TrainingConfig:
    model_variant: str
    imgsz: int
    batch: int
    epochs: int
    optimizer: str
    lr0: float
    weight_decay: float
    amp: bool
    augmentation: dict[str, float]
    hardware_profile: HardwareProfile
    data_yaml: Path
    run_dir: Path | None = None


@dataclass
class ValidationMetrics:
    map50: float
    map50_95: float
    precision: float
    recall: float
    f1: float
    per_class_map50: dict[str, float]
    small_object_map50: dict[str, float]
    false_positive_rate: float
    passed_gate: bool
    stal_recommendations: list[str] = field(default_factory=list)


@dataclass
class TrainingResult:
    run_id: str
    config: TrainingConfig
    metrics: ValidationMetrics | None
    completed: bool
    duration_seconds: float
    checkpoint_path: Path | None


@dataclass
class ReviewCounts:
    total: int
    staged_for_deletion: int
    per_class: dict[str, int]


@dataclass
class ComparisonReport:
    runs: list[TrainingResult]
    best_run_id: str
    param_diffs: dict[str, list]
    output_md: Path
    output_csv: Path


@dataclass
class UploadManifest:
    uploaded: dict[str, str]
    failed: list[str]
