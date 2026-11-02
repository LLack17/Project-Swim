# Known-answer checks for the long-term compounder screen, on made-up numbers only.
# Usage, from the repo root:  python scripts/phase3/test_compounder.py
import sys
import numpy as np
import pandas as pd

sys.path.insert(0, "scripts/phase3")
import compounder_engine as C  # noqa: E402

results = []


def check(name, cond):
    results.append((name, bool(cond)))
    print(f"{'ok  ' if cond else 'FAIL'} {name}")


RUN = "2026-11-02"
DATES = [f"{2025 - k}-12-31" for k in range(11)]


def co(rev0=100.0, g=0.12, oi_margin=0.25, gm=0.6, debt=50.0, eq=None, cash=60.0, ocf_m=0.22, capex_m=0.04,
       sh0=100.0, sh_g=0.0, ebitda_m=0.30, sbc=2.0, override=None):
    """11 years newest first; revenue grows g a year (newest = rev0 * (1+g)^10)."""
    inc, bal, cf = [], [], []
    for k in range(11):
        r = rev0 * (1 + g) ** (10 - k)
        inc.append({"date": DATES[k], "revenue": r, "operatingIncome": r * oi_margin, "incomeBeforeTax": r * oi_margin,
                    "incomeTaxExpense": r * oi_margin * 0.21, "grossProfit": r * gm, "ebitda": r * ebitda_m,
                    "weightedAverageShsOutDil": sh0 * (1 + sh_g) ** (10 - k)})
        bal.append({"date": DATES[k], "totalDebt": debt, "totalStockholdersEquity": (0.6 * r if eq is None else eq),
                    "cashAndShortTermInvestments": cash})
        cf.append({"date": DATES[k], "operatingCashFlow": r * ocf_m, "capitalExpenditure": -r * capex_m,
                   "stockBasedCompensation": sbc})
    if override:
        override(inc, bal, cf)
    return inc, bal, cf


inc, bal, cf = co()
rev0 = inc[0]["revenue"]
m = C.metrics(inc, bal, cf, [3.0] * 10, market_cap=3.0 * rev0 - 50 + 60 - 0, run_date=RUN)
check("not missing", not m["missing"])
check("10-yr growth = 12%", abs(m["cagr10"] - 0.12) < 1e-9 and m["up_years"] == 10)
r0, r1_ = inc[0]["revenue"], inc[1]["revenue"]
roic0 = r0 * 0.25 * 0.79 / (((0.6 * r0 - 10) + (0.6 * r1_ - 10)) / 2)
check("ROIC all 10 years above 15%; latest = NOPAT / avg invested capital", m["roic_years_15"] == 10 and m["roic_median"] > 0.15 and roic0 > 0.30)
check("FCF positive all 10 years", m["fcf_pos_years"] == 10)
check("growth estimate = (12% + 5%) / 2", abs(m["growth_est"] - 0.085) < 1e-12)
check("EV/sales today = median -> drift 0", abs(m["drift"]) < 1e-9)
fy = (rev0 * 0.18 - 2.0 * 0.79) / (3.0 * rev0 + 10)
check("FCF yield after stock pay", abs(m["fcf_yield"] - fy) < 1e-12)
check("expected return = yield + growth + drift", abs(m["exp_return"] - (fy + 0.085)) < 1e-12)
check("base company passes all 7", m["pass"])

check("rule 1: 9% growth fails", not C.metrics(*co(g=0.09), [3.0] * 10, 3 * rev0, RUN)["r1"])
def two_down(inc, bal, cf):
    inc[2]["revenue"] = inc[3]["revenue"] * 0.95; inc[5]["revenue"] = inc[6]["revenue"] * 0.95; inc[7]["revenue"] = inc[8]["revenue"] * 0.97
m3 = C.metrics(*co(override=two_down), [3.0] * 10, 3 * rev0, RUN)
check("rule 1: 3 down years (7 of 10 up) fails", not m3["r1"] and m3["up_years"] == 7)
check("rule 2: 5% operating margin -> ROIC under 15% -> fails", not C.metrics(*co(oi_margin=0.05), [3.0] * 10, 3 * rev0, RUN)["r2"])
def gm_drop(inc, bal, cf):
    inc[0]["grossProfit"] = inc[0]["revenue"] * 0.50
check("rule 3: gross margin 10 pts below average fails", not C.metrics(*co(override=gm_drop), [3.0] * 10, 3 * rev0, RUN)["r3"])
inc_n, bal_n, cf_n = co(gm=1.0)
mm = C.metrics(inc_n, bal_n, cf_n, [3.0] * 10, 3 * rev0, RUN)
check("rule 3: no cost-of-revenue line -> not measurable, passes", mm["r3"] and mm["gm_note"] == "not measurable")
def neg_fcf(inc, bal, cf):
    for k in (1, 3, 5): cf[k]["capitalExpenditure"] = -cf[k]["operatingCashFlow"] * 2
check("rule 4: 3 negative FCF years fails", not C.metrics(*co(override=neg_fcf), [3.0] * 10, 3 * rev0, RUN)["r4"])
e0 = rev0 * 0.30
check("rule 5: net debt 2.0x EBITDA passes", C.metrics(*co(debt=60 + 2 * e0), [3.0] * 10, 3 * rev0, RUN)["r5"])
check("rule 5: net debt 2.1x fails", not C.metrics(*co(debt=60 + 2.1 * e0), [3.0] * 10, 3 * rev0, RUN)["r5"])
check("rule 6: shares +2.5%/yr fails", not C.metrics(*co(sh_g=0.025), [3.0] * 10, 3 * rev0, RUN)["r6"])
check("rule 6: shares +1.5%/yr passes", C.metrics(*co(sh_g=0.015), [3.0] * 10, 3 * rev0, RUN)["r6"])
mx = C.metrics(*co(), [1.5] * 10, 3 * rev0 + 10, RUN)
check("rule 7: EV/sales 3.0 vs median 1.5 -> drift = 0.5^(1/10)-1", abs(mx["drift"] - (0.5 ** 0.1 - 1)) < 1e-6)
mexp = C.metrics(*co(), [3.0] * 10, 30 * rev0, RUN)
check("rule 7: very expensive (30x sales) -> return under 9% fails", not mexp["r7"])
check("growth estimate capped at 15%", abs(C.metrics(*co(g=0.40), [3.0] * 10, 3 * rev0 * 30, RUN)["growth_est"] - 0.15) < 1e-12)
check("negative invested capital with profits -> counts as above 15%",
      C.metrics(*co(eq=-500), [3.0] * 10, 3 * rev0, RUN)["roic_years_15"] == 10)
check("only 10 years of statements -> missing", C.metrics(inc[:10], bal[:10], cf[:10], [3.0] * 10, 3 * rev0, RUN)["missing"])
check("stale latest year -> missing", C.metrics(*co(), [3.0] * 10, 3 * rev0, "2027-06-30")["missing"])
check("fewer than 5 EV/sales years -> missing", C.metrics(*co(), [3.0] * 4, 3 * rev0, RUN)["missing"])
p, cg, up = C.cagr_rule(inc, RUN)
check("prefilter agrees with rule 1", p and abs(cg - 0.12) < 1e-9)
u = pd.DataFrame({"sector": ["Financial Services", "Financial Services", "Financial Services", "Real Estate", "Technology"],
                  "industry": ["Financial - Credit Services", "Banks - Regional", "Financial - Data & Stock Exchanges", "REIT", "Software"]})
check("universe: payments and exchanges in; banks and REITs out", list(C.universe_filter(u).index) == [0, 2, 4])
d = pd.DataFrame({"symbol": list("ABC"), "roic_median": [0.40, 0.20, 0.30], "growth_sd": [0.05, 0.02, 0.10],
                  "exp_return": [0.10, 0.12, 0.14]})
s = C.score(d)
check("score: half durability, half return", abs(s.set_index("symbol").score["A"] - ((100 + 66.6667) / 2 + 33.3333) / 2) < 1e-3)

bad = [n for n, ok in results if not ok]
print(f"\n{len(results) - len(bad)}/{len(results)} passed")
sys.exit(1 if bad else 0)
