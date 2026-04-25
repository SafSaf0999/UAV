"""
Check false detections on the Birds.v1i.yolov8 valid split.
For each model, count:
  - Correct: Bird predicted as Bird
  - False: Bird predicted as Drone (false positive on bird = missed threat confusion)
  - Miss: Bird in GT but no detection
"""
from pathlib import Path
import shutil, tempfile
import yaml

ROOT = Path("/home/safsaf/Projects/UAV-dataset-workflow")
IMG_DIR = ROOT / "datasets" / "Birds.v1i.yolov8" / "valid" / "images"
LBL_DIR = ROOT / "datasets" / "Birds.v1i.yolov8" / "valid" / "labels"

MODELS = [
    ("BirdDrone-Local",
     ROOT / "training" / "run_2class_yolo26s_rtx2070_100ep" / "weights" / "best.pt"),
    ("BirdDrone-Local-FT",
     ROOT / "training" / "finetuned" / "run_2class_dut_finetune_20260407_005234" / "weights" / "best.pt"),
]

CONF  = 0.25
EXTS  = {".jpg",".jpeg",".png"}

def make_tmp():
    tmp = Path(tempfile.mkdtemp())
    (tmp/"images").mkdir(); (tmp/"labels").mkdir()
    for img in IMG_DIR.iterdir():
        if img.suffix.lower() not in EXTS: continue
        lbl = LBL_DIR / (img.stem + ".txt")
        if not lbl.is_file(): continue
        # GT: token "0" = Bird → class 0
        lines = []
        for line in lbl.read_text().splitlines():
            p = line.strip().split()
            if len(p) == 5:
                try: [float(v) for v in p[1:]]
                except ValueError: continue
                if p[0] == "0":
                    lines.append("0 " + " ".join(p[1:]))
        if lines:
            shutil.copy2(img, tmp/"images"/img.name)
            (tmp/"labels"/(img.stem+".txt")).write_text("\n".join(lines))
    with open(tmp/"data.yaml","w") as f:
        yaml.dump({"path":str(tmp),"train":"images","val":"images","test":"images",
                   "nc":2,"names":["Bird","Drone"]},f)
    return tmp

from ultralytics import YOLO

for name, weights in MODELS:
    print(f"\n=== {name} ===")
    model = YOLO(str(weights))
    tmp = make_tmp()
    imgs = list((tmp/"images").iterdir())

    bird_correct = bird_as_drone = no_detection = total_gt_birds = 0

    for img in imgs:
        lbl = tmp / "labels" / (img.stem + ".txt")
        gt_boxes = [l for l in lbl.read_text().splitlines() if l.strip()]
        total_gt_birds += len(gt_boxes)

        results = model(str(img), conf=CONF, verbose=False, device=0)
        preds = results[0].boxes
        if preds is None or len(preds) == 0:
            no_detection += len(gt_boxes)
            continue

        pred_classes = [int(b.cls.item()) for b in preds]
        has_bird_pred  = 0 in pred_classes
        has_drone_pred = 1 in pred_classes

        if has_bird_pred:
            bird_correct += 1
        if has_drone_pred and not has_bird_pred:
            bird_as_drone += 1  # bird image, only drone predicted = false class

    shutil.rmtree(tmp, ignore_errors=True)

    print(f"Total GT bird images : {len(imgs)}")
    print(f"Total GT bird boxes  : {total_gt_birds}")
    print(f"Correct (Bird→Bird)  : {bird_correct}  ({bird_correct/len(imgs)*100:.1f}%)")
    print(f"False class (Bird→Drone): {bird_as_drone}  ({bird_as_drone/len(imgs)*100:.1f}%)")
    print(f"No detection         : {no_detection} boxes missed")
