# Pure functions for reading SEC EDGAR "company facts" JSON (data.sec.gov/api/xbrl/companyfacts/CIK##########.json)
# into annual series. No downloads here, so the logic can be tested on made-up JSON (test_phase3.py).
import pandas as pd

# Each line: our name -> XBRL tags tried in order (companies use different tags for the same number). Later tags
# fill only years the earlier ones lack. Net income falls back to income available to common shareholders, then to
# profit including minority interests (e.g. Caterpillar stopped using NetIncomeLoss after 2010); equity falls back to
# equity including minority interests (e.g. P&G, Caterpillar), so small gaps against FMP are expected there.
CONCEPTS = {
    "revenue": ["Revenues", "RevenueFromContractWithCustomerExcludingAssessedTax", "SalesRevenueNet",
                "RevenueFromContractWithCustomerIncludingAssessedTax"],
    "operating_income": ["OperatingIncomeLoss"],
    "net_income": ["NetIncomeLoss", "NetIncomeLossAvailableToCommonStockholdersBasic", "ProfitLoss"],
    "operating_cash_flow": ["NetCashProvidedByUsedInOperatingActivities"],
    "capex": ["PaymentsToAcquirePropertyPlantAndEquipment"],
    "equity": ["StockholdersEquity", "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest"],
    "cash": ["CashAndCashEquivalentsAtCarryingValue"],
    "long_term_debt": ["LongTermDebtNoncurrent", "LongTermDebt"],
}
FLOWS = {"revenue", "operating_income", "net_income", "operating_cash_flow", "capex"}


def annual_series(facts, tags, flow=True):
    """Annual values from 10-K filings (including 10-K/A). Tags are tried in order FOR EACH YEAR: a year takes its
    value from the first tag that has one, so a company that switched tags (e.g. to the ASC 606 revenue tag in
    2018) still gets a full series. Flows keep only ~one-year periods (350-380 days, which covers 52/53-week
    years); balances keep year-end points. For each fiscal year-end the most recently FILED value wins, so later
    restatements replace originals. Returns (Series indexed by year-end date, list of tags used)."""
    gaap = facts.get("facts", {}).get("us-gaap", {})
    combined, used = pd.Series(dtype=float), []
    for tag in tags:
        units = gaap.get(tag, {}).get("units", {}).get("USD", [])
        rows = []
        for u in units:
            if not str(u.get("form", "")).startswith("10-K"):
                continue
            end = pd.Timestamp(u["end"])
            if flow:
                if "start" not in u:
                    continue
                days = (end - pd.Timestamp(u["start"])).days
                if not 350 <= days <= 380:
                    continue
            rows.append((end, pd.Timestamp(u["filed"]), float(u["val"])))
        if rows:
            d = pd.DataFrame(rows, columns=["end", "filed", "val"]).sort_values(["end", "filed"])
            s = d.groupby("end").val.last()
            before = len(combined)
            combined = s if combined.empty else combined.combine_first(s)
            if len(combined) > before:
                used.append(tag)
    return combined.sort_index(), used


def company_table(facts):
    """All CONCEPTS as one annual table (rows = fiscal year-end dates) plus the tag used for each column."""
    cols, used = {}, {}
    for name, tags in CONCEPTS.items():
        s, tag = annual_series(facts, tags, flow=name in FLOWS)
        cols[name], used[name] = s, ", ".join(tag) if tag else None
    t = pd.DataFrame(cols)
    t.index = pd.DatetimeIndex(t.index)
    return t.sort_index(), used


def cross_check(edgar_row, fmp_row, tol=0.02):
    """Compare matching numbers for one fiscal year; returns {name: (edgar, fmp, relative gap, ok)}."""
    pairs = {"revenue": "revenue", "operating_income": "operatingIncome", "net_income": "netIncome",
             "operating_cash_flow": "operatingCashFlow", "equity": "totalStockholdersEquity"}
    out = {}
    for e, f in pairs.items():
        a, b = edgar_row.get(e), fmp_row.get(f)
        if a is None or b is None or pd.isna(a) or pd.isna(b):
            out[e] = (a, b, None, None)
            continue
        gap = abs(a - b) / max(abs(a), 1.0)
        out[e] = (a, b, gap, gap <= tol)
    return out
