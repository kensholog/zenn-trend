"""Aggregate phase-1 data exactly as pre-registered in docs/roadmap.md.

  python scripts/aggregate.py --criteria   # retreat criteria A and B only (run this BEFORE looking at any rate)
  python scripts/aggregate.py              # criteria + B1..B5, writes docs/results.md and docs/data/*.csv

Definitions (frozen 2026-09-04, see docs/roadmap.md):
  birth month  = first calendar month (JST) with >= 10 articles in the topic
  target topic = new-group topic, full history reachable, birth in [2024-01, 2025-08], >= 100 articles,
                 and fewer than 50 articles before the birth month
  m            = months since birth (0-based); early = {0,1,2}; late = {6..11}
  R10/R5/R1    = share of articles with liked_count >= 10 / 5 / 1;  BM1 = share with bookmarked_count >= 1
  author stratum = (total_liked_count - liked_count) / max(articles_count - 1, 1): <1, 1-5, 5-20, >=20
  letters stratum = body_letters_count: <2000, 2000-5999, >=6000
  B1 ratio     = R_early standardized to the late population's (author x letters) stratum mix, divided by R_late
"""
import argparse
import csv
import io
import json
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone, timedelta
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", line_buffering=True)
ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
JST = timezone(timedelta(hours=9))

NEW_TOPICS = [
    "claudecode", "cursor", "dify", "mcp", "codex", "geminicli", "windsurf", "devin", "openclaw", "kiro",
    "cline", "roocode", "claude", "copilot", "githubcopilot", "agentskills", "n8n", "ollama", "langgraph",
    "v0", "bolt", "lovable", "replit", "aider", "openhands", "mastra", "a2a", "vibecoding", "deepseek",
    "gemini", "chatgpt", "openai", "llm", "rag", "aiエージェント", "生成ai", "ai", "antigravity", "codexcli",
]
CONTROL_TOPICS = ["react", "python", "typescript", "nextjs", "aws", "docker", "go"]
EARLY = {0, 1, 2}
LATE = set(range(6, 12))
BIRTH_MIN, BIRTH_MAX = "2024-01", "2025-08"
AUTHOR_BINS = [("<1", lambda x: x < 1), ("1-5", lambda x: 1 <= x < 5), ("5-20", lambda x: 5 <= x < 20), (">=20", lambda x: x >= 20)]
LETTER_BINS = [("<2000", lambda x: x < 2000), ("2000-5999", lambda x: 2000 <= x < 6000), (">=6000", lambda x: x >= 6000)]


def month_key(published_at):
    d = datetime.fromisoformat(published_at.replace("Z", "+00:00")).astimezone(JST)
    return f"{d.year:04d}-{d.month:02d}"


def month_index(key):
    y, m = key.split("-")
    return int(y) * 12 + int(m) - 1


def month_from_index(i):
    return f"{i // 12:04d}-{i % 12 + 1:02d}"


def bin_of(bins, x):
    if x is None:
        return "unknown"
    for name, f in bins:
        if f(x):
            return name
    return "unknown"


def rate(rows, key, thr):
    return (sum(1 for r in rows if (r.get(key) or 0) >= thr) / len(rows)) if rows else None


def spearman(xs, ys):
    n = len(xs)
    if n < 3:
        return None

    def ranks(v):
        order = sorted(range(n), key=lambda i: v[i])
        r = [0.0] * n
        i = 0
        while i < n:
            j = i
            while j + 1 < n and v[order[j + 1]] == v[order[i]]:
                j += 1
            for k in range(i, j + 1):
                r[order[k]] = (i + j) / 2 + 1
            i = j + 1
        return r

    rx, ry = ranks(xs), ranks(ys)
    mx, my = sum(rx) / n, sum(ry) / n
    num = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    den = (sum((a - mx) ** 2 for a in rx) * sum((b - my) ** 2 for b in ry)) ** 0.5
    return num / den if den else None


def load():
    meta = json.loads((DATA / "topics_meta.json").read_text(encoding="utf-8"))
    arts = {}
    for p in sorted((DATA / "topics").glob("*.jsonl")):
        topic = p.stem
        for line in open(p, encoding="utf-8"):
            r = json.loads(line)
            r["month"] = month_key(r["published_at"])
            arts[(topic, r["id"])] = r
    users = {}
    up = DATA / "users.jsonl"
    if up.exists():
        for line in open(up, encoding="utf-8"):
            u = json.loads(line)
            users[u["username"]] = u
    return meta, list(arts.values()), users


def enrich(arts, users):
    for r in arts:
        u = users.get(r.get("username"))
        if u and u.get("status") == 200 and u.get("articles_count"):
            past = ((u.get("total_liked_count") or 0) - (r.get("liked_count") or 0)) / max(u["articles_count"] - 1, 1)
            r["author_avg"] = past
            r["follower_count"] = u.get("follower_count")
        else:
            r["author_avg"] = None
        r["author_bin"] = bin_of(AUTHOR_BINS, r["author_avg"])
        r["letters_bin"] = bin_of(LETTER_BINS, r.get("body_letters_count"))
        r["is_pub"] = bool(r.get("publication"))


def topic_profile(meta, arts):
    by_topic = defaultdict(list)
    for r in arts:
        by_topic[r["topic"]].append(r)
    prof = {}
    for t, rows in by_topic.items():
        months = Counter(r["month"] for r in rows)
        birth = next((mk for mk in sorted(months) if months[mk] >= 10), None)
        pre = sum(v for mk, v in months.items() if birth and mk < birth)
        m = meta.get(t, {})
        prof[t] = {
            "topic": t, "group": "new" if t in NEW_TOPICS else "control", "rows": len(rows),
            "articles_count": m.get("articles"), "capped": m.get("capped"), "birth": birth, "pre_birth": pre,
            "oldest": min(r["month"] for r in rows), "newest": max(r["month"] for r in rows),
        }
        p = prof[t]
        p["target"] = (p["group"] == "new" and p["capped"] is False and birth is not None
                       and BIRTH_MIN <= birth <= BIRTH_MAX and (p["articles_count"] or 0) >= 100 and pre < 50)
        if birth:
            b = month_index(birth)
            for r in rows:
                r["m"] = month_index(r["month"]) - b
    return prof, by_topic


def standardized_ratio(early, late, keyfn):
    """R_early standardized to late's stratum mix, divided by R_late. Returns (ratio, r_early_std, r_late, table)."""
    late_by = defaultdict(list)
    early_by = defaultdict(list)
    for r in late:
        late_by[keyfn(r)].append(r)
    for r in early:
        early_by[keyfn(r)].append(r)
    table, num, den = [], 0.0, 0
    for s in sorted(late_by):
        if s == "unknown" or "unknown" in s:
            continue
        w = len(late_by[s])
        re_ = rate(early_by.get(s, []), "liked_count", standardized_ratio.thr)
        rl = rate(late_by[s], "liked_count", standardized_ratio.thr)
        table.append((s, len(early_by.get(s, [])), re_, w, rl))
        if re_ is not None:
            num += w * re_
            den += w
    r_early_std = num / den if den else None
    known_late = [r for s, rows in late_by.items() if "unknown" not in s for r in rows]
    r_late = rate(known_late, "liked_count", standardized_ratio.thr)
    ratio = (r_early_std / r_late) if (r_early_std is not None and r_late) else None
    return ratio, r_early_std, r_late, table


standardized_ratio.thr = 10


def fmt(x, pct=True):
    if x is None:
        return "—"
    return f"{x * 100:.1f}%" if pct else f"{x:.2f}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--criteria", action="store_true", help="print retreat criteria A/B only")
    args = ap.parse_args()

    meta, arts, users = load()
    enrich(arts, users)
    prof, by_topic = topic_profile(meta, arts)
    targets = sorted(t for t, p in prof.items() if p["target"])
    out = []

    # ---- criteria A
    all_authors = {r["username"] for r in arts if r.get("username")}
    ok_authors = {u for u in all_authors if users.get(u, {}).get("status") == 200}
    a_rate = len(ok_authors) / len(all_authors) if all_authors else 0
    out.append("## 撤退基準の判定\n")
    out.append(f"- A: 対象トピック **{len(targets)} 個**（5 個以上で通過）。著者取得 {len(ok_authors):,} / {len(all_authors):,} = **{a_rate * 100:.1f}%**（95% 以上で通過）")
    out.append(f"  - 対象: {', '.join(targets) if targets else '(なし)'}")
    a_pass = len(targets) >= 5 and a_rate >= 0.95
    # ---- criteria B (counts only)
    tgt = [r for t in targets for r in by_topic[t]]
    early = [r for r in tgt if r.get("m") in EARLY]
    late = [r for r in tgt if r.get("m") in LATE]
    early_new = [r for r in early if r["author_bin"] == "<1"]
    out.append(f"- B: 早期（m=0〜2）の記事 **{len(early):,} 本**（500 本以上で B1 判定可）。うち著者層 <1 は **{len(early_new):,} 本**（100 本以上で B2 判定可）。後期（m=6〜11）は {len(late):,} 本")
    b1_ok, b2_ok = len(early) >= 500, len(early_new) >= 100
    out.append(f"- 判定: A {'通過' if a_pass else '**抵触**'} / B1 {'判定可' if b1_ok else '**判定不能**'} / B2 {'判定可' if b2_ok else '**判定不能**'}\n")

    out.append("## トピックの誕生月と対象判定\n")
    out.append("| topic | 群 | 取得行 | 記事総数 | 上限到達 | 最古 | 誕生月 | 誕生前の本数 | 対象 |")
    out.append("|---|---|---|---|---|---|---|---|---|")
    for t, p in sorted(prof.items(), key=lambda kv: (kv[1]["group"], kv[1]["birth"] or "")):
        out.append(f"| {t} | {p['group']} | {p['rows']:,} | {p['articles_count']} | {'✗' if p['capped'] else '✓' if p['capped'] is False else '?'} | {p['oldest']} | {p['birth']} | {p['pre_birth']} | {'**対象**' if p['target'] else ''} |")
    out.append("")

    if args.criteria:
        print("\n".join(out))
        return

    # ---- B1
    def key_b1(r):
        return f"{r['author_bin']} × {r['letters_bin']}"

    out.append("## B1 先行者利得（全体）\n")
    b1 = {}
    for thr in (10, 5, 1):
        standardized_ratio.thr = thr
        ratio, re_, rl, table = standardized_ratio(early, late, key_b1)
        b1[thr] = (ratio, re_, rl, table)
        out.append(f"- R{thr}: 早期（層別標準化）{fmt(re_)} ÷ 後期 {fmt(rl)} = **{fmt(ratio, False)}**")
    out.append("- 判定（R10、閾値 1.5）: **" + ("先行者利得あり" if (b1[10][0] or 0) >= 1.5 else "先行者利得なし") + "**\n")
    out.append("層別の内訳（R10）:\n\n| 層（著者 × 文字数） | 早期 n | 早期 R10 | 後期 n | 後期 R10 |\n|---|---|---|---|---|")
    for s, ne, re_, nl, rl in b1[10][3]:
        out.append(f"| {s} | {ne} | {fmt(re_)} | {nl} | {fmt(rl)} |")
    out.append("")
    # bookmark variant
    standardized_ratio.thr = 1
    e2 = [dict(r, liked_count=r.get("bookmarked_count")) for r in early]
    l2 = [dict(r, liked_count=r.get("bookmarked_count")) for r in late]
    ratio, re_, rl, _ = standardized_ratio(e2, l2, key_b1)
    out.append(f"- 副指標 BM1: 早期 {fmt(re_)} ÷ 後期 {fmt(rl)} = **{fmt(ratio, False)}**\n")

    # ---- B2
    out.append("## B2 新参への適用（著者層 <1、R5）\n")
    e_new = [r for r in early if r["author_bin"] == "<1"]
    l_new = [r for r in late if r["author_bin"] == "<1"]
    standardized_ratio.thr = 5
    ratio, re_, rl, table = standardized_ratio(e_new, l_new, lambda r: r["letters_bin"])
    out.append(f"- R5: 早期 {fmt(re_)}（n={len(e_new)}） ÷ 後期 {fmt(rl)}（n={len(l_new)}） = **{fmt(ratio, False)}** → " + ("新参にも効く" if (ratio or 0) >= 1.5 else "新参には効かない") + (" （判定不能: 早期 100 本未満）" if not b2_ok else ""))
    for thr in (1, 10):
        standardized_ratio.thr = thr
        r2, a, b, _ = standardized_ratio(e_new, l_new, lambda r: r["letters_bin"])
        out.append(f"- 参考 R{thr}: 早期 {fmt(a)} ÷ 後期 {fmt(b)} = {fmt(r2, False)}")
    out.append("")

    # ---- B3 controls
    out.append("## B3 差の差（対照トピックの同じ暦月）\n")
    ctrl = [r for t in CONTROL_TOPICS for r in by_topic.get(t, [])]
    ctrl_by_month = defaultdict(list)
    for r in ctrl:
        ctrl_by_month[r["month"]].append(r)
    out.append("| 対象 | 誕生月 | 早期の暦月 | 対照 早期 n | 対照 早期 R10 | 対照 後期 n | 対照 後期 R10 | 対照の比 | 対象の比（R10、粗） |\n|---|---|---|---|---|---|---|---|---|")
    num, den = 0.0, 0
    for t in targets:
        b = month_index(prof[t]["birth"])
        ce = [r for m in EARLY for r in ctrl_by_month.get(month_from_index(b + m), [])]
        cl = [r for m in LATE for r in ctrl_by_month.get(month_from_index(b + m), [])]
        rce, rcl = rate(ce, "liked_count", 10), rate(cl, "liked_count", 10)
        cr = (rce / rcl) if (rce is not None and rcl) else None
        te = [r for r in by_topic[t] if r.get("m") in EARLY]
        tl = [r for r in by_topic[t] if r.get("m") in LATE]
        rte, rtl = rate(te, "liked_count", 10), rate(tl, "liked_count", 10)
        tr = (rte / rtl) if (rte is not None and rtl) else None
        if cr is not None:
            num += len(tl) * cr
            den += len(tl)
        out.append(f"| {t} | {prof[t]['birth']} | {month_from_index(b)}〜{month_from_index(b + 2)} | {len(ce)} | {fmt(rce)} | {len(cl)} | {fmt(rcl)} | {fmt(cr, False)} | {fmt(tr, False)} |")
    b3 = num / den if den else None
    did = (b1[10][0] / b3) if (b1[10][0] is not None and b3) else None
    out.append(f"\n- 対照の比（後期本数で加重）: **{fmt(b3, False)}**。B1 ÷ B3 = **{fmt(did, False)}** → " + ("age 効果では説明できない" if (did or 0) >= 1.5 else "**age 効果と区別できない**（必ず明記）") + "\n")

    # ---- B4 / B5 per topic by elapsed month
    out.append("## B4 ピークの位置 / B5 供給と希釈\n")
    out.append("| 対象 | 誕生月 | 観測 m | ピーク m（R10） | ピークの n | Spearman(n, R10) |\n|---|---|---|---|---|---|")
    rows_csv = []
    for t in targets:
        bym = defaultdict(list)
        for r in by_topic[t]:
            if r.get("m") is not None and r["m"] >= 0:
                bym[r["m"]].append(r)
        ms = sorted(bym)
        series = [(m, len(bym[m]), rate(bym[m], "liked_count", 10), rate(bym[m], "liked_count", 5),
                   rate(bym[m], "liked_count", 1), rate(bym[m], "bookmarked_count", 1)) for m in ms]
        for m, n, r10, r5, r1, bm1 in series:
            rows_csv.append({"topic": t, "birth": prof[t]["birth"], "m": m, "month": month_from_index(month_index(prof[t]["birth"]) + m),
                             "n": n, "R10": r10, "R5": r5, "R1": r1, "BM1": bm1})
        w = [(m, n, r10) for m, n, r10, *_ in series if m <= 11]
        peak = max(w, key=lambda x: (x[2] or 0)) if w else None
        rho = spearman([n for _, n, _ in w], [r or 0 for _, _, r in w]) if len(w) >= 3 else None
        out.append(f"| {t} | {prof[t]['birth']} | {len(ms)} | {peak[0] if peak else '—'} | {peak[1] if peak else '—'} | {fmt(rho, False)} |")
    out.append("")

    # ---- write
    (ROOT / "docs" / "data").mkdir(parents=True, exist_ok=True)
    with open(ROOT / "docs" / "data" / "topic_month_rates.csv", "w", encoding="utf-8", newline="") as f:
        wri = csv.DictWriter(f, fieldnames=["topic", "birth", "m", "month", "n", "R10", "R5", "R1", "BM1"])
        wri.writeheader()
        wri.writerows(rows_csv)
    header = [f"# 結果（集計日 {datetime.now(JST).strftime('%Y-%m-%d')}）\n",
              "定義は docs/roadmap.md（凍結）。B1 の「層別して合算した比」は、早期の到達率を後期の層構成（著者層 × 文字数層）で直接標準化し、後期の到達率で割ったもの。著者の実績は取得時点の値（未来の実績が混ざる）。liked_count は取得時点の累計。\n"]
    (ROOT / "docs" / "results.md").write_text("\n".join(header + out), encoding="utf-8")
    print("\n".join(header + out))


if __name__ == "__main__":
    main()
