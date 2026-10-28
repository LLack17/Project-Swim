# Known-answer checks for the Phase 3 screen and EDGAR functions, on made-up numbers only.
# Usage, from the repo root:  python scripts/phase3/test_phase3.py
import sys
import numpy as np
import pandas as pd

sys.path.insert(0, "scripts/phase3")
import screen_engine as S  # noqa: E402
import edgar_engine as G  # noqa: E402

results = []


def check(name, cond):
    results.append((name, bool(cond)))
    print(f"{'ok  ' if cond else 'FAIL'} {name}")


def raises(f):
    try:
        f()
    except (ValueError, KeyError):
        return True
    return False


close = lambda a, b, t=1e-9: abs(a - b) < t  # noqa: E731

# 1. universe
scr = pd.DataFrame([
    dict(symbol="AAA", companyName="A Co", marketCap=5e9, sector="Technology", industry="Software", country="US",
         isEtf=False, isFund=False, isActivelyTrading=True, volume=100),
    dict(symbol="BBB", companyName="B Bank", marketCap=5e9, sector="Financial Services", industry="Banks", country="US",
         isEtf=False, isFund=False, isActivelyTrading=True, volume=100),
    dict(symbol="CCC", companyName="C Small", marketCap=1.9e9, sector="Industrials", industry="Tools", country="US",
         isEtf=False, isFund=False, isActivelyTrading=True, volume=100),
    dict(symbol="DDD", companyName="D Foreign", marketCap=5e9, sector="Industrials", industry="Tools", country="GB",
         isEtf=False, isFund=False, isActivelyTrading=True, volume=100),
    dict(symbol="EEE-P", companyName="E Pref", marketCap=5e9, sector="Utilities", industry="Power", country="US",
         isEtf=False, isFund=False, isActivelyTrading=True, volume=100),
    dict(symbol="FFF", companyName="F ETF", marketCap=5e9, sector="Industrials", industry="Tools", country="US",
         isEtf=True, isFund=False, isActivelyTrading=True, volume=100),
    dict(symbol="GOOG", companyName="G Co", marketCap=5e9, sector="Technology", industry="Internet", country="US",
         isEtf=False, isFund=False, isActivelyTrading=True, volume=50),
    dict(symbol="GOOGL", companyName="G Co", marketCap=5e9, sector="Technology", industry="Internet", country="US",
         isEtf=False, isFund=False, isActivelyTrading=True, volume=80),
    dict(symbol="HHH", companyName="H REIT", marketCap=5e9, sector="Real Estate", industry="REIT", country="US",
         isEtf=False, isFund=False, isActivelyTrading=True, volume=100),
    dict(symbol="III", companyName="I Shell", marketCap=5e9, sector="Financial Services", industry="Shell Companies",
         country="US", isEtf=False, isFund=False, isActivelyTrading=True, volume=100),
    dict(symbol="JJJ", companyName="J Exact", marketCap=2e9, sector="Energy", industry="Oil", country="US",
         isEtf=False, isFund=False, isActivelyTrading=True, volume=100)])
U, steps = S.universe(scr)
check("universe: keeps US $2B+ non-financial common stocks", sorted(U.symbol) == ["AAA", "GOOGL", "JJJ"])
check("universe: one share class (most traded) per company", "GOOGL" in set(U.symbol) and "GOOG" not in set(U.symbol))
check("universe: exactly $2B is kept", "JJJ" in set(U.symbol))
check("universe: step counts recorded", steps["start"] == 11 and list(steps.values())[-1] == 3)

# 2. price stats
d = pd.date_range("2025-01-01", periods=300, freq="B")
px = pd.DataFrame({"close": 100 * np.cumprod(np.r_[1, np.tile([1.01, 0.99], 150)[:-1]]), "volume": 1e6}, index=d)
vol, dv = S.price_stats(px)
r = (px.close / px.close.shift(1) - 1).dropna().iloc[-252:]
check("price stats: volatility = std of last 252 daily returns", close(vol, float(r.std())))
check("price stats: dollar volume = mean close x volume over last 63 days",
      close(dv, float((px.close.iloc[-63:] * 1e6).mean()), 1e-3))
v2, _ = S.price_stats(px.iloc[-200:])
check("price stats: under 240 returns -> missing", np.isnan(v2))

# 3. company metrics
def inc(oi, ni, rev=100.0, ebitda=30.0, cogs=40.0, sga=20.0, intr=5.0):
    return dict(operatingIncome=oi, netIncome=ni, revenue=rev, ebitda=ebitda, costOfRevenue=cogs,
                sellingGeneralAndAdministrativeExpenses=sga, interestExpense=intr)


def bal(debt=50.0, cash=20.0, st=10.0, eq=100.0):
    return dict(totalDebt=debt, cashAndShortTermInvestments=cash, shortTermDebt=st, totalStockholdersEquity=eq)


def cf(ocf, capex=-5.0):
    return dict(operatingCashFlow=ocf, capitalExpenditure=capex)


I3 = [inc(20, 15), inc(18, 14), inc(16, 12)]
B3 = [bal(), bal(), bal()]
C3 = [cf(16), cf(15), cf(14)]
m = S.company_metrics(I3, B3, C3, market_cap=200.0)
check("metrics: healthy company passes all filters", m["pass"] and not m["missing"])
check("metrics: net debt / EBITDA", close(m["net_debt_ebitda"], 30 / 30))
check("metrics: book-to-price", close(m["book_to_price"], 0.5))
check("metrics: earnings yield = operating income / EV", close(m["earnings_yield"], 20 / (200 + 50 - 20)))
check("metrics: FCF yield = (OCF - |capex|) / market cap", close(m["fcf_yield"], (16 - 5) / 200))
check("metrics: Ken French operating profitability", close(m["op_profitability"], (100 - 40 - 20 - 5) / 100))
check("metrics: cash/profit ratio", close(m["cash_to_profit"], 45 / 41))
m2 = S.company_metrics([inc(20, 15), inc(-1, 14), inc(16, 12)], B3, C3, 200.0)
check("filter 1: a loss year fails", not m2["f_profits"] and not m2["pass"])
check("filter 1: zero operating income fails", not S.company_metrics([inc(20, 15), inc(0, 14), inc(16, 12)], B3, C3, 200.0)["f_profits"])
check("filter 2: net debt exactly 3x EBITDA passes", S.company_metrics(I3, [bal(debt=110.0, cash=20.0)], C3, 200.0)["f_leverage"])
check("filter 2: above 3x fails", not S.company_metrics(I3, [bal(debt=110.1, cash=20.0)], C3, 200.0)["f_leverage"])
check("filter 2: net cash passes even with tiny EBITDA",
      S.company_metrics([inc(20, 15, ebitda=1.0), inc(18, 14), inc(16, 12)], [bal(debt=5.0, cash=20.0)], C3, 200.0)["f_leverage"])
check("filter 2: EBITDA <= 0 fails", not S.company_metrics([inc(20, 15, ebitda=0.0), inc(18, 14), inc(16, 12)],
                                                            [bal(debt=5.0, cash=20.0)], C3, 200.0)["f_leverage"])
check("filter 3: short-term debt covered exactly passes", S.company_metrics(I3, [bal(st=36.0)], C3, 200.0)["f_short_term"])
check("filter 3: not covered fails", not S.company_metrics(I3, [bal(st=36.1)], C3, 200.0)["f_short_term"])
check("filter 4: cash flow exactly 80% of profit passes",
      S.company_metrics(I3, B3, [cf(0.8 * 41 / 3)] * 3, 200.0)["f_cash"])
check("filter 4: below 80% fails", not S.company_metrics(I3, B3, [cf(0.79 * 41 / 3)] * 3, 200.0)["f_cash"])
check("metrics: two years of statements -> missing", S.company_metrics(I3[:2], B3, C3, 200.0)["missing"])
check("metrics: a missing number -> missing", S.company_metrics([inc(20, None), inc(18, 14), inc(16, 12)], B3, C3, 200.0)["missing"])
check("metrics: missing EBITDA -> missing", S.company_metrics([inc(20, 15, ebitda=None), inc(18, 14), inc(16, 12)], B3, C3, 200.0)["missing"])
def dated(rows, years):
    return [{**r, "date": f"{y}-06-30"} for r, y in zip(rows, years)]


I3d, B3d, C3d = dated(I3, [2025, 2024, 2023]), dated(B3, [2025, 2024, 2023]), dated(C3, [2025, 2024, 2023])
check("consistency: same recent years pass", not S.company_metrics(I3d, B3d, C3d, 200.0, run_date="2026-08-28")["missing"])
check("consistency: balance sheet from another year -> missing",
      S.company_metrics(I3d, dated(B3, [2024, 2023, 2022]), C3d, 200.0, run_date="2026-08-28")["missing"])
check("consistency: a gap year -> missing",
      S.company_metrics(dated(I3, [2025, 2024, 2022]), B3d, dated(C3, [2025, 2024, 2022]), 200.0, run_date="2026-08-28")["missing"])
check("consistency: latest year older than ~15 months -> missing",
      S.company_metrics(I3d, B3d, C3d, 200.0, run_date="2026-10-28")["missing"])
check("metrics: zero revenue counts as missing", S.company_metrics([inc(20, 15, rev=0.0), inc(18, 14), inc(16, 12)], B3, C3, 200.0)["missing"])
check("metrics: EV <= 0 counts as cheapest", S.company_metrics(I3, [bal(debt=0.0, cash=500.0)], C3, 200.0)["earnings_yield"] == np.inf)
opn = S.op_profit(dict(revenue=100.0, costOfRevenue=None, sellingGeneralAndAdministrativeExpenses=30.0, interestExpense=None))
check("op profitability: missing items count as 0 if one is reported", close(opn, 70.0))
check("op profitability: all three missing -> NaN", np.isnan(S.op_profit(dict(revenue=100.0))))
check("op profitability: negative interest sign handled", close(S.op_profit(dict(revenue=100.0, interestExpense=-5.0)), 95.0))

# 4. score and shortlist
n = 10
D_ = pd.DataFrame({"symbol": [f"S{i}" for i in range(n)], "sector": ["A", "A", "A", "B", "B", "C", "C", "D", "E", "F"],
                   "book_to_price": np.arange(n, dtype=float), "earnings_yield": np.arange(n, dtype=float),
                   "fcf_yield": np.arange(n, dtype=float), "op_profitability": np.arange(n, dtype=float)[::-1],
                   "volatility": np.arange(n, dtype=float)})
SC = S.score(D_)
check("score: value rank averages three ranks", close(SC.loc[9, "value"], 100.0) and close(SC.loc[0, "value"], 10.0))
check("score: low volatility ranked highest", close(SC.loc[0, "low_vol"], 100.0))
check("score: combined = mean of three", close(SC.loc[3, "combined"], (SC.loc[3, "value"] + SC.loc[3, "quality"] + SC.loc[3, "low_vol"]) / 3))
D2 = D_.assign(earnings_yield=np.arange(n, dtype=float)[::-1], fcf_yield=np.arange(n, dtype=float)[::-1])
check("score: value blends all three measures", close(S.score(D2).loc[9, "value"], (100.0 + 10.0 + 10.0) / 3))
check("score: missing measure raises", raises(lambda: S.score(D_.assign(volatility=[np.nan] + [1.0] * 9))))
sl = S.shortlist(SC, n=5, per_sector=2)
check("shortlist: at most 2 per sector", sl.sector.value_counts().max() <= 2 and len(sl) == 5)
SC2 = SC.copy()
SC2["combined"] = [90, 89, 88, 70, 60, 50, 40, 30, 20, 10]
sl2 = S.shortlist(SC2, n=3, per_sector=2)
check("shortlist: third company from a full sector is skipped", list(sl2.symbol) == ["S0", "S1", "S3"])
SC3 = SC2.copy()
SC3["combined"] = 50.0
SC3["quality"] = np.arange(10, dtype=float)
big = pd.DataFrame({"symbol": [f"X{i}" for i in range(45)], "sector": [f"S{i % 9}" for i in range(45)],
                    "combined": np.linspace(99, 1, 45), "quality": 50.0})
dl = S.shortlist(big)
check("shortlist default: 30 names, at most 4 per sector, 9 sectors are enough", len(dl) == 30 and dl.sector.value_counts().max() <= 4)
check("shortlist: ties go to the higher quality rank", S.shortlist(SC3, n=1, per_sector=2).symbol[0] == "S9")

# 5. EDGAR annual series
def fact(start, end, val, filed, form="10-K"):
    d = {"end": end, "val": val, "filed": filed, "form": form}
    if start:
        d["start"] = start
    return d


facts = {"facts": {"us-gaap": {
    "Revenues": {"units": {"USD": [
        fact("2022-01-01", "2022-12-31", 100, "2023-02-01"),
        fact("2022-01-01", "2022-12-31", 105, "2024-02-01"),             # restated in the next 10-K: wins
        fact("2023-01-01", "2023-12-31", 120, "2024-02-01"),
        fact("2023-10-01", "2023-12-31", 30, "2024-02-01"),              # a quarter inside a 10-K: ignored
        fact("2024-01-01", "2024-12-31", 999, "2024-05-01", form="10-Q")]}},   # 10-Q: ignored
    "RevenueFromContractWithCustomerExcludingAssessedTax": {"units": {"USD": [
        fact("2021-01-01", "2021-12-31", 90, "2022-02-01")]}},
    "StockholdersEquity": {"units": {"USD": [fact(None, "2022-12-31", 50, "2023-02-01"),
                                             fact(None, "2023-12-31", 60, "2024-02-01")]}},
    "NetIncomeLoss": {"units": {"USD": [fact("2023-01-01", "2023-12-31", 12, "2024-02-01")]}}}}}
s, tag = G.annual_series(facts, G.CONCEPTS["revenue"])
check("edgar: years filled from each tag in order", tag == ["Revenues", "RevenueFromContractWithCustomerExcludingAssessedTax"]
      and s.loc["2021-12-31"] == 90 and len(s) == 3)
check("edgar: restated value (latest filing) wins", s.loc["2022-12-31"] == 105)
check("edgar: quarters and 10-Qs ignored", s.loc["2023-12-31"] == 120 and "2024-12-31" not in s.index.strftime("%Y-%m-%d"))
facts2 = {"facts": {"us-gaap": {
    "Revenues": {"units": {"USD": [fact("2015-01-01", "2015-12-31", 50, "2016-02-01"),
                                   fact("2016-01-01", "2016-12-31", 55, "2017-02-01")]}},
    "RevenueFromContractWithCustomerExcludingAssessedTax": {"units": {"USD": [
        fact("2016-01-01", "2016-12-31", 56, "2019-02-01"), fact("2018-01-01", "2018-12-31", 70, "2019-02-01"),
        fact("2019-01-01", "2019-12-31", 80, "2020-02-01")]}}}}}
s3, t3 = G.annual_series(facts2, G.CONCEPTS["revenue"])
check("edgar: a company that switched tags keeps recent years", list(s3.values) == [50, 55, 70, 80] and len(t3) == 2)
s4, _ = G.annual_series({"facts": {"us-gaap": {"Revenues": {"units": {"USD": [fact("2019-12-29", "2020-12-31", 7, "2021-02-01")]}}}}},
                        ["Revenues"])
check("edgar: a 53-week year (368 days) counts", len(s4) == 1)
cat = {"facts": {"us-gaap": {
    "NetIncomeLoss": {"units": {"USD": [fact("2010-01-01", "2010-12-31", 2.7, "2011-02-01")]}},
    "NetIncomeLossAvailableToCommonStockholdersBasic": {"units": {"USD": [fact("2025-01-01", "2025-12-31", 9.0, "2026-02-01")]}},
    "ProfitLoss": {"units": {"USD": [fact("2025-01-01", "2025-12-31", 9.1, "2026-02-01"),
                                     fact("2024-01-01", "2024-12-31", 10.8, "2025-02-01")]}},
    "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest": {"units": {"USD": [fact(None, "2025-12-31", 20.0, "2026-02-01")]}}}}}
ct, cu = G.company_table(cat)
check("edgar: net income falls back past an old tag (Caterpillar case), common-shareholder figure first",
      ct.loc["2025-12-31", "net_income"] == 9.0 and ct.loc["2024-12-31", "net_income"] == 10.8 and ct.loc["2010-12-31", "net_income"] == 2.7)
check("edgar: equity falls back to the tag including minority interests", ct.loc["2025-12-31", "equity"] == 20.0)
s2, tag2 = G.annual_series(facts, ["Nope", "RevenueFromContractWithCustomerExcludingAssessedTax"])
check("edgar: falls back to the next tag", tag2 == ["RevenueFromContractWithCustomerExcludingAssessedTax"] and s2.iloc[0] == 90)
eq, _ = G.annual_series(facts, ["StockholdersEquity"], flow=False)
check("edgar: balances use year-end points", list(eq.values) == [50, 60])
t, used = G.company_table(facts)
check("edgar: table has every concept, missing ones empty", set(t.columns) == set(G.CONCEPTS) and used["capex"] is None)
check("edgar: table dates are real dates (can be compared with FMP dates)", isinstance(t.index, pd.DatetimeIndex)
      and len(t.index[abs((t.index - pd.Timestamp("2023-12-28")).days) <= 10]) == 1)
cc = G.cross_check({"revenue": 100.0, "net_income": 10.0, "operating_income": None},
                   {"revenue": 101.9, "netIncome": 10.3, "operatingIncome": 5.0})
check("edgar: cross-check within 2% ok, above flagged", cc["revenue"][3] and not cc["net_income"][3] and cc["operating_income"][3] is None)

# 6. clean-up and robustness functions
check("partnership: 'L.P.' and 'LP' endings", S.is_partnership("Plains All American Pipeline, L.P.") and S.is_partnership("Energy Transfer LP"))
check("partnership: 'LPG' and 'Ltd.' are not", not S.is_partnership("Dorian LPG Ltd.") and not S.is_partnership("Alpha Corp"))
b0 = dict(totalDebt=50.0, cashAndShortTermInvestments=20.0, totalCurrentAssets=70.0, totalCurrentLiabilities=40.0,
          shortTermDebt=10.0, propertyPlantEquipmentNet=60.0)
ey_, roc_ = S.magic_formula_inputs({"operatingIncome": 23.0}, b0, 200.0)
check("magic formula: EY = OI / EV", close(ey_, 23.0 / 230.0))
check("magic formula: ROC = OI / (NWC + net fixed assets)", close(roc_, 23.0 / ((70 - 20) - (40 - 10) + 60)))
check("magic formula: capital <= 0 ranks highest", S.magic_formula_inputs({"operatingIncome": 5.0}, {**b0, "propertyPlantEquipmentNet": -100.0}, 200.0)[1] == np.inf)
check("magic formula: missing input -> NaN", np.isnan(S.magic_formula_inputs({"operatingIncome": None}, b0, 200.0)[0]))
def fy(ni, gp, rev, sh):
    return dict(netIncome=ni, grossProfit=gp, revenue=rev, weightedAverageShsOutDil=sh)
def fb(ta, ltd, ca, cl):
    return dict(totalAssets=ta, longTermDebt=ltd, totalCurrentAssets=ca, totalCurrentLiabilities=cl)
inc_g = [fy(12, 45, 110, 100), fy(8, 40, 100, 101)]
bal_g = [fb(100, 20, 50, 25), fb(100, 30, 40, 25), fb(100, 30, 40, 25)]
check("piotroski: all nine tests pass -> 9", S.piotroski(inc_g, bal_g, [dict(operatingCashFlow=15)]) == 9)
inc_b = [fy(-5, 35, 90, 110), fy(8, 40, 100, 101)]
bal_b = [fb(100, 40, 30, 25), fb(100, 30, 40, 25), fb(100, 30, 40, 25)]
check("piotroski: all nine fail -> 0", S.piotroski(inc_b, bal_b, [dict(operatingCashFlow=-6)]) == 0)
check("piotroski: two years only -> NaN", np.isnan(S.piotroski(inc_g, bal_g[:2], [dict(operatingCashFlow=15)])))
check("piotroski: ROA and turnover use beginning-of-year assets", S.piotroski([fy(12, 45, 110, 100), fy(8, 40, 100, 101)],
      [fb(100, 20, 50, 25), fb(1000, 30, 40, 25), fb(100, 30, 40, 25)], [dict(operatingCashFlow=15)]) == 6)
check("gross profitability", close(S.gross_profitability({"grossProfit": 30.0}, {"totalAssets": 120.0}), 0.25))
check("label: robust / mixed / fragile", S.robustness_label([80, 75, 10]) == "robust" and S.robustness_label([80, 10, np.nan]) == "mixed"
      and S.robustness_label([10, 20, np.nan]) == "fragile" and S.robustness_label([70, 70, 0]) == "robust")
sub = {"filings": {"recent": {"form": ["8-K", "8-K", "10-Q", "8-K/A", "8-K"], "filingDate": ["2026-06-02", "2025-11-01", "2026-07-01", "2026-03-01", "2026-04-01"],
                              "items": ["2.01,9.01", "2.01", "", "2.01", "5.02,2.011"], "accessionNumber": ["a", "b", "c", "d", "e"]}}}
hits = S.item_201_after(sub, "2025-12-31")
check("SEC flags: 8-K and 8-K/A with Item 2.01 after year-end only", [h[3] for h in hits] == ["a", "d"])

bad = [n_ for n_, ok in results if not ok]
print(f"\n{len(results) - len(bad)} of {len(results)} checks passed" + (f"; FAILED: {bad}" if bad else ""))
sys.exit(1 if bad else 0)
