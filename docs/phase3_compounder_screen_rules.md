# Phase 3 long-term compounder screen: rules fixed before any data is pulled

Written 2026-11-01 with Landon, before this screen's data is downloaded or run. Changes go in the amendment log at the bottom, dated, with the reason. It sources ideas for the **long-term growth sleeve** (2 slots; decision log 2026-11-01). Every finalist still needs a full pitch, the long-term bar in docs/phase3_growth_screen_rules.md (amendment 2026-11-01), a red-team review and Landon's approval.

## Why a new screen

The growth screen (2026-10-29) asked "who is growing fast now?" (3-year and trailing-12-month growth). With a 15-30 year horizon the question is "who has compounded for a decade and can keep going?" The answer needs 10 years of history, proof of a lasting edge (high returns on capital, year after year), and a price that still leaves a decent long-run return. Its results stand on their own; the growth screen's results stay on record.

## 1. Universe (on the run date)

Same as the quality screen (US-listed, US companies, market value at least $2 billion, average daily trading at least $20 million over 3 months, no funds, ETFs, partnerships, preferred shares, units, warrants or shells, one share class per company), with one change: **financial companies whose accounts work like ordinary businesses are allowed**: FMP industries "Financial - Credit Services" (payment networks such as Visa and Mastercard) and "Financial - Data & Stock Exchanges" (exchanges, ratings and index firms). Banks, insurers, asset managers, brokers and mortgage firms stay out (debt is their raw material). Lenders inside "Credit Services" (card lenders) should fail the debt rule; any that do not are removed in the review step, with the reason written down. Real Estate stays out.

## 2. Hard filters (all must pass), from the last 10 fiscal years (11 years of statements)

1. **Steady growth:** revenue grew at least 10% a year over 10 years (latest year vs 10 years earlier), and rose year over year in at least 8 of the 10 years.
2. **A lasting edge:** return on invested capital at least 15% in at least 8 of the 10 years. ROIC = operating income x (1 - tax rate) / average invested capital (total debt + equity - cash and short-term investments, average of the year's start and end). Tax rate = income tax / pre-tax income, kept between 0% and 35%; 21% if not measurable. Invested capital at or below zero with positive operating income counts as above 15% (an asset-light business).
3. **Pricing power holding up:** latest gross margin no more than 5 percentage points below its 10-year average. If gross profit is reported equal to revenue (no cost of revenue line), this rule is recorded as "not measurable" and passes.
4. **Self-funding:** free cash flow (operating cash flow minus capital spending) positive in at least 8 of the 10 years.
5. **Debt:** net debt (total debt minus cash and short-term investments, latest year) at most 2.0 times the latest year's EBITDA. Net cash passes; EBITDA at or below zero with net debt fails.
6. **Little dilution:** diluted share count grew no more than 2% a year over 10 years.
7. **Long-run return of at least 9% a year**, estimated as:
   - **Yield:** latest year's free cash flow minus stock-based pay after 21% tax, divided by today's market value;
   - **plus growth:** the average of the 10-year revenue growth rate and 5% (fast growth fades over decades toward the economy's pace), at most 15%;
   - **plus or minus valuation drift:** the change, spread over 10 years, if enterprise value / sales moves from today's level to its median of the last 10 year-ends ((median / today)^(1/10) - 1).

A company with a missing number needed by a rule is excluded and counted as "missing data".

## 3. Score and list

Among companies that pass: **durability** = average of two percentile ranks, the 10-year median ROIC (higher is better) and the steadiness of yearly revenue growth (standard deviation, lower is better); **return** = percentile rank of the long-run return from rule 7. Score = half durability, half return. The output lists the top 30 with no sector limit and marks names already on the quality research list.

## 4. Review step (written, before full research)

For the top 10: a short "20-year view" each (edge, room to reinvest, balance sheet, management). Set aside, with the reason written down: names Landon has excluded (NVDA: chip leadership is hard to rely on over decades), companies dependent on one product whose protection ends within about 10 years, lenders that slipped through, and one-offs (a large deal after the latest fiscal year, under the existing 10% standard). Landon picks finalists for full research.

## Implementation

- FMP Starter: annual income, balance-sheet and cash-flow statements (11 years), annual key metrics (10 years, for enterprise value / sales history), screener on the run date; cached in data/phase3/raw/. Rule 1 is applied first so the other downloads are only made for companies that pass it.
- Consistency: fiscal year-ends 350-380 days apart and the latest no more than about 15 months before the run date; otherwise missing data.
- Prices and trading volume from Yahoo for companies that pass all filters (liquidity rule; 1-year volatility reported, not scored).

## Amendment log

| Date | Change | Reason |
|---|---|---|
