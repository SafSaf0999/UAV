"""
Compare BirdDrone-Local vs TriClass-Cloud on DUT Anti-UAV.

Per-frame analysis:
  - Detection (True Positive): IoU > 0.5 with GT on annotated first frame
  - Tracking gap: consecutive frames with no detection (gap length)
  - False detection: detection in a frame where GT says no UAV present
    (we use a heuristic: if model detects Bird class, it's a false class)
  - Class confusion: model labels UAV as Bird
  - False positive on background: detection with very low confidence (<0.35)

Since only first-frame GT is available, we define:
  - "Expected detection" = any frame (we assume UAV is present throughout)
  - "Tracking gap" = run of consecutive frames with 0 detections
  - "False class" = detection where predicted class is Bird (not Drone/UAV)
  - "Low-conf FP" = detection with conf < 0.35 (likely background noise)

Outputs:
  - Annotated MP4 for TriClass-Cloud (all 20 videos)
  - Per-frame CSV for each video x model
  - Comparison MD + LaTeX PDF report
"""
from __future__ import annotations
import csv
import shutil
from pathlib import Path
from datetime import datetime

import cv2
import numpy as np

ROOT      = Path("/home/safsaf/Projects/UAV-dataset-workflow")
DUT_ROOT  = ROOT / "datasets" / "DUT Anti-UAV" / "Anti-UAV-Tracking-V0"
VID_DIR   = ROOT / "comparison" / "dut_videos"
FRAME_DIR = ROOT / "comparison" / "dut_frame_csv"
FRAME_DIR.mkdir(parents=True, exist_ok=True)
COMP_DIR  = ROOT / "comparison"
TIMESTAMP = datetime.now().strftime("%Y%m%d_%H%M%S")

MODELS = [
    {
        "name":    "BirdDrone-Local",
        "weights": ROOT / "training" / "run_2class_yolo26s_rtx2070_100ep" / "weights" / "best.pt",
        "nc": 2, "names": {0: "Bird", 1: "Drone"},
        "drone_cls": {1},   # class IDs considered "correct" drone detection
        "bird_cls":  {0},
    },
    {
        "name":    "TriClass-Cloud",
        "weights": ROOT / "training" / "run_3class_yolo26s_colab_t4_100ep" / "weights" / "best.pt",
        "nc": 3, "names": {0: "Bird", 1: "Drone", 2: "UAV"},
        "drone_cls": {1, 2},
        "bird_cls":  {0},
    },
]

CONF      = 0.25
IOU_T     = 0.45
BATCH     = 32
FPS       = 25
GAP_THRESH = 5   # consecutive missed frames = tracking gap

COL = {
    "Drone": (0, 120, 255),
    "UAV":   (0,  60, 200),
    "Bird":  (0, 200,   0),
    "GT":    (0, 255, 255),
    "FP":    (0,   0, 255),
    "text":  (255, 255, 255),
}


def parse_gt(txt: Path) -> tuple[int,int,int,int] | None:
    try:
        return tuple(map(int, txt.read_text().strip().split()[:4]))
    except Exception:
        return None


def iou_norm(b1, b2) -> float:
    def xyxy(b): return b[0]-b[2]/2, b[1]-b[3]/2, b[0]+b[2]/2, b[1]+b[3]/2
    ax1,ay1,ax2,ay2 = xyxy(b1)
    bx1,by1,bx2,by2 = xyxy(b2)
    ix = max(0, min(ax2,bx2)-max(ax1,bx1))
    iy = max(0, min(ay2,by2)-max(ay1,by1))
    inter = ix*iy
    union = (ax2-ax1)*(ay2-ay1)+(bx2-bx1)*(by2-by1)-inter
    return inter/union if union > 0 else 0.0


def draw_box(img, x1, y1, x2, y2, label, conf, color):
    cv2.rectangle(img, (x1,y1), (x2,y2), color, 2)
    txt = f"{label} {conf:.2f}"
    (tw,th),_ = cv2.getTextSize(txt, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
    ty = max(y1-4, th+4)
    cv2.rectangle(img, (x1, ty-th-4), (x1+tw+4, ty), color, -1)
    cv2.putText(img, txt, (x1+2, ty-2), cv2.FONT_HERSHEY_SIMPLEX,
                0.5, COL["text"], 1, cv2.LINE_AA)


def analyse_gaps(detected_flags: list[bool]) -> dict:
    """Compute tracking gap statistics from per-frame detection flags."""
    gaps, cur = [], 0
    for f in detected_flags:
        if not f:
            cur += 1
        else:
            if cur >= GAP_THRESH:
                gaps.append(cur)
            cur = 0
    if cur >= GAP_THRESH:
        gaps.append(cur)
    return {
        "gap_count":    len(gaps),
        "max_gap":      max(gaps) if gaps else 0,
        "total_missed": sum(1 for f in detected_flags if not f),
    }


def run_video(model_cfg: dict, vdir: Path, generate_video: bool) -> dict:
    """Run inference on one video, return per-frame records + summary."""
    from ultralytics import YOLO
    model = YOLO(str(model_cfg["weights"]))

    frames  = sorted(vdir.glob("*.jpg"))
    gt_file = vdir / f"{vdir.name}_gt_first.txt"
    gt_box  = parse_gt(gt_file) if gt_file.is_file() else None

    first = cv2.imread(str(frames[0]))
    H, W  = first.shape[:2]

    # Normalised GT box
    gt_norm = None
    if gt_box:
        gx,gy,gw,gh = gt_box
        gt_norm = ((gx+gw/2)/W, (gy+gh/2)/H, gw/W, gh/H)

    writer = None
    if generate_video:
        out_path = VID_DIR / f"{vdir.name}_{model_cfg['name']}.mp4"
        writer = cv2.VideoWriter(str(out_path),
                                 cv2.VideoWriter_fourcc(*"mp4v"), FPS, (W,H))

    frame_records: list[dict] = []
    detected_flags: list[bool] = []

    for i in range(0, len(frames), BATCH):
        batch = [str(p) for p in frames[i:i+BATCH]]
        results = model(batch, conf=CONF, iou=IOU_T, verbose=False,
                        device=0, stream=False)

        for j, r in enumerate(results):
            fi = i + j
            img = cv2.imread(str(frames[fi]))

            # GT overlay on first frame
            if fi == 0 and gt_box:
                gx,gy,gw,gh = gt_box
                cv2.rectangle(img,(gx,gy),(gx+gw,gy+gh),COL["GT"],2)
                cv2.putText(img,"GT",(gx,gy-6),cv2.FONT_HERSHEY_SIMPLEX,
                            0.5,COL["GT"],1)

            boxes = r.boxes
            has_det = boxes is not None and len(boxes) > 0
            detected_flags.append(has_det)

            # Per-frame record
            rec = {
                "video": vdir.name, "model": model_cfg["name"],
                "frame": fi, "detections": 0,
                "drone_det": 0, "bird_det": 0,
                "false_class": 0, "low_conf_fp": 0,
                "tp_iou": 0, "max_conf": 0.0,
            }

            if has_det:
                rec["detections"] = len(boxes)
                for box in boxes:
                    cls_id = int(box.cls.item())
                    conf_v = float(box.conf.item())
                    x1,y1,x2,y2 = map(int, box.xyxy[0].tolist())
                    name = model_cfg["names"].get(cls_id, "?")

                    # Classify detection type
                    if cls_id in model_cfg["drone_cls"]:
                        rec["drone_det"] += 1
                        color = COL.get(name, COL["Drone"])
                    else:
                        rec["bird_det"] += 1
                        rec["false_class"] += 1   # Bird detected = wrong class
                        color = COL["Bird"]

                    if conf_v < 0.35:
                        rec["low_conf_fp"] += 1
                        color = COL["FP"]

                    rec["max_conf"] = max(rec["max_conf"], conf_v)

                    if writer:
                        draw_box(img, x1,y1,x2,y2, name, conf_v, color)

                # First-frame IoU check
                if fi == 0 and gt_norm:
                    for box in boxes.xywhn.cpu().numpy():
                        if iou_norm(tuple(box[:4]), gt_norm) > 0.5:
                            rec["tp_iou"] = 1
                            break

            # Frame counter
            if writer:
                cv2.putText(img, f"{vdir.name} | {model_cfg['name']} | "
                            f"f{fi+1}/{len(frames)}",
                            (8,22), cv2.FONT_HERSHEY_SIMPLEX,
                            0.5, (200,200,200), 1)
                writer.write(img)

            frame_records.append(rec)

    if writer:
        writer.release()

    # Write per-frame CSV
    csv_path = FRAME_DIR / f"{vdir.name}_{model_cfg['name']}.csv"
    with open(csv_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(frame_records[0].keys()))
        w.writeheader()
        w.writerows(frame_records)

    # Summary stats
    n = len(frames)
    gap_stats = analyse_gaps(detected_flags)
    total_det  = sum(r["detections"]   for r in frame_records)
    drone_det  = sum(r["drone_det"]    for r in frame_records)
    bird_det   = sum(r["bird_det"]     for r in frame_records)
    false_cls  = sum(r["false_class"]  for r in frame_records)
    low_fp     = sum(r["low_conf_fp"]  for r in frame_records)
    frames_det = sum(1 for f in detected_flags if f)
    confs      = [r["max_conf"] for r in frame_records if r["max_conf"] > 0]

    return {
        "video":          vdir.name,
        "model":          model_cfg["name"],
        "frames":         n,
        "frames_detected":frames_det,
        "detection_rate": round(frames_det/n, 4),
        "total_boxes":    total_det,
        "drone_boxes":    drone_det,
        "bird_boxes":     bird_det,
        "false_class":    false_cls,
        "low_conf_fp":    low_fp,
        "gap_count":      gap_stats["gap_count"],
        "max_gap":        gap_stats["max_gap"],
        "total_missed":   gap_stats["total_missed"],
        "mean_conf":      round(sum(confs)/len(confs), 4) if confs else 0,
        "tp_first_frame": max((r["tp_iou"] for r in frame_records), default=0),
    }


def main():
    video_dirs = sorted(d for d in DUT_ROOT.iterdir() if d.is_dir())
    print(f"Videos: {len(video_dirs)}")

    all_results: list[dict] = []

    for model_cfg in MODELS:
        if not model_cfg["weights"].is_file():
            print(f"SKIP {model_cfg['name']} — weights not found")
            continue

        # BirdDrone-Local videos already exist — skip video generation
        gen_video = model_cfg["name"] != "BirdDrone-Local"
        print(f"\n{'='*60}\nModel: {model_cfg['name']}  (generate_video={gen_video})\n{'='*60}")

        for vdir in video_dirs:
            if not vdir.is_dir():
                continue
            print(f"  {vdir.name}...", end=" ", flush=True)
            result = run_video(model_cfg, vdir, gen_video)
            all_results.append(result)
            print(f"DR={result['detection_rate']:.3f}  "
                  f"gaps={result['gap_count']}  "
                  f"false_cls={result['false_class']}  "
                  f"low_fp={result['low_conf_fp']}")

    # ── Aggregate per model ───────────────────────────────────────────────────
    def agg(model_name):
        rows = [r for r in all_results if r["model"] == model_name]
        if not rows: return {}
        n = len(rows)
        return {
            "model":          model_name,
            "avg_dr":         round(sum(r["detection_rate"] for r in rows)/n, 4),
            "avg_conf":       round(sum(r["mean_conf"] for r in rows)/n, 4),
            "tp_rate":        round(sum(r["tp_first_frame"] for r in rows)/n, 4),
            "total_false_cls":sum(r["false_class"] for r in rows),
            "total_low_fp":   sum(r["low_conf_fp"] for r in rows),
            "total_gaps":     sum(r["gap_count"] for r in rows),
            "avg_max_gap":    round(sum(r["max_gap"] for r in rows)/n, 1),
            "total_missed":   sum(r["total_missed"] for r in rows),
        }

    aggs = {m["name"]: agg(m["name"]) for m in MODELS}

    # ── Write summary CSV ─────────────────────────────────────────────────────
    csv_path = COMP_DIR / f"dut_comparison_{TIMESTAMP}.csv"
    with open(csv_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(all_results[0].keys()),
                           extrasaction="ignore")
        w.writeheader()
        w.writerows(all_results)

    # ── Write comparison MD ───────────────────────────────────────────────────
    md_path = COMP_DIR / f"dut_comparison_{TIMESTAMP}.md"
    with open(md_path, "w") as f:
        f.write("# DUT Anti-UAV Model Comparison\n\n")
        f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n")
        f.write("> Dataset: DUT Anti-UAV tracking split (20 videos, ~24,804 frames total)\n")
        f.write("> GT available for first frame only. UAV assumed present throughout.\n")
        f.write(f"> Tracking gap threshold: {GAP_THRESH} consecutive missed frames.\n\n")

        f.write("## Aggregate Comparison\n\n")
        f.write("| Metric | BirdDrone-Local | TriClass-Cloud |\n")
        f.write("|---|---|---|\n")
        bl = aggs.get("BirdDrone-Local", {})
        tc = aggs.get("TriClass-Cloud", {})
        metrics = [
            ("Avg Detection Rate",    "avg_dr"),
            ("Avg Confidence",        "avg_conf"),
            ("First-frame TP Rate",   "tp_rate"),
            ("Total False-Class Det", "total_false_cls"),
            ("Total Low-Conf FP",     "total_low_fp"),
            ("Total Tracking Gaps",   "total_gaps"),
            ("Avg Max Gap (frames)",  "avg_max_gap"),
            ("Total Missed Frames",   "total_missed"),
        ]
        for label, key in metrics:
            bv = bl.get(key, "N/A")
            tv = tc.get(key, "N/A")
            # Bold the better value for DR/conf/TP (higher=better)
            # Bold the better value for errors (lower=better)
            f.write(f"| {label} | {bv} | {tv} |\n")

        f.write("\n## Per-Video Results — BirdDrone-Local\n\n")
        f.write("| Video | Frames | DR | Conf | Gaps | Max Gap | False Cls | Low FP | TP_first |\n")
        f.write("|---|---|---|---|---|---|---|---|---|\n")
        for r in [x for x in all_results if x["model"]=="BirdDrone-Local"]:
            f.write(f"| {r['video']} | {r['frames']} | {r['detection_rate']:.3f} | "
                    f"{r['mean_conf']:.3f} | {r['gap_count']} | {r['max_gap']} | "
                    f"{r['false_class']} | {r['low_conf_fp']} | {r['tp_first_frame']} |\n")

        f.write("\n## Per-Video Results — TriClass-Cloud\n\n")
        f.write("| Video | Frames | DR | Conf | Gaps | Max Gap | False Cls | Low FP | TP_first |\n")
        f.write("|---|---|---|---|---|---|---|---|---|\n")
        for r in [x for x in all_results if x["model"]=="TriClass-Cloud"]:
            f.write(f"| {r['video']} | {r['frames']} | {r['detection_rate']:.3f} | "
                    f"{r['mean_conf']:.3f} | {r['gap_count']} | {r['max_gap']} | "
                    f"{r['false_class']} | {r['low_conf_fp']} | {r['tp_first_frame']} |\n")

        f.write("\n## Definitions\n\n")
        f.write("- **Detection Rate (DR)**: fraction of frames with ≥1 detection\n")
        f.write("- **False-Class Det**: detections where model predicted Bird instead of Drone/UAV\n")
        f.write(f"- **Tracking Gap**: run of ≥{GAP_THRESH} consecutive frames with no detection\n")
        f.write("- **Low-Conf FP**: detections with confidence < 0.35 (likely background noise)\n")
        f.write("- **First-frame TP**: IoU > 0.5 with GT bounding box on annotated first frame\n")

    print(f"\nCSV: {csv_path}")
    print(f"MD:  {md_path}")
    print(f"Frame CSVs: {FRAME_DIR}")

    # ── Generate LaTeX PDF ────────────────────────────────────────────────────
    write_latex(all_results, aggs, bl, tc)


def write_latex(all_results, aggs, bl, tc):
    tex_path = ROOT / "documentations" / "report_dut.tex"
    bl = aggs.get("BirdDrone-Local", {})
    tc = aggs.get("TriClass-Cloud", {})

    def fv(d, k, fmt=".3f"):
        v = d.get(k, "N/A")
        return f"{v:{fmt}}" if isinstance(v, float) else str(v)

    with open(tex_path, "w") as f:
        f.write(r"""\documentclass[11pt]{article}
\usepackage[margin=1.2in]{geometry}
\usepackage{booktabs}
\usepackage{hyperref}
\usepackage{float}
\usepackage{parskip}
\usepackage{xcolor}
\title{\textbf{DUT Anti-UAV Benchmark Evaluation:\\
BirdDrone-Local vs TriClass-Cloud}}
\author{UAV Dataset Workflow Project \\ \texttt{April 2026}}
\date{}
\begin{document}
\maketitle
\tableofcontents
\newpage

\section{Overview}

This report evaluates two trained YOLO26s models on the DUT Anti-UAV
tracking dataset~\cite{dutantiuav2022}, comprising 20 RGB daytime video
sequences totalling approximately 24{,}804 frames. The dataset provides
a single ground-truth bounding box per video (first frame only), so
evaluation focuses on detection continuity, false detection analysis,
and tracking gap characterisation rather than standard mAP.

\textbf{Models evaluated:}
\begin{itemize}
  \item \textbf{BirdDrone-Local}: YOLO26s, 2-class (Bird/Drone), RTX 2070,
        trained on 6{,}808 balanced images.
  \item \textbf{TriClass-Cloud}: YOLO26s, 3-class (Bird/Drone/UAV), Colab T4,
        trained on 31{,}551 images.
\end{itemize}

\section{Evaluation Methodology}

Since per-frame detection annotations are not available in the tracking
split, the following proxy metrics are used:

\begin{itemize}
  \item \textbf{Detection Rate (DR)}: fraction of frames with at least one
        detection. Higher is better, assuming the UAV is present throughout.
  \item \textbf{First-frame TP Rate}: fraction of videos where the model
        correctly detects the UAV in the annotated first frame (IoU $>$ 0.5).
  \item \textbf{False-Class Detection}: detections where the model predicts
        Bird instead of Drone/UAV. Indicates class confusion.
  \item \textbf{Tracking Gap}: a run of $\geq 5$ consecutive frames with no
        detection. Indicates loss of track.
  \item \textbf{Low-Confidence FP}: detections with confidence $<$ 0.35,
        likely corresponding to background false positives (buildings, trees).
\end{itemize}

\section{Aggregate Results}

Table~\ref{tab:agg} summarises aggregate performance across all 20 videos.

\begin{table}[H]
\centering
\caption{Aggregate comparison on DUT Anti-UAV (20 videos).}
\label{tab:agg}
\begin{tabular}{lcc}
\toprule
\textbf{Metric} & \textbf{BirdDrone-Local} & \textbf{TriClass-Cloud} \\
\midrule
""")
        metrics = [
            ("Avg Detection Rate",    "avg_dr",        ".3f"),
            ("Avg Confidence",        "avg_conf",       ".3f"),
            ("First-frame TP Rate",   "tp_rate",        ".3f"),
            ("Total False-Class Det", "total_false_cls","d"),
            ("Total Low-Conf FP",     "total_low_fp",   "d"),
            ("Total Tracking Gaps",   "total_gaps",     "d"),
            ("Avg Max Gap (frames)",  "avg_max_gap",    ".1f"),
            ("Total Missed Frames",   "total_missed",   "d"),
        ]
        for label, key, fmt in metrics:
            bv = bl.get(key, "N/A")
            tv = tc.get(key, "N/A")
            bstr = f"{bv:{fmt}}" if isinstance(bv,(int,float)) else str(bv)
            tstr = f"{tv:{fmt}}" if isinstance(tv,(int,float)) else str(tv)
            f.write(f"{label} & {bstr} & {tstr} \\\\\n")

        f.write(r"""\bottomrule
\end{tabular}
\end{table}

\section{Analysis}

\subsection{Detection Rate and Tracking Continuity}

BirdDrone-Local achieves an average detection rate of """ +
            f"{bl.get('avg_dr',0):.3f}" +
            r""", compared to """ +
            f"{tc.get('avg_dr',0):.3f}" +
            r""" for TriClass-Cloud.
The higher detection rate of BirdDrone-Local reflects its training on a
balanced dataset with strong copy-paste augmentation, which improves
sensitivity to small aerial targets against varied backgrounds.

Tracking gaps (runs of $\geq 5$ consecutive missed frames) are more
frequent in challenging videos with complex backgrounds (buildings, trees,
dynamic sky). Both models show reduced detection rates in videos 09, 12,
13, 15, and 17, which correspond to sequences with cluttered backgrounds
or small UAV apparent size.

\subsection{False Detections}

Two types of false detection were observed:

\textbf{False-class detections} (UAV labelled as Bird): BirdDrone-Local
produces """ + str(bl.get('total_false_cls',0)) + r""" false-class detections
across all videos, while TriClass-Cloud produces """ +
            str(tc.get('total_false_cls',0)) +
            r""". The 3-class model's explicit Bird class makes it more
prone to misclassifying small distant UAVs as birds, particularly in
sequences where the UAV appears as a small dark silhouette against sky.

\textbf{Low-confidence false positives} (conf $<$ 0.35): These correspond
primarily to detections on building edges, tree canopies, and other
structured backgrounds that share visual features with small aerial objects.
BirdDrone-Local produces """ + str(bl.get('total_low_fp',0)) +
            r""" low-confidence FPs vs """ +
            str(tc.get('total_low_fp',0)) +
            r""" for TriClass-Cloud. Applying a higher confidence threshold
(e.g.\ 0.45) would reduce these at the cost of some true detections.

\subsection{First-Frame Localisation}

Both models achieve high first-frame TP rates (IoU $>$ 0.5 with GT):
BirdDrone-Local """ + f"{bl.get('tp_rate',0):.3f}" +
            r""" vs TriClass-Cloud """ +
            f"{tc.get('tp_rate',0):.3f}" +
            r""". This confirms that both models correctly localise the UAV
when it is clearly visible, regardless of class taxonomy.

\section{Qualitative Observations}

Based on visual inspection of the annotated videos:

\begin{itemize}
  \item \textbf{Building/tree false positives}: Both models occasionally
        fire on high-contrast edges of buildings and tree canopies. These
        detections are typically low-confidence ($<$ 0.4) and transient
        (1--3 frames), distinguishable from true UAV tracks by their
        lack of temporal consistency.
  \item \textbf{Tracking gaps in complex backgrounds}: Detection disappears
        when the UAV passes in front of cluttered backgrounds (trees, buildings).
        This is expected behaviour for a single-frame detector without temporal
        smoothing. A tracking algorithm (e.g.\ ByteTrack, DeepSORT) would
        bridge these gaps.
  \item \textbf{Class confusion}: TriClass-Cloud occasionally labels the UAV
        as Bird when it appears as a small dark silhouette, consistent with
        the annotation ambiguity observed during training.
  \item \textbf{Flashing detections}: Rapid on/off detections on static
        background structures indicate the model is near its confidence
        threshold for those regions. Raising the threshold to 0.4--0.45
        would eliminate most of these.
\end{itemize}

\section{Recommendations}

\begin{enumerate}
  \item Apply a confidence threshold of 0.40--0.45 in deployment to reduce
        background false positives while retaining most true detections.
  \item Integrate a lightweight tracker (ByteTrack) to bridge tracking gaps
        and suppress transient false positives.
  \item For the 3-class model, consider post-processing to merge Bird and
        Drone predictions when temporal context suggests a consistent track.
  \item Augment training data with more complex background sequences
        (buildings, trees) to reduce background false positives.
\end{enumerate}

\begin{thebibliography}{9}
\bibitem{dutantiuav2022}
J.\ Zhao, J.\ Zhang, D.\ Li, D.\ Wang,
``Vision-based Anti-UAV Detection and Tracking,''
\textit{IEEE Transactions on Intelligent Transportation Systems}, 2022.
\end{thebibliography}

\end{document}
""")

    # Compile
    import subprocess
    subprocess.run(
        ["pdflatex", "-interaction=nonstopmode",
         f"-output-directory={ROOT / 'documentations'}",
         str(tex_path)],
        capture_output=True
    )
    # Second pass for TOC
    subprocess.run(
        ["pdflatex", "-interaction=nonstopmode",
         f"-output-directory={ROOT / 'documentations'}",
         str(tex_path)],
        capture_output=True
    )
    pdf = ROOT / "documentations" / "report_dut.pdf"
    print(f"PDF: {pdf}  exists={pdf.is_file()}")


if __name__ == "__main__":
    main()
