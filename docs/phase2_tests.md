# Phase 2 test log

Every test in Phase 2, grouped by the question it answered. Tests are numbered in the order they were designed; Tests 27-30 were designed before Test 31 but run after it, on the rebuilt data. Each test fixed its rules, metrics and pass/fail criteria before running, and recorded a prediction. Full write-ups, including predictions scored, are in the project's research notes; outputs are in `data/phase2_macro/`.

**Data versions.** Tests 1-26 use "v1" data (bond returns estimated from monthly-average yields, gold from monthly-average prices). Tests 27-32 use "v2" data (actual IEF returns from 2002, GLD from 2004, month-end yields before that). Test 32 rechecked the close calls on v2; no earlier decision flipped because of the data change.

## 1. Does diversification work?

| Test | Question | Result | Decided |
|---|---|---|---|
| 5 | Does a fixed stock/bond mix cut losses? | 60/40 cut the worst drawdown from -50% to about -30% (1970-2026), costing about 1.8 points a year, in both halves of the sample. | Diversification is the base layer. |
| 15 | Does leverage (risk parity) improve it? | Levered to 10% volatility, a stock/bond risk parity replica lost 27% in 2022, worse than stocks. | No leverage (confirms the mandate). |

## 2. When do bonds fail as a hedge?

| Test | Question | Result | Decided |
|---|---|---|---|
| 4, 8, 9 | Does the stock-bond correlation depend on inflation? | Yes: +0.33 above 3% core PCE vs -0.14 below; the sign flips near 3%, but the data cannot locate the break more precisely than about 2.5-3.5%. | Inflation level is the state to watch. |
| 6, 7 | Do bonds protect in the worst stock quarters? | At low inflation, +6.0% a quarter and positive 92% of the time; at high inflation, -1.3%, and cash beat bonds 8 times out of 10. | Bonds protect in growth shocks, not inflation shocks. |
| 12 | What predicts next year's correlation? | Inflation level, weakly (out-of-sample R-squared 0.18); last year's correlation predicts nothing. | Signals can only tilt, not switch. |
| 16 | Does it hold in other countries? | After 1950, in 14 of 16 countries; before 1950, no. | The finding belongs to the modern central-bank era. |

## 3. Can the shift be timed?

| Test | Question | Result | Decided |
|---|---|---|---|
| 1-3 | Do growth/inflation quadrant labels predict returns? | No: random label shuffles matched the real spread 30.5% (stocks) and 56.8% (bonds) of the time. | Quadrants are a stress-test lens, not a signal. |
| 10, 13, 14 | Does trimming bonds into cash at high inflation (Trigger 1) help? | About 2 points shallower worst drawdown in the US at no return cost; insensitive to the exact thresholds; random timing matched it 28% of the time. | Trigger 1 adopted (act 3.25%, restore 3.0%). |
| 17 | Does Trigger 1 work abroad? | 2.1 points shallower on average across 16 countries, 1950-2020; no random timing matched it. Two-step version added nothing. | Kept, one-step. |
| 28, 29 | Is Trigger 1 worth it in the final portfolio, after inflation? | Abroad, 0.4 points with a range including zero. It helped in inflation years (2022: -13.6% vs -16.8%), but the test measured the worst drawdown, which is 2008. | **Trigger 1 made watch-only.** |
| 18 | Which recession signal is most usable? | The 10-year minus 3-month yield curve: 6 of 7 recessions, 5-16 months of warning, one false alarm. | Trigger 2 = yield curve; Sahm rule watch-only. |
| 20, 21 | How should Trigger 2 act? | Acting only while inverted did no better than random timing; holding 12 months after un-inversion passed in the US (random timing matched 6%), on a second attempt. | Trigger 2 active: 10 points, cash under Trigger 1. |
| 25 | Does Trigger 2 work abroad? | No: 34 of 105 downturns caught, 57 of 76 inversions were false alarms, random timing matched 80%. | **Trigger 2 made watch-only.** |
| 11 | Where are we now? | Core PCE about 3.0%; 24-month stock-bond correlation -0.26. | Starting state recorded. |

## 4. What else hedges?

| Test | Question | Result | Decided |
|---|---|---|---|
| 19 | Do gold, commodities or TIPS hedge inflation shocks? | None passed all three pre-committed criteria. | No inflation-hedge asset. |
| 22, 23 | Is gold a useful diversifier? | Near-zero correlation with stocks and bonds; drawdown benefit equal to Treasuries; flat in 2022, but fell 16% in October 2008. | Gold in at 5% as a declared judgment exception. |
| 26 | Does gold's diversification hold abroad? | Yes: correlation -0.04 with local stocks; about as good as more local bonds. | Exception stands. |
| 27 | Should gold be held at today's price? | Real price above 99% of its 1975-2026 history; every start from the top fifth averaged -3.5% a year over 10 years. | **Gold removed**, with a re-entry rule. |
| 29 | Is cash a real inflation hedge? | Cash earned +1.4% a year after inflation while Trigger 1 was on; bonds +2.0%. | Cash is a parking place, not a hedge. |
| 31f | Do index puts or collars help? | Puts cut the 2008 crash but not 2022's slow decline; the collar did better in 2022 (2008-2026 data only). | Informs Phase 4 overlay design. |

## 5. How much in stocks, and any tilts?

| Test | Question | Result | Decided |
|---|---|---|---|
| 24 | How much can a concentrated stock sleeve hold? | With six random industries, 55% stocks was the most within the plain 60/40's drawdown. | 55/40/5. |
| 24 rerun, 32a | Does it hold without Trigger 2 and on better data? | Yes, by 0.4 and then 1.2 points. | Unchanged. |
| 32d | Final split with no gold and no triggers? | 55/45: -27.9% vs a -29.0% bar. | **55% stocks / 45% Treasuries.** |
| 30 | Should stocks tilt toward inflation winners? | Industries that led in 1970-97 inflation months lagged in later ones. | No sector tilts. |

## 6. Is the data good enough?

| Test | Question | Result | Decided |
|---|---|---|---|
| 31a | Are estimated bond returns accurate? | The old estimate used monthly-average yields (correlation 0.72 with IEF); on month-end yields 0.99, but it overstates drawdowns by about 4 points. | Use IEF's actual returns from 2002. |
| 31b | Are monthly-average gold prices accurate? | No: correlation 0.63 with GLD; October 2008 showed -2.8% instead of -16.1%. | Use GLD from 2004. |
| 31c | Does revised inflation data change Trigger 1? | No: first-published data switched it within 5 months of revised data. | Revised data acceptable. |
| 31d | Does month-end data hide crashes? | Yes: 2020 was -17.5% daily vs -7.8% month-end. | Report daily drawdowns for risk. |
| 31e | Do trading costs matter? | 0.15-0.38 points a year. | Costs noted; no change. |
| 32b, 32c | Do the close calls survive v2 data? | Yes. | No flips. |
