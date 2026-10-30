# Phase 3 growth screen: rules fixed before any data is pulled

Written 2026-10-29, before the growth screen's data is downloaded or run. Changes after this date go in the amendment log at the bottom, dated, with the reason. Like the quality screen (docs/phase3_screen_rules.md), it sources ideas only: every pick needs a full pitch memo (with the extra growth research below), a red-team review and Landon's approval.

## Why a growth sleeve, given 2B-G

The 2026-10-27 decision said the stock screen has no growth tilt, because growth beat the market in only 1 of 4 crashes (2B-G). That finding stands, and the quality sleeve keeps it. The growth sleeve exists for a different reason: the benchmark is 55% VTI, which carries a large weight in fast-growing large companies, and a stock part made only of value/quality/low-volatility names would trail it badly in a growth-led market. So the sleeve is limited, sized by risk, and is the first candidate for the protective put / collar overlay, which addresses the crash weakness 2B-G found.

## Portfolio structure (two sleeves)

| Sleeve | Names | Weight |
|---|---|---|
| Quality | 4-5, from the 13-name research list | at least 65% of the stock part |
| Growth | 2 (the growth sleeve has two slots) | at most 35% of the stock part; at most 6% of the total portfolio per name |

The mandate still applies to the whole: 6-8 stocks, no stock above 12%, no sector above 20% (at most 2 per sector across both sleeves), positions sized by risk.

## 1. Universe

Same as the quality screen: US-listed common stocks of US-domiciled companies, market value at least $2 billion, average daily trading at least $20 million over the last 3 months, no Financial Services or Real Estate sector, no funds, ETFs, partnerships, preferred shares, units or warrants, one share class per company.

## 2. Hard filters (all must pass)

"TTM" = the last four reported quarters; "prior TTM" = the four quarters before those.

1. **Fast growth, sustained:** revenue grew at least 20% a year over 3 fiscal years (latest annual revenue vs 3 years earlier).
2. **Still growing fast now:** TTM revenue at least 15% above prior-TTM revenue.
3. **A real margin:** TTM gross margin at least 40%.
4. **Rule of 40:** TTM revenue growth plus TTM free-cash-flow margin at least 40 percentage points.
5. **Cash flow, loose version (Landon's choice):** TTM free-cash-flow margin at least 0%, OR at least -10% and higher than the prior-TTM margin (close to break-even and improving). Free cash flow = operating cash flow minus capital spending.
6. **Debt:** net debt (total debt minus cash and short-term investments, latest quarter) at most 2.0 times TTM EBITDA. Net cash passes; EBITDA at or below zero with net debt fails.
7. **Dilution:** diluted share count grew no more than 3% a year over the 3 fiscal years.
8. **Valuation guardrail, loose version (Landon's choice):** enterprise value / TTM revenue, divided by TTM revenue growth in percent, at most 0.8 (example: 24x sales passes at 30% growth). Enterprise value = market value + total debt - cash and short-term investments; at or below zero passes.

A company with a missing number needed by a filter is excluded and counted as "missing data". A gross margin of 100% or more (cost of revenue reported as zero) counts as missing.

## 3. Score and list

Among companies that pass, two percentile ranks (0-100): Rule of 40 (higher is better) and the valuation ratio from filter 8 (lower is better). Score = their average. The output lists the top 30 with no sector limit. Landon cleans the top 10 (one-offs, corporate actions under the existing 10% standard), picks 4-5 for full research, and 2 enter the portfolio.

## 4. Extra research for each growth pitch

The standard pitch format plus: a reverse valuation (what growth the price already assumes), market size and share runway, customer retention and unit economics, the competitive moat, stock-based pay counted as a real cost, and an options plan (each growth name is a collar candidate).

## Implementation

- FMP Starter: screener on the run date; annual income statements (4 years); quarterly income, cash-flow and balance-sheet statements (8 quarters); cached in data/phase3/raw/ (git-ignored). Prices and trading volume from Yahoo (adjusted, cached by run date), only for companies that pass the fundamental filters; 1-year volatility is reported, not scored.
- Consistency: annual fiscal years 350-380 days apart and the latest no more than about 15 months old; quarters 80-100 days apart and the latest no more than about 200 days old; otherwise missing data.
- FMP data was checked against SEC 10-K filings on 2026-10-28 (quality screen data check); this screen does not repeat that check.

## Amendment log

| Date | Change | Reason |
|---|---|---|
