# Phase 3 stock screen: rules fixed before any data is pulled

Written 2026-10-28, before the screen's data is downloaded or run. Changes after this date go in the amendment log at the bottom, dated, with the reason. The screen sources ideas; it does not pick stocks. Every pick still needs a full pitch memo and Landon's approval.

## Where the rules come from

| Rule | Evidence |
|---|---|
| Value, quality and low volatility as the score | Phase 2B stock style test (2B-G): each beat the market in at least 3 of the 4 US crashes after inflation; growth beat it in 1 |
| Equal-weight average of the three | Value failed in 2007-09 (cheap stocks were fragile lenders) and quality failed in 1973-74 (the Nifty Fifty); combining covers each one's weak spot |
| Hard filters on profits, debt, short-term funding and cash flow | The company lessons from the four crash case studies (1973-74, 2000-02, 2007-09, 2022) |
| No banks, insurers or REITs | Their accounts do not fit these measures (debt is their raw material); 2008 showed the risk of misreading them |
| At most 2 stocks per sector, 6-8 stocks | Mandate: at least 6 stocks, no stock above 12%, no sector above 20% of the portfolio, stock part about 50% (49.5% after the managed-futures fund check) |
| $2B+ market value and $20M+ daily trading | Matches institutional mid/large-cap practice; liquid listed options are needed for the hedging overlay |

## 1. Universe (on the screen date)

- US-listed common stocks of US-domiciled companies (NYSE, NASDAQ, NYSE American).
- Market value of at least $2 billion.
- Average daily dollar trading volume of at least $20 million over the last 3 months.
- Excluded: Financial Services and Real Estate sectors (FMP sector labels), funds, ETFs, SPACs, preferred shares, and companies with zero or negative book equity (their book-to-price and profitability are not meaningful; the Ken French portfolios used in 2B-G exclude them too).

## 2. Hard filters (all must pass)

Using the three most recent fiscal years in FMP's annual statements as of the screen date.

1. **Profits now, not promised:** operating income above zero in each of the 3 years.
2. **Leverage limit:** net debt (total debt minus cash and short-term investments) no more than 3.0 times EBITDA in the latest year. Net cash passes. EBITDA at or below zero fails.
3. **Short-term funding:** short-term debt (debt due within a year) no more than cash and short-term investments plus the latest year's operating cash flow.
4. **Cash backs up profits:** operating cash flow summed over the 3 years at least 80% of net income summed over the same years.

A company with a missing number needed by a filter is excluded and counted as "missing data".

## 3. Score

Each measure is turned into a percentile rank (0-100) among the companies that pass the filters.

- **Value** = average of three ranks: book-to-price (book equity / market value), earnings yield (EBIT / enterprise value) and free-cash-flow yield (operating cash flow minus capital spending, divided by market value), latest fiscal year, market values on the screen date.
- **Quality** = rank of operating profitability as in the Ken French data used in 2B-G: (revenue minus cost of goods sold minus selling, general and administrative expense minus interest expense) / book equity, latest fiscal year.
- **Low volatility** = rank of the standard deviation of daily returns over the last 252 trading days, lowest volatility ranked highest.
- **Combined score** = average of the value, quality and low-volatility ranks. Ties go to the higher quality rank.

## 4. Shortlist

- The 30 highest combined scores, at most 2 per sector (FMP sector labels): when a sector already has 2, the next-best company from another sector takes the place.
- The output lists every shortlisted company's three ranks, the filter results, and how many companies each step removed.

## 5. After the screen (judgment, not formula)

1. Claude writes one paragraph per shortlisted company: what it does, why it scored well, any obvious red flag.
2. Landon picks 10-12 for a closer look.
3. 6-8 get full pitch memos (Research & Reporting Outline: business, moat, financial-statement quality, valuation by DCF and comps, catalysts, bull/base/bear, "I'm wrong if...", hedge design where relevant, sizing), each red-teamed before approval.
4. Each approved pick is committed to the repo with the date, price and thesis before it is bought.
5. Pricing power and honest accounts are judged in the memos, since a formula cannot measure them well.

## Data and reproducibility

- Financial Modeling Prep (FMP) Starter plan, one month. Raw FMP data stays out of the public repo (git-ignored) because its terms limit redistribution; the script, the rules and the summary results are committed, so anyone with an FMP key can rerun the screen.
- The screen date and the FMP data date are printed in the results.

## Amendment log

| Date | Change | Reason |
|---|---|---|
