"""Fetch every page of the Zenn topic listing for the registered topics.

  python scripts/fetch_topic_articles.py            # all topics (new + control), resumable
  python scripts/fetch_topic_articles.py mcp dify   # only these topics

Output: data/topics/<topic>.jsonl  (one article per line; listing fields only, no body)
        data/topics_meta.json       (per-topic articlesCount etc. from the topic page)
Rate:   1 request per second. Stops when next_page is null (hard cap: page 100).
Resume: a topic with an existing data/topics/<topic>.done marker is skipped.
"""
import io
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone, timedelta
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "topics"
UA = "Mozilla/5.0 (personal research on Zenn topics; 1 req/s; contact via zenn.dev/kensholog)"
JST = timezone(timedelta(hours=9))
SLEEP = 1.0

NEW_TOPICS = [
    "claudecode", "cursor", "dify", "mcp", "codex", "geminicli", "windsurf", "devin", "openclaw", "kiro",
    "cline", "roocode", "claude", "copilot", "githubcopilot", "agentskills", "n8n", "ollama", "langgraph",
    "v0", "bolt", "lovable", "replit", "aider", "openhands", "mastra", "a2a", "vibecoding", "deepseek",
    "gemini", "chatgpt", "openai", "llm", "rag", "aiエージェント", "生成ai", "ai", "antigravity", "codexcli",
]
CONTROL_TOPICS = ["react", "python", "typescript", "nextjs", "aws", "docker", "go", "rust", "個人開発", "データ分析", "統計", "投資"]


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
        "article_type": a.get("article_type"), "emoji": a.get("emoji"),
        "published_at": a.get("published_at"), "body_updated_at": a.get("body_updated_at"),
        "liked_count": a.get("liked_count"), "bookmarked_count": a.get("bookmarked_count"),
        "comments_count": a.get("comments_count"), "body_letters_count": a.get("body_letters_count"),
        "username": u.get("username"), "user_id": u.get("id"),
        "publication": p.get("name") if p else None,
    }


def fetch_topic(topic, meta):
    OUT.mkdir(parents=True, exist_ok=True)
    done = OUT / f"{topic}.done"
    out = OUT / f"{topic}.jsonl"
    if done.exists():
        print(f"[skip] {topic} (done)")
        return
    q = urllib.parse.quote(topic)
    st, html = get(f"https://zenn.dev/topics/{q}")
    time.sleep(SLEEP)
    m = re.search(r'"articlesCount":(\d+),"booksCount":(\d+),"scrapsCount":(\d+)', html)
    meta[topic] = {"page_status": st, "articles": int(m.group(1)) if m else None,
                   "books": int(m.group(2)) if m else None, "scraps": int(m.group(3)) if m else None,
                   "fetched_at": datetime.now(JST).isoformat(timespec="seconds")}
    n = 0
    with open(out, "w", encoding="utf-8") as f:
        page = 1
        while page <= 100:
            st, body = get(f"https://zenn.dev/api/articles?topicname={q}&order=latest&count=48&page={page}")
            time.sleep(SLEEP)
            if st != 200:
                print(f"[warn] {topic} page {page} status {st}")
                meta[topic]["last_status"] = st
                break
            d = json.loads(body)
            arts = d.get("articles", [])
            for a in arts:
                row = slim(a)
                row["topic"] = topic
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
            n += len(arts)
            nxt = d.get("next_page")
            if not arts or nxt is None:
                meta[topic]["last_page"] = page
                break
            page = nxt
    meta[topic]["rows"] = n
    meta[topic]["capped"] = page >= 100
    done.write_text(datetime.now(JST).isoformat(timespec="seconds"), encoding="utf-8")
    print(f"[done] {topic}: {n} rows, last page {meta[topic].get('last_page')}, capped={meta[topic]['capped']}")


def main():
    topics = sys.argv[1:] or (NEW_TOPICS + CONTROL_TOPICS)
    meta_path = ROOT / "data" / "topics_meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.exists() else {}
    for t in topics:
        try:
            fetch_topic(t, meta)
        finally:
            meta_path.parent.mkdir(parents=True, exist_ok=True)
            meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
