"""Second project aggregation, exactly as registered in docs/decisions/0003 (with the Q1b fix in 0004).

  python scripts/aggregate_q.py --criteria   # retreat criteria A' / B' only (counts; run BEFORE looking at any rate)
  python scripts/aggregate_q.py              # criteria + Q1a..Q1e + Q2, writes docs/results_q.md and docs/data/q*.csv

Inputs: data/author_articles.jsonl, data/author_done.txt, data/users.jsonl, data/topics/*.jsonl, data/hatebu.jsonl
"""
import argparse
import csv
import io
import json
import statistics as st
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone, timedelta
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", line_buffering=True)
sys.path.insert(0, str(Path(__file__).resolve().parent))
import aggregate as ag  # noqa: E402  (topic-side helpers; it re-wraps stdout too, harmless)

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
JST = timezone(timedelta(hours=9))
HIT, SUB = 10, 5
WINDOW = 3
KMAX = 20


def fmt(x, pct=True):
    if x is None:
        return "—"
    return f"{x * 100:.1f}%" if pct else f"{x:.2f}"


def quarter(published_at):
    d = datetime.fromisoformat(published_at.replace("Z", "+00:00")).astimezone(JST)
    return f"{d.year}Q{(d.month - 1) // 3 + 1}"


def load_authors():
    arts = {}
    for line in open(DATA / "author_articles.jsonl", encoding="utf-8"):
        r = json.loads(line)
        if r.get("username") and r.get("id") is not None:
            arts[(r["username"], r["id"])] = r
    by = defaultdict(list)
    for r in arts.values():
        by[r["username"]].append(r)
    authors = {}
    for name, rows in by.items():
        rows.sort(key=lambda r: r["published_at"])
        for k, r in enumerate(rows, 1):
            r["k"] = k
        hits10 = [r["k"] for r in rows if (r.get("liked_count") or 0) >= HIT]
        hits5 = [r["k"] for r in rows if (r.get("liked_count") or 0) >= SUB]
        authors[name] = {
            "name": name, "rows": rows, "n": len(rows), "panel": rows[0].get("panel"),
            "k0": hits10[0] if hits10 else None, "k0_5": hits5[0] if hits5 else None,
            "any_pub": any(r.get("publication") for r in rows),
        }
    done = {}
    if (DATA / "author_done.txt").exists():
        for line in open(DATA / "author_done.txt", encoding="utf-8"):
            p = line.rstrip("\n").split("\t")
            if p[0]:
                done[p[0]] = (int(p[1]) if len(p) > 1 and p[1].isdigit() else 0, int(p[2]) if len(p) > 2 and p[2].isdigit() else 0)
    users = {}
    for line in open(DATA / "users.jsonl", encoding="utf-8"):
        u = json.loads(line)
        users[u["username"]] = u
    return authors, done, users


def hazard(authors, label):
    """Q1a: h(k) = first hit at k / authors with >= k articles and no hit before k. KM cumulative."""
    rows, surv = [], 1.0
    for k in range(1, KMAX + 1):
        at_risk = [a for a in authors if a["n"] >= k and (a["k0"] is None or a["k0"] >= k)]
        events = [a for a in at_risk if a["k0"] == k]
        h = len(events) / len(at_risk) if at_risk else None
        if h is not None:
            surv *= (1 - h)
        rows.append({"group": label, "k": k, "at_risk": len(at_risk), "first_hit": len(events), "h": h, "cum_hit_km": 1 - surv if h is not None else None})
    return rows


def window_rate(rows, lo, hi, thr):
    w = [r for r in rows if lo <= r["k"] <= hi]
    return (sum(1 for r in w if (r.get("liked_count") or 0) >= thr), len(w))


def carryover(authors, thr_after=HIT, stratify=True, pub_filter=None):
    """Q1b (0004): treated = first hit at k0 >= 2 with >= 1 article after; control = no hit in 1..k0, >= k0+1 articles.
    Ratio of after-window R (positions k0+1..k0+3), stratified by the calendar quarter of the k0-th article."""
    treated = [a for a in authors if a["k0"] is not None and a["k0"] >= 2 and a["n"] > a["k0"]]
    if pub_filter is not None:
        treated = [a for a in treated if bool(a["rows"][a["k0"] - 1].get("publication")) == pub_filter]
    # treated after-window hits/counts per (k0, quarter)
    t_cell = defaultdict(lambda: [0, 0])
    for a in treated:
        h, n = window_rate(a["rows"], a["k0"] + 1, a["k0"] + WINDOW, thr_after)
        key = (a["k0"], quarter(a["rows"][a["k0"] - 1]["published_at"]) if stratify else "all")
        t_cell[key][0] += h
        t_cell[key][1] += n
    # control per (k0, quarter): authors with n >= k0+1 and no hit in 1..k0, k0-th article in that quarter
    c_cell = defaultdict(lambda: [0, 0])
    k0s = sorted({k for k, _ in t_cell})
    for a in authors:
        for k0 in k0s:
            if a["n"] < k0 + 1 or (a["k0"] is not None and a["k0"] <= k0):
                continue
            if pub_filter is not None and bool(a["rows"][k0 - 1].get("publication")) != pub_filter:
                continue
            key = (k0, quarter(a["rows"][k0 - 1]["published_at"]) if stratify else "all")
            if key not in t_cell:
                continue
            h, n = window_rate(a["rows"], k0 + 1, k0 + WINDOW, thr_after)
            c_cell[key][0] += h
            c_cell[key][1] += n
    # pooled: weight each cell by treated after-window article count
    num_t = sum(h for h, n in t_cell.values())
    den_t = sum(n for h, n in t_cell.values())
    r_t = num_t / den_t if den_t else None
    wsum, acc = 0, 0.0
    for key, (h, n) in t_cell.items():
        ch, cn = c_cell.get(key, [0, 0])
        if cn:
            acc += n * (ch / cn)
            wsum += n
    r_c = acc / wsum if wsum else None
    ratio = r_t / r_c if (r_t is not None and r_c) else None
    n_c_articles = sum(n for h, n in c_cell.values())
    return {"treated_authors": len(treated), "treated_articles": den_t, "treated_R": r_t, "control_articles": n_c_articles,
            "control_R": r_c, "ratio": ratio, "cells": len(t_cell)}


def placebo(authors):
    """Before-window (k0-3..k0-1) R5 for treated vs control, unstratified (0004 diagnostic)."""
    treated = [a for a in authors if a["k0"] is not None and a["k0"] >= 2 and a["n"] > a["k0"]]
    th = tn = 0
    for a in treated:
        h, n = window_rate(a["rows"], max(1, a["k0"] - WINDOW), a["k0"] - 1, SUB)
        th += h
        tn += n
    ch = cn = 0
    k0s = Counter(a["k0"] for a in treated)
    for a in authors:
        for k0, w in k0s.items():
            if a["n"] < k0 + 1 or (a["k0"] is not None and a["k0"] <= k0):
                continue
            h, n = window_rate(a["rows"], max(1, k0 - WINDOW), k0 - 1, SUB)
            ch += h
            cn += n
    return (th / tn if tn else None, tn, ch / cn if cn else None, cn)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--criteria", action="store_true")
    args = ap.parse_args()
    authors, done, users = load_authors()
    p1_names = [u for u, d in users.items() if d.get("status") == 200]
    out = []

    # ---- A'
    fetched_ok = [n for n in p1_names if n in done and done[n][1] == 200]
    a_fetch = len(fetched_ok) / len(p1_names) if p1_names else 0
    match = mism = 0
    for n in fetched_ok:
        ac = users[n].get("articles_count") or 0
        got = done[n][0]
        if ac == 0:
            continue
        if abs(got - ac) <= 0.02 * ac:
            match += 1
        else:
            mism += 1
    a_match = match / (match + mism) if (match + mism) else 0
    p1 = [authors[n] for n in fetched_ok if n in authors]
    p2 = [a for a in authors.values() if a["panel"] == "p2"]
    treated = [a for a in p1 if a["k0"] is not None and a["k0"] >= 2 and a["n"] > a["k0"]]
    out.append("## 撤退基準の判定\n")
    out.append(f"- A': P1 の記事一覧取得 {len(fetched_ok):,} / {len(p1_names):,} = **{a_fetch * 100:.1f}%**。取得記事数が articles_count の ±2% に収まる著者 {match:,} / {match + mism:,} = **{a_match * 100:.1f}%**（どちらも 95% 以上で通過）")
    out.append(f"- B': Q1b の処置群（k0 ≥ 2 かつ後に 1 本以上）**{len(treated):,} 人**（300 人以上で判定可）")
    out.append(f"- 判定: A' {'通過' if a_fetch >= 0.95 and a_match >= 0.95 else '**抵触**'} / B' {'判定可' if len(treated) >= 300 else '**判定不能**'}")
    out.append(f"- 規模: P1 {len(p1):,} 人 {sum(a['n'] for a in p1):,} 本、P2（直近投稿者）{len(p2):,} 人 {sum(a['n'] for a in p2):,} 本\n")
    if args.criteria:
        print("\n".join(out))
        return

    (ROOT / "docs" / "data").mkdir(parents=True, exist_ok=True)

    # ---- Q1a
    out.append("## Q1a 何本目で当たるか: h(k) と累積（P1）\n")
    ind = [a for a in p1 if not a["any_pub"]]
    pub = [a for a in p1 if a["any_pub"]]
    haz = hazard(p1, "all") + hazard(ind, "individual") + hazard(pub, "publication") + hazard(p2, "p2_latest")
    with open(ROOT / "docs" / "data" / "q1_hazard.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(haz[0].keys()))
        w.writeheader()
        w.writerows(haz)
    out.append("| k | 到達著者 | 初ヒット | h(k) 全体 | 累積（KM） | h(k) 個人 | h(k) Publication | h(k) 直近投稿者 |\n|---|---|---|---|---|---|---|---|")
    hz = {(r["group"], r["k"]): r for r in haz}
    for k in range(1, KMAX + 1):
        r = hz[("all", k)]
        out.append(f"| {k} | {r['at_risk']:,} | {r['first_hit']} | {fmt(r['h'])} | {fmt(r['cum_hit_km'])} | {fmt(hz[('individual', k)]['h'])} | {fmt(hz[('publication', k)]['h'])} | {fmt(hz[('p2_latest', k)]['h'])} |")
    ever = sum(1 for a in p1 if a["k0"] is not None) / len(p1)
    out.append(f"\n- P1 で 1 本でもヒットした著者 **{ever * 100:.1f}%**。初ヒットが 1 本目の著者は全体の {sum(1 for a in p1 if a['k0'] == 1) / len(p1) * 100:.1f}%\n")

    # ---- Q1b
    out.append("## Q1b 持ち越し（0004 の定義）\n")
    main_r = carryover(p1, HIT, True)
    crude = carryover(p1, HIT, False)
    sub = carryover(p1, SUB, True)
    pb = placebo(p1)
    out.append(f"- 主指標（R10、四半期で層別）: 処置群 {fmt(main_r['treated_R'])}（著者 {main_r['treated_authors']:,}、記事 {main_r['treated_articles']:,}）÷ 対照 {fmt(main_r['control_R'])}（記事 {main_r['control_articles']:,}）= **{fmt(main_r['ratio'], False)}** → " + ("**持ち越しあり**" if (main_r["ratio"] or 0) >= 1.5 else "**持ち越しは無い**"))
    out.append(f"- 粗い比（層別なし）: {fmt(crude['treated_R'])} ÷ {fmt(crude['control_R'])} = {fmt(crude['ratio'], False)}")
    out.append(f"- R5: {fmt(sub['treated_R'])} ÷ {fmt(sub['control_R'])} = {fmt(sub['ratio'], False)}")
    out.append(f"- プラセボ（k0 前 3 本の R5）: 処置群 {fmt(pb[0])}（記事 {pb[1]:,}） vs 対照 {fmt(pb[2])}（記事 {pb[3]:,}）\n")
    rows_cv = [dict(kind=k, **v) for k, v in (("R10_stratified", main_r), ("R10_crude", crude), ("R5_stratified", sub))]

    # ---- Q1c
    out.append("## Q1c 個人 vs Publication\n")
    for label, flt in (("個人（k0 の記事が個人）", False), ("Publication（k0 の記事が Publication）", True)):
        r = carryover(p1, HIT, True, pub_filter=flt)
        rows_cv.append(dict(kind=f"R10_stratified_{'pub' if flt else 'ind'}", **r))
        out.append(f"- {label}: 処置群 {fmt(r['treated_R'])}（著者 {r['treated_authors']:,}）÷ 対照 {fmt(r['control_R'])} = **{fmt(r['ratio'], False)}**")
    with open(ROOT / "docs" / "data" / "q1_carryover.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows_cv[0].keys()))
        w.writeheader()
        w.writerows(rows_cv)
    out.append("")

    # ---- Q1d
    out.append("## Q1d 読者の交換レート（P1、取得時点の断面）\n")
    out.append("| フォロワー | 著者数 | フォロワー ÷ 累計いいね の中央値 | 累計いいね 中央値 | 記事数 中央値 |\n|---|---|---|---|---|")
    bins = [("0", 0, 1), ("1-9", 1, 10), ("10-99", 10, 100), ("100-999", 100, 1000), (">=1000", 1000, 10 ** 9)]
    for label, lo, hi in bins:
        g = [users[n] for n in fetched_ok if lo <= (users[n].get("follower_count") or 0) < hi]
        ratios = [(u.get("follower_count") or 0) / (u.get("total_liked_count") or 0) for u in g if (u.get("total_liked_count") or 0) > 0]
        out.append(f"| {label} | {len(g):,} | {st.median(ratios):.3f} | {st.median([u.get('total_liked_count') or 0 for u in g]):.0f} | {st.median([u.get('articles_count') or 0 for u in g]):.0f} |" if g else f"| {label} | 0 | — | — | — |")
    out.append("")

    # ---- Q1e
    out.append("## Q1e 量産: N 本以上書いてヒットが 1 本も無い著者の割合（P1）\n")
    out.append("| N | 著者数 | ヒット無し | 割合 |\n|---|---|---|---|")
    for N in (5, 10, 20, 50):
        g = [a for a in p1 if a["n"] >= N]
        z = [a for a in g if a["k0"] is None]
        out.append(f"| {N} | {len(g):,} | {len(z):,} | {fmt(len(z) / len(g) if g else None)} |")
    out.append("")

    # ---- Q2
    out.append("## Q2 新参のヒットは外から来たか（はてなブックマーク）\n")
    hb = {}
    hp = DATA / "hatebu.jsonl"
    if hp.exists():
        for line in open(hp, encoding="utf-8"):
            r = json.loads(line)
            hb[r["path"]] = r.get("count")
    meta, arts, tusers = ag.load()
    ag.enrich(arts, tusers)
    prof, by_topic = ag.topic_profile(meta, arts)
    targets = sorted(t for t, p in prof.items() if p["target"])
    tg = [r for t in targets for r in by_topic[t]]
    got = sum(1 for r in tg if hb.get(r["path"]) is not None)
    out.append(f"- はてブ件数を取得できた記事 {got:,} / {len(tg):,}（対象 17 トピック）")
    q2rows = []
    out.append("| 層 | 区分 | 記事数 | はてブ 1 件以上 | 3 件以上 |\n|---|---|---|---|---|")
    for label, sel in (("新参（過去平均 <1）", lambda r: r["author_bin"] == "<1"), ("全著者", lambda r: True)):
        res = {}
        for kind, cond in (("ヒット（いいね 10 以上）", lambda r: (r.get("liked_count") or 0) >= HIT), ("非ヒット", lambda r: (r.get("liked_count") or 0) < HIT)):
            g = [r for r in tg if sel(r) and cond(r) and hb.get(r["path"]) is not None]
            s1 = sum(1 for r in g if hb[r["path"]] >= 1) / len(g) if g else None
            s3 = sum(1 for r in g if hb[r["path"]] >= 3) / len(g) if g else None
            res[kind] = (len(g), s1, s3)
            q2rows.append({"stratum": label, "kind": kind, "n": len(g), "hatebu_ge1": s1, "hatebu_ge3": s3})
            out.append(f"| {label} | {kind} | {len(g):,} | {fmt(s1)} | {fmt(s3)} |")
        h, nh = res["ヒット（いいね 10 以上）"], res["非ヒット"]
        ratio = (h[1] / nh[1]) if (h[1] is not None and nh[1]) else None
        out.append(f"| {label} | **比（ヒット ÷ 非ヒット、1 件以上）** | | **{fmt(ratio, False)}** | |")
        if label.startswith("新参"):
            out.append(f"\n- 判定（閾値 3）: " + ("**新参のヒットは外部経路と結びついている**" if (ratio or 0) >= 3 else "**はてブでは説明できない**（X など測れない経路の可能性）") + "\n")
    with open(ROOT / "docs" / "data" / "q2_hatebu.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(q2rows[0].keys()))
        w.writeheader()
        w.writerows(q2rows)

    header = [f"# 第 2 プロジェクトの結果（集計日 {datetime.now(JST).strftime('%Y-%m-%d')}）\n",
              "定義は docs/decisions/0003（Q1b は 0004 で修正）。liked_count・フォロワー数は取得時点の値。著者名は含まない。\n"]
    (ROOT / "docs" / "results_q.md").write_text("\n".join(header + out), encoding="utf-8")
    print("\n".join(header + out))


if __name__ == "__main__":
    main()
