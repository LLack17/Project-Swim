# Phase 3 long-term compounder screen (long-term growth sleeve). Rules: docs/phase3_compounder_screen_rules.md
# (fixed 2026-11-01, before any data was pulled).
# Usage, from the repo root (FMP Starter; roughly 1,300 calls plus 3 per company that passes rule 1; Yahoo for prices):
#   python scripts/phase3/compounder_screen.py
# Output: data/phase3/compounder_screen_results.txt (filter counts + top 30) and data/phase3/compounder_screen_scores.csv.
# Raw downloads are cached in data/phase3/raw/ (git-ignored), so a rerun continues where it stopped.
import datetime
import os
import sys
import numpy as np
import pandas as pd

sys.path.insert(0, "scripts/phase3")
import screen_engine as S  # noqa: E402
import compounder_engine as C  # noqa: E402
import sources as D  # noqa: E402

OUT = "data/phase3"
RESEARCH_LIST = {"EHC", "GILD", "INGR", "CL", "BYD", "GNTX", "ITW", "AOS", "VNT", "EEFT", "CARG", "EOG", "SHW"}
RULES = [("r2", "ROIC >= 15% in 8+ of 10 years"), ("r3", "gross margin within 5 pts of 10-yr average"),
         ("r4", "free cash flow positive in 8+ of 10 years"), ("r5", "net debt <= 2x EBITDA (or net cash)"),
         ("r6", "diluted shares +2%/yr at most (10 yrs)"), ("r7", "estimated long-run return >= 9%/yr")]
lines = []


def log(s=""):
    print(s, flush=True)
    lines.append(s)


def finish():
    os.makedirs(OUT, exist_ok=True)
    with open(f"{OUT}/compounder_screen_results.txt", "w") as f:
        f.write("\n".join(lines) + "\n")
    print(f"\nSaved {OUT}/compounder_screen_results.txt")


def _on_error(exc_type, exc, tb):
    if exc_type is not SystemExit:
        log(f"\nERROR, screen stopped: {exc_type.__name__}: {exc}")
        finish()
    sys.__excepthook__(exc_type, exc, tb)


sys.excepthook = _on_error
key = lambda x: x.get("date", "")  # noqa: E731
annual = lambda ep, sym, n: sorted(D.fmp(ep, symbol=sym, period="annual", limit=n) or [], key=key, reverse=True)  # noqa: E731

log("PHASE 3 LONG-TERM COMPOUNDER SCREEN")
log("=" * 100)
RUN = datetime.date.today()
log(f"Run date {RUN}; rules: docs/phase3_compounder_screen_rules.md")

# ======================= UNIVERSE =======================
rows = []
for ex in ["NYSE", "NASDAQ", "AMEX"]:
    got = D.fmp("company-screener", cache_tag=str(RUN), marketCapMoreThan=int(2e9), country="US", exchange=ex,
                isEtf="false", isFund="false", isActivelyTrading="true", limit=10000) or []
    if len(got) >= 10000:
        raise ValueError(f"screener returned its row limit for {ex}: list may be cut off")
    rows += got
scr = pd.DataFrame(rows).drop_duplicates("symbol")
d = scr[(scr.country == "US") & (~scr.isEtf.astype(bool)) & (~scr.isFund.astype(bool)) & scr.isActivelyTrading.astype(bool)]
log("\nUNIVERSE (companies left after each step)")
log(f"  {'US, not a fund, actively trading, $2B+':52s} {len(d):6d}")
d = C.universe_filter(d[d.marketCap >= 2e9])
log(f"  {'no banks/insurers/REITs (payments, exchanges in)':52s} {len(d):6d}")
d = d[~d.symbol.str.contains(r"[-.]", regex=True)]
d = d.sort_values("volume", ascending=False).drop_duplicates("companyName", keep="first")
d = d[~d.companyName.map(S.is_partnership)].reset_index(drop=True)
log(f"  {'common stock, one class, not a partnership':52s} {len(d):6d}")

# ======================= RULE 1 (income statements only) =======================
inc_all, r1_pass, miss1 = {}, [], 0
for i, r in enumerate(d.itertuples(index=False)):
    if i % 250 == 0:
        print(f"  income statements {i}/{len(d)}", flush=True)
    inc = annual("income-statement", r.symbol, C.YEARS + 1)
    res = C.cagr_rule(inc, RUN)
    if res is None:
        miss1 += 1
        continue
    inc_all[r.symbol] = inc
    if res[0]:
        r1_pass.append(r.symbol)
log(f"  {'11 years of consistent statements':52s} {len(d) - miss1:6d}   (removed {miss1} as missing data)")
log(f"  {'revenue +10%/yr over 10 yrs, up in 8+ of 10':52s} {len(r1_pass):6d}")

# ======================= RULES 2-7 =======================
caps = d.set_index("symbol")
recs, miss2 = [], 0
for sym in r1_pass:
    bal = annual("balance-sheet-statement", sym, C.YEARS + 1)
    cf = annual("cash-flow-statement", sym, C.YEARS + 1)
    km = annual("key-metrics", sym, C.YEARS)
    row = caps.loc[sym]
    m = C.metrics(inc_all[sym], bal, cf, [x.get("evToSales") for x in km], float(row.marketCap), RUN)
    if m["missing"]:
        miss2 += 1
        continue
    recs.append({"symbol": sym, "companyName": row.companyName, "sector": row.sector, "industry": row.industry,
                 "marketCap": float(row.marketCap), **{k: v for k, v in m.items() if k != "missing"}})
M = pd.DataFrame(recs)
log(f"  {'balance sheet, cash flow, valuation history complete':52s} {len(M):6d}   (removed {miss2} as missing data)")
if M.empty:
    raise ValueError("no company has complete data")
left = M.copy()
for r_, lab in RULES:
    left = left[left[r_]]
    log(f"  {lab:52s} {len(left):6d}")

prices = D.yahoo_prices(left.symbol.tolist(), RUN)
stats = {s: S.price_stats(prices[s]) if s in prices else (np.nan, np.nan) for s in left.symbol}
left = left.assign(volatility=left.symbol.map(lambda s: stats[s][0]) * np.sqrt(252),
                   dollar_volume=left.symbol.map(lambda s: stats[s][1]))
n0 = len(left)
left = left[left.dollar_volume.notna()]
log(f"  {'price history available (Yahoo)':52s} {len(left):6d}   (removed {n0 - len(left)} as missing data)")
left = left[left.dollar_volume >= 20e6]
log(f"  {'average daily trading >= $20M (last 3 months)':52s} {len(left):6d}")
if left.empty:
    raise ValueError("no company passed every rule")

SC = C.score(left)
top = SC.head(30)
log(f"\nTOP {len(top)} by score (half durability: 10-yr median ROIC and steady growth; half estimated long-run return)")
log(f"  {'#':>3s} {'symbol':7s} {'company':28s} {'sector':20s} {'mkt cap':>8s} {'10y gr':>6s} {'ROIC md':>7s} "
    f"{'gross':>6s} {'FCF yld':>7s} {'drift':>6s} {'exp ret':>7s} {'vol':>5s} {'score':>6s}")
for k, r in top.iterrows():
    flag = " *" if r.symbol in RESEARCH_LIST else ""
    roic = "n/m" if np.isinf(r.roic_median) else f"{r.roic_median * 100:5.0f}%"
    log(f"  {k + 1:3d} {r.symbol:7s} {str(r.companyName)[:28]:28s} {str(r.sector)[:20]:20s} {r.marketCap / 1e9:7.1f}B "
        f"{r.cagr10 * 100:5.0f}% {roic:>7s} {r.gross_margin * 100:5.0f}% {r.fcf_yield * 100:6.1f}% {r.drift * 100:5.1f}% "
        f"{r.exp_return * 100:6.1f}% {r.volatility * 100:4.0f}% {r.score:6.1f}{flag}")
log("  * already on the quality research list")
log("\nSector count in the top 30: " + ", ".join(f"{s} {n}" for s, n in top.sector.value_counts().items()))
cols = ["symbol", "companyName", "sector", "industry", "marketCap", "cagr10", "up_years", "growth_sd", "roic_years_15",
        "roic_median", "gross_margin", "gross_margin_avg10", "gm_note", "fcf_pos_years", "net_debt_ebitda", "dilution",
        "fcf_yield", "growth_est", "ev_sales_now", "ev_sales_median10", "drift", "exp_return"] + [f"r{k}" for k in range(1, 8)]
out = M.merge(SC[["symbol", "volatility", "durability", "return_rank", "score"]], on="symbol", how="left")
out.assign(passed_all=out.symbol.isin(SC.symbol)).sort_values("score", ascending=False)[
    cols + ["passed_all", "volatility", "durability", "return_rank", "score"]].to_csv(f"{OUT}/compounder_screen_scores.csv", index=False)
log(f"\nAll {len(M)} companies that reached the full checks: {OUT}/compounder_screen_scores.csv")
log("\nNotes: FMP annual statements (11 fiscal years) and key metrics; market values on the run date; prices from Yahoo.")
log("ROIC n/m = invested capital at or below zero with profits (counted as above 15%). Expected return = FCF yield after")
log("stock pay + faded growth + EV/sales drift toward its 10-yr median. The screen sources ideas only: review step next.")
finish()
