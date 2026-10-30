# Phase 3 growth screen. Rules: docs/phase3_growth_screen_rules.md (fixed 2026-10-29, before any data was pulled).
# Usage, from the repo root (FMP Starter plan, roughly 2,000-2,500 calls; Yahoo for prices):
#   python scripts/phase3/growth_screen.py
# Output: data/phase3/growth_screen_results.txt (filter counts + top 30) and data/phase3/growth_screen_scores.csv
# (every company that reached the full checks, with each filter result). Raw downloads are cached in
# data/phase3/raw/ (git-ignored), so a rerun after an interruption continues where it stopped.
import datetime
import os
import sys
import numpy as np
import pandas as pd

sys.path.insert(0, "scripts/phase3")
import screen_engine as S  # noqa: E402
import growth_engine as E  # noqa: E402
import sources as D  # noqa: E402

OUT = "data/phase3"
RESEARCH_LIST = {"EHC", "GILD", "INGR", "CL", "BYD", "GNTX", "ITW", "AOS", "VNT", "EEFT", "CARG", "EOG", "SHW"}
FILTERS = [("f2", "TTM revenue growth >= 15%"), ("f3", "TTM gross margin >= 40%"),
           ("f4", "Rule of 40 (growth + FCF margin >= 40)"), ("f5", "FCF margin >= 0%, or >= -10% and improving"),
           ("f6", "net debt <= 2x TTM EBITDA (or net cash)"), ("f7", "diluted shares +3%/yr at most"),
           ("f8", "EV/sales per point of growth <= 0.8")]
lines = []


def log(s=""):
    print(s, flush=True)
    lines.append(s)


def finish():
    os.makedirs(OUT, exist_ok=True)
    with open(f"{OUT}/growth_screen_results.txt", "w") as f:
        f.write("\n".join(lines) + "\n")
    print(f"\nSaved {OUT}/growth_screen_results.txt")


def _on_error(exc_type, exc, tb):
    if exc_type is not SystemExit:
        log(f"\nERROR, screen stopped: {exc_type.__name__}: {exc}")
        finish()
    sys.__excepthook__(exc_type, exc, tb)


sys.excepthook = _on_error
key = lambda x: x.get("date", "")  # noqa: E731

log("PHASE 3 GROWTH SCREEN")
log("=" * 100)
RUN = datetime.date.today()
log(f"Run date {RUN}; rules: docs/phase3_growth_screen_rules.md")

# ======================= UNIVERSE (same as the quality screen) =======================
rows = []
for ex in ["NYSE", "NASDAQ", "AMEX"]:
    got = D.fmp("company-screener", cache_tag=str(RUN), marketCapMoreThan=int(2e9), country="US", exchange=ex,
                isEtf="false", isFund="false", isActivelyTrading="true", limit=10000) or []
    if len(got) >= 10000:
        raise ValueError(f"screener returned its row limit for {ex}: list may be cut off")
    rows += got
scr = pd.DataFrame(rows).drop_duplicates("symbol")
U, steps = S.universe(scr)
log("\nUNIVERSE (companies left after each step)")
for k, v in steps.items():
    log(f"  {k:52s} {v:6d}")
U = U[~U.companyName.map(S.is_partnership)]
log(f"  {'not a partnership':52s} {len(U):6d}")

# ======================= FILTER 1: 3-year revenue growth (annual statements) =======================
annual, f1_pass, missing1 = {}, [], 0
for i, r in enumerate(U.itertuples(index=False)):
    if i % 250 == 0:
        print(f"  annual statements {i}/{len(U)}", flush=True)
    inc = sorted(D.fmp("income-statement", symbol=r.symbol, period="annual", limit=4) or [], key=key, reverse=True)
    if len(inc) < 4 or any(x.get("revenue") in (None, 0) for x in inc[:4]) or inc[3]["revenue"] < 0:
        missing1 += 1
        continue
    annual[r.symbol] = inc
    if (inc[0]["revenue"] / inc[3]["revenue"]) ** (1 / 3) - 1 >= E.MIN_CAGR3 - E.EPS:
        f1_pass.append(r.symbol)
log(f"  {'4 years of annual revenue available':52s} {len(U) - missing1:6d}   (removed {missing1} as missing data)")
log(f"  {'3-yr revenue growth >= 20%/yr':52s} {len(f1_pass):6d}")

# ======================= FILTERS 2-8: quarterly statements =======================
recs, missing2 = [], 0
caps = U.set_index("symbol")
for sym in f1_pass:
    iq = sorted(D.fmp("income-statement", symbol=sym, period="quarter", limit=8) or [], key=key, reverse=True)
    cq = sorted(D.fmp("cash-flow-statement", symbol=sym, period="quarter", limit=8) or [], key=key, reverse=True)
    bq = sorted(D.fmp("balance-sheet-statement", symbol=sym, period="quarter", limit=1) or [], key=key, reverse=True)
    row = caps.loc[sym]
    m = E.metrics(annual[sym], iq, cq, bq[0] if bq else {}, float(row.marketCap), RUN)
    if m["missing"]:
        missing2 += 1
        continue
    recs.append({"symbol": sym, "companyName": row.companyName, "sector": row.sector, "industry": row.industry,
                 "marketCap": float(row.marketCap), **{k: v for k, v in m.items() if k != "missing"}})
M = pd.DataFrame(recs)
log(f"  {'8 quarters consistent and recent':52s} {len(M):6d}   (removed {missing2} as missing data)")
if M.empty:
    raise ValueError("no company has complete quarterly statements: check the FMP data")
left = M.copy()
for f_, lab in FILTERS:
    left = left[left[f_]]
    log(f"  {lab:52s} {len(left):6d}")

# ======================= LIQUIDITY (Yahoo), only for the survivors =======================
prices = D.yahoo_prices(left.symbol.tolist(), RUN)
stats = {s: S.price_stats(prices[s]) if s in prices else (np.nan, np.nan) for s in left.symbol}
left = left.assign(volatility=left.symbol.map(lambda s: stats[s][0]) * np.sqrt(252),
                   dollar_volume=left.symbol.map(lambda s: stats[s][1]))
n0 = len(left)
left = left[left.dollar_volume.notna()]
log(f"  {'price history available (Yahoo)':52s} {len(left):6d}   (removed {n0 - len(left)} as missing data)")
left = left[left.dollar_volume >= 20e6]
log(f"  {'average daily trading >= $20M (last 3 months)':52s} {len(left):6d}")
if left.empty:
    raise ValueError("no company passed every filter")

# ======================= SCORE =======================
SC = E.score(left)
top = SC.head(30)
log(f"\nTOP {len(top)} by growth score (average rank of Rule of 40 and valuation per point of growth; 0-100), no sector limit")
log(f"  {'#':>3s} {'symbol':7s} {'company':30s} {'sector':22s} {'mkt cap':>8s} {'3y gr':>6s} {'TTM gr':>6s} {'gross':>6s} "
    f"{'FCF m':>6s} {'R40':>5s} {'EV/S':>5s} {'val':>5s} {'vol':>5s} {'score':>6s}")
for k, r in top.iterrows():
    flag = " *" if r.symbol in RESEARCH_LIST else ""
    log(f"  {k + 1:3d} {r.symbol:7s} {str(r.companyName)[:30]:30s} {str(r.sector)[:22]:22s} {r.marketCap / 1e9:7.1f}B "
        f"{r.cagr3 * 100:5.0f}% {r.ttm_growth * 100:5.0f}% {r.gross_margin * 100:5.0f}% {r.fcf_margin * 100:5.0f}% "
        f"{r.rule40 * 100:5.0f} {r.ev_sales:5.1f} {r.val_ratio:5.2f} {r.volatility * 100:4.0f}% {r.growth_score:6.1f}{flag}")
log("  * already on the quality research list")
log("\nSector count in the top 30: " + ", ".join(f"{s} {n}" for s, n in top.sector.value_counts().items()))
cols = ["symbol", "companyName", "sector", "industry", "marketCap", "cagr3", "ttm_growth", "gross_margin", "fcf_margin",
        "fcf_margin_prior", "rule40", "net_debt_ebitda", "dilution", "ev_sales", "val_ratio"] + [f"f{k}" for k in range(1, 9)]
M.assign(passed_all=M.symbol.isin(SC.symbol)).merge(SC[["symbol", "volatility", "growth_score"]], on="symbol", how="left") \
    .sort_values("growth_score", ascending=False)[cols + ["passed_all", "volatility", "growth_score"]] \
    .to_csv(f"{OUT}/growth_screen_scores.csv", index=False)
log(f"\nAll {len(M)} companies that reached the full checks: {OUT}/growth_screen_scores.csv")
log("\nNotes: FMP statements (4 fiscal years; 8 quarters, TTM = last 4); market values from FMP on the run date;")
log("prices and volume from Yahoo (adjusted). Volatility is annualized and reported only. FMP total debt may include")
log("leases (stricter debt filter for heavy lessees). The screen sources ideas only: Landon cleans the top 10 (one-offs,")
log("corporate actions under the 10% standard), picks 4-5 for full research, and 2 enter the portfolio.")
finish()
