# Phase 3 long-term compounder screen: pure functions (no downloads), checked on made-up numbers in
# test_compounder.py. Rules: docs/phase3_compounder_screen_rules.md (fixed 2026-11-01, before any data was pulled).
import numpy as np
import pandas as pd

EPS = 1e-12
YEARS = 10
MIN_CAGR = 0.10
MIN_UP_YEARS = 8
MIN_ROIC = 0.15
MIN_ROIC_YEARS = 8
MAX_GM_DROP = 0.05
MIN_FCF_YEARS = 8
MAX_ND_EBITDA = 2.0
MAX_DILUTION = 0.02
MIN_RETURN = 0.09
TAX_DEFAULT, TAX_MAX = 0.21, 0.35
SBC_TAX = 0.21
FADE_TO = 0.05
GROWTH_CAP = 0.15
ALLOWED_FINANCIAL = {"Financial - Credit Services", "Financial - Data & Stock Exchanges"}


def universe_filter(d):
    """Quality-screen universe, but with two financial industries allowed back in (rules section 1)."""
    keep = (d.sector != "Real Estate") & ((d.sector != "Financial Services") | d.industry.isin(ALLOWED_FINANCIAL))
    return d[keep & (d.industry != "Shell Companies")]


def _n(d, k):
    v = d.get(k) if d else None
    return None if v is None or (isinstance(v, float) and np.isnan(v)) else float(v)


def _years_ok(rows, run_date, n):
    try:
        ds = [pd.Timestamp(x["date"]) for x in rows[:n]]
    except (KeyError, ValueError, TypeError):
        return False
    if len(ds) < n or any(not 350 <= (ds[k] - ds[k + 1]).days <= 380 for k in range(n - 1)):
        return False
    return (pd.Timestamp(run_date) - ds[0]).days <= 460


def cagr_rule(inc, run_date):
    """Rule 1 only (cheap prefilter). inc: 11 annual income statements, NEWEST FIRST. Returns (passes, cagr,
    up_years) or None if missing."""
    n = YEARS + 1
    if len(inc) < n or not _years_ok(inc, run_date, n):
        return None
    rev = [_n(x, "revenue") for x in inc[:n]]
    if any(r is None or r <= 0 for r in rev):
        return None
    cagr = (rev[0] / rev[YEARS]) ** (1 / YEARS) - 1
    up = sum(rev[k] > rev[k + 1] for k in range(YEARS))
    return (cagr >= MIN_CAGR - EPS and up >= MIN_UP_YEARS), cagr, up


def metrics(inc, bal, cf, ev_sales_hist, market_cap, run_date):
    """inc, bal, cf: 11 annual statements each, NEWEST FIRST, same year-ends. ev_sales_hist: up to 10 year-end
    EV/sales values. Returns a dict with measures, r1..r7 booleans and 'pass'; {'missing': True} if data is short."""
    n = YEARS + 1
    if len(inc) < n or len(bal) < n or len(cf) < n:
        return {"missing": True}
    inc, bal, cf = inc[:n], bal[:n], cf[:n]
    dates = [x.get("date") for x in inc]
    if dates != [x.get("date") for x in bal] or dates != [x.get("date") for x in cf] or not _years_ok(inc, run_date, n):
        return {"missing": True}
    c = cagr_rule(inc, run_date)
    if c is None:
        return {"missing": True}
    m = {"missing": False, "r1": c[0], "cagr10": c[1], "up_years": c[2]}
    rev = [x["revenue"] for x in inc]
    yearly = [rev[k] / rev[k + 1] - 1 for k in range(YEARS)]
    m["growth_sd"] = float(np.std(yearly))
    # rule 2: ROIC in years 0..9 on average invested capital (that year's end and the prior year's end)
    def ic(b):
        vals = [_n(b, "totalDebt"), _n(b, "totalStockholdersEquity"), _n(b, "cashAndShortTermInvestments")]
        return None if any(v is None for v in vals) else vals[0] + vals[1] - vals[2]
    roics = []
    for k in range(YEARS):
        oi, pti, tax = _n(inc[k], "operatingIncome"), _n(inc[k], "incomeBeforeTax"), _n(inc[k], "incomeTaxExpense")
        a, b = ic(bal[k]), ic(bal[k + 1])
        if oi is None or a is None or b is None:
            return {"missing": True}
        t = TAX_DEFAULT if (pti is None or tax is None or pti <= 0) else min(TAX_MAX, max(0.0, tax / pti))
        nopat, cap = oi * (1 - t), (a + b) / 2
        roics.append(np.inf if (cap <= 0 and nopat > 0) else (nopat / cap if cap > 0 else -np.inf))
    m["roic_years_15"] = int(sum(r >= MIN_ROIC - EPS for r in roics))
    m["roic_median"] = float(np.median(roics))
    m["r2"] = m["roic_years_15"] >= MIN_ROIC_YEARS
    # rule 3: gross margin
    gms = []
    for x in inc[:YEARS]:
        g = _n(x, "grossProfit")
        if g is None:
            cr = _n(x, "costOfRevenue")
            g = None if cr is None else x["revenue"] - abs(cr)
        if g is None:
            return {"missing": True}
        gms.append(g / x["revenue"])
    if min(gms) >= 1.0 - 1e-9:
        m["gm_note"], m["r3"] = "not measurable", True
    else:
        m["gm_note"] = ""
        m["r3"] = gms[0] >= float(np.mean(gms)) - MAX_GM_DROP - EPS
    m["gross_margin"], m["gross_margin_avg10"] = gms[0], float(np.mean(gms))
    # rule 4: free cash flow
    fcfs = []
    for x in cf[:YEARS]:
        o, cx = _n(x, "operatingCashFlow"), _n(x, "capitalExpenditure")
        if o is None or cx is None:
            return {"missing": True}
        fcfs.append(o - abs(cx))
    m["fcf_pos_years"] = int(sum(f > 0 for f in fcfs))
    m["r4"] = m["fcf_pos_years"] >= MIN_FCF_YEARS
    # rule 5: debt
    d0, c0, e0 = _n(bal[0], "totalDebt"), _n(bal[0], "cashAndShortTermInvestments"), _n(inc[0], "ebitda")
    if d0 is None or c0 is None or e0 is None:
        return {"missing": True}
    nd = d0 - c0
    m["net_debt_ebitda"] = nd / e0 if e0 > 0 else (-np.inf if nd <= 0 else np.inf)
    m["r5"] = bool(nd <= 0 or (e0 > 0 and nd / e0 <= MAX_ND_EBITDA + EPS))
    # rule 6: dilution
    s0, s10 = _n(inc[0], "weightedAverageShsOutDil"), _n(inc[YEARS], "weightedAverageShsOutDil")
    if s0 is None or s10 is None or s10 <= 0:
        return {"missing": True}
    m["dilution"] = (s0 / s10) ** (1 / YEARS) - 1
    m["r6"] = m["dilution"] <= MAX_DILUTION + EPS
    # rule 7: long-run return = yield + faded growth + valuation drift
    sbc = _n(cf[0], "stockBasedCompensation") or 0.0
    m["fcf_yield"] = (fcfs[0] - sbc * (1 - SBC_TAX)) / market_cap
    m["growth_est"] = min(GROWTH_CAP, (c[1] + FADE_TO) / 2)
    ev_now = market_cap + d0 - c0
    hist = [v for v in ev_sales_hist if v is not None and not (isinstance(v, float) and np.isnan(v)) and v > 0]
    if len(hist) < 5 or ev_now <= 0:
        return {"missing": True}
    m["ev_sales_now"], m["ev_sales_median10"] = ev_now / rev[0], float(np.median(hist))
    m["drift"] = (m["ev_sales_median10"] / m["ev_sales_now"]) ** (1 / YEARS) - 1
    m["exp_return"] = m["fcf_yield"] + m["growth_est"] + m["drift"]
    m["r7"] = m["exp_return"] >= MIN_RETURN - EPS
    m["pass"] = all(m[f"r{k}"] for k in range(1, 8))
    return m


def score(df):
    """Companies that passed: durability = mean rank(median ROIC high, growth sd low); return = rank(exp_return);
    score = half each."""
    d = df.copy()
    if d[["roic_median", "growth_sd", "exp_return"]].isna().any().any():
        raise ValueError("score inputs missing")
    r = lambda s, hi=True: s.rank(pct=True, ascending=hi, method="average") * 100  # noqa: E731
    d["durability"] = (r(d.roic_median.replace(np.inf, 1e9)) + r(d.growth_sd, hi=False)) / 2
    d["return_rank"] = r(d.exp_return)
    d["score"] = (d.durability + d.return_rank) / 2
    return d.sort_values("score", ascending=False).reset_index(drop=True)
