"""Phase 1 in one detached run: topic listings, then authors.

  pwsh -NoProfile -ExecutionPolicy Bypass -File scripts/run_detached.ps1 -Script scripts/phase1.py -Log data/phase1.log

Each child is resumable, so re-running after an interruption continues where it stopped.
"""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
for name in ("fetch_topic_articles.py", "fetch_users.py"):
    print(f"=== {name}", flush=True)
    r = subprocess.run([sys.executable, "-u", str(ROOT / "scripts" / name)], cwd=ROOT)
    if r.returncode != 0:
        print(f"=== {name} failed with {r.returncode}", flush=True)
        sys.exit(r.returncode)
print("=== phase 1 fetch complete", flush=True)
