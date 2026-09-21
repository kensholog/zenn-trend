"""2b: does R10 of the late articles rise on a re-fetch? As registered in docs/decisions/0002 (readings fixed in 0008).

  python scripts/aggregate_2b.py --check    # counts and dates only: panels, match rates, fetch dates (no rate is printed)
  python scripts/aggregate_2b.py            # check + verdict + descriptive tables -> docs/results_2b.md, docs/data/2b_*.csv
  python scripts/aggregate_2b.py --fixture data/2b_fixture/main   # same on synthetic data (scripts/make_2b_fixture.py)

Wave 1 = data/topics/ + data/topics_meta.json (2026-09-04). Wave 2 = data/topics_2026-10/ + data/topics_2026-10_meta.json
(python scripts/fetch_topic_articles.py --out data/topics_2026-10, on or after 2026-10-02).
Guard: refuses to print any rate unless every target and control topic of wave 2 was fetched completely on or after
2026-10-02 JST. Topics, birth months and m come from wave 1 only (aggregate.topic_profile); wave 2 only supplies new counts.
Written on 2026-09-21, before wave 2 exists, and tested on synthetic data only.
"""
import argparse
import csv
import json
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import aggregate as ag  # noqa: E402  (re-wraps stdout as UTF-8; do not wrap again here)

WAVE2_MIN = datetime(2026, 10, 2, 0, 0, tzinfo=ag.JST)
REL_MIN = 0.20          # 0002: relative rise of the late R10 of 20% or more -> "age", otherwise "overall decline"
MATCH_MIN = 0.95        # 0008: the target late panel must be found again in wave 2
AGE_BINS = [("0", 0, 1), ("1-2", 1, 3), ("3-5", 3, 6), ("6-11", 6, 12), ("12-23", 12, 24), (">=24", 24, 10 ** 6)]


def load_wave(root, name):
    meta = json.loads((root / "data" / f"{name}_meta.json").read_text(encoding="utf-8"))
    rows = {}
    for p in sorted((root / "data" / name).glob("*.jsonl")):
        for line in open(p, encoding="utf-8"):
            r = json.loads(line)
            r["topic"], r["month"] = p.stem, ag.month_key(r["published_at"])
            rows[(p.stem, r["id"])] = r
    return meta, rows


def fetched(meta, topics):
    return sorted(datetime.fromisoformat(meta[t]["fetched_at"]) for t in topics if t in meta and meta[t].get("fetched_at"))


def rates(pairs, key="liked_count", thr=10):
    """(n, rate in wave 1, rate in wave 2, relative change) on a fixed panel of (wave-1 row, wave-2 row) pairs."""
    r1, r2 = ag.rate([a for a, _ in pairs], key, thr), ag.rate([b for _, b in pairs], key, thr)
    return len(pairs), r1, r2, (r2 / r1 - 1) if r1 else None


def standardized(ctrl_pairs_by_month, weights, key="liked_count", thr=10):
    """Control rate standardized to the target panel's calendar-month mix, in both waves."""
    num1 = num2 = den = 0.0
    for mk, w in weights.items():
        n, r1, r2, _ = rates(ctrl_pairs_by_month.get(mk, []), key, thr)
        if n:
            num1, num2, den = num1 + w * r1, num2 + w * r2, den + w
    if not den:
        return None, None, None
    return num1 / den, num2 / den, (num2 / num1 - 1) if num1 else None


def fmt(x, kind="pct"):
    if x is None:
        return "—"
    return f"{x * 100:.1f}%" if kind == "pct" else f"{x * 100:+.1f}%" if kind == "rel" else f"{x:.1f}"


def run(root, mode="full"):
    root = Path(root)
    meta1, rows1 = load_wave(root, "topics")
    prof, by_topic = ag.topic_profile(meta1, list(rows1.values()))
    targets = sorted(t for t, p in prof.items() if p["target"])
    controls = [t for t in ag.CONTROL_TOPICS if t in by_topic]
    late1 = [r for t in targets for r in by_topic[t] if r.get("m") in ag.LATE]
    early1 = [r for t in targets for r in by_topic[t] if r.get("m") in ag.EARLY]
    res = {"targets": targets, "late_n": len(late1), "ready": False}
    out = ["## 取得の確認（件数と日付だけ）\n",
           f"- 1 回目: {fetched(meta1, meta1)[0].isoformat(timespec='minutes')} 〜 {fetched(meta1, meta1)[-1].isoformat(timespec='minutes')}。対象 {len(targets)} トピック、後期（m=6〜11）{len(late1):,} 本、早期（m=0〜2）{len(early1):,} 本、対照 {len(controls)} トピック"]
    if not (root / "data" / "topics_2026-10_meta.json").exists():
        out.append("- 2 回目: **未取得**（`python scripts/fetch_topic_articles.py --out data/topics_2026-10` を 2026-10-02 以降に実行する）")
        return res, out
    meta2, rows2 = load_wave(root, "topics_2026-10")
    need = targets + controls
    missing = [t for t in need if t not in meta2 or "last_status" in meta2[t] or not (root / "data" / "topics_2026-10" / f"{t}.done").exists()]
    f1, f2 = fetched(meta1, need), fetched(meta2, need)
    too_early = bool(f2) and f2[0] < WAVE2_MIN
    pairs = lambda rows: [(r, rows2[(r["topic"], r["id"])]) for r in rows if (r["topic"], r["id"]) in rows2]  # noqa: E731
    late, early = pairs(late1), pairs(early1)
    match = len(late) / len(late1) if late1 else None
    days = (f2[len(f2) // 2] - f1[len(f1) // 2]).total_seconds() / 86400 if f1 and f2 else None
    out += [f"- 2 回目: {f2[0].isoformat(timespec='minutes') if f2 else '—'} 〜 {f2[-1].isoformat(timespec='minutes') if f2 else '—'}（1 回目から **{fmt(days, 'num')} 日**）。取得が不完全なトピック: {', '.join(missing) if missing else 'なし'}",
            f"- 対象の後期パネル: 2 回目にも出た記事 {len(late):,} / {len(late1):,} = **{fmt(match)}**（95% 以上で判定可。出なかった記事は削除・非公開・トピックの付け替え）"]
    res.update({"late_matched": len(late), "match": match, "days": days, "missing": missing})
    if missing or too_early or (match or 0) < MATCH_MIN:
        why = "取得が不完全" if missing else "2 回目の取得が 2026-10-02 より前" if too_early else "後期パネルの一致率が 95% 未満"
        out.append(f"\n**{why}なので、率は出さない（decisions/0002・0008）。**")
        return res, out
    res["ready"] = True

    # control rows of the same calendar months, found in both waves
    ctrl_by_month = defaultdict(list)
    for t in controls:
        for r in by_topic[t]:
            if (t, r["id"]) in rows2:
                ctrl_by_month[r["month"]].append((r, rows2[(t, r["id"])]))
    ctrl1_by_month = defaultdict(int)
    for t in controls:
        for r in by_topic[t]:
            ctrl1_by_month[r["month"]] += 1

    def month_weights(panel):
        w = defaultdict(int)
        for a, _ in panel:
            w[a["month"]] += 1
        return w

    w_late = month_weights(late)
    ctrl_union = [p for mk in w_late for p in ctrl_by_month.get(mk, [])]
    ctrl_union1 = sum(ctrl1_by_month[mk] for mk in w_late)
    out.append(f"- 対照（対象の後期と同じ暦月 {min(w_late)}〜{max(w_late)}）: 2 回目にも出た記事 {len(ctrl_union):,} / {ctrl_union1:,} = {fmt(len(ctrl_union) / ctrl_union1 if ctrl_union1 else None)}（対照は 7 トピックとも一覧の上限に達しているので、古い月から押し出される）\n")
    if mode == "check":
        return res, out

    # ---- verdict (0002; readings in 0008)
    n, t1, t2, trel = rates(late)
    c1, c2, crel = standardized(ctrl_by_month, w_late)
    _, u1, u2, urel = rates(ctrl_union)
    res.update({"t1": t1, "t2": t2, "trel": trel, "c1": c1, "c2": c2, "crel": crel, "urel": urel})
    out += ["## 2b の判定: 後期（m=6〜11）の R10 は再取得で上がったか\n",
            "| 群 | 記事数 | R10（1 回目） | R10（2 回目） | 相対変化 |\n|---|---|---|---|---|",
            f"| **対象（{len(targets)} トピックの後期。判定に使う）** | {n:,} | {fmt(t1)} | {fmt(t2)} | **{fmt(trel, 'rel')}** |",
            f"| 対照（対象の暦月構成に標準化） | {len(ctrl_union):,} | {fmt(c1)} | {fmt(c2)} | {fmt(crel, 'rel')} |",
            f"| 対照（同じ暦月の全記事、重みなし） | {len(ctrl_union):,} | {fmt(u1)} | {fmt(u2)} | {fmt(urel, 'rel')} |"]
    if trel is None:
        out.append("\n- 判定: **判定不能**（1 回目の R10 が 0）")
    else:
        age = trel >= REL_MIN
        out.append(f"\n- 判定（対象の相対変化、閾値 +20%）: **{'age 効果が主（古い記事ほどいいねが溜まる）' if age else '全体の反応率低下が主'}**")
        if crel is not None and (crel >= REL_MIN) != age:
            out.append(f"- **対照は逆の側だった**（{fmt(crel, 'rel')}）。判定は変えないが、必ず併記する")
        else:
            out.append(f"- 対照も同じ側（{fmt(crel, 'rel')}）")
    out.append(f"- 取得の間隔は {fmt(days, 'num')} 日。0002 は「2026-10-02 以降（4 週間後）」とだけ定めたので、間隔が長いほど相対変化は大きく出る\n")

    # ---- descriptive only
    out += ["## 記述のみ（判定に使わない）\n", "| パネル | 指標 | 記事数 | 1 回目 | 2 回目 | 相対変化 |\n|---|---|---|---|---|---|"]
    csv_rows = []
    w_early = month_weights(early)
    for label, panel, weights in (("対象・後期", late, w_late), ("対象・早期（m=0〜2）", early, w_early)):
        for name, key, thr in (("R10", "liked_count", 10), ("R5", "liked_count", 5), ("R1", "liked_count", 1), ("BM1", "bookmarked_count", 1)):
            n_, a, b, rel = rates(panel, key, thr)
            ca, cb, crel_ = standardized(ctrl_by_month, weights, key, thr)
            out.append(f"| {label} | {name} | {n_:,} | {fmt(a)} | {fmt(b)} | {fmt(rel, 'rel')} |")
            out.append(f"| 対照（{label}の暦月に標準化） | {name} | — | {fmt(ca)} | {fmt(cb)} | {fmt(crel_, 'rel')} |")
            csv_rows += [{"panel": label, "group": "target", "metric": name, "n": n_, "wave1": a, "wave2": b, "rel_change": rel},
                         {"panel": label, "group": "control_standardized", "metric": name, "n": None, "wave1": ca, "wave2": cb, "rel_change": crel_}]
    up = sum(1 for a, b in late if (a.get("liked_count") or 0) < 10 <= (b.get("liked_count") or 0))
    down = sum(1 for a, b in late if (b.get("liked_count") or 0) < 10 <= (a.get("liked_count") or 0))
    res.update({"up": up, "down": down})
    out.append(f"\n- 対象・後期で いいね 10 を新たに超えた記事 {up} 本、10 を割った記事 {down} 本（R10 を動かしたのはこの差）\n")

    wave1_month = ag.month_index(ag.month_key(fetched(meta1, need)[0].isoformat()))
    out += ["記事の年齢別（1 回目の取得時点での経過月数。対象 = 対象トピックの全記事、対照 = 対照トピックの全記事。2 回とも出た記事だけ）\n",
            "| 群 | 年齢（月） | 記事数 | いいね増分の中央値 | 増分 1 以上の割合 | R10（1 回目） | R10（2 回目） |\n|---|---|---|---|---|---|---|"]
    age_rows = []
    for label, topics in (("対象", targets), ("対照", controls)):
        allp = pairs([r for t in topics for r in by_topic[t]])
        for name, lo, hi in AGE_BINS:
            g = [(a, b) for a, b in allp if lo <= wave1_month - ag.month_index(a["month"]) < hi]
            inc = sorted((b.get("liked_count") or 0) - (a.get("liked_count") or 0) for a, b in g)
            n_, a1, a2, _ = rates(g)
            med = inc[len(inc) // 2] if inc else None
            share = sum(1 for x in inc if x >= 1) / len(inc) if inc else None
            out.append(f"| {label} | {name} | {n_:,} | {med if med is not None else '—'} | {fmt(share)} | {fmt(a1)} | {fmt(a2)} |")
            age_rows.append({"group": label, "age_months": name, "n": n_, "median_increment": med, "share_increment_ge1": share, "R10_wave1": a1, "R10_wave2": a2})
    out.append("")

    fixture = root.resolve() != ag.ROOT.resolve()
    ddir = root / "docs_data" if fixture else ag.ROOT / "docs" / "data"
    ddir.mkdir(parents=True, exist_ok=True)
    for name, rows in (("2b_panels.csv", csv_rows), ("2b_age.csv", age_rows)):
        with open(ddir / name, "w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)
    return res, out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="counts and dates only")
    ap.add_argument("--fixture", help="folder with synthetic data/topics, data/topics_2026-10 and their meta files")
    args = ap.parse_args()
    root = Path(args.fixture) if args.fixture else ag.ROOT
    res, out = run(root, "check" if args.check else "full")
    header = [f"# 2b 再取得の結果{'（合成データ。実データではない）' if args.fixture else ''}\n",
              "定義は docs/decisions/0002 の 2b 節（実装に委ねられた読み方は 0008）。対象トピック・誕生月・m は 1 回目の取得で決めたまま。著者名は含まない。\n"]
    text = "\n".join(header + out)
    print(text)
    if res["ready"] and not args.check:
        (root / "results_2b.md" if args.fixture else ag.ROOT / "docs" / "results_2b.md").write_text(text, encoding="utf-8")
    if not res["ready"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
