# Launch-day steps — Thursday 2026-11-12

The plan was written and committed before any trade. Follow it in order; if something is not covered here, stop and
decide with Claude, then log what was decided and why. Times are US Eastern.

## Night before (Wed Nov 11)

- [ ] Commit the launch package (IPS sign-off, order sheet script and tests, these steps, empty trade and options logs).
- [ ] In IBKR paper (DUT162870): **Orders** tab shows no open or leftover orders; **Portfolio** shows no positions;
      cash about $1,004,372. If anything is already there (e.g. a preview that was sent by mistake), cancel or close
      it and tell Claude before launch.

## Morning, before the open (8:30–9:30)

- [ ] **News check** on GNTX, EOG, ITW, INGR, MA (and KMLM, IEF for anything unusual). Stop an order only if the news
      plausibly breaks that stock's written thesis (see its "what proves it wrong" list). Log the reason.
- [ ] **Market check:** no market-wide halt or broken open. If the S&P 500 opens down more than 3%, wait until 11:00
      and decide with Claude; the plan does not change, only the timing.

## At 9:40 — final order sheet

- [ ] Run, from the repo root:
      `conda activate project-swim && python scripts/launch/test_order_sheet.py && python scripts/launch/order_sheet.py --date 2026-11-12`
- [ ] Check the bottom line says **"All checks pass: OK to trade."** If any check FAILS, do not trade; send it to Claude.
- [ ] Compare a couple of reference prices with IBKR's quotes. If Yahoo looks stale, re-run with IBKR asks, e.g.
      `--price GNTX=19.61 --price EOG=154.10` (any ticker you pass overrides Yahoo).
- [ ] Commit the final order sheet **before the first trade**:
      `git add docs/launch/order_sheet_2026-11-12.md data/trades/planned_orders_2026-11-12.csv && git commit -m "Final launch order sheet (pre-trade)" && git push`

## 9:45–3:45 — placing orders

For each of orders 1–7, in order (IEF, KMLM, GNTX, EOG, ITW, INGR, MA):

1. **Buy · Limit · DAY · shares from the sheet · limit price = the sheet's MAX LIMIT.** This is a "marketable limit"
   order: it fills right away at the best available price, and the max limit is only a ceiling that is never exceeded.
   (IBKR paper shows DELAYED quotes, so don't set the limit from IBKR's ask; use the sheet.)
2. **Preview** → check ticker, side (BUY), shares, limit, account DUT162870 → **Transmit**.
3. **Not filled within 5 minutes?** The price has moved above the max limit. Don't chase: wait 30 minutes. If it is
   still unfilled, cancel, re-run the order sheet for that ticker with a fresh price, commit it with a note, and
   re-place at the new max limit.
4. **Partial fill?** Leave the rest working at the same limit; log each fill as its own row.
5. **Log the fill** in `data/trades/trade_log.csv` right away (one row per fill; see `data/trades/README.md`).

Notes by ticker:
- **IEF** is very liquid: should fill within seconds at the ask.
- **KMLM** trades less and has a wider spread; its max limit is 1% over the reference, so it still fills at the best
  available price under that ceiling.

**Order 8, VTI (after 1–7 have filled):** shares = (1,000,000 − total $ actually spent on 1–7 incl. commissions) ÷ VTI ask,
rounded down. Limit = the sheet's VTI max limit. Log it.

**Stop placing new orders at 3:45.** Anything unfilled is cancelled at the close (DAY orders); re-place it the next
morning from the same sheet and log the delay.

## If something goes wrong

| Problem | What to do |
|---|---|
| Wrong quantity or wrong ticker filled | Don't panic-trade. Log it as filled, tell Claude, fix with one correcting order, log that too with reason "error correction". |
| A stock is halted | Skip it, finish the rest, retry it next day. Its money stays in cash (not VTI) until then. |
| IBKR app down / "Load failed" | Restart the app; if still down, use IBKR Client Portal in the browser. Same orders. |
| Order rejected | Screenshot the message, send to Claude; don't work around it. |
| Order sits unfilled (price above max limit) | Step 3 above: wait 30 min, then re-run the sheet for that ticker. |

## After the close (4:00–5:00)

- [ ] **Reconcile:** IBKR Portfolio shares = shares in the trade log, ticker by ticker. Fix any mismatch in the log.
- [ ] **Day 0 record:** fill in `data/performance/day0_2026-11-12.md` (portfolio value, cash, each position's close,
      VTI and IEF closes for the 55/45 benchmark and CPI + 4% start date).
- [ ] **Screenshot** the Portfolio tab and save it as `private/launch/portfolio_2026-11-12.png` (screenshots stay private).
- [ ] Commit the results: `git add data/trades/trade_log.csv data/performance/day0_2026-11-12.md && git commit -m "Launch fills and day-0 record (2026-11-12)" && git push`

## Next dates

- **Nov 19, after Copart's report:** apply its checkpoint (US insurance units excluding the lost insurer). Pass → buy
  Copart's launch half (~$30,000) by selling the same amount of VTI, both logged. Fail → revisit before buying.
- **Each month (first trading day):** rebalance (1-point threshold), sweep dividends, check staged halves and dip-slot prices.
