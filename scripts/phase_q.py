"""Second project (decisions/0003) in one detached run: author histories (Q1), then Hatena Bookmark counts (Q2).

  pwsh -NoProfile -ExecutionPolicy Bypass -File scripts/run_detached.ps1 -Script scripts/phase_q.py -Log data/phase_q.log

Each child is resumable. Pass --no-hatebu to skip Q2.
"""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
steps = ["fetch_author_histories.py"] + ([] if "--no-hatebu" in sys.argv else ["fetch_hatebu.py"])
for name in steps:
    print(f"=== {name}", flush=True)
    r = subprocess.run([sys.executable, "-u", str(ROOT / "scripts" / name)], cwd=ROOT)
    if r.returncode != 0:
        print(f"=== {name} failed with {r.returncode}", flush=True)
        sys.exit(r.returncode)
print("=== phase Q fetch complete", flush=True)
