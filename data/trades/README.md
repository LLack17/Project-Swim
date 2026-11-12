# Trade and options logs

Every trade in the Project Swim paper account (IBKR DUT162870) is logged here the same day, one row per fill.
These files are the official record of the track record; IBKR statements are the cross-check.

## trade_log.csv (one row per fill)

| Column | Meaning | Example |
|---|---|---|
| date | Trade date (YYYY-MM-DD) | 2026-11-12 |
| time_et | Fill time, US Eastern (HH:MM) | 09:52 |
| account | IBKR account | DUT162870 |
| ticker | Symbol | EOG |
| action | BUY or SELL | BUY |
| shares | Shares filled in this row (partial fills = separate rows) | 261 |
| order_type | LMT (limit) | LMT |
| limit_price | Limit on the order when it filled | 154.10 |
| fill_price | Average fill price for this row | 154.02 |
| commission | IBKR commission in USD | 1.00 |
| amount | shares x fill_price + commission (BUY) or - commission (SELL) | 40200.22 |
| planned_price | Reference price on the committed order sheet | 153.77 |
| price_vs_plan_pct | (fill_price / planned_price - 1) x 100, 2 decimals | 0.16 |
| reason | Why: launch, staged buy, rebalance, dip slot, thesis broken, error correction ... | launch |
| ips_rule | IPS section or decision-log date the trade follows | IPS 4; decision 2026-11-11 |
| notes | Anything unusual (partial fill, limit moved, halt) | limit moved once |

## options_log.csv (one row per hedge; fill in the first 6 columns BEFORE trading)

| Column | Meaning |
|---|---|
| date_opened | Date the hedge is bought |
| ticker | Stock being hedged (must be owned) |
| shares_owned | Shares owned that day; contracts x 100 may not exceed this |
| event_and_date | The dated event the hedge covers (e.g. "Copart FQ2 earnings, 2027-02-19") |
| why_it_could_break_thesis | One sentence, tied to the stock's "what proves it wrong" list |
| instrument | PUT or COLLAR (collar = buy put + sell call on owned shares) |
| strike | Put strike (and call strike for a collar, "put/call") |
| expiry | Expiry date (no more than 6 months out) |
| contracts | Number of contracts (100 shares each) |
| premium_paid | Net premium in USD incl. commissions (collar: put cost minus call income) |
| budget_used_ytd | Total premium spent this calendar year incl. this one (cap $5,000) |
| date_closed | Date sold or expired |
| result | Premium recovered / payoff in USD, and one line on whether the hedge did its job |
| notes | Anything else |
