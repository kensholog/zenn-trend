"""Fetch the Zenn user API for every author that appears in data/topics/*.jsonl.

  python scripts/fetch_users.py

Output: data/users.jsonl (one user per line: username, follower_count, total_liked_count, articles_count, ...)
Rate:   1 request per second. Resumable: usernames already present in data/users.jsonl are skipped.
"""
import io
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone, timedelta
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
TOPICS = ROOT / "data" / "topics"
OUT = ROOT / "data" / "users.jsonl"
UA = "Mozilla/5.0 (personal research on Zenn topics; 1 req/s; contact via zenn.dev/kensholog)"
JST = timezone(timedelta(hours=9))
SLEEP = 1.0


def get(url, retries=3):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    for i in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return r.status, r.read().decode("utf-8", "ignore")
        except urllib.error.HTTPError as e:
            if e.code in (404, 403):
                return e.code, ""
            time.sleep(5 * (i + 1))
        except Exception:
            time.sleep(5 * (i + 1))
    return 0, ""


def main():
    names = set()
    for p in sorted(TOPICS.glob("*.jsonl")):
        for line in open(p, encoding="utf-8"):
            u = json.loads(line).get("username")
            if u:
                names.add(u)
    done = set()
    if OUT.exists():
        for line in open(OUT, encoding="utf-8"):
            done.add(json.loads(line)["username"])
    todo = sorted(names - done)
    print(f"{len(names)} authors, {len(done)} done, {len(todo)} to fetch (~{len(todo) * SLEEP / 60:.0f} min)")
    with open(OUT, "a", encoding="utf-8") as f:
        for i, name in enumerate(todo, 1):
            st, body = get(f"https://zenn.dev/api/users/{urllib.parse.quote(name)}")
            time.sleep(SLEEP)
            row = {"username": name, "status": st, "fetched_at": datetime.now(JST).isoformat(timespec="seconds")}
            if st == 200:
                u = json.loads(body).get("user") or {}
                row.update({k: u.get(k) for k in ("id", "follower_count", "following_count", "total_liked_count",
                                                   "articles_count", "books_count", "scraps_count", "created_at")})
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
            f.flush()
            if i % 100 == 0:
                print(f"  {i}/{len(todo)}")
    print("done")


if __name__ == "__main__":
    main()
