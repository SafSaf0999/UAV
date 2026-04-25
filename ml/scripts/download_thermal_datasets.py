"""
Download thermal datasets for anti-UAV detection.
Run: python download_thermal_datasets.py

HIT-UAV is the only one with direct automated download.
Others require manual steps (see thermal_datasets/README.md).
"""
import os
import subprocess
import sys
from pathlib import Path

THERMAL_DIR = Path("thermal_datasets")


def download_hit_uav():
    """Download HIT-UAV from Dataset Ninja (no registration needed)."""
    print("\n=== Downloading HIT-UAV ===")
    out_dir = THERMAL_DIR / "hit_uav"
    out_dir.mkdir(exist_ok=True)

    # Dataset Ninja provides direct download via their CLI
    try:
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "-q", "dataset-tools"],
            check=True
        )
        import dataset_tools as dtools
        dtools.convert(
            dataset="HIT-UAV",
            dst_dir=str(out_dir),
            to_format="yolov8"
        )
        print(f"HIT-UAV downloaded to {out_dir}")
    except Exception as e:
        print(f"Dataset Ninja CLI failed: {e}")
        print("Manual download: https://datasetninja.com/hit-uav")
        print(f"Place files in: {out_dir}")


def clone_anti_uav():
    """Clone Anti-UAV repository."""
    print("\n=== Anti-UAV Thermal ===")
    out_dir = THERMAL_DIR / "anti_uav_thermal"
    if (out_dir / ".git").exists():
        print("Already cloned.")
        return
    print("Cloning Anti-UAV repository...")
    subprocess.run(
        ["git", "clone", "https://github.com/ZhaoJ9014/Anti-UAV", str(out_dir)],
        check=True
    )
    print(f"Cloned to {out_dir}")
    print("NOTE: Dataset files require separate download from the repo's README.")


def check_roboflow_thermal():
    """Search Roboflow for thermal drone datasets."""
    print("\n=== Roboflow Thermal Datasets ===")
    print("Search these on universe.roboflow.com:")
    print("  - 'thermal drone'")
    print("  - 'infrared UAV'")
    print("  - 'FLIR drone'")
    print("  - 'thermal bird drone'")
    print("\nOnce found, add to download_datasets.py and run it.")


def main():
    print("Thermal Dataset Downloader")
    print("=" * 40)

    # HIT-UAV — automated
    download_hit_uav()

    # Anti-UAV — clone repo
    clone_anti_uav()

    # Roboflow — manual search
    check_roboflow_thermal()

    print("\n=== Summary ===")
    print(f"Directory: {THERMAL_DIR.absolute()}")
    for d in THERMAL_DIR.iterdir():
        if d.is_dir():
            files = list(d.rglob("*"))
            print(f"  {d.name}/: {len(files)} files")

    print("\nNext steps:")
    print("1. Check thermal_datasets/README.md for manual downloads")
    print("2. Once datasets are in place, run:")
    print("   python -m anti_uav inspect thermal_datasets/hit_uav")
    print("   python -m anti_uav normalize thermal_datasets/hit_uav --mapping thermal_mapping.json")


if __name__ == "__main__":
    main()
