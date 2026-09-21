"""Synthetic two-wave topic listings with known answers, to test aggregate_2b.py before wave 2 exists (decisions/0008).

  python scripts/make_2b_fixture.py     # writes data/2b_fixture/<scenario>/ and checks aggregate_2b against the known answers

Scenarios: main (target +48.9% -> age; control +16.7% -> the "other side" line; deletions, an unlike, cap push-out),
           weighted (the control rises more in the later months, so the month-standardized figure differs from the plain one),
           flat (no change -> overall decline), too_early / incomplete / low_match (the guard must refuse), no_wave2.
Everything is invented. Expected values come from the generator's own bookkeeping with the late months written out by
hand, not from aggregate.topic_profile.
"""
import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import aggregate_2b as a2  # noqa: E402  (stdout is already UTF-8 via aggregate)

BASE = a2.ag.ROOT / "data" / "2b_fixture"
L12 = [0, 2, 4, 6, 8, 9, 9, 12, 15, 20, 30, 50]
L20 = [0, 1, 3, 5, 7, 9, 9, 11, 14, 25, 0, 1, 3, 5, 7, 8, 8, 11, 14, 25]
# topic: (first month, months, per month, capped, pattern)
TOPICS = {"mcp": ("2025-01", 20, 12, False, L12), "dify": ("2024-06", 27, 10, False, L12), "cursor": ("2025-01", 6, 10, True, L12),
          "react": ("2024-01", 32, 20, True, L20), "python": ("2024-01", 32, 20, True, L20)}
LATE = {"mcp": ["2025-07", "2025-08", "2025-09", "2025-10", "2025-11", "2025-12"],     # birth 2025-01, m = 6..11
        "dify": ["2024-12", "2025-01", "2025-02", "2025-03", "2025-04", "2025-05"]}    # birth 2024-06, m = 6..11
DELETED = {("mcp", "2025-07", 0), ("mcp", "2025-08", 7)}     # gone in wave 2: one miss, one hit
UNLIKED = {("dify", "2025-01", 7): 8}                        # 12 -> 8
PUSHED_OUT = ("react", "2024-12")                            # a capped control topic loses its oldest month


def months(first, n):
    i = a2.ag.month_index(first)
    return [a2.ag.month_from_index(i + k) for k in range(n)]


def build(scenario):
    out = BASE / scenario
    if out.exists():
        shutil.rmtree(out)
    w1, w2 = out / "data" / "topics", out / "data" / "topics_2026-10"
    w1.mkdir(parents=True)
    book, meta1, meta2, next_id = [], {}, {}, 1
    for topic, (first, n, per, capped, pat) in TOPICS.items():
        rows = []
        for mk in months(first, n):
            for k in range(per):
                likes1 = pat[k % len(pat)]
                likes2 = likes1
                if scenario in ("main", "weighted", "too_early", "incomplete", "low_match"):
                    if topic in LATE or topic == "cursor":
                        likes2 = likes1 + 1 if likes1 == 9 else likes1
                    elif k == 5 or (scenario == "weighted" and k == 6 and mk >= "2025-07"):
                        likes2 = likes1 + 1
                    likes2 = UNLIKED.get((topic, mk, k), likes2)
                gone = scenario != "flat" and ((topic, mk, k) in DELETED or (topic, mk) == PUSHED_OUT)
                if scenario == "low_match" and topic in LATE and mk in LATE[topic] and k == 1:
                    gone = True
                rows.append({"id": next_id, "topic": topic, "month": mk, "k": k, "likes1": likes1, "likes2": likes2, "gone": gone})
                next_id += 1
        book += rows
        meta1[topic] = {"page_status": 200, "articles": len(rows), "capped": capped, "rows": len(rows), "fetched_at": "2026-09-04T12:30:00+09:00"}
        meta2[topic] = dict(meta1[topic], fetched_at="2026-09-25T10:00:00+09:00" if scenario == "too_early" else "2026-10-03T10:00:00+09:00")

        def line(r, likes):
            return json.dumps({"id": r["id"], "slug": f"s{r['id']}", "path": f"/u{r['id']}/articles/s{r['id']}", "title": "x",
                               "published_at": f"{r['month']}-15T12:00:00.000+09:00", "liked_count": likes, "bookmarked_count": likes // 2,
                               "comments_count": 0, "body_letters_count": 3000, "username": f"u{r['id']}", "publication": None, "topic": r["topic"]}) + "\n"

        with open(w1 / f"{topic}.jsonl", "w", encoding="utf-8") as f:
            f.writelines(line(r, r["likes1"]) for r in rows)
        if scenario != "no_wave2":
            w2.mkdir(parents=True, exist_ok=True)
            with open(w2 / f"{topic}.jsonl", "w", encoding="utf-8") as f:
                f.writelines(line(r, r["likes2"]) for r in rows if not r["gone"])
                for k in range(5):   # articles published after wave 1: never part of a panel
                    f.write(line({"id": next_id, "month": "2026-09", "topic": topic}, 3))
                    next_id += 1
            (w2 / f"{topic}.done").write_text("x", encoding="utf-8")
    if scenario == "incomplete":
        meta2["dify"]["last_status"] = 500
    (out / "data" / "topics_meta.json").write_text(json.dumps(meta1), encoding="utf-8")
    if scenario != "no_wave2":
        (out / "data" / "topics_2026-10_meta.json").write_text(json.dumps(meta2), encoding="utf-8")
    return out, book


def expected(book):
    late = [r for r in book if r["topic"] in LATE and r["month"] in LATE[r["topic"]]]
    kept = [r for r in late if not r["gone"]]
    h1, h2 = sum(r["likes1"] >= 10 for r in kept), sum(r["likes2"] >= 10 for r in kept)
    months_late = {r["month"] for r in kept}
    ctrl = [r for r in book if r["topic"] in ("react", "python") and r["month"] in months_late]
    ckept = [r for r in ctrl if not r["gone"]]
    c1, c2 = sum(r["likes1"] >= 10 for r in ckept) / len(ckept), sum(r["likes2"] >= 10 for r in ckept) / len(ckept)
    s1 = s2 = 0.0   # control standardized to the kept target panel's month mix, written out by hand
    for mk in months_late:
        w = sum(1 for r in kept if r["month"] == mk)
        cm = [r for r in ckept if r["month"] == mk]
        s1 += w * sum(r["likes1"] >= 10 for r in cm) / len(cm)
        s2 += w * sum(r["likes2"] >= 10 for r in cm) / len(cm)
    return {"late_n": len(late), "late_matched": len(kept), "t1": h1 / len(kept), "t2": h2 / len(kept), "trel": h2 / h1 - 1,
            "urel": c2 / c1 - 1, "crel": s2 / s1 - 1, "ctrl_union": len(ckept), "ctrl_union1": len(ctrl),
            "up": sum(r["likes1"] < 10 <= r["likes2"] for r in kept), "down": sum(r["likes2"] < 10 <= r["likes1"] for r in kept)}


def check(name, got, want):
    ok = got == want or (isinstance(want, float) and got is not None and abs(got - want) < 1e-9)
    print(f"  {'ok ' if ok else 'NG '} {name}: got {got} / expected {want}")
    return ok


def main():
    results = []
    for scenario in ("main", "weighted", "flat", "too_early", "incomplete", "low_match", "no_wave2"):
        out, book = build(scenario)
        res, lines = a2.run(out, "full")
        text = "\n".join(lines)
        print(f"=== {scenario}")
        e = expected(book)
        results += [check("targets", res["targets"], ["dify", "mcp"]), check("late panel (wave 1)", res["late_n"], e["late_n"])]
        if scenario in ("main", "weighted", "flat"):
            (out / "results_2b.md").write_text(text, encoding="utf-8")
            results += [check("ready", res["ready"], True), check("late panel found again", res["late_matched"], e["late_matched"]),
                        check("target R10 wave 1", res["t1"], e["t1"]), check("target R10 wave 2", res["t2"], e["t2"]),
                        check("target relative change", res["trel"], e["trel"]), check("control union relative change", res["urel"], e["urel"]),
                        check("control standardized to the target month mix", res["crel"], e["crel"]),
                        check("standardized differs from plain only in 'weighted'", abs(e["crel"] - e["urel"]) > 1e-6, scenario == "weighted"),
                        check("crossed 10 upward / downward", (res["up"], res["down"]), (e["up"], e["down"])),
                        check("control counts in the report", f"{e['ctrl_union']:,} / {e['ctrl_union1']:,}" in text, True),
                        check("days between waves", round(res["days"], 2), 28.9)]
            verdict = "age 効果が主" if e["trel"] >= 0.20 else "全体の反応率低下が主"
            results += [check(f"verdict '{verdict}'", f"**{verdict}" in text, True),
                        check("other-side line", "対照は逆の側だった" in text, scenario == "main")]
        else:
            results += [check("not ready (guard)", res["ready"], False), check("no rate keys", [k for k in res if k in ("t1", "trel", "crel")], []),
                        check("no verdict section", "2b の判定" in text, False)]
    print("ALL OK" if all(results) else "FAILED")
    sys.exit(0 if all(results) else 1)


if __name__ == "__main__":
    main()
