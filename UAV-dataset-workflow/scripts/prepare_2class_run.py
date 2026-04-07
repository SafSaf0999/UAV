"""
Prepare 2-class dataset (Bird vs Drone) from existing raw datasets.
Run after the 3-class training finishes:
    python prepare_2class_run.py

This re-normalizes and re-merges using mapping_2class.json,
outputting to merged_dataset_2class/
"""
import subprocess
import sys
from pathlib import Path

VENV_PYTHON = Path(".venv/bin/python")
python = str(VENV_PYTHON) if VENV_PYTHON.exists() else sys.executable

DATASETS = [
    "datasets/uavs",
    "datasets/yolo-exp",
    "datasets/anti-uav",
    "datasets/uavdetector",
]
MAPPING = "mapping_2class.json"
OUTPUT = "merged_dataset_2class"


def run(cmd):
    print(f"\n$ {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=False)
    if result.returncode != 0:
        print(f"ERROR: command failed with code {result.returncode}")
        sys.exit(1)


def main():
    print("=" * 50)
    print("Preparing 2-class dataset: Bird vs Drone")
    print("UAV + Drone → merged into 'Drone' class")
    print("=" * 50)

    # Step 1: Re-normalize each dataset with 2-class mapping
    # Note: datasets are already normalized with 3-class mapping
    # We need to re-normalize from scratch — restore from backup first
    print("\nStep 1: Restoring raw datasets from backup...")
    import tarfile, shutil, os

    backup = Path("datasets/backup_raw_datasets.tar.gz")
    if not backup.exists():
        print("ERROR: datasets/backup_raw_datasets.tar.gz not found")
        print("Cannot re-normalize without the original raw datasets")
        sys.exit(1)

    # Extract to a temp location
    temp_dir = Path("datasets_raw_temp")
    if temp_dir.exists():
        shutil.rmtree(temp_dir)
    temp_dir.mkdir()

    print(f"Extracting {backup} to {temp_dir}...")
    with tarfile.open(backup) as tf:
        tf.extractall(temp_dir)

    # Find extracted dataset dirs
    raw_dirs = []
    for name in ["uavs", "yolo-exp", "anti-uav", "uavdetector"]:
        # Search in temp_dir
        for p in temp_dir.rglob(name):
            if p.is_dir():
                raw_dirs.append(str(p))
                break

    if not raw_dirs:
        # Try direct paths
        raw_dirs = [str(temp_dir / "datasets" / name)
                    for name in ["uavs", "yolo-exp", "anti-uav", "uavdetector"]]

    print(f"Found {len(raw_dirs)} dataset directories")

    # Step 2: Normalize each with 2-class mapping
    print("\nStep 2: Normalizing with 2-class mapping...")
    for ds in raw_dirs:
        if Path(ds).exists():
            run([python, "-m", "anti_uav", "normalize", ds, "--mapping", MAPPING])
        else:
            print(f"WARNING: {ds} not found, skipping")

    # Step 3: Merge into 2-class output
    print(f"\nStep 3: Merging into {OUTPUT}/...")
    merge_cmd = [python, "-m", "anti_uav", "merge"] + raw_dirs + ["--output", OUTPUT]
    run(merge_cmd)

    # Step 4: Verify
    import yaml
    data_yaml = Path(OUTPUT) / "data.yaml"
    if data_yaml.exists():
        with open(data_yaml) as f:
            cfg = yaml.safe_load(f)
        print(f"\n=== 2-class dataset ready ===")
        print(f"Classes: {cfg['names']}")
        print(f"Output: {OUTPUT}/")
        print(f"\nTo train:")
        print(f"  python -m anti_uav train --profile colab_t4")
        print(f"  (update data_yaml in train config to point to {OUTPUT}/data.yaml)")
    else:
        print("ERROR: data.yaml not found in output")

    # Cleanup temp
    shutil.rmtree(temp_dir)
    print("\nDone.")


if __name__ == "__main__":
    main()
