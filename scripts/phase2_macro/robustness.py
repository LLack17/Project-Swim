import io
import os
import zipfile
import urllib.request
import numpy as np
import pandas as pd
from dotenv import load_dotenv
from fredapi import Fred

BASE = "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/"

def french(name):
    req = urllib.request.Request(BASE + name + "_CSV.zip", headers={"User-Agent": "Mozilla/5.0"})
    z = zipfile.ZipFile(io.BytesIO(urllib.request.urlopen(req).read()))
    lines = z.read(z.namelist()[0]).decode("latin-1").splitlines()
    rows, started = [], False
    for line in lines:
        parts = [p.strip() for p in line.split(",")]
        if len(parts[0]) == 6 and parts[0].isdigit():
            started = True
            rows.append(parts)
        elif started:
            break
    d = pd.DataFrame(rows)
    d.index = pd.to_datetime(d[0], format="%Y%m") + pd.offsets.MonthEnd(0)
    return d.drop(columns=0).astype(float)

def month_end(s):
    s = s.copy()
    s.index = s.index + pd.offsets.MonthEnd(0)
    return s

load_dotenv()
fred = Fred(api_key=os.getenv("FRED_API_KEY"))

fac = french("F-F_Research_Data_Factors")
stocks = (fac[1] + fac[4]) / 100

y = month_end(fred.get_series("GS10")) / 100
y_prev = y.shift(1)
dur = (1 - (1 + y_prev / 2) ** -20) / y_prev
bonds = y_prev / 12 - dur * (y - y_prev)

infl = month_end(fred.get_series("PCEPILFE")).pct_change(12) * 100

df = pd.DataFrame({"stocks": stocks, "bonds": bonds, "infl": infl}).dropna()
df = df["1970":]
print(f"Data: {df.index[0].date()} to {df.index[-1].date()}, {len(df)} months\n")

rng = np.random.default_rng(0)

def block_idx(n, block=12):
    nb = int(np.ceil(n / block))
    starts = rng.integers(0, n, nb)
    return ((starts[:, None] + np.arange(block)[None, :]).ravel() % n)[:n]

# ---------- TEST 1: stock-bond correlation, high vs low inflation ----------
def corr_by_group(d):
    hi = d[d.infl > 3]
    lo = d[d.infl <= 3]
    return hi.stocks.corr(hi.bonds), lo.stocks.corr(lo.bonds)

hi_c, lo_c = corr_by_group(df)
boots = np.array([corr_by_group(df.iloc[block_idx(len(df))]) for _ in range(2000)])
diff = boots[:, 0] - boots[:, 1]
print("TEST 1: stock-bond correlation (monthly), by core PCE inflation")
print(f"  Inflation > 3%:  {hi_c:.2f}  ({(df.infl > 3).sum()} months)")
print(f"  Inflation <= 3%: {lo_c:.2f}  ({(df.infl <= 3).sum()} months)")
lo_ci, hi_ci = np.nanpercentile(diff, [2.5, 97.5])
print(f"  Difference (high minus low): {hi_c - lo_c:.2f}, 95% CI [{lo_ci:.2f}, {hi_ci:.2f}]")

# ---------- TEST 2: fixed mixes vs stocks alone ----------
vol_s = df.stocks.rolling(36).std().shift(1)
vol_b = df.bonds.rolling(36).std().shift(1)
w_s = (1 / vol_s) / (1 / vol_s + 1 / vol_b)
P = pd.DataFrame({
    "Stocks": df.stocks,
    "60/40": 0.6 * df.stocks + 0.4 * df.bonds,
    "InvVol": w_s * df.stocks + (1 - w_s) * df.bonds,
}).dropna()

def max_dd(r):
    w = np.cumprod(1 + r)
    return (w / np.maximum.accumulate(w) - 1).min()

def worst12(r):
    w = pd.Series(1 + r).rolling(12).apply(np.prod, raw=True) - 1
    return w.min()

def summarize(d):
    return pd.DataFrame({
        "ann_return_%": ((1 + d).prod() ** (12 / len(d)) - 1) * 100,
        "ann_vol_%": d.std() * np.sqrt(12) * 100,
        "max_drawdown_%": [max_dd(d[c].values) * 100 for c in d],
        "worst_12m_%": [worst12(d[c].values) * 100 for c in d],
    }).round(1)

print("\nTEST 2: portfolios (monthly rebalanced)")
for name, d in [("Full sample", P), ("Before 2000", P[:"1999"]), ("2000 onward", P["2000":])]:
    print(f"\n  {name}: {len(d)} months")
    print(summarize(d).to_string())

arr = P.values
def stat(a):
    return (a[:, 1].std() - a[:, 0].std()) * np.sqrt(12) * 100, (max_dd(a[:, 1]) - max_dd(a[:, 0])) * 100
vd, dd = zip(*[stat(arr[block_idx(len(arr))]) for _ in range(1000)])
v_obs, d_obs = stat(arr)
print(f"\n  60/40 minus Stocks, volatility (pts): {v_obs:.1f}, 95% CI {np.percentile(vd, [2.5, 97.5]).round(1)}")
print(f"  60/40 minus Stocks, max drawdown (pts, positive = shallower): {d_obs:.1f}, 95% CI {np.percentile(dd, [2.5, 97.5]).round(1)}")

# ---------- TEST 3: bonds in the worst 10% of stock quarters ----------
q = (1 + df[["stocks", "bonds"]]).resample("QE").prod() - 1
cnt = df.stocks.resample("QE").count()
q["infl"] = df.infl.resample("QE").last()
q = q[cnt == 3].dropna()
cut = q.stocks.quantile(0.10)
worst = q[q.stocks <= cut]
rest = q[q.stocks > cut]
print(f"\nTEST 3: worst 10% of stock quarters ({len(worst)} quarters, stocks <= {cut * 100:.1f}%)")
def line(label, d):
    print(f"  {label}: n={len(d)}, avg bond return {d.bonds.mean() * 100:.1f}% per quarter, bonds positive in {(d.bonds > 0).mean() * 100:.0f}%")
line("All worst quarters", worst)
line("  with inflation > 3%", worst[worst.infl > 3])
line("  with inflation <= 3%", worst[worst.infl <= 3])
line("All other quarters", rest)
bm = [rng.choice(worst.bonds.values, len(worst)).mean() for _ in range(5000)]
print(f"  Avg bond return in worst quarters, 95% CI: {np.percentile(bm, [2.5, 97.5]).round(3) * 100} (% per quarter)")

# ---------- TEST 7: cash vs bonds in the worst stock quarters ----------
cash_m = (fac[4] / 100).reindex(df.index)
cash_q = (1 + cash_m).resample("QE").prod() - 1
print("\nTEST 7: cash vs bonds in the worst 10% of stock quarters")
for label, d in [("Inflation > 3%", worst[worst.infl > 3]), ("Inflation <= 3%", worst[worst.infl <= 3])]:
    c = cash_q.reindex(d.index)
    print(f"  {label}: n={len(d)}, bonds {d.bonds.mean() * 100:.1f}%, cash {c.mean() * 100:.1f}% per quarter, cash beat bonds in {(c > d.bonds).sum()} of {len(d)} quarters")

# ---------- TEST 8: stock-bond correlation by inflation band ----------
bands = [(0, 2), (2, 3), (3, 4), (4, 20)]
def band_corr(d, lo, hi):
    s = d[(d.infl >= lo) & (d.infl < hi)]
    return s.stocks.corr(s.bonds), len(s)
boot_dfs = [df.iloc[block_idx(len(df))] for _ in range(1000)]
print("\nTEST 8: stock-bond correlation by core PCE inflation band")
for lo, hi in bands:
    c, n = band_corr(df, lo, hi)
    bs = [band_corr(b, lo, hi)[0] for b in boot_dfs]
    ci = np.nanpercentile(bs, [2.5, 97.5])
    print(f"  {lo}% to {hi}%: correlation {c:.2f}, {n} months, 95% CI [{ci[0]:.2f}, {ci[1]:.2f}]")

# ---------- TEST 9: finer bands (0.5 steps) and threshold sweep (0.25 steps) ----------
fine = [(0, 1.5)] + [(round(a, 2), round(a + 0.5, 2)) for a in np.arange(1.5, 5.0, 0.5)] + [(5, 20)]
print("\nTEST 9a: stock-bond correlation, 0.5-point inflation bands")
for lo, hi in fine:
    c, n = band_corr(df, lo, hi)
    bs = [band_corr(b, lo, hi)[0] for b in boot_dfs]
    ci = np.nanpercentile(bs, [2.5, 97.5])
    print(f"  {lo:>4}% to {hi:>4}%: corr {c:5.2f}, {n:3d} months, 95% CI [{ci[0]:5.2f}, {ci[1]:5.2f}]")

def split_diff(d, x):
    hi_s, lo_s = d[d.infl >= x], d[d.infl < x]
    return hi_s.stocks.corr(hi_s.bonds) - lo_s.stocks.corr(lo_s.bonds)

print("\nTEST 9b: threshold sweep, correlation difference (inflation >= X minus < X)")
for x in np.arange(2.0, 4.76, 0.25):
    d_obs = split_diff(df, x)
    bs = [split_diff(b, x) for b in boot_dfs]
    ci = np.nanpercentile(bs, [2.5, 97.5])
    print(f"  X = {x:.2f}%: difference {d_obs:5.2f}, 95% CI [{ci[0]:5.2f}, {ci[1]:5.2f}], {(df.infl >= x).sum():3d} months above")

# ---------- TEST 10: backtest of Trigger 1 (trim bonds into cash when inflation is high) ----------
UP, DOWN, HOLD = 3.25, 2.75, 3
known = df.infl.shift(2)
state = np.zeros(len(df), dtype=bool)
on = False
for i in range(len(df)):
    w = known.iloc[max(0, i - HOLD + 1): i + 1]
    if len(w) == HOLD and w.notna().all():
        if not on and (w > UP).all():
            on = True
        elif on and (w < DOWN).all():
            on = False
    state[i] = on

cash_t = (fac[4] / 100).reindex(df.index)

def run(f, st):
    bw = np.where(st, 0.4 * (1 - f), 0.4)
    cw = np.where(st, 0.4 * f, 0.0)
    return pd.Series(0.6 * df.stocks.values + bw * df.bonds.values + cw * cash_t.values, index=df.index)

def stats(r):
    return {
        "ann_ret_%": round(((1 + r).prod() ** (12 / len(r)) - 1) * 100, 1),
        "vol_%": round(r.std() * np.sqrt(12) * 100, 1),
        "max_dd_%": round(max_dd(r.values) * 100, 1),
        "worst_12m_%": round(worst12(r.values) * 100, 1),
    }

print("\nTEST 10: Trigger 1 backtest (60/40 baseline; trimmed bonds go to cash)")
print(f"  Months in trimmed state: {state.sum()} of {len(state)} ({state.mean() * 100:.0f}%), switches: {int((np.diff(state.astype(int)) != 0).sum())}")
rows = {"Baseline 60/40": stats(run(0, state))}
for f, name in [(1 / 3, "Trim 1/3"), (0.5, "Trim 1/2"), (1.0, "Trim all bonds")]:
    rows[name] = stats(run(f, state))
print(pd.DataFrame(rows).T.to_string())

print("\n  Return and max drawdown by half (baseline vs trim 1/2):")
for label, sl in [("1970-1999", slice("1970", "1999")), ("2000-2026", slice("2000", "2026"))]:
    b, t = run(0, state)[sl], run(0.5, state)[sl]
    print(f"   {label}: baseline {stats(b)['ann_ret_%']}% / {stats(b)['max_dd_%']}%, trim 1/2 {stats(t)['ann_ret_%']}% / {stats(t)['max_dd_%']}%")

print("\n  Calendar-year returns, baseline vs trim 1/2 (%):")
for yr in [1974, 1979, 1980, 1981, 2008, 2022]:
    b = (1 + run(0, state)[str(yr)]).prod() - 1
    t = (1 + run(0.5, state)[str(yr)]).prod() - 1
    print(f"   {yr}: {b * 100:6.1f} vs {t * 100:6.1f}")

act = stats(run(0.5, state))
rng2 = np.random.default_rng(1)
sims = []
for _ in range(1000):
    k = int(rng2.integers(24, len(state) - 24))
    s = stats(run(0.5, np.roll(state, k)))
    sims.append((s["ann_ret_%"], s["max_dd_%"]))
sims = np.array(sims)
print("\n  Placebo (trim 1/2, random timing, same time spent trimmed):")
print(f"   Real rule: {act['ann_ret_%']}% return, {act['max_dd_%']}% max drawdown")
print(f"   Share of placebos with return at least as high: {(sims[:, 0] >= act['ann_ret_%']).mean() * 100:.0f}%")
print(f"   Share of placebos with a drawdown at least as shallow: {(sims[:, 1] >= act['max_dd_%']).mean() * 100:.0f}%")

# ---------- TEST 11: where are we now? ----------
print("\nTEST 11: current stock-bond correlation and inflation state")
for n in [12, 24, 36]:
    cur = df.stocks.iloc[-n:].corr(df.bonds.iloc[-n:])
    hist = df.stocks.rolling(n).corr(df.bonds).dropna()
    print(f"  Last {n} months: correlation {cur:5.2f}  (history median {hist.median():5.2f}; {(hist < cur).mean() * 100:.0f}% of past windows were lower)")
vol36 = df.infl.rolling(36).std()
print(f"  Latest data month: {df.index[-1].date()}")
print(f"  Core PCE inflation now: {df.infl.iloc[-1]:.2f}%  (above 3.25%: {df.infl.iloc[-1] > 3.25})")
print(f"  Inflation variability (36-month std of YoY inflation): {vol36.iloc[-1]:.2f}  ({(vol36.dropna() < vol36.iloc[-1]).mean() * 100:.0f}th percentile of history)")
print(f"  Trigger 1 state in the backtest at the last month: {'TRIMMED' if state[-1] else 'NOT trimmed'}")
r12 = df.stocks.rolling(12).corr(df.bonds)
print("  Rolling 12-month correlation, last 12 months (every 3rd):")
print(r12.iloc[-12::3].round(2).to_string())

# ---------- TEST 12: inflation level vs inflation variability ----------
d2 = pd.DataFrame({
    "level": df.infl,
    "vol": df.infl.rolling(36).std(),
    "past": r12,
    "fwd": r12.shift(-12),
}).dropna()

def fit_pred(cols, tr, te):
    Xtr = np.column_stack([np.ones(len(tr))] + [tr[c].values for c in cols])
    Xte = np.column_stack([np.ones(len(te))] + [te[c].values for c in cols])
    beta = np.linalg.lstsq(Xtr, tr.fwd.values, rcond=None)[0]
    return Xtr @ beta, Xte @ beta, beta

def r2(y, p):
    return 1 - ((y - p) ** 2).sum() / ((y - y.mean()) ** 2).sum()

train, test = d2[:"1999"], d2["2000":]
models = [["level"], ["vol"], ["level", "vol"], ["past"], ["past", "level"], ["past", "level", "vol"]]
print("\nTEST 12: what predicts the NEXT 12 months of stock-bond correlation?")
print(f"  Level and variability are correlated with each other: {d2.level.corr(d2.vol):.2f}")
print(f"  {'Predictors':<22}{'R2 in-sample 1970-99':>22}{'R2 out-of-sample 2000-26':>28}")
for cols in models:
    p_tr, p_te, _ = fit_pred(cols, train, test)
    mean_pred = np.full(len(test), train.fwd.mean())
    oos = 1 - ((test.fwd.values - p_te) ** 2).sum() / ((test.fwd.values - mean_pred) ** 2).sum()
    print(f"  {'+'.join(cols):<22}{r2(train.fwd.values, p_tr):>22.2f}{oos:>28.2f}")

z = (d2[["level", "vol"]] - d2[["level", "vol"]].mean()) / d2[["level", "vol"]].std()
z["fwd"] = d2.fwd
def coefs(d):
    X = np.column_stack([np.ones(len(d)), d.level.values, d.vol.values])
    return np.linalg.lstsq(X, d.fwd.values, rcond=None)[0][1:]
obs = coefs(z)
bs = np.array([coefs(z.iloc[block_idx(len(z), 24)]) for _ in range(1000)])
ci = np.percentile(bs, [2.5, 97.5], axis=0)
print(f"\n  Full sample, standardized coefficients (effect of a 1-std-dev change on next-12m correlation):")
print(f"    Inflation level:       {obs[0]:5.2f}, 95% CI [{ci[0, 0]:5.2f}, {ci[1, 0]:5.2f}]")
print(f"    Inflation variability: {obs[1]:5.2f}, 95% CI [{ci[0, 1]:5.2f}, {ci[1, 1]:5.2f}]")

# ---------- Trimmed-period timeline ----------
chg = np.diff(state.astype(int), prepend=0)
starts = list(df.index[chg == 1])
ends = list(df.index[chg == -1])
print("\nTRIMMED PERIODS (Trigger 1 backtest):")
for i, s in enumerate(starts):
    e = ends[i] if i < len(ends) else None
    print(f"  {s.date()} to {e.date() if e is not None else 'still trimmed'}")

# ---------- DATA COVERAGE CHECK ----------
print("\nDATA COVERAGE CHECK")
print(f"  Main dataset: {df.index[0].date()} to {df.index[-1].date()}, {len(df)} months")
expected = pd.date_range(df.index[0], df.index[-1], freq="ME")
missing = expected.difference(df.index)
print(f"  Missing months inside the range: {len(missing)}")
per_year = df.groupby(df.index.year).size()
short = per_year[per_year < 12]
print(f"  Years with fewer than 12 months: {short.to_dict()}")
print(f"  Portfolio comparison (Test 2) starts: {P.index[0].date()}, {len(P)} months")
print(f"  Correlation prediction (Test 12) uses: {d2.index[0].date()} to {d2.index[-1].date()}, {len(d2)} months")
print(f"  Trigger 1 backtest covers: {df.index[0].date()} to {df.index[-1].date()}")

# ---------- TEST 13: sensitivity of Trigger 1 to its two lines ----------
def make_state(up, down, hold=3):
    st = np.zeros(len(df), dtype=bool)
    on_ = False
    for i in range(len(df)):
        w = known.iloc[max(0, i - hold + 1): i + 1]
        if len(w) == hold and w.notna().all():
            if not on_ and (w > up).all():
                on_ = True
            elif on_ and (w < down).all():
                on_ = False
        st[i] = on_
    return st

print("\nTEST 13: Trigger 1 sensitivity (trim 1/2). Baseline 60/40 for reference:")
b = stats(run(0, state))
print(f"  Baseline: return {b['ann_ret_%']}%, max drawdown {b['max_dd_%']}%, 2022 {((1 + run(0, state)['2022']).prod() - 1) * 100:.1f}%")
print(f"  {'Act above':>10}{'Restore below':>15}{'% months trimmed':>18}{'periods':>9}{'return %':>10}{'max DD %':>10}{'2022 %':>8}{'trimmed now':>13}")
for up in [3.0, 3.25, 3.5]:
    for down in [2.5, 2.75, 3.0]:
        st = make_state(up, down)
        r = run(0.5, st)
        s = stats(r)
        n_per = int((np.diff(st.astype(int), prepend=0) == 1).sum())
        y22 = ((1 + r['2022']).prod() - 1) * 100
        print(f"  {up:>10.2f}{down:>15.2f}{st.mean() * 100:>18.0f}{n_per:>9}{s['ann_ret_%']:>10.1f}{s['max_dd_%']:>10.1f}{y22:>8.1f}{str(bool(st[-1])):>13}")

# ---------- TEST 14: trigger shoot-out (all rules fixed in advance; no parameter was fitted) ----------
bidx = (1 + df.bonds).cumprod()
b_known = bidx.shift(1)
sma = b_known.rolling(10).mean()
st_trend = ((b_known <= sma) & sma.notna()).values
corr_known = df.stocks.rolling(12).corr(df.bonds).shift(1)
st_corr = ((corr_known > 0) & corr_known.notna()).values
st_infl = make_state(3.25, 3.0)
rules = {
    "Baseline 60/40": np.zeros(len(df), dtype=bool),
    "Inflation rule (3.25/3.0)": st_infl,
    "Bond trend filter (10-mo avg)": st_trend,
    "Past-12m correlation > 0": st_corr,
    "Inflation OR trend": st_infl | st_trend,
    "Inflation AND trend": st_infl & st_trend,
}

def quick(r):
    return ((1 + r).prod() ** (12 / len(r)) - 1) * 100, max_dd(r.values) * 100

print("\nTEST 14: trigger shoot-out (trim 1/2 of bonds into cash when the rule is on), 1970-2026")
rows, rets = {}, {}
for name, st in rules.items():
    r = run(0 if name.startswith("Baseline") else 0.5, st)
    rets[name] = r
    s = stats(r)
    s["% trimmed"] = round(st.mean() * 100)
    s["switches"] = int((np.diff(st.astype(int)) != 0).sum())
    rows[name] = s
print(pd.DataFrame(rows).T.to_string())

print("\n  Return % / max drawdown % by half:")
for name, r in rets.items():
    a, b = quick(r["1970":"1999"]), quick(r["2000":"2026"])
    print(f"   {name:<32} 1970-99: {a[0]:5.1f} / {a[1]:6.1f}    2000-26: {b[0]:5.1f} / {b[1]:6.1f}")

print("\n  Calendar-year returns (%):")
print(f"   {'':<32}{'1974':>8}{'1980':>8}{'2008':>8}{'2022':>8}")
for name, r in rets.items():
    ys = [((1 + r[str(y)]).prod() - 1) * 100 for y in (1974, 1980, 2008, 2022)]
    print(f"   {name:<32}" + "".join(f"{v:8.1f}" for v in ys))

print("\n  Placebo (same time spent trimmed, timing shifted at random; 500 draws):")
rng3 = np.random.default_rng(2)
for name, st in rules.items():
    if name.startswith("Baseline") or st.sum() == 0:
        continue
    act = quick(rets[name])
    sims = np.array([quick(run(0.5, np.roll(st, int(rng3.integers(24, len(st) - 24))))) for _ in range(500)])
    print(f"   {name:<32} placebos matching return: {(sims[:, 0] >= act[0]).mean() * 100:3.0f}%   matching drawdown: {(sims[:, 1] >= act[1]).mean() * 100:3.0f}%")

# ---------- TEST 15: risk parity replica (stocks + 10Y bonds only) ----------
W, TARGET, CAP, SPREAD = 36, 0.10, 3.0, 0.005 / 12
sr, br, cr = df.stocks.values, df.bonds.values, cash_t.values
n = len(df)
gross = np.full(n, np.nan)
lev = np.full(n, np.nan)
levered = np.full(n, np.nan)
for t in range(W, n):
    S, B = sr[t - W:t], br[t - W:t]
    sd_s, sd_b = S.std(ddof=1), B.std(ddof=1)
    w_s = (1 / sd_s) / (1 / sd_s + 1 / sd_b)
    w_b = 1 - w_s
    c = np.cov(S, B)
    pv = w_s ** 2 * c[0, 0] + w_b ** 2 * c[1, 1] + 2 * w_s * w_b * c[0, 1]
    L = min(CAP, TARGET / np.sqrt(pv * 12))
    gross[t] = w_s * sr[t] + w_b * br[t]
    lev[t] = L
    levered[t] = L * gross[t] - (L - 1) * (cr[t] + SPREAD)
rp = pd.DataFrame({
    "Stocks": df.stocks,
    "60/40": 0.6 * df.stocks + 0.4 * df.bonds,
    "Risk parity, unlevered": pd.Series(gross, index=df.index),
    "Risk parity, levered to 10% vol": pd.Series(levered, index=df.index),
}).dropna()
print(f"\nTEST 15: risk parity replica, {rp.index[0].date()} to {rp.index[-1].date()} ({len(rp)} months)")
print("  Assumptions: inverse-vol weights from trailing 36 months, leverage up to 3x, financing at T-bill + 0.5%/yr")
print(pd.DataFrame({c: stats(rp[c]) for c in rp}).T.to_string())
lv = pd.Series(lev, index=df.index).dropna()
print(f"\n  Leverage used: average {lv.mean():.2f}x, max {lv.max():.2f}x, at 2021-12: {lv['2021-12'].iloc[0]:.2f}x, at 2022-12: {lv['2022-12'].iloc[0]:.2f}x")
print("\n  Calendar-year returns (%):")
print(f"   {'':<34}{'1974':>8}{'1981':>8}{'2008':>8}{'2022':>8}")
for c in rp:
    ys = [((1 + rp[c][str(y)]).prod() - 1) * 100 for y in (1974, 1981, 2008, 2022)]
    print(f"   {c:<34}" + "".join(f"{v:8.1f}" for v in ys))

# ---------- TEST 18: growth-shock signals for Trigger 2 (all rules fixed in advance) ----------
unrate = month_end(fred.get_series("UNRATE"))
tb3 = month_end(fred.get_series("TB3MS"))
gs10 = month_end(fred.get_series("GS10"))
indpro = month_end(fred.get_series("INDPRO"))
usrec = month_end(fred.get_series("USREC"))

u3 = unrate.rolling(3).mean()
sahm = u3 - u3.rolling(12).min()
raw_sig = {
    "Sahm rule (unemployment +0.5)": sahm >= 0.5,
    "Yield curve inverted (10Y-3M < 0)": (gs10 - tb3) < 0,
    "Industrial production YoY < 0": indpro.pct_change(12) < 0,
}
idx = df.index
signals = {k: v.astype(float).shift(1).reindex(idx).fillna(0).astype(bool).values for k, v in raw_sig.items()}   # one-month publication lag
rec = usrec.reindex(idx).fillna(0).values
starts = [i for i in range(1, len(idx)) if rec[i] == 1 and rec[i - 1] == 0 and idx[i] >= pd.Timestamp("1972-01-01")]

def onsets(s):
    return [i for i in range(len(s)) if s[i] and not s[max(0, i - 6):i].any()]

print("\nTEST 18: growth-shock signals vs. NBER recessions")
print("  Recession starts since 1972: " + ", ".join(idx[i].strftime("%Y-%m") for i in starts))
print("  Lead = months from signal onset to recession start (negative = signal came after the start)")
for name, s in signals.items():
    on = onsets(s)
    leads, missed = [], 0
    for r in starts:
        cand = [p for p in on if r - 24 <= p <= r + 6]
        if cand:
            leads.append(r - cand[0])
        else:
            missed += 1
    false = [p for p in on if not (rec[p] == 1 or any(p < r <= p + 24 for r in starts))]
    print(f"\n  {name}")
    print(f"    Recessions caught: {len(starts) - missed} of {len(starts)}; leads (months): {leads}")
    print(f"    Signal onsets: {len(on)}, false alarms (no recession underway or within 24 months): {len(false)}")
    print(f"    Months signal is on: {s.mean() * 100:.0f}%")

    fwd = {}
    for lab, ser in [("stocks", df.stocks), ("bonds", df.bonds)]:
        c = (1 + ser).rolling(12).apply(np.prod, raw=True).shift(-12) - 1
        fwd[lab] = c.values
    ok = [p for p in on if p + 12 < len(idx)]
    if ok:
        print(f"    Next 12 months after onset (n={len(ok)}): stocks {np.nanmean([fwd['stocks'][p] for p in ok]) * 100:5.1f}%, bonds {np.nanmean([fwd['bonds'][p] for p in ok]) * 100:5.1f}%   | all months: stocks {np.nanmean(fwd['stocks']) * 100:5.1f}%, bonds {np.nanmean(fwd['bonds']) * 100:5.1f}%")

print("\n  Portfolio rule: when signal is on, hold 40% stocks / 60% bonds instead of 60/40 (1970-2026)")
def port_run(st):
    w = 0.6 - 0.2 * st.astype(float)
    return pd.Series(w * df.stocks.values + (1 - w) * df.bonds.values, index=idx)
base = port_run(np.zeros(len(idx), dtype=bool))
rows = {"Baseline 60/40": stats(base)}
rng4 = np.random.default_rng(3)
placebo = {}
for name, s in signals.items():
    r = port_run(s)
    st = stats(r)
    st["% on"] = round(s.mean() * 100)
    rows[name] = st
    act = quick(r)
    sims = np.array([quick(port_run(np.roll(s, int(rng4.integers(24, len(s) - 24))))) for _ in range(500)])
    placebo[name] = ((sims[:, 0] >= act[0]).mean() * 100, (sims[:, 1] >= act[1]).mean() * 100)
print(pd.DataFrame(rows).T.to_string())
print("  Calendar-year returns (%), baseline vs. each signal:")
yrs = [1974, 1981, 2001, 2008, 2020, 2022]
print(f"   {'':<36}" + "".join(f"{y:>8}" for y in yrs))
for name, r in [("Baseline 60/40", base)] + [(n, port_run(s)) for n, s in signals.items()]:
    print(f"   {name:<36}" + "".join(f"{((1 + r[str(y)]).prod() - 1) * 100:8.1f}" for y in yrs))
print("  Placebo (same time on, random timing): share matching return / share matching drawdown")
for name, (a, b) in placebo.items():
    print(f"   {name:<36} {a:3.0f}% / {b:3.0f}%")

# ---------- TEST 18 follow-up: yield-curve onsets and current readings ----------
s_curve = signals["Yield curve inverted (10Y-3M < 0)"]
print("\nYIELD-CURVE ONSETS (month the inversion signal turned on):")
for p in onsets(s_curve):
    nxt_rec = [r for r in starts if r >= p]
    msg = f"recession starts {idx[nxt_rec[0]].strftime('%Y-%m')} ({nxt_rec[0] - p} months later)" if nxt_rec else "no recession after"
    print(f"  {idx[p].strftime('%Y-%m')}: {msg}")
print("\nCURRENT READINGS (latest month with data):")
print(f"  10Y minus 3M spread: {(gs10 - tb3).dropna().iloc[-1]:.2f} points  (inverted if below 0)")
print(f"  Sahm rule value: {sahm.dropna().iloc[-1]:.2f}  (signal at 0.50 or more)")
print(f"  Industrial production YoY: {indpro.pct_change(12).dropna().iloc[-1] * 100:.1f}%  (signal if below 0)")
