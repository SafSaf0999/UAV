# Project Progress Presentation
## AI Multi-Agent Anti-UAV Detection System
### ~10 Minutes | Google Meet

---

## Slide 1 — What We're Building (1 min)

**Quick recap for anyone who needs it:**

We're building a distributed anti-UAV detection system. The idea is simple — you put a camera on an edge device (a laptop, Jetson, Raspberry Pi), it runs AI inference locally, and everything feeds into a central web dashboard where operators can monitor detections, watch live feeds, and control cameras.

The two main deliverables are:
1. A trained YOLO model that can tell drones apart from birds
2. A full control center system that ties everything together

---

## Slide 2 — The Training Pipeline (2 min)

**What we trained and how:**

We trained four YOLO26s models. The architecture is from Ultralytics, released late 2025 — it has a small-target-aware label assignment which is exactly what we need for detecting drones at distance.

**The dataset:**
- Pulled from Roboflow and Kaggle — all open license (CC BY 4.0 / CC0)
- 6,808 images for the base 2-class model — perfectly balanced 50/50 Bird/Drone
- The balance matters a lot — an imbalanced dataset would bias the model toward whichever class has more data

**The models:**

| Model | Classes | mAP@0.5 |
|---|---|---|
| BirdDrone-2C | Bird, Drone | 0.926 |
| BirdDrone-3C | Bird, Drone, UAV | 0.892 |
| **BirdDrone-2C-FT** | **Bird, Drone** | **0.969** |
| BirdDrone-3C-FT | Bird, Drone, UAV | 0.881 |

The FT models are fine-tuned on the DUT Anti-UAV benchmark — 20 real-world video sequences. We used pseudo-labeling: ran the base model on the videos, kept only high-confidence detections (≥0.70), and used those as training labels.

---

## Slide 3 — Why BirdDrone-2C-FT is the One (1.5 min)

**The key result:**

Bird false alarm rate = **0.3%**. Out of 378 bird images, only 1 gets misclassified as a drone. That's the number that matters operationally — a system that cries wolf on every bird gets turned off.

Fine-tuning also:
- Reduced low-confidence false positives by **55%** (2,549 → 1,154)
- Reduced tracking gaps by **34%** (199 → 131)
- Increased average detection confidence from 0.671 → **0.790**

The higher confidence means we can set a stricter threshold in deployment (0.40–0.45 instead of 0.25) and basically eliminate background false positives.

**One honest caveat:** we fine-tuned on the same sequences we evaluated on, so the DUT numbers are somewhat optimistic. The cross-dataset results (Anti-UAV test set: 0.929 mAP@0.5) are the more trustworthy generalisation metric.

---

## Slide 4 — The Control Center (2 min)

**What we built:**

A full-stack web application. React frontend, FastAPI backend, all running in Docker. You open a browser, log in, and you get:

- **Overview dashboard** — device cards showing detection counts, uptime, active model
- **Interactive map** — OpenStreetMap with device markers, click any marker to get a slide-in panel with live feed + health data
- **Live feeds** — up to 4 simultaneous WebRTC streams with bounding box overlay
- **Device detail** — health gauges, detection history, runtime config push
- **Logs** — structured log viewer, filterable, CSV export
- **Settings** — user management, invite tokens, session control, webhooks, alert thresholds

**The architecture:**

```
Edge Device                    Main Device (Docker)
─────────────                  ─────────────────────
Camera → YOLO → MQTT ────────► Mosquitto Broker
                               Aggregation Service
WebRTC stream ───────────────► Signaling Server → Browser
```

Everything communicates over MQTT. The edge device publishes detections, health, logs. The control center subscribes and pushes updates to the browser via WebSocket in real time.

---

## Slide 5 — Notable Technical Bits (1.5 min)

**A few things worth mentioning:**

**IP Webcam integration** — if you're using an Android phone as the camera, the control center can remotely control it: zoom, torch, ISO, exposure, focus mode, take snapshots. All proxied through the edge device.

**Multi-device PTZ follow** — if you have two cameras, you can configure one to automatically pan toward whatever the other one is detecting. We have a simulator (`edge_sim.py`) so you can test this without hardware.

**Offline map** — we imported Sudan's OpenStreetMap data into a self-hosted tile server. The map works completely offline now.

**Electron desktop app** — the whole thing is packaged as a desktop app. You launch it from the KDE application launcher, it starts Docker automatically, and when you close it you get a dialog asking whether to minimize to tray or shut everything down.

---

## Slide 6 — The Report (1.5 min)

**Where we are with the report:**

56 pages, 6 chapters, following the FYP guidelines.

- **Chapter 1** — Introduction: background, problem statement, significance, objectives, methodology overview
- **Chapter 2** — Literature Review: theoretical background (YOLO, transfer learning, edge computing, MQTT, WebRTC), related work, comparative analysis table, research gap
- **Chapter 3** — Methodology: requirements, design scenarios, system framework, datasets, training config, evaluation plan
- **Chapter 4** — Results: training curves, validation metrics, cross-dataset evaluation, DUT benchmark results, IoU explanation
- **Chapter 5** — Discussion: why BirdDrone-2C-FT, comparison with KFUPM thesis, edge deployment analysis, fine-tuning dynamics
- **Chapter 6** — Conclusion: findings, deployment recommendations, future work

We've incorporated 6 reference papers including the Sensors 2021 Drone vs. Bird Grand Challenge paper, the KFUPM thesis (similar project), and the Stäcker et al. edge deployment paper.

---

## Slide 7 — What's Left (0.5 min)

**Honest status:**

- Report is structurally complete and follows the guidelines
- Still need PTZ controls and live feed screenshots for Chapter 5
- Weather robustness evaluation (rain/blur) is identified as a gap — not done, but documented as future work
- The system is running and tested end-to-end on real hardware

---

## Slide 8 — Demo (if time allows)

**Quick live demo:**

1. Launch the Electron app from KDE
2. Show the overview dashboard with edge device online
3. Show the map with the device marker
4. Show the live feed with bounding box overlay
5. Show the Settings page — tokens, sessions, webhooks

---

## Notes for Presenter

- Keep slides 2 and 3 tight — the numbers speak for themselves, don't over-explain
- Slide 4 is the most visual — if you can share screen and show the actual dashboard, do it
- The 0.3% false alarm rate is the headline number — mention it at least twice
- If asked about the DUT evaluation caveat, be upfront: "we evaluated on the same data we fine-tuned on, so those numbers are optimistic — the cross-dataset results are the honest ones"
- Total time budget: ~8 minutes talking + 2 minutes for questions
