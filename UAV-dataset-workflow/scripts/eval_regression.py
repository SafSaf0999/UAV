"""
Regression + DUT re-evaluation after fine-tuning.

Tests run:
  A) Original val sets (regression check)
     - merged_dataset_2class/val  (original BirdDrone-Local val)
     - anti-uav test split
     - uavdetector test split
     - Birds.v1i valid split

  B) DUT Anti-UAV videos (same 20 videos, same metrics as before)
     - Detection Rate, False-Class, Tracking Gaps, Low-Conf FP

Compares:
  - BirdDrone-Local (original best.pt)
  - BirdDrone-Local-FT (fine-tuned best.pt)

Outputs to: comparison/regression/
"""
from __future__ import annotations
import csv
import shutil
import tempfile
from pathlib import Path
from datetime import datetime

import cv2
import yaml

ROOT      = Path("/home/safsaf/Projects/UAV-dataset-workflow")
DUT_ROOT  = ROOT / "datasets" / "DUT Anti-UAV" / "Anti-UAV-Tracking-V0"
OUT_DIR   = ROOT / "comparison" / "regression"
VID_DIR   = OUT_DIR / "dut_videos_finetuned"
FRAME_DIR = OUT_DIR / "dut_frame_csv"
OUT_DIR.mkdir(parents=True, exist_ok=True)
VID_DIR.mkdir(parents=True, exist_ok=True)
FRAME_DIR.mkdir(parents=True, exist_ok=True)

TIMESTAMP = datetime.now().strftime("%Y%m%d_%H%M%S")

MODELS = [
    {
        "name":      "BirdDrone-Local",
        "weights":   ROOT / "training" / "run_2class_yolo26s_rtx2070_100ep" / "weights" / "best.pt",
        "nc": 2, "names": {0: "Bird", 1: "Drone"},
        "drone_cls": {1}, "bird_cls": {0},
    },
    {
        "name":      "BirdDrone-Local-FT",
        "weights":   ROOT / "training" / "finetuned" / "run_2class_dut_finetune_20260407_005234" / "weights" / "best.pt",
        "nc": 2, "names": {0: "Bird", 1: "Drone"},
        "drone_cls": {1}, "bird_cls": {0},
    },
]

CONF = 0.25
IOU  = 0.45
BATCH = 32
FPS   = 25
GAP_THRESH = 5
EXTS = {".jpg",".jpeg",".png",".bmp"}

COL = {"Drone":(0,120,255),"Bird":(0,200,0),"GT":(0,255,255),"FP":(0,0,255),"text":(255,255,255)}


# ── helpers ───────────────────────────────────────────────────────────────────

def make_temp_dataset(img_dir, lbl_dir, nc, names, token_remap):
    tmp = Path(tempfile.mkdtemp())
    (tmp/"images").mkdir(); (tmp/"labels").mkdir()
    for img in img_dir.iterdir():
        if img.suffix.lower() not in EXTS: continue
        lbl = lbl_dir / (img.stem+".txt")
        if not lbl.is_file(): continue
        lines = []
        for line in lbl.read_text().splitlines():
            p = line.strip().split()
            if len(p)!=5: continue
            try: [float(v) for v in p[1:]]
            except ValueError: continue
            if p[0] in token_remap:
                lines.append(f"{token_remap[p[0]]} "+" ".join(p[1:]))
        if lines:
            shutil.copy2(img, tmp/"images"/img.name)
            (tmp/"labels"/(img.stem+".txt")).write_text("\n".join(lines))
    with open(tmp/"data.yaml","w") as f:
        yaml.dump({"path":str(tmp),"train":"images","val":"images","test":"images",
                   "nc":nc,"names":names},f)
    return tmp

def run_val(model, data_yaml, tag):
    from ultralytics import YOLO
    m = YOLO(str(model["weights"]))
    r = m.val(data=str(data_yaml), split="test", imgsz=640, batch=16,
              device=0, workers=0, verbose=False, plots=False,
              name=f"reg_{tag}", project=str(OUT_DIR/"val_runs"), exist_ok=True)
    return {"map50":round(float(r.box.map50),4),
            "map50_95":round(float(r.box.map),4),
            "precision":round(float(r.box.mp),4),
            "recall":round(float(r.box.mr),4)}

def iou_norm(b1,b2):
    def xy(b): return b[0]-b[2]/2,b[1]-b[3]/2,b[0]+b[2]/2,b[1]+b[3]/2
    ax1,ay1,ax2,ay2=xy(b1); bx1,by1,bx2,by2=xy(b2)
    ix=max(0,min(ax2,bx2)-max(ax1,bx1)); iy=max(0,min(ay2,by2)-max(ay1,by1))
    inter=ix*iy; union=(ax2-ax1)*(ay2-ay1)+(bx2-bx1)*(by2-by1)-inter
    return inter/union if union>0 else 0.0

def parse_gt(txt,W,H):
    try:
        x,y,w,h=map(float,txt.read_text().strip().split()[:4])
        return (x+w/2)/W,(y+h/2)/H,w/W,h/H
    except: return None

def draw_box(img,x1,y1,x2,y2,label,conf,color):
    cv2.rectangle(img,(x1,y1),(x2,y2),color,2)
    txt=f"{label} {conf:.2f}"
    (tw,th),_=cv2.getTextSize(txt,cv2.FONT_HERSHEY_SIMPLEX,0.5,1)
    ty=max(y1-4,th+4)
    cv2.rectangle(img,(x1,ty-th-4),(x1+tw+4,ty),color,-1)
    cv2.putText(img,txt,(x1+2,ty-2),cv2.FONT_HERSHEY_SIMPLEX,0.5,COL["text"],1)

def analyse_gaps(flags):
    gaps,cur=[],0
    for f in flags:
        if not f: cur+=1
        else:
            if cur>=GAP_THRESH: gaps.append(cur)
            cur=0
    if cur>=GAP_THRESH: gaps.append(cur)
    return {"gap_count":len(gaps),"max_gap":max(gaps) if gaps else 0,
            "total_missed":sum(1 for f in flags if not f)}

def run_dut_video(model_cfg, vdir, gen_video):
    from ultralytics import YOLO
    from PIL import Image
    model = YOLO(str(model_cfg["weights"]))
    frames = sorted(vdir.glob("*.jpg"))
    gt_file = vdir/f"{vdir.name}_gt_first.txt"
    first = cv2.imread(str(frames[0])); H,W=first.shape[:2]
    gt_norm = parse_gt(gt_file,W,H) if gt_file.is_file() else None

    writer=None
    if gen_video:
        out_path = VID_DIR/f"{vdir.name}_{model_cfg['name']}.mp4"
        writer = cv2.VideoWriter(str(out_path),cv2.VideoWriter_fourcc(*"mp4v"),FPS,(W,H))

    frame_records=[]; detected_flags=[]
    for i in range(0,len(frames),BATCH):
        batch=[str(p) for p in frames[i:i+BATCH]]
        results=model(batch,conf=CONF,iou=IOU,verbose=False,device=0,stream=False)
        for j,r in enumerate(results):
            fi=i+j; img=cv2.imread(str(frames[fi]))
            if fi==0 and gt_norm:
                gx,gy,gw,gh=int(gt_norm[0]*W-gt_norm[2]*W/2),int(gt_norm[1]*H-gt_norm[3]*H/2),int(gt_norm[2]*W),int(gt_norm[3]*H)
                cv2.rectangle(img,(gx,gy),(gx+gw,gy+gh),COL["GT"],2)
            boxes=r.boxes; has_det=boxes is not None and len(boxes)>0
            detected_flags.append(has_det)
            rec={"video":vdir.name,"model":model_cfg["name"],"frame":fi,
                 "detections":0,"drone_det":0,"bird_det":0,"false_class":0,
                 "low_conf_fp":0,"tp_iou":0,"max_conf":0.0}
            if has_det:
                rec["detections"]=len(boxes)
                for box in boxes:
                    cls_id=int(box.cls.item()); conf_v=float(box.conf.item())
                    x1,y1,x2,y2=map(int,box.xyxy[0].tolist())
                    name=model_cfg["names"].get(cls_id,"?")
                    if cls_id in model_cfg["drone_cls"]: rec["drone_det"]+=1; color=COL.get(name,COL["Drone"])
                    else: rec["bird_det"]+=1; rec["false_class"]+=1; color=COL["Bird"]
                    if conf_v<0.35: rec["low_conf_fp"]+=1; color=COL["FP"]
                    rec["max_conf"]=max(rec["max_conf"],conf_v)
                    if writer: draw_box(img,x1,y1,x2,y2,name,conf_v,color)
                if fi==0 and gt_norm:
                    for box in boxes.xywhn.cpu().numpy():
                        if iou_norm(tuple(box[:4]),gt_norm)>0.5: rec["tp_iou"]=1; break
            if writer:
                cv2.putText(img,f"{vdir.name}|{model_cfg['name']}|f{fi+1}/{len(frames)}",(8,22),cv2.FONT_HERSHEY_SIMPLEX,0.5,(200,200,200),1)
                writer.write(img)
            frame_records.append(rec)
    if writer: writer.release()

    # Save frame CSV
    csv_path=FRAME_DIR/f"{vdir.name}_{model_cfg['name']}.csv"
    with open(csv_path,"w",newline="") as f:
        w=csv.DictWriter(f,fieldnames=list(frame_records[0].keys())); w.writeheader(); w.writerows(frame_records)

    n=len(frames); gap_stats=analyse_gaps(detected_flags)
    frames_det=sum(1 for f in detected_flags if f)
    confs=[r["max_conf"] for r in frame_records if r["max_conf"]>0]
    return {"video":vdir.name,"model":model_cfg["name"],"frames":n,
            "frames_detected":frames_det,"detection_rate":round(frames_det/n,4),
            "false_class":sum(r["false_class"] for r in frame_records),
            "low_conf_fp":sum(r["low_conf_fp"] for r in frame_records),
            "gap_count":gap_stats["gap_count"],"max_gap":gap_stats["max_gap"],
            "total_missed":gap_stats["total_missed"],
            "mean_conf":round(sum(confs)/len(confs),4) if confs else 0,
            "tp_first_frame":max((r["tp_iou"] for r in frame_records),default=0)}


# ── Section A: regression on original val sets ────────────────────────────────

def run_section_a():
    D = ROOT/"datasets"
    TEST_SETS = [
        {"name":"2class-val",    "img":ROOT/"merged_dataset_2class"/"val"/"images",
         "lbl":ROOT/"merged_dataset_2class"/"val"/"labels",
         "remap":{"0":0,"1":1},"nc":2,"names":["Bird","Drone"]},
        {"name":"anti-uav-test", "img":D/"anti-uav"/"test"/"images",
         "lbl":D/"anti-uav"/"test"/"labels",
         "remap":{"UAV":1},"nc":2,"names":["Bird","Drone"]},
        {"name":"uavdetector-test","img":D/"uavdetector"/"test"/"images",
         "lbl":D/"uavdetector"/"test"/"labels",
         "remap":{"UAV":1},"nc":2,"names":["Bird","Drone"]},
        {"name":"birds-valid",   "img":D/"Birds.v1i.yolov8"/"valid"/"images",
         "lbl":D/"Birds.v1i.yolov8"/"valid"/"labels",
         "remap":{"0":0},"nc":2,"names":["Bird","Drone"]},
    ]
    results=[]
    for model in MODELS:
        for ts in TEST_SETS:
            if not ts["img"].is_dir(): continue
            print(f"  {model['name']} × {ts['name']}...", end=" ", flush=True)
            tmp=make_temp_dataset(ts["img"],ts["lbl"],ts["nc"],ts["names"],ts["remap"])
            try:
                m=run_val(model,tmp/"data.yaml",f"{model['name']}_{ts['name']}")
                results.append({"model":model["name"],"test_set":ts["name"],**m})
                print(f"mAP50={m['map50']:.3f}")
            except Exception as e: print(f"ERROR: {e}")
            finally: shutil.rmtree(tmp,ignore_errors=True)
    return results


# ── Section B: DUT re-evaluation ──────────────────────────────────────────────

def run_section_b():
    video_dirs=sorted(d for d in DUT_ROOT.iterdir() if d.is_dir())
    results=[]
    for model in MODELS:
        gen_video = model["name"]=="BirdDrone-Local-FT"  # only generate new videos for FT
        print(f"\n{'='*55}\nDUT eval: {model['name']}  (gen_video={gen_video})")
        for vdir in video_dirs:
            if not vdir.is_dir(): continue
            print(f"  {vdir.name}...",end=" ",flush=True)
            r=run_dut_video(model,vdir,gen_video)
            results.append(r)
            print(f"DR={r['detection_rate']:.3f} gaps={r['gap_count']} false_cls={r['false_class']}")
    return results


# ── Write comparison report ───────────────────────────────────────────────────

def write_report(sec_a, sec_b):
    md=OUT_DIR/f"regression_report_{TIMESTAMP}.md"
    def fmt(v,d=3): return f"{v:.{d}f}" if isinstance(v,float) else str(v)

    with open(md,"w") as f:
        f.write("# Regression & Fine-tune Comparison Report\n\n")
        f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n")
        f.write("Comparing **BirdDrone-Local** (original) vs **BirdDrone-Local-FT** (fine-tuned on DUT pseudo-labels).\n\n")

        f.write("## Section A: Regression on Original Test Sets\n\n")
        f.write("| Test Set | BirdDrone-Local mAP@0.5 | BirdDrone-Local-FT mAP@0.5 | Δ | P | R |\n")
        f.write("|---|---|---|---|---|---|\n")
        test_sets = sorted(set(r["test_set"] for r in sec_a))
        for ts in test_sets:
            orig = next((r for r in sec_a if r["model"]=="BirdDrone-Local" and r["test_set"]==ts),{})
            ft   = next((r for r in sec_a if r["model"]=="BirdDrone-Local-FT" and r["test_set"]==ts),{})
            o50=orig.get("map50",0); f50=ft.get("map50",0)
            delta=round(f50-o50,3)
            sign="+" if delta>=0 else ""
            f.write(f"| {ts} | {fmt(o50)} | {fmt(f50)} | **{sign}{delta}** | "
                    f"{fmt(ft.get('precision',0))} | {fmt(ft.get('recall',0))} |\n")

        f.write("\n## Section B: DUT Anti-UAV Performance\n\n")
        def agg(model_name,rows):
            r=[x for x in rows if x["model"]==model_name]
            if not r: return {}
            n=len(r)
            return {"avg_dr":round(sum(x["detection_rate"] for x in r)/n,4),
                    "avg_conf":round(sum(x["mean_conf"] for x in r)/n,4),
                    "tp_rate":round(sum(x["tp_first_frame"] for x in r)/n,4),
                    "total_false_cls":sum(x["false_class"] for x in r),
                    "total_low_fp":sum(x["low_conf_fp"] for x in r),
                    "total_gaps":sum(x["gap_count"] for x in r),
                    "total_missed":sum(x["total_missed"] for x in r)}
        bl=agg("BirdDrone-Local",sec_b); ft=agg("BirdDrone-Local-FT",sec_b)
        metrics=[("Avg Detection Rate","avg_dr",".3f"),
                 ("Avg Confidence","avg_conf",".3f"),
                 ("First-frame TP Rate","tp_rate",".3f"),
                 ("Total False-Class Det","total_false_cls","d"),
                 ("Total Low-Conf FP","total_low_fp","d"),
                 ("Total Tracking Gaps","total_gaps","d"),
                 ("Total Missed Frames","total_missed","d")]
        f.write("| Metric | BirdDrone-Local | BirdDrone-Local-FT | Δ |\n")
        f.write("|---|---|---|---|\n")
        for label,key,fmt_str in metrics:
            bv=bl.get(key,0); fv=ft.get(key,0)
            if isinstance(bv,float): delta=f"{fv-bv:+.3f}"
            else: delta=f"{fv-bv:+d}"
            f.write(f"| {label} | {bv:{fmt_str}} | {fv:{fmt_str}} | **{delta}** |\n")

        f.write("\n## Per-Video DUT Comparison\n\n")
        f.write("| Video | Orig DR | FT DR | Δ DR | Orig Gaps | FT Gaps | Orig FalseCls | FT FalseCls |\n")
        f.write("|---|---|---|---|---|---|---|---|\n")
        vids=sorted(set(r["video"] for r in sec_b))
        for v in vids:
            o=next((r for r in sec_b if r["model"]=="BirdDrone-Local" and r["video"]==v),{})
            t=next((r for r in sec_b if r["model"]=="BirdDrone-Local-FT" and r["video"]==v),{})
            odr=o.get("detection_rate",0); tdr=t.get("detection_rate",0)
            f.write(f"| {v} | {odr:.3f} | {tdr:.3f} | **{tdr-odr:+.3f}** | "
                    f"{o.get('gap_count',0)} | {t.get('gap_count',0)} | "
                    f"{o.get('false_class',0)} | {t.get('false_class',0)} |\n")

    # Write CSVs
    for name,data in [("regression_sec_a",sec_a),("regression_sec_b",sec_b)]:
        if not data: continue
        with open(OUT_DIR/f"{name}_{TIMESTAMP}.csv","w",newline="") as f:
            w=csv.DictWriter(f,fieldnames=list(data[0].keys()),extrasaction="ignore")
            w.writeheader(); w.writerows(data)

    print(f"\nReport: {md}")
    print(f"Videos: {VID_DIR}")
    print(f"Frame CSVs: {FRAME_DIR}")


def main():
    print("="*60)
    print("SECTION A: Regression on original test sets")
    print("="*60)
    sec_a = run_section_a()

    print("\n"+"="*60)
    print("SECTION B: DUT Anti-UAV re-evaluation")
    print("="*60)
    sec_b = run_section_b()

    write_report(sec_a, sec_b)


if __name__ == "__main__":
    main()
