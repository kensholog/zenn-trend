"""Author data for C (decisions/0006): article histories and the user API for the authors of the birth cohort and of
every trend article. One acquisition, after T_end (the first snapshot at or after 2026-10-02 12:10 JST).

  python scripts/fetch_c_authors.py --count   # how many authors / requests (needs T_end; prints counts only)
  pwsh -NoProfile -ExecutionPolicy Bypass -File scripts/run_detached.ps1 -Script scripts/fetch_c_authors.py -Log data/c/fetch.log

Before T_end it refuses to run: 0006 allows a single acquisition after the observation window closes.
Output: data/c/author_articles.jsonl   one article per line (listing fields; no body), with "username"
        data/c/author_done.txt         usernames finished (resume marker: name, fetched count, last status)
        data/c/users.jsonl             one user per line (follower_count, total_liked_count, articles_count, ...)
        (kept apart from data/author_articles.jsonl and data/users.jsonl of phase 1 / Q / 2b)
Rate:   1 request per second. Resumable. Raw rows are not committed (/data/ is ignored); only aggregates are published.
"""
import json
import sys
import time
import urllib.parse
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import c_common as cc  # noqa: E402
# same request helper and listing fields as Q1; the import also re-wraps stdout as UTF-8, so do not wrap again here
from fetch_author_histories import get, slim, SLEEP  # noqa: E402

OUT_DIR = cc.ROOT / "data" / "c"
ARTS, DONE, USERS = OUT_DIR / "author_articles.jsonl", OUT_DIR / "author_done.txt", OUT_DIR / "users.jsonl"
USER_KEYS = ("id", "follower_count", "following_count", "total_liked_count", "articles_count", "books_count",
             "scraps_count", "created_at")


def fetch_history(name, f):
    q = urllib.parse.quote(name)
    n, page, status = 0, 1, 200
    while page <= 100:
        status, body = get(f"https://zenn.dev/api/articles?username={q}&order=latest&count=48&page={page}")
        time.sleep(SLEEP)
        if status != 200:
            break
        d = json.loads(body)
        arts = d.get("articles", [])
        for a in arts:
            f.write(json.dumps(slim(a), ensure_ascii=False) + "\n")
        n += len(arts)
        if not arts or d.get("next_page") is None:
            break
        page = d["next_page"]
    f.flush()
    return n, status


def fetch_user(name):
    st, body = get(f"https://zenn.dev/api/users/{urllib.parse.quote(name)}")
    time.sleep(SLEEP)
    row = {"username": name, "status": st, "fetched_at": datetime.now(cc.JST).isoformat(timespec="seconds")}
    if st == 200:
        u = json.loads(body).get("user") or {}
        row.update({k: u.get(k) for k in USER_KEYS})
    return row


def main():
    t_end, names = cc.c_authors(cc.ROOT)
    if t_end is None:
        print(f"T_end not reached: no snapshot at or after {cc.T_END_MIN.isoformat()}. Nothing fetched (decisions/0006).")
        sys.exit(1)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    done = set()
    if DONE.exists():
        done = {line.split("\t")[0] for line in open(DONE, encoding="utf-8") if line.strip()}
    have_user = set()
    if USERS.exists():
        have_user = {json.loads(line)["username"] for line in open(USERS, encoding="utf-8") if line.strip()}
    todo = [n for n in names if n not in done or n not in have_user]
    print(f"T_end {t_end.isoformat()}  authors {len(names)}  done {len(names) - len(todo)}  to fetch {len(todo)}"
          f"  (>= {len(todo) * 2} requests, ~{len(todo) * 2 * SLEEP / 60:.0f} min or more)")
    if "--count" in sys.argv:
        return
    with open(ARTS, "a", encoding="utf-8") as fa, open(DONE, "a", encoding="utf-8") as fd, \
            open(USERS, "a", encoding="utf-8") as fu:
        for i, name in enumerate(todo, 1):
            if name not in done:
                n, status = fetch_history(name, fa)
                fd.write(f"{name}\t{n}\t{status}\n")
                fd.flush()
            if name not in have_user:
                fu.write(json.dumps(fetch_user(name), ensure_ascii=False) + "\n")
                fu.flush()
            if i % 250 == 0:
                print(f"  {i}/{len(todo)} authors")
    print("done")


if __name__ == "__main__":
    main()
