"""Hourly snapshot of Zenn's official trending RSS plus the newest 48 articles.

  python scripts/fetch_trend_feed.py

Writes one JSON line per run to
  trend_feed/YYYY-MM-DD.jsonl   {fetched_at, source, items:[{rank, title, path, published_at, liked_count, ...}]}
  latest_feed/YYYY-MM-DD.jsonl  {fetched_at, items:[{path, published_at, liked_count, bookmarked_count, ...}]}
Dates are JST. About 22 requests per run at 1 request per second.
Sources: https://zenn.dev/feed (official, "現在Zennでトレンドとなっている投稿"), zenn.dev/api/articles/{slug}, zenn.dev/api/articles?order=latest
"""
import io
import json
import re
import sys
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
UA = "Mozilla/5.0 (personal research on Zenn trends; hourly; 1 req/s; contact via zenn.dev/kensholog)"
JST = timezone(timedelta(hours=9))
SLEEP = 1.0
NS = {"dc": "http://purl.org/dc/elements/1.1/"}


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


def article_detail(path):
    m = re.match(r"^/([^/]+)/articles/([^/?#]+)", path)
    if not m:
        return {}
    st, body = get(f"https://zenn.dev/api/articles/{m.group(2)}")
    time.sleep(SLEEP)
    if st != 200:
        return {"detail_status": st}
    a = json.loads(body).get("article") or {}
    u = a.get("user") or {}
    p = a.get("publication") or {}
    return {
        "detail_status": 200, "id": a.get("id"), "article_type": a.get("article_type"),
        "published_at": a.get("published_at"), "body_updated_at": a.get("body_updated_at"),
        "liked_count": a.get("liked_count"), "authenticated_liked_count": a.get("authenticated_liked_count"),
        "anonymous_liked_count": a.get("anonymous_liked_count"), "bookmarked_count": a.get("bookmarked_count"),
        "comments_count": a.get("comments_count"), "body_letters_count": a.get("body_letters_count"),
        "topics": [t.get("name") for t in a.get("topics") or []],
        "username": u.get("username"), "publication": p.get("name") if p else None,
    }


def main():
    now = datetime.now(JST)
    stamp = now.isoformat(timespec="seconds")
    day = now.strftime("%Y-%m-%d")

    # 1. official trending feed
    st, xml_text = get("https://zenn.dev/feed")
    time.sleep(SLEEP)
    items = []
    if st == 200:
        root = ET.fromstring(xml_text.encode("utf-8"))
        for rank, it in enumerate(root.iter("item"), 1):
            link = (it.findtext("link") or "").strip()
            path = re.sub(r"^https?://zenn\.dev", "", link)
            row = {"rank": rank, "title": (it.findtext("title") or "").strip(), "path": path,
                   "pub_date": (it.findtext("pubDate") or "").strip(),
                   "creator": (it.findtext("dc:creator", namespaces=NS) or "").strip()}
            row.update(article_detail(path))
            items.append(row)
    rec = {"fetched_at": stamp, "source": "https://zenn.dev/feed", "feed_status": st, "items": items}
    d = ROOT / "trend_feed"
    d.mkdir(exist_ok=True)
    with open(d / f"{day}.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    print(f"trend: status {st}, {len(items)} items")

    # 2. newest 48 articles (control pool)
    st, body = get("https://zenn.dev/api/articles?order=latest&count=48&page=1")
    time.sleep(SLEEP)
    latest = []
    if st == 200:
        for a in json.loads(body).get("articles", []):
            u = a.get("user") or {}
            p = a.get("publication") or {}
            latest.append({"path": a.get("path"), "article_type": a.get("article_type"),
                           "published_at": a.get("published_at"), "liked_count": a.get("liked_count"),
                           "bookmarked_count": a.get("bookmarked_count"), "comments_count": a.get("comments_count"),
                           "body_letters_count": a.get("body_letters_count"), "username": u.get("username"),
                           "publication": p.get("name") if p else None})
    rec = {"fetched_at": stamp, "status": st, "items": latest}
    d = ROOT / "latest_feed"
    d.mkdir(exist_ok=True)
    with open(d / f"{day}.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    print(f"latest: status {st}, {len(latest)} items")


if __name__ == "__main__":
    main()
