"""Figures for article 2 (second project), drawn only from the public CSVs in docs/data/.

  python scripts/figures_q.py [out_dir]     default: ../zenn-content/images/zenn-trend

  q_fig1_hazard.png        h(k): first-hit probability at the k-th article (all / individual / Publication, plus 2025-only)
  q_fig2_carryover.png     before vs after the first hit: treated vs control (R5), and R10 after
  q_fig3_hatebu.png        Hatena Bookmark share: newcomers' hits vs non-hits, all authors
  q_fig4_h1_by_quarter.png h(1) of the first article by quarter, individual vs Publication
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
C_ALL, C_IND, C_PUB, C_GRAY, C_TGT = "#212529", "#1c7ed6", "#d9480f", "#868e96", "#d9480f"


def read(name):
    with open(DATA / name, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def fl(x):
    return float(x) if x not in ("", None) else None


# ---- fig 1: hazard
hz = read("q1_hazard.csv")
win = read("q_posthoc_hazard_window.csv")
fig, ax = plt.subplots(figsize=(8, 4.6))
for grp, color, label, ls in (("all", C_ALL, "全体（17,942 人）", "-"), ("individual", C_IND, "個人（Publication の記事が無い著者）", "-"), ("publication", C_PUB, "Publication の記事がある著者", "-")):
    rows = [r for r in hz if r["group"] == grp and int(r["k"]) <= 15]
    ax.plot([int(r["k"]) for r in rows], [fl(r["h"]) * 100 for r in rows], marker="o", color=color, label=label, ls=ls)
rows = [r for r in win if r["window"] == "2025-01..2025-12" and int(r["k"]) <= 12]
ax.plot([int(r["k"]) for r in rows], [fl(r["h"]) * 100 for r in rows], marker="s", color=C_GRAY, ls="--", label="全体、2025 年に公開された k 本目だけ（暦の効果を除く）")
ax.set_xlabel("その著者の何本目の記事か（k）")
ax.set_ylabel("k 本目で初めていいね 10 に届く確率 h(k)（%）")
ax.set_title("初めて当たるのは 1 本目が一番多く、本数を重ねるほど確率は下がる\n（それまで当たっていない著者のうち、k 本目で当たった割合。取得 2026-09-05）", fontsize=10.5)
ax.set_xticks(range(1, 16))
ax.set_ylim(0, 45)
ax.grid(alpha=0.3)
ax.legend(fontsize=8.5)
fig.tight_layout()
fig.savefig(OUT / "q_fig1_hazard.png")
plt.close(fig)

# ---- fig 2: carryover placebo
pb = read("q_posthoc_placebo.csv")
before = next(r for r in pb if r["window"].startswith("before"))
after5 = next(r for r in pb if r["window"].startswith("after") and r["metric"] == "R5")
after10 = next(r for r in pb if r["window"].startswith("after") and r["metric"] == "R10")
fig, ax = plt.subplots(figsize=(8, 4.6))
labels = ["初ヒットの前 3 本\n（いいね 5 以上）", "初ヒットの後 3 本\n（いいね 5 以上）", "初ヒットの後 3 本\n（いいね 10 以上）"]
t_vals = [fl(before["treated_R"]) * 100, fl(after5["treated_R"]) * 100, fl(after10["treated_R"]) * 100]
c_vals = [fl(before["control_R"]) * 100, fl(after5["control_R"]) * 100, fl(after10["control_R"]) * 100]
ratios = [fl(before["ratio"]), fl(after5["ratio"]), fl(after10["ratio"])]
x = range(3)
w = 0.36
b1 = ax.bar([i - w / 2 for i in x], t_vals, w, color=C_TGT, label="当たった著者（初ヒットが 2 本目以降の 3,260 人）")
b2 = ax.bar([i + w / 2 for i in x], c_vals, w, color=C_GRAY, label="同じ本数までまだ当たっていない著者")
for i in x:
    ax.text(i - w / 2, t_vals[i] + 1, f"{t_vals[i]:.0f}%", ha="center", fontsize=9)
    ax.text(i + w / 2, c_vals[i] + 1, f"{c_vals[i]:.0f}%", ha="center", fontsize=9)
    ax.text(i, max(t_vals[i], c_vals[i]) + 7, f"比 {ratios[i]:.2f}", ha="center", fontsize=10, fontweight="bold")
ax.set_xticks(list(x))
ax.set_xticklabels(labels, fontsize=9)
ax.set_ylabel("届いた記事の割合（%）")
ax.set_ylim(0, 60)
ax.set_title("当たった著者はその後も届きやすい。ただし当たる前から同じだけ差があった\n（後の比 2.41 ÷ 前の比 3.64 = 0.66。ヒットが次を押し上げた証拠は無い）", fontsize=10.5)
ax.grid(axis="y", alpha=0.3)
ax.legend(fontsize=8.5, loc="upper left")
fig.tight_layout()
fig.savefig(OUT / "q_fig2_carryover.png")
plt.close(fig)

# ---- fig 3: hatebu
q2 = read("q2_hatebu.csv")
fig, ax = plt.subplots(figsize=(8, 4.2))
cats = [("新参（過去平均 <1）", "ヒット（いいね 10 以上）", "新参の\n届いた記事"), ("新参（過去平均 <1）", "非ヒット", "新参の\n届かなかった記事"), ("全著者", "ヒット（いいね 10 以上）", "全著者の\n届いた記事"), ("全著者", "非ヒット", "全著者の\n届かなかった記事")]
v1, v3, ns, xl = [], [], [], []
for s, k, label in cats:
    r = next(x for x in q2 if x["stratum"] == s and x["kind"] == k)
    v1.append(fl(r["hatebu_ge1"]) * 100)
    v3.append(fl(r["hatebu_ge3"]) * 100)
    ns.append(int(r["n"]))
    xl.append(label)
x = range(4)
ax.bar([i - 0.2 for i in x], v1, 0.4, color=C_TGT, label="はてブ 1 件以上")
ax.bar([i + 0.2 for i in x], v3, 0.4, color=C_GRAY, label="はてブ 3 件以上")
for i in x:
    ax.text(i - 0.2, v1[i] + 1.5, f"{v1[i]:.0f}%", ha="center", fontsize=9)
    ax.text(i + 0.2, v3[i] + 1.5, f"{v3[i]:.0f}%", ha="center", fontsize=9)
ax.set_xticks(list(x))
ax.set_xticklabels([f"{l}\n(n={n:,})" for l, n in zip(xl, ns)], fontsize=9)
ax.set_ylabel("はてなブックマークが付いた割合（%）")
ax.set_ylim(0, 95)
ax.set_title("新参の記事が届いたとき、6 割にははてブが付いていた（届かなかった記事は 5%）\n（対象 17 トピック 16,092 本。はてブ件数は 2026-09-05 取得）", fontsize=10.5)
ax.grid(axis="y", alpha=0.3)
ax.legend(fontsize=9)
fig.tight_layout()
fig.savefig(OUT / "q_fig3_hatebu.png")
plt.close(fig)

# ---- fig 4: h(1) by quarter
h1 = [r for r in read("q_posthoc_h1_by_quarter.csv") if r["quarter"] >= "2023Q1"]
fig, ax = plt.subplots(figsize=(8, 4.2))
xs = [r["quarter"] for r in h1]
ax.plot(xs, [fl(r["h1_ind"]) * 100 for r in h1], marker="o", color=C_IND, label="個人の 1 本目")
ax.plot(xs, [fl(r["h1_pub"]) * 100 for r in h1], marker="o", color=C_PUB, label="Publication から出た 1 本目")
for r in h1:
    ax.annotate(f"{int(r['n_ind']):,}", (r["quarter"], fl(r["h1_ind"]) * 100), textcoords="offset points", xytext=(0, -12), ha="center", fontsize=7, color=C_IND)
ax.set_ylabel("1 本目がいいね 10 に届いた割合（%）")
ax.set_xlabel("1 本目の公開四半期（数字は個人の著者数）")
ax.set_title("個人の 1 本目は届かなくなった。Publication の 1 本目は変わらない\n（いいね数は取得時点の累計。新しい記事ほど溜まっていない効果を含む）", fontsize=10.5)
ax.set_ylim(0, 70)
ax.grid(alpha=0.3)
ax.legend(fontsize=9)
plt.setp(ax.get_xticklabels(), rotation=30, ha="right", fontsize=8)
fig.tight_layout()
fig.savefig(OUT / "q_fig4_h1_by_quarter.png")
plt.close(fig)
print("wrote", OUT)
