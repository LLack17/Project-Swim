# Long history for the narrowed-down companies, straight from their 10-K filings (SEC EDGAR, free), plus a check
# of FMP's numbers against the filings.
# Usage, from the repo root:  python scripts/phase3/edgar_history.py AAPL MSFT ...
# Needs SEC_USER_AGENT in .env (the SEC asks for a name and contact email); FMP_API_KEY is optional (cross-check).
# Output: data/phase3/edgar/<TICKER>.csv (annual figures from 10-Ks, public data) and
#         data/phase3/edgar/edgar_check.txt (which XBRL tag each number came from, and the FMP comparison).
import os
import sys
import pandas as pd

sys.path.insert(0, "scripts/phase3")
import edgar_engine as G  # noqa: E402
import sources as D  # noqa: E402

OUT = "data/phase3/edgar"
tickers = [t.upper() for t in sys.argv[1:]]
if not tickers:
    raise SystemExit("usage: python scripts/phase3/edgar_history.py TICKER [TICKER ...]")
os.makedirs(OUT, exist_ok=True)
ciks = D.sec_ciks()
lines = []


def log(s=""):
    print(s)
    lines.append(s)


for t in tickers:
    log("=" * 90)
    if t not in ciks:
        log(f"{t}: not found in the SEC ticker list")
        continue
    table, used = G.company_table(D.sec_facts(ciks[t]))
    if table.empty:
        log(f"{t}: no annual 10-K figures found")
        continue
    table.index.name = "fiscal_year_end"
    table.to_csv(f"{OUT}/{t}.csv")
    log(f"{t} (CIK {ciks[t]}): {len(table)} fiscal years, {table.index[0]:%Y-%m} to {table.index[-1]:%Y-%m} -> {OUT}/{t}.csv")
    log("  Tags used: " + "; ".join(f"{k}={v or 'NOT FOUND'}" for k, v in used.items()))
    show = table.iloc[-12:] / 1e9
    show.index = show.index.strftime("%Y-%m-%d")
    log("  Last 12 years, $ billions:")
    for line in show.round(2).to_string().splitlines():
        log("    " + line)
    if os.getenv("FMP_API_KEY"):
        inc = D.fmp("income-statement", symbol=t, period="annual", limit=5) or []
        bal = D.fmp("balance-sheet-statement", symbol=t, period="annual", limit=5) or []
        cf = D.fmp("cash-flow-statement", symbol=t, period="annual", limit=5) or []
        by = lambda rows: {r.get("date"): r for r in rows}  # noqa: E731
        bi, bb, bc = by(inc), by(bal), by(cf)
        log("  FMP vs filings (gap; OK = within 2%):")
        for d in sorted(bi, reverse=True):
            end = pd.Timestamp(d)
            near = table.index[abs((table.index - end).days) <= 10]
            if not len(near):
                log(f"    {d}: year not in EDGAR table")
                continue
            cc = G.cross_check(table.loc[near[0]].to_dict(), {**bi[d], **bb.get(d, {}), **bc.get(d, {})})
            log(f"    {d}: " + "; ".join(
                f"{k} {'n/a' if g is None else f'{g * 100:.1f}%' + ('' if ok else ' CHECK')}" for k, (_, _, g, ok) in cc.items()))
log("\nNotes: values are as filed in 10-Ks (latest filing wins for restated years). Companies sometimes change XBRL")
log("tags; a missing year or a 'CHECK' gap means look at the 10-K itself before using the number.")
with open(f"{OUT}/edgar_check.txt", "w") as f:
    f.write("\n".join(lines) + "\n")
print(f"\nSaved {OUT}/edgar_check.txt")
