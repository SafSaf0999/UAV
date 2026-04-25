# Regression & Fine-tune Comparison Report

Generated: 2026-04-07 03:22

Comparing **BirdDrone-Local** (original) vs **BirdDrone-Local-FT** (fine-tuned on DUT pseudo-labels).

## Section A: Regression on Original Test Sets

| Test Set | BirdDrone-Local mAP@0.5 | BirdDrone-Local-FT mAP@0.5 | Δ | P | R |
|---|---|---|---|---|---|
| 2class-val | 0.927 | 0.922 | **-0.004** | 0.929 | 0.866 |
| anti-uav-test | 0.934 | 0.929 | **-0.005** | 0.927 | 0.862 |
| birds-valid | 0.973 | 0.972 | **-0.001** | 0.942 | 0.934 |
| uavdetector-test | 0.273 | 0.341 | **+0.069** | 0.549 | 0.425 |

## Section B: DUT Anti-UAV Performance

| Metric | BirdDrone-Local | BirdDrone-Local-FT | Δ |
|---|---|---|---|
| Avg Detection Rate | 0.808 | 0.818 | **+0.010** |
| Avg Confidence | 0.671 | 0.790 | **+0.119** |
| First-frame TP Rate | 0.850 | 0.850 | **+0.000** |
| Total False-Class Det | 159 | 65 | **-94** |
| Total Low-Conf FP | 2549 | 1154 | **-1395** |
| Total Tracking Gaps | 199 | 131 | **-68** |
| Total Missed Frames | 6164 | 5704 | **-460** |

## Per-Video DUT Comparison

| Video | Orig DR | FT DR | Δ DR | Orig Gaps | FT Gaps | Orig FalseCls | FT FalseCls |
|---|---|---|---|---|---|---|---|
| video01 | 0.824 | 0.855 | **+0.031** | 5 | 5 | 3 | 0 |
| video02 | 0.879 | 1.000 | **+0.121** | 0 | 0 | 26 | 0 |
| video03 | 0.970 | 1.000 | **+0.030** | 0 | 0 | 64 | 61 |
| video04 | 0.994 | 0.991 | **-0.003** | 0 | 0 | 9 | 1 |
| video05 | 0.951 | 0.944 | **-0.007** | 1 | 1 | 5 | 0 |
| video06 | 1.000 | 1.000 | **+0.000** | 0 | 0 | 4 | 1 |
| video07 | 0.712 | 0.757 | **+0.046** | 12 | 11 | 1 | 0 |
| video08 | 0.883 | 0.898 | **+0.016** | 5 | 5 | 41 | 0 |
| video09 | 0.606 | 0.650 | **+0.045** | 5 | 3 | 0 | 0 |
| video10 | 0.694 | 0.846 | **+0.152** | 31 | 8 | 1 | 0 |
| video11 | 0.982 | 0.979 | **-0.003** | 0 | 0 | 0 | 0 |
| video12 | 0.663 | 0.666 | **+0.003** | 5 | 5 | 0 | 0 |
| video13 | 0.488 | 0.625 | **+0.136** | 43 | 28 | 0 | 0 |
| video14 | 0.827 | 0.831 | **+0.003** | 7 | 5 | 0 | 0 |
| video15 | 0.641 | 0.847 | **+0.206** | 22 | 7 | 0 | 0 |
| video16 | 0.746 | 0.279 | **-0.468** | 21 | 7 | 0 | 0 |
| video17 | 0.550 | 0.606 | **+0.056** | 21 | 17 | 0 | 0 |
| video18 | 0.958 | 0.956 | **-0.002** | 2 | 1 | 5 | 2 |
| video19 | 0.995 | 0.850 | **-0.145** | 0 | 8 | 0 | 0 |
| video20 | 0.793 | 0.769 | **-0.024** | 19 | 20 | 0 | 0 |
