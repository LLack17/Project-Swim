# One-off check (judgment, not a rule): would AT&T still make the shortlist on numbers that include its 2026 deals?
# AT&T closed the Lumen fiber purchase (Feb 2, 2026) and the $23B EchoStar spectrum purchase (Q3 2026) after its
# fiscal 2025 year-end, so the screen's FY2025 balance sheet no longer describes it.
# Method: every other company keeps exactly the numbers the screen used. AT&T's FY2025 FMP numbers are moved to
# "now" by adding the change reported in its own Q3 2026 10-Q (same definitions as FMP, only the change is added):
#   balance sheet: Sep 30, 2026 minus Dec 31, 2025; flows: last 12 months = FY2025 + 9M 2026 - 9M 2025.
# Market value stays at the screen's run-date value, like everyone else's. Quality numerator (revenue minus costs,
# SG&A and interest) is not in the 10-Q summary, so it keeps FY2025 over the new equity (approximation, stated).
# Source: AT&T 10-Q for the quarter ended Sep 30, 2026,
#   https://www.sec.gov/Archives/edgar/data/0000732717/000073271726000372/t-20260930.htm  ($ millions)
# Usage, from the repo root:  python scripts/phase3/recheck_att.py   -> data/phase3/recheck_att_results.txt
import sys
import numpy as np
import pandas as pd

sys.path.insert(0, "scripts/phase3")
import screen_engine as S  # noqa: E402
import sources as D  # noqa: E402

M_ = 1e6
Q = {  # 10-Q figures, $ millions
    "op_income_9m": (17791, 18374), "da_9m": (14910, 15758), "net_income_9m": (9239, 18137),
    "ocf_9m": (28915, 28964), "capex_9m": (15638, 14061),
    "cash": (10767, 18234), "debt": (9483 + 150144, 9011 + 127089), "equity_att": (106775, 110533)}
RUN = "2026-10-27"
lines = []


def log(s=""):
    print(s)
    lines.append(s)


def statements(sym):
    key = lambda x: x.get("date", "")  # noqa: E731
    return [sorted(D.fmp(e, symbol=sym, period="annual", limit=3) or [], key=key, reverse=True)
            for e in ["income-statement", "balance-sheet-statement", "cash-flow-statement"]]


SC = pd.read_csv("data/phase3/screen_scores.csv")
rows, stmts = [], {}
for r in SC.itertuples():
    inc, bal, cf = statements(r.symbol)
    stmts[r.symbol] = (inc, bal, cf)
    m = S.company_metrics(inc, bal, cf, r.marketCap, run_date=RUN)
    px = pd.read_csv(f"data/phase3/raw/yahoo/{RUN}/{r.symbol}.csv", index_col=0, parse_dates=True)
    vol, _ = S.price_stats(px)
    rows.append({"symbol": r.symbol, "sector": r.sector, "marketCap": r.marketCap, "volatility": vol,
                 **{k: m[k] for k in ["book_to_price", "earnings_yield", "fcf_yield", "op_profitability",
                                      "net_debt_ebitda"]}})
M = pd.DataFrame(rows)
base = S.score(M)
chk = base.merge(SC[["symbol", "combined"]], on="symbol", suffixes=("", "_csv"))
gap = (chk.combined - chk.combined_csv).abs().max()
if gap > 1e-6:
    raise SystemExit(f"could not reproduce the screen's scores (max gap {gap}); stopping")
log("AT&T RECHECK (judgment check, not a rule): screen numbers vs numbers including the 2026 deals")
log("=" * 100)
log(f"Reproduced the screen's scores for all {len(M)} companies (max gap {gap:.1e}).")

inc, bal, cf = stmts["T"]
i0, b0, c0 = inc[0], bal[0], cf[0]
d = lambda k: (Q[k][0] - Q[k][1]) * M_  # noqa: E731
op = i0["operatingIncome"] + d("op_income_9m")
ebitda = i0["ebitda"] + d("op_income_9m") + d("da_9m")
debt = b0["totalDebt"] + d("debt")
cash = b0["cashAndShortTermInvestments"] + d("cash")
equity = b0["totalStockholdersEquity"] + d("equity_att")
fcf = (c0["operatingCashFlow"] + d("ocf_9m")) - (abs(c0["capitalExpenditure"]) + d("capex_9m"))
mc = float(SC.loc[SC.symbol == "T", "marketCap"].iloc[0])
old = M[M.symbol == "T"].iloc[0]
new = old.copy()
new["book_to_price"] = equity / mc
new["earnings_yield"] = op / (mc + debt - cash)
new["fcf_yield"] = fcf / mc
new["op_profitability"] = S.op_profit(i0) / equity
new["net_debt_ebitda"] = (debt - cash) / ebitda
log(f"\nFMP FY2025 ({i0['date']}) vs now (FY2025 moved forward by the 10-Q changes), $ billions:")
for lab, a, b in [("total debt", b0["totalDebt"], debt), ("cash", b0["cashAndShortTermInvestments"], cash),
                  ("equity", b0["totalStockholdersEquity"], equity), ("operating income (12 mo)", i0["operatingIncome"], op),
                  ("EBITDA (12 mo)", i0["ebitda"], ebitda),
                  ("free cash flow (12 mo)", c0["operatingCashFlow"] - abs(c0["capitalExpenditure"]), fcf)]:
    log(f"  {lab:28s} {a / 1e9:8.1f} -> {b / 1e9:8.1f}")
log(f"  {'net debt / EBITDA':28s} {old.net_debt_ebitda:8.2f} -> {new.net_debt_ebitda:8.2f}   (filter: at most 3.00)")
passes = new.net_debt_ebitda <= 3.0 + S.EPS
log(f"\nDebt filter now: {'PASS' if passes else 'FAIL: AT&T would be removed before scoring'}")

M2 = M.copy()
M2.loc[M2.symbol == "T", ["book_to_price", "earnings_yield", "fcf_yield", "op_profitability", "net_debt_ebitda"]] = \
    new[["book_to_price", "earnings_yield", "fcf_yield", "op_profitability", "net_debt_ebitda"]].values
new_sc = S.score(M2)
for lab, df in [("screen (FY2025)", base), ("now (with 2026 deals)" + ("" if passes else ", ignoring the filter"), new_sc)]:
    t = df[df.symbol == "T"].iloc[0]
    rank = int((df.combined > t.combined).sum()) + 1
    sl = S.shortlist(df.merge(SC[["symbol", "companyName"]], on="symbol"))
    pos = sl.index[sl.symbol == "T"]
    log(f"  {lab:45s} value {t.value:5.1f}  quality {t.quality:5.1f}  low vol {t.low_vol:5.1f}  "
        f"score {t.combined:5.1f}  rank {rank} of {len(df)}  shortlist: {'#' + str(pos[0] + 1) if len(pos) else 'not in top 30'}")
log("\nNotes: market value kept at the screen's run date (as for every company); the quality numerator stays at FY2025")
log("(not in the 10-Q summary). This is a judgment check for one company and changes no rule.")
with open("data/phase3/recheck_att_results.txt", "w") as f:
    f.write("\n".join(lines) + "\n")
