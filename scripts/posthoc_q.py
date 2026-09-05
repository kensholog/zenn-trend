"""Post-hoc reference tables for the second project (NOT pre-registered; verdicts in decisions/0005 are not changed by these).

  python scripts/posthoc_q.py   -> docs/results_q_posthoc.md, docs/data/q_posthoc_*.csv

  PQ1  h(k) restricted to k-th articles published inside a fixed calendar window (removes most of the age effect)
  PQ2  h(1) by calendar quarter of the first article (how much of h(1)=20.8% is age)
  PQ3  Q1b placebo vs after: same-metric (R5) ratio before and after the first hit
"""
import csv
import sys
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import aggregate_q as aq  # noqa: E402

ROOT = aq.ROOT
JST = timezone(timedelta(hours=9))


def hazard_window(authors, lo, hi, kmax=12):
    rows = []
    for k in range(1, kmax + 1):
        at_risk = [a for a in authors if a["n"] >= k and (a["k0"] is None or a["k0"] >= k) and lo <= a["rows"][k - 1]["published_at"][:7] <= hi]
        ev = [a for a in at_risk if a["k0"] == k]
        rows.append({"window": f"{lo}..{hi}", "k": k, "at_risk": len(at_risk), "first_hit": len(ev), "h": len(ev) / len(at_risk) if at_risk else None})
    return rows


def main():
    authors, done, users = aq.load_authors()
    p1_names = [u for u, d in users.items() if d.get("status") == 200]
    p1 = [authors[n] for n in p1_names if n in authors]
    out = [f"# 第 2 プロジェクトの事後の参考表（集計日 {datetime.now(JST).strftime('%Y-%m-%d')}。事前登録外。判定には使わない）\n"]

    out.append("## PQ1 暦を固定した h(k): k 本目の記事が同じ期間に公開された著者だけで計算\n")
    out.append("| k | 2024-01〜2024-12 到達 | h(k) | 2025-01〜2025-12 到達 | h(k) | 2026-01〜2026-08 到達 | h(k) |\n|---|---|---|---|---|---|---|")
    w1 = hazard_window(p1, "2024-01", "2024-12")
    w2 = hazard_window(p1, "2025-01", "2025-12")
    w3 = hazard_window(p1, "2026-01", "2026-08")
    rows = []
    for a, b, c in zip(w1, w2, w3):
        rows += [a, b, c]
        out.append(f"| {a['k']} | {a['at_risk']:,} | {aq.fmt(a['h'])} | {b['at_risk']:,} | {aq.fmt(b['h'])} | {c['at_risk']:,} | {aq.fmt(c['h'])} |")
    with open(ROOT / "docs" / "data" / "q_posthoc_hazard_window.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    out.append("")

    out.append("## PQ2 1 本目の公開四半期ごとの h(1)\n")
    out.append("| 1 本目の公開四半期 | 著者数 | h(1) | 個人 h(1) | Publication h(1) |\n|---|---|---|---|---|")
    byq = defaultdict(list)
    for a in p1:
        byq[aq.quarter(a["rows"][0]["published_at"])].append(a)
    for q in sorted(byq):
        if q < "2023Q1":
            continue
        g = byq[q]
        ind = [a for a in g if not a["rows"][0].get("publication")]
        pub = [a for a in g if a["rows"][0].get("publication")]
        h = sum(1 for a in g if a["k0"] == 1) / len(g)
        hi = sum(1 for a in ind if a["k0"] == 1) / len(ind) if ind else None
        hp = sum(1 for a in pub if a["k0"] == 1) / len(pub) if pub else None
        out.append(f"| {q} | {len(g):,} | {aq.fmt(h)} | {aq.fmt(hi)} | {aq.fmt(hp)} |")
    out.append("")

    out.append("## PQ3 持ち越しのプラセボ比較（同じ R5 で、初ヒット前と後）\n")
    sub_after = aq.carryover(p1, aq.SUB, True)
    pb = aq.placebo(p1)
    before_ratio = (pb[0] / pb[2]) if (pb[0] is not None and pb[2]) else None
    out.append(f"- 初ヒット**前** 3 本の R5: 処置群 {aq.fmt(pb[0])} ÷ 対照 {aq.fmt(pb[2])} = **{aq.fmt(before_ratio, False)}**")
    out.append(f"- 初ヒット**後** 3 本の R5（四半期で層別）: 処置群 {aq.fmt(sub_after['treated_R'])} ÷ 対照 {aq.fmt(sub_after['control_R'])} = **{aq.fmt(sub_after['ratio'], False)}**")
    out.append(f"- 後 ÷ 前 = **{aq.fmt(sub_after['ratio'] / before_ratio if (sub_after['ratio'] and before_ratio) else None, False)}**（1 を超えなければ、ヒットそのものが次の記事を押し上げた証拠は無い）\n")

    text = "\n".join(out)
    (ROOT / "docs" / "results_q_posthoc.md").write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
