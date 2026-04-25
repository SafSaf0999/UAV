"""
Pull training results from Kaggle kernel output.
Run this after the kernel completes:
    python pull_results.py
"""
import os
import subprocess
import zipfile
from pathlib import Path
from datetime import datetime

KERNEL_SLUG = "mustafamubarak99/anti-uav-yolo26s-training-run-1"
TRAINING_DIR = Path("training")

def main():
    token = os.environ.get("KAGGLE_API_TOKEN", "")
    env = {**os.environ, "KAGGLE_API_TOKEN": token} if token else os.environ

    # Check status first
    result = subprocess.run(
        [".venv/bin/kaggle", "kernels", "status", KERNEL_SLUG],
        capture_output=True, text=True, env=env
    )
    print(result.stdout.strip())

    if "complete" not in result.stdout.lower():
        print("Kernel not complete yet. Check back later.")
        return

    # Create run folder
    run_dir = TRAINING_DIR / f"run_{datetime.now().strftime('%Y%m%d_%H%M%S')}_yolo26s_kaggle"
    run_dir.mkdir(parents=True, exist_ok=True)

    # Download all outputs
    print(f"\nDownloading outputs to {run_dir}...")
    dl = subprocess.run(
        [".venv/bin/kaggle", "kernels", "output", KERNEL_SLUG, "-p", str(run_dir)],
        capture_output=True, text=True, env=env
    )
    print(dl.stdout)
    if dl.returncode != 0:
        print(f"Error: {dl.stderr}")
        return

    # Extract any zip files
    for zf in run_dir.glob("*.zip"):
        print(f"Extracting {zf.name}...")
        with zipfile.ZipFile(zf) as z:
            z.extractall(run_dir)
        zf.unlink()

    # Show what we got
    print(f"\nResults saved to: {run_dir}")
    print("\nContents:")
    for p in sorted(run_dir.rglob("*")):
        if p.is_file():
            size = p.stat().st_size / 1024 / 1024
            print(f"  {p.relative_to(run_dir)}  ({size:.1f} MB)")

if __name__ == "__main__":
    main()
