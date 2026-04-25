"""
Assign unique names to runs and remove 1-class baseline from comparisons.
Updates: comparison MD/CSV, documentation files, report.tex
"""
from pathlib import Path
import re

ROOT = Path("/home/safsaf/Projects/UAV-dataset-workflow")

NAME_MAP = {
    "run_2class_yolo26s_rtx2070_100ep":      "BirdDrone-RTX",
    "run_3class_yolo26s_colab_t4_100ep":     "TriClass-T4",
    "run_2class_yolo26s_colab_t4_160ep_old": "BirdDrone-T4old",
    "run_1class_yolov12n_rtx2070_100ep":     "REMOVED",
    # old labels
    "2-class ours":                          "BirdDrone-RTX",
    "YOLO26s 2-class RTX2070 (Bird/Drone)":  "BirdDrone-RTX",
    "3-class T4":                            "TriClass-T4",
    "YOLO26s 3-class T4 (Bird/Drone/UAV)":   "TriClass-T4",
    "2-class old T4":                        "BirdDrone-T4old",
    "YOLO26s 2-class T4 (Old, 160ep)":       "BirdDrone-T4old",
    "YOLOv12n 1-class (Baseline)":           "REMOVED",
}

def patch_file(path: Path) -> None:
    if not path.is_file():
        return
    text = path.read_text()
    original = text
    for old, new in NAME_MAP.items():
        text = text.replace(old, new)
    # Remove lines containing REMOVED (for MD tables)
    lines = [l for l in text.splitlines() if "REMOVED" not in l]
    text = "\n".join(lines) + "\n"
    if text != original:
        path.write_text(text)
        print(f"  Updated: {path.name}")

# Patch all comparison and documentation files
for p in (ROOT / "comparison").glob("*.md"):
    patch_file(p)
for p in (ROOT / "comparison").glob("*.csv"):
    patch_file(p)
for p in (ROOT / "documentations").glob("*.md"):
    patch_file(p)
patch_file(ROOT / "documentations" / "report.tex")

print("Done.")
