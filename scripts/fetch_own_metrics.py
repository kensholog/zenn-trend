"""Record the public metrics of one Zenn account's articles (likes, bookmarks, comments, Hatena Bookmark counts)
and the account's follower count. Used to judge the operating policy (ideas/zenn-trend.md, decision of 2026-09-05):
"by the 6th article, if no article reached 10 likes and none has 3+ Hatena bookmarks, an individual account does not reach".

  python scripts/fetch_own_metrics.py [username]      default: kensholog
  -> appends one JSON line to own_metrics/<username>.jsonl  (run by .github/workflows/trend-feed.yml)

3 requests per run (user API, article list, Hatena count API). All values are public on zenn.dev.
"""
import json
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
JST = timezone(timedelta(hours=9))
UA = "Mozilla/5.0 (research; kensholog/zenn-trend own-metrics; 1req/s)"
USER = sys.argv[1] if len(sys.argv) > 1 else "kensholog"


def get_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))


def main():
    now = datetime.now(JST).isoformat(timespec="seconds")
    u = get_json(f"https://zenn.dev/api/users/{USER}")["user"]
    time.sleep(1.0)
    arts = get_json(f"https://zenn.dev/api/articles?username={USER}&order=latest&count=48")["articles"]
    time.sleep(1.0)
    urls = [f"https://zenn.dev{a['path']}" for a in arts]
    hb = {}
    if urls:
        q = "&".join("url=" + urllib.parse.quote(x, safe="") for x in urls[:50])
        try:
            hb = get_json("https://bookmark.hatenaapis.com/count/entries?" + q)
        except Exception as e:  # keep the Zenn metrics even if Hatena fails
            print("[warn] hatebu:", e, flush=True)
    rec = {
        "fetched_at": now,
        "username": USER,
        "follower_count": u.get("follower_count"),
        "total_liked_count": u.get("total_liked_count"),
        "articles_count": u.get("articles_count"),
        "articles": [
            {
                "path": a["path"], "published_at": a["published_at"], "liked_count": a["liked_count"],
                "bookmarked_count": a["bookmarked_count"], "comments_count": a["comments_count"],
                "hatebu": hb.get(f"https://zenn.dev{a['path']}"),
            }
            for a in arts
        ],
    }
    out = ROOT / "own_metrics"
    out.mkdir(exist_ok=True)
    with open(out / f"{USER}.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    print(f"{now} {USER}: followers={rec['follower_count']} total_liked={rec['total_liked_count']} articles={len(arts)} "
          + " ".join(f"{a['path'].rsplit('/', 1)[-1][:24]}:like{a['liked_count']}/hb{a['hatebu']}" for a in rec["articles"]), flush=True)


if __name__ == "__main__":
    main()
