"""Generate the Kaggle training notebook for the anti-UAV workflow."""
from pathlib import Path
from anti_uav.models import HardwareProfile, RemoteBackend, TrainingConfig
from anti_uav.colab_bridge import generate_notebook
import nbformat

# Override the generated notebook with a custom one tailored for our dataset
import nbformat.v4 as nv4

dataset_slug = "mustafamubarak99/anti-uav-merged-dataset"

mount_cell = nv4.new_code_cell(
    "# Mount dataset\n"
    "import os, subprocess\n"
    f"DATASET_SLUG = '{dataset_slug}'\n"
    "dataset_path = f'/kaggle/input/{DATASET_SLUG.split(\"/\")[-1]}'\n"
    "print(f'Dataset path: {dataset_path}')\n"
    "import os; print(os.listdir(dataset_path))\n"
)

extract_cell = nv4.new_code_cell(
    "# Extract dataset backup\n"
    "import tarfile, os\n"
    "extract_dir = '/kaggle/working/dataset'\n"
    "os.makedirs(extract_dir, exist_ok=True)\n"
    "tar_path = os.path.join(dataset_path, 'backup_merged_dataset.tar.gz')\n"
    "print(f'Extracting {tar_path}...')\n"
    "with tarfile.open(tar_path) as tf:\n"
    "    tf.extractall(extract_dir)\n"
    "data_yaml = os.path.join(extract_dir, 'merged_dataset', 'data.yaml')\n"
    "print(f'data.yaml: {data_yaml}')\n"
    "# Fix paths in data.yaml to point to extracted location\n"
    "import yaml\n"
    "with open(data_yaml) as f:\n"
    "    cfg = yaml.safe_load(f)\n"
    "base = os.path.join(extract_dir, 'merged_dataset')\n"
    "cfg['path'] = base\n"
    "cfg['train'] = os.path.join(base, 'train', 'images')\n"
    "cfg['val'] = os.path.join(base, 'val', 'images')\n"
    "cfg['test'] = os.path.join(base, 'test', 'images')\n"
    "with open(data_yaml, 'w') as f:\n"
    "    yaml.dump(cfg, f)\n"
    "print('data.yaml paths updated')\n"
)

install_cell = nv4.new_code_cell(
    "# Install dependencies\n"
    "import subprocess\n"
    "subprocess.run(['pip', 'install', '-q', 'ultralytics>=8.4.0'], check=True)\n"
    "from ultralytics import YOLO\n"
    "print('ultralytics ready')\n"
)

train_cell = nv4.new_code_cell(
    "# Run training\n"
    "from ultralytics import YOLO\n"
    "model = YOLO('yolo26s.pt')\n"
    "results = model.train(\n"
    "    data=data_yaml,\n"
    "    imgsz=640,\n"
    "    batch=32,\n"
    "    epochs=100,\n"
    "    optimizer='MuSGD',\n"
    "    lr0=0.01,\n"
    "    weight_decay=0.0005,\n"
    "    amp=True,\n"
    "    device='0',\n"
    "    mosaic=1.0,\n"
    "    mixup=0.05,\n"
    "    copy_paste=0.5,\n"
    "    hsv_h=0.02,\n"
    "    hsv_s=0.7,\n"
    "    hsv_v=0.5,\n"
    "    degrees=20.0,\n"
    "    translate=0.15,\n"
    "    scale=0.8,\n"
    "    flipud=0.3,\n"
    "    fliplr=0.5,\n"
    "    project='/kaggle/working/runs',\n"
    "    name='anti_uav_run1',\n"
    ")\n"
    "print('Training complete')\n"
    "print(f'Best weights: {results.save_dir}/weights/best.pt')\n"
)

save_cell = nv4.new_code_cell(
    "# Save outputs\n"
    "import shutil, os\n"
    "output_dir = '/kaggle/working'\n"
    "runs_dir = '/kaggle/working/runs'\n"
    "print('Output files:')\n"
    "for root, dirs, files in os.walk(runs_dir):\n"
    "    for f in files:\n"
    "        path = os.path.join(root, f)\n"
    "        size = os.path.getsize(path) / 1024 / 1024\n"
    "        print(f'  {path} ({size:.1f} MB)')\n"
    "print('Done — download weights from the Output tab')\n"
)

nb = nv4.new_notebook()
nb.cells = [mount_cell, extract_cell, install_cell, train_cell, save_cell]

Path("kaggle_upload/notebook.ipynb").write_text(nbformat.writes(nb))
print("Notebook written to kaggle_upload/notebook.ipynb")
