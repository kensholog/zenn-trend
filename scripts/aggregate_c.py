"""C aggregation, exactly as registered in docs/decisions/0006 (readings left to the implementation: 0007).

  python scripts/aggregate_c.py --snapshots   # collection health only (A''-1, A''-3 so far). The one mode allowed before T_end
  python scripts/aggregate_c.py --criteria    # A'' / B'' only (counts; run BEFORE looking at any rate)
  python scripts/aggregate_c.py               # criteria + C1a, C1b, C2, C2', C3 -> docs/results_c.md and docs/data/c_*.csv
  python scripts/aggregate_c.py --fixture data/c_fixture   # same on synthetic data (scripts/make_c_fixture.py); writes into that folder

Guard: on the real feeds nothing but --snapshots runs before T_end (first snapshot at or after 2026-10-02 12:10 JST).
The script was written on 2026-09-21, before T_end, and was only ever run on synthetic data until then.
Inputs: trend_feed/, latest_feed/, data/c/author_articles.jsonl, data/c/author_done.txt, data/c/users.jsonl
"""
import argparse
import csv
import io
import json
import sys
from collections import Counter, defaultdict
from datetime import timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import c_common as cc  # noqa: E402

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", line_buffering=True)
NEW, VET, PUB = "個人×新参", "個人×実績あり", "Publication"
STRATA = (NEW, VET, PUB)
RATIO_MIN, ENTRY_LIKES, HIT = 3.0, 10, 10           # C1a / C1b threshold, C2 threshold, "hit" as in 0001
B_ENTERED_MIN, B_NEW_MIN, C2_NEW_MIN = 100, 500, 20  # B'' and the C2' floor
AVG_BINS = [("<1（初投稿を含む）", lambda x: x < 1), ("1-5", lambda x: 1 <= x < 5), ("5-20", lambda x: 5 <= x < 20), (">=20", lambda x: x >= 20)]
FOLLOWER_BINS = [("0", lambda x: x == 0), ("1-9", lambda x: 1 <= x < 10), ("10-99", lambda x: 10 <= x < 100), (">=100", lambda x: x >= 100)]


def pct(xs, p):
    xs = sorted(xs)
    if not xs:
        return None
    k = (len(xs) - 1) * p
    lo = int(k)
    hi = min(lo + 1, len(xs) - 1)
    return xs[lo] + (xs[hi] - xs[lo]) * (k - lo)


def fmt(x, kind="pct"):
    if x is None:
        return "—"
    return f"{x * 100:.2f}%" if kind == "pct" else f"{x:.2f}" if kind == "num" else f"{x:.1f}"


def hours(d):
    return d.total_seconds() / 3600


def health(pairs):
    gaps = cc.long_gaps(pairs)
    ok = sum(1 for p in pairs if p[3])
    all_gaps = sorted(hours(b - a) for a, b in zip([p[0] for p in pairs], [p[0] for p in pairs][1:]))
    return {"n": len(pairs), "complete": ok, "rate": ok / len(pairs) if pairs else None, "gaps": gaps,
            "gap_total_h": sum(hours(b - a) for a, b in gaps), "gap_median_h": pct(all_gaps, 0.5), "gap_max_h": all_gaps[-1] if all_gaps else None}


def health_lines(h, t_end):
    a1 = "通過" if (h["rate"] or 0) >= 0.95 else "**抵触**"
    a3 = "通過" if h["gap_total_h"] <= cc.GAP_TOTAL_MAX_H else "**抵触**"
    return [f"- 期間: {h['first'].isoformat(timespec='minutes')} 〜 {h['last'].isoformat(timespec='minutes')}、T_end {'未到達' if t_end is None else t_end.isoformat(timespec='minutes')}",
            f"- A''-1: 完全なスナップショット（トレンド 200・20 件 かつ 新着 200・48 件）{h['complete']:,} / {h['n']:,} = **{fmt(h['rate'])}**（95% 以上で通過）→ {a1}",
            f"- A''-3: 12 時間を超える取得間隔 {len(h['gaps'])} 回、合計 **{h['gap_total_h']:.1f} 時間**（72 時間以下で通過）→ {a3}。間隔の中央値 {fmt(h['gap_median_h'], 'h')} 時間、最大 {fmt(h['gap_max_h'], 'h')} 時間"]


def load_authors(root):
    d = Path(root) / "data" / "c"
    hist, final = defaultdict(list), {}
    for line in open(d / "author_articles.jsonl", encoding="utf-8"):
        r = json.loads(line)
        s = r.get("slug") or cc.slug_of(r.get("path"))
        if not (r.get("username") and s and r.get("published_at")):
            continue
        hist[r["username"]].append((cc.ts(r["published_at"]), s, r.get("liked_count") or 0))
        final[s] = r.get("liked_count") or 0
    done = {}
    for line in open(d / "author_done.txt", encoding="utf-8"):
        p = line.rstrip("\n").split("\t")
        if p[0]:
            done[p[0]] = int(p[2]) if len(p) > 2 and p[2].isdigit() else 0
    users = {}
    for line in open(d / "users.jsonl", encoding="utf-8"):
        u = json.loads(line)
        users[u["username"]] = u
    return hist, final, done, users


def past_avg(rows, slug, published):
    """Mean liked_count of the same author's articles published strictly before this one. None = first post."""
    earlier = [likes for p, s, likes in rows if p < published and s != slug]
    return sum(earlier) / len(earlier) if earlier else None


def classify(a, publication, hist, done):
    """0006 strata. Publication articles need no author data; individuals with no usable history stay unclassified."""
    if publication:
        return PUB, None
    if done.get(a["username"]) != 200 or a.get("published") is None:
        return None, None
    avg = past_avg(hist.get(a["username"], []), a["slug"], a["published"])
    return (NEW if avg is None or avg < 1 else VET), avg


def rate_rows(arts, key, labels):
    rows = []
    for lab in labels:
        g = [a for a in arts if a[key] == lab]
        e = sum(1 for a in g if a["entered"])
        rows.append({"label": lab, "n": len(g), "entered": e, "rate": e / len(g) if g else None})
    return rows


def ratio_verdict(num, den, yes, no):
    """num, den: rate rows. A zero denominator count with a non-zero numerator is read as '3 or more' (0006 for C1a, 0007 for C1b)."""
    if not num["n"] or not den["n"] or (num["entered"] == 0 and den["entered"] == 0):
        return None, "**判定不能**（層が空、または両方 0 本）"
    if den["entered"] == 0:
        return float("inf"), f"分母 0 本のため「3 以上」として扱う（分母の率の 95% 上限 {fmt(3 / den['n'])}）→ **{yes}**"
    r = num["rate"] / den["rate"]
    return r, f"**{fmt(r, 'num')}** → **{yes if r >= RATIO_MIN else no}**"


def c1(pairs, t_end, margin_h, gaps, trend, hist, done, users):
    cohort, dropped = cc.birth_cohort(pairs, t_end, margin_h, gaps)
    arts = list(cohort.values())
    for a in arts:
        t = trend.get(a["slug"])
        a["entered"] = t is not None
        pub = t["publication"] if t and t["has_detail"] else a["publication"]  # trend_feed wins when both exist
        a["stratum"], _ = classify(a, pub, hist, done)
        # descriptive bins use the author's past average whatever the stratum; a first post counts as 0 (as in 0001)
        a["avg"] = None
        if done.get(a["username"]) == 200:
            v = past_avg(hist.get(a["username"], []), a["slug"], a["published"])
            a["avg"] = 0.0 if v is None else v
        a["avg_bin"] = next((lab for lab, f in AVG_BINS if a["avg"] is not None and f(a["avg"])), "不明")
        u = users.get(a["username"]) or {}
        fc = u.get("follower_count") if u.get("status") == 200 else None
        a["fol_bin"] = next((lab for lab, f in FOLLOWER_BINS if fc is not None and f(fc)), "不明")
    return arts, dropped


def summary(xs, ps):
    return {"n": len(xs), **{f"p{int(p * 100)}": pct(xs, p) for p in ps}}


def run(root, mode="full"):
    root = Path(root)
    trend_s, latest_s = cc.load_snapshots(root, "trend_feed"), cc.load_snapshots(root, "latest_feed")
    t_end = cc.find_t_end(trend_s)
    pairs = cc.pair(trend_s, latest_s, until=t_end)
    h = health(pairs)
    h["first"], h["last"] = pairs[0][0], pairs[-1][0]
    out = ["## 収集の到達（件数と時刻だけ）\n"] + health_lines(h, t_end) + [""]
    res = {"health": h, "t_end": t_end}
    if mode == "snapshots" or t_end is None:
        if mode != "snapshots":
            out.append("**T_end 前なので、指標は出さない（decisions/0006）。** `--snapshots` 以外は T_end の後に実行する。")
        return res, out

    hist, final, done, users = load_authors(root)
    gaps = h["gaps"]
    trend = cc.trend_articles(pairs)
    _, names = cc.c_authors(root)
    got = sum(1 for n in names if done.get(n) == 200 and (users.get(n) or {}).get("status") == 200)
    arts, dropped = c1(pairs, t_end, cc.MARGIN_H, gaps, trend, hist, done, users)
    entered = sum(1 for a in arts if a["entered"])
    n_new = sum(1 for a in arts if a["stratum"] == NEW)
    a2 = got / len(names) if names else None
    res.update({"a2": a2, "cohort_n": len(arts), "cohort_entered": entered, "n_new": n_new, "dropped_gap": dropped})
    c1_ok = entered >= B_ENTERED_MIN and n_new >= B_NEW_MIN
    a_ok = (h["rate"] or 0) >= 0.95 and (a2 or 0) >= 0.95 and h["gap_total_h"] <= cc.GAP_TOTAL_MAX_H
    out += ["## 撤退基準の判定\n",
            f"- A''-2: 著者データ（記事一覧とユーザー API の両方が 200）{got:,} / {len(names):,} = **{fmt(a2)}**（95% 以上で通過）",
            f"- B'': 誕生コホート（公開が T_end − {cc.MARGIN_H} 時間以前）{len(arts):,} 本、うちトレンド入り **{entered:,} 本**（100 本以上）、個人×新参 **{n_new:,} 本**（500 本以上）。12 時間超の欠測区間で除いた記事 {dropped:,} 本、層を決められなかった記事 {sum(1 for a in arts if a['stratum'] is None):,} 本",
            f"- 判定: A'' {'通過' if a_ok else '**抵触（記事化しない）**'} / B'' {'C1 判定可' if c1_ok else '**C1 は判定不能**（C2・C3 だけで書く）'}\n"]
    if mode == "criteria":
        return res, out

    # ---- C1a / C1b
    csv_rates = []
    for margin in (cc.MARGIN_H, cc.MARGIN_ROBUST_H):
        if margin != cc.MARGIN_H:
            arts_m, _ = c1(pairs, t_end, margin, gaps, trend, hist, done, users)
        else:
            arts_m = arts
        rows = rate_rows(arts_m, "stratum", STRATA)
        by = {r["label"]: r for r in rows}
        title = "主" if margin == cc.MARGIN_H else "頑健性"
        out += [f"## C1 トレンドには誰が入るか（{title}: 公開が T_end − {margin} 時間以前、{len(arts_m):,} 本）\n",
                "| 層 | 記事数 | トレンド入り | 率 |\n|---|---|---|---|"]
        out += [f"| {r['label']} | {r['n']:,} | {r['entered']:,} | {fmt(r['rate'])} |" for r in rows]
        ra, va = ratio_verdict(by[PUB], by[NEW], "トレンド入りも著者の経路で決まる（いいねと同じ構造）", "トレンドは新参にも開かれている")
        rb, vb = ratio_verdict(by[VET], by[NEW], "個人でも既存の読者があれば入る（経路は Publication だけではない）", "個人では実績があっても新参と大差ない")
        out += [f"\n- **C1a** Publication ÷ 個人×新参 = {va}", f"- **C1b** 個人×実績あり ÷ 個人×新参 = {vb}"]
        if margin == cc.MARGIN_H:
            res.update({"c1_rows": by, "c1a": ra, "c1b": rb})
            if not c1_ok:
                out.append("- **B'' に抵触しているので、上の比は判定に使わない（参考値）**")
        for kind, key, labels in (("過去平均（著者の、その記事より前の記事の平均いいね）", "avg_bin", [b[0] for b in AVG_BINS] + ["不明"]),
                                  ("フォロワー（取得時点。トレンド入りで増えた分を含む）", "fol_bin", [b[0] for b in FOLLOWER_BINS] + ["不明"])):
            sub = rate_rows(arts_m, key, labels)
            out += [f"\n副の層（記述のみ）: {kind}\n", "| 層 | 記事数 | トレンド入り | 率 |\n|---|---|---|---|"]
            out += [f"| {r['label']} | {r['n']:,} | {r['entered']:,} | {fmt(r['rate'])} |" for r in sub]
            csv_rates += [dict(margin_h=margin, kind=key, **r) for r in sub]
        csv_rates += [dict(margin_h=margin, kind="stratum", **r) for r in rows]
        out.append("")

    # ---- C2 / C2'
    obs = [t for t in trend.values() if not t["left_censored"]]
    for t in obs:
        t["stratum"], _ = classify(t, t["publication"], hist, done)
    likes = [t["first_likes"] for t in obs if t["first_likes"] is not None]
    med = pct(likes, 0.5)
    res.update({"c2_n": len(likes), "c2_median": med})
    out += ["## C2 入口の高さ: 初観測時いいね\n",
            f"- 対象: トレンドに出た記事 {len(trend):,} 本のうち、最初のスナップショットに居た {sum(1 for t in trend.values() if t['left_censored'])} 本を除く {len(obs):,} 本（初観測時いいねが欠けた記事 {len(obs) - len(likes)} 本）",
            f"- p10 {fmt(pct(likes, 0.1), 'h')} / p25 {fmt(pct(likes, 0.25), 'h')} / **中央値 {fmt(med, 'h')}** / p75 {fmt(pct(likes, 0.75), 'h')}"]
    if med is not None and med < ENTRY_LIKES:
        out.append("- 判定: **過半の記事は いいね 10 に届く前にトレンドに入っている**（いいね 10 到達はトレンド入りの後に起きうる）。初観測時いいねは入口の上限なので、この結論は取得間隔に対して頑健")
    elif med is not None:
        out.append("- 判定: **トレンドに見つかった時点で過半は既に 10 を超えている**。ただし初観測は実際のトレンド入りより最大で取得間隔ぶん遅く、初観測時いいねは入口の**上限**。取得間隔による上振れの可能性がある")
    c2_rows = [dict(group="all", **summary(likes, (0.1, 0.25, 0.5, 0.75)))]
    out.append("\n| 層 | 記事数 | p25 | 中央値 | p75 |\n|---|---|---|---|---|")
    for lab in STRATA:
        v = [t["first_likes"] for t in obs if t["stratum"] == lab and t["first_likes"] is not None]
        c2_rows.append(dict(group=lab, **summary(v, (0.1, 0.25, 0.5, 0.75))))
        if lab == NEW and len(v) < C2_NEW_MIN:   # below the C2' floor: count and range only
            out.append(f"| {lab} | {len(v)} | — | — | — |")
            note = f"- **C2'** 個人×新参は {len(v)} 本で 20 本未満 → **判定不能**" + (f"（範囲 {min(v)}〜{max(v)}）" if v else "")
        else:
            out.append(f"| {lab} | {len(v):,} | {fmt(pct(v, 0.25), 'h')} | {fmt(pct(v, 0.5), 'h')} | {fmt(pct(v, 0.75), 'h')} |")
        if lab == NEW:
            m = pct(v, 0.5)
            res.update({"c2new_n": len(v), "c2new_median": m})
            if len(v) >= C2_NEW_MIN:
                note = f"- **C2'** 個人×新参の中央値 {fmt(m, 'h')} → " + ("**新参も いいね 10 に届く前に入っている**" if m < ENTRY_LIKES else "**新参は見つかった時点で既に 10 を超えている**（上振れの注意は同じ）")
    out += ["", note, f"- 層を決められなかった記事 {sum(1 for t in obs if t['stratum'] is None)} 本は層別の表に入れていない", ""]

    # ---- C3 (descriptive only)
    up = [hours(t["first"] - t["published"]) for t in obs if t["published"]]
    lo = [max(hours(t["prev"] - t["published"]), 0.0) for t in obs if t["published"] and t["prev"]]
    stay = [hours(t["last"] - t["first"]) for t in obs]
    censored = sum(1 for t in obs if t["last"] == pairs[-1][0])
    share = [t["first_likes"] / final[t["slug"]] for t in obs if t["first_likes"] is not None and final.get(t["slug"])]
    res.update({"c3_up_median": pct(up, 0.5), "c3_share_median": pct(share, 0.5)})
    out += ["## C3 記述のみ（判定なし）\n",
            "| 指標 | 記事数 | p10 | 中央値 | p90 |\n|---|---|---|---|---|",
            f"| (a) 公開から初観測まで（時間、上限） | {len(up):,} | {fmt(pct(up, 0.1), 'h')} | {fmt(pct(up, 0.5), 'h')} | {fmt(pct(up, 0.9), 'h')} |",
            f"| (a) 公開から直前のスナップショットまで（時間、下限） | {len(lo):,} | {fmt(pct(lo, 0.1), 'h')} | {fmt(pct(lo, 0.5), 'h')} | {fmt(pct(lo, 0.9), 'h')} |",
            f"| (b) 初観測から最終観測まで（時間） | {len(stay):,} | {fmt(pct(stay, 0.1), 'h')} | {fmt(pct(stay, 0.5), 'h')} | {fmt(pct(stay, 0.9), 'h')} |",
            f"| (c) 初観測時いいね ÷ 取得時点のいいね | {len(share):,} | {fmt(pct(share, 0.1), 'num')} | {fmt(pct(share, 0.5), 'num')} | {fmt(pct(share, 0.9), 'num')} |",
            f"\n- (a) 初観測が公開から {cc.MARGIN_H} 時間より後だった記事 {fmt(sum(1 for x in up if x > cc.MARGIN_H) / len(up) if up else None)}、{cc.MARGIN_ROBUST_H} 時間より後 {fmt(sum(1 for x in up if x > cc.MARGIN_ROBUST_H) / len(up) if up else None)}（コホートの打ち切りが足りているかの確認）",
            f"- (b) T_end の時点でまだトレンドに居た記事 {censored} 本（滞在は右側打ち切り）",
            "- (c) は因果ではない（伸びる記事がトレンドに入ったのか、入ったから伸びたのかは区別できない）\n",
            "(d) 誕生コホートでトレンドに入らなかった記事の、取得時点のいいね\n",
            "| 層 | 記事数 | 中央値 | p75 | p90 | いいね 10 以上 |\n|---|---|---|---|---|---|"]
    c3_rows = [dict(metric=m, **summary(v, (0.1, 0.5, 0.9))) for m, v in (("publish_to_first_upper_h", up), ("publish_to_prev_lower_h", lo), ("stay_h", stay), ("first_likes_share", share))]
    for lab in STRATA:
        v = [final[a["slug"]] for a in arts if not a["entered"] and a["stratum"] == lab and a["slug"] in final]
        out.append(f"| {lab} | {len(v):,} | {fmt(pct(v, 0.5), 'h')} | {fmt(pct(v, 0.75), 'h')} | {fmt(pct(v, 0.9), 'h')} | {fmt(sum(1 for x in v if x >= HIT) / len(v) if v else None)} |")
        c3_rows.append(dict(metric=f"not_entered_final_likes_{lab}", **summary(v, (0.1, 0.5, 0.9))))
    hrs = Counter(a["published"].hour for a in arts)
    out += ["\n誕生コホートの公開時刻（JST の時。新着プールの時刻の偏りの確認）\n", "| 時 | " + " | ".join(str(i) for i in range(24)) + " |", "|---|" + "---|" * 24,
            "| 記事数 | " + " | ".join(str(hrs.get(i, 0)) for i in range(24)) + " |", ""]

    fixture = root.resolve() != cc.ROOT.resolve()
    ddir = root / "docs_data" if fixture else cc.ROOT / "docs" / "data"
    ddir.mkdir(parents=True, exist_ok=True)
    for name, rows in (("c_rates.csv", csv_rates), ("c_first_likes.csv", c2_rows), ("c_timing.csv", c3_rows),
                       ("c_hours.csv", [{"hour": i, "n": hrs.get(i, 0)} for i in range(24)])):
        with open(ddir / name, "w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)
    return res, out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--snapshots", action="store_true")
    ap.add_argument("--criteria", action="store_true")
    ap.add_argument("--fixture", help="folder with synthetic trend_feed/, latest_feed/ and data/c/ (scripts/make_c_fixture.py)")
    args = ap.parse_args()
    root = Path(args.fixture) if args.fixture else cc.ROOT
    res, out = run(root, "snapshots" if args.snapshots else "criteria" if args.criteria else "full")
    header = [f"# C「トレンドには誰が入るか、入口はどの高さか」の結果{'（合成データ。実データではない）' if args.fixture else ''}\n",
              "定義は docs/decisions/0006（実装に委ねられた読み方は 0007）。liked_count・フォロワー数は取得時点の値。著者名は含まない。\n"]
    text = "\n".join(header + out)
    print(text)
    if res["t_end"] is not None and not args.snapshots and not args.criteria:
        (root / "results_c.md" if args.fixture else cc.ROOT / "docs" / "results_c.md").write_text(text, encoding="utf-8")
    if res["t_end"] is None and not args.snapshots:
        sys.exit(1)


if __name__ == "__main__":
    main()
