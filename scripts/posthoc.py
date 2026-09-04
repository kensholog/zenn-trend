"""Post-hoc reference tables (NOT pre-registered; never used to change the B1/B2/B3 verdicts).

  python scripts/posthoc.py   -> prints markdown, writes docs/results_posthoc.md and docs/data/posthoc_*.csv

  P1  control topics, author stratum <1, R5 early/late over the same calendar windows as each target (compare with B2)
  P2  R10 / R5 by calendar quarter, controls vs targets (secular trend that B3 captures)
  P3  targets pooled by elapsed month m (all authors, and <1 stratum)
  P4  R10 by author stratum, early vs late, targets pooled (reads off the B1 stratum table)
"""
import csv
import io
import sys
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import aggregate as ag  # noqa: E402

# stdout is already re-wrapped as UTF-8 by the aggregate import; wrapping again would close the buffer.
ROOT = ag.ROOT
JST = timezone(timedelta(hours=9))


def q(month):
    y, m = month.split("-")
    return f"{y}Q{(int(m) - 1) // 3 + 1}"


def main():
    meta, arts, users = ag.load()
    ag.enrich(arts, users)
    prof, by_topic = ag.topic_profile(meta, arts)
    targets = sorted(t for t, p in prof.items() if p["target"])
    ctrl = [r for t in ag.CONTROL_TOPICS for r in by_topic.get(t, [])]
    ctrl_by_month = defaultdict(list)
    for r in ctrl:
        ctrl_by_month[r["month"]].append(r)
    out = ["# 事後の参考表（事前登録外。B1〜B3 の判定には使わない）\n",
           f"集計日 {datetime.now(JST).strftime('%Y-%m-%d')}。定義は docs/roadmap.md と同じ。\n"]

    # P1: control newcomers over target windows
    out.append("## P1 対照トピックの新参層（著者過去平均 <1）: 同じ暦月での R5 早期 ÷ 後期\n")
    out.append("| 対象 | 対照 <1 早期 n | 早期 R5 | 対照 <1 後期 n | 後期 R5 | 対照の比 | 対象 <1 早期 n | 対象 <1 R5 早期 | 対象 <1 後期 n | 対象 <1 R5 後期 | 対象の比 |\n|---|---|---|---|---|---|---|---|---|---|---|")
    num = den = 0.0
    for t in targets:
        b = ag.month_index(prof[t]["birth"])
        ce = [r for m in ag.EARLY for r in ctrl_by_month.get(ag.month_from_index(b + m), []) if r["author_bin"] == "<1"]
        cl = [r for m in ag.LATE for r in ctrl_by_month.get(ag.month_from_index(b + m), []) if r["author_bin"] == "<1"]
        te = [r for r in by_topic[t] if r.get("m") in ag.EARLY and r["author_bin"] == "<1"]
        tl = [r for r in by_topic[t] if r.get("m") in ag.LATE and r["author_bin"] == "<1"]
        rce, rcl = ag.rate(ce, "liked_count", 5), ag.rate(cl, "liked_count", 5)
        rte, rtl = ag.rate(te, "liked_count", 5), ag.rate(tl, "liked_count", 5)
        cr = rce / rcl if (rce is not None and rcl) else None
        tr = rte / rtl if (rte is not None and rtl) else None
        if cr is not None:
            num += len(tl) * cr
            den += len(tl)
        out.append(f"| {t} | {len(ce)} | {ag.fmt(rce)} | {len(cl)} | {ag.fmt(rcl)} | {ag.fmt(cr, False)} | {len(te)} | {ag.fmt(rte)} | {len(tl)} | {ag.fmt(rtl)} | {ag.fmt(tr, False)} |")
    p1 = num / den if den else None
    out.append(f"\n- 対照の新参層の比（対象の <1 後期本数で加重）: **{ag.fmt(p1, False)}**（B2 の 1.91 と比べる）\n")

    # P2: secular trend by quarter
    out.append("## P2 暦四半期ごとの到達率（対照 7 トピック vs 対象 17 トピック）\n")
    out.append("| 四半期 | 対照 n | 対照 R10 | 対照 R5 | 対照 <1 n | 対照 <1 R5 | 対象 n | 対象 R10 | 対象 R5 |\n|---|---|---|---|---|---|---|---|---|")
    tg = [r for t in targets for r in by_topic[t]]
    cq, tq = defaultdict(list), defaultdict(list)
    for r in ctrl:
        cq[q(r["month"])].append(r)
    for r in tg:
        tq[q(r["month"])].append(r)
    rows = []
    for k in sorted(set(cq) | set(tq)):
        if k < "2024Q1":
            continue
        c, t_ = cq.get(k, []), tq.get(k, [])
        c1 = [r for r in c if r["author_bin"] == "<1"]
        row = {"quarter": k, "ctrl_n": len(c), "ctrl_R10": ag.rate(c, "liked_count", 10), "ctrl_R5": ag.rate(c, "liked_count", 5),
               "ctrl_new_n": len(c1), "ctrl_new_R5": ag.rate(c1, "liked_count", 5),
               "tgt_n": len(t_), "tgt_R10": ag.rate(t_, "liked_count", 10), "tgt_R5": ag.rate(t_, "liked_count", 5)}
        rows.append(row)
        out.append(f"| {k} | {len(c)} | {ag.fmt(row['ctrl_R10'])} | {ag.fmt(row['ctrl_R5'])} | {len(c1)} | {ag.fmt(row['ctrl_new_R5'])} | {len(t_)} | {ag.fmt(row['tgt_R10'])} | {ag.fmt(row['tgt_R5'])} |")
    with open(ROOT / "docs" / "data" / "posthoc_quarter_rates.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    out.append("")

    # P3: pooled by m
    out.append("## P3 対象 17 トピック合算、誕生からの経過月 m ごと\n")
    out.append("| m | n | R10 | R5 | R1 | BM1 | <1 n | <1 R5 | <1 R10 |\n|---|---|---|---|---|---|---|---|---|")
    bym = defaultdict(list)
    for r in tg:
        if r.get("m") is not None and 0 <= r["m"] <= 17:
            bym[r["m"]].append(r)
    rows = []
    for m in sorted(bym):
        rs = bym[m]
        n1 = [r for r in rs if r["author_bin"] == "<1"]
        row = {"m": m, "n": len(rs), "R10": ag.rate(rs, "liked_count", 10), "R5": ag.rate(rs, "liked_count", 5),
               "R1": ag.rate(rs, "liked_count", 1), "BM1": ag.rate(rs, "bookmarked_count", 1),
               "new_n": len(n1), "new_R5": ag.rate(n1, "liked_count", 5), "new_R10": ag.rate(n1, "liked_count", 10)}
        rows.append(row)
        out.append(f"| {m} | {len(rs)} | {ag.fmt(row['R10'])} | {ag.fmt(row['R5'])} | {ag.fmt(row['R1'])} | {ag.fmt(row['BM1'])} | {len(n1)} | {ag.fmt(row['new_R5'])} | {ag.fmt(row['new_R10'])} |")
    with open(ROOT / "docs" / "data" / "posthoc_pooled_by_m.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    out.append("")

    # P4: by author stratum
    out.append("## P4 著者層ごとの到達率（対象合算、早期 vs 後期、全文字数）\n")
    out.append("| 著者層 | 早期 n | 早期 R10 | 早期 R5 | 後期 n | 後期 R10 | 後期 R5 | Publication 率（後期） |\n|---|---|---|---|---|---|---|---|")
    early = [r for r in tg if r.get("m") in ag.EARLY]
    late = [r for r in tg if r.get("m") in ag.LATE]
    for name, _ in ag.AUTHOR_BINS + [("unknown", None)]:
        e = [r for r in early if r["author_bin"] == name]
        l_ = [r for r in late if r["author_bin"] == name]
        if not e and not l_:
            continue
        pub = (sum(1 for r in l_ if r["is_pub"]) / len(l_)) if l_ else None
        out.append(f"| {name} | {len(e)} | {ag.fmt(ag.rate(e, 'liked_count', 10))} | {ag.fmt(ag.rate(e, 'liked_count', 5))} | {len(l_)} | {ag.fmt(ag.rate(l_, 'liked_count', 10))} | {ag.fmt(ag.rate(l_, 'liked_count', 5))} | {ag.fmt(pub)} |")
    out.append("")

    # P5: what "実績" stands for — follower count vs past-average-like, late period, targets pooled
    out.append("## P5 「実績」の中身: フォロワー数 × 過去平均いいね（対象合算、後期 m=6〜11、R10）\n")
    FOLLOWER_BINS = [("0", lambda x: x == 0), ("1-9", lambda x: 1 <= x < 10), ("10-99", lambda x: 10 <= x < 100),
                     ("100-999", lambda x: 100 <= x < 1000), (">=1000", lambda x: x >= 1000)]
    for r in late:
        r["follower_bin"] = bin_of_f(FOLLOWER_BINS, r.get("follower_count"))
    cols = [n for n, _ in ag.AUTHOR_BINS]
    out.append("| フォロワー数 \\ 過去平均いいね | " + " | ".join(cols) + " | 行計 |\n|---|" + "---|" * (len(cols) + 1))
    for fb, _ in FOLLOWER_BINS:
        row = [r for r in late if r["follower_bin"] == fb]
        cells = []
        for ab in cols:
            c = [r for r in row if r["author_bin"] == ab]
            cells.append(f"{ag.fmt(ag.rate(c, 'liked_count', 10))} (n={len(c)})" if c else "—")
        out.append(f"| {fb} | " + " | ".join(cells) + f" | {ag.fmt(ag.rate(row, 'liked_count', 10))} (n={len(row)}) |")
    out.append("")

    # P6: Publication vs individual within author stratum, late period
    out.append("## P6 Publication 所属 × 過去平均いいね（対象合算、後期、R10）\n")
    out.append("| 過去平均いいね | 個人 n | 個人 R10 | Publication n | Publication R10 |\n|---|---|---|---|---|")
    for ab in cols:
        ind = [r for r in late if r["author_bin"] == ab and not r["is_pub"]]
        pub = [r for r in late if r["author_bin"] == ab and r["is_pub"]]
        out.append(f"| {ab} | {len(ind)} | {ag.fmt(ag.rate(ind, 'liked_count', 10))} | {len(pub)} | {ag.fmt(ag.rate(pub, 'liked_count', 10))} |")
    out.append("")

    # P7: first-timers (articles_count == 1 at fetch) among newcomers, late period
    out.append("## P7 新参層の内訳: 取得時点の記事数（対象合算、後期、<1 層）\n")
    out.append("| 取得時点の記事数 | n | R10 | R5 | R1 |\n|---|---|---|---|---|")
    new_late = [r for r in late if r["author_bin"] == "<1"]
    ARTICLE_BINS = [("1", lambda x: x == 1), ("2-4", lambda x: 2 <= x < 5), ("5-19", lambda x: 5 <= x < 20), (">=20", lambda x: x >= 20)]
    for nb, f in ARTICLE_BINS:
        c = [r for r in new_late if r.get("articles_count") is not None and f(r["articles_count"])]
        out.append(f"| {nb} | {len(c)} | {ag.fmt(ag.rate(c, 'liked_count', 10))} | {ag.fmt(ag.rate(c, 'liked_count', 5))} | {ag.fmt(ag.rate(c, 'liked_count', 1))} |")
    out.append("")

    # P8: first-timers (articles_count == 1) by Publication x follower count, late period
    out.append("## P8 初投稿（取得時点の記事数 1）の内訳: Publication × フォロワー数（対象合算、後期、R10 / R5）\n")
    out.append("| 所属 | フォロワー 0 | フォロワー 1〜9 | フォロワー 10 以上 |\n|---|---|---|---|")
    ft = [r for r in new_late if r.get("articles_count") == 1]
    for pub, label in ((False, "個人"), (True, "Publication")):
        cells = []
        for fb, f in (("0", lambda x: x == 0), ("1-9", lambda x: 1 <= x < 10), (">=10", lambda x: x >= 10)):
            c = [r for r in ft if r["is_pub"] == pub and r.get("follower_count") is not None and f(r["follower_count"])]
            cells.append(f"{ag.fmt(ag.rate(c, 'liked_count', 10))} / {ag.fmt(ag.rate(c, 'liked_count', 5))} (n={len(c)})" if c else "—")
        out.append(f"| {label} | " + " | ".join(cells) + " |")
    out.append("")

    text = "\n".join(out)
    (ROOT / "docs" / "results_posthoc.md").write_text(text, encoding="utf-8")
    print(text)


def bin_of_f(bins, x):
    if x is None:
        return "unknown"
    for name, f in bins:
        if f(x):
            return name
    return "unknown"


if __name__ == "__main__":
    main()
