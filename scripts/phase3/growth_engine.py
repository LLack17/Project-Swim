# Phase 3 growth screen: pure functions (no downloads), checked on made-up numbers in test_growth.py.
# Rules: docs/phase3_growth_screen_rules.md (fixed 2026-10-29, before any data was pulled).
import numpy as np
import pandas as pd

EPS = 1e-12
MIN_CAGR3 = 0.20      # 1. 3-year revenue growth a year
MIN_TTM_GROWTH = 0.15  # 2. TTM vs prior TTM
MIN_GROSS = 0.40      # 3. TTM gross margin
MIN_RULE40 = 0.40     # 4. growth + FCF margin
MIN_FCF_LOOSE = -0.10  # 5. floor when the FCF margin is improving
MAX_ND_EBITDA = 2.0   # 6.
MAX_DILUTION = 0.03   # 7. diluted shares, a year
MAX_VAL = 0.8         # 8. (EV / TTM revenue) / (TTM growth in %)


def _n(d, k):
    v = d.get(k)
    return None if v is None or (isinstance(v, float) and np.isnan(v)) else float(v)


def _gaps_ok(dates, lo, hi):
    try:
        ds = [pd.Timestamp(x) for x in dates]
    except (ValueError, TypeError):
        return False
    return all(lo <= (ds[k] - ds[k + 1]).days <= hi for k in range(len(ds) - 1))


def metrics(inc_a, inc_q, cf_q, bal_q, market_cap, run_date):
    """inc_a: 4 annual income statements, NEWEST FIRST; inc_q, cf_q: 8 quarterly income / cash-flow statements,
    NEWEST FIRST, same quarter-ends; bal_q: latest quarterly balance sheet (dict). Returns a dict with the measures,
    one boolean per filter (f1..f8) and 'pass'; 'missing' True if a needed number is absent or dates are inconsistent."""
    m = {"missing": True}
    if len(inc_a) < 4 or len(inc_q) < 8 or len(cf_q) < 8 or not bal_q:
        return m
    inc_a, inc_q, cf_q = inc_a[:4], inc_q[:8], cf_q[:8]
    run = pd.Timestamp(run_date)
    if not _gaps_ok([x.get("date") for x in inc_a], 350, 380) or (run - pd.Timestamp(inc_a[0]["date"])).days > 460:
        return m
    dq = [x.get("date") for x in inc_q]
    if dq != [x.get("date") for x in cf_q] or not _gaps_ok(dq, 80, 100) or (run - pd.Timestamp(dq[0])).days > 200:
        return m
    if bal_q.get("date") != dq[0]:
        return m
    need_q = ["revenue", "ebitda"]
    need_cf = ["operatingCashFlow", "capitalExpenditure"]
    if any(_n(x, k) is None for x in inc_q for k in need_q) or any(_n(x, k) is None for x in cf_q for k in need_cf):
        return m
    if any(_n(x, k) is None for x in inc_a for k in ["revenue", "weightedAverageShsOutDil"]):
        return m
    if any(_n(bal_q, k) is None for k in ["totalDebt", "cashAndShortTermInvestments"]):
        return m
    gp = []
    for x in inc_q[:4]:
        g = _n(x, "grossProfit")
        if g is None:
            c = _n(x, "costOfRevenue")
            g = None if c is None else x["revenue"] - abs(c)
        if g is None:
            return m
        gp.append(g)
    r0, r3 = inc_a[0]["revenue"], inc_a[3]["revenue"]
    s0, s3 = inc_a[0]["weightedAverageShsOutDil"], inc_a[3]["weightedAverageShsOutDil"]
    ttm = sum(x["revenue"] for x in inc_q[:4])
    prior = sum(x["revenue"] for x in inc_q[4:])
    if r3 <= 0 or s3 <= 0 or ttm <= 0 or prior <= 0:
        return m
    fcf = lambda rows: sum(x["operatingCashFlow"] - abs(x["capitalExpenditure"]) for x in rows)  # noqa: E731
    m = {"missing": False}
    m["cagr3"] = (r0 / r3) ** (1 / 3) - 1
    m["ttm_growth"] = ttm / prior - 1
    m["gross_margin"] = sum(gp) / ttm
    if m["gross_margin"] >= 1.0 - EPS:
        return {"missing": True}
    m["fcf_margin"] = fcf(cf_q[:4]) / ttm
    m["fcf_margin_prior"] = fcf(cf_q[4:]) / prior
    m["rule40"] = m["ttm_growth"] + m["fcf_margin"]
    ebitda = sum(x["ebitda"] for x in inc_q[:4])
    nd = bal_q["totalDebt"] - bal_q["cashAndShortTermInvestments"]
    m["net_debt_ebitda"] = (nd / ebitda) if ebitda > 0 else (-np.inf if nd <= 0 else np.inf)
    m["dilution"] = (s0 / s3) ** (1 / 3) - 1
    ev = market_cap + bal_q["totalDebt"] - bal_q["cashAndShortTermInvestments"]
    m["ev"] = ev
    m["ev_sales"] = ev / ttm
    g_pct = m["ttm_growth"] * 100
    m["val_ratio"] = (-np.inf if ev <= 0 else (m["ev_sales"] / g_pct if g_pct > 0 else np.inf))
    m["f1"] = m["cagr3"] >= MIN_CAGR3 - EPS
    m["f2"] = m["ttm_growth"] >= MIN_TTM_GROWTH - EPS
    m["f3"] = m["gross_margin"] >= MIN_GROSS - EPS
    m["f4"] = m["rule40"] >= MIN_RULE40 - EPS
    m["f5"] = bool(m["fcf_margin"] >= -EPS or (m["fcf_margin"] >= MIN_FCF_LOOSE - EPS and m["fcf_margin"] > m["fcf_margin_prior"]))
    m["f6"] = bool(nd <= 0 or (ebitda > 0 and nd / ebitda <= MAX_ND_EBITDA + EPS))
    m["f7"] = m["dilution"] <= MAX_DILUTION + EPS
    m["f8"] = bool(m["val_ratio"] <= MAX_VAL + EPS)
    m["pass"] = all(m[f"f{k}"] for k in range(1, 9))
    return m


def score(df):
    """df: companies that passed, with rule40 and val_ratio. Adds r_rule40, r_value and growth_score (0-100)."""
    d = df.copy()
    if d[["rule40", "val_ratio"]].isna().any().any():
        raise ValueError("rule40 or val_ratio missing")
    d["r_rule40"] = d.rule40.rank(pct=True, method="average") * 100
    d["r_value"] = d.val_ratio.rank(pct=True, ascending=False, method="average") * 100
    d["growth_score"] = (d.r_rule40 + d.r_value) / 2
    return d.sort_values("growth_score", ascending=False).reset_index(drop=True)
