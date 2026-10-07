# Project Swim

Self-directed investment research project, built alongside CFA Level II study. A concentrated multi-asset model portfolio — full bottom-up underwriting, top-down asset allocation, and an options hedging overlay — tracked monthly with real discipline, not a one-off stock pitch.

**Named for the old idea of throwing a kid in the deep end to teach them to swim.** This project is deliberately structured to force real learning under real (if simulated) stakes, not just studying the concepts in the abstract.

## Status

🟡 **Phase 2 (top-down macro view)**: testing is complete and the macro thesis is final. The allocation step (equity / fixed income / alternatives split) is next. No positions selected yet. Checkpoint: assets selected and paper trading set up by 2026-10-22.

## Phase 2: Top-down macro view

**The question.** Before picking any position, decide how the portfolio splits across equities, fixed income and alternatives, and when, if ever, that split should change. The standard tool is the growth/inflation "regime" framework behind all-weather and risk parity portfolios. Phase 2 tested whether that framework holds up before relying on it.

**How the tests were run.** Each test fixed its metrics, thresholds and pass/fail criteria before running, and a written prediction was recorded beforehand. Rules were compared against random timing (shuffled labels or placebo on/off schedules), so a rule had to beat luck, not just the baseline. All data is free and public: FRED, the Ken French Data Library, the Jordà-Schularick-Taylor Macrohistory Database, World Bank commodity prices and yfinance.

### What we found

| Question | Result | Tests |
|---|---|---|
| Do growth/inflation quadrant labels predict next-quarter returns? | No. Random label shuffles matched the real spread between quadrants 30.5% of the time for stocks and 56.8% for bonds. | 1–3 |
| Does diversification work? | Yes. A fixed 60/40 mix cut the worst drawdown from about -50% to about -30% (1970–2026), at a cost of about 1.8 points of annual return, in both halves of the sample. | 5 |
| Do bonds always hedge stocks? | No. The stock-bond correlation was +0.33 when core PCE inflation was above 3% and -0.14 below it. In the worst stock quarters, bonds gained 6.0% a quarter at low inflation and lost 1.3% at high inflation, and cash beat bonds in 8 of 10 high-inflation quarters. | 4, 6–9 |
| Does that hold outside the US? | After 1950, yes: the correlation was higher at high inflation in 14 of 16 countries. Before 1950, no. Bonds abroad were hurt less than in the US. | 16 |
| Does leverage fix it, as risk parity claims? | No. A stock-bond risk parity replica levered to 10% volatility lost 27% in 2022, worse than stocks (-20%) and 60/40 (-18%). | 15 |
| Can a slow inflation rule help? | Modestly. Trimming half the bonds into cash when core inflation is high made the worst drawdown about 2 points shallower at essentially no return cost, in the US and on average across 16 countries. | 10, 13, 14, 17 |
| Which recession signal is most usable? | The 10-year minus 3-month yield curve: it caught 6 of 7 recessions since 1972 with 5 to 16 months of warning and one false alarm (2022). | 18 |
| Does acting on it help? | Only with a hold. Shifting out of stocks only while the curve was inverted did no better than random timing; holding the shift 12 months after the curve un-inverted made the worst drawdown about 2 points shallower than Trigger 1 alone at no return cost (random timing matched it 6% of the time). The hold was designed after seeing history, on a second attempt. | 20, 21 |
| Do gold, commodities or TIPS solve the inflation problem? | None passed all three pre-committed criteria. Gold diversified but did not protect in high-inflation selloffs; commodities did, but deepened drawdowns elsewhere; TIPS fell with stocks and bonds in 2022. | 19 |
| Is gold still worth holding as a diversifier? | As a judgment call, yes. A 10% gold sleeve cut the worst drawdown about as much as 10% more Treasuries (-24.2% vs -24.0%, 1975–2026) at a slightly lower return cost, with almost no correlation to stocks (-0.03) or bonds (0.05). It held flat in 2022 while bonds fell 15.5%, but fell 16% in October 2008. It did not beat Treasuries. | 22, 23 |

Two findings changed the plan. The regime framework is kept as a stress-test lens, not a trading signal. And the defensive sleeve cannot rely on nominal bonds alone, because the stock-bond hedge failed at inflation levels close to today's (core PCE 3.0% in August 2026).

### The macro thesis (final, 2026-10-06)

> Since the 1950s, the main threat to the defensive sleeve of a diversified portfolio without leverage is not failing to predict the next regime but a shift to inflation-driven markets, when stocks and bonds fall together. I cannot time regimes, and my tests showed the growth and inflation quadrant labels did not predict returns, so I will not trade them. What I can do is recognize the dangerous state from a slow signal (core inflation above about 3.25%) and avoid relying on one hedge: nominal bonds for growth shocks, cash and my options overlay for inflation shocks. Across 16 countries from 1950 to 2020, trimming bonds into cash when inflation was high made the worst drawdown about 2 points shallower on average at essentially no cost in return. This is modest insurance, not a forecast, and I will drop it if the stock-bond correlation stays at or below zero through 18 months of high inflation.

### Rules the portfolio follows

- **Trigger 1 (bonds and inflation).** When core PCE has been above 3.25% for three months, trim half of the bond position into cash. Restore when it has been below 3.0% for three months. Current state: not trimmed (core PCE 3.01% in August 2026).
- **Trigger 2 (growth shock).** When the 10-year Treasury yield is below the 3-month yield (prior month's data), and for 12 months after it last was, move 10 points from stocks to bonds, or to cash while Trigger 1 is on. The hold matters because selloffs came after the curve un-inverted in 2001, 2008 and 2020. The Sahm rule is watched but does not trigger anything. Current state: off (the hold from the 2022 inversion ended in December 2025).
- **Trigger 3 (when to drop the idea).** If core PCE stays above 3.25% for 18 months and the stock-bond correlation over that period is still at or below zero, restore the bonds and rerun the tests.
- **Gold (declared judgment exception).** Held at 5% as a diversifier, not an inflation hedge; it did not pass the Test 19 criteria. Dropped if its 36-month correlation with stocks rises above +0.3. Trigger 1 still sends trimmed bonds to cash.
- **Monthly review.** On the first of each month, record core PCE, the 12- and 24-month stock-bond correlation, the yield-curve spread and the state of each trigger, before looking at performance.

The thresholds are judgment calls, not fitted values. Results barely changed across nearby settings (Test 13), and the data cannot tell a break at 3% from one anywhere between about 2.5% and 3.5% (Test 9).

### What this does not show

- **Few independent episodes.** The inflation evidence rests mainly on the 1970s to early 1980s and 2021 to 2023, plus similar periods abroad.
- **Approximate data.** US bond returns are estimated from yields; the cross-country data is annual and uses headline CPI; gold and commodity prices are monthly averages, which understate volatility and drawdowns. Everything is in-sample, uses today's revised data and ignores transaction costs.
- **Small effects.** Both triggers are modest insurance worth about 2 points of worst drawdown, not an edge. In the US, random timing matched Trigger 1's drawdown gain 28% of the time and Trigger 2's (with its hold) 6%, the latter on a second attempt.
- **Not tested.** Verdad's market-based signals (high-yield spreads), real-time data vintages, and the options overlay (no free historical options data).

### Reproducing the results

Run each script from the repo root, in the `project-swim` conda environment. FRED access needs a free API key in a git-ignored `.env` file as `FRED_API_KEY=...`. Downloaded source files (JST, World Bank) are cached in `data/phase2_macro/`. The CSVs are written by the scripts; the `.txt` results are the printed output, saved with a redirect (example below the table).

| Script (`scripts/phase2_macro/`) | Tests | Output (`data/phase2_macro/`) |
|---|---|---|
| `regimes.py` | 1 (raw quadrant labels) | `regimes.csv` |
| `regimes2.py` | 1 (smoothed labels) | `regimes_smoothed.csv` |
| `quadrant_returns.py` | 2 (stocks by quadrant) | `quadrant_returns_same.csv`, `quadrant_returns_next.csv` |
| `bonds.py` | 3 (bonds by quadrant) | `bond_returns_same.csv`, `bond_returns_next.csv` |
| `robustness.py` | 4–15, 18 (US monthly tests, Triggers 1 and 2) | `robustness_results.txt` |
| `cross_country.py` | 16 | `cross_country_results.txt` |
| `cross_country_rule.py` | 17 | `cross_country_rule_results.txt` |
| `inflation_leg.py` | 19 | `inflation_leg_results.txt` |
| `trigger_interaction.py` | 20 (Triggers 1 and 2 together) | `trigger_interaction_results.txt` |
| `trigger2_hold.py` | 21 (Trigger 2 with a 12-month hold) | `trigger2_hold_results.txt` |
| `gold_tests.py` | 22 (gold vs. more Treasuries), 23 (crisis replay) | `gold_tests_results.txt` |
| `inflation.py` | none (quick check of current core PCE) | printed only |

```bash
conda activate project-swim
python scripts/phase2_macro/robustness.py > data/phase2_macro/robustness_results.txt
```

Inside `robustness.py`, the printed labels TEST 1 to 3 correspond to Tests 4 to 6 above; the other labels match.

Full write-ups: the Macro Thesis and the test log ("Regime Failures Since 2020", Tests 1 to 23) are kept as working docs and will be exported to `research/` with the allocation decision.

## Structure

- `research/` — position theses, macro/top-down notes, sector write-ups
- `models/` — valuation models (DCF, comps)
- `scripts/` — Python scripts (data pulls, backtests); Phase 2 tests in `scripts/phase2_macro/`
- `data/` — local data cache and test outputs (no credentials — see `.gitignore`); Phase 2 in `data/phase2_macro/`
- `dashboard/` — source for the live portfolio tracking dashboard

## Disclaimer

This is an educational, self-directed project. Nothing here is investment advice. The portfolio is paper-traded/simulated — no real client money is involved.

## License

MIT — see `LICENSE`.
