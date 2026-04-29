import subprocess
from pathlib import Path

REPO = Path('/home/safsaf/Projects/UAV/UAV')

def run(cmd):
    r = subprocess.run(cmd, cwd=str(REPO), capture_output=True, text=True)
    if r.stdout.strip(): print(r.stdout.strip())
    if r.stderr.strip(): print('STDERR:', r.stderr.strip())
    return r.returncode

run(['git', 'add', 'docs/'])
run(['git', 'add', 'control-center/'])
run(['git', 'add', 'ml/'])
run(['git', 'add', '-u'])

print("--- Status ---")
run(['git', 'status', '--short'])

run(['git', 'commit', '-m', 'refactor: reorganize into docs/ control-center/ ml/ — see ml/CHANGES.md'])

print("\n--- Pushing to restructure branch ---")
run(['git', 'push', 'origin', 'HEAD:restructure'])
print("Done. testing branch unchanged.")
