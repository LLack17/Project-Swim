# Managed-futures live-fund check: sets managed futures at 5% or 10% and picks the fund.
# Usage, from the repo root:  python scripts/phase2b/fund_check.py
# Output: data/phase2b/fund_check_results.txt
#
# Rule: docs/phase2b_research_plan.md, amendment 2026-10-27 "Managed-futures fund check", written before any fund
# data was looked at. Candidate funds: AQMIX, DBMF, KMLM (US-listed, at least 5 years of monthly returns). Index =
# AQR's official trend factor (TSMOM) + T-bill (Ken French RF) - 1.0 pt/yr, the same index used in 2B-A and 2B-H.
# Each fund's monthly total return (Yahoo adjusted closes, so after the fund's own fees and with distributions
# reinvested) is compared with the index over the fund's whole live history up to the index's last month.
# Pass = correlation 0.7+ AND annual return at most 1.0 pt/yr below the index. Any pass -> 10% (49.5/40.5/10) with
# the passing fund of highest correlation; otherwise 5% with the eligible fund of highest correlation.
# Returns start with the first full month after launch (launch-month close to next month-end).
import os
import sys
import pandas as pd

sys.path.insert(0, "scripts/phase2b")
from common2b import OUT, aqr_tsmom, french  # noqa: E402
from common import yf_close  # noqa: E402
import mix_engine as E  # noqa: E402

FUNDS = ["AQMIX", "DBMF", "KMLM"]
LAUNCH = {"AQMIX": "2010-01", "DBMF": "2019-05", "KMLM": "2020-12"}     # launch months (fund documents)
RESULTS = f"{OUT}/fund_check_results.txt"
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
px = yf_close(FUNDS, "2009-01-01")
px = px.reindex(columns=FUNDS).groupby(level=0).last()       # last real value per fund per month-end
for f in FUNDS:
    first = px[f].first_valid_index()
    if first is None or first > pd.Timestamp(LAUNCH[f]) + pd.offsets.MonthEnd(3):
        raise ValueError(f"{f}: no data or data starts well after launch ({first}); download problem")

log("MANAGED-FUTURES LIVE-FUND CHECK (sets 5% or 10%)")
log("=" * 100)
log(f"Index: AQR official trend factor + T-bill - 1.0 pt/yr, {index_r.index[0]:%Y-%m} to {index_r.index[-1]:%Y-%m}")
log("Pass = at least 60 months, correlation 0.7+ AND annual return at most 1.0 pt/yr below the index (same months)\n")
res = {}
for f in FUNDS:
    p = px[f].dropna()
    r = E.chg(p).dropna()                      # first return = launch-month close to the next month-end
    r = r[:index_r.index[-1]]
    res[f] = E.fund_rule(r, index_r)
    x = res[f]
    if not x["eligible"]:
        log(f"  {f:6s} {x['n']} months: NOT ELIGIBLE (needs 60)")
        continue
    log(f"  {f:6s} {x['start']:%Y-%m} to {x['end']:%Y-%m} ({x['n']} months): correlation {x['corr']:.2f}, "
        f"lags the index by {x['lag'] * 100:+.2f} pts/yr -> {'PASS' if x['pass_'] else 'fail'}")
log("\nCalendar-year total returns (compare by hand with each fund's published returns before accepting; Yahoo has")
log("mis-adjusted mutual-fund distributions in the past):")
for f in FUNDS:
    r = E.chg(px[f].dropna()).dropna()
    yr = (1 + r).groupby(r.index.year).prod() - 1
    full = r.groupby(r.index.year).size() == 12
    log(f"  {f:6s} " + ", ".join(f"{y} {v * 100:+.1f}%" for y, v in yr[full].items()))
w, pick = E.fund_choice(res)
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
