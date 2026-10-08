# Phase 2 charts for the README. Uses the v2 data from data_check.py (Test 31).
# Run from the repo root:  python scripts/phase2_macro/charts.py
# Writes five figures to docs/figures/, in the order of the thesis:
#   fig1 two kinds of crash, fig2 stock-bond correlation by inflation, fig3 timing rules out of sample,
#   fig4 drawdowns of the final portfolio, fig5 gold's real price.
import os
import re
import sys
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import load_v2

OUT = "docs/figures"
os.makedirs(OUT, exist_ok=True)
SURFACE, INK, INK2, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#e4e3df"
BLUE, ORANGE, AQUA, GRAY = "#2a78d6", "#eb6834", "#1baf7a", "#8a8984"
plt.rcParams.update({
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
    "axes.edgecolor": GRID, "axes.labelcolor": INK2, "xtick.color": INK2, "ytick.color": INK2,
    "text.color": INK, "font.size": 10, "axes.spines.top": False, "axes.spines.right": False,
    "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.6, "axes.axisbelow": True,
})

def title(ax, main, sub):
    ax.set_title(main, loc="left", fontsize=13, fontweight="bold", color=INK, pad=24)
    ax.text(0, 1.02, sub, transform=ax.transAxes, fontsize=9.5, color=INK2, va="bottom")

M = load_v2()
rng = np.random.default_rng(1)


# ---- Figure 1: two kinds of crash (stock peak to stock bottom) ----
episodes = [("1973-74", "1972-12-31", "1974-12-31", "inflation"), ("2000-02", "2000-08-31", "2002-10-31", "growth"),
            ("2007-09", "2007-10-31", "2009-03-31", "growth"), ("2020", "2020-01-31", "2020-03-31", "growth"),
            ("2022", "2021-12-31", "2022-10-31", "inflation")]
rows1 = []
for lab, a, b, kind in episodes:
    seg = M.loc[a:b, ["stocks", "bonds"]].dropna()
    w = (1 + seg.stocks).cumprod()
    w = pd.concat([pd.Series([1.0], index=[seg.index[0] - pd.offsets.MonthEnd(1)]), w])
    trough = (w / w.cummax()).idxmin()
    peak = w.loc[:trough].idxmax()
    win = seg.loc[(seg.index > peak) & (seg.index <= trough)]
    rows1.append((lab, kind, ((1 + win.stocks).prod() - 1) * 100, ((1 + win.bonds).prod() - 1) * 100,
                  f"{(peak + pd.offsets.MonthEnd(1)).strftime('%b %y')} to {trough.strftime('%b %y')}"))
order = [r for r in rows1 if r[1] == "growth"] + [r for r in rows1 if r[1] == "inflation"]
fig, ax = plt.subplots(figsize=(9, 5))
w = 0.36
x = np.array([0, 1, 2, 3.6, 4.6])
for k, (lab, col, idx) in enumerate([("US stocks", ORANGE, 2), ("10-year Treasuries", AQUA, 3)]):
    xs = x + (k - 0.5) * (w + 0.03)
    vals = [r[idx] for r in order]
    ax.bar(xs, vals, width=w, color=col, label=lab, zorder=2)
    for xx, v in zip(xs, vals):
        ax.text(xx, v + (1.2 if v >= 0 else -1.2), f"{v:+.0f}%", ha="center", va="bottom" if v >= 0 else "top", fontsize=9, color=INK)
ax.axhline(0, color=INK2, linewidth=1)
ax.set_xticks(x, [f"{r[0]}\n{r[4]}" for r in order], fontsize=8.5)
ax.set_ylim(-62, 42)
ax.text(1, 38, "Growth crashes", ha="center", fontsize=10, fontweight="bold", color=INK)
ax.text(4.1, 38, "Inflation crashes", ha="center", fontsize=10, fontweight="bold", color=INK)
ax.axvline(2.8, color=GRID, linewidth=1.2)
ax.set_ylabel("Total return, stock peak to stock bottom (%)")
ax.legend(loc="lower right", frameon=False, ncol=1)
ax.set_xlim(-0.6, 5.2)
title(ax, "In growth crashes Treasuries rose; in inflation crashes they did not",
      "Five major US stock selloffs since 1970, stock peak to stock bottom, month-end data (Tests 6, 23, 31).")
fig.tight_layout()
fig.savefig(f"{OUT}/fig1_two_crashes.png", dpi=200)
plt.close(fig)

# ---- Figure 3: timing rules tested in other countries ----
def grab(path, pattern):
    try:
        m = re.search(pattern, open(path).read())
    except FileNotFoundError:
        return None
    return tuple(float(g) for g in m.groups()) if m else None
num = r"\s*([-\d.]+)"
rules = [
    ("Trigger 1, 60/40, nominal\n16 countries, 1950-2020 (Test 17)", grab("data/phase2_macro/cross_country_rule_results.txt", r"One-step rule\s+drawdown" + num + r" pts \[" + num + r"," + num + r"\]")),
    ("Trigger 1, final portfolio, after inflation\n15 countries, 1976-2020 (Test 28)", grab("data/phase2_macro/final_tests_results.txt", r"Non-US 15: real drawdown gain" + num + r" pts \[" + num + r"," + num + r"\]")),
    ("Trigger 2, yield curve\n15 countries, 1950-2020 (Test 25)", grab("data/phase2_macro/cross_country_oos_results.txt", r"Non-US 15\s+drawdown gain" + num + r" pts \[" + num + r"," + num + r"\]")),
    ("Gold instead of more bonds\n15 countries, 1975-2020 (Test 26)", grab("data/phase2_macro/cross_country_oos_results.txt", r"Non-US 15\s+gold minus bonds sleeve: drawdown" + num + r" pts \[" + num + r"," + num + r"\]")),
]
rules = [(lab, v) for lab, v in rules if v is not None]
if rules:
    fig, ax = plt.subplots(figsize=(9, 4.8))
    ys = np.arange(len(rules))[::-1]
    for y, (lab, (m_, lo, hi)) in zip(ys, rules):
        ax.plot([lo, hi], [y, y], color=INK2, linewidth=1.6, zorder=2)
        ax.plot([m_], [y], "o", color=BLUE, markersize=9, markeredgecolor=SURFACE, markeredgewidth=2, zorder=3)
        ax.text(hi + 0.1, y, f"{m_:+.1f} pts  [{lo:+.1f}, {hi:+.1f}]", va="center", fontsize=9, color=INK)
    ax.axvline(0, color=INK2, linewidth=1)
    ax.set_yticks(ys, [r[0] for r in rules], fontsize=9)
    ax.set_xlim(min(-1, min(v[1] for _, v in rules) - 0.5), max(v[2] for _, v in rules) + 1.8)
    ax.set_xlabel("Improvement in worst drawdown, percentage points (average; 95% range)")
    ax.grid(axis="y", visible=False)
    title(ax, "Tested in other countries, every rule's benefit was small",
          "Three of the four 95% ranges reach zero. Both triggers are now watch-only.")
    fig.tight_layout()
    fig.savefig(f"{OUT}/fig3_timing_rules.png", dpi=200)
    plt.close(fig)
else:
    print("Figure 3 skipped: run the cross-country tests first (results files not found).")

# ---- Figure 2: stock-bond correlation by core inflation band ----
d = M.dropna(subset=["stocks", "bonds", "infl"])
bands = [("Below 2%", -99, 2), ("2-3%", 2, 3), ("3-4%", 3, 4), ("4% and above", 4, 99)]
def block_boot(x, y, n=2000, block=12):
    k = len(x)
    vals = []
    for _ in range(n):
        starts = rng.integers(0, k, int(np.ceil(k / block)))
        ix = ((starts[:, None] + np.arange(block)[None, :]).ravel() % k)[:k]
        vals.append(np.corrcoef(x[ix], y[ix])[0, 1])
    return np.nanpercentile(vals, [2.5, 97.5])
rows = []
for lab, lo, hi in bands:
    m = (d.infl >= lo) & (d.infl < hi)
    s, b = d.stocks[m].values, d.bonds[m].values
    c = np.corrcoef(s, b)[0, 1]
    ci = block_boot(s, b)
    rows.append((lab, c, ci[0], ci[1], int(m.sum())))
fig, ax = plt.subplots(figsize=(9, 4.8))
x = np.arange(len(rows))
vals = [r[1] for r in rows]
ax.bar(x, vals, width=0.5, color=BLUE, zorder=2)
ax.errorbar(x, vals, yerr=[[r[1] - r[2] for r in rows], [r[3] - r[1] for r in rows]], fmt="none", ecolor=INK2, elinewidth=1.2, capsize=4, zorder=3)
ax.axhline(0, color=INK2, linewidth=1)
for i, r in enumerate(rows):
    ax.text(i, (r[3] + 0.04) if r[1] >= 0 else (r[2] - 0.04), f"{r[1]:+.2f}", ha="center", va="bottom" if r[1] >= 0 else "top", fontsize=10, color=INK)
    ax.text(i, -0.62, f"{r[4]} months", ha="center", fontsize=8.5, color=INK2)
ax.set_xticks(x, [r[0] for r in rows])
ax.set_ylim(-0.7, 0.7)
ax.set_ylabel("Correlation of monthly stock and bond returns")
ax.set_xlabel("Core PCE inflation over the previous 12 months")
title(ax, "Bonds stop hedging stocks once core inflation passes about 3%",
      f"US stocks vs 10-year Treasuries, monthly, {d.index[0].year}-{d.index[-1].year}. Whiskers: 95% range (12-month block bootstrap). Tests 4, 8, 16.")
fig.tight_layout()
fig.savefig(f"{OUT}/fig2_stock_bond_correlation.png", dpi=200)
plt.close(fig)

# ---- Figure 4: drawdowns, stocks vs 55/45 ----
D = M.loc["1975":].dropna(subset=["stocks", "bonds"])
def underwater(r):
    w = (1 + r).cumprod()
    return (w / w.cummax() - 1) * 100
uw_s = underwater(D.stocks)
uw_p = underwater(0.55 * D.stocks + 0.45 * D.bonds)
fig, ax = plt.subplots(figsize=(9, 4.8))
ax.plot(uw_s.index, uw_s.values, color=ORANGE, linewidth=1.4, label="100% US stocks")
ax.plot(uw_p.index, uw_p.values, color=BLUE, linewidth=1.4, label="55% stocks / 45% Treasuries")
summ = []
for lab, a, b in [("2008-09", "2007-06", "2009-12"), ("2022", "2021-06", "2023-06")]:
    summ.append(f"{lab}: stocks {uw_s.loc[a:b].min():.0f}%, 55/45 {uw_p.loc[a:b].min():.0f}%")
ax.text(0.99, 0.04, "Worst loss in each episode\n" + "\n".join(summ), transform=ax.transAxes, ha="right", va="bottom",
        fontsize=9, color=INK, linespacing=1.5, bbox=dict(boxstyle="round,pad=0.5", facecolor=SURFACE, edgecolor=GRID))
ax.axhline(0, color=INK2, linewidth=1)
ax.set_ylabel("Loss from previous peak (%)")
ax.set_ylim(min(uw_s.min(), uw_p.min()) - 8, 3)
ax.legend(loc="lower left", frameon=False)
title(ax, "55/45 roughly halved the worst loss; in 2022 bonds fell with stocks",
      f"Month-end losses from the previous peak, {D.index[0].year}-{D.index[-1].year}, rebalanced monthly. Daily data shows deeper crashes (Test 31d).")
fig.tight_layout()
fig.savefig(f"{OUT}/fig4_drawdowns.png", dpi=200)
plt.close(fig)

# ---- Figure 5: gold's real price ----
G = M.loc["1975":].dropna(subset=["gold", "cpi_m"])
rp = (1 + G.gold).cumprod() / (1 + G.cpi_m).cumprod()
rp = rp / rp.iloc[-1] * 100
cut = rp.quantile(0.8)
fig, ax = plt.subplots(figsize=(9, 4.8))
ax.plot(rp.index, rp.values, color=BLUE, linewidth=2, label="Gold, inflation-adjusted (today = 100)")
ax.axhline(cut, color=GRAY, linewidth=1.2, linestyle="--")
ax.text(pd.Timestamp("1986-01-31"), cut + 3, "Top fifth of its history: gold is removed above this line", fontsize=9, color=INK2)
pk = rp.loc[:"1985"].idxmax()
ax.annotate(f"1980 peak: not regained\nuntil 2025", (pk, rp[pk]), xytext=(18, -8), textcoords="offset points", fontsize=9, color=INK, va="top")
ax.annotate("Today", (rp.index[-1], rp.iloc[-1]), xytext=(-40, 4), textcoords="offset points", fontsize=9, color=INK)
ax.set_ylabel("Real price index")
ax.set_ylim(0, max(110, rp.max() * 1.08))
title(ax, "Gold's inflation-adjusted price is above 99% of its history since 1975",
      "Every start from the top fifth (1979-81, 2010-13) lost money or broke even over 10 years (Test 27).")
fig.tight_layout()
fig.savefig(f"{OUT}/fig5_gold_real_price.png", dpi=200)
plt.close(fig)
print(f"Wrote charts to {OUT}/")
