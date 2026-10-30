# Known-answer checks for the growth screen functions, on made-up numbers only.
# Usage, from the repo root:  python scripts/phase3/test_growth.py
import sys
import numpy as np
import pandas as pd

sys.path.insert(0, "scripts/phase3")
import growth_engine as E  # noqa: E402

results = []


def check(name, cond):
    results.append((name, bool(cond)))
    print(f"{'ok  ' if cond else 'FAIL'} {name}")


RUN = "2026-11-01"
QDATES = [str(d.date()) for d in pd.date_range(end="2026-09-30", periods=8, freq="QE")][::-1]
ADATES = ["2025-12-31", "2024-12-31", "2023-12-31", "2022-12-31"]


def company(rev_a=(200, 160, 128, 100), shares=(100, 100, 100, 100), q_rev=(65, 60, 55, 50, 50, 45, 40, 35),
            gm=0.7, ebitda=10, ocf=10, capex=2, debt=50, cash=100, cogs_zero=False):
    inc_a = [{"date": d, "revenue": r, "weightedAverageShsOutDil": s} for d, r, s in zip(ADATES, rev_a, shares)]
    inc_q = [{"date": d, "revenue": r, "grossProfit": r if cogs_zero else r * gm, "ebitda": ebitda}
             for d, r in zip(QDATES, q_rev)]
    cf_q = [{"date": d, "operatingCashFlow": ocf, "capitalExpenditure": -capex} for d in QDATES]
    bal = {"date": QDATES[0], "totalDebt": debt, "cashAndShortTermInvestments": cash}
    return inc_a, inc_q, cf_q, bal


# base company: annual 100 -> 200 over 3 yrs (CAGR 25.99%); TTM 230 vs prior 170 (+35.3%); FCF 8/q -> 32/230
a = company()
m = E.metrics(*a, market_cap=2000, run_date=RUN)
check("not missing", not m["missing"])
check("3-yr growth = 2^(1/3)-1", abs(m["cagr3"] - (2 ** (1 / 3) - 1)) < 1e-9)
check("TTM growth = 230/170-1", abs(m["ttm_growth"] - (230 / 170 - 1)) < 1e-9)
check("gross margin 70%", abs(m["gross_margin"] - 0.7) < 1e-9)
check("FCF margin = 32/230", abs(m["fcf_margin"] - 32 / 230) < 1e-9)
check("Rule of 40 = growth + FCF margin", abs(m["rule40"] - (230 / 170 - 1 + 32 / 230)) < 1e-9)
check("EV = 2000 + 50 - 100", abs(m["ev"] - 1950) < 1e-9)
check("valuation ratio = (1950/230)/(35.29)", abs(m["val_ratio"] - (1950 / 230) / ((230 / 170 - 1) * 100)) < 1e-9)
check("base passes all", m["pass"])

# 1. slow 3-year growth fails f1 only
m = E.metrics(*company(rev_a=(130, 120, 110, 100)), market_cap=2000, run_date=RUN)
check("3-yr growth 9% fails f1", not m["f1"] and m["f2"])
# 2. TTM growth just under 15% fails
m = E.metrics(*company(q_rev=(57, 57, 57, 59, 50, 50, 50, 50)), market_cap=1000, run_date=RUN)
check("TTM growth 15% boundary: 230/200 passes", m["f2"])
m = E.metrics(*company(q_rev=(57, 57, 57, 58, 50, 50, 50, 50)), market_cap=1000, run_date=RUN)
check("TTM growth 14.5% fails", not m["f2"])
# 3. gross margin
check("gross margin 39% fails", not E.metrics(*company(gm=0.39), market_cap=2000, run_date=RUN)["f3"])
check("gross margin reported as 100% -> missing", E.metrics(*company(cogs_zero=True), market_cap=2000, run_date=RUN)["missing"])
# 5. cash flow, loose: -5% and improving passes; -5% and worsening fails; -12% improving fails
inc_a, inc_q, cf_q, bal = company()
cf = [{"date": d, "operatingCashFlow": (-3 if k < 4 else -5), "capitalExpenditure": 0} for k, d in enumerate(QDATES)]
m = E.metrics(inc_a, inc_q, cf, bal, 2000, RUN)
check("FCF -5.2% and improving passes f5", m["f5"])
cf = [{"date": d, "operatingCashFlow": (-3 if k < 4 else 0), "capitalExpenditure": 0} for k, d in enumerate(QDATES)]
check("FCF -5.2% and worsening fails f5", not E.metrics(inc_a, inc_q, cf, bal, 2000, RUN)["f5"])
cf = [{"date": d, "operatingCashFlow": (-7 if k < 4 else -9), "capitalExpenditure": 0} for k, d in enumerate(QDATES)]
check("FCF -12% even if improving fails f5", not E.metrics(inc_a, inc_q, cf, bal, 2000, RUN)["f5"])
# 6. debt: net debt 2x EBITDA boundary (EBITDA ttm 40)
check("net debt 80 = 2.0x passes", E.metrics(*company(debt=180, cash=100), market_cap=2000, run_date=RUN)["f6"])
check("net debt 81 fails", not E.metrics(*company(debt=181, cash=100), market_cap=2000, run_date=RUN)["f6"])
check("negative EBITDA with net debt fails", not E.metrics(*company(ebitda=-1, debt=200, cash=100), market_cap=2000, run_date=RUN)["f6"])
check("negative EBITDA with net cash passes", E.metrics(*company(ebitda=-1), market_cap=2000, run_date=RUN)["f6"])
# 7. dilution: 100 -> 110 over 3 yrs = 3.23%/yr fails; 100 -> 109 = 2.91% passes
check("dilution 3.2%/yr fails", not E.metrics(*company(shares=(110, 105, 102, 100)), market_cap=2000, run_date=RUN)["f7"])
check("dilution 2.9%/yr passes", E.metrics(*company(shares=(109, 105, 102, 100)), market_cap=2000, run_date=RUN)["f7"])
# 8. valuation: growth 35.29% -> limit EV/sales 28.24 -> EV 6494 (EV = market cap - 50 net cash); 6600 fails, 6400 passes
check("valuation over 0.8 fails", not E.metrics(*company(), market_cap=6600, run_date=RUN)["f8"])
check("valuation under 0.8 passes", E.metrics(*company(), market_cap=6400, run_date=RUN)["f8"])
check("EV at or below zero passes valuation", E.metrics(*company(debt=0, cash=3000), market_cap=2000, run_date=RUN)["f8"])
# consistency
inc_a, inc_q, cf_q, bal = company()
check("stale latest quarter -> missing", E.metrics(inc_a, inc_q, cf_q, bal, 2000, "2027-06-30")["missing"])
check("cash-flow quarters not matching -> missing",
      E.metrics(inc_a, inc_q, cf_q[1:] + [cf_q[0]], bal, 2000, RUN)["missing"])
check("missing gross profit and cost -> missing",
      E.metrics(inc_a, [{**x, "grossProfit": None} for x in inc_q], cf_q, bal, 2000, RUN)["missing"])
check("cost of revenue used when gross profit absent",
      not E.metrics(inc_a, [{**{k: v for k, v in x.items() if k != "grossProfit"}, "costOfRevenue": -x["revenue"] * 0.3}
                            for x in inc_q], cf_q, bal, 2000, RUN)["missing"])
# score
d = pd.DataFrame({"symbol": ["A", "B", "C"], "rule40": [0.6, 0.5, 0.4], "val_ratio": [0.7, 0.2, 0.5]})
s = E.score(d)
check("score: B best = (66.7 + 100) / 2", s.symbol.iloc[0] == "B" and abs(s.growth_score.iloc[0] - 250 / 3) < 1e-6)
check("score ranks: C last", s.symbol.iloc[-1] == "C")

bad = [n for n, ok in results if not ok]
print(f"\n{len(results) - len(bad)}/{len(results)} passed")
sys.exit(1 if bad else 0)
