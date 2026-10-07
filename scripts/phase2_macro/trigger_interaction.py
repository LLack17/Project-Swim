# Test 20: how Trigger 1 (inflation) and Trigger 2 (yield curve) interact, and how big Trigger 2's shift should be.
# Run from the repo root:  python scripts/phase2_macro/trigger_interaction.py > data/phase2_macro/trigger_interaction_results.txt
#
# Rules (fixed before running):
#   Base portfolio: 60% stocks / 40% 10-year Treasuries, rebalanced monthly, 1970-2026.
#   Trigger 1: core PCE YoY (2-month data lag) above 3.25% for 3 months -> trim half of the original 40% bonds into cash;
#              restore after 3 months below 3.0%. Starts untrimmed.
#   Trigger 2: 10Y minus 3M spread below 0 (prior month's data) -> move S points from stocks.
#   Routing "bonds": the S points always go to bonds (Trigger 1 trims only the original 40%).
#   Routing "cash":  the S points go to bonds, except while Trigger 1 is on, when they go to cash.
#   Sizes tested: S = 10 and 20 points.
#
# Pre-committed decisions:
#   Routing: keep the cash routing (it follows from Trigger 1) unless it is materially worse than bonds routing:
#            max drawdown deeper by more than 1 point, or annual return lower by more than 0.2 points.
#   Size:    use 10 points unless 20 points gives a max drawdown at least 1 point shallower than 10 points
#            AND fewer than 10% of random-timing placebos match its drawdown.
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
t2 = ((gs10 - tb3) < 0).astype(float).shift(1).reindex(idx).fillna(0).astype(bool).values

both = t1 & t2
print("Trigger states (share of months on):")
print(f"  Trigger 1 (inflation): {t1.mean() * 100:.0f}%   Trigger 2 (curve inverted): {t2.mean() * 100:.0f}%   both: {both.mean() * 100:.0f}% ({both.sum()} months)")
print(f"  Share of Trigger 2 months that overlap Trigger 1: {both.sum() / max(t2.sum(), 1) * 100:.0f}%")
yrs = sorted(set(idx[both].year))
print(f"  Years with overlap months: {yrs}\n")

# ---------- portfolios ----------
def port(S, route, t1s=t1, t2s=t2):
    f1, f2 = t1s.astype(float), t2s.astype(float)
    ws = 0.6 - S * f2
    wb = 0.4 - 0.2 * f1
    wc = 0.2 * f1
    if route == "bonds":
        wb = wb + S * f2
    else:  # cash routing: shift goes to cash while Trigger 1 is on
        wb = wb + S * f2 * (1 - f1)
        wc = wc + S * f2 * f1
    return pd.Series(ws * df.stocks.values + wb * df.bonds.values + wc * df.cash.values, index=idx)

base = pd.Series(0.6 * df.stocks.values + 0.4 * df.bonds.values, index=idx)
t1_only = port(0.0, "cash")
runs = {"Baseline 60/40": base, "Trigger 1 only": t1_only}
for S in (0.10, 0.20):
    for route in ("bonds", "cash"):
        runs[f"T1 + T2 {int(S * 100)}pt, route {route}"] = port(S, route)

print("TEST 20a: full sample, 1970-2026")
print(pd.DataFrame({k: stats(v) for k, v in runs.items()}).T.to_string())

print("\nTEST 20b: calendar-year returns (%)")
cal = [1973, 1974, 1979, 1980, 1981, 1982, 2001, 2008, 2020, 2022, 2023, 2024]
print(f"  {'':<28}" + "".join(f"{y:>7}" for y in cal))
for k, v in runs.items():
    print(f"  {k:<28}" + "".join(f"{((1 + v[str(y)]).prod() - 1) * 100:7.1f}" for y in cal))

print("\nTEST 20c: return in overlap months only (both triggers on), stocks / bonds / cash, annualized %")
for lab in ("stocks", "bonds", "cash"):
    r = df[lab].values[both]
    print(f"  {lab:<7} {((1 + r).prod() ** (12 / len(r)) - 1) * 100:6.1f}" if len(r) else f"  {lab}: no overlap")

# ---------- placebo: Trigger 2 timing shifted at random, Trigger 1 kept as is ----------
print("\nTEST 20d: placebo (Trigger 2's on/off pattern shifted at random, same time on; 500 draws)")
rng = np.random.default_rng(20)
shifts = [int(rng.integers(24, len(idx) - 24)) for _ in range(500)]
plc = {}
for S in (0.10, 0.20):
    for route in ("bonds", "cash"):
        act = stats(port(S, route))
        sims = np.array([[stats(port(S, route, t2s=np.roll(t2, k)))[m] for m in ("ann_ret_%", "max_dd_%")] for k in shifts])
        name = f"T1 + T2 {int(S * 100)}pt, route {route}"
        plc[name] = ((sims[:, 0] >= act["ann_ret_%"]).mean() * 100, (sims[:, 1] >= act["max_dd_%"]).mean() * 100)
        print(f"  {name:<28} share matching return {plc[name][0]:3.0f}%, matching drawdown {plc[name][1]:3.0f}%")

# ---------- pre-committed decisions ----------
s = {k: stats(v) for k, v in runs.items()}
print("\nDECISIONS (rules fixed before running)")
for S in (10, 20):
    b, c = s[f"T1 + T2 {S}pt, route bonds"], s[f"T1 + T2 {S}pt, route cash"]
    worse = (c["max_dd_%"] < b["max_dd_%"] - 1) or (c["ann_ret_%"] < b["ann_ret_%"] - 0.2)
    print(f"  Routing at {S}pt: cash minus bonds = drawdown {c['max_dd_%'] - b['max_dd_%']:+.1f} pts, return {c['ann_ret_%'] - b['ann_ret_%']:+.2f} pts -> {'REJECT cash routing' if worse else 'keep cash routing'}")
c10, c20 = s["T1 + T2 10pt, route cash"], s["T1 + T2 20pt, route cash"]
gain = c20["max_dd_%"] - c10["max_dd_%"]
pick20 = gain >= 1 and plc["T1 + T2 20pt, route cash"][1] < 10
print(f"  Size (cash routing): 20pt minus 10pt drawdown {gain:+.1f} pts, 20pt placebo drawdown match {plc['T1 + T2 20pt, route cash'][1]:.0f}% -> use {'20' if pick20 else '10'} points")
