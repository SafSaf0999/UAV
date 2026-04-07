"""
Download all three anti-UAV datasets from Roboflow Universe.
Usage: python download_datasets.py
"""
from roboflow import Roboflow
from pathlib import Path

API_KEY = "isXmw2bZCbFyS9M0kcZH"  # replace with your key

DATASETS = [
    {
        "workspace": "uavs-7l7kv",
        "project":   "uavs-vqpqt",
        "version":   2,
        "location":  "datasets/uavs",
        "classes":   ["drone"],
    },
    {
        "workspace": "dronesbird",
        "project":   "yolo-exp",
        "version":   5,
        "location":  "datasets/yolo-exp",
        "classes":   ["Bird", "drone"],
    },
    {
        "workspace": "yogith-nams8",
        "project":   "anti-uav-s8wri",
        "version":   1,
        "location":  "datasets/anti-uav",
        "classes":   ["UAV"],
    },
    {
        "workspace": "sihadenemeler",
        "project":   "uavdetector",
        "version":   1,
        "location":  "datasets/uavdetector",
        "classes":   ["fixed wing UAV dataset - v1 fixed wing UAV"],
    },
]

def main():
    rf = Roboflow(api_key=API_KEY)
    Path("datasets").mkdir(exist_ok=True)

    for ds in DATASETS:
        print(f"\nDownloading {ds['project']} (classes: {ds['classes']})...")
        try:
            rf.workspace(ds["workspace"]) \
              .project(ds["project"]) \
              .version(ds["version"]) \
              .download("yolov8", location=ds["location"])
            print(f"  Done → {ds['location']}")
        except Exception as e:
            print(f"  Failed: {e}")
            print(f"  Try changing version number in DATASETS config above.")

    print("\nAll downloads complete. Run:")
    print("  anti-uav inspect datasets/uavs")
    print("  anti-uav inspect datasets/yolo-exp")
    print("  anti-uav inspect datasets/anti-uav")

if __name__ == "__main__":
    main()
