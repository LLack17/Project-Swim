# Known-answer tests for case_study.py, using made-up data only (no downloads, nothing written to data/).
# Run from the repo root:  python scripts/phase2b/test_case_study.py
import io
import os
import sys
import tempfile
import contextlib
import numpy as np
import pandas as pd

sys.path.insert(0, "scripts/phase2b")
sys.path.insert(0, "scripts/phase2_macro")
import common   # noqa: E402
import common2b  # noqa: E402
from common2b import bond_ret, q_lag, tbill_bey  # noqa: E402

passed = 0


def check(cond, msg):
    global passed
    if not cond:
        raise AssertionError(msg)
    passed += 1


# ---------- unit tests ----------
y = pd.Series([5.0] * 6, index=pd.date_range("2000-01-31", periods=6, freq="ME"))
r = bond_ret(y, 10)
check(np.allclose(r, 0.05 / 12), "constant yield should earn yield/12")
y2 = pd.Series([7.5, 7.6, np.nan, np.nan, 6.0, 6.1], index=pd.date_range("2000-01-31", periods=6, freq="ME"))
r2 = bond_ret(y2, 20)
check(len(r2) == 2 and r2.abs().max() < 0.05, f"gaps must be dropped, not turned into huge returns: {r2.to_dict()}")
check(r2.iloc[0] < 0, "yield up means a loss")
q = pd.Series([1.0, 2.0], index=pd.to_datetime(["2007-01-31", "2007-04-30"]))   # Q1, Q2 as fred_m stores them
ql = q_lag(q)
check(pd.isna(ql.get(pd.Timestamp("2007-05-31"), np.nan)) and ql[pd.Timestamp("2007-06-30")] == 1.0
      and ql[pd.Timestamp("2007-09-30")] == 2.0, "Q1 data should first appear at June 30, Q2 at Sept 30")
check(q_lag(q, 2)[pd.Timestamp("2007-09-30")] == 1.0, "two-quarter lag: Q1 at Sept 30")
check(abs(tbill_bey(pd.Series([5.0])).iloc[0] - 18.25 / 355.45 * 100) < 1e-9, "bond-equivalent yield of a 5% discount: 365*0.05/(360-91*0.05)")

# ---------- end-to-end with an engineered crash ----------
idx = pd.date_range("1960-01-31", "2026-08-31", freq="ME")
INFL = 0.002                                   # 0.2% inflation every month, so real and nominal differ
fall, rise = 0.5 ** (1 / 10) - 1, 2.2 ** (1 / 20) - 1
k_rec = int(np.ceil(np.log(2) / np.log(1 + rise)))   # months after the bottom to regain the peak (real)


def engineered(peak):
    """REAL stock returns: flat, +1% in the peak month, -50% over 10 months, then up 2.2x over 20 months."""
    s = pd.Series(0.0, index=idx)
    p = idx.get_loc(pd.Timestamp(peak))
    s.iloc[p] = 0.01
    s.iloc[p + 1:p + 11] = fall
    s.iloc[p + 11:p + 31] = rise
    return s


class FakeFred:
    """Fake FRED data built so that each publication lag and conversion changes a printed number:
    - CPI, core PCE and unemployment jump IN the peak month (a one-month lag must hide the jump);
    - private credit steps from 150 to 200 one quarter before the peak's quarter (a two-quarter lag must show 150);
    - the T-bill discount rate is 4.9 in the inversion months: below the 10y's 5.0, but above it once converted
      to a bond-equivalent yield (5.03), so only the conversion detects the inversion;
    - the budget series can be cut short to test the staleness limit."""
    def __init__(self, peak, credit_pct=True, inv_months=(3, 4, 5, 6), deficit_end="2025-01-01", hpi_end="2026-04-01"):
        self.hpi_end = hpi_end
        self.peak, self.credit_pct = pd.Timestamp(peak), credit_pct
        self.inv = [self.peak - pd.offsets.MonthEnd(k) for k in inv_months]
        self.deficit_end = deficit_end

    def get_series(self, sid):
        if sid.startswith("DGS"):
            i = pd.date_range("1962-01-02", "2026-09-30", freq="B")
            return pd.Series(5.0 + np.sin(np.arange(len(i)) / 300.0), index=i)
        if sid == "FYFSGDA188S":
            return pd.Series(-2.0, index=pd.date_range("1930-01-01", self.deficit_end, freq="YS"))
        q = pd.date_range("1947-01-01", "2026-04-01", freq="QS")
        if sid == "QUSPAM770A":
            if not self.credit_pct:
                raise ValueError("Bad Request.  The series does not exist.")
            return pd.Series(np.where(q >= self.peak - pd.offsets.MonthEnd(5) - pd.offsets.MonthBegin(1), 200.0, 150.0), index=q)
        if sid == "USSTHPI":
            return pd.Series(200.0, index=pd.date_range("1975-01-01", self.hpi_end, freq="QS"))
        if sid in ("GDP", "CP", "QUSPAMUSDA", "BOGZ1FL663067003Q"):
            return pd.Series({"GDP": 1000.0, "CP": 100.0, "QUSPAMUSDA": 1500.0, "USSTHPI": 200.0,
                              "BOGZ1FL663067003Q": 5000.0}[sid], index=q)
        i = pd.date_range("1947-01-01", "2026-09-01", freq="MS")
        jump = (i + pd.offsets.MonthEnd(0)) >= self.peak                      # True from the peak month on
        if sid in ("CPIAUCSL", "PCEPILFE"):
            return pd.Series(100.0 * (1 + INFL) ** np.arange(len(i)) * np.where(jump, 1.05, 1.0), index=i)
        if sid == "UNRATE":
            return pd.Series(np.where(jump, 7.0, 5.0), index=i)
        if sid == "FEDFUNDS":
            return pd.Series(np.where((i.year >= 1950) & (i.year < 1960), 8.0, 4.0), index=i)
        if sid == "TB3MS":
            return pd.Series(np.where((i + pd.offsets.MonthEnd(0)).isin(self.inv), 4.9, 4.0), index=i)
        return pd.Series({"UNRATE": 5.0, "BAA": 7.0, "GS10": 5.0, "WALCL": 2e6}.get(sid, 3.0), index=i)

    def get_series_info(self, sid):
        return {"title": f"fake {sid}", "units_short": "x"}


def run(crisis, peak, good_checks=True, credit_pct=True, drop_rows=None, bond_jump=False, **fred_kw):
    rng = np.random.default_rng(0)
    real = engineered(peak)
    nominal = (1 + real) * (1 + INFL) - 1
    v2 = pd.DataFrame({"stocks": nominal, "cash": INFL, "bonds": INFL, "gold": np.nan, "cpi_m": INFL}, index=idx)
    if bond_jump:          # bonds +10% real the month after the peak: 55/45 is briefly ABOVE its start
        v2.loc[pd.Timestamp(peak) + pd.offsets.MonthEnd(1), "bonds"] = 1.10 * (1 + INFL) - 1
    if drop_rows:
        v2 = v2.drop(pd.to_datetime(drop_rows))
    fake = FakeFred(peak, credit_pct, **fred_kw)
    common.fred = lambda: fake
    common2b.fred = lambda: fake
    common2b.load_v2 = lambda: v2
    common2b.wb_gold = lambda: pd.Series(100.0, index=idx)
    comm = pd.DataFrame({"Commodities Market": rng.normal(0, 0.03, len(idx))}, index=idx)
    common2b.aqr_century = lambda: comm
    common2b.nareit = lambda: pd.Series(INFL, index=idx[idx >= "1972-01-31"])
    common2b.shiller_cape = lambda: pd.Series(np.linspace(10, 30, len(idx)), index=idx)
    ind = pd.DataFrame(np.tile(nominal.values[:, None] * 100, (1, 49)), index=idx)
    ind.iloc[idx.get_loc(pd.Timestamp(peak)) + 2, 0] = -99.99      # one industry missing a month mid-crash
    common2b.french = lambda n, daily=False: ind

    def fake_yf(t, s, interval="1mo"):
        if not good_checks:
            ei = pd.date_range("1985-01-31", "2026-09-30", freq="ME")
            return pd.DataFrame({k: np.cumprod(1 + rng.normal(0, 0.02, len(ei))) for k in t}, index=ei)
        # PLUMBING test only: "funds" built from the script's own estimates, so the checks must pass.
        # It proves alignment and pass/fail logic, not that the yield method matches real funds.
        dgs = common2b.fred_m
        src = {"SHY": bond_ret(dgs("DGS2"), 2), "TLT": bond_ret(dgs("DGS20"), 20),
               "^SPGSCI": common2b.aqr_century()["Commodities Market"] + INFL}
        return pd.DataFrame({k: (1 + src[k].fillna(0)).cumprod() for k in t})
    common.yf_close = fake_yf
    tmp = tempfile.mkdtemp()
    common2b.OUT = tmp
    pd.DataFrame({"old": [1]}).to_csv(f"{tmp}/case_{crisis}_wealth.csv")     # an older run's file
    sys.argv = ["case_study.py", crisis]
    buf = io.StringIO()
    code = 0
    with contextlib.redirect_stdout(buf):
        try:
            exec(compile(open("scripts/phase2b/case_study.py").read(), "case_study.py", "exec"), {"__name__": "__main__"})
        except SystemExit as e:
            code = e.code if e.code is not None else 0
    return buf.getvalue(), tmp, code


out, tmp, code = run("2022", "2021-12-31")
check(code == 0 and "STOP" not in out and "CAUTION" not in out, "data checks pass on consistent data")
check("peak 2021-12, bottom 2022-10 (10 months)" in out, "peak/bottom found")
nom_depth = 0.5 * (1 + INFL) ** 10 - 1
infl_fall = (1 + INFL) ** 10 - 1
check(f"Depth: stocks -50.0% after inflation, {nom_depth * 100:+.1f}% before inflation; "
      f"inflation over the fall {infl_fall * 100:+.1f}%" in out, "depth before/after inflation")
rec = pd.Timestamp("2022-10-31") + pd.offsets.MonthEnd(k_rec)
check(f"Stocks back to the old peak (after inflation): {rec:%Y-%m}, {10 + k_rec} months after the peak" in out,
      f"real recovery time ({10 + k_rec} months)")
real_bond = (1 + INFL) / (1 + INFL) - 1                   # bonds earn exactly inflation: 0% real
p_bottom = (1 + 0.55 * fall + 0.45 * real_bond) ** 10 - 1
check(f"rebalanced monthly : at stock bottom {p_bottom * 100:+.1f}%" in out, "55/45 at bottom (monthly rebalancing)")
check(f"rebalanced never   : at stock bottom {(0.55 * 0.5 + 0.45 - 1) * 100:+.1f}%" in out, "55/45 at bottom (never)")
hist = fake.get_series("FEDFUNDS") if (fake := FakeFred("2021-12-31")) else None
hist = hist[:"2021-12-01"]
check(f"{(hist <= 4.0).mean() * 100:12.0f}%" in [ln[-13:] for ln in out.splitlines() if ln.startswith("Fed funds rate")],
      "fed funds percentile vs a history with higher 1950s rates")
check("(48 with complete data)" in out, "an industry with a missing month is left out, not given a partial return")
check("Yield curve inverted in the 24 months before the peak: yes" in out,
      "inversion detected (needs the T-bill conversion: 4.9 discount = 5.03 bond-equivalent > 5.0)")


def signal_row(name):
    ln = [x for x in out.splitlines() if x.startswith(name)][0]
    return ln[44:54].strip(), ln[54:66].strip()


check(signal_row("CPI inflation, 12m (%)")[0] == f"{((1 + INFL) ** 12 - 1) * 100:.2f}",
      "CPI lagged a month: the jump in the peak month must not show")
check(signal_row("Core PCE inflation, 12m (%)")[0] == f"{((1 + INFL) ** 12 - 1) * 100:.2f}", "core PCE lagged a month")
check(signal_row("Unemployment (%)")[0] == "5.00", "unemployment lagged a month")
check(signal_row("Private credit / GDP (%)")[0] == "150.00", "BIS credit lagged two quarters")
score = {ln[:30].strip(): ln[30:].strip() for ln in out.splitlines() if ln.startswith("  ") and ln.strip().endswith("%")
         and len(ln) < 45}
check(score.get("Treasuries 7-10y (ours)") == "+0.0%" and score.get("US stocks") == "-50.0%"
      and score.get("Cash (T-bills)") == "+0.0%", f"scorecard: {score}")
check("Real house prices, 12m (%)" in out and [ln for ln in out.splitlines() if ln.startswith("Real house")][0].split()[5]
      == f"{((1 / (1 + INFL) ** 12) - 1) * 100:.2f}",
      "real house prices deflated by CPI lagged like house prices (the peak-month CPI jump must not show)")
check("Federal budget balance (% of GDP, negative = deficit): -2.0" in out, "budget balance read")
check("Food -50%" in out, "industries are measured after inflation (nominal would show a smaller loss)")


def hand_replay(real_s, mode):
    """Independent 55/45 replay written separately from the script, month by month. Bonds earn 0% real here."""
    vs, vb, path = 0.55, 0.45, []
    for t, r in real_s.items():
        if mode == "yearly" and t.month == 1:
            vs, vb = 0.55 * (vs + vb), 0.45 * (vs + vb)
        vs, vb = vs * (1 + r), vb
        if mode == "monthly":
            vs, vb = 0.55 * (vs + vb), 0.45 * (vs + vb)
        path.append(vs + vb)
    return pd.Series(path, index=real_s.index)


real_s = engineered("2021-12-31")["2022-01-31":"2026-08-31"]
for mode in ["monthly", "yearly", "never"]:
    w_ = pd.concat([pd.Series([1.0], index=[pd.Timestamp("2021-12-31")]), hand_replay(real_s, mode)])
    tr = w_.idxmin()
    back = w_[tr:][w_[tr:] >= 1.0]
    back = f"{back.index[0]:%Y-%m}" if len(back) else "not by 2026-08"
    want = (f"rebalanced {mode:8s}: at stock bottom {(w_['2022-10-31'] - 1) * 100:+.1f}%, worst {(w_.min() - 1) * 100:+.1f}% "
            f"({tr:%Y-%m}), back to start {back}")
    check(want in out, f"replay line ({mode}) matches an independent calculation: {want}")
check(len({ln.split(":")[1] for ln in out.splitlines() if ln.startswith("  rebalanced")}) == 3,
      "monthly, yearly and never give three different results")
r3 = real_s["2022-11-30":"2025-10-31"]
check(len(r3) == 36, "36 months")
want3 = f"3y: stocks {((1 + r3).prod() ** (1 / 3) - 1) * 100:+.1f}%, 55/45 {((1 + 0.55 * r3).prod() ** (1 / 3) - 1) * 100:+.1f}%"
check(want3 in out, f"returns after the bottom match an independent calculation: {want3}")

w = pd.read_csv(f"{tmp}/case_2022_wealth.csv", index_col=0, parse_dates=True)
check(abs(w.loc["2021-12-31", "stocks_real"] - 1) < 1e-9 and abs(w.loc["2021-12-31", "p5545_real_monthly_rebal"] - 1) < 1e-9,
      "wealth CSV: both series start at 1 at the peak")

out, _, _ = run("2007-09", "2008-04-30")                  # bottom lands on 2009-02-28 (February)
check("bottom 2009-02" in out, "February bottom")
check(f"3y: stocks {((1 + rise) ** 20 ** 1 * 1.0) ** (1 / 3) * 100 - 100:+.1f}%" in out,
      "3-year return after a February bottom uses 36 months")

out, tmp, code = run("2022", "2021-12-31", good_checks=False)
check(code == 1 and "STOP: data checks failed" in out and "DURING" not in out, "failed checks stop the script")
check(not os.path.exists(f"{tmp}/case_2022_wealth.csv"), "a failed check deletes the older results file")

out, _, code = run("2022", "2021-12-31", inv_months=(24,))
check("Yield curve inverted in the 24 months before the peak: no" in out,
      "an inversion exactly 24 months before the peak is outside the 24-month window")
out, _, code = run("2022", "2021-12-31", inv_months=(23,))
check("Yield curve inverted in the 24 months before the peak: yes" in out, "an inversion 23 months before is inside")
out, _, code = run("2022", "2021-12-31", bond_jump=True)
line = [ln for ln in out.splitlines() if ln.startswith("  rebalanced monthly")][0]
check("back to start 2022-01" not in line and "back to start 202" in line,
      f"recovery is searched after the low, not from the peak (a brief rise above the start doesn't count): {line}")

out, _, code = run("2022", "2021-12-31", hpi_end="2020-04-01")
check([ln for ln in out.splitlines() if ln.startswith("Real house")][0].split()[5] == "n/a",
      "a signal whose latest value is over a year old shows n/a")
out, _, code = run("2022", "2021-12-31", deficit_end="2022-01-01")
check("-2.0 in the bottom year, nan a year later" in out,
      "budget data ending Jan 2022: the bottom year (2022) is covered, a year later (2023) is n/a")

out, _, code = run("2022", "2021-12-31", credit_pct=False)
check(code == 0 and "QUSPAMUSDA / GDP (fallback)" in out and "Private credit / GDP latest value 150" in out,
      "credit fallback gives % of GDP")

out, _, code = run("2022", "2021-12-31", drop_rows=["2025-10-31", "2025-11-30"])
check(code != 0 and "missing months" in str(code), "missing months in v2 stop the script")

print(f"All {passed} checks passed.")
