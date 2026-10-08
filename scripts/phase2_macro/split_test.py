# Test 24: the stock / Treasury / gold split, with a concentrated equity sleeve.
# Run from the repo root:  python scripts/phase2_macro/split_test.py > data/phase2_macro/split_test_results.txt
# Without Trigger 2:      python scripts/phase2_macro/split_test.py --no-t2 > data/phase2_macro/split_test_no_t2_results.txt
#
# Splits (stocks / Treasuries / gold): 60/35/5, 57/38/5, 55/40/5, 50/45/5. All run with Triggers 1 and 2
# (Trigger 1 trims half of the base bond weight into cash; Trigger 2 moves 10 points from stocks, to cash while
# Trigger 1 is on). Gold is a static 5%. 1975 to 2026, monthly rebalancing.
# Equity sleeve: (a) the whole market (Ken French), and (b) concentration proxy: N random Ken French industry
# portfolios, equal-weighted, 1,000 draws, N = 4, 6, 8. Industries are themselves diversified, so this
# UNDERSTATES the risk of holding N single stocks; treat it as a lower bound.
#
# Pre-committed decision rule: the reference risk is the plain index 60/40 with no triggers and no gold (the
# portfolio every earlier test was built around). Choose the split with the MOST stocks whose median max
# drawdown, with a 6-industry equity sleeve, is no deeper than that reference. If none qualifies, choose 50/45/5.
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


# --no-t2: rerun with Trigger 2 off (watch-only after Test 25). Same splits, same decision rule.
import sys
if "--no-t2" in sys.argv:
    t2 = np.zeros_like(t2)
    print("RUN WITHOUT TRIGGER 2 (watch-only after Test 25)\n")

def max_dd(r):
    w = np.cumprod(1 + np.asarray(r))
    return (w / np.maximum.accumulate(w) - 1).min()

def stats(r):
    r = pd.Series(r)
    return {"ann_ret_%": round(((1 + r).prod() ** (12 / len(r)) - 1) * 100, 2),
            "vol_%": round(r.std() * np.sqrt(12) * 100, 1),
            "max_dd_%": round(max_dd(r) * 100, 1),
            "worst_12m_%": round(((1 + r).rolling(12).apply(np.prod, raw=True) - 1).min() * 100, 1)}

def port(eq, s, b, g=0.05, triggers=True):
    """eq = equity sleeve returns (array), s/b = base stock/bond weights."""
    f1, f2 = (t1, t2) if triggers else (np.zeros(len(idx)), np.zeros(len(idx)))
    ws = s - 0.10 * f2
    wb = b - 0.5 * b * f1 + 0.10 * f2 * (1 - f1)
    wc = 0.5 * b * f1 + 0.10 * f2 * f1
    return ws * eq + wb * D.bonds.values + wc * D.cash.values + g * D.gold.values

# ---- industries (concentration proxy) ----
ind = french("49_Industry_Portfolios") / 100
ind = ind.reindex(idx)
ind = ind.loc[:, (ind > -0.99).all() & ind.notna().all()]
print(f"Industries with full data over the sample: {ind.shape[1]}\n")
IND = ind.values

ref = port(D.stocks.values, 0.6, 0.4, g=0.0, triggers=False)
ref_s = stats(ref)
print(f"Reference: plain index 60/40, no triggers, no gold: return {ref_s['ann_ret_%']}%, max drawdown {ref_s['max_dd_%']}%\n")

splits = [(0.60, 0.35), (0.57, 0.38), (0.55, 0.40), (0.50, 0.45)]
name = lambda s, b: f"{int(round(s*100))}/{int(round(b*100))}/5"

print("TEST 24a: equity sleeve = whole market, with Trigger 1" + (" (Trigger 2 off)" if "--no-t2" in sys.argv else " and Trigger 2"))
print(pd.DataFrame({name(s, b): stats(port(D.stocks.values, s, b)) for s, b in splits}).T.to_string())

rng = np.random.default_rng(24)
print("\nTEST 24b: equity sleeve = N random industries (lower bound on single-stock concentration), 1,000 draws")
print("  median [10th percentile = bad draw] of return and max drawdown; also the equity sleeve's own volatility")
res = {}
for N in (4, 6, 8):
    draws = [rng.choice(IND.shape[1], N, replace=False) for _ in range(1000)]
    eqs = [IND[:, d].mean(axis=1) for d in draws]
    vol_eq = np.median([e.std() * np.sqrt(12) * 100 for e in eqs])
    print(f"\n  N = {N} (median equity-sleeve volatility {vol_eq:.1f}% vs market {D.stocks.std() * np.sqrt(12) * 100:.1f}%)")
    for s, b in splits:
        out = np.array([[((1 + port(e, s, b)).prod() ** (12 / len(idx)) - 1) * 100, max_dd(port(e, s, b)) * 100] for e in eqs])
        res[(N, name(s, b))] = out
        print(f"   {name(s, b):<8} return {np.median(out[:, 0]):5.2f}% [{np.percentile(out[:, 0], 10):5.2f}]   max drawdown {np.median(out[:, 1]):6.1f}% [{np.percentile(out[:, 1], 10):6.1f}]")

print("\nDECISION (rule fixed before running): most stocks with median max drawdown (N = 6) no deeper than the reference "
      f"({ref_s['max_dd_%']}%)")
pick = "50/45/5"
for s, b in splits:
    md = np.median(res[(6, name(s, b))][:, 1])
    ok = md >= ref_s["max_dd_%"]
    print(f"  {name(s, b):<8} median max drawdown {md:6.1f}%  -> {'qualifies' if ok else 'too deep'}")
for s, b in splits:
    if np.median(res[(6, name(s, b))][:, 1]) >= ref_s["max_dd_%"]:
        pick = name(s, b)
        break
print(f"  -> base split: {pick}")
