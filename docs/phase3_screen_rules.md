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
| 2026-10-28 | **Shortlist: at most 4 per sector, not 2.** FMP uses 11 sectors; without Financial Services and Real Estate, 9 remain, so 2 per sector could never fill 30 places (maximum 18). The 2-per-sector limit belongs to the portfolio (20% sector cap) and still applies when the final 6-8 are picked. | Found while testing the script on made-up data, before any real data was pulled; Landon's choice. |
| 2026-10-28 | **Implementation details fixed before the first run.** (1) EBIT = FMP operating income. (2) Operating profitability follows the Ken French convention: a missing cost of goods sold, SG&A or interest expense counts as zero if at least one of the three is reported. (3) Enterprise value at or below zero counts as the cheapest earnings yield. (4) Volatility needs at least 240 daily returns; prices and dollar volume come from Yahoo (adjusted closes), cached by run date; the screen stops if more than 2% of the universe has no prices. (5) One share class per company (the most traded); symbols containing '-' or '.' are excluded (preferred shares, units, warrants, and a few dual-class names such as BF.B). (6) A company counts as missing data if its three statements are not for the same fiscal year-ends, its fiscal years are not consecutive, its latest year-end is more than about 15 months before the run date, or its revenue is zero. (7) **Data check:** FMP's revenue and net income for MSFT, PG and CAT must match their 10-K filings on SEC EDGAR within 2% for the latest fiscal year, or the screen stops; FMP total debt is also shown next to 10-K long-term debt (information: FMP's total debt may include leases, which makes the leverage filter stricter for heavy lessees). (8) SEC EDGAR is also used for the narrowed-down companies: annual 10-K figures back to about 2009 and a check of FMP's numbers against the filings (scripts/phase3/edgar_history.py). | Choices the rules left open, written down before any screen data is pulled; the data check and the consistency rules came from an independent code review. |
| 2026-10-28 | **Fix to the SEC filing reader (no rule change).** The first run stopped at the data check: Caterpillar's net income showed as not found because it stopped using the standard NetIncomeLoss tag after 2010, and P&G's and Caterpillar's equity use a tag that includes minority interests. The reader now falls back, year by year, to net income available to common shareholders, then profit including minority interests, and to equity including minority interests. The 2% data check itself is unchanged. No screen results existed at the time (the run stopped before the universe step). | Found by the data check on the first run; fix verified on the cached filings (Caterpillar 2025 net income now read). |
| 2026-10-28 | **Data clean-up of the shortlist, after the first results (disclosed).** (1) **Partnerships out:** companies whose name ends in "L.P." or "LP" are removed (the rules allow common stocks only; FMP's screener did not exclude them; Plains All American, L.P. reached #26). (2) **Corporate separations:** any shortlisted company that completed a spin-off, split, or other 8-K Item 2.01 transaction (completed acquisition or disposition) after its latest fiscal year-end is flagged, because its statements no longer match its market value (e.g. Honeywell completed its aerospace spin-off in June 2026 while its latest statements are for 2025). Flags come from SEC 8-K filings plus a news check; each flag is decided in data/phase3/corporate_actions.csv (replace or keep, with the reason and a source link). Replaced companies give their place to the next-best eligible company, which gets the same check. Every change is shown next to the original list, which stays committed. | Found when reading the first results: the rules were right but two data problems slipped through. Decided by Landon before the clean-up was coded. |
| 2026-10-28 | **Robustness check of the shortlist (does not change it).** Three well-known alternative rankings, each a percentile rank among the 537 companies that passed the filters: (1) **Magic Formula** (Greenblatt): average of the ranks of earnings yield (operating income / enterprise value) and return on capital (operating income / (net working capital + net fixed assets); net working capital = current assets minus cash and short-term investments minus (current liabilities minus short-term debt); capital at or below zero ranks highest); (2) **Piotroski F-score** (0-9): latest year vs the year before: return on assets > 0, operating cash flow > 0, return on assets up, cash flow > net income, long-term debt / total assets down, current ratio up, diluted shares not up, gross margin up, asset turnover up (return on assets and turnover on beginning-of-year assets); (3) **Gross profitability** (Novy-Marx): gross profit / total assets. Each shortlisted company is labelled **robust** if it is in the top 30% (rank 70+) on at least 2 of the 3, **fragile** if on none, **mixed** otherwise. Fragile names are not removed; they get a harder look in the memo stage. The overlap between each alternative's own top 30 and the shortlist is reported as information. | Landon asked whether other rankings would agree. Choosing among rankings after seeing them would be rank-shopping, so the main score stays the decision rule and the alternatives only label how much each name depends on it. Written before the check was coded. |
| 2026-10-28 | **Decision standard for corporate-action flags** (written after seeing which companies were flagged, before the cleaned list was produced): replace a company if it completed a spin-off or split, or an acquisition or sale worth 10% or more of its market value, after its latest fiscal year-end; keep it if the deal completed before that year-end (its balance sheet already includes it) or is under 10%. Applied: Comcast, FedEx, Honeywell, Corteva (spin-offs), National Fuel Gas, Allison Transmission, NRG, John Wiley (acquisitions of 17-60% of market value) replaced; California Resources kept (Berry merger closed before year-end). Sources in data/phase3/corporate_actions.csv. | A consistent rule for the flags rather than case-by-case judgment; disclosed timing. |
| 2026-10-28 | **Corporate-action standard covers asset purchases (applies to future screens; tightens, does not loosen).** A purchase or sale of assets (licenses, plants, business lines) worth 10% or more of market value, completed after the latest fiscal year-end, counts the same as an acquisition under the decision standard above, whether or not the company filed it as an 8-K Item 2.01 completed acquisition. The 8-K check is supplemented by a news and filings check of each shortlisted company. Current list: AT&T's $23B EchoStar spectrum purchase (closed Jul 2026, about 16% of market value) was missed by the 8-K check; a recheck with the 10-Q figures (scripts/phase3/recheck_att.py, data/phase3/recheck_att_results.txt) shows net debt / EBITDA of 3.51x, over the 3.0x filter, so AT&T is out on the existing debt rule. | Found in the shortlist news review. Written after the case was seen, so it is disclosed as such; it can only remove names, never add them. |
