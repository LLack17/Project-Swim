# Phase 3 stock screen: pure functions (no downloads), so every rule can be checked on made-up numbers in
# test_phase3.py. Rules: docs/phase3_screen_rules.md (and its amendment log).
import numpy as np
import pandas as pd

EPS = 1e-12
EXCLUDED_SECTORS = {"Financial Services", "Real Estate"}
EXCLUDED_INDUSTRIES = {"Shell Companies"}


def universe(scr, min_cap=2e9):
    """FMP screener rows -> eligible universe. Keeps US-domiciled common stocks of at least `min_cap`, outside the
    excluded sectors/industries; drops symbols with '-' or '.' (preferred shares, units, warrants); keeps one share
    class per company (the most traded). Returns (DataFrame, counts of what each step removed)."""
    d = scr.copy()
    steps = {"start": len(d)}
    d = d[(d.country == "US") & (~d.isEtf.astype(bool)) & (~d.isFund.astype(bool)) & (d.isActivelyTrading.astype(bool))]
    steps["US, not a fund, actively trading"] = len(d)
    d = d[d.marketCap >= min_cap]
    steps[f"market value >= ${min_cap / 1e9:.0f}B"] = len(d)
    d = d[~d.sector.isin(EXCLUDED_SECTORS) & ~d.industry.isin(EXCLUDED_INDUSTRIES)]
    steps["not financials, real estate or shells"] = len(d)
    d = d[~d.symbol.str.contains(r"[-.]", regex=True)]
    steps["no preferred shares, units or warrants"] = len(d)
    d = d.sort_values("volume", ascending=False).drop_duplicates("companyName", keep="first")
    steps["one share class per company"] = len(d)
    return d.reset_index(drop=True), steps


def price_stats(px, vol_days=252, min_obs=240, liq_days=63):
    """px: DataFrame with columns close (adjusted) and volume, daily, oldest first. Returns daily-return volatility
    over the last `vol_days` days (NaN if fewer than `min_obs` returns) and average daily dollar volume over the
    last `liq_days` days."""
    px = px.dropna(subset=["close"]).sort_index()
    r = (px.close / px.close.shift(1) - 1).dropna().iloc[-vol_days:]
    vol = float(r.std()) if len(r) >= min_obs else np.nan
    last = px.iloc[-liq_days:]
    dollar = float((last.close * last.volume).mean()) if len(last) == liq_days else np.nan
    return vol, dollar


def op_profit(inc):
    """Ken French operating profitability numerator for one year: revenue minus cost of goods sold, SG&A and
    interest expense, with a missing item treated as zero as long as at least one of the three is reported."""
    items = [inc.get("costOfRevenue"), inc.get("sellingGeneralAndAdministrativeExpenses"), inc.get("interestExpense")]
    if inc.get("revenue") is None or pd.isna(inc.get("revenue")) or all(x is None or pd.isna(x) for x in items):
        return np.nan
    return inc["revenue"] - sum(0.0 if (x is None or pd.isna(x)) else abs(x) for x in items)


def _consistent(inc3, bal3, cf3, run_date, max_age_days=460):
    """Same latest fiscal year-end across the three statements, three consecutive fiscal years (350-380 days
    apart) in the income and cash-flow statements, and a latest year-end no older than ~15 months."""
    try:
        di = [pd.Timestamp(x["date"]) for x in inc3]
        dc = [pd.Timestamp(x["date"]) for x in cf3]
        db = pd.Timestamp(bal3[0]["date"])
    except (KeyError, ValueError, TypeError):
        return False
    if not (di[0] == dc[0] == db) or di != dc:
        return False
    if any(not 350 <= (di[k] - di[k + 1]).days <= 380 for k in range(len(di) - 1)):
        return False
    return (pd.Timestamp(run_date) - di[0]).days <= max_age_days


def company_metrics(inc3, bal3, cf3, market_cap, run_date=None):
    """inc3, bal3, cf3: lists of three annual statement dicts, NEWEST FIRST. Returns a dict of filter results and
    raw measures. Any needed number missing (revenue of zero counts as missing), statements for different years,
    or a latest year older than ~15 months -> 'missing' is True."""
    m = {"missing": False}
    need = [(inc3, ["operatingIncome", "netIncome", "revenue"]),
            (bal3[:1], ["totalDebt", "cashAndShortTermInvestments", "shortTermDebt", "totalStockholdersEquity"]),
            (cf3, ["operatingCashFlow", "capitalExpenditure"])]
    if len(inc3) < 3 or len(bal3) < 1 or len(cf3) < 3:
        m["missing"] = True
        return m
    for rows, keys in need:
        for row in rows:
            for k in keys:
                if row.get(k) is None or pd.isna(row.get(k)):
                    m["missing"] = True
                    return m
    if inc3[0].get("ebitda") is None or pd.isna(inc3[0].get("ebitda")) or any(x["revenue"] <= 0 for x in inc3):
        m["missing"] = True
        return m
    if run_date is not None and not _consistent(inc3[:3], bal3, cf3[:3], run_date):
        m["missing"] = True
        return m
    b, i0, c0 = bal3[0], inc3[0], cf3[0]
    cash = b["cashAndShortTermInvestments"]
    equity = b["totalStockholdersEquity"]
    net_debt = b["totalDebt"] - cash
    ebitda = i0["ebitda"]
    m["f_profits"] = all(x["operatingIncome"] > 0 for x in inc3)
    m["net_debt_ebitda"] = net_debt / ebitda if ebitda > 0 else np.inf
    m["f_leverage"] = bool(ebitda > 0 and (net_debt <= 0 or net_debt / ebitda <= 3.0 + EPS))
    m["f_short_term"] = bool(b["shortTermDebt"] <= cash + c0["operatingCashFlow"] + EPS)
    ni, ocf = sum(x["netIncome"] for x in inc3), sum(x["operatingCashFlow"] for x in cf3)
    m["cash_to_profit"] = ocf / ni if ni > 0 else np.nan
    m["f_cash"] = bool(ocf >= 0.8 * ni - EPS)
    m["equity"] = equity
    m["book_to_price"] = equity / market_cap
    ev = market_cap + b["totalDebt"] - cash
    m["ev"] = ev
    m["earnings_yield"] = i0["operatingIncome"] / ev if ev > 0 else np.inf
    m["fcf_yield"] = (c0["operatingCashFlow"] - abs(c0["capitalExpenditure"])) / market_cap
    opn = op_profit(i0)
    m["op_profitability"] = opn / equity if (equity > 0 and not pd.isna(opn)) else np.nan
    m["pass"] = bool(m["f_profits"] and m["f_leverage"] and m["f_short_term"] and m["f_cash"])
    return m


def pct_rank(s, higher_is_better=True):
    """Percentile rank 0-100 (average for ties) among non-missing values."""
    r = s.rank(pct=True, ascending=higher_is_better, method="average") * 100
    return r


def score(df):
    """df: one row per company that passed the filters, with book_to_price, earnings_yield, fcf_yield,
    op_profitability, volatility. Adds value, quality, low_vol ranks and the combined score."""
    d = df.copy()
    for c in ["book_to_price", "earnings_yield", "fcf_yield", "op_profitability", "volatility"]:
        if d[c].isna().any():
            raise ValueError(f"{c} missing for some companies; they must be removed as 'missing data' first")
    d["value"] = (pct_rank(d.book_to_price) + pct_rank(d.earnings_yield) + pct_rank(d.fcf_yield)) / 3
    d["quality"] = pct_rank(d.op_profitability)
    d["low_vol"] = pct_rank(d.volatility, higher_is_better=False)
    d["combined"] = (d.value + d.quality + d.low_vol) / 3
    return d


def shortlist(d, n=30, per_sector=4):
    """Highest combined scores, ties to the higher quality rank, at most `per_sector` per sector."""
    d = d.sort_values(["combined", "quality", "symbol"], ascending=[False, False, True])
    picked, count = [], {}
    for _, row in d.iterrows():
        if count.get(row.sector, 0) >= per_sector:
            continue
        picked.append(row)
        count[row.sector] = count.get(row.sector, 0) + 1
        if len(picked) == n:
            break
    return pd.DataFrame(picked).reset_index(drop=True)
