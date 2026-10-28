# One-off check (judgment, not a rule): Boyd Gaming without its FanDuel gain.
# Boyd sold its 5% FanDuel stake in Q3 2025 and booked a $1.4B after-tax gain (Q3 2026 release, via
# https://www.gaming.net/boyd-gaming-q3-net-income-falls-against-fanduel-boosted-prior-year/).
# Where the gain sits in FMP's FY2025 numbers: NOT in operating income (it is in other income, $1.45B), NOT in
# operating cash flow (removed as a non-cash item), but IN net income, IN FMP's EBITDA ($2.79B vs operating income +
# D&A of $1.18B) and IN book equity (retained earnings). So of the screen's measures, only book-to-price, quality
# (profit / equity) and net debt / EBITDA can be affected. This check removes it: equity minus the $1.4B after-tax
# gain, EBITDA = operating income + D&A. Everyone else keeps the screen's numbers.
# Usage, from the repo root:  python scripts/phase3/recheck_byd.py   -> data/phase3/recheck_byd_results.txt
import sys
import pandas as pd

sys.path.insert(0, "scripts/phase3")
import screen_engine as S  # noqa: E402
import sources as D  # noqa: E402

RUN, GAIN_AFTER_TAX = "2026-10-27", 1.4e9
lines = []


def log(s=""):
    print(s)
    lines.append(s)


def statements(sym):
    key = lambda x: x.get("date", "")  # noqa: E731
    return [sorted(D.fmp(e, symbol=sym, period="annual", limit=3) or [], key=key, reverse=True)
            for e in ["income-statement", "balance-sheet-statement", "cash-flow-statement"]]


SC = pd.read_csv("data/phase3/screen_scores.csv")
rows, st = [], {}
for r in SC.itertuples():
    inc, bal, cf = st[r.symbol] = statements(r.symbol)
    m = S.company_metrics(inc, bal, cf, r.marketCap, run_date=RUN)
    vol, _ = S.price_stats(pd.read_csv(f"data/phase3/raw/yahoo/{RUN}/{r.symbol}.csv", index_col=0, parse_dates=True))
    rows.append({"symbol": r.symbol, "sector": r.sector, "volatility": vol,
                 **{k: m[k] for k in ["book_to_price", "earnings_yield", "fcf_yield", "op_profitability", "net_debt_ebitda"]}})
M = pd.DataFrame(rows)
base = S.score(M)
gap = (base.merge(SC[["symbol", "combined"]], on="symbol", suffixes=("", "_c")).eval("combined - combined_c").abs().max())
if gap > 1e-6:
    raise SystemExit(f"could not reproduce the screen's scores (max gap {gap})")
inc, bal, cf = st["BYD"]
i0, b0 = inc[0], bal[0]
mc = float(SC.loc[SC.symbol == "BYD", "marketCap"].iloc[0])
eq = b0["totalStockholdersEquity"] - GAIN_AFTER_TAX
ebitda = i0["operatingIncome"] + i0["depreciationAndAmortization"]
M2 = M.copy()
k = M2.symbol == "BYD"
M2.loc[k, "book_to_price"] = eq / mc
M2.loc[k, "op_profitability"] = S.op_profit(i0) / eq
M2.loc[k, "net_debt_ebitda"] = (b0["totalDebt"] - b0["cashAndShortTermInvestments"]) / ebitda
new = S.score(M2)
log("BOYD GAMING RECHECK (judgment check, not a rule): screen numbers vs numbers without the FanDuel gain")
log("=" * 100)
log(f"Reproduced the screen's scores for all {len(M)} companies (max gap {gap:.1e}).")
log(f"  equity {b0['totalStockholdersEquity'] / 1e9:.2f}B -> {eq / 1e9:.2f}B; EBITDA {i0['ebitda'] / 1e9:.2f}B -> {ebitda / 1e9:.2f}B; "
    f"net debt / EBITDA {M.loc[k, 'net_debt_ebitda'].iloc[0]:.2f} -> {M2.loc[k, 'net_debt_ebitda'].iloc[0]:.2f} (limit 3.00)")
log("  operating income, free cash flow and price volatility are unchanged (the gain is not in them)")
for lab, df in [("screen", base), ("without the gain", new)]:
    t = df[df.symbol == "BYD"].iloc[0]
    rank = int((df.combined > t.combined).sum()) + 1
    sub = df.copy()
    sub["bp_rank"] = S.pct_rank(sub.book_to_price)
    log(f"  {lab:18s} book/price rank {sub.loc[sub.symbol == 'BYD', 'bp_rank'].iloc[0]:5.1f}  value {t.value:5.1f}  "
        f"quality {t.quality:5.1f}  low vol {t.low_vol:5.1f}  score {t.combined:5.1f}  rank {rank} of {len(df)}")
with open("data/phase3/recheck_byd_results.txt", "w") as f:
    f.write("\n".join(lines) + "\n")
