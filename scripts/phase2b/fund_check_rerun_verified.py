# Managed-futures fund RE-CHECK, DATA-VERIFIED: same as fund_check_rerun.py, plus the pre-registered by-hand check of
# calendar-year returns against published figures. Usage, from the repo root:
#     python scripts/phase2b/fund_check_rerun_verified.py
# Output: data/phase2b/fund_check_rerun_verified_results.txt
#
# Why: fund_check_rerun.py showed KMLM 2022 at +24.2% (Yahoo), but published 2022 total return is +30.4% (ETF Replay
# +30.37%, mutualfunds.com +30.4%, AAII NAV +30.5%). KMLM paid a $4.04 distribution in Dec 2022; some data sources
# record $2.48, which fits a mis-adjusted Dec-2022 Yahoo return. Fix (fixed before this script ran): scale KMLM's
# Dec-2022 monthly return so its 2022 total matches the published +30.37%. All other KMLM years and all DBMF years
# matched published figures within 0.1 pt; WTMF/FMF fail far from the bar either way. Nothing else changes.
#
# Rule: docs/phase2b_research_plan.md, amendment 2026-11-11 "Managed-futures fund re-check", committed before this
# script and before any WTMF/FMF data was pulled. Same index, same pass bar and same choice rule as fund_check.py
# (amendment 2026-10-27); only the candidate list changes. Candidates: DBMF, KMLM, WTMF, FMF. A fund must also have
# passed an order preview in the IBKR paper account (TRADEABLE below, filled from Landon's previews before the run).
# AQMIX is shown for reference only: it failed the order preview on 2026-11-11 and cannot be chosen.
import os
import sys
import pandas as pd

sys.path.insert(0, "scripts/phase2b")
from common2b import OUT, aqr_tsmom, french  # noqa: E402
from common import yf_close  # noqa: E402
import mix_engine as E  # noqa: E402

FUNDS = ["DBMF", "KMLM", "WTMF", "FMF"]
REFERENCE = ["AQMIX"]                                              # shown, never chosen
LAUNCH = {"AQMIX": "2010-01", "DBMF": "2019-05", "KMLM": "2020-12", "WTMF": "2011-01", "FMF": "2013-08"}
# Order preview in the IBKR paper account (DUT162870), filled in from Landon's previews BEFORE the run:
TRADEABLE = {"DBMF": True, "KMLM": True, "WTMF": True, "FMF": True}   # all four previews accepted 2026-11-11
RESULTS = f"{OUT}/fund_check_rerun_verified_results.txt"
# Published calendar-year total returns used to correct mis-adjusted Yahoo years (fund: {year: return})
PUBLISHED = {"KMLM": {2022: 0.3037}}
lines = []


def log(s=""):
    print(s)
    lines.append(s)


def finish():
    os.makedirs(OUT, exist_ok=True)
    with open(RESULTS, "w") as f:
        f.write("\n".join(lines) + "\n")
    print(f"\nSaved {RESULTS}")


def _on_error(exc_type, exc, tb):
    if exc_type is not SystemExit:
        log(f"\nERROR, script stopped: {exc_type.__name__}: {exc}")
        finish()
    sys.__excepthook__(exc_type, exc, tb)


sys.excepthook = _on_error

rf = french("F-F_Research_Data_Factors")[4] / 100
tsmom = aqr_tsmom()["TSMOM"]
index_r = (tsmom + rf - 0.01 / 12).dropna()
if any(v is None for v in TRADEABLE.values()):
    raise ValueError("Fill TRADEABLE from the IBKR order previews before running")
ALL = FUNDS + REFERENCE
px = yf_close(ALL, "2009-01-01")
px = px.reindex(columns=ALL).groupby(level=0).last()       # last real value per fund per month-end
for f in ALL:
    first = px[f].first_valid_index()
    if first is None or first > pd.Timestamp(LAUNCH[f]) + pd.offsets.MonthEnd(3):
        raise ValueError(f"{f}: no data or data starts well after launch ({first}); download problem")

log("MANAGED-FUTURES FUND RE-CHECK, AQMIX NOT TRADEABLE, DATA-VERIFIED (sets 5% or 10%)")
log("=" * 100)
log(f"Index: AQR official trend factor + T-bill - 1.0 pt/yr, {index_r.index[0]:%Y-%m} to {index_r.index[-1]:%Y-%m}")
log("Pass = at least 60 months, correlation 0.7+ AND annual return at most 1.0 pt/yr below the index (same months);")
log("only funds that passed the IBKR order preview can be chosen\n")
RET = {}
for f in ALL:
    r = E.chg(px[f].dropna()).dropna()         # first return = launch-month close to the next month-end
    for yr_, pub in PUBLISHED.get(f, {}).items():
        dec = pd.Timestamp(f"{yr_}-12-31")
        yahoo = float((1 + r[str(yr_)]).prod() - 1)
        r.loc[dec] = (1 + r.loc[dec]) * (1 + pub) / (1 + yahoo) - 1
        log(f"  DATA FIX {f} {yr_}: Yahoo {yahoo * 100:+.1f}% -> published {pub * 100:+.1f}% (Dec-{yr_} return scaled)")
    RET[f] = r
log("")
res = {}
for f in ALL:
    r = RET[f][:index_r.index[-1]]
    res[f] = E.fund_rule(r, index_r)
    x = res[f]
    if not x["eligible"]:
        log(f"  {f:6s} {x['n']} months: NOT ELIGIBLE (needs 60)")
        continue
    log(f"  {f:6s} {x['start']:%Y-%m} to {x['end']:%Y-%m} ({x['n']} months): correlation {x['corr']:.2f}, "
        f"lags the index by {x['lag'] * 100:+.2f} pts/yr -> {'PASS' if x['pass_'] else 'fail'}"
        + ("  [reference only: not tradeable]" if f in REFERENCE else
           ("" if TRADEABLE[f] else "  [NOT TRADEABLE: excluded]")))
log("\nCalendar-year total returns (compare by hand with each fund's published returns before accepting; Yahoo has")
log("mis-adjusted mutual-fund distributions in the past):")
for f in ALL:
    r = RET[f]
    yr = (1 + r).groupby(r.index.year).prod() - 1
    full = r.groupby(r.index.year).size() == 12
    log(f"  {f:6s} " + ", ".join(f"{y} {v * 100:+.1f}%" for y, v in yr[full].items()))
w, pick = E.fund_choice({f: res[f] for f in FUNDS if TRADEABLE[f]})
log(f"\nRESULT: managed futures {int(w * 100)}%"
    + (f" using {pick}" if pick else " (no eligible fund: fund choice needs another look before launch)"))
if w == 0.10:
    log("  Portfolio: 49.5% US stocks / 40.5% Treasuries 7-10y / 10% managed futures")
else:
    log("  Portfolio: 52.25% US stocks / 42.75% Treasuries 7-10y / 5% managed futures")
log("\nNotes: fund histories are short (5-16 years) and cover one inflation shock (2022); the comparison checks whether a")
log("real fund delivers the index, not whether trend-following works (2B-A tested that). Yahoo adjusted closes include")
log("distributions; the index is hypothetical and charged a 1.0 pt/yr fee. Each fund starts with its first full month")
log("after launch; '5 years' is counted as months overlapping the index (for these funds the same as by the check date).")
finish()
