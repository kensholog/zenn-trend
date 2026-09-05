"""Figures for article 1, drawn only from the public CSVs in docs/data/ (no raw data needed).

  python scripts/figures.py [out_dir]     default out_dir: ../zenn-content/images/zenn-trend

  fig1_early_vs_late.png   per-topic early/late reach ratio, targets vs. matched control months (B1/B3)
  fig2_quarter_trend.png   reach rate (likes >= 10) by calendar quarter, controls vs. targets (P2)
  fig3_track_record.png    reach rate by author stratum (P4) and for first articles by Publication x followers (P8)
"""
import csv
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "docs" / "data"
OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT.parent / "zenn-content" / "images" / "zenn-trend"
OUT.mkdir(parents=True, exist_ok=True)

plt.rcParams["font.family"] = ["Noto Sans JP", "Meiryo", "BIZ UDPGothic", "MS Gothic", "sans-serif"]
plt.rcParams["axes.unicode_minus"] = False
plt.rcParams["figure.dpi"] = 150
C_TGT, C_CTRL, C_GRAY = "#d9480f", "#1c7ed6", "#868e96"


def read(name):
    with open(DATA / name, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def fl(x):
    return float(x) if x not in ("", None) else None


# ---- fig 1
rows = read("b3_topics.csv")
rows = [r for r in rows if fl(r["tgt_ratio"]) is not None and fl(r["ctrl_ratio"]) is not None]
rows.sort(key=lambda r: fl(r["tgt_ratio"]))
fig, ax = plt.subplots(figsize=(8, 6.2))
y = range(len(rows))
ax.scatter([fl(r["ctrl_ratio"]) for r in rows], y, color=C_CTRL, s=46, zorder=3, label="対照（成熟トピック、同じ暦月）")
ax.scatter([fl(r["tgt_ratio"]) for r in rows], y, color=C_TGT, s=46, zorder=4, label="対象（新興トピック）")
for i, r in enumerate(rows):
    ax.plot([fl(r["ctrl_ratio"]), fl(r["tgt_ratio"])], [i, i], color=C_GRAY, lw=1, zorder=2)
ax.axvline(1.0, color=C_GRAY, lw=0.8, ls=":")
ax.axvline(1.5, color="black", lw=0.9, ls="--")
ax.text(1.52, len(rows) - 0.6, "閾値 1.5", fontsize=9, va="top")
ax.set_yticks(list(y))
ax.set_yticklabels([f"{r['topic']}（誕生 {r['birth']}）" for r in rows], fontsize=9)
ax.set_xlabel("いいね 10 到達率の比: 誕生 0〜2 ヶ月目 ÷ 6〜11 ヶ月目")
ax.set_xscale("log")
ax.set_xticks([0.5, 1, 1.5, 2, 3, 4, 6])
ax.set_xticklabels(["0.5", "1", "1.5", "2", "3", "4", "6"])
ax.set_title("早期の記事は伸びて見えるが、成熟トピックの同じ暦月でも同じだけ伸びて見える\n（対象 17 トピック合算: 1.40、対照: 1.44。集計 2026-09-04）", fontsize=10.5)
ax.legend(loc="lower right", fontsize=9)
ax.grid(axis="x", alpha=0.3)
fig.tight_layout()
fig.savefig(OUT / "fig1_early_vs_late.png")
plt.close(fig)

# ---- fig 2
q = read("posthoc_quarter_rates.csv")
fig, ax = plt.subplots(figsize=(8, 4.4))
xs = [r["quarter"] for r in q]
ax.plot(xs, [fl(r["tgt_R10"]) * 100 for r in q], marker="o", color=C_TGT, label="対象 17 トピック（AI ツール系）")
ax.plot(xs, [fl(r["ctrl_R10"]) * 100 for r in q], marker="o", color=C_CTRL, label="対照 7 トピック（react, python など）")
for r in q:
    ax.annotate(f"{fl(r['tgt_n']):,.0f}", (r["quarter"], fl(r["tgt_R10"]) * 100), textcoords="offset points", xytext=(0, 6), ha="center", fontsize=7, color=C_TGT)
ax.set_ylabel("いいね 10 に届いた記事の割合（%）")
ax.set_xlabel("記事の公開四半期（数字は対象の記事数）")
ax.set_title("公開が新しい記事ほど届いていない。新興・成熟どちらでも同じ形\n（いいね数は 2026-09-04 時点の累計。古い記事ほど溜まっている効果を含む）", fontsize=10.5)
ax.set_ylim(0, 60)
ax.grid(alpha=0.3)
ax.legend(fontsize=9)
plt.setp(ax.get_xticklabels(), rotation=30, ha="right", fontsize=8)
fig.tight_layout()
fig.savefig(OUT / "fig2_quarter_trend.png")
plt.close(fig)

# ---- fig 3
p4 = [r for r in read("posthoc_author_strata.csv") if r["author_bin"] != "unknown"]
p8 = read("posthoc_first_timers.csv")
fig, (a1, a2) = plt.subplots(1, 2, figsize=(10, 4.4), gridspec_kw={"width_ratios": [1, 1.15]})
labels = {"<1": "1 未満", "1-5": "1〜5", "5-20": "5〜20", ">=20": "20 以上"}
xs = [labels[r["author_bin"]] for r in p4]
vals = [fl(r["late_R10"]) * 100 for r in p4]
bars = a1.bar(xs, vals, color=[C_GRAY, C_GRAY, C_TGT, C_TGT])
for b, r in zip(bars, p4):
    a1.text(b.get_x() + b.get_width() / 2, b.get_height() + 1, f"{b.get_height():.0f}%\n(n={int(r['late_n']):,})", ha="center", fontsize=8)
a1.set_xlabel("著者の他の記事の平均いいね（取得時点）")
a1.set_ylabel("いいね 10 に届いた割合（%）")
a1.set_title("「実績」で 9% と 68% の差がつく\n（対象 17 トピック、誕生 6〜11 ヶ月目の記事）", fontsize=10)
a1.set_ylim(0, 85)
a1.grid(axis="y", alpha=0.3)

groups = [("個人", "0", "個人\nフォロワー 0"), ("個人", "1-9", "個人\nフォロワー 1〜9"), ("Publication", "0", "Publication\nフォロワー 0"), ("Publication", "1-9", "Publication\nフォロワー 1〜9")]
xs2, v2, n2 = [], [], []
for pub, fb, label in groups:
    r = next(x for x in p8 if x["publication"] == pub and x["follower_bin"] == fb)
    xs2.append(label)
    v2.append(fl(r["R10"]) * 100)
    n2.append(int(r["n"]))
bars = a2.bar(xs2, v2, color=[C_GRAY, C_GRAY, C_TGT, C_TGT])
for b, n in zip(bars, n2):
    a2.text(b.get_x() + b.get_width() / 2, b.get_height() + 1, f"{b.get_height():.0f}%\n(n={n})", ha="center", fontsize=8)
a2.set_title("初投稿でも、経路と読者があるかで 2% と 35% の差\n（他の記事の平均いいねが 1 未満の著者、記事 1 本目）", fontsize=10)
a2.set_ylim(0, 85)
a2.grid(axis="y", alpha=0.3)
plt.setp(a2.get_xticklabels(), fontsize=8.5)
fig.tight_layout()
fig.savefig(OUT / "fig3_track_record.png")
plt.close(fig)
print("wrote", OUT)
