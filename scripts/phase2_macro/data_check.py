# Test 31: data check and rebuild. Run FIRST; it writes data/phase2_macro/v2_monthly.csv used by Tests 27-32.
# Run from the repo root:  python scripts/phase2_macro/data_check.py > data/phase2_macro/data_check_results.txt
#
# Fixes the six data weaknesses found in the red-team (2026-10-07):
#   31a Bonds: estimated 10-year Treasury returns vs actual funds (IEF from 2002, VFITX from 1991). v2 uses IEF's
#       actual returns where they exist and the estimate before.
#   31b Gold: World Bank monthly AVERAGE prices vs GLD month-end prices (2004 on). v2 uses GLD where it exists.
#   31c Real-time inflation: Trigger 1 rebuilt from core PCE as first published (FRED/ALFRED vintages).
#   31d Daily drawdowns: the final portfolio on daily data (Ken French daily stocks, daily 10-year yields, GLD daily).
#   31e Trading costs: rebalancing and Trigger 1 trades plus 50% a year stock turnover, at two cost levels.
#   31f Options overlay: Cboe PPUT (S&P 500 + 5% out-of-the-money puts) and CLL (collar) vs the S&P 500 total return.
#
# Pre-committed: an estimate is ACCEPTABLE if its monthly returns correlate at least 0.90 with the real series and
# its max drawdown is within 3 points. Separately, every earlier decision stands unless rebuilt data flips the
# result of a pre-committed rule (checked in recheck.py, Test 32).
import os
import sys
import numpy as np
import pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import (DATA, V2_PATH, french, month_end, fred, yf_close, par_duration, wb_gold, realtime_core_pce,
                    t1_states, final_port, max_dd, ann, worst12, stats, get_url)

f = fred()

def fill_months(level):
    """Fill months with no published value (e.g. October 2025, when the shutdown stopped data collection) by
    log-linear interpolation of the price level, so the months around them are not dropped."""
    level = level.dropna()
    full = level.reindex(pd.date_range(level.index[0], level.index[-1], freq="ME"))
    missing = full[full.isna()].index
    if len(missing):
        print(f"  Filled {len(missing)} unpublished month(s) in {level.name or 'a price index'}: {[d.strftime('%Y-%m') for d in missing]}")
    return np.exp(np.log(full).interpolate())

fac = french("F-F_Research_Data_Factors") / 100
# Fix after the first run (2026-10-07): GS10 is a monthly AVERAGE of daily yields, which smoothed and lagged the
# estimate (correlation 0.72 with IEF even though yearly returns matched). Use the month-END 10-year yield instead.
y = f.get_series("DGS10").resample("ME").last() / 100
yp = y.shift(1)
ya = month_end(f.get_series("GS10")) / 100
yap = ya.shift(1)
M = pd.DataFrame({
    "stocks": fac[1] + fac[4],
    "cash": fac[4],
    "bonds_est": yp / 12 - par_duration(yp) * (y - yp),
    "bonds_est_avg": yap / 12 - par_duration(yap) * (ya - yap),
    "infl": fill_months(month_end(f.get_series("PCEPILFE"))).pct_change(12) * 100,
    "cpi_m": fill_months(month_end(f.get_series("CPIAUCSL"))).pct_change(),
}).dropna()["1970":]
gavg = wb_gold()
M["gold_avg"] = gavg.pct_change().reindex(M.index)
M.loc[M.index < "1975-01-31", "gold_avg"] = np.nan          # US citizens could not own gold before 1975
idx = M.index
print(f"Core data: {idx[0].date()} to {idx[-1].date()}, {len(M)} months\n")

px = yf_close(["IEF", "VFITX", "GLD"], start="1990-01-01")
fund = px.pct_change().reindex(idx)

def accept(a, b):
    m = a.notna() & b.notna()
    if m.sum() < 24:
        print(f"   only {m.sum()} overlapping months; cannot judge")
        return False
    a, b = a[m], b[m]
    c = a.corr(b)
    dd_a, dd_b = max_dd(a) * 100, max_dd(b) * 100
    ok = c >= 0.90 and abs(dd_a - dd_b) <= 3
    print(f"   months {m.sum()}, correlation {c:.3f}, tracking error {(a - b).std() * np.sqrt(12) * 100:.1f}% a year")
    print(f"   return {ann(a) * 100:.2f}% (estimate) vs {ann(b) * 100:.2f}% (actual); volatility {a.std() * np.sqrt(12) * 100:.1f}% vs {b.std() * np.sqrt(12) * 100:.1f}%; "
          f"max drawdown {dd_a:.1f}% vs {dd_b:.1f}%")
    for yr in (2008, 2013, 2020, 2022):
        if str(yr) in a.index.year.astype(str):
            print(f"   {yr}: estimate {((1 + a[a.index.year == yr]).prod() - 1) * 100:6.1f}%, actual {((1 + b[b.index.year == yr]).prod() - 1) * 100:6.1f}%")
    print(f"   -> {'ACCEPTABLE' if ok else 'NOT ACCEPTABLE'} (needs correlation >= 0.90 and drawdown within 3 points)")
    return ok

print("TEST 31a: estimated 10-year Treasury returns vs actual funds")
print("  Old estimate (monthly-average yields, used in Tests 1-30) vs IEF:")
accept(M.bonds_est_avg, fund["IEF"])
print("  New estimate (month-end yields) vs IEF (7-10 year Treasury ETF):")
ok_b1 = accept(M.bonds_est, fund["IEF"])
print("  New estimate vs VFITX (Vanguard Intermediate-Term Treasury fund; shorter maturity, so expect a lower volatility):")
accept(M.bonds_est, fund["VFITX"])
ief_start = fund["IEF"].first_valid_index()
M["bonds"] = np.where(idx >= ief_start, fund["IEF"], M.bonds_est)
M["bonds"] = M["bonds"].fillna(M.bonds_est)
print(f"  v2 bonds: estimate until {(ief_start - pd.offsets.MonthEnd(1)).date()}, IEF actual returns from {ief_start.date()}")

print("\nTEST 31b: gold, World Bank monthly averages vs GLD month-end prices")
ok_g = accept(M.gold_avg, fund["GLD"])
g = pd.concat([M.gold_avg, fund["GLD"]], axis=1, keys=["avg", "gld"]).dropna()
worst = g.gld.nsmallest(5)
print("   GLD's 5 worst months and what the averages showed:")
for d0, v in worst.items():
    print(f"     {d0.strftime('%Y-%m')}: GLD {v * 100:6.1f}%, averages {g.avg[d0] * 100:6.1f}%")
gld_start = fund["GLD"].first_valid_index()
M["gold"] = np.where(idx >= gld_start, fund["GLD"], M.gold_avg)
M["gold"] = M["gold"].fillna(M.gold_avg)          # fill any missing GLD month
print(f"  v2 gold: averages 1975 to {(gld_start - pd.offsets.MonthEnd(1)).date()}, GLD month-end from {gld_start.date()}")

print("\nTEST 31c: Trigger 1 with inflation as first published (ALFRED) vs today's revised data")
rt = realtime_core_pce()
M["infl_rt"] = np.nan
if rt is None or len(rt) == 0:
    print("  ALFRED vintages could not be downloaded; real-time check skipped.")
else:
    M["infl_rt"] = rt.reindex(idx)
    known_rev = M.infl.shift(2)                      # revised: two-month publication lag, as in Tests 10-28
    known_rt = M.infl_rt.shift(1)                     # published during month t, acted on in month t+1
    have = known_rt.notna()
    first = have[have].index[0]
    sub = M[M.index >= first]
    s_rev = t1_states(known_rev[sub.index])
    s_rt = t1_states(known_rt[sub.index])
    print(f"  Vintages available from {first.date()} ({have.sum()} months)")
    diff = sub.infl.shift(2) - known_rt[sub.index]
    print(f"  First-published minus revised inflation (same month): mean {-diff.mean():+.2f} pts, largest gap {diff.abs().max():.2f} pts")
    import common as _c
    det = pd.DataFrame(_c.RT_DETAILS)
    if len(det):
        det["revised_yoy"] = det.obs.map(lambda o: M.infl.get(o + pd.offsets.MonthEnd(0), np.nan))
        det["gap"] = det.yoy - det.revised_yoy
        cols = ["obs", "released", "yoy", "revised_yoy", "gap", "index_now", "index_year_ago", "year_ago_vintage"]
        print("  DIAGNOSTIC: first releases more than 1 point away from revised data")
        bad = det[det.gap.abs() > 1]
        print(bad[cols].round(3).to_string(index=False) if len(bad) else "    none")
        print("  DIAGNOSTIC: the last 8 first releases")
        print(det[cols].tail(8).round(3).to_string(index=False))
    def switches(s):
        return [sub.index[i].strftime("%Y-%m") + (" ON" if s[i] else " OFF") for i in range(1, len(s)) if s[i] != s[i - 1]]
    print(f"  Switches, revised data:   {switches(s_rev)}")
    print(f"  Switches, real-time data: {switches(s_rt)}")
    print(f"  Months where the two disagree: {(s_rev != s_rt).sum()} of {len(sub)}")
    print("  55/40/5 over this period (v2 bonds and gold):")
    for lab, st in [("static", np.zeros(len(sub))), ("Trigger 1, revised", s_rev), ("Trigger 1, real-time", s_rt)]:
        r = final_port(sub, st)
        print(f"    {lab:<22} return {ann(r) * 100:5.2f}%, max drawdown {max_dd(r) * 100:6.1f}%, 2022 {((1 + pd.Series(r, index=sub.index)['2022']).prod() - 1) * 100:6.1f}%")

M.to_csv(V2_PATH)
print(f"\n  Saved {V2_PATH} ({len(M)} months): stocks, cash, bonds (v2), bonds_est, gold (v2), gold_avg, infl, infl_rt, cpi_m")

print("\nTEST 31d: daily vs month-end drawdowns (55/40/5 static, daily rebalanced; 58/42 before GLD exists)")
dfac = french("F-F_Research_Data_Factors_daily", daily=True) / 100
dy = f.get_series("DGS10") / 100
dy = dy.reindex(dfac.index).ffill()
dyp = dy.shift(1)
dgld = yf_close("GLD", start="2004-01-01", interval="1d")
gr = dgld.iloc[:, 0].pct_change().reindex(dfac.index)
Dd = pd.DataFrame({"stocks": dfac[1] + dfac[4], "bonds": dyp / 252 - par_duration(dyp) * (dy - dyp), "gold": gr}).dropna(subset=["stocks", "bonds"])
Dd = Dd[Dd.index >= "1962-02-01"]
w_g = np.where(Dd.gold.notna(), 0.05, 0.0)
w_s = np.where(Dd.gold.notna(), 0.55, 0.55 / 0.95)
w_b = 1 - w_s - w_g
Dd["port"] = w_s * Dd.stocks + w_b * Dd.bonds + w_g * Dd.gold.fillna(0)
mon = (1 + Dd[["port", "stocks"]]).resample("ME").prod() - 1
print(f"  Daily data {Dd.index[0].date()} to {Dd.index[-1].date()}")
for col, lab in [("port", "55/40/5"), ("stocks", "stocks alone")]:
    print(f"  {lab:<13} max drawdown: daily {max_dd(Dd[col]) * 100:6.1f}%, month-end {max_dd(mon[col]) * 100:6.1f}%")
for lab, a, b in [("1987 crash", "1987-08-01", "1987-12-31"), ("2008-09", "2007-10-01", "2009-03-31"),
                  ("2020 Covid", "2020-01-01", "2020-06-30"), ("2022", "2022-01-01", "2022-12-31")]:
    d0 = Dd.loc[a:b, "port"]
    m0 = mon.loc[a:b, "port"]
    print(f"  {lab:<11} 55/40/5 drawdown within the episode: daily {max_dd(d0) * 100:6.1f}%, month-end {max_dd(m0) * 100:6.1f}%")

print("\nTEST 31e: trading costs on the final portfolio (55/40/5 with Trigger 1, monthly rebalancing, 1975-2026)")
V = M.dropna(subset=["gold"]).copy()
st = t1_states(V.infl.shift(2))
def run_costs(c_fund, c_stock, turnover=0.5):
    tgt = np.column_stack([np.full(len(V), 0.55), 0.40 * (1 - 0.5 * st), 0.40 * 0.5 * st, np.full(len(V), 0.05)])
    rets = V[["stocks", "bonds", "cash", "gold"]].values
    w = tgt[0].copy()
    gross, net, traded_total = [], [], 0.0
    for i in range(len(V)):
        r = rets[i]
        pr = float(w @ r)
        drift = w * (1 + r) / (1 + pr)
        nxt = tgt[i + 1] if i + 1 < len(V) else tgt[i]
        trade = np.abs(nxt - drift)
        cost = c_stock * trade[0] + c_fund * trade[1:].sum() + c_stock * 0.55 * 2 * turnover / 12
        traded_total += trade.sum()
        gross.append(pr)
        net.append(pr - cost)
        w = nxt
    return np.array(gross), np.array(net), traded_total / (len(V) / 12)
for lab, cf, cs in [("low costs (funds 0.05%, stocks 0.20% per trade)", 0.0005, 0.002), ("high costs (funds 0.10%, stocks 0.50%)", 0.001, 0.005)]:
    gr_, nt_, tv = run_costs(cf, cs)
    print(f"  {lab}: gross {ann(gr_) * 100:.2f}% -> net {ann(nt_) * 100:.2f}% a year (drag {(ann(gr_) - ann(nt_)) * 100:.2f} pts); "
          f"rebalancing turnover {tv * 100:.0f}% of the portfolio a year, plus 50% stock turnover")

print("\nTEST 31f: options overlay benchmarks (Cboe PPUT = S&P 500 + monthly 5% out-of-the-money puts; CLL = collar)")
def cboe(name):
    path = f"{DATA}/{name}_History.csv"
    if not os.path.exists(path):
        try:
            with open(path, "wb") as fh:
                fh.write(get_url(f"https://cdn.cboe.com/api/global/us_indices/daily_prices/{name}_History.csv"))
        except Exception as e:
            if os.path.exists(path):
                os.remove(path)
            print(f"  Could not download {name} ({e}). Download its history from cboe.com/us/indices/index-protection/ "
                  f"and save it as {path}, then rerun.")
            return None
    rows = []
    for line in open(path, encoding="latin-1").read().splitlines():
        parts = [p.strip() for p in line.split(",")]
        if len(parts) < 2:
            continue
        d0 = pd.to_datetime(parts[0], errors="coerce")
        try:
            v = float(parts[-1])
        except ValueError:
            continue
        if pd.notna(d0):
            rows.append((d0, v))
    s = pd.Series(dict(rows)).sort_index()
    return s.resample("ME").last().pct_change().dropna()
pput, cll = cboe("PPUT"), cboe("CLL")
if pput is not None and cll is not None:
    spx = yf_close("^SP500TR", start="1988-01-01").iloc[:, 0].pct_change()
    O = pd.concat([spx, pput, cll], axis=1, keys=["S&P 500 TR", "PPUT", "CLL"]).dropna()
    O = O[O.index <= idx[-1]]
    print(f"  {O.index[0].date()} to {O.index[-1].date()}")
    rows = {k: {**stats(O[k]), "worst_12m_%": round(worst12(O[k]) * 100, 1),
                **{str(yr): round(((1 + O[k][O.index.year == yr]).prod() - 1) * 100, 1) for yr in (2000, 2001, 2002, 2008, 2020, 2022)}}
            for k in O.columns}
    print(pd.DataFrame(rows).T.to_string())
    B = M.reindex(O.index)
    for lab, hedge in [("no overlay", O["S&P 500 TR"]), ("a third of stocks in PPUT", O["PPUT"]), ("a third of stocks in CLL", O["CLL"])]:
        stock_sleeve = (2 / 3) * O["S&P 500 TR"] + (1 / 3) * hedge
        r = 0.55 * stock_sleeve + 0.40 * B.bonds + 0.05 * B.gold
        print(f"  55/40/5 with {lab:<26} return {ann(r) * 100:5.2f}%, max drawdown {max_dd(r) * 100:6.1f}%, 2008 {((1 + r[r.index.year == 2008]).prod() - 1) * 100:6.1f}%")
    print("  Note: index options, not options on single stocks; single-stock puts cost more because single stocks are more volatile.")

print("\nSUMMARY (rule fixed before running: correlation >= 0.90 and max drawdown within 3 points)")
print(f"  Bond estimate vs IEF: {'ACCEPTABLE' if ok_b1 else 'NOT ACCEPTABLE'}; gold averages vs GLD: {'ACCEPTABLE' if ok_g else 'NOT ACCEPTABLE'}")
print("  Next: python scripts/phase2_macro/recheck.py (Test 32), then final_tests.py (Tests 27-30)")
