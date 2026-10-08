# Tests 25-26: out-of-sample checks on 15 other countries (JST Macrohistory, annual), for the parts of the
# portfolio built on US data only.
# Run from the repo root:  python scripts/phase2_macro/cross_country_oos.py > data/phase2_macro/cross_country_oos_results.txt
#
# Test 25 (Trigger 2 abroad, 1950-2020): curve inverted in year t = long-term rate below short-term rate (annual
#   averages). Annual version of the 12-month hold: Trigger 2 is on in year t if the curve was inverted in year t-1
#   or t-2. It moves 10 points from stocks to bonds, or to cash while Trigger 1 is on. Trigger 1 as in Test 17
#   (lagged inflation above 3.25% acts, below 3.0% restores, trims half of the bonds). Base: 60/40.
#   Measured: Trigger 1 + Trigger 2 versus Trigger 1 alone, per country. Signal quality is scored against years
#   when real GDP per capita fell (informational).
#   Pre-committed: Trigger 2 is CONFIRMED if, across the 15 non-US countries, the average drawdown gain is positive
#   with a 95% range excluding zero, the return cost is at most 0.2 points a year, and fewer than 10% of placebos
#   match it. If not confirmed, Trigger 2 is DOWNGRADED to watch-only.
#
# Test 26 (gold abroad, 1975-2020): gold in each country's own currency (World Bank USD gold, annual average price,
#   converted with JST exchange rates). Core = 60/40 with Triggers 1 and 2; compare a static 5% sleeve of gold,
#   of more local bonds, or of cash.
#   Pre-committed: gold is REMOVED if, across the 15 non-US countries, the gold sleeve's average max drawdown is
#   deeper than the bond sleeve's with a 95% range excluding zero. Otherwise the judgment exception stands.
#
# Caveats: annual data understates drawdowns; annual-average rates and prices smooth everything; countries share
#   global shocks, so ranges are too narrow; for non-US investors, gold also carries a dollar exposure.
import os
import urllib.request
import numpy as np
import pandas as pd

JST = "data/phase2_macro/JSTdatasetR6.xlsx"
WB = "data/phase2_macro/CMO-Historical-Data-Monthly.xlsx"
rng = np.random.default_rng(25)

raw = pd.read_excel(JST)
d = raw[["country", "year", "cpi", "eq_tr", "bond_tr", "bill_rate", "stir", "ltrate", "xrusd", "rgdpbarro"]].sort_values(["country", "year"]).copy()
sr = 0.01 if d.eq_tr.abs().median() > 1 else 1.0
sb = 0.01 if d.bill_rate.abs().median() > 1 else 1.0
d["stocks"], d["bonds"], d["cash"] = d.eq_tr * sr, d.bond_tr * sr, d.bill_rate * sb
g = d.groupby("country")
d["infl_lag"] = g.cpi.pct_change().groupby(d.country).shift(1) * 100
d["inv"] = (d.ltrate < d.stir).astype(float)
d.loc[d.ltrate.isna() | d.stir.isna(), "inv"] = np.nan
d["t2"] = ((d.groupby("country").inv.shift(1) == 1) | (d.groupby("country").inv.shift(2) == 1)).astype(float)
d["gdp_fall"] = (d.groupby("country").rgdpbarro.pct_change() < 0).astype(float)

def t1_states(il):
    on, out = False, []
    for v in il:
        if v > 3.25:
            on = True
        elif v < 3.0:
            on = False
        out.append(on)
    return np.array(out, dtype=float)

def port(s, b, c, f1, f2, sleeve=None, w=0.0):
    ws = 0.6 - 0.10 * f2
    wb = 0.4 - 0.2 * f1 + 0.10 * f2 * (1 - f1)
    wc = 0.2 * f1 + 0.10 * f2 * f1
    core = ws * s + wb * b + wc * c
    return core if sleeve is None else (1 - w) * core + w * sleeve

def max_dd(r):
    x = np.cumprod(1 + np.asarray(r))
    return (x / np.maximum.accumulate(x) - 1).min()

def ann(r):
    return np.prod(1 + np.asarray(r)) ** (1 / len(r)) - 1

def boot(x, n=3000):
    x = np.asarray(x)
    return np.percentile([rng.choice(x, len(x)).mean() for _ in range(n)], [2.5, 97.5])

# ================= TEST 25 =================
p = d[(d.year >= 1950) & (d.year <= 2020)].dropna(subset=["stocks", "bonds", "cash", "infl_lag", "inv"])
rows, keep = [], {}
for c, x in p.groupby("country"):
    if len(x) < 50:
        continue
    s, b, ca = x.stocks.values, x.bonds.values, x.cash.values
    f1, f2 = t1_states(x.infl_lag.values), x.t2.values
    z = np.zeros(len(x))
    r1, r12 = port(s, b, ca, f1, z), port(s, b, ca, f1, f2)
    gf = x.gdp_fall.values
    starts = [i for i in range(1, len(x)) if gf[i] == 1 and gf[i - 1] == 0]
    inv = x.inv.values
    caught = sum(1 for i in starts if inv[max(0, i - 2):i].any())
    onsets = [i for i in range(1, len(x)) if inv[i] == 1 and inv[i - 1] == 0]
    false = sum(1 for i in onsets if not any(i < j <= i + 2 for j in starts))
    keep[c] = (s, b, ca, f1, f2)
    rows.append({"country": c, "yrs": len(x), "t2_on_%": f2.mean() * 100, "overlap_t1_%": (f1 * f2).sum() / max(f2.sum(), 1) * 100,
                 "gdp_falls": len(starts), "caught": caught, "inversions": len(onsets), "false_alarms": false,
                 "dd_t1": max_dd(r1) * 100, "dd_gain": (max_dd(r12) - max_dd(r1)) * 100, "ret_chg": (ann(r12) - ann(r1)) * 100})
t = pd.DataFrame(rows).set_index("country")
print("TEST 25: Trigger 2 (annual, 12-month hold) added to Trigger 1, 60/40 base, 1950-2020")
print("  dd_gain > 0 = shallower worst drawdown than Trigger 1 alone; ret_chg in points a year\n")
print(t.round(1).to_string())
nus = t.drop(index="USA", errors="ignore")
print(f"\n  Signal quality, non-US: caught {nus.caught.sum()} of {nus.gdp_falls.sum()} GDP-per-capita declines within 2 years; "
      f"{nus.false_alarms.sum()} false alarms in {nus.inversions.sum()} inversions")
for lab, tt in [("All 16", t), ("Non-US 15", nus)]:
    ci, rc = boot(tt.dd_gain), boot(tt.ret_chg)
    print(f"  {lab:<10} drawdown gain {tt.dd_gain.mean():5.2f} pts [{ci[0]:5.2f}, {ci[1]:5.2f}], better in {(tt.dd_gain > 0.05).sum()}, worse in {(tt.dd_gain < -0.05).sum()}; "
          f"return {tt.ret_chg.mean():5.2f} pts/yr [{rc[0]:5.2f}, {rc[1]:5.2f}]")
sims = []
for _ in range(500):
    gains = []
    for c, (s, b, ca, f1, f2) in keep.items():
        if c == "USA":
            continue
        k = int(rng.integers(5, len(f2) - 5))
        gains.append((max_dd(port(s, b, ca, f1, np.roll(f2, k))) - max_dd(port(s, b, ca, f1, np.zeros(len(f2))))) * 100)
    sims.append(np.mean(gains))
plc = (np.array(sims) >= nus.dd_gain.mean()).mean() * 100
ci = boot(nus.dd_gain)
ok25 = ci[0] > 0 and nus.ret_chg.mean() >= -0.2 and plc < 10
print(f"  Placebo (non-US, Trigger 2 timing shifted at random): {plc:.0f}% match the actual average gain")
print(f"\n  DECISION (fixed before running): {'CONFIRMED: Trigger 2 stays active' if ok25 else 'NOT CONFIRMED: Trigger 2 downgraded to watch-only'}")

# ================= TEST 26 =================
xl = pd.read_excel(WB, sheet_name=[s for s in pd.ExcelFile(WB).sheet_names if "monthly" in s.lower() and "price" in s.lower()][0], header=None)
xl = xl.fillna("")
col0 = xl.iloc[:, 0].astype(str).str.strip()
first = col0[col0.str.match(r"^\d{4}M\d{2}$")].index[0]
hdr = [r for r in range(first - 1, max(-1, first - 12), -1) if xl.iloc[r].astype(str).str.strip().str.lower().str.startswith("gold").any()][0]
gcol = [i for i, v in enumerate(xl.iloc[hdr].astype(str).str.strip()) if v.lower().startswith("gold")][0]
mask = col0.str.match(r"^\d{4}M\d{2}$")
gm = pd.Series(pd.to_numeric(xl.loc[mask, gcol].replace("", np.nan), errors="coerce").values, index=col0[mask].str[:4].astype(int).values)
gold_usd_px = gm.groupby(level=0).mean()

q = d[(d.year >= 1975) & (d.year <= 2020)].dropna(subset=["stocks", "bonds", "cash", "infl_lag", "xrusd"]).copy()
q["gold_px_local"] = q.year.map(gold_usd_px) * q.xrusd
q["gold"] = q.groupby("country").gold_px_local.pct_change()
q = q.dropna(subset=["gold"])
rows = []
for c, x in q.groupby("country"):
    if len(x) < 40:
        continue
    s, b, ca, gl = x.stocks.values, x.bonds.values, x.cash.values, x.gold.values
    f1 = t1_states(x.infl_lag.values)
    f2 = x.t2.values
    core = port(s, b, ca, f1, f2)
    rg, rb, rc = (port(s, b, ca, f1, f2, gl, 0.05), port(s, b, ca, f1, f2, b, 0.05), port(s, b, ca, f1, f2, ca, 0.05))
    rows.append({"country": c, "yrs": len(x), "corr_gold_stocks": np.corrcoef(gl, s)[0, 1], "corr_gold_bonds": np.corrcoef(gl, b)[0, 1],
                 "dd_core": max_dd(core) * 100, "dd_gold": max_dd(rg) * 100, "dd_bonds": max_dd(rb) * 100, "dd_cash": max_dd(rc) * 100,
                 "gold_minus_bonds_dd": (max_dd(rg) - max_dd(rb)) * 100, "gold_minus_bonds_ret": (ann(rg) - ann(rb)) * 100})
u = pd.DataFrame(rows).set_index("country")
print("\n\nTEST 26: 5% gold sleeve in local currency vs 5% more local bonds vs 5% cash; core 60/40 with Triggers 1 and 2; 1975-2020")
print("  gold_minus_bonds_dd > 0 = gold sleeve has the shallower worst drawdown\n")
print(u.round(2).to_string())
nu = u.drop(index="USA", errors="ignore")
for lab, tt in [("All 16", u), ("Non-US 15", nu)]:
    ci, rc = boot(tt.gold_minus_bonds_dd), boot(tt.gold_minus_bonds_ret)
    print(f"  {lab:<10} gold minus bonds sleeve: drawdown {tt.gold_minus_bonds_dd.mean():5.2f} pts [{ci[0]:5.2f}, {ci[1]:5.2f}]; return {tt.gold_minus_bonds_ret.mean():5.2f} pts/yr [{rc[0]:5.2f}, {rc[1]:5.2f}]; "
          f"avg correlation gold-stocks {tt.corr_gold_stocks.mean():.2f}, gold-bonds {tt.corr_gold_bonds.mean():.2f}")
ci = boot(nu.gold_minus_bonds_dd)
print(f"\n  DECISION (fixed before running): {'REMOVE gold' if ci[1] < 0 else 'gold judgment exception STANDS'}")
