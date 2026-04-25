import subprocess, shutil
from pathlib import Path

REPO = Path('/home/safsaf/Projects/UAV/UAV')
src  = REPO / 'UAV-dataset-workflow/documentations/report_full.pdf'
dst  = REPO / 'report_full.pdf'

shutil.copy2(str(src), str(dst))
print(f"Copied {src.stat().st_size // 1024}KB -> {dst}")

def run(cmd):
    r = subprocess.run(cmd, cwd=str(REPO), capture_output=True, text=True)
    if r.stdout.strip(): print(r.stdout.strip())
    if r.stderr.strip(): print('STDERR:', r.stderr.strip())

run(['git', 'add', 'report_full.pdf'])
run(['git', 'commit', '-m', 'report: update root report_full.pdf with latest changes'])
run(['git', 'push', 'origin', 'testing'])
