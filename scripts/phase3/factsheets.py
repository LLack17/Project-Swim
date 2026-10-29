# One-page fact sheet per research pick from the FMP research pull (private/fmp_research/) and the SEC history
# (data/phase3/edgar/). Output: private/fmp_research/factsheets.txt and correlations.csv (git-ignored, FMP data).
# Usage, from the repo root, after fmp_research_pull.py and edgar_history.py:  python scripts/phase3/factsheets.py
import os
import numpy as np
import pandas as pd

R = "private/fmp_research"
PICKS = ["EHC", "GILD", "INGR", "CL", "BYD", "GNTX", "ITW", "AOS", "VNT", "EEFT", "CARG", "EOG", "SHW"]
TTM = {"P/E": "priceToEarningsRatioTTM", "EV/EBITDA": "evToEBITDATTM", "FCF yield %": "freeCashFlowYieldTTM",
       "ROIC %": "returnOnInvestedCapitalTTM", "Net debt/EBITDA": "netDebtToEBITDATTM",
       "Gross margin %": "grossProfitMarginTTM", "Op margin %": "operatingProfitMarginTTM",
       "Net margin %": "netProfitMarginTTM", "Div yield %": "dividendYieldTTM", "Interest cover": "interestCoverageRatioTTM"}
PCT = {"FCF yield %", "ROIC %", "Gross margin %", "Op margin %", "Net margin %", "Div yield %"}


def read(s, n, sub=""):
    f = f"{R}/{sub}{s}/{n}.csv"
    return pd.read_csv(f) if os.path.exists(f) else pd.DataFrame()


def closes(df):
    return df.assign(date=pd.to_datetime(df.date)).set_index("date").close.sort_index()


def ttm_row(s, sub=""):
    a, b = read(s, "key_metrics_ttm", sub), read(s, "ratios_ttm", sub)
    rec = {}
    for d in (a, b):
        if len(d):
            rec.update(d.iloc[0].to_dict())
    out = {}
    for k, c in TTM.items():
        v = rec.get(c, np.nan)
        out[k] = v * 100 if (k in PCT and pd.notna(v)) else v
    return out


def cagr(a, b, yrs):
    return (b / a) ** (1 / yrs) - 1 if a and b and a > 0 and b > 0 and yrs > 0 else np.nan


spy = closes(pd.read_csv(f"{R}/market/prices_SPY.csv"))
lines, rets = [], {}
for s in PICKS:
    p = read(s, "profile").iloc[0]
    px = closes(read(s, "prices"))
    r = px.pct_change().dropna()
    rets[s] = r
    last = px.index[-1]

    def back(y):
        q = px[px.index <= last - pd.DateOffset(years=y)]
        return px.iloc[-1] / q.iloc[-1] - 1 if len(q) else np.nan
    dd = (px / px.cummax() - 1).min()
    vol1 = r.iloc[-252:].std() * np.sqrt(252)
    corr = r.iloc[-756:].corr(spy.pct_change().reindex(r.index).iloc[-756:])
    lines += ["=" * 100, f"{s}  {p.companyName}  | {p.industry} | price {p.price:.2f} | mkt cap {p.marketCap / 1e9:.1f}B | "
              f"beta {p.beta:.2f} | employees {p.fullTimeEmployees}", f"  {str(p.description)[:420]}"]
    lines.append(f"  PRICE: 1y {back(1):+.0%}, 3y {back(3):+.0%}, 5y {back(5):+.0%} (price only); 1y volatility {vol1:.0%}; "
                 f"worst fall in 5y {dd:.0%}; correlation with S&P 500 (3y daily) {corr:.2f}")
    # TTM vs peers
    me = ttm_row(s)
    pr = read(s, "peers")
    peer_rows = [ttm_row(x, "peers/") for x in pr.symbol.astype(str) if os.path.exists(f"{R}/peers/{x}")] if len(pr) else []
    pm = pd.DataFrame(peer_rows).median() if peer_rows else pd.Series(dtype=float)
    lines.append(f"  VALUATION/QUALITY (TTM)  company | peer median ({len(peer_rows)} peers: {', '.join(pr.symbol.astype(str)[:8]) if len(pr) else '-'})")
    lines.append("    " + "; ".join(f"{k} {me[k]:.1f} | {pm.get(k, np.nan):.1f}" for k in TTM))
    # analysts
    pt, gc, est = read(s, "price_target_consensus"), read(s, "grades_consensus"), read(s, "analyst_estimates")
    if len(pt):
        t = pt.iloc[0]
        lines.append(f"  ANALYSTS: target consensus {t.targetConsensus:.0f} (low {t.targetLow:.0f}, high {t.targetHigh:.0f}) = "
                     f"{t.targetConsensus / p.price - 1:+.0%} vs price")
    if len(gc):
        g = gc.iloc[0]
        lines.append(f"    ratings: strong buy {g.strongBuy}, buy {g.buy}, hold {g.hold}, sell {g.sell}, strong sell {g.strongSell} -> {g.consensus}")
    if len(est):
        e = est.assign(y=est.date.str[:4].astype(int)).sort_values("y")
        e = e[e.y >= last.year - 1].head(4)
        lines.append("    EPS estimates: " + "; ".join(f"FY{r.y} {r.epsAvg:.2f} (n={r.numAnalystsEps}), revenue {r.revenueAvg / 1e9:.2f}B" for r in e.itertuples()))
    ea = read(s, "earnings")
    if len(ea):
        ea = ea.dropna(subset=["epsActual", "epsEstimated"]).sort_values("date").tail(8)
        beats = (ea.epsActual > ea.epsEstimated).sum()
        surp = ((ea.epsActual / ea.epsEstimated - 1).replace([np.inf, -np.inf], np.nan)).mean()
        up = read(s, "earnings").sort_values("date")
        nxt = up[up.epsActual.isna() & (pd.to_datetime(up.date) >= last)].head(1)
        lines.append(f"  EARNINGS: beat EPS estimate in {beats} of last {len(ea)} quarters, average surprise {surp:+.1%}"
                     + (f"; next report {nxt.date.iloc[0]} (est. EPS {nxt.epsEstimated.iloc[0]})" if len(nxt) else ""))
    ins = read(s, "insider_stats")
    if len(ins):
        i4 = ins.sort_values(["year", "quarter"]).tail(4)
        lines.append(f"  INSIDERS (last 4 quarters): {int(i4.totalPurchases.sum())} purchases, {int(i4.totalSales.sum())} sales")
    dcf = read(s, "dcf")
    if len(dcf):
        lines.append(f"  FMP DCF value {dcf.dcf.iloc[0]:.0f} vs price {p.price:.0f} (FMP's own model; reference only)")
    seg = read(s, "segments_product")
    if len(seg):
        sg = seg.sort_values("fiscalYear").iloc[-1]
        parts = {c[5:]: v for c, v in sg.items() if c.startswith("data.") and pd.notna(v) and v > 0}
        tot = sum(parts.values())
        lines.append(f"  SEGMENTS FY{sg.fiscalYear}: " + "; ".join(f"{k} {v / tot:.0%}" for k, v in sorted(parts.items(), key=lambda x: -x[1])[:6]))
    # long history from 10-Ks
    e = pd.read_csv(f"data/phase3/edgar/{s}.csv", index_col=0, parse_dates=True)
    e = e[e.index.year >= e.index.year.max() - 10]
    rv, ni = e.revenue.dropna(), e.net_income.dropna()
    lines.append(f"  10-K HISTORY ({e.index.year.min()}-{e.index.year.max()}): revenue {rv.iloc[0] / 1e9:.2f}B -> {rv.iloc[-1] / 1e9:.2f}B "
                 f"({cagr(rv.iloc[0], rv.iloc[-1], (rv.index[-1] - rv.index[0]).days / 365.25):+.1%}/yr); net income "
                 f"{ni.iloc[0] / 1e9:.2f}B -> {ni.iloc[-1] / 1e9:.2f}B ({cagr(ni.iloc[0], ni.iloc[-1], (ni.index[-1] - ni.index[0]).days / 365.25):+.1%}/yr); "
                 f"loss years: {int((ni < 0).sum())}")
    lines.append("    net margin by year: " + " ".join(f"{d.year % 100:02d}:{v:.0%}" for d, v in (e.net_income / e.revenue).dropna().items()))
R3 = pd.DataFrame(rets).iloc[-756:]
for x in ["SPY", "IEF", "AQMIX"]:
    R3[x] = closes(pd.read_csv(f"{R}/market/prices_{x}.csv")).pct_change().reindex(R3.index)
C = R3.corr()
C.round(2).to_csv(f"{R}/correlations.csv")
lines += ["=" * 100, "CORRELATIONS (3 years of daily returns), average with the other picks:"]
lines.append("  " + "; ".join(f"{s} {C.loc[s, PICKS].drop(s).mean():.2f}" for s in PICKS))
lines.append("  with IEF: " + "; ".join(f"{s} {C.loc[s, 'IEF']:.2f}" for s in PICKS) + f"; AQMIX with SPY {C.loc['AQMIX', 'SPY']:.2f}")
tr = pd.read_csv(f"{R}/market/treasury_rates.csv").sort_values("date").iloc[-1]
lines.append(f"TREASURY RATES {tr.date}: 3m {tr.month3}%, 1y {tr.year1}%, 10y {tr.year10}%")
open(f"{R}/factsheets.txt", "w").write("\n".join(lines) + "\n")
print("\n".join(lines))
