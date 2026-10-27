# Phase 2B decision test 2B-D: non-US stocks. Does holding stocks abroad reduce Japan-style disaster risk?
# Usage, from the repo root:  python scripts/phase2b/non_us.py
# Output: data/phase2b/non_us_results.txt
#
# Rules: docs/phase2b_research_plan.md, 2B-D row and amendment 2026-10-27 ("2B-D details fixed before coding").
#   - JST annual 1950-2020; every country with complete stock (eq_tr), CPI and exchange-rate (xrusd) data for
#     every year 1949-2020 (1949 is needed for the first year's currency change and inflation).
#   - Home only = the country's own stocks. With stocks abroad = 2/3 home stocks + 1/3 split equally across the
#     other countries, converted to home currency unhedged (JST xrusd), rebalanced yearly. Both after home CPI.
#   - Part 1: the longest time underwater is at least 1 year shorter with stocks abroad in more than half the
#     countries. Part 2: for a US investor, 2/3 US stocks + 1/3 developed markets outside the US (Ken French, USD,
#     monthly from 1990-07, rebalanced monthly) costs at most 0.5 pts/yr after US inflation vs US stocks alone.
#     Both parts must pass. If met: consider a non-US stock fund, up to a third of the stock part.
import io
import os
import sys
import zipfile
import pandas as pd

sys.path.insert(0, "scripts/phase2b")
from common2b import OUT, fred_m  # noqa: E402
from common import JST_PATH, KF, get_url  # noqa: E402
import mix_engine as E  # noqa: E402

RESULTS = f"{OUT}/non_us_results.txt"
lines = []


def log(s=""):
    print(s)
    lines.append(s)


def pct(x, d=1):
    return "n/a" if x is None or pd.isna(x) else f"{x * 100:+.{d}f}%"


def pts(x):
    return "n/a" if x is None or pd.isna(x) else f"{x * 100:+.2f} pts"


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


def kf(name):
    z = zipfile.ZipFile(io.BytesIO(get_url(KF + name + "_CSV.zip")))
    return E.parse_french_csv(z.read(z.namelist()[0]).decode("latin-1"))


# ======================= PART 1: 16 COUNTRIES =======================
j = pd.read_excel(JST_PATH)[["country", "year", "eq_tr", "cpi", "xrusd"]]
j["year"] = j.year.astype(int)
if j.eq_tr.abs().median() > 1:
    raise ValueError("JST eq_tr does not look like decimals")
j = j[(j.year >= 1949) & (j.year <= 2020)]
wide = {k: j.pivot(index="year", columns="country", values=k) for k in ["eq_tr", "cpi", "xrusd"]}
full = [c for c in wide["eq_tr"].columns
        if all(len(wide[k][c].dropna()) == 72 for k in wide)]
eq, fx = wide["eq_tr"][full], wide["xrusd"][full]
infl = wide["cpi"][full] / wide["cpi"][full].shift(1) - 1
res = E.home_vs_abroad(eq, fx, infl)              # rows 1949-2020; results 1950-2020

log("PHASE 2B DECISION TEST 2B-D: NON-US STOCKS (after inflation)")
log("=" * 100)
log(f"PART 1: JST, 1950-2020, {len(full)} countries with complete data ({', '.join(full)})")
log("  Home only vs 2/3 home + 1/3 the other countries (equal weights, home currency, unhedged), yearly")
log(f"  {'':14s}{'underwater home':>17s}{'with abroad':>13s}{'worst loss home':>17s}{'with abroad':>13s}{'return home':>13s}{'with abroad':>13s}")
wins = 0
for c, (h, m) in res.items():
    uh, um = E.longest_underwater(h), E.longest_underwater(m)
    ok = uh - um >= 1
    wins += ok
    log(f"  {c:14s}{uh:>14d} yr{um:>10d} yr{pct(E.max_dd(h)):>17s}{pct(E.max_dd(m)):>13s}"
        f"{pct(E.ann(h, 1)):>13s}{pct(E.ann(m, 1)):>13s}  {'shorter by 1+ yr' if ok else ''}")
part1 = wins > len(res) / 2
log(f"  Shorter by 1+ year in {wins} of {len(res)} countries -> {'PASS (more than half)' if part1 else 'fail'}")
# Sensitivity (report only): JST's 1949->1950 exchange-rate moves for Germany and Japan look like data artifacts
# (D-mark devalued to 4.20 in Sept 1949; yen pegged at 360 from 1949), so the same count is shown from 1951.
res51 = E.home_vs_abroad(eq.loc[1950:], fx.loc[1950:], infl.loc[1950:])
w51 = sum(E.longest_underwater(h) - E.longest_underwater(m) >= 1 for h, m in res51.values())
log(f"  Sensitivity (report only, the rule uses 1950-2020): starting in 1951 instead, shorter by 1+ year in {w51} of "
    f"{len(res51)}; Japan {E.longest_underwater(res51['Japan'][0]) if 'Japan' in res51 else 'n/a'} vs "
    f"{E.longest_underwater(res51['Japan'][1]) if 'Japan' in res51 else 'n/a'} years")
if "Japan" in res:
    h, m = res["Japan"]
    log(f"  Japan: longest underwater {E.longest_underwater(h)} years home only vs {E.longest_underwater(m)} with stocks abroad; "
        f"worst loss {pct(E.max_dd(h))} vs {pct(E.max_dd(m))}")

# ======================= PART 2: US INVESTOR SINCE 1990 =======================
ff = kf("F-F_Research_Data_Factors")
dx = kf("Developed_ex_US_3_Factors")
cpi, filled = E.fill_index(fred_m("CPIAUCSL"))
P = pd.DataFrame({"us": ff["Mkt-RF"] + ff["RF"], "ex": dx["Mkt-RF"] + dx["RF"], "i": E.chg(cpi)}).dropna()
P = E.contiguous(P["1990-07":], "US investor sample")
us_r = E.real(P.us, P.i)
mix_r = E.real(E.port(P, {"us": 2 / 3, "ex": 1 / 3}), P.i)
cost = E.ann(us_r) - E.ann(mix_r)
part2 = cost <= 0.005 + E.EPS
log(f"\nPART 2: US investor, {P.index[0]:%Y-%m} to {P.index[-1]:%Y-%m}, monthly, after US inflation "
    f"(unpublished CPI months filled: {[f'{t:%Y-%m}' for t in filled] or 'none'})")
log(f"  US stocks only: return {pct(E.ann(us_r))}/yr, worst loss {pct(E.max_dd(us_r))}, longest underwater "
    f"{E.longest_underwater(us_r)} months")
log(f"  2/3 US + 1/3 developed ex-US: return {pct(E.ann(mix_r))}/yr, worst loss {pct(E.max_dd(mix_r))}, longest underwater "
    f"{E.longest_underwater(mix_r)} months")
log(f"  Cost {pts(cost)}/yr (limit 0.50) -> {'PASS' if part2 else 'fail'}")
log("  Crash losses: " + "; ".join(f"{k} {pct(E.window_loss(us_r, k))} vs {pct(E.window_loss(mix_r, k))}"
                                   for k in ["2000-02", "2007-09", "2022"]))

log(f"\nRESULT: {'PASS: consider a non-US stock fund, up to a third of the stock part' if part1 and part2 else 'not supported: the stock part stays US'}")
log("\nNotes: JST exchange rates are annual figures (possibly year averages; to confirm in the JST documentation) and")
log("returns are yearly, so short currency swings are missed. JST's 1950 rates for Germany and Japan look like data")
log("artifacts (see the 1951 sensitivity line). Equal")
log("weights across countries differ from a world index. Ken French ex-US returns are in dollars and before fund fees.")
finish()
