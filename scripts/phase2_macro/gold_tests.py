# Tests 22-23: gold as a DIVERSIFIER (role fixed before running; the inflation-hedge question was settled in Test 19).
# Run from the repo root:  python scripts/phase2_macro/gold_tests.py > data/phase2_macro/gold_tests_results.txt
#
# Test 22 (gold vs. more Treasuries): does a 10% gold sleeve beat simply holding 10% more Treasuries (and 10% cash)?
#   Two settings: a static 60/40 core, and our actual core with Triggers 1 and 2 (final rules). Sleeves are static
#   10% and sit outside the triggers. Gold = World Bank monthly average prices, 1975 on.
# Test 23 (crisis replay): gold month by month in four stock selloffs, with GLD month-end prices where available
#   (2004 on), so the smoothing in the averages is visible. Case studies, not statistics.
#
# Decision: Landon's judgment call (decided before running), labeled as a judgment exception either way.
# Reading guide fixed before running (informs the call, not binding):
#   Test 22 favors gold if, in the with-triggers setting, the gold sleeve's max drawdown is at least 1 point
#   shallower than the Treasury sleeve's, at a return cost of at most 0.5 points, and it is shallower in both halves.
#   Test 23 favors gold if it was flat or positive in most of the stock-down months of the four episodes.
import io
import os
import zipfile
import urllib.request
import warnings
import numpy as np
import pandas as pd
from dotenv import load_dotenv
from fredapi import Fred

warnings.simplefilter("ignore")
BASE = "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/"
WB_URL = "https://thedocs.worldbank.org/en/doc/74e8be41ceb20fa0da750cda2f6b9e4e-0050012026/related/CMO-Historical-Data-Monthly.xlsx"
WB_PATH = "data/phase2_macro/CMO-Historical-Data-Monthly.xlsx"

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

def par_duration(y):
    y = y.where(y.abs() > 1e-4, 1e-4)
    return (1 - (1 + y / 2) ** -20) / y

load_dotenv()
fred = Fred(api_key=os.getenv("FRED_API_KEY"))

# ---- core series: stocks, bonds (approximated from GS10), cash, inflation ----
fac = french("F-F_Research_Data_Factors")
y10 = month_end(fred.get_series("GS10")) / 100
yp = y10.shift(1)
bonds = yp / 12 - par_duration(yp) * (y10 - yp)
infl = month_end(fred.get_series("PCEPILFE")).pct_change(12) * 100
M = pd.DataFrame({"stocks": (fac[1] + fac[4]) / 100, "bonds": bonds, "cash": fac[4] / 100, "infl": infl}).dropna()["1970":]
print(f"Core data: {M.index[0].date()} to {M.index[-1].date()}, {len(M)} months")

# ---- World Bank commodity data (free, CC-BY, no key) ----
if not os.path.exists(WB_PATH):
    print("Downloading World Bank commodity price data (free)...")
    req = urllib.request.Request(WB_URL, headers={"User-Agent": "Mozilla/5.0"})
    with open(WB_PATH, "wb") as f:
        f.write(urllib.request.urlopen(req).read())
xl = pd.ExcelFile(WB_PATH)

def pick_sheet(*words):
    for s in xl.sheet_names:
        if all(w in s.lower() for w in words):
            return s
    print("Could not find a sheet containing", words, "; sheets are:", xl.sheet_names)
    raise SystemExit

def wb_sheet(sheet, key):
    raw = pd.read_excel(WB_PATH, sheet_name=sheet, header=None)
    col0 = raw.iloc[:, 0].astype(str).str.strip()
    first = col0[col0.str.match(r"^\d{4}M\d{2}$")].index[0]
    hdr = None
    for r in range(first - 1, max(-1, first - 12), -1):
        if raw.iloc[r].astype(str).str.strip().str.lower().str.startswith(key.lower()).any():
            hdr = r
            break
    if hdr is None:
        print(f"Could not find a header row containing '{key}' in sheet '{sheet}'")
        raise SystemExit
    data = raw.iloc[first:].copy()
    data.columns = [str(n).strip() for n in raw.iloc[hdr].tolist()]
    data.index = pd.to_datetime(col0.loc[first:].str.replace("M", "-") + "-01") + pd.offsets.MonthEnd(0)
    return data.drop(columns=[data.columns[0]]).apply(pd.to_numeric, errors="coerce")

prices = wb_sheet(pick_sheet("monthly", "price"), "gold")
indices = wb_sheet(pick_sheet("monthly", "ind"), "energy")
gold_col = [c for c in prices.columns if c.lower().startswith("gold")]
en_col = [c for c in indices.columns if c.lower() == "energy"]
ne_col = [c for c in indices.columns if c.lower().startswith("non-energy") or c.lower().startswith("non energy")]
if not (gold_col and en_col and ne_col):
    print("Could not find the expected columns. Price columns:", list(prices.columns)[:60])
    print("Index columns:", list(indices.columns)[:60])
    raise SystemExit
print(f"World Bank columns used: gold = '{gold_col[0]}', energy index = '{en_col[0]}', non-energy index = '{ne_col[0]}'")
gold = prices[gold_col[0]].pct_change()

gold = gold["1975":].dropna()   # US citizens could not own gold before 1975; matches Test 19

# ---- our trigger rules on the 60/40 core (Triggers 1 and 2, final) ----
tb3 = month_end(fred.get_series("TB3MS"))
inv_raw = ((month_end(fred.get_series("GS10")) - tb3) < 0)
M["gold"] = gold
D = M.dropna().copy()
idx = D.index
print(f"Test sample (gold available): {idx[0].date()} to {idx[-1].date()}, {len(D)} months\n")

# Trigger 1 computed on the full 1970+ history, then cut to the sample
known = M.infl.shift(2)
t1f = np.zeros(len(M), dtype=bool)
on = False
for i in range(len(M)):
    w = known.iloc[max(0, i - 2): i + 1]
    if len(w) == 3 and w.notna().all():
        if not on and (w > 3.25).all():
            on = True
        elif on and (w < 3.0).all():
            on = False
    t1f[i] = on
inv = inv_raw.astype(float).shift(1).reindex(M.index).fillna(0).astype(bool).values
t2f = np.zeros(len(M), dtype=bool)
last = -10**9
for i in range(len(M)):
    if inv[i]:
        last = i
    t2f[i] = inv[i] or (i - last) <= 12
t1 = pd.Series(t1f, index=M.index).reindex(idx).values.astype(float)
t2 = pd.Series(t2f, index=M.index).reindex(idx).values.astype(float)

def core(triggers):
    if not triggers:
        return 0.6 * D.stocks + 0.4 * D.bonds
    ws = 0.6 - 0.1 * t2
    wb = 0.4 - 0.2 * t1 + 0.1 * t2 * (1 - t1)
    wc = 0.2 * t1 + 0.1 * t2 * t1
    return pd.Series(ws * D.stocks.values + wb * D.bonds.values + wc * D.cash.values, index=idx)

def max_dd(r):
    w = np.cumprod(1 + np.asarray(r))
    return (w / np.maximum.accumulate(w) - 1).min()

def stats(r):
    r = pd.Series(r)
    return {"ann_ret_%": round(((1 + r).prod() ** (12 / len(r)) - 1) * 100, 2),
            "vol_%": round(r.std() * np.sqrt(12) * 100, 1),
            "max_dd_%": round(max_dd(r) * 100, 1),
            "worst_12m_%": round(((1 + r).rolling(12).apply(np.prod, raw=True) - 1).min() * 100, 1)}

cal = [1980, 1981, 1987, 2001, 2002, 2008, 2013, 2020, 2022]
for label, trig in [("STATIC 60/40 CORE", False), ("CORE WITH TRIGGERS 1 AND 2 (the portfolio we will run)", True)]:
    c = core(trig)
    runs = {
        "Core alone": c,
        "+10% Treasuries": 0.9 * c + 0.1 * D.bonds,
        "+10% cash": 0.9 * c + 0.1 * D.cash,
        "+10% gold": 0.9 * c + 0.1 * D.gold,
    }
    print(f"TEST 22: {label}")
    print(pd.DataFrame({k: stats(v) for k, v in runs.items()}).T.to_string())
    print("  Max drawdown by half (%):")
    for lab, sl in [("1975-2000", slice("1975", "2000")), ("2001-2026", slice("2001", "2026"))]:
        print("   " + lab + ": " + ", ".join(f"{k} {stats(v[sl])['max_dd_%']}" for k, v in runs.items()))
    print("  Calendar-year returns (%):")
    print(f"   {'':<18}" + "".join(f"{y:>7}" for y in cal))
    for k, v in runs.items():
        print(f"   {k:<18}" + "".join(f"{((1 + v[str(y)]).prod() - 1) * 100:7.1f}" for y in cal))
    if trig:
        g, t = stats(runs["+10% gold"]), stats(runs["+10% Treasuries"])
        halves = all(stats(runs["+10% gold"][sl])["max_dd_%"] > stats(runs["+10% Treasuries"][sl])["max_dd_%"]
                     for sl in [slice("1975", "2000"), slice("2001", "2026")])
        dd_gain = g["max_dd_%"] - t["max_dd_%"]
        cost = t["ann_ret_%"] - g["ann_ret_%"]
        print(f"  Reading guide: gold minus Treasuries sleeve = drawdown {dd_gain:+.1f} pts (needs >= +1.0), return cost {cost:+.2f} pts (needs <= 0.50), shallower in both halves: {halves}")
        print("   -> " + ("FAVORS GOLD" if (dd_gain >= 1 and cost <= 0.5 and halves) else "FAVORS TREASURIES (or neither)"))
    print()

q = (1 + D[["stocks", "bonds", "cash", "gold"]]).resample("QE").prod() - 1
qi = D.infl.resample("QE").last()
cut = q.stocks.quantile(0.10)
w = q[q.stocks <= cut]
print("TEST 22b: worst 10% of stock quarters, average return per quarter (%)")
for lab, m in [("inflation > 3%", qi[w.index] > 3), ("inflation <= 3%", qi[w.index] <= 3)]:
    s = w[m.values]
    print(f"  {lab:<16} n={len(s):2d}  bonds {s.bonds.mean() * 100:5.1f}  gold {s.gold.mean() * 100:5.1f}  cash {s.cash.mean() * 100:5.1f}   gold beat bonds in {(s.gold > s.bonds).mean() * 100:.0f}%")
print("\n  Monthly correlations: gold-stocks {:.2f}, gold-bonds {:.2f}, bonds-stocks {:.2f}".format(
    D.gold.corr(D.stocks), D.gold.corr(D.bonds), D.bonds.corr(D.stocks)))
print("  Gold-bonds correlation when Trigger 2 is on: {:.2f}; off: {:.2f}".format(
    D.gold[t2 == 1].corr(D.bonds[t2 == 1]), D.gold[t2 == 0].corr(D.bonds[t2 == 0])))

# ---- Test 23: crisis replay ----
gld = None
try:
    import yfinance as yf
    px = yf.download("GLD", start="2004-10-01", interval="1mo", auto_adjust=True, progress=False)["Close"]
    px = px.squeeze()
    px.index = pd.to_datetime(px.index).tz_localize(None) + pd.offsets.MonthEnd(0)
    gld = px.pct_change()
except Exception as e:
    print("GLD download failed:", e)

episodes = [("2001-02 dot-com bear", "2000-09", "2002-09"), ("2008 financial crisis", "2007-11", "2009-03"),
            ("2020 Covid crash", "2020-01", "2020-06"), ("2022 inflation selloff", "2022-01", "2022-12")]
print("\nTEST 23: crisis replay (monthly %, gold = World Bank monthly average; GLD = ETF month-end price)")
tot_down = tot_ok = 0
for name, a, b in episodes:
    e = D.loc[a:b, ["stocks", "bonds", "cash", "gold"]].copy()
    e["GLD"] = gld.reindex(e.index) if gld is not None else np.nan
    print(f"\n  {name} ({a} to {b})")
    print("   month      stocks  bonds   cash   gold    GLD")
    for d, r in e.iterrows():
        g = "    n/a" if pd.isna(r.GLD) else f"{r.GLD * 100:7.1f}"
        print(f"   {d.strftime('%Y-%m')}  {r.stocks * 100:7.1f}{r.bonds * 100:7.1f}{r.cash * 100:7.1f}{r.gold * 100:7.1f}{g}")
    cum = (1 + e).prod() - 1
    print("   total   " + "".join(f"{cum[c] * 100:7.1f}" if not pd.isna(cum[c]) and e[c].notna().all() else "    n/a" for c in ["stocks", "bonds", "cash", "gold", "GLD"]))
    down = e[e.stocks < 0]
    gsrc = down.GLD if down.GLD.notna().all() else down.gold
    ok = (gsrc >= 0).sum()
    tot_down += len(down); tot_ok += ok
    print(f"   stock-down months: {len(down)}; gold ({'GLD' if down.GLD.notna().all() else 'average price'}) flat or up in {ok}; bonds up in {(down.bonds >= 0).sum()}")
print(f"\n  All four episodes: gold flat or up in {tot_ok} of {tot_down} stock-down months ({tot_ok / tot_down * 100:.0f}%)")
print("   -> " + ("FAVORS GOLD" if tot_ok > tot_down / 2 else "DOES NOT FAVOR GOLD"))
