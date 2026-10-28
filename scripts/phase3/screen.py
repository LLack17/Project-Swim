# Phase 3 stock screen. Rules: docs/phase3_screen_rules.md (fixed 2026-10-28, before any data was pulled).
# Usage, from the repo root (needs the FMP Starter plan for about 4,000-5,000 calls, plus SEC_USER_AGENT in .env):
#   python scripts/phase3/screen.py
# Output: data/phase3/screen_results.txt (summary + shortlist) and data/phase3/screen_scores.csv (ranks and filter
# results for every company that reached the scoring step). Raw downloads are cached in data/phase3/raw/
# (git-ignored), so a rerun after an interruption continues where it stopped.
#
# Data check first: FMP's numbers for three large companies are compared with their 10-K filings on SEC EDGAR
# (latest fiscal year both have). Revenue and net income must match within 2% for all three, or the screen stops.
import datetime
import os
import sys
import numpy as np
import pandas as pd

sys.path.insert(0, "scripts/phase3")
import screen_engine as S  # noqa: E402
import edgar_engine as G  # noqa: E402
import sources as D  # noqa: E402

OUT = "data/phase3"
CHECK_COMPANIES = ["MSFT", "PG", "CAT"]
lines = []


def log(s=""):
    print(s)
    lines.append(s)


def finish():
    os.makedirs(OUT, exist_ok=True)
    with open(f"{OUT}/screen_results.txt", "w") as f:
        f.write("\n".join(lines) + "\n")
    print(f"\nSaved {OUT}/screen_results.txt")


def _on_error(exc_type, exc, tb):
    if exc_type is not SystemExit:
        log(f"\nERROR, screen stopped: {exc_type.__name__}: {exc}")
        finish()
    sys.__excepthook__(exc_type, exc, tb)


sys.excepthook = _on_error


def statements(sym):
    inc = D.fmp("income-statement", symbol=sym, period="annual", limit=3)
    bal = D.fmp("balance-sheet-statement", symbol=sym, period="annual", limit=3)
    cf = D.fmp("cash-flow-statement", symbol=sym, period="annual", limit=3)
    key = lambda x: x.get("date", "")  # noqa: E731
    return (sorted(inc or [], key=key, reverse=True), sorted(bal or [], key=key, reverse=True),
            sorted(cf or [], key=key, reverse=True))


log("PHASE 3 STOCK SCREEN")
log("=" * 100)
RUN = datetime.date.today()
log(f"Run date {RUN}; rules: docs/phase3_screen_rules.md (and amendment log)")

# ======================= DATA CHECK: FMP vs SEC EDGAR =======================
log("\nDATA CHECK: FMP vs the companies' own 10-K filings (SEC EDGAR), latest fiscal year both have")
ciks = D.sec_ciks()
bad = []
for sym in CHECK_COMPANIES:
    inc, bal, cf = statements(sym)
    table, used = G.company_table(D.sec_facts(ciks[sym]))
    if not inc or table.empty:
        bad.append(sym)
        log(f"  {sym}: no data")
        continue
    fmp_row = {**inc[0], **(bal[0] if bal else {}), **(cf[0] if cf else {})}
    end = pd.Timestamp(inc[0]["date"])
    near = table.index[(abs((table.index - end).days) <= 10)]
    if not len(near):
        bad.append(sym)
        log(f"  {sym}: FMP year {end.date()} not found in EDGAR")
        continue
    cc = G.cross_check(table.loc[near[0]].to_dict(), fmp_row)
    must = all(cc[k][3] for k in ["revenue", "net_income"])
    bad += [] if must else [sym]
    log(f"  {sym} {end.date()}: " + "; ".join(
        f"{k} {'n/a' if g is None else f'{g * 100:.1f}% gap'}" for k, (_, _, g, _) in cc.items())
        + f" -> {'OK' if must else ('FAIL (not found in the filings: cannot verify)' if any(cc[k][2] is None for k in ['revenue', 'net_income']) else 'FAIL (revenue or net income gap above 2%)')}")
    ltd = table.loc[near[0]].get("long_term_debt")
    log(f"      (information) FMP total debt {fmp_row.get('totalDebt', float('nan')) / 1e9:.1f}B vs 10-K long-term debt "
        f"{(ltd if ltd is not None and not pd.isna(ltd) else float('nan')) / 1e9:.1f}B; a large gap usually means FMP "
        f"counts leases or short-term debt in total debt")
if bad:
    raise ValueError(f"FMP data does not match the filings for {bad}; screen not run")

# ======================= UNIVERSE =======================
rows = []
for ex in ["NYSE", "NASDAQ", "AMEX"]:
    got = D.fmp("company-screener", cache_tag=str(RUN), marketCapMoreThan=int(2e9), country="US", exchange=ex,
                isEtf="false", isFund="false", isActivelyTrading="true", limit=10000) or []
    if len(got) >= 10000:
        raise ValueError(f"screener returned its row limit for {ex}: list may be cut off")
    rows += got
scr = pd.DataFrame(rows).drop_duplicates("symbol")
need = ["symbol", "companyName", "marketCap", "sector", "industry", "country", "isEtf", "isFund",
        "isActivelyTrading", "volume"]
miss = [c for c in need if c not in scr.columns]
if miss:
    raise ValueError(f"FMP screener fields missing: {miss}; available: {list(scr.columns)}")
U, steps = S.universe(scr)

log("\nUNIVERSE AND FILTERS (companies left after each step)")
for k, v in steps.items():
    log(f"  {k:52s} {v:6d}")

prices = D.yahoo_prices(U.symbol.tolist(), RUN)
no_px = [x for x in U.symbol if x not in prices]
if len(no_px) > 0.02 * len(U):
    raise ValueError(f"Yahoo returned no prices for {len(no_px)} of {len(U)} companies (over 2%): rerun later")
stats = {s: S.price_stats(prices[s]) if s in prices else (np.nan, np.nan) for s in U.symbol}
U["volatility"] = U.symbol.map(lambda s: stats[s][0])
U["dollar_volume"] = U.symbol.map(lambda s: stats[s][1])
n0 = len(U)
U = U[U.dollar_volume.notna() & U.volatility.notna()]
log(f"  {'price history available (Yahoo, 240+ days)':52s} {len(U):6d}   (removed {n0 - len(U)} as missing data)")
U = U[U.dollar_volume >= 20e6]
log(f"  {'average daily trading >= $20M (last 3 months)':52s} {len(U):6d}")

recs, missing, nonpos = [], 0, 0
for _, r in U.iterrows():
    inc, bal, cf = statements(r.symbol)
    m = S.company_metrics(inc, bal, cf, r.marketCap, run_date=RUN)
    if m["missing"]:
        missing += 1
        continue
    if m["equity"] <= 0:
        nonpos += 1
        continue
    recs.append({**r.to_dict(), **{k: v for k, v in m.items() if k != "missing"}})
M = pd.DataFrame(recs)
log(f"  {'statements complete, same years, recent':52s} {len(M) + nonpos:6d}   (removed {missing} as missing data)")
if M.empty:
    raise ValueError("no company has complete statements: check the FMP data")
log(f"  {'positive book equity':52s} {len(M):6d}")
for f_, lab in [("f_profits", "operating income > 0 in each of 3 years"), ("f_leverage", "net debt <= 3x EBITDA"),
                ("f_short_term", "short-term debt covered by cash + 1 yr cash flow"),
                ("f_cash", "3-yr cash flow >= 80% of 3-yr profit")]:
    M = M[M[f_]]
    log(f"  {lab:52s} {len(M):6d}")
M = M[M.op_profitability.notna()]
log(f"  {'operating profitability measurable':52s} {len(M):6d}")
if len(M) < 30:
    raise ValueError(f"only {len(M)} companies passed; the shortlist needs 30")

# ======================= SCORE AND SHORTLIST =======================
SC = S.score(M)
top = S.shortlist(SC)
log(f"\nSHORTLIST: top {len(top)} by combined score (value, quality, low volatility; 0-100), at most 4 per sector")
log("  (the portfolio itself holds at most 2 per sector: the 20% sector cap)")
log(f"  {'#':>3s} {'symbol':7s} {'company':34s} {'sector':24s} {'mkt cap':>9s} {'value':>6s} {'qual':>6s} {'lowvol':>6s} {'score':>6s}")
for k, r in top.iterrows():
    log(f"  {k + 1:3d} {r.symbol:7s} {str(r.companyName)[:34]:34s} {str(r.sector)[:24]:24s} {r.marketCap / 1e9:8.1f}B "
        f"{r.value:6.1f} {r.quality:6.1f} {r.low_vol:6.1f} {r.combined:6.1f}")
cols = ["symbol", "companyName", "sector", "industry", "marketCap", "value", "quality", "low_vol", "combined",
        "net_debt_ebitda", "cash_to_profit"]
os.makedirs(OUT, exist_ok=True)
SC.sort_values("combined", ascending=False)[cols].to_csv(f"{OUT}/screen_scores.csv", index=False)
log(f"\nAll {len(SC)} scored companies: {OUT}/screen_scores.csv")
log("\nNotes: FMP annual statements (latest 3 fiscal years as of the run date); market values from FMP on the run date;")
log("prices and trading volume from Yahoo (adjusted, cached by run date). EBIT = operating income. FMP total debt may")
log("include lease liabilities, which makes the leverage filter stricter for heavy lessees (retailers, restaurants).")
log("Spot-check unusually high quality ranks in the memos: FMP may show an unreported cost line as 0. The screen sources ideas only: every")
log("pick needs a full memo, a red-team review and Landon's approval, and is date-stamped in the repo before it is bought.")
finish()
