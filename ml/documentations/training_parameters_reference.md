# YOLO26 Training Parameters Reference

## Parameter Explanations

### Core
| Parameter | Description |
|---|---|
| `epochs` | Total training passes over the dataset |
| `imgsz` | Input image size (resized to square). 640 is standard |
| `batch` | Images per gradient update. Higher = more stable gradients but more VRAM |
| `workers` | CPU threads for data loading |
| `patience` | Early stopping: stop if no improvement for N epochs |
| `seed` | Random seed for reproducibility |
| `amp` | Automatic Mixed Precision (float16 where safe). Saves VRAM, speeds up training |
| `pretrained` | Start from ImageNet/COCO pretrained weights instead of random init |
| `exist_ok` | Whether to overwrite an existing run folder |

### Optimiser
| Parameter | Description |
|---|---|
| `optimizer` | SGD (momentum-based), MuSGD (scaled variant), or Adam |
| `lr0` | Initial learning rate — the most important single parameter |
| `lrf` | Final lr as a fraction of lr0 (lr decays from lr0 → lr0×lrf over training) |
| `momentum` | SGD momentum. 0.937 is the YOLO standard |
| `weight_decay` | L2 regularisation. Penalises large weights to prevent overfitting |
| `warmup_epochs` | Ramp lr from near-zero to lr0 over first N epochs. Prevents early instability |
| `warmup_momentum` | Momentum during warmup (lower than training momentum) |
| `warmup_bias_lr` | Separate warmup lr for bias parameters |
| `nbs` | Nominal batch size. lr is auto-scaled relative to this (lr × batch/nbs) |
| `cos_lr` | Use cosine lr schedule instead of linear decay |

### Loss Weights
| Parameter | Description |
|---|---|
| `box` | Weight for bounding box regression loss (IoU-based) |
| `cls` | Weight for classification loss |
| `dfl` | Weight for Distribution Focal Loss (bbox precision) |
| `pose`, `kobj`, `rle`, `angle` | For pose/keypoint/OBB tasks — irrelevant for detection |

### Augmentation
| Parameter | Description |
|---|---|
| `mosaic` | Probability of combining 4 images into one. Great for small objects and context variety |
| `copy_paste` | Cuts objects from one image and pastes onto another. Critical for rare/small targets |
| `copy_paste_mode` | `flip` means pasted objects are randomly flipped |
| `mixup` | Blends two images together at pixel level. Helps generalisation but can hurt small objects |
| `cutmix` | Cuts a patch from one image and pastes into another (no class awareness) |
| `hsv_h/s/v` | Random hue/saturation/value shifts. Meaningless on grayscale thermal images |
| `degrees` | Random rotation range (±degrees) |
| `translate` | Random translation as fraction of image size |
| `scale` | Random scale factor range |
| `shear` | Random shear transformation |
| `perspective` | Random perspective warp |
| `flipud` | Probability of vertical flip |
| `fliplr` | Probability of horizontal flip |
| `bgr` | Probability of BGR→RGB channel swap (irrelevant for grayscale) |
| `erasing` | Random rectangular erasure probability. Simulates occlusion/overlays |
| `auto_augment` | Policy-based augmentation (randaugment, autoaugment, augmix) |
| `close_mosaic` | Disable mosaic for the last N epochs to stabilise final training |

---

## Run Comparison

| Parameter | 2-class RGB | 3-class RGB | Finetune-2C | Thermal (1-class) |
|---|---|---|---|---|
| model | yolo26s | yolo26s | best.pt (2C) | yolo26s |
| classes | 2 (Bird, Drone) | 3 (Bird, Drone, UAV) | 2 (Bird, Drone) | 1 (Drone) |
| dataset | merged_2class ~6,808 | merged ~31,551 | finetune_2class ~13,984 | SIDD thermal 4,737 |
| hardware | RTX 2070 | Colab T4 | RTX 2070 | RTX 2070 |
| epochs | 100 | 100 | 20 | 100 |
| batch | 16 | 32 | 16 | 8 |
| optimizer | SGD | MuSGD | SGD | SGD |
| lr0 | 0.01 | 0.01 | 0.001 | 0.005 |
| lrf | 0.01 | 0.01 | 0.01 | 0.01 |
| patience | 30 | 30 | 8 | 20 |
| warmup_epochs | 3 | 3 | 3 | 5 |
| mosaic | 1.0 | 1.0 | 1.0 | 1.0 |
| copy_paste | 0.6 | 0.5 | 0.6 | 0.7 |
| mixup | 0.0 | 0.05 | 0.0 | 0.0 |
| hsv_h | 0.02 | 0.02 | 0.02 | 0.0 |
| hsv_s | 0.7 | 0.7 | 0.7 | 0.0 |
| hsv_v | 0.5 | 0.5 | 0.5 | 0.15 |
| degrees | 20 | 20 | 20 | 15 |
| scale | 0.8 | 0.8 | 0.8 | 0.7 |
| erasing | 0.4 | 0.4 | 0.4 | 0.3 |

### Key Thermal Differences
- `batch=8` — smaller dataset, conservative VRAM usage
- `lr0=0.005` — lower than RGB runs due to smaller dataset size
- `hsv_h/s=0.0` — fully disabled, thermal is grayscale
- `hsv_v=0.15` — slight brightness variation only
- `copy_paste=0.7` — higher than RGB, compensates for tiny drone targets in sea/sky scenes
- `warmup_epochs=5` — longer warmup for stability with lower lr
- `patience=20` — tighter than RGB runs (30), dataset is smaller so convergence is faster

---

## Results Summary

| Model | mAP@0.5 | mAP@0.5:0.95 | Precision | Recall | Notes |
|---|---|---|---|---|---|
| BirdDrone-2C | 0.926 | 0.554 | 0.942 | 0.873 | Base RGB model |
| BirdDrone-3C | 0.892 | 0.574 | 0.852 | 0.837 | Base RGB model |
| BirdDrone-2C-FT | 0.969* | 0.678* | — | — | Fine-tuned, recommended |
| BirdDrone-3C-FT | 0.881* | 0.598* | — | — | Fine-tuned |
| ThermalDrone | TBD | TBD | TBD | TBD | In training |

*On combined val set (original + DUT pseudo-labels)
