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
comm = 0.5 * indices[en_col[0]].pct_change() + 0.5 * indices[ne_col[0]].pct_change()

# ---- inflation-linked bonds: synthetic from the 10-year real yield (FRED DFII10, 2003+) ----
real_y = fred.get_series("DFII10").dropna().resample("ME").mean() / 100
ryp = real_y.shift(1)
real_ret = ryp / 12 - par_duration(ryp) * (real_y - ryp)
cpi_m = month_end(fred.get_series("CPIAUCSL")).pct_change()
tips = ((1 + real_ret) * (1 + cpi_m) - 1)["2003-02":]

assets = {
    "Gold spot": gold["1975":],
    "Commodities spot": comm,
    "Gold+Comm spot": (0.5 * gold + 0.5 * comm)["1975":],
    "TIPS synthetic": tips,
}

# ---- investable ETFs via yfinance (free, no key): GLD, DBC, TIP ----
try:
    import yfinance as yf
    px = yf.download(["GLD", "DBC", "TIP"], start="2003-06-01", interval="1mo", auto_adjust=True, progress=False)["Close"]
    px.index = pd.to_datetime(px.index).tz_localize(None) + pd.offsets.MonthEnd(0)
    er = px.pct_change()
    assets["GLD ETF"] = er["GLD"].dropna()
    assets["DBC ETF"] = er["DBC"].dropna()
    assets["TIP ETF"] = er["TIP"].dropna()
    assets["GLD+DBC ETFs"] = (0.5 * er["GLD"] + 0.5 * er["DBC"]).dropna()
except Exception as e:
    print("ETF data skipped (", e, "). Run: pip install yfinance")

# ======================= ANALYSIS =======================
def max_dd(r):
    w = np.cumprod(1 + np.asarray(r))
    return (w / np.maximum.accumulate(w) - 1).min()

def worst12(r):
    return (pd.Series(1 + np.asarray(r)).rolling(12).apply(np.prod, raw=True) - 1).min()

def stats(r):
    r = pd.Series(r)
    return {"ret_%": round(((1 + r).prod() ** (12 / len(r)) - 1) * 100, 1),
            "vol_%": round(r.std() * np.sqrt(12) * 100, 1),
            "maxDD_%": round(max_dd(r.values) * 100, 1),
            "worst12_%": round(worst12(r.values) * 100, 1)}

def year_ret(r, y):
    x = r[str(y)]
    return ((1 + x).prod() - 1) * 100 if len(x) == 12 else np.nan

def qret(r):
    q = (1 + r).resample("QE").prod() - 1
    return q[r.resample("QE").count() == 3]

# Trigger 1 state (act above 3.25%, restore below 3.0%, 3 months each, 2-month data lag)
known = M.infl.shift(2)
st_full = np.zeros(len(M), dtype=bool)
on_ = False
for i in range(len(M)):
    w = known.iloc[max(0, i - 2): i + 1]
    if len(w) == 3 and w.notna().all():
        if not on_ and (w > 3.25).all():
            on_ = True
        elif on_ and (w < 3.0).all():
            on_ = False
    st_full[i] = on_
st_full = pd.Series(st_full, index=M.index)

verdicts = {}
for name, a in assets.items():
    D = pd.DataFrame({"a": a, "s": M.stocks, "b": M.bonds, "c": M.cash, "infl": M.infl}).dropna()
    D = D.join(st_full.rename("st"))
    print("\n" + "=" * 78)
    print(f"{name}: {D.index[0].date()} to {D.index[-1].date()} ({len(D)} months, {len(D) / 12:.0f} years)")
    base = 0.6 * D.s + 0.4 * D.b
    short = len(D) < 15 * 12

    # 1) Scorecard on quarterly data
    Q = pd.DataFrame({k: qret(D[k]) for k in ["a", "s", "b", "c"]})
    Q["infl"] = D.infl.resample("QE").last()
    Q = Q.dropna()
    hi, lo = Q[Q.infl > 3], Q[Q.infl <= 3]
    cor_h = hi.a.corr(hi.s) if len(hi) > 5 else np.nan
    cor_l = lo.a.corr(lo.s) if len(lo) > 5 else np.nan
    print(f"  Standalone: return {stats(D.a)['ret_%']}%, vol {stats(D.a)['vol_%']}%.  Correlation with stocks (quarterly): inflation>3% {cor_h:.2f} (n={len(hi)}), <=3% {cor_l:.2f} (n={len(lo)})")
    cut = Q.s.quantile(0.10)
    w_ = Q[Q.s <= cut]
    crit_a = None
    for lab, g in [("worst stock quarters, inflation > 3%", w_[w_.infl > 3]), ("worst stock quarters, inflation <= 3%", w_[w_.infl <= 3])]:
        if len(g) == 0:
            continue
        print(f"  {lab}: n={len(g):2d}  asset {g.a.mean() * 100:5.1f}% (positive {(g.a > 0).mean() * 100:3.0f}%)  bonds {g.b.mean() * 100:5.1f}%  cash {g.c.mean() * 100:4.1f}%  asset beat cash {(g.a > g.c).mean() * 100:3.0f}%")
        if lab.endswith("> 3%"):
            crit_a = (len(g) >= 5) and (g.a.mean() > g.c.mean()) and ((g.a > 0).mean() > 0.5)

    # 2) Static 10% sleeve funded proportionally from stocks and bonds
    def sleeve(x, w=0.10):
        return (1 - w) * base + w * x
    mid = D.index[len(D) // 2]
    rows = {"Baseline 60/40": stats(base), "+10% cash": stats(sleeve(D.c)), f"+10% {name[:22]}": stats(sleeve(D.a))}
    t = pd.DataFrame(rows).T
    t["2022_%"] = [year_ret(base, 2022), year_ret(sleeve(D.c), 2022), year_ret(sleeve(D.a), 2022)]
    print("\n  Static 10% sleeve (taken proportionally from stocks and bonds):")
    print(t.round(1).to_string())
    s_a, s_c = sleeve(D.a), sleeve(D.c)
    dd_b, dd_c, dd_a = max_dd(base.values), max_dd(s_c.values), max_dd(s_a.values)
    ret_cost = stats(base)["ret_%"] - stats(s_a)["ret_%"]
    crit_b = (dd_a > dd_b) and (dd_a > dd_c) and (ret_cost <= 0.5)
    h1 = max_dd(s_a[:mid].values) - max_dd(base[:mid].values)
    h2 = max_dd(s_a[mid:].values) - max_dd(base[mid:].values)
    crit_c = (h1 > 0) and (h2 > 0)
    print(f"  Drawdown improvement vs baseline by half: first half {h1 * 100:+.1f} pts, second half {h2 * 100:+.1f} pts")

    # 3) Trigger 1 destination: when the inflation rule is on, where do the trimmed bonds go?
    st = D.st.astype(float)
    def dest(x):
        return 0.6 * D.s + 0.4 * (1 - 0.5 * st) * D.b + 0.4 * 0.5 * st * x
    rows2 = {"Baseline 60/40": stats(base), "Trim to cash": stats(dest(D.c)), f"Trim to {name[:20]}": stats(dest(D.a))}
    t2 = pd.DataFrame(rows2).T
    t2["2022_%"] = [year_ret(base, 2022), year_ret(dest(D.c), 2022), year_ret(dest(D.a), 2022)]
    print(f"\n  Trigger 1 destination (rule on {st.mean() * 100:.0f}% of this sample's months):")
    print(t2.round(1).to_string())

    verdicts[name] = (crit_a, crit_b, crit_c, short)

print("\n" + "=" * 78)
print("PRE-COMMITTED VERDICTS (an asset earns a place in the defensive sleeve only if all three pass)")
print("  (a) in the worst stock quarters with inflation > 3%, beats cash and is positive in most (needs n >= 5)")
print("  (b) a 10% sleeve gives a shallower max drawdown than both the baseline and a 10% cash sleeve, costing at most 0.5 pt/yr of return")
print("  (c) the drawdown improvement vs baseline appears in both halves of the sample")
for name, (a_, b_, c_, short) in verdicts.items():
    f = lambda x: "n/a" if x is None else ("PASS" if x else "FAIL")
    all_ok = bool(a_) and bool(b_) and bool(c_)
    tag = "EARNS A PLACE" if all_ok and not short else ("passes, but SHORT SAMPLE: case study only" if all_ok else "not supported")
    print(f"  {name:<40} (a) {f(a_)}  (b) {f(b_)}  (c) {f(c_)}  -> {tag}")
