# Phase 2B decision test 2B-G: stock style. Which kinds of US stocks held up in crashes?
# Usage, from the repo root:  python scripts/phase2b/style_tests.py
# Output: data/phase2b/style_tests_results.txt
#
# Rules: docs/phase2b_research_plan.md, 2B-G row and amendment "2B-G rules fixed before coding" (2026-10-27).
#   - Styles = top fifth of US stocks by each trait, value-weighted (Ken French, first block of each file):
#     value = "Hi 20" of the BE-ME file, growth = "Lo 20" of the BE-ME file, quality = "Hi 20" of the OP file,
#     low-volatility = "Lo 20" of the VAR file. Columns are picked by NAME; the script stops if a name is missing.
#   - Market = Ken French US market (Mkt-RF + RF). All returns after inflation (CPI, FRED CPIAUCSL; months that
#     were never published are filled log-linearly and listed).
#   - Sample: 1963-07 to the latest month common to all files; every month must be present.
#   - Pass: smaller after-inflation loss than the market (worst fall inside the case-study window) in at least
#     3 of the 4 crashes (1973-74, 2000-02, 2007-09, 2022), AND full-period after-inflation annual return at
#     most 1 point a year below the market's. Every passing style becomes a Phase 3 screening criterion.
#   - International, report only: Ken French developed ex-US value-minus-growth factor (HML), 1990 on,
#     compounded over the crash windows that fall inside its data.
import io
import os
import sys
import zipfile
import pandas as pd

sys.path.insert(0, "scripts/phase2b")
from common2b import OUT, fred_m, load_v2  # noqa: E402
from common import KF, get_url  # noqa: E402
import mix_engine as E  # noqa: E402

RESULTS = f"{OUT}/style_tests_results.txt"
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


def col(d, name, file):
    if name not in d.columns:
        raise ValueError(f"column '{name}' not found in {file}; columns are {list(d.columns)}")
    return d[name]


# ======================= DATA =======================
ff = kf("F-F_Research_Data_Factors")
bm = kf("Portfolios_Formed_on_BE-ME")
op = kf("Portfolios_Formed_on_OP")
var = kf("Portfolios_Formed_on_VAR")
intl = kf("Developed_ex_US_3_Factors")
cpi, cpi_filled = E.fill_index(fred_m("CPIAUCSL"))
infl = E.chg(cpi)

nominal = pd.DataFrame({
    "Market": col(ff, "Mkt-RF", "F-F factors") + col(ff, "RF", "F-F factors"),
    "Value (cheapest fifth)": col(bm, "Hi 20", "BE-ME"),
    "Growth (most expensive fifth)": col(bm, "Lo 20", "BE-ME"),
    "Quality (most profitable fifth)": col(op, "Hi 20", "OP"),
    "Low volatility (calmest fifth)": col(var, "Lo 20", "VAR"),
    "_infl": infl}, )
start = max(s.first_valid_index() for _, s in nominal.items())
end = min(s.last_valid_index() for _, s in nominal.items())
if start != pd.Timestamp("1963-07-31"):
    raise ValueError(f"sample must start 1963-07 (rule); data start {start:%Y-%m}")
end_by = [k for k, s_ in nominal.items() if s_.last_valid_index() == end]
N = nominal[start:end]
if N.isna().any().any():
    bad = N.columns[N.isna().any()].tolist()
    raise ValueError(f"missing months inside the sample in: {bad}")
E.contiguous(N, "style sample")
R = pd.DataFrame({k: E.real(N[k], N["_infl"]) for k in N.columns if k != "_infl"})

# ======================= DATA CHECKS =======================
log("PHASE 2B DECISION TEST 2B-G: STOCK STYLE (US, after inflation)")
log("=" * 100)
log("DATA CHECKS")
log(f"  Sample {R.index[0]:%Y-%m} to {R.index[-1]:%Y-%m} ({len(R)} months, no gaps); end set by: {', '.join(end_by)}")
log(f"  Unpublished CPI months filled: {[f'{t:%Y-%m}' for t in cpi_filled] or 'none'}")
v2 = load_v2()
both = pd.concat([N["Market"], v2.stocks], axis=1, sort=True).dropna()
d_mkt = (both.iloc[:, 0] - both.iloc[:, 1]).abs().max()
both = pd.concat([N["_infl"], v2.cpi_m], axis=1, sort=True).dropna()
d_cpi = (both.iloc[:, 0] - both.iloc[:, 1]).abs().max()
ok_m, ok_c = d_mkt <= 0.0005, d_cpi <= 0.001
log(f"  Market vs our v2 US stocks (1970 on): largest monthly difference {d_mkt * 100:.3f} pts (limit 0.05)  {'OK' if ok_m else 'FAIL'}")
log(f"  CPI vs our v2 inflation (1970 on): largest monthly difference {d_cpi * 100:.3f} pts (limit 0.1)  {'OK' if ok_c else 'FAIL'}")
if not (ok_m and ok_c):
    raise ValueError("market or CPI series does not match our v2 data: wrong column, units, or v2 needs rebuilding")

# ======================= RESULTS =======================
mkt = R["Market"]
log("\nCRASH LOSSES AFTER INFLATION (worst fall inside each case-study window)")
log(f"  {'':34s}" + "".join(f"{k:>10s}" for k in E.WINDOWS) + f"{'return/yr':>11s}{'worst fall':>12s}")
for name in R.columns:
    r = R[name]
    log(f"  {name:34s}" + "".join(f"{pct(E.window_loss(r, k)):>10s}" for k in E.WINDOWS)
        + f"{pct(E.ann(r)):>11s}{pct(E.max_dd(r)):>12s}")

log("\nVERDICTS (pass = smaller loss than the market in 3+ of 4 crashes AND at most 1 pt/yr behind the market)")
passed = []
for name in [c for c in R.columns if c != "Market"]:
    res = E.style_rule(R[name], mkt)
    won = [k for k, (a, b) in res["loss"].items() if a > b]
    if res["pass"]:
        passed.append(name)
    log(f"  {name:34s} beat the market in {res['wins']} of 4 ({', '.join(won) or 'none'}); "
        f"return vs market {pts(-res['lag'])}/yr -> {'PASS: screening criterion' if res['pass'] else 'not supported'}")
log(f"\n  RESULT: {'styles for the Phase 3 screen: ' + '; '.join(passed) if passed else 'no style passes; the screen uses no style tilt'}")

log("\nINTERNATIONAL (report only, not comparable to the US test): developed markets ex-US HML factor (a long-short")
log("value-minus-growth factor, 30/70 split), nominal, compounded over the whole window")
h = intl["HML"].dropna()
for k, (a, b) in E.WINDOWS.items():
    if h.index[0] <= pd.Timestamp(a) + pd.offsets.MonthEnd(0) and h.index[-1] >= pd.Timestamp(b) + pd.offsets.MonthEnd(0):
        x = E.contiguous(h[a:b], f"international HML {k}")
        if len(x) != (pd.Period(b, "M") - pd.Period(a, "M")).n + 1:
            raise ValueError(f"international HML {k}: incomplete window")
        log(f"  {k:8s} {pct((1 + x).prod() - 1)}  ({'value factor positive' if (1 + x).prod() > 1 else 'value factor negative'})")
    else:
        log(f"  {k:8s} outside the data ({h.index[0]:%Y-%m} on)")

log("\nNotes: \"fifth\" = Ken French quintile using NYSE breakpoints (not a fifth of all stocks by count). Portfolios")
log("are hypothetical, value-weighted, before trading costs and fund fees; a real fund")
log("tracking a style holds a broader slice. Four crashes is a small sample: a style can win 3 of 4 by chance.")
log("CPI before 1983 counted mortgage rates and overstates 1970s inflation somewhat (it affects the styles and the market alike).")
finish()
