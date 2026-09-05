"""Fetch Hatena Bookmark counts for every article URL in data/topics/*.jsonl (decisions/0003, Q2).

  python scripts/fetch_hatebu.py

API:    https://bookmark.hatenaapis.com/count/entries?url=...&url=...   (up to 50 URLs per request)
Output: data/hatebu.jsonl   {"path": "/user/articles/slug", "count": N, "fetched_at": ...}
Rate:   one request every 3 seconds (the API doc asks for "数秒の間隔" when repeating). Resumable.
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

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", line_buffering=True)
ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
OUT = DATA / "hatebu.jsonl"
UA = "Mozilla/5.0 (personal research on Zenn articles; 1 req/s; contact via zenn.dev/kensholog)"
JST = timezone(timedelta(hours=9))
SLEEP = 3.0
BATCH = 50


def get(url, retries=3):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    for i in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return r.status, r.read().decode("utf-8", "ignore")
        except urllib.error.HTTPError as e:
            if e.code in (404, 403, 400):
                return e.code, ""
            time.sleep(5 * (i + 1))
        except Exception:
            time.sleep(5 * (i + 1))
    return 0, ""


def main():
    paths = []
    for p in sorted((DATA / "topics").glob("*.jsonl")):
        for line in open(p, encoding="utf-8"):
            paths.append(json.loads(line)["path"])
    paths = list(dict.fromkeys(paths))
    done = set()
    if OUT.exists():
        for line in open(OUT, encoding="utf-8"):
            done.add(json.loads(line)["path"])
    todo = [p for p in paths if p not in done]
    print(f"=== hatebu: {len(paths)} urls, {len(done)} done, {len(todo)} to fetch (~{len(todo) / BATCH * SLEEP / 60:.0f} min)")
    with open(OUT, "a", encoding="utf-8") as f:
        for i in range(0, len(todo), BATCH):
            batch = todo[i:i + BATCH]
            qs = "&".join("url=" + urllib.parse.quote("https://zenn.dev" + p, safe="") for p in batch)
            st, body = get("https://bookmark.hatenaapis.com/count/entries?" + qs)
            time.sleep(SLEEP)
            stamp = datetime.now(JST).isoformat(timespec="seconds")
            counts = {}
            if st == 200:
                try:
                    counts = json.loads(body)
                except Exception:
                    counts = {}
            for p in batch:
                c = counts.get("https://zenn.dev" + p)
                f.write(json.dumps({"path": p, "count": c, "status": st, "fetched_at": stamp}, ensure_ascii=False) + "\n")
            f.flush()
            if (i // BATCH) % 200 == 0:
                print(f"  {i}/{len(todo)} status {st}")
    print("done")


if __name__ == "__main__":
    main()
