# Phase 2B case studies (US crises): the numbers part of the template (before / during / after).
# Companies and "what experts said at the time" are researched and written up separately.
# Usage, from the repo root:  python scripts/phase2b/case_study.py 1973-74
# Rules fixed before any run (see docs/phase2b_research_plan.md):
#   - Peak = highest level of US stocks' total return after inflation inside the search window;
#     bottom = lowest level after that peak inside the window.
#   - "Before" signals are read at the peak month. Monthly economic data (CPI, core PCE, unemployment) are lagged
#     one month; quarterly national data (profits, GDP, house prices, margin loans) one quarter; BIS private
#     credit two quarters. Market data (CAPE, yields, spreads, fed funds) are not lagged. Each signal is ranked
#     against its own history up to the peak (percentile). Values are today's REVISED figures, not first
#     releases, so GDP- and profit-based signals may look cleaner than they did at the time.
#   - Data checks print first and must pass before results are read:
#       a 2y yield-based return estimate vs SHY and the 20y estimate vs TLT (correlation 0.9 or more, 2002 on);
#       AQR commodity returns vs the S&P GSCI (correlation 0.7 or more, 1985 on);
#       private credit must be in % of GDP (a value between 50 and 400).
#   - Gold before 1975 is the London price (US citizens could not own it); World Bank monthly averages.
import os
import sys
import numpy as np
import pandas as pd

sys.path.insert(0, "scripts/phase2b")
from common2b import (OUT, aqr_century, bond_ret, drawdown, french, fred_m, load_v2, nareit, q_lag,  # noqa: E402
                      shiller_cape, tbill_bey, wb_gold)
from common import fred as _fred, yf_close  # noqa: E402

M = pd.offsets.MonthEnd
WINDOWS = {"1973-74": ("1972-06", "1975-12"), "2000-02": ("1999-06", "2003-06"),
           "2007-09": ("2007-01", "2009-12"), "2022": ("2021-06", "2023-06")}
crisis = sys.argv[1] if len(sys.argv) > 1 else "1973-74"
if crisis not in WINDOWS:
    raise SystemExit(f"choose one of {list(WINDOWS)}")
lines = []
failed = []


def log(s=""):
    print(s)
    lines.append(s)


def pct(x, d=1):
    return "n/a" if pd.isna(x) else f"{x * 100:+.{d}f}%"


def chg(s, n=1):
    """n-period change. Written out because pandas 2.x pct_change() silently fills gaps forward,
    which would turn a missing month into a 0% return or keep a stale value alive."""
    return s / s.shift(n) - 1


def months_between(a, b):
    return (b.year - a.year) * 12 + b.month - a.month


def wealth(r):
    if r.isna().any():
        raise ValueError(f"missing returns in {r.name} between {r.index[0]:%Y-%m} and {r.index[-1]:%Y-%m}")
    return (1 + r).cumprod()


def at(s, t, tol=0):
    """Latest value on or before t; NaN if t is more than `tol` months past the last data point."""
    s = s.dropna()
    if s.empty or t > s.index[-1] + M(tol):
        return np.nan
    s = s[:t]
    return s.iloc[-1] if len(s) else np.nan


# ---------------- data ----------------
v2 = load_v2()
if not v2.index.equals(pd.date_range(v2.index[0], v2.index[-1], freq="ME")):
    raise SystemExit("v2_monthly.csv has missing months: rerun scripts/phase2_macro/data_check.py")
infl = v2.cpi_m
A = pd.DataFrame(index=v2.index)
A["US stocks"] = v2.stocks
A["Cash (T-bills)"] = v2.cash
A["Treasuries 1y"] = bond_ret(fred_m("DGS1"), 1)
A["Treasuries 7-10y (ours)"] = v2.bonds
A["Treasuries 20y"] = bond_ret(fred_m("DGS20"), 20)
A["Gold"] = v2.gold.fillna(chg(wb_gold()))
aqr = aqr_century()
A["Commodities (futures)"] = aqr["Commodities Market"] + v2.cash
A["REITs"] = nareit()
R = A.apply(lambda c: (1 + c) / (1 + infl) - 1)          # real monthly returns

# ---------------- data checks (printed first) ----------------
log("DATA CHECKS")
etf = yf_close(["SHY", "TLT", "^SPGSCI"], "1985-01-01")
etf = chg(etf[~etf.index.duplicated(keep="first")])
checks = [("2y yield-based estimate (method check)", bond_ret(fred_m("DGS2"), 2), "SHY", 0.9),
          ("Treasuries 20y estimate", A["Treasuries 20y"], "TLT", 0.9),
          ("AQR commodities", aqr["Commodities Market"] + v2.cash, "^SPGSCI", 0.7)]
for label, est, tk, need in checks:
    both = pd.concat([est, etf[tk]], axis=1).dropna()
    c = both.corr().iloc[0, 1]
    dd_e, dd_f = drawdown((1 + both.iloc[:, 0]).cumprod()).min(), drawdown((1 + both.iloc[:, 1]).cumprod()).min()
    ok = c >= need
    if not ok:
        failed.append(label)
    log(f"  {label} vs {tk}, {both.index[0]:%Y}-{both.index[-1]:%Y}: correlation {c:.2f} (needs {need}), "
        f"worst drawdown {pct(dd_e)} vs {pct(dd_f)}  {'OK' if ok else 'CAUTION'}")
log("  (The 1y series uses the same method as the 2y check; SHY holds 1-3y bonds.)")
try:
    credit, credit_src = fred_m("QUSPAM770A"), "QUSPAM770A (BIS, % of GDP)"
except Exception:
    credit = (fred_m("QUSPAMUSDA") / fred_m("GDP") * 100).dropna()   # both quarterly, same dates; billions of USD
    credit_src = "QUSPAMUSDA / GDP (fallback)"
log(f"  Private credit source: {credit_src}")
c_last = credit.dropna().iloc[-1]
ok = 50 <= c_last <= 400
if not ok:
    failed.append("private credit units")
log(f"  Private credit / GDP latest value {c_last:.0f} (needs 50-400 to be % of GDP)  {'OK' if ok else 'CAUTION'}")
for sid in ["BAA", "GS10", "TB3MS", "FEDFUNDS", "CPIAUCSL", "PCEPILFE", "UNRATE", "CP", "GDP", "QUSPAM770A",
            "BOGZ1FL663067003Q", "USSTHPI", "FYFSGDA188S", "WALCL", "DGS1", "DGS2", "DGS20"]:
    try:
        info = _fred().get_series_info(sid)
        log(f"  {sid}: {info['title'][:85]} [{info['units_short']}]")
    except Exception as e:
        log(f"  {sid}: title lookup failed ({type(e).__name__})")
if failed:
    log(f"\nSTOP: data checks failed ({', '.join(failed)}). No results computed; paste this output.")
    if os.path.exists(f"{OUT}/case_{crisis}_wealth.csv"):
        os.remove(f"{OUT}/case_{crisis}_wealth.csv")           # never leave an older run's numbers looking current
    with open(f"{OUT}/case_{crisis}_results.txt", "w") as f:
        f.write("\n".join(lines) + "\n")
    raise SystemExit(1)
log("")


def portfolio(r_s, r_b, mode):
    """55/45, rebalanced monthly, yearly (each January) or never. Real returns in, real returns out."""
    if mode == "monthly":
        return 0.55 * r_s + 0.45 * r_b
    out, ws, wb = [], 0.55, 0.45
    for t in r_s.index:
        if mode == "yearly" and t.month == 1:
            tot = ws + wb
            ws, wb = 0.55 * tot, 0.45 * tot
        prev = ws + wb
        ws, wb = ws * (1 + r_s[t]), wb * (1 + r_b[t])
        out.append((ws + wb) / prev - 1)
    return pd.Series(out, index=r_s.index)


# ---------------- peak and bottom ----------------
lo, hi = WINDOWS[crisis]
ws_real = wealth(R["US stocks"].dropna())
ws_nom = wealth(A["US stocks"].dropna())
win = ws_real[lo:hi]
peak = win.idxmax()
bottom = win[peak:].idxmin()
if bottom == peak:
    raise SystemExit("No fall after the peak inside the window: widen the window.")
log(f"Case study {crisis}: US stocks peak {peak:%Y-%m}, bottom {bottom:%Y-%m} ({months_between(peak, bottom)} months)")
if peak == win.index[0] or bottom == win.index[-1]:
    log("WARNING: the peak or bottom sits on the edge of the search window; the window may be too narrow.")
log("=" * 78)

# ---------------- BEFORE ----------------
log("\nBEFORE: warning signs at the peak month (published-by-then lags; today's revised figures)")
log(f"{'signal':44s}{'at peak':>10s}{'24m before':>12s}{'percentile*':>13s}")
gdp = q_lag(fred_m("GDP"))
cpi = fred_m("CPIAUCSL")
unrate = fred_m("UNRATE")
signals = {
    "Shiller CAPE (stock valuation)": shiller_cape(),
    "Credit spread, Baa minus 10y (pts)": fred_m("BAA") - fred_m("GS10"),
    "Yield curve, 10y minus 3m (pts)": fred_m("GS10") - tbill_bey(fred_m("TB3MS")),
    "Fed funds rate (%)": fred_m("FEDFUNDS"),
    "CPI inflation, 12m (%)": (chg(cpi, 12) * 100).shift(1),
    "Core PCE inflation, 12m (%)": (chg(fred_m("PCEPILFE"), 12) * 100).shift(1),
    "Unemployment (%)": unrate.shift(1),
    "Unemployment rise from 12m low (pts)": (unrate - unrate.rolling(12).min()).shift(1),
    "Profit margin, profits / GDP (%)": q_lag(fred_m("CP")) / gdp * 100,
    "Private credit / GDP (%)": q_lag(credit, 2),
    "Margin loans / GDP (%)": q_lag(fred_m("BOGZ1FL663067003Q")) / 1000 / gdp * 100,
    "Real house prices, 12m (%)": chg(q_lag(fred_m("USSTHPI")) / q_lag(cpi), 12) * 100,
}
for name, s in signals.items():
    s = s.dropna()
    hist = s[:peak]
    if hist.empty or hist.index[-1] < peak - M(12):             # no data, or the latest value is over a year stale
        log(f"{name:44s}{'n/a':>10s}")
        continue
    now = hist.iloc[-1]
    ago = at(s, peak - M(24))
    rank = (hist <= now).mean() * 100
    log(f"{name:44s}{now:10.2f}{ago:12.2f}{rank:12.0f}%")
curve = signals["Yield curve, 10y minus 3m (pts)"][peak - M(23):peak]
log(f"\n  Yield curve inverted in the 24 months before the peak: {'yes' if (curve < 0).any() else 'no'} "
    f"(lowest {curve.min():.2f} pts in {curve.idxmin():%Y-%m})")
log("  * percentile = share of all months up to the peak with a lower or equal value (100% = highest on record).")
log("  The 3m T-bill is converted to a bond-equivalent yield so it compares with the 10y.")

# ---------------- DURING ----------------
log("\nDURING: asset scorecard, peak to bottom, after inflation")
score = {}
for c in R.columns:
    r = R[c][peak + M(1):bottom]
    score[c] = np.nan if r.isna().any() or len(r) != months_between(peak, bottom) else (1 + r).prod() - 1
for c, v in sorted(score.items(), key=lambda kv: -np.nan_to_num(kv[1], nan=-9)):
    log(f"  {c:28s}{pct(v):>10s}")
nom = ws_nom[bottom] / ws_nom[peak] - 1
log(f"\n  Depth: stocks {pct(score['US stocks'])} after inflation, {pct(nom)} before inflation; "
    f"inflation over the fall {pct((1 + infl[peak + M(1):bottom]).prod() - 1)}")

ind = french("49_Industry_Portfolios").replace([-99.99, -999], np.nan) / 100
assert ind.shape[1] == 49, "expected 49 industries"
ind = ind.apply(lambda c: (1 + c) / (1 + infl.reindex(ind.index)) - 1)
ind.columns = ["Agric", "Food", "Soda", "Beer", "Smoke", "Toys", "Fun", "Books", "Hshld", "Clths", "Hlth", "MedEq",
               "Drugs", "Chems", "Rubbr", "Txtls", "BldMt", "Cnstr", "Steel", "FabPr", "Mach", "ElcEq", "Autos",
               "Aero", "Ships", "Guns", "Gold", "Mines", "Coal", "Oil", "Util", "Telcm", "PerSv", "BusSv", "Hardw",
               "Softw", "Chips", "LabEq", "Paper", "Boxes", "Trans", "Whlsl", "Rtail", "Meals", "Banks", "Insur",
               "RlEst", "Fin", "Other"]
seg = ind[peak + M(1):bottom]
complete = seg.columns[seg.notna().all()]
ir = ((1 + seg[complete]).prod() - 1).sort_values()
log(f"\n  Industries (Ken French 49), real return peak to bottom ({len(complete)} with complete data)")
log("    worst 5: " + ", ".join(f"{k} {pct(v, 0)}" for k, v in ir.head(5).items()))
log("    best 5:  " + ", ".join(f"{k} {pct(v, 0)}" for k, v in ir.tail(5)[::-1].items()))

log("\n  Policy response")
ff = fred_m("FEDFUNDS")
tmax = ff[peak - M(24):bottom].idxmax()
log(f"    Fed funds: {at(ff, peak - M(12)):.2f}% a year before the peak, {at(ff, peak):.2f}% at the peak, "
    f"highest {ff[tmax]:.2f}% ({tmax:%Y-%m}, searching from 2 years before the peak to the bottom), "
    f"{at(ff, bottom):.2f}% at the bottom, {at(ff, bottom + M(12)):.2f}% a year later")
deficit = fred_m("FYFSGDA188S").dropna()
log(f"    Federal budget balance (% of GDP, negative = deficit): {at(deficit, peak - M(12), tol=12):.1f} the year before "
    f"the peak, {at(deficit, bottom, tol=12):.1f} in the bottom year, {at(deficit, bottom + M(12), tol=12):.1f} a year later")
if bottom.year >= 2003:
    bs = fred_m("WALCL").dropna()
    log(f"    Fed balance sheet: ${at(bs, peak) / 1e6:.2f}tn at the peak, "
        f"${at(bs, bottom + M(12)) / 1e6:.2f}tn a year after the bottom")
log("    (Written up separately: what the Fed and government did, and how fast.)")

# ---------------- 55/45 replay ----------------
seg_end = min(bottom + M(60), R.index[-1])
log(f"\nOUR PORTFOLIO: 55% stocks / 45% Treasuries 7-10y, after inflation, from the stock peak to {seg_end:%Y-%m}")
rs = R["US stocks"][peak + M(1):seg_end]
rb = R["Treasuries 7-10y (ours)"][peak + M(1):seg_end]
for mode in ["monthly", "yearly", "never"]:
    w = pd.concat([pd.Series([1.0], index=[peak]), wealth(portfolio(rs, rb, mode))])
    trough = w.idxmin()
    rec = w[trough:]
    rec = rec[rec >= 1.0]
    log(f"  rebalanced {mode:8s}: at stock bottom {pct(w[bottom] - 1)}, worst {pct(w.min() - 1)} ({trough:%Y-%m}), "
        f"back to start {f'not by {seg_end:%Y-%m}' if rec.empty else f'{rec.index[0]:%Y-%m}'}")

# ---------------- AFTER ----------------
log("\nAFTER")
for label, w in [("after inflation", ws_real), ("before inflation", ws_nom)]:
    later = w[bottom:]
    hit = later[later >= w[peak]]
    log(f"  Stocks back to the old peak ({label}): " +
        (f"not by {w.index[-1]:%Y-%m}" if hit.empty else
         f"{hit.index[0]:%Y-%m}, {months_between(peak, hit.index[0])} months after the peak "
         f"({months_between(peak, hit.index[0]) / 12:.1f} years)"))
pm = pd.concat([pd.Series([1.0], index=[peak]),
                wealth(portfolio(R["US stocks"][peak + M(1):].dropna(), R["Treasuries 7-10y (ours)"][peak + M(1):].dropna(),
                                 "monthly"))])
rec = pm[pm[:seg_end].idxmin():]
rec = rec[rec >= 1.0]
log(f"  55/45 back to its value at the stock peak (after inflation): " +
    (f"not by {pm.index[-1]:%Y-%m}" if rec.empty else
     f"{rec.index[0]:%Y-%m} ({months_between(peak, rec.index[0]) / 12:.1f} years)"))
log("  Returns after the bottom, after inflation, a year:")
for yrs in [1, 3, 5]:
    end = bottom + M(12 * yrs)
    if end > R.index[-1]:
        log(f"    {yrs}y: not enough data yet")
        continue
    rs_, rb_ = R["US stocks"][bottom + M(1):end], R["Treasuries 7-10y (ours)"][bottom + M(1):end]
    assert len(rs_) == 12 * yrs
    s_ = (1 + rs_).prod() ** (1 / yrs) - 1
    p_ = (1 + 0.55 * rs_ + 0.45 * rb_).prod() ** (1 / yrs) - 1
    log(f"    {yrs}y: stocks {pct(s_)}, 55/45 {pct(p_)}")

log("\nData notes: stocks = Ken French US market; Treasuries 1y and 20y estimated from month-end yields (a simple "
    "duration model that understates big rallies slightly); 7-10y = IEF from 2002, a 10y estimate before; "
    "gold = World Bank monthly averages before GLD (smooths moves); commodities = AQR commodity futures plus "
    "T-bill return; REITs = FTSE Nareit All Equity REITs (from 1972); 'after inflation' uses CPI, which before 1983 "
    "counted mortgage rates in housing costs and so overstates 1970s inflation somewhat; CAPE uses Shiller's "
    "interpolated earnings (a small look-ahead); real house prices start in 1975.")

path = f"{OUT}/case_{crisis}_results.txt"
with open(path, "w") as f:
    f.write("\n".join(lines) + "\n")
out = pd.DataFrame({"stocks_real": ws_real / ws_real[peak], "p5545_real_monthly_rebal": pm})
out.loc[peak - M(24):seg_end].to_csv(f"{OUT}/case_{crisis}_wealth.csv")
print(f"\nSaved {path}")
