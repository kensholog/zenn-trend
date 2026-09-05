"""Fetch every author's full article list (decisions/0003, Q1).

  python scripts/fetch_author_histories.py            # P1 (data/users.jsonl, status 200) + P2 (latest 100 pages)
  python scripts/fetch_author_histories.py --p2-only  # only build the P2 panel and fetch its authors

Output: data/author_articles.jsonl   one article per line (listing fields; no body), with "username" and "panel"
        data/author_done.txt         usernames finished (resume marker; one per line, with fetched count)
        data/latest_panel.jsonl      P2 articles (order=latest, 100 pages) as fetched
Rate:   1 request per second. Per-user listing pages until next_page is null (hard cap 100 pages).
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
OUT = DATA / "author_articles.jsonl"
DONE = DATA / "author_done.txt"
LATEST = DATA / "latest_panel.jsonl"
UA = "Mozilla/5.0 (personal research on Zenn authors; 1 req/s; contact via zenn.dev/kensholog)"
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


def slim(a):
    u = a.get("user") or {}
    p = a.get("publication") or {}
    return {
        "id": a.get("id"), "slug": a.get("slug"), "path": a.get("path"), "title": a.get("title"),
        "article_type": a.get("article_type"), "published_at": a.get("published_at"),
        "liked_count": a.get("liked_count"), "bookmarked_count": a.get("bookmarked_count"),
        "comments_count": a.get("comments_count"), "body_letters_count": a.get("body_letters_count"),
        "username": u.get("username"), "publication": p.get("name") if p else None,
    }


def fetch_user(name, panel, f):
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
            row = slim(a)
            row["panel"] = panel
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
        n += len(arts)
        nxt = d.get("next_page")
        if not arts or nxt is None:
            break
        page = nxt
    f.flush()
    return n, status


def build_p2():
    names = []
    if LATEST.exists():
        for line in open(LATEST, encoding="utf-8"):
            names.append(json.loads(line)["username"])
        return list(dict.fromkeys(names))
    with open(LATEST, "w", encoding="utf-8") as f:
        page = 1
        while page <= 100:
            st, body = get(f"https://zenn.dev/api/articles?order=latest&count=48&page={page}")
            time.sleep(SLEEP)
            if st != 200:
                print(f"[warn] latest page {page} status {st}")
                break
            d = json.loads(body)
            arts = d.get("articles", [])
            for a in arts:
                row = slim(a)
                row["fetched_at"] = datetime.now(JST).isoformat(timespec="seconds")
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
                names.append(row["username"])
            if not arts or d.get("next_page") is None:
                break
            page = d["next_page"]
    return list(dict.fromkeys(n for n in names if n))


def main():
    p2_only = "--p2-only" in sys.argv
    p1 = []
    if not p2_only:
        for line in open(DATA / "users.jsonl", encoding="utf-8"):
            u = json.loads(line)
            if u.get("status") == 200:
                p1.append(u["username"])
    print(f"=== building P2 panel (order=latest, 100 pages)")
    p2 = build_p2()
    print(f"P1 {len(p1)} authors, P2 {len(p2)} authors ({len(set(p2) - set(p1))} not in P1)")
    done = {}
    if DONE.exists():
        for line in open(DONE, encoding="utf-8"):
            parts = line.rstrip("\n").split("\t")
            if parts[0]:
                done[parts[0]] = parts[1] if len(parts) > 1 else ""
    todo = [(n, "p1") for n in p1 if n not in done] + [(n, "p2") for n in p2 if n not in done and n not in set(p1)]
    print(f"{len(done)} done, {len(todo)} to fetch")
    with open(OUT, "a", encoding="utf-8") as f, open(DONE, "a", encoding="utf-8") as fd:
        for i, (name, panel) in enumerate(todo, 1):
            n, status = fetch_user(name, panel, f)
            fd.write(f"{name}\t{n}\t{status}\n")
            fd.flush()
            if i % 500 == 0:
                print(f"  {i}/{len(todo)} authors")
    print("done")


if __name__ == "__main__":
    main()
