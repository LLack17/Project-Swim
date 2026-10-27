# Phase 2B decision tests, stage 1: inflation protection (2B-A), commodities (2B-I), bond length (2B-F).
# Usage, from the repo root:  python scripts/phase2b/mix_tests.py
# Output: data/phase2b/mix_tests_results.txt. Final mix (2B-H) runs later, using these results.
#
# Rules: docs/phase2b_research_plan.md (2B-A, 2B-F rows; amendments 2026-10-09, 2026-10-16 (2B-I), 2026-10-26).
# Implementation details fixed here, before any run on real data:
#   - Crash windows are the case-study windows. A crash "loss" = the worst fall inside the window, after
#     inflation (CPI), measured from the window's start.
#   - High-inflation selloff quarters (Test 19 definition): the worst tenth of NOMINAL US stock quarters,
#     1970-2026, keeping those with core PCE inflation (12-month, revised) above 3% at quarter-end. Picked ONCE
#     and used for both measures and every candidate (each candidate uses those inside its own months).
#     For the 1927-on check (2B-I (e)), core PCE does not exist before 1959, so CPI inflation is used there.
#   - 2B-I (e) "points the same way" is defined here, before running, as: on 1927-on data the candidate beats
#     55/45 on average in high-inflation selloff quarters AND costs at most 0.5 pts a year.
#   - Costs are compared unrounded (Test 19 compared returns rounded to 0.1 point; this is slightly stricter).
#   - Baseline: 55% US stocks / 45% Treasuries 7-10y (our v2 series), rebalanced monthly.
#   - Fund costs: commodity futures 0.5 pts/yr, managed futures 1.0 pts/yr, charged monthly; REITs none.
#   - Commodity futures = AQR Century "Commodities Market" excess return + T-bill (French RF).
#   - Trend proxy (2026-10-09 amendment): long/short on the past 12-month excess return of AQR's stock-index,
#     bond and commodity market series, each sized to 10% annual volatility using the past 36 months, equal
#     weight; uses data to the prior month-end only. The proxy is then scaled by one constant so its
#     volatility matches AQR's official trend factor over their common months (size only: correlation is
#     unaffected). Used for 2B-A only if its correlation with the official factor is 0.7 or more; otherwise the
#     official factor (1985 on) is used and the result is flagged as resting on one inflation crash (2022).
#     The scale uses the official factor's 1985-on volatility, i.e. later data sets the position size used in
#     the 1970s; this affects drawdown and cost, not the correlation check, and is stated in the results.
#   - 2B-I index variant: the S&P GSCI series from Yahoo (^SPGSCI) has an unclear form (excess or total
#     return). A data check compares it with the GSG fund (GSCI total return, 0.75% fee), 2007-2025 calendar
#     years, under both readings, and uses the closer one if its average yearly gap is under 2 points;
#     otherwise the variant is reported as not run (broad basket by default, as the rule says).
#   - 2B-F bonds are modelled from month-end yields (par bond, constant maturity) for all three lengths so they
#     are compared on equal terms: 1-3y = 2-year yield (average of 1- and 3-year yields before June 1976);
#     7-10y = 10-year yield; 20y+ = 20-year yield (1987-1993 gap: returns from the 30-year yield). In gap months
#     the return is computed entirely from the stand-in yield, so no month mixes two different yields.
#   - The trend filter's signal uses commodity returns before the 0.5-pt cost; the cost is charged when held.
#   - The index-type comparison uses the static winner, even if the trend filter is adopted.
#   - Drawdowns count the starting value as a high point (Test 19 did not; this only matters if the first
#     month is a loss).
#   - Index months that were never published (e.g. US CPI for October 2025) are filled log-linearly between
#     neighbouring months; filled months are listed in the results. Our v2 data already does the same.
#   - Bond returns use a duration-only model (no convexity), which slightly understates long-bond returns
#     when rates move a lot; this is stated next to the 2B-F result.
#   - AQR's commodity and bond "Market" series are used as published; their volatility is printed next to the
#     GSCI and GSG funds so their scale can be checked by eye (not a gate).
#   - Data checks print first. Each gates only the test it feeds: the bond models must correlate 0.9 or more
#     with SHY, IEF and TLT (2002 on) and have no missing months, or 2B-F does not run; AQR commodities must
#     correlate 0.7 or more with the S&P GSCI, the GSCI form check must pass and the GSCI series must have no
#     missing months, or the index-type variant does not run (broad basket by default). A missing month in an
#     ETF series skips only the information-only supplement. Any other sample must cover every month between
#     its first and last date, or the script stops with an error (the error is written to the results file).
import os
import sys
import pandas as pd

sys.path.insert(0, "scripts/phase2b")
from common2b import OUT, aqr_century, aqr_tsmom, bond_ret, french, fred_m, load_v2, nareit  # noqa: E402
from common import yf_close  # noqa: E402
import mix_engine as E  # noqa: E402

COMM_FEE, MF_FEE = 0.005, 0.010
RESULTS = f"{OUT}/mix_tests_results.txt"
lines, failed = [], []           # failed = bond data checks (gate 2B-F only)


def log(s=""):
    print(s)
    lines.append(s)


def pct(x, d=1):
    return "n/a" if x is None or pd.isna(x) else f"{x * 100:+.{d}f}%"


def pts(x):
    return "n/a" if x is None or pd.isna(x) else f"{x * 100:+.2f} pts"


def share(x):
    return "n/a" if x is None or pd.isna(x) else f"{x * 100:.0f}%"


def yn(b):
    return "PASS" if b else "FAIL"


def finish(code=0):
    os.makedirs(OUT, exist_ok=True)
    with open(RESULTS, "w") as f:
        f.write("\n".join(lines) + "\n")
    print(f"\nSaved {RESULTS}")
    if code:
        raise SystemExit(code)


def _on_error(exc_type, exc, tb):
    """Write what was produced so far, plus the error, to the results file before stopping."""
    if exc_type is not SystemExit:
        log(f"\nERROR, script stopped: {exc_type.__name__}: {exc}")
        finish()
    sys.__excepthook__(exc_type, exc, tb)


sys.excepthook = _on_error

# ======================= DATA =======================
v2 = load_v2()
if not v2.index.equals(pd.date_range(v2.index[0], v2.index[-1], freq="ME")):
    raise SystemExit("v2_monthly.csv has missing months: rerun scripts/phase2_macro/data_check.py")
v2 = v2["1970":]
s, b, c, infl = v2.stocks, v2.bonds, v2.cash, v2.cpi_m
pce_lvl, pce_filled = E.fill_index(fred_m("PCEPILFE"))
pce_q = E.quarter_end(E.chg(pce_lvl, 12) * 100)
cpiL, cpi_filled = E.fill_index(fred_m("CPIAUCNS"))

fac = french("F-F_Research_Data_Factors")
rf_all = fac[4] / 100
aqr = aqr_century()
comm_all = aqr["Commodities Market"] + rf_all - COMM_FEE / 12          # 1926 on, after fund costs
comm_gross_all = aqr["Commodities Market"] + rf_all                     # before costs (for the trend signal)
tsmom = aqr_tsmom()["TSMOM"]
reits = nareit()

y = {k: fred_m(k) for k in ["DGS1", "DGS2", "DGS3", "DGS10", "DGS20", "DGS30"]}
# Gap months take returns computed entirely from the stand-in yield, so no month mixes two different yields.
r2 = E.splice(bond_ret(y["DGS2"], 2), bond_ret((y["DGS1"] + y["DGS3"]) / 2, 2), "1962", "1976-06")
r20 = E.splice(bond_ret(y["DGS20"], 20), bond_ret(y["DGS30"], 20), "1987-01", "1993-12")
BONDS = {"1-3y": r2, "7-10y": bond_ret(y["DGS10"], 10), "20y+": r20}
BONDS = {k: v.reindex(v2.index) for k, v in BONDS.items()}

etf = yf_close(["SHY", "IEF", "TLT", "^SPGSCI", "GSG"], "1985-01-01")
etf = E.chg(etf[~etf.index.duplicated(keep="last")])[:v2.index[-1]]      # no partial current month
etf = etf.reindex(columns=["SHY", "IEF", "TLT", "^SPGSCI", "GSG"])       # a missing ticker becomes empty, not an error

# ======================= DATA CHECKS =======================
log("PHASE 2B DECISION TESTS, STAGE 1: inflation protection (2B-A), commodities (2B-I), bond length (2B-F)")
log("=" * 100)
log("DATA CHECKS")
for k, v in BONDS.items():
    gaps = v.isna().sum()
    if gaps:
        failed.append(f"bond {k} gaps")
    log(f"  Bond model {k}: {gaps} missing months 1970-{v2.index[-1]:%Y-%m}  {'OK' if not gaps else 'FAIL'}")
for k, tk in [("1-3y", "SHY"), ("7-10y", "IEF"), ("20y+", "TLT")]:
    both = pd.concat([BONDS[k], etf[tk]], axis=1, sort=True).dropna()
    if len(both) < 24:
        failed.append(f"bond model {k}")
        log(f"  Bond model {k} vs {tk}: no usable fund data  FAIL")
        continue
    cr = both.corr().iloc[0, 1]
    gap = E.ann(both.iloc[:, 0]) - E.ann(both.iloc[:, 1])
    ok = cr >= 0.9
    if not ok:
        failed.append(f"bond model {k}")
    log(f"  Bond model {k} vs {tk}, {both.index[0]:%Y-%m} to {both.index[-1]:%Y-%m}: correlation {cr:.2f} (needs 0.9); "
        f"yearly return gap {pts(gap)}  {'OK' if ok else 'FAIL'}")
both = pd.concat([aqr["Commodities Market"] + rf_all, etf["^SPGSCI"]], axis=1, sort=True).dropna()
if len(both) < 24:
    gsci_corr_ok = False
    log("  AQR commodities vs S&P GSCI: no usable GSCI data  FAIL: index-type variant will not run")
else:
    cr = both.corr().iloc[0, 1]
    gsci_corr_ok = cr >= 0.7
    log(f"  AQR commodities vs S&P GSCI, {both.index[0]:%Y}-{both.index[-1]:%Y}: correlation {cr:.2f} (needs 0.7)  "
        f"{'OK' if gsci_corr_ok else 'FAIL: index-type variant will not run'}")
vol = lambda r: f"{r.std() * 12 ** 0.5 * 100:.1f}%" if len(r) > 1 else "n/a"  # noqa: E731
v_ = pd.concat({"aqr_c": aqr["Commodities Market"] + rf_all, "aqr_b": aqr["Fixed income Market"] + rf_all,
                "gsci": etf["^SPGSCI"], "gsg": etf["GSG"], "ief": etf["IEF"]}, axis=1, sort=True)["2007":"2025"]
log(f"  Scale check (annual volatility, 2007-2025, not a gate): AQR commodities {vol(v_.aqr_c.dropna())}, "
    f"S&P GSCI {vol(v_.gsci.dropna())}, GSG fund {vol(v_.gsg.dropna())}; AQR bonds (used only in the "
    f"1927-on check) {vol(v_.aqr_b.dropna())}, IEF {vol(v_.ief.dropna())}")
log(f"  Unpublished months filled: CPI {[f'{t:%Y-%m}' for t in cpi_filled] or 'none'}; "
    f"core PCE {[f'{t:%Y-%m}' for t in pce_filled] or 'none'}")
d = (v2.cash - rf_all.reindex(v2.index)).abs().max()
log(f"  v2 cash vs Ken French T-bill: largest difference {d:.6f} (should be ~0)  {'OK' if d < 1e-6 else 'CAUTION'}")

# Trend proxy
Xm = aqr[["Equity indices Market", "Fixed income Market", "Commodities Market"]]
proxy_raw = E.trend_proxy(Xm)
pc = pd.concat([proxy_raw, tsmom], axis=1, sort=True).dropna()
proxy_corr = pc.corr().iloc[0, 1]
scale = pc.iloc[:, 1].std() / pc.iloc[:, 0].std()
use_proxy = proxy_corr >= 0.7
log(f"  Trend proxy vs AQR official trend factor, {pc.index[0]:%Y-%m} to {pc.index[-1]:%Y-%m}: correlation "
    f"{proxy_corr:.2f} (needs 0.7) -> {'proxy used from 1970' if use_proxy else 'official factor used (1985 on, ONE inflation crash)'}; "
    f"size scale {scale:.2f} (set from the official factor's 1985-on volatility)")
mf_proxy = (scale * proxy_raw + rf_all - MF_FEE / 12).dropna()
mf_official = (tsmom + rf_all - MF_FEE / 12).dropna()

# GSCI form check
g = pd.concat({"gsci": etf["^SPGSCI"], "gsg": etf["GSG"], "rf": rf_all}, axis=1, sort=True).dropna()["2007":"2025"]
g = g[g.groupby(g.index.year)["gsci"].transform("size") == 12]               # whole calendar years only
yr = lambda r: (1 + r).groupby(r.index.year).prod() - 1  # noqa: E731
gap_er = (yr(g.gsci + g.rf - 0.0075 / 12) - yr(g.gsg)).abs().mean() if len(g) else float("nan")
gap_tr = (yr(g.gsci - 0.0075 / 12) - yr(g.gsg)).abs().mean() if len(g) else float("nan")
gsci_form = ("excess" if gap_er <= gap_tr else "total") if min(gap_er, gap_tr) < 0.02 and gsci_corr_ok else None
log(f"  S&P GSCI form vs GSG fund, 2007-2025: average yearly gap if excess-return {pts(gap_er)}, if total-return "
    f"{pts(gap_tr)} -> {gsci_form + '-return reading used' if gsci_form else 'unclear or failed: index variant NOT RUN'}")
if gsci_form:
    gsci_total = (etf["^SPGSCI"] + (rf_all if gsci_form == "excess" else 0)).dropna() - COMM_FEE / 12
    try:
        E.contiguous(gsci_total, "S&P GSCI")
    except ValueError:
        gsci_form = None
        log("  S&P GSCI series has a missing month: index variant NOT RUN")

bonds_ok = not failed
if failed:
    log(f"  2B-F WILL NOT RUN: bond data checks failed: {failed}")

# Baseline and reference (after inflation)
R_ = lambda r: E.real(r, infl)  # noqa: E731
base_n = 0.55 * s + 0.45 * b
base_r = R_(base_n)
log("\n  Our 55/45 crash losses (worst fall inside each case-study window, after inflation). The case studies")
log("  measured from the stock peak instead, so small differences are expected:")
ref = {"1973-74": -0.396, "2000-02": -0.207, "2007-09": -0.271, "2022": -0.248}
for k in E.WINDOWS:
    log(f"    {k:8s} {pct(E.window_loss(base_r, k))}   (case study {pct(ref[k])})")
sel_q = E.selloff_quarters(s, pce_q)          # fixed 1970-2026 set, used by 2B-A and 2B-I
log(f"  High-inflation selloff quarters 1970-{v2.index[-1]:%Y}: {len(sel_q)}: " + ", ".join(f"{q:%Y}Q{(q.month - 1) // 3 + 1}" for q in sel_q))

# ======================= 2B-A INFLATION PROTECTION =======================
log("\n" + "=" * 100)
log("2B-A INFLATION PROTECTION: does a 10% slice (taken proportionally from stocks and bonds) earn a place?")
log("Pass = all three Test 19 criteria, both before AND after inflation, on 55/45:")
log("  (a) high-inflation selloff quarters: at least 5, average beats cash, positive in more than half")
log("  (b) 10% slice: shallower worst drawdown than 55/45 AND than a 10% cash slice; costs at most 0.5 pts/yr")
log("  (c) the drawdown improvement shows up in both halves (1970-97, 1998-2026)")
mf = mf_proxy if use_proxy else mf_official
cands = {"Managed futures" + (" (trend proxy)" if use_proxy else " (official, 1985 on)"): mf,
         "REITs (from 1972)": reits, "Commodity futures": comm_all}
a_pass = {}
for name, a in cands.items():
    a = a.reindex(v2.index)
    log(f"\n  {name}")
    res = {}
    for meas, f in [("before inflation", lambda x: x), ("after inflation", R_)]:
        for bw in [(0.55, 0.45), (0.60, 0.40)]:
            t = E.test19(f(a), f(s), f(b), f(c), sel_q, base_w=bw)
            res[(meas, bw)] = t
            tag = "" if bw == (0.55, 0.45) else "   [60/40, for comparison with Test 19 only]"
            log(f"    {meas:16s} {int(bw[0] * 100)}/{int(bw[1] * 100)} {t['start']:%Y-%m}-{t['end']:%Y-%m}: "
                f"(a) {yn(t['a'])} n={t['n_q']}, asset {pct(t['q_asset'])} vs cash {pct(t['q_cash'])}, positive {share(t['q_pos'])} | "
                f"(b) {yn(t['b'])} worst drawdown {pct(t['dd_slice'])} vs base {pct(t['dd_base'])} vs cash slice {pct(t['dd_cash'])}, "
                f"cost {pts(t['cost'])} | (c) {yn(t['c'])} " + ", ".join(f"{h0}-{h1} {pts(i)}" for h0, h1, i in t["halves"]) + tag)
    ok = res[("before inflation", (0.55, 0.45))]["pass"] and res[("after inflation", (0.55, 0.45))]["pass"]
    a_pass[name] = ok
    sl = E.contiguous(R_(0.9 * base_n + 0.1 * a).dropna(), name)
    log("    Crash losses after inflation, 55/45 with the 10% slice vs 55/45: " +
        "; ".join(f"{k} {pct(E.window_loss(sl, k))} vs {pct(E.window_loss(base_r, k))}"
                  for k in E.WINDOWS if sl.index[0] <= pd.Timestamp(E.WINDOWS[k][0]) + pd.offsets.MonthEnd(0) and sl.index[-1] >= pd.Timestamp(E.WINDOWS[k][1]) + pd.offsets.MonthEnd(0)))
    log(f"    VERDICT: {'EARNS A PLACE (up to 10%)' if ok else 'not supported'}"
        + ("  (weight decided by 2B-I, not here)" if name.startswith("Commodity") else ""))
if not use_proxy:
    log("  NOTE: managed futures rest on one inflation crash (2022) because the trend proxy failed its check.")
else:
    t = E.test19(R_(mf_official.reindex(v2.index)), R_(s), R_(b), R_(c), sel_q)
    log(f"  Supplement (information only, the proxy decides): official trend factor 1985 on, after inflation: "
        f"(a) {yn(t['a'])} (b) {yn(t['b'])} (c) {yn(t['c'])}")

# ======================= 2B-I COMMODITIES =======================
log("\n" + "=" * 100)
log("2B-I COMMODITY FUTURES FUNDED FROM BONDS (after inflation, rebalanced monthly)")
log("Pass = all of: (a) smaller loss than 55/45 in both inflation crashes AND better in most high-inflation selloff")
log("quarters; (b) no more than 3 pts worse in each growth crash; (c) costs at most 0.5 pts/yr; (d) (a) and (c) hold in")
log("each half (1970-97, 1998-2026); (e) 1927-on check points the same way, defined in advance as: better on")
log("average in high-inflation selloff quarters (CPI-based) and costs at most 0.5 pts/yr.")
P = E.contiguous(pd.DataFrame({"s": s, "b": b, "m": comm_all.reindex(v2.index)}).dropna(), "2B-I sample")
infl_i = infl.reindex(P.index)
base_i = E.real(E.port(P, {"s": 0.55, "b": 0.45}), infl_i)
sel_i = sel_q[sel_q <= P.index[-1]]                       # the fixed set, inside this test's months
log(f"  Sample {P.index[0]:%Y-%m} to {P.index[-1]:%Y-%m} (AQR data end)")
# long sample for (e)
L = E.contiguous(pd.DataFrame({"s": (fac[1] + fac[4]) / 100, "b": aqr["Fixed income Market"] + rf_all,
                               "m": comm_all, "i": E.chg(cpiL)}).dropna()["1927":], "long sample")
selL = E.selloff_quarters(L.s, E.quarter_end(E.chg(cpiL, 12) * 100))
baseL = E.real(E.port(L, {"s": 0.55, "b": 0.45}), L.i)
log(f"  Long check sample {L.index[0]:%Y-%m} to {L.index[-1]:%Y-%m} (Ken French stocks, AQR bonds, CPI); "
    f"{len(selL)} high-inflation selloff quarters")


def run_i(label, m_series, mL_series, w):
    PP = P.assign(m=m_series.reindex(P.index))
    cand = E.real(E.port(PP, {"s": 0.55, "b": 0.45 - w, "m": w}), infl_i)
    r = E.crit_commod(cand, base_i, sel_i)
    LL = E.contiguous(L.assign(m=mL_series.reindex(L.index)).dropna(), "long sample (variant)")
    candL = E.real(E.port(LL, {"s": 0.55, "b": 0.45 - w, "m": w}), LL.i)
    e = E.crit_long(candL, baseL.reindex(candL.index), selL[(selL >= candL.index[0]) & (selL <= candL.index[-1])])
    r["e"] = e["e"]
    r["pass"] = r["a"] and r["b"] and r["c"] and r["d"] and r["e"]
    log(f"\n  {label}")
    log("    Crash losses (candidate vs 55/45): " + "; ".join(f"{k} {pct(v[0])} vs {pct(v[1])}" for k, v in r["loss"].items()))
    log(f"    Selloff quarters better than 55/45: {share(r['q_better'])} of {r['q_n']};  cost {pts(r['cost'])}/yr")
    log("    Halves: " + "; ".join(f"{h[0]}-{h[1]}: better in {share(qb)} of {n} selloff quarters, cost {pts(cst)}"
                               for h, qb, n, cst in r["half_detail"]))
    log(f"    Long check: average selloff-quarter edge {pts(e['q_diff'])} (n={e['q_n']}), cost {pts(e['cost'])}/yr")
    log(f"    (a) {yn(r['a'])} (b) {yn(r['b'])} (c) {yn(r['c'])} (d) {yn(r['d'])} (e) {yn(r['e'])}  -> {'PASSES' if r['pass'] else 'fails'}")
    return r, cand


r5, c5 = run_i("55/40/5 (5% commodities, always held)", comm_all, comm_all, 0.05)
r10, c10 = run_i("55/35/10 (10% commodities, always held)", comm_all, comm_all, 0.10)
win = E.pick_weight(r5, r10, r5["pass"], r10["pass"])
log(f"\n  PRIMARY RESULT: {'no candidate passes; 55/45 stays (no commodities)' if win is None else f'{win}% commodities'}")

if win is not None:
    w = win / 100
    rw, cw = (r5, c5) if win == 5 else (r10, c10)
    log("\n  Second stage (judged only against the primary winner):")
    tf, held = E.trend_filter(comm_gross_all, rf_all, fee_m=COMM_FEE / 12)
    rt, ct = run_i(f"  Trend-filtered {win}% (commodities held in {share(held.reindex(P.index).mean())} of months, "
                   f"{P.index[0]:%Y}-{P.index[-1]:%Y})", tf, tf, w)
    adopt_tf, gw, gt = E.trend_adopt(rw, rt)
    log(f"    Worse growth-crash loss: trend-filtered {pct(gt)} vs static {pct(gw)} (needs 2+ pts better and (a)-(e)) "
        f"-> {'ADOPT trend filter' if adopt_tf else 'keep static'}")
    if gsci_form:
        PG = E.contiguous(pd.DataFrame({"s": s, "b": b, "broad": comm_all.reindex(v2.index),
                                        "gsci": gsci_total.reindex(v2.index)}).dropna(), "index-type sample")
        ig = infl.reindex(PG.index)
        pb = E.real(E.port(PG, {"s": 0.55, "b": 0.45 - w, "broad": w}), ig)
        pg = E.real(E.port(PG, {"s": 0.55, "b": 0.45 - w, "gsci": w}), ig)
        use_g, l22b, l22g, cost_g = E.gsci_rule(pb, pg)
        log(f"    Index type (static {win}%), {PG.index[0]:%Y-%m} to {PG.index[-1]:%Y-%m}: 2022 loss GSCI {pct(l22g)} vs broad {pct(l22b)}; "
            f"GSCI cost {pts(cost_g)}/yr (GSCI needs 5+ pts better in 2022 at <= 1 pt/yr) -> {'GSCI' if use_g else 'broad basket'}")
    else:
        log("    Index type: NOT RUN (GSCI data check failed) -> broad basket by default")
    log("    Conditional signal variant: waits for 2B-B (warning signs) and the rule freeze (2027-10-08).")
else:
    log("  Second stage not run (plan rule: variants are judged only against a primary winner).")

# ======================= 2B-F BOND LENGTH =======================
log("\n" + "=" * 100)
log("2B-F BOND LENGTH: 55% stocks / 45% Treasuries of each length, after inflation, rebalanced monthly, 1970 on")
log("Pass = cuts the worse growth-crash loss AND the worse inflation-crash loss by 1+ pt each vs 7-10y, at <= 0.3 pts/yr")
if not bonds_ok:
    log("  NOT RUN: bond data checks failed (see DATA CHECKS).")
    PF = {}
else:
    PF = {k: E.real(0.55 * s + 0.45 * v, infl) for k, v in BONDS.items()}
for k, r in PF.items():
    log(f"  {k:6s} " + "; ".join(f"{w_} {pct(E.window_loss(r, w_))}" for w_ in E.WINDOWS)
        + f"; return {pct(E.ann(r))}/yr; worst drawdown 1970 on {pct(E.max_dd(r))}")
for k in [x for x in ["1-3y", "20y+"] if PF]:
    br = E.bond_rule(PF["7-10y"], PF[k])
    log(f"  {k} vs 7-10y: worse growth-crash loss {pts(br['growth'])}, worse inflation-crash loss {pts(br['infl'])}, "
        f"cost {pts(br['cost'])}/yr -> {'CHANGE BOND FUND' if br['pass'] else 'not supported'}")
if PF:
    log("  Supplement (information only): actual funds from 2002, 55% stocks / 45% fund, after inflation:")
for tk in ["SHY", "IEF", "TLT"] if PF else []:
    try:
        r = E.contiguous(E.real((0.55 * s + 0.45 * etf[tk].reindex(v2.index)).dropna(), infl), tk)
        log(f"    {tk}: " + "; ".join(f"{w_} {pct(E.window_loss(r, w_))}" for w_ in ["2007-09", "2022"]))
    except ValueError as e:
        log(f"    {tk}: skipped ({e})")
if PF:
    log("  Note: the bond model has no convexity term, so it slightly understates long-bond returns when rates")
    log("  move a lot (1970s-80s, 2022); results close to the 1-point bar should be read with that in mind.")

log("\nNotes: history holds few independent crashes, so every result rests on a handful of episodes. CPI before 1983")
log("counted mortgage rates in housing costs and overstates 1970s inflation somewhat. AQR series are hypothetical")
log("index returns before costs (costs deducted here as stated). Monthly rebalancing throughout; 2B-H compares rules.")
finish()
