# Launch order sheet — Thursday 2026-11-12

Account: IBKR paper DUT162870. Sized on **$1,000,000** (the account shows ~$1,004,372; the extra ~$4,400 stays as cash, outside the portfolio).
Rules: IPS v1 (approved 2026-11-11). Planned prices = 2026-11-11 close (FMP). Copart is NOT bought at launch: it waits for its Nov 19 earnings checkpoint; its money sits in VTI.

## Orders (in this order)

| # | Ticker | What | Target at launch | Shares | Planned price | Planned $ | % of $1M | Max limit (planned +1%) |
|---|---|---|---|---|---|---|---|---|
| 1 | IEF | Treasuries 7-10y, full position | $427,500 | 4,700 | $90.94 | $427,418 | 42.74% | $91.85 |
| 2 | KMLM | Managed futures, full position | $50,000 | 1,708 | $29.26 | $49,976 | 5.00% | $29.55 |
| 3 | GNTX | Quality, half of 8.05% | $40,250 | 2,055 | $19.58 | $40,237 | 4.02% | $19.78 |
| 4 | EOG | Quality, half of 8.05% | $40,250 | 261 | $153.77 | $40,134 | 4.01% | $155.31 |
| 5 | ITW | Quality, half of 8.05% | $40,250 | 139 | $288.72 | $40,132 | 4.01% | $291.61 |
| 6 | INGR | Quality, half of 8.05% | $40,250 | 433 | $92.83 | $40,195 | 4.02% | $93.76 |
| 7 | MA | Long-term growth, half of 6% | $30,000 | 45 | $660.73 | $29,733 | 2.97% | $667.34 |
| 8 | VTI | Holding place for unbought stock money (re-size last) | ~$331,500 | 887 | $374.25 | $331,960 | 33.20% | $377.99 |

VTI holds: 4 quality second halves ($161,000) + dip slot ($80,500) + Copart full ($60,000) + Mastercard second half ($30,000) = $331,500.
**Order 8 is re-sized after 1-7 fill:** VTI shares = (1,000,000 - total spent on 1-7) / VTI price, rounded down.

## Pre-trade checks (all pass on planned numbers)

| Check | Limit | Planned |
|---|---|---|
| Stock exposure (stocks + VTI) | 52.25% | 52.24% |
| Largest single stock | <= 12% | 4.02% at launch (8.05% at full size) |
| Largest sector | <= 20% | 4.02% at launch (16.1% at full size: INGR + CL) |
| Stocks per sector | <= 2 | max 1 at launch |
| Only approved names | decision log | yes |
| Leverage / shorting | none | none (cash left ~$215 + the extra ~$4,372) |

## Launch-day steps

1. **Before the open:** check news on all 7 names. If any has a thesis-breaking headline, stop that order and tell Claude.
2. **Wait until 9:45 ET** (skip the first 15 minutes). Stop placing new orders after 3:45 ET.
3. **Refresh prices.** If a price is more than 2% above the planned price, recompute its shares (target $ / new price, rounded down) and log why.
4. **Place orders 1-7 as LIMIT, DAY:** limit = current ask, never above the max limit column. Use Preview, then Transmit.
5. **If not filled in 15 minutes:** move the limit to the new ask (still under the max limit). If the max limit is hit, leave it and decide with Claude; do not chase.
6. **KMLM** trades less: use a limit at the ask, be patient.
7. **After 1-7 fill:** re-size and buy VTI (order 8) with the remainder.
8. **Log every fill** in `data/trades/trade_log.csv` (date, time, price, shares, commission, price vs plan, reason).
9. **Screenshot** the Portfolio tab at the close; that is day 0 of the track record (vs 55% VTI / 45% IEF from the same day's close).

## After launch

- **Nov 19 (Copart FQ1):** if US insurance units ex-lost-insurer are not shrinking again, buy Copart's launch half (~$30,000) from VTI. If they are, revisit before buying.
- Staged halves: bought over 3-6 months; Copart <= $32.50 and Mastercard <= $660 for their second halves; INGR's second half only if its 2027 EPS guide (Feb 2027) is >= $10.
- Dip slot: EHC below ~$120 (now $142.24) or CL below $87 (now $98.00). Checked at each monthly rebalance.
