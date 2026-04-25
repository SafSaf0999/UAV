"""Quick diagnostic — print token distribution per dataset."""
from pathlib import Path

ROOT = Path("/home/safsaf/Projects/UAV-dataset-workflow")
D    = ROOT / "datasets"

def check(name, paths):
    tokens = {}
    total  = 0
    for p in paths:
        if not p.is_dir():
            print(f"  MISSING: {p}")
            continue
        for lbl in p.rglob("*.txt"):
            if lbl.name in {"classes.txt","obj.names","README.txt"}:
                continue
            for line in lbl.read_text().splitlines():
                parts = line.strip().split()
                if len(parts) == 5:
                    try:
                        [float(v) for v in parts[1:]]
                        tokens[parts[0]] = tokens.get(parts[0], 0) + 1
                        total += 1
                    except ValueError:
                        pass
    print(f"{name}: {total} annotations, tokens={tokens}")

check("Birds.v1i.yolov8", [D/"Birds.v1i.yolov8"/"train"/"labels",
                            D/"Birds.v1i.yolov8"/"valid"/"labels"])
check("fixed-wing-uav",   [D/"fixed-wing-uav"/"images"])
check("anti-uav",         [D/"anti-uav"/"train"/"labels",
                            D/"anti-uav"/"valid"/"labels",
                            D/"anti-uav"/"test"/"labels"])
