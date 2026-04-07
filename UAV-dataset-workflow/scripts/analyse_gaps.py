"""
Extract wide tracking gaps from frame CSVs and report start/end frame numbers.
This lets you check in the video whether the gap is due to out-of-frame UAV
or genuine detection failure.
"""
from pathlib import Path
import csv

ROOT      = Path("/home/safsaf/Projects/UAV-dataset-workflow")
FRAME_DIR = ROOT / "comparison" / "dut_frame_csv"
OUT       = ROOT / "comparison" / "gap_analysis.md"

MIN_GAP = 10   # only report gaps >= 10 frames (shorter ones are noise)

def find_gaps(csv_path: Path) -> list[dict]:
    rows = list(csv.DictReader(csv_path.open()))
    gaps = []
    start = None
    length = 0
    for row in rows:
        frame = int(row["frame"])
        detected = int(row["detections"]) > 0
        if not detected:
            if start is None:
                start = frame
            length += 1
        else:
            if length >= MIN_GAP:
                gaps.append({"start": start, "end": frame - 1, "length": length})
            start = None
            length = 0
    # trailing gap
    if length >= MIN_GAP:
        gaps.append({"start": start, "end": int(rows[-1]["frame"]), "length": length})
    return gaps

lines = ["# Wide Tracking Gaps (≥10 frames)\n",
         f"Threshold: {MIN_GAP} consecutive missed frames\n",
         "Check these frame ranges in the annotated videos to determine if the UAV moved out of frame.\n\n"]

for model in ["BirdDrone-Local", "TriClass-Cloud"]:
    lines.append(f"## {model}\n\n")
    lines.append("| Video | Gap # | Start Frame | End Frame | Length | Approx Time @25fps |\n")
    lines.append("|---|---|---|---|---|---|\n")
    for vid in sorted(FRAME_DIR.glob(f"*_{model}.csv")):
        vname = vid.stem.replace(f"_{model}", "")
        gaps = find_gaps(vid)
        wide = [g for g in gaps if g["length"] >= MIN_GAP]
        for i, g in enumerate(wide, 1):
            secs = g["length"] / 25
            lines.append(f"| {vname} | {i} | {g['start']} | {g['end']} | "
                         f"{g['length']} | {secs:.1f}s |\n")
    lines.append("\n")

OUT.write_text("".join(lines))
print(f"Written: {OUT}")

# Also print to console
print("".join(lines))
