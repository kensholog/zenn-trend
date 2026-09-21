"""Definitions shared by the C scripts (fetch_c_authors.py, aggregate_c.py), as registered in docs/decisions/0006.

Nothing here prints an indicator. Windows and thresholds are frozen by 0006 (2026-09-21); do not edit them.
Readings of 0006 that the text leaves to the implementation are listed in docs/decisions/0007.
"""
import json
import re
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
JST = timezone(timedelta(hours=9))
ARTICLE_RE = re.compile(r"^/([^/]+)/articles/([^/?#]+)$")  # books, scraps and other paths are out of every indicator
T_END_MIN = datetime(2026, 10, 2, 12, 10, tzinfo=JST)      # T_end = first snapshot at or after this
MARGIN_H, MARGIN_ROBUST_H = 72, 168                         # birth cohort: published_at <= T_end - margin
GAP_EXCLUDE_H, GAP_TOTAL_MAX_H = 12, 72                     # exclusion rule / criterion A''-3
TREND_N, LATEST_N = 20, 48                                  # a complete snapshot (criterion A''-1)


def ts(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00")).astimezone(JST)


def slug_of(path):
    m = ARTICLE_RE.match(path or "")
    return m.group(2) if m else None


def load_snapshots(root, name):
    snaps = []
    for p in sorted((Path(root) / name).glob("*.jsonl")):
        for line in open(p, encoding="utf-8"):
            if line.strip():
                r = json.loads(line)
                r["t"] = ts(r["fetched_at"])
                snaps.append(r)
    snaps.sort(key=lambda r: r["t"])
    return snaps


def find_t_end(snaps):
    return next((r["t"] for r in snaps if r["t"] >= T_END_MIN), None)


def complete(trend, latest):
    """A''-1: trend 200 with 20 items and latest 200 with 48 items."""
    return (trend.get("feed_status") == 200 and len(trend["items"]) == TREND_N
            and latest is not None and latest.get("status") == 200 and len(latest["items"]) == LATEST_N)


def pair(trend_snaps, latest_snaps, until=None):
    """Both feeds are written by one run with the same fetched_at. Returns [(t, trend, latest, complete)]."""
    lat = {r["fetched_at"]: r for r in latest_snaps}
    rows = []
    for tr in trend_snaps:
        if until is not None and tr["t"] > until:
            continue
        la = lat.get(tr["fetched_at"])
        rows.append((tr["t"], tr, la, complete(tr, la)))
    return rows


def long_gaps(pairs):
    """Intervals between consecutive complete snapshots longer than 12 hours (an incomplete run observes nothing)."""
    ok = [t for t, _, _, c in pairs if c]
    return [(a, b) for a, b in zip(ok, ok[1:]) if (b - a) > timedelta(hours=GAP_EXCLUDE_H)]


def birth_cohort(pairs, t_end, margin_h, gaps):
    """slug -> article first seen in latest_feed, T0 <= published_at <= T_end - margin, not inside a long gap."""
    t0 = pairs[0][0]
    cut = t_end - timedelta(hours=margin_h)
    cohort, dropped_gap = {}, 0
    for t, _, la, _ in pairs:
        for it in (la or {}).get("items", []):
            s = slug_of(it.get("path"))
            if not s or s in cohort or not it.get("published_at"):
                continue
            p = ts(it["published_at"])
            if not (t0 <= p <= cut):
                continue
            if any(a < p < b for a, b in gaps):
                dropped_gap += 1
                continue
            cohort[s] = {"slug": s, "path": it["path"], "username": it.get("username"), "published": p,
                         "publication": it.get("publication"), "first_latest": t}
    return cohort, dropped_gap


def trend_articles(pairs):
    """slug -> sightings of an article in trend_feed. first_likes is liked_count at the first sighting (an upper bound
    of the likes at entry, because the true entry lies between the previous snapshot and the first sighting)."""
    seen, prev_t = {}, None
    first_t = pairs[0][0]
    for t, tr, _, _ in pairs:
        for it in tr["items"]:
            s = slug_of(it.get("path"))
            if not s:
                continue
            if s not in seen:
                seen[s] = {"slug": s, "path": it["path"], "username": it.get("username"),
                           "publication": it.get("publication"), "has_detail": it.get("detail_status") == 200,
                           "published": ts(it["published_at"]) if it.get("published_at") else None,
                           "first": t, "prev": prev_t, "last": t, "n": 0, "first_likes": it.get("liked_count"),
                           "last_likes": it.get("liked_count"), "left_censored": t == first_t}
            a = seen[s]
            a["last"], a["n"] = t, a["n"] + 1
            if it.get("liked_count") is not None:
                a["last_likes"] = it["liked_count"]
            if not a["username"] and it.get("username"):
                a["username"] = it["username"]
        if tr["items"]:
            prev_t = t
    return seen


def c_authors(root):
    """Usernames whose histories 0006 needs: birth cohort (72 h margin) plus every trend article. None before T_end."""
    trend, latest = load_snapshots(root, "trend_feed"), load_snapshots(root, "latest_feed")
    t_end = find_t_end(trend)
    if t_end is None:
        return None, None
    pairs = pair(trend, latest, until=t_end)
    cohort, _ = birth_cohort(pairs, t_end, MARGIN_H, long_gaps(pairs))
    names = {a["username"] for a in cohort.values()} | {a["username"] for a in trend_articles(pairs).values()}
    return t_end, sorted(n for n in names if n)
