# Phase 2B decision test 2B-B: warning signs. Do the "before" signals predict crashes out of sample?
# Usage, from the repo root:  python scripts/phase2b/warning_signs.py
# Output: data/phase2b/warning_signs_results.txt
#
# Rules: docs/phase2b_research_plan.md, 2B-B row and amendments 2026-10-16 ("2B-B signals fixed") and
# 2026-10-27 ("2B-B details fixed before coding", which corrects the yield-curve direction).
#   - Country-years from JST annual data (every country with stock data). Signals at the end of year t:
#       credit   = change over 5 years in private loans as % of GDP (tloans / gdp), on in the top fifth
#       dividend yield (eq_dp), on in the BOTTOM fifth (expensive stocks)
#       inflation = CPI change over the year, on in the top fifth
#       yield curve = ltrate - stir, on in the BOTTOM fifth (flat or inverted)
#     US only, year-end values: margin loans / GDP (FRED BOGZ1FL663067003Q / GDP, Q4 values), Baa minus 10-year
#     Treasury yield (FRED BAA - GS10, December), Shiller CAPE (December); each on in the top fifth.
#   - "Top/bottom fifth of its own history" = above the 80th / below the 20th percentile of the same country's
#     values in EARLIER years (from its first year of data, year t itself left out), needing 20 earlier values.
#   - Baa spread = Baa corporate yield minus the 10-year Treasury yield (as in the case studies).
#   - Luck check runs on the full 1986-2017 grid per country, missing years kept in place (blocks 1986-90, ...).
#   - Crash after year t = real stock total-return index (eq_tr after local CPI) 30%+ below its year-t level at
#     some year-end in t+1..t+3. Annual data understates falls.
#   - Judged on 1986-2017 pooled across countries (1950-1985 also reported). Pass = crash rate when on >= 2x the
#     rate when off, at least 5 on-years followed by a crash, and the luck check (5-year blocks of each
#     country's on/off sequence shuffled 1,000 times, seed 0) matching the real ratio less than 10% of the time.
#   - A passing signal goes on the monthly watch list (watch-only; no trading). Values are today's revised data.
import os
import sys
import numpy as np
import pandas as pd

sys.path.insert(0, "scripts/phase2b")
from common2b import OUT, fred_m, shiller_cape  # noqa: E402
from common import JST_PATH  # noqa: E402
import mix_engine as E  # noqa: E402

RESULTS = f"{OUT}/warning_signs_results.txt"
CHECK, BUILD = (1986, 2017), (1950, 1985)
lines = []


def log(s=""):
    print(s)
    lines.append(s)


def finish():
    os.makedirs(OUT, exist_ok=True)
    with open(RESULTS, "w") as f:
        f.write("\n".join(lines) + "\n")
    print(f"\nSaved {RESULTS}")


def _on_error(exc_type, exc, tb):
    if exc_type is not SystemExit:
        log(f"\nERROR, script stopped: {exc_type.__name__}: {exc}")
        finish()
    sys.__excepthook__(exc_type, exc, tb)


sys.excepthook = _on_error


def rate(x):
    return "n/a" if x is None or pd.isna(x) else f"{x * 100:.0f}%"


# ======================= DATA =======================
j = pd.read_excel(JST_PATH)
need = ["country", "year", "eq_tr", "eq_dp", "tloans", "gdp", "cpi", "ltrate", "stir"]
miss = [c for c in need if c not in j.columns]
if miss:
    raise ValueError(f"JST columns missing: {miss}")
j = j[need].sort_values(["country", "year"]).copy()
j["year"] = j.year.astype(int)
if j.eq_tr.abs().median() > 1 or j.eq_dp.abs().median() > 1:
    raise ValueError("JST eq_tr / eq_dp do not look like decimals")
countries = sorted(c for c, x in j.groupby("country") if x.eq_tr.notna().any())

rows = []
for c in countries:
    x = j[j.country == c].set_index("year")
    x = x.reindex(range(x.index.min(), x.index.max() + 1))           # explicit missing years
    infl = x.cpi / x.cpi.shift(1) - 1
    real = (1 + x.eq_tr) / (1 + infl) - 1
    credit = (x.tloans / x.gdp * 100) - (x.tloans / x.gdp * 100).shift(5)
    sig = pd.DataFrame({
        "Credit growth (5y)": E.expanding_flag(credit, "top"),
        "Dividend yield (low)": E.expanding_flag(x.eq_dp, "bottom"),
        "Inflation (high)": E.expanding_flag(infl * 100, "top"),
        "Yield curve (flat/inverted)": E.expanding_flag(x.ltrate - x.stir, "bottom")})
    sig["crash"] = E.crash_ahead(real)
    sig["country"] = c
    rows.append(sig.reset_index().rename(columns={"index": "year"}))
panel = pd.concat(rows, ignore_index=True)

# US-only signals (year-end values)
us = j[j.country == "USA"].set_index("year")
us = us.reindex(range(us.index.min(), us.index.max() + 1))
us_crash = E.crash_ahead((1 + us.eq_tr) / (1 + us.cpi / us.cpi.shift(1) - 1) - 1)


def year_end(s, month=12):
    s = s.dropna()
    s = s[s.index.month == month]
    return pd.Series(s.values, index=s.index.year)


margin = year_end(fred_m("BOGZ1FL663067003Q") / fred_m("GDP"), month=10)   # quarterly, dated at quarter start: Q4 = Oct
# (margin loans in millions, GDP in billions: the ratio is scaled by 1,000, which does not change percentile flags)
baa = year_end(fred_m("BAA") - fred_m("GS10"))
cape = year_end(shiller_cape())
US = {"US margin loans / GDP": margin, "US Baa spread (Baa minus 10-year Treasury)": baa, "US CAPE": cape}

# ======================= RESULTS =======================
log("PHASE 2B DECISION TEST 2B-B: WARNING SIGNS (JST annual data, after inflation)")
log("=" * 100)
log(f"Countries with stock data: {len(countries)} ({', '.join(countries)})")
log(f"Judged on {CHECK[0]}-{CHECK[1]} pooled (1950-1985 shown for reference). Pass = crash rate when on >= 2x when off,")
log("at least 5 on-years followed by a crash, luck check below 10%.")
log("A 'crash' = real stocks 30%+ below the year-end level within the next 3 years.")


def judge(name, df):
    """df: columns country, year, on, crash."""
    out = {}
    for lab, (a, z) in [("1950-1985", BUILD), ("1986-2017", CHECK)]:
        w = df[(df.year >= a) & (df.year <= z)]
        grid = pd.MultiIndex.from_product([sorted(w.country.unique()), range(a, z + 1)], names=["country", "year"])
        g = w.set_index(["country", "year"]).reindex(grid).reset_index()          # full grid, gaps kept in place
        o = E.odds(g.on, g.crash)
        p = E.block_shuffle_p(g[["country", "on", "crash"]]) if lab == "1986-2017" and o["n_on"] and o["n_off"] else np.nan
        out[lab] = (o, p, int(g[["on", "crash"]].notna().all(axis=1).sum()))
    o, p, n = out["1986-2017"]
    ok = E.signal_rule(o, p) if not pd.isna(p) else False
    ob = out["1950-1985"][0]
    log(f"\n  {name}")
    log(f"    1950-1985: crash after {rate(ob['rate_on'])} of {ob['n_on']} on-years vs {rate(ob['rate_off'])} of {ob['n_off']} off-years "
        f"(ratio {ob['ratio']:.2f})" if not pd.isna(ob["ratio"]) else "    1950-1985: not enough data")
    log(f"    1986-2017: crash after {rate(o['rate_on'])} of {o['n_on']} on-years vs {rate(o['rate_off'])} of {o['n_off']} off-years; "
        f"ratio {o['ratio']:.2f} (needs 2.00), hits {o['hits']} (needs 5), luck check {rate(p)} (needs < 10%) "
        f"-> {'PASS: add to watch list' if ok else 'not supported'}")
    return ok


passed = []
log("\nCROSS-COUNTRY SIGNALS")
for name in ["Credit growth (5y)", "Dividend yield (low)", "Inflation (high)", "Yield curve (flat/inverted)"]:
    df = panel[["country", "year", name, "crash"]].rename(columns={name: "on"})
    if judge(name, df):
        passed.append(name)

log("\nUS-ONLY SIGNALS (few US crashes, so reaching 5 hits is unlikely; that is a limit of the data)")
for name, s in US.items():
    on = E.expanding_flag(s, "top")
    df = pd.DataFrame({"country": "USA", "year": on.index, "on": on.values,
                       "crash": us_crash.reindex(on.index).values})
    if judge(name, df):
        passed.append(name)

log(f"\nRESULT: {'add to the monthly watch list: ' + '; '.join(passed) if passed else 'no signal passes; the watch list is unchanged'}")
log("\nNotes: values are today's revised figures, not what was known at the time. Crashes cluster in time (1987, 2000-02,")
log("2007-09 hit many countries at once), which is why the luck check shuffles blocks of years. Annual data misses")
log("falls that happen and recover within a year. 'History' for the fifths starts at each country's first JST year and")
log("uses only years BEFORE year t. JST CPI is an annual average, so inflation is average-to-average and real returns mix")
log("year-end prices with average-price inflation (standard JST practice). The luck check keeps missing years in place,")
log("so blocks run 1986-90, 1991-95, ... for every country.")
finish()
