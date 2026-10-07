# Test 21: Trigger 2 with a hold period. The curve usually un-inverts before the selloff, so the
# "on while inverted" rule (Test 20) is out of the market at the wrong time.
# Run from the repo root:  python scripts/phase2_macro/trigger2_hold.py > data/phase2_macro/trigger2_hold_results.txt
#
# Rule (fixed before running): Trigger 2 is on while the 10Y minus 3M spread is negative (prior month's data)
#   AND for 12 months after the last inverted month. When on, move 10 points from stocks: to bonds normally,
#   to cash while Trigger 1 is on (Test 20). Trigger 1 unchanged (act 3.25 / restore 3.0, 3 months, 2-month lag).
# Disclosed: the 12-month hold and the "after un-inversion" timing are informed by history already seen
#   (Test 18 lead times; 2001, 2008 and 2020 selloffs came after the curve un-inverted). This is in-sample.
#
# Pre-committed decision: Trigger 2 becomes ACTIVE only if BOTH
#   (1) fewer than 10% of random-timing placebos match its max drawdown, and
#   (2) its annual return is at most 0.2 points below Trigger 1 alone.
# Otherwise Trigger 2 is WATCH-ONLY and we stop testing it.
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

def max_dd(r):
    w = np.cumprod(1 + r)
    return (w / np.maximum.accumulate(w) - 1).min()

def worst12(r):
    return (pd.Series(1 + r).rolling(12).apply(np.prod, raw=True) - 1).min()

def stats(r):
    return {
        "ann_ret_%": round(((1 + r).prod() ** (12 / len(r)) - 1) * 100, 2),
        "vol_%": round(r.std() * np.sqrt(12) * 100, 1),
        "max_dd_%": round(max_dd(r.values) * 100, 1),
        "worst_12m_%": round(worst12(r.values) * 100, 1),
    }

# ---------- data (same construction as robustness.py) ----------
load_dotenv()
fred = Fred(api_key=os.getenv("FRED_API_KEY"))
fac = french("F-F_Research_Data_Factors")
stocks = (fac[1] + fac[4]) / 100
cash = fac[4] / 100
y = month_end(fred.get_series("GS10")) / 100
y_prev = y.shift(1)
dur = (1 - (1 + y_prev / 2) ** -20) / y_prev
bonds = y_prev / 12 - dur * (y - y_prev)
infl = month_end(fred.get_series("PCEPILFE")).pct_change(12) * 100
tb3 = month_end(fred.get_series("TB3MS"))
gs10 = month_end(fred.get_series("GS10"))

df = pd.DataFrame({"stocks": stocks, "bonds": bonds, "cash": cash, "infl": infl}).dropna()["1970":]
idx = df.index
print(f"Data: {idx[0].date()} to {idx[-1].date()}, {len(df)} months\n")


# ---------- trigger states ----------
known = df.infl.shift(2)
t1 = np.zeros(len(df), dtype=bool)
on = False
for i in range(len(df)):
    w = known.iloc[max(0, i - 2): i + 1]
    if len(w) == 3 and w.notna().all():
        if not on and (w > 3.25).all():
            on = True
        elif on and (w < 3.0).all():
            on = False
    t1[i] = on
inv = ((gs10 - tb3) < 0).astype(float).shift(1).reindex(idx).fillna(0).astype(bool).values   # prior month's data

HOLD = 12
t2 = np.zeros(len(idx), dtype=bool)
last_inv = -10**9
for i in range(len(idx)):
    if inv[i]:
        last_inv = i
    t2[i] = inv[i] or (i - last_inv) <= HOLD

def periods(st):
    out, i = [], 0
    while i < len(st):
        if st[i]:
            j = i
            while j + 1 < len(st) and st[j + 1]:
                j += 1
            out.append(f"{idx[i].strftime('%Y-%m')} to {idx[j].strftime('%Y-%m')}")
            i = j + 1
        else:
            i += 1
    return out

print(f"Trigger 2 (hold version) on {t2.mean() * 100:.0f}% of months (inverted-only version: {inv.mean() * 100:.0f}%); overlap with Trigger 1: {(t1 & t2).sum() / t2.sum() * 100:.0f}% of its months")
print("Periods on: " + "; ".join(periods(t2)) + "\n")

S = 0.10
def port(t2s, S=S):
    f1, f2 = t1.astype(float), t2s.astype(float)
    ws = 0.6 - S * f2
    wb = 0.4 - 0.2 * f1 + S * f2 * (1 - f1)
    wc = 0.2 * f1 + S * f2 * f1
    return pd.Series(ws * df.stocks.values + wb * df.bonds.values + wc * df.cash.values, index=idx)

base = pd.Series(0.6 * df.stocks.values + 0.4 * df.bonds.values, index=idx)
runs = {
    "Baseline 60/40": base,
    "Trigger 1 only": port(np.zeros(len(idx), dtype=bool)),
    "T1 + T2 inverted-only (Test 20)": port(inv),
    "T1 + T2 hold 12m (Test 21)": port(t2),
}
print("TEST 21a: full sample, 1970-2026 (10-point shift, cash routing while Trigger 1 is on)")
print(pd.DataFrame({k: stats(v) for k, v in runs.items()}).T.to_string())

print("\nTEST 21b: calendar-year returns (%)")
cal = [1973, 1974, 1980, 1981, 1982, 1990, 2001, 2002, 2007, 2008, 2009, 2020, 2023, 2024]
print(f"  {'':<32}" + "".join(f"{y:>7}" for y in cal))
for k, v in runs.items():
    print(f"  {k:<32}" + "".join(f"{((1 + v[str(y)]).prod() - 1) * 100:7.1f}" for y in cal))

print("\nTEST 21c: placebo (hold-version on/off pattern shifted at random, same time on; 500 draws)")
rng = np.random.default_rng(21)
act = stats(port(t2))
sims = np.array([[stats(port(np.roll(t2, int(rng.integers(24, len(idx) - 24)))))[m] for m in ("ann_ret_%", "max_dd_%")] for _ in range(500)])
p_ret = (sims[:, 0] >= act["ann_ret_%"]).mean() * 100
p_dd = (sims[:, 1] >= act["max_dd_%"]).mean() * 100
print(f"  Share of placebos matching return: {p_ret:.0f}%, matching drawdown: {p_dd:.0f}%")

t1s = stats(runs["Trigger 1 only"])
cost = t1s["ann_ret_%"] - act["ann_ret_%"]
print("\nDECISION (rule fixed before running)")
print(f"  Placebo drawdown match {p_dd:.0f}% (needs < 10%); return cost vs Trigger 1 only {cost:+.2f} pts (needs <= 0.20)")
print("  -> Trigger 2 ACTIVE: 10 points, cash while Trigger 1 is on" if (p_dd < 10 and cost <= 0.2) else "  -> Trigger 2 WATCH-ONLY; stop testing it")
