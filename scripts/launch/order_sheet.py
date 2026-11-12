# Launch order sheet: turns the IPS target weights into share counts, limit prices and pre-trade checks.
# Usage, from the repo root, on launch morning (around 9:40 ET):
#     python scripts/launch/order_sheet.py                       # prices from Yahoo (yfinance)
#     python scripts/launch/order_sheet.py --price GNTX=19.61    # override any price (e.g. the IBKR ask)
#     python scripts/launch/order_sheet.py --date 2026-11-12 --price ... (all 8 tickers) for a fully manual run
# Output: docs/launch/order_sheet_<date>.md and data/trades/planned_orders_<date>.csv
#
# Rules come from the IPS v1 (approved 2026-11-11) and the decision log; nothing here is a new decision:
#   mix 52.25% US stocks / 42.75% IEF / 5% KMLM; equal weights within sleeve (quality 8.05% x 5 places, growth 6% x 2);
#   launch buys IEF and KMLM in full and half of each picked stock; Copart waits for its Nov 19 checkpoint (decision
#   2026-11-11); the dip-buy slot (EHC < ~$120 / CL < $87) is only bought at those prices; money not yet in a stock is
#   held in VTI so stock exposure stays at 52.25%. Limits: <= 12% per stock, <= 20% per sector, <= 2 stocks per sector,
#   approved names only, no leverage (cash never below zero). Sized on $1,000,000.
import argparse
import datetime as dt
import math
import os
import sys

CAPITAL = 1_000_000
STOCK_TARGET = 0.5225
CAP_STOCK, CAP_SECTOR, MAX_PER_SECTOR = 0.12, 0.20, 2
EXPOSURE_TOL = 0.0025                     # stock exposure (stocks + VTI) must be within 0.25 pt of 52.25%

# ticker: (name, sleeve, sector, full weight, fraction bought at launch, max-limit buffer over reference price)
PLAN = {
    "IEF":  ("iShares 7-10 Year Treasury Bond ETF", "Bonds", "Treasuries", 0.4275, 1.0, 0.003),
    "KMLM": ("KraneShares Mount Lucas Managed Futures", "Managed futures", "Managed futures", 0.05, 1.0, 0.010),
    "GNTX": ("Gentex", "Quality", "Consumer cyclical", 0.0805, 0.5, 0.005),
    "EOG":  ("EOG Resources", "Quality", "Energy", 0.0805, 0.5, 0.005),
    "ITW":  ("Illinois Tool Works", "Quality", "Industrials", 0.0805, 0.5, 0.005),
    "INGR": ("Ingredion", "Quality", "Consumer defensive", 0.0805, 0.5, 0.005),
    "MA":   ("Mastercard", "Long-term growth", "Financials", 0.06, 0.5, 0.005),
    "CPRT": ("Copart", "Long-term growth", "Industrials", 0.06, 0.0, 0.005),      # waits for Nov 19 checkpoint
}
DIP_SLOT = {"EHC": ("Encompass Health", "Healthcare"), "CL": ("Colgate-Palmolive", "Consumer defensive")}
DIP_WEIGHT = 0.0805
HOLDING = ("VTI", "Vanguard Total Stock Market ETF", 0.005)   # holding place for unbought stock money
APPROVED = set(PLAN) | set(DIP_SLOT) | {"VTI"}
ORDER = ["IEF", "KMLM", "GNTX", "EOG", "ITW", "INGR", "MA", "VTI"]   # placement order; VTI last (takes the remainder)


def parse_args(argv):
    p = argparse.ArgumentParser()
    p.add_argument("--date", default=dt.date.today().isoformat())
    p.add_argument("--price", action="append", default=[], help="TICKER=PRICE override (repeatable)")
    p.add_argument("--no-fetch", action="store_true", help="do not call Yahoo; every price must be given")
    p.add_argument("--out-md", default=None)
    p.add_argument("--out-csv", default=None)
    return p.parse_args(argv)


def fetch_prices(tickers):
    import yfinance as yf
    out = {}
    for t in tickers:
        fi = yf.Ticker(t).fast_info
        try:
            px = fi.last_price
        except Exception:                               # older/newer yfinance spellings
            px = fi["lastPrice"]
        if not px or px <= 0:
            raise ValueError(f"{t}: no price from Yahoo; pass --price {t}=...")
        out[t] = float(px)
    return out


def build(prices):
    """Return (orders, checks, notes). Pure function of prices; no I/O."""
    rows, spent = [], 0.0
    for t in ORDER[:-1]:
        name, sleeve, sector, w, frac, buf = PLAN[t]
        px = prices[t]
        target = CAPITAL * w * frac
        sh = math.floor(target / px)
        amt = sh * px
        spent += amt
        rows.append(dict(ticker=t, name=name, sleeve=sleeve, sector=sector, full_weight=w, launch_fraction=frac,
                         target_usd=target, ref_price=px, shares=sh, planned_usd=amt,
                         max_limit=round(px * (1 + buf), 2), weight_at_launch=amt / CAPITAL))
    t, name, buf = HOLDING
    px = prices[t]
    remainder = CAPITAL - spent
    sh = math.floor(remainder / px)
    amt = sh * px
    spent += amt
    rows.append(dict(ticker=t, name=name, sleeve="Holding (unbought stock money)", sector="US total market",
                     full_weight=None, launch_fraction=None, target_usd=remainder, ref_price=px, shares=sh,
                     planned_usd=amt, max_limit=round(px * (1 + buf), 2), weight_at_launch=amt / CAPITAL))
    cash = CAPITAL - spent

    stock_rows = [r for r in rows if r["sleeve"] in ("Quality", "Long-term growth")]
    exposure = sum(r["planned_usd"] for r in stock_rows) + rows[-1]["planned_usd"]
    checks = []

    def chk(name, limit, value, ok):
        checks.append((name, limit, value, "PASS" if ok else "FAIL"))

    chk("Stock exposure (stocks + VTI)", f"{STOCK_TARGET:.2%} +/- 0.25 pt", f"{exposure / CAPITAL:.2%}",
        abs(exposure / CAPITAL - STOCK_TARGET) <= EXPOSURE_TOL)
    big = max(stock_rows, key=lambda r: r["weight_at_launch"])
    chk("Largest stock at launch", f"<= {CAP_STOCK:.0%}", f"{big['weight_at_launch']:.2%} ({big['ticker']})",
        big["weight_at_launch"] <= CAP_STOCK)
    full = {t: v[3] for t, v in PLAN.items() if v[1] in ("Quality", "Long-term growth")}
    chk("Largest stock at full size", f"<= {CAP_STOCK:.0%}", f"{max(max(full.values()), DIP_WEIGHT):.2%}",
        max(max(full.values()), DIP_WEIGHT) <= CAP_STOCK)
    worst_sector, worst_count = 0.0, 0
    for dip, (_, dip_sector) in DIP_SLOT.items():          # check both possible dip-slot fills
        sec, cnt = {}, {}
        for t, w in full.items():
            s = PLAN[t][2]
            sec[s] = sec.get(s, 0) + w
            cnt[s] = cnt.get(s, 0) + 1
        sec[dip_sector] = sec.get(dip_sector, 0) + DIP_WEIGHT
        cnt[dip_sector] = cnt.get(dip_sector, 0) + 1
        s_max = max(sec, key=sec.get)
        c_max = max(cnt, key=cnt.get)
        if sec[s_max] > worst_sector:
            worst_sector, worst_sector_name = sec[s_max], f"{s_max}, if {dip} fills the dip slot"
        if cnt[c_max] > worst_count:
            worst_count, worst_count_name = cnt[c_max], f"{c_max}, if {dip} fills the dip slot"
    chk("Largest sector at full size", f"<= {CAP_SECTOR:.0%}", f"{worst_sector:.2%} ({worst_sector_name})",
        worst_sector <= CAP_SECTOR + 1e-9)
    chk("Stocks per sector at full size", f"<= {MAX_PER_SECTOR}", f"{worst_count} ({worst_count_name})",
        worst_count <= MAX_PER_SECTOR)
    chk("Only approved names", "decision log", ", ".join(r["ticker"] for r in rows),
        all(r["ticker"] in APPROVED for r in rows))
    chk("No leverage: cash left >= 0", ">= $0", f"${cash:,.2f}", cash >= 0)
    chk("Total invested <= capital", f"<= ${CAPITAL:,.0f}", f"${spent:,.2f}", spent <= CAPITAL)
    chk("Bonds and managed futures at full weight", "42.75% / 5.00% (within rounding)",
        f"{rows[0]['weight_at_launch']:.2%} / {rows[1]['weight_at_launch']:.2%}",
        abs(rows[0]["weight_at_launch"] - 0.4275) < 0.001 and abs(rows[1]["weight_at_launch"] - 0.05) < 0.001)
    held = {"Quality second halves": CAPITAL * 0.0805 * 0.5 * 4, "Dip slot": CAPITAL * DIP_WEIGHT,
            "Copart (waits for Nov 19)": CAPITAL * 0.06, "Mastercard second half": CAPITAL * 0.06 * 0.5}
    return rows, checks, held, cash, spent


def to_markdown(date, rows, checks, held, cash, spent, sources):
    L = [f"# Launch order sheet — {date}", "",
         "Account: IBKR paper DUT162870. Sized on **$1,000,000** (the account's extra ~$4,372 stays as cash, outside "
         "the portfolio). Rules: IPS v1, approved 2026-11-11. Generated by `scripts/launch/order_sheet.py`.", "",
         f"Reference prices: {sources}. **Max limit** = reference price + buffer (0.3% IEF, 1.0% KMLM, 0.5% others); "
         "never pay more. Copart is not bought today: it waits for its Nov 19 checkpoint, and its money sits in VTI.",
         "", "## Orders (place in this order)", "",
         "| # | Ticker | Sleeve | Full weight | Bought today | Shares | Ref. price | Planned $ | % of $1M | Max limit |",
         "|---|---|---|---|---|---|---|---|---|---|"]
    for i, r in enumerate(rows, 1):
        fw = f"{r['full_weight']:.2%}" if r["full_weight"] is not None else "—"
        fr = {1.0: "all", 0.5: "half"}.get(r["launch_fraction"], "remainder")
        L.append(f"| {i} | **{r['ticker']}** | {r['sleeve']} | {fw} | {fr} | {r['shares']:,} | ${r['ref_price']:,.2f} | "
                 f"${r['planned_usd']:,.0f} | {r['weight_at_launch']:.2%} | ${r['max_limit']:,.2f} |")
    L += ["", f"Total planned ${spent:,.0f}; cash left ${cash:,.2f}.", "",
          "**VTI (order 8) is re-sized after orders 1-7 fill:** shares = (1,000,000 - actual $ spent on 1-7) / VTI price, "
          "rounded down. Re-run this script with the fill prices, or do the division by hand.", "",
          "VTI holds, until each is bought:", ""]
    L += [f"- {k}: ${v:,.0f}" for k, v in held.items()]
    L += [f"- **Total: ${sum(held.values()):,.0f}**", "", "## Pre-trade checks", "",
          "| Check | Limit | Planned | Result |", "|---|---|---|---|"]
    L += [f"| {a} | {b} | {c} | **{d}** |" for a, b, c, d in checks]
    ok = all(c[3] == "PASS" for c in checks)
    L += ["", "**All checks pass: OK to trade.**" if ok else "**A CHECK FAILED: do not trade until it is resolved.**", "",
          "Launch-day procedure: `docs/launch/launch_day_steps.md`."]
    return "\n".join(L) + "\n", ok


def main(argv=None):
    a = parse_args(argv)
    tickers = ORDER
    overrides = {}
    for s in a.price:
        t, v = s.split("=")
        overrides[t.strip().upper()] = float(v)
    missing = [t for t in tickers if t not in overrides]
    if missing and a.no_fetch:
        raise SystemExit(f"--no-fetch needs a price for: {', '.join(missing)}")
    fetched = fetch_prices(missing) if missing else {}
    prices = {**fetched, **overrides}
    src = ("Yahoo last price at run time" if fetched and not overrides else
           "manual" if not fetched else f"Yahoo, with manual overrides for {', '.join(sorted(overrides))}")
    rows, checks, held, cash, spent = build(prices)
    md, ok = to_markdown(a.date, rows, checks, held, cash, spent, src + f" (run {dt.datetime.now():%Y-%m-%d %H:%M})")
    out_md = a.out_md or f"docs/launch/order_sheet_{a.date}.md"
    out_csv = a.out_csv or f"data/trades/planned_orders_{a.date}.csv"
    os.makedirs(os.path.dirname(out_md), exist_ok=True)
    os.makedirs(os.path.dirname(out_csv), exist_ok=True)
    with open(out_md, "w") as f:
        f.write(md)
    with open(out_csv, "w") as f:
        f.write("order,ticker,sleeve,full_weight,launch_fraction,ref_price,shares,planned_usd,weight_at_launch,max_limit\n")
        for i, r in enumerate(rows, 1):
            f.write(f"{i},{r['ticker']},{r['sleeve']},{r['full_weight'] if r['full_weight'] is not None else ''},"
                    f"{r['launch_fraction'] if r['launch_fraction'] is not None else ''},{r['ref_price']:.2f},"
                    f"{r['shares']},{r['planned_usd']:.2f},{r['weight_at_launch']:.6f},{r['max_limit']:.2f}\n")
    print(md)
    print(f"Saved {out_md} and {out_csv}")
    if not ok:
        sys.exit(1)


if __name__ == "__main__":
    main()
