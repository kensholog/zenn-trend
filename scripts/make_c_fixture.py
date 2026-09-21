"""Synthetic feeds with known answers, to test aggregate_c.py without looking at any real indicator (decisions/0006).

  python scripts/make_c_fixture.py            # writes data/c_fixture/<scenario>/ and checks aggregate_c against the known answers

Scenarios: main (C1a >= 3, C1b < 3, C2 >= 10), no_new (no newcomer ever trends: zero-denominator rule, C2' undecidable),
           early (timeline stops before T_end: the guard must refuse to print indicators).
Everything is invented: a snapshot every 3 hours, 48 births per snapshot with fixed strata, a fixed rule for who trends.
The expected values are computed from the generator's own bookkeeping, not by calling the code under test.
"""
import json
import shutil
import statistics
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import aggregate_c as agc  # noqa: E402  (re-wraps stdout as UTF-8; do not wrap again here)
import c_common as cc  # noqa: E402

BASE = cc.ROOT / "data" / "c_fixture"
T0 = datetime(2026, 9, 4, 12, 10, tzinfo=cc.JST)
STEP = timedelta(hours=3)
LAST_IDX = 225                      # index 224 is 2026-10-02 12:10 (= T_end); 225 lies after T_end and must be ignored
MISSING = set(range(100, 105))      # 18-hour hole between 99 and 105 -> births at 105 fall inside it and are dropped
FAILED = {50}                       # trend feed failed (500, no items); latest still fine -> an incomplete snapshot
FIRST_LIKES = {agc.NEW: 6, agc.VET: 12, agc.PUB: 15}


def iso(t):
    return t.isoformat(timespec="seconds")


def stratum_of(j):
    return agc.NEW if j < 24 else agc.VET if j < 40 else agc.PUB


def build(scenario):
    out = BASE / scenario
    if out.exists():
        shutil.rmtree(out)
    for d in ("trend_feed", "latest_feed", "data/c"):
        (out / d).mkdir(parents=True)
    last = 60 if scenario == "early" else LAST_IDX
    idx = [i for i in range(last + 1) if i not in MISSING]
    t = {i: T0 + STEP * i for i in idx}
    trend_ok = [i for i in idx if i not in FAILED]

    arts, sightings = [], {i: [] for i in idx}
    for i in idx:
        for j in range(48):
            s = stratum_of(j)
            failed_author = (j == 23 and i % 10 == 0)
            enters = (j in (40, 41)) if s == agc.PUB else (j == 24) if s == agc.VET else (j == 0 and i % 2 == 0 and scenario != "no_new")
            a = {"slug": f"a{i:03d}x{j:02d}", "user": f"u{i:03d}x{j:02d}", "pub": "pubx" if s == agc.PUB else None,
                 "stratum": None if failed_author else s, "born": i, "published": t[i] - timedelta(hours=1),
                 "first_timer": j < 12, "failed_author": failed_author, "first": None, "first_likes": None}
            a["path"] = f"/{a['pub'] or a['user']}/articles/{a['slug']}"
            if enters:
                slots = [k for k in trend_ok if k >= i + 2][:3]
                for n, k in enumerate(slots):
                    sightings[k].append((a, FIRST_LIKES[s] + 5 * n))
                if slots:
                    a["first"], a["first_likes"] = slots[0], FIRST_LIKES[s]
            a["final"] = (a["first_likes"] or 1) * 4 if a["first"] is not None else (2 if s == agc.NEW else 8)
            arts.append(a)
    olds = []
    for k in (30, 60, 90):
        if k in t and k in trend_ok:
            o = {"slug": f"old{k}", "user": f"old{k}", "pub": None, "path": f"/old{k}/articles/old{k}", "stratum": agc.VET,
                 "published": datetime(2026, 8, 20, 9, 0, tzinfo=cc.JST), "first": k, "first_likes": 40, "final": 80,
                 "first_timer": False, "failed_author": False}
            sightings[k].append((o, 40))
            olds.append(o)

    def trend_item(rank, path, user, pub, published, likes):
        return {"rank": rank, "title": "x", "path": path, "pub_date": "", "creator": "x", "detail_status": 200, "id": rank,
                "article_type": "tech", "published_at": iso(published), "liked_count": likes, "bookmarked_count": 0,
                "comments_count": 0, "body_letters_count": 3000, "topics": [], "username": user, "publication": pub}

    filler_pub = datetime(2026, 8, 1, 9, 0, tzinfo=cc.JST)
    for i in idx:
        day = t[i].strftime("%Y-%m-%d")
        items = []
        if i in trend_ok:
            for a, likes in sightings[i]:
                items.append(trend_item(len(items) + 1, a["path"], a["user"], a["pub"], a["published"], likes))
            if 10 <= i <= 12:   # a book without detail fields: must be ignored everywhere
                items.append({"rank": len(items) + 1, "title": "book", "path": "/someone/books/book1", "pub_date": "", "creator": "x"})
            k = 0
            while len(items) < cc.TREND_N:
                items.append(trend_item(len(items) + 1, f"/filler{k}/articles/f{k:02d}", f"filler{k}", None, filler_pub, 100))
                k += 1
        rec = {"fetched_at": iso(t[i]), "source": "synthetic", "feed_status": 200 if i in trend_ok else 500, "items": items}
        with open(out / "trend_feed" / f"{day}.jsonl", "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        latest = [{"path": a["path"], "article_type": "tech", "published_at": iso(a["published"]), "liked_count": 0,
                   "bookmarked_count": 0, "comments_count": 0, "body_letters_count": 3000, "username": a["user"],
                   "publication": a["pub"]} for a in arts if a["born"] == i]
        with open(out / "latest_feed" / f"{day}.jsonl", "a", encoding="utf-8") as f:
            f.write(json.dumps({"fetched_at": iso(t[i]), "status": 200, "items": latest}, ensure_ascii=False) + "\n")

    def row(user, slug, path, published, likes, pub=None):
        return json.dumps({"id": 1, "slug": slug, "path": path, "title": "x", "article_type": "tech", "published_at": iso(published),
                           "liked_count": likes, "bookmarked_count": 0, "comments_count": 0, "body_letters_count": 3000,
                           "username": user, "publication": pub}, ensure_ascii=False) + "\n"

    with open(out / "data/c/author_articles.jsonl", "w", encoding="utf-8") as fa, \
            open(out / "data/c/author_done.txt", "w", encoding="utf-8") as fd, \
            open(out / "data/c/users.jsonl", "w", encoding="utf-8") as fu:
        everyone = arts + olds + [{"slug": f"f{k:02d}", "user": f"filler{k}", "pub": None, "path": f"/filler{k}/articles/f{k:02d}",
                                   "published": filler_pub, "final": 400, "stratum": agc.VET, "first_timer": False,
                                   "failed_author": False} for k in range(cc.TREND_N)]
        for a in everyone:
            if a["failed_author"]:
                fd.write(f"{a['user']}\t0\t404\n")
                fu.write(json.dumps({"username": a["user"], "status": 404}) + "\n")
                continue
            past = [] if a["first_timer"] else {agc.NEW: [0, 1], agc.VET: [4, 6], agc.PUB: [20, 40]}[a["stratum"]]
            fa.write(row(a["user"], a["slug"], a["path"], a["published"], a["final"], a["pub"]))
            for n, likes in enumerate(past):
                fa.write(row(a["user"], f"{a['slug']}p{n}", f"/{a['user']}/articles/{a['slug']}p{n}", a["published"] - timedelta(days=30 * (n + 1)), likes))
            fd.write(f"{a['user']}\t{1 + len(past)}\t200\n")
            fu.write(json.dumps({"username": a["user"], "status": 200, "follower_count": 0 if a["first_timer"] else 50,
                                 "total_liked_count": a["final"] + sum(past), "articles_count": 1 + len(past)}) + "\n")
    return out, t, idx, arts, olds


def expected(t, idx, arts, olds):
    """Known answers from the generator's own records (the registered rules re-stated by hand, not via c_common)."""
    t_end = t[224]
    gap_a, gap_b = t[99], t[105]
    exp = {}
    for margin in (72, 168):
        cut = t_end - timedelta(hours=margin)
        coh = [a for a in arts if T0 <= a["published"] <= cut and not (gap_a < a["published"] < gap_b)]
        exp[margin] = {s: (sum(1 for a in coh if a["stratum"] == s), sum(1 for a in coh if a["stratum"] == s and a["first"] is not None and a["first"] <= 224))
                       for s in agc.STRATA}
        exp[margin]["n"] = len(coh)
    exp["dropped"] = sum(1 for a in arts if gap_a < a["published"] < gap_b and T0 <= a["published"] <= t_end - timedelta(hours=72))
    seen = [a for a in arts + olds if a["first"] is not None and a["first"] <= 224]
    exp["c2_n"] = len(seen)
    exp["c2_median"] = statistics.median(a["first_likes"] for a in seen)
    exp["c2new_n"] = sum(1 for a in seen if a["stratum"] == agc.NEW)
    exp["complete"] = sum(1 for i in idx if i <= 224 and i not in FAILED)
    exp["snapshots"] = sum(1 for i in idx if i <= 224)
    return exp


def check(name, got, want):
    ok = got == want or (isinstance(want, float) and got is not None and abs(got - want) < 1e-9)  # == first: inf - inf is nan
    print(f"  {'ok ' if ok else 'NG '} {name}: got {got} / expected {want}")
    return ok


def main():
    results = []
    for scenario in ("main", "no_new", "early"):
        out, t, idx, arts, olds = build(scenario)
        res, lines = agc.run(out, "full")
        print(f"=== {scenario}: {out.relative_to(cc.ROOT)}")
        if scenario == "early":
            results += [check("t_end is None (guard)", res["t_end"], None),
                        check("no indicator keys", sorted(k for k in res if k.startswith("c")), []),
                        check("refusal line present", any("指標は出さない" in x for x in lines), True)]
            continue
        (out / "results_c.md").write_text("\n".join(lines), encoding="utf-8")
        e = expected(t, idx, arts, olds)
        by = res["c1_rows"]
        results += [check("snapshots up to T_end", res["health"]["n"], e["snapshots"]),
                    check("complete snapshots", res["health"]["complete"], e["complete"]),
                    check("long gap total hours", res["health"]["gap_total_h"], 18.0),
                    check("cohort size (72 h)", res["cohort_n"], e[72]["n"]),
                    check("dropped by the gap rule", res["dropped_gap"], e["dropped"])]
        for s in agc.STRATA:
            results.append(check(f"{s} (n, entered)", (by[s]["n"], by[s]["entered"]), e[72][s]))
        new_n, new_e = e[72][agc.NEW]
        if new_e:
            results += [check("C1a ratio", res["c1a"], (e[72][agc.PUB][1] / e[72][agc.PUB][0]) / (new_e / new_n)),
                        check("C1b ratio", res["c1b"], (e[72][agc.VET][1] / e[72][agc.VET][0]) / (new_e / new_n))]
        else:
            results += [check("C1a zero-denominator rule", res["c1a"], float("inf")), check("C1b zero-denominator rule", res["c1b"], float("inf"))]
        results += [check("C2 articles", res["c2_n"], e["c2_n"]), check("C2 median", float(res["c2_median"]), float(e["c2_median"])),
                    check("C2' newcomer articles", res["c2new_n"], e["c2new_n"])]
    print("ALL OK" if all(results) else "FAILED")
    sys.exit(0 if all(results) else 1)


if __name__ == "__main__":
    main()
