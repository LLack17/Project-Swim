# Tests 27-30: the last Phase 2 tests, each answering a red-team attack. Uses the v2 data from Test 31.
# Run from the repo root (after data_check.py):  python scripts/phase2_macro/final_tests.py > data/phase2_macro/final_tests_results.txt
#
# Final portfolio: 55% stocks / 40% Treasuries / 5% gold, Trigger 1 only (act above 3.25%, restore below 3.0%,
# 3 months, 2-month lag; trims half the bonds into cash). Trigger 2 is watch-only.
#
# Test 27 (attack 4, gold after a big run): gold's real (CPI-adjusted) losing spells since 1975, and whether a high
#   starting real price was followed by weak 10-year real returns. Pre-committed: REMOVE gold if today's real price
#   is in the top fifth of its 1975-2026 history AND starts in the top fifth averaged a negative 10-year real return.
#   Otherwise gold stays. (Landon kept this rule as written, 2026-10-07.)
# Test 28 (attack 5, is Trigger 1 worth it?): 55/40/5 with Trigger 1 vs static, nominal and after inflation, US monthly
#   1975-2026 and 16 countries annual 1976-2020 (JST, local-currency gold). Pre-committed: KEEP Trigger 1 if, across the
#   15 non-US countries, the after-inflation max drawdown gain is positive with a 95% range above zero, the real return
#   cost is at most 0.2 points a year, and fewer than 10% of placebos match it. Otherwise Trigger 1 becomes watch-only.
# Test 29 (attack 7, cash and inflation): after-inflation results by asset and in the 1970s and 2021-23. Informational.
# Test 30 (equity tilts): do any of 12 industries reliably beat the market while Trigger 1 is on? Pick the top 2 on
#   1970-1997, measure them on 1998-2026. Pre-committed: ADOPT an inflation tilt only if the picks' out-of-sample excess
#   return in Trigger 1 months is positive with a 95% range above zero. Otherwise: no top-down sector tilts.
import os
import sys
import numpy as np
import pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import (load_v2, french, wb_gold, t1_states, final_port, max_dd, ann, worst12, real, boot_mean, JST_PATH)

rng = np.random.default_rng(27)
M = load_v2()
D = M.dropna(subset=["gold"]).copy()
idx = D.index
t1_all = t1_states(M.infl.shift(2))
t1 = pd.Series(t1_all, index=M.index).reindex(idx).values

# ======================= TEST 27 =======================
cpi_idx = (1 + D.cpi_m).cumprod()
gold_idx = (1 + D.gold).cumprod()
rp = gold_idx / cpi_idx
rp = rp / rp.iloc[-1] * 100                     # today's real price = 100
dd = rp / rp.cummax() - 1
spells, start = [], None
for d0, v in dd.items():
    if v < 0 and start is None:
        start = d0
    if v >= 0 and start is not None:
        spells.append((start, d0))
        start = None
if start is not None:
    spells.append((start, None))
mon = lambda a, b: ((b if b is not None else rp.index[-1]).year - a.year) * 12 + (b if b is not None else rp.index[-1]).month - a.month
print("TEST 27: gold in real terms (v2 gold: averages to 2004, GLD after; divided by US CPI), 1975-2026")
print(f"  Worst real drawdown: {dd.min() * 100:.1f}% (trough {dd.idxmin().strftime('%Y-%m')})")
print("  Longest real underwater spells (from a real peak until it was regained):")
for a, b in sorted(spells, key=lambda s: mon(*s), reverse=True)[:3]:
    print(f"    {a.strftime('%Y-%m')} to {b.strftime('%Y-%m') if b is not None else 'still underwater'}: {mon(a, b) / 12:.1f} years")
pct_now = (rp < rp.iloc[-1]).mean() * 100
fwd = (rp.shift(-120) / rp) ** (1 / 10) - 1
q = pd.qcut(rp, 5, labels=["1 (cheapest)", "2", "3", "4", "5 (dearest)"])
tab = pd.DataFrame({"fifth": q, "fwd": fwd}).dropna().groupby("fifth", observed=True).fwd.agg(["mean", "min", "max", "count"])
print(f"\n  Today's real price is above {pct_now:.0f}% of months since 1975")
print("  Average 10-year real return by starting real-price fifth (overlapping windows; only starts up to 2016):")
for k, r in tab.iterrows():
    print(f"    {k:<13} {r['mean'] * 100:6.1f}% a year (range {r['min'] * 100:5.1f}% to {r['max'] * 100:5.1f}%, {int(r['count'])} start months)")
top = tab.loc["5 (dearest)"] if "5 (dearest)" in tab.index else None
if top is not None:
    tops = pd.DataFrame({"fifth": q, "fwd": fwd}).dropna()
    yrs = sorted(set(tops[tops.fifth == "5 (dearest)"].index.year))
    print(f"    top-fifth start years with 10 years of data: {yrs}")
top_now = pct_now >= 80
top_fwd = top["mean"] if top is not None else np.nan
remove = bool(top_now and top_fwd < 0)
print(f"\n  DECISION (fixed before running): today in top fifth: {top_now}; top-fifth starts averaged {top_fwd * 100:.1f}% a year -> {'REMOVE gold' if remove else 'gold STAYS'}")

# ======================= TEST 28 (US) =======================
static, trig = final_port(D, np.zeros(len(idx))), final_port(D, t1)
def row(r):
    rr = real(r, D.cpi_m.values)
    return {"ret_%": round(ann(r) * 100, 2), "max_dd_%": round(max_dd(r) * 100, 1), "real_ret_%": round(ann(rr) * 100, 2),
            "real_max_dd_%": round(max_dd(rr) * 100, 1), "real_worst_12m_%": round(worst12(rr) * 100, 1)}
print("\n\nTEST 28 (US, monthly, 1975-2026, v2 data): 55/40/5 static vs with Trigger 1")
print(pd.DataFrame({"Static 55/40/5": row(static), "With Trigger 1": row(trig)}).T.to_string())
act = max_dd(real(trig, D.cpi_m.values)) - max_dd(real(static, D.cpi_m.values))
sims = [max_dd(real(final_port(D, np.roll(t1, int(rng.integers(24, len(t1) - 24)))), D.cpi_m.values)) - max_dd(real(static, D.cpi_m.values)) for _ in range(500)]
print(f"  Real max drawdown gain from Trigger 1: {act * 100:+.1f} pts; random timing matched it {(np.array(sims) >= act).mean() * 100:.0f}% of the time")

# ======================= TEST 29 =======================
print("\nTEST 29 (US): after inflation")
on = t1 == 1
for lab in ("cash", "bonds", "stocks", "gold"):
    rr = real(D[lab].values, D.cpi_m.values)
    print(f"  {lab:<6} real return while Trigger 1 was on: {ann(rr[on]) * 100:5.1f}% a year ({on.sum()} months); while off: {ann(rr[~on]) * 100:5.1f}%")
for lab, a, b in [("1975-1981", "1975-01-01", "1981-12-31"), ("2021-2023", "2021-01-01", "2023-12-31")]:
    m = (idx >= a) & (idx <= b)
    print(f"  {lab}: cumulative real return, static {(np.prod(1 + real(static, D.cpi_m.values)[m]) - 1) * 100:6.1f}%, "
          f"with Trigger 1 {(np.prod(1 + real(trig, D.cpi_m.values)[m]) - 1) * 100:6.1f}%")

# ======================= TEST 28 (16 countries) =======================
j = pd.read_excel(JST_PATH)[["country", "year", "cpi", "eq_tr", "bond_tr", "bill_rate", "xrusd"]].sort_values(["country", "year"])
sr = 0.01 if j.eq_tr.abs().median() > 1 else 1.0
sb = 0.01 if j.bill_rate.abs().median() > 1 else 1.0
j["stocks"], j["bonds"], j["cash"] = j.eq_tr * sr, j.bond_tr * sr, j.bill_rate * sb
j["infl"] = j.groupby("country").cpi.pct_change()
j["infl_lag"] = j.groupby("country").infl.shift(1) * 100
gp = wb_gold()
j["gpx"] = j.year.map(gp.groupby(gp.index.year).mean()) * j.xrusd
j["gold"] = j.groupby("country").gpx.pct_change()
j = j[(j.year >= 1976) & (j.year <= 2020)].dropna(subset=["stocks", "bonds", "cash", "infl", "infl_lag", "gold"])
rows, keep = [], {}
for c, x in j.groupby("country"):
    if len(x) < 40:
        continue
    fs = t1_states(x.infl_lag.values)
    s0, s1 = final_port(x, np.zeros(len(x))), final_port(x, fs)
    keep[c] = (x, fs, s0)
    rows.append({"country": c, "yrs": len(x), "t1_on_%": fs.mean() * 100,
                 "real_dd_static": max_dd(real(s0, x.infl.values)) * 100,
                 "real_dd_gain": (max_dd(real(s1, x.infl.values)) - max_dd(real(s0, x.infl.values))) * 100,
                 "real_ret_chg": (ann(real(s1, x.infl.values), 1) - ann(real(s0, x.infl.values), 1)) * 100})
t = pd.DataFrame(rows).set_index("country")
print("\n\nTEST 28 (16 countries, annual, 1976-2020, local-currency gold): Trigger 1 vs static 55/40/5, after inflation")
print(t.round(1).to_string())
nus = t.drop(index="USA", errors="ignore")
ci, rc = boot_mean(nus.real_dd_gain, rng), boot_mean(nus.real_ret_chg, rng)
sims = []
for _ in range(500):
    g_ = []
    for c, (x, fs, s0) in keep.items():
        if c == "USA":
            continue
        k = int(rng.integers(5, len(fs) - 5))
        g_.append((max_dd(real(final_port(x, np.roll(fs, k)), x.infl.values)) - max_dd(real(s0, x.infl.values))) * 100)
    sims.append(np.mean(g_))
plc = (np.array(sims) >= nus.real_dd_gain.mean()).mean() * 100
print(f"  Non-US 15: real drawdown gain {nus.real_dd_gain.mean():.2f} pts [{ci[0]:.2f}, {ci[1]:.2f}], better in {(nus.real_dd_gain > 0.05).sum()}, "
      f"worse in {(nus.real_dd_gain < -0.05).sum()}; real return {nus.real_ret_chg.mean():.2f} pts/yr [{rc[0]:.2f}, {rc[1]:.2f}]; placebos matching {plc:.0f}%")
keep_t1 = ci[0] > 0 and nus.real_ret_chg.mean() >= -0.2 and plc < 10
print(f"\n  DECISION (fixed before running): {'KEEP Trigger 1' if keep_t1 else 'Trigger 1 becomes WATCH-ONLY (static 55/40/5)'}")

# ======================= TEST 30 =======================
ind = french("12_Industry_Portfolios") / 100
rel = ind.sub(M.stocks.reindex(ind.index), axis=0).reindex(M.index).dropna()
s1 = pd.Series(t1_all, index=M.index).reindex(rel.index).astype(bool).values
yrs_ = rel.index.year
halves = {"1970-1997": yrs_ <= 1997, "1998-2026": yrs_ >= 1998}
tab30 = pd.DataFrame({h: rel[m & s1].mean() * 1200 for h, m in halves.items()})
print("\n\nTEST 30: 12 industries, return minus the market while Trigger 1 is on (annualized %)")
print(tab30.round(1).to_string())
print("  Trigger 1 months: " + ", ".join(f"{h} {int((m & s1).sum())}" for h, m in halves.items()))
def oos(fit, test):
    picks = tab30[fit].sort_values(ascending=False).index[:2].tolist()
    x = rel.loc[halves[test] & s1, picks].mean(axis=1).values
    blocks = [x[i:i + 12] for i in range(0, len(x), 12)]
    sims = [np.concatenate([blocks[k] for k in rng.integers(0, len(blocks), len(blocks))]).mean() * 1200 for _ in range(3000)]
    lo, hi = np.percentile(sims, [2.5, 97.5])
    return picks, x.mean() * 1200, lo, hi, len(x)
for fit, test in [("1970-1997", "1998-2026"), ("1998-2026", "1970-1997")]:
    picks, m, lo, hi, n = oos(fit, test)
    print(f"  Picked on {fit}: {picks}; in {test} Trigger 1 months: {m:+.1f}% a year vs market [{lo:+.1f}, {hi:+.1f}], {n} months")
picks, m, lo, hi, n = oos("1970-1997", "1998-2026")
print(f"\n  DECISION (fixed before running, picks from 1970-1997 tested on 1998-2026): {'ADOPT a tilt to ' + str(picks) if lo > 0 else 'NO top-down sector tilts'}")
print("  (Industry columns are Ken French's 12 industries, numbered in file order: 1 NoDur, 2 Durbl, 3 Manuf, 4 Enrgy, 5 Chems, 6 BusEq, 7 Telcm, 8 Utils, 9 Shops, 10 Hlth, 11 Money, 12 Other)")
