import os
import urllib.request
import numpy as np
import pandas as pd

URL = "https://www.macrohistory.net/app/download/9834512569/JSTdatasetR6.xlsx?t=1763503850"
PATH = "data/phase2_macro/JSTdatasetR6.xlsx"
if not os.path.exists(PATH):
    print("Downloading the JST Macrohistory database (free, non-commercial use)...")
    req = urllib.request.Request(URL, headers={"User-Agent": "Mozilla/5.0"})
    with open(PATH, "wb") as f:
        f.write(urllib.request.urlopen(req).read())
raw = pd.read_excel(PATH)

need = ["country", "year", "cpi", "eq_tr", "bond_tr", "bill_rate"]
missing = [c for c in need if c not in raw.columns]
if missing:
    print("Missing columns:", missing)
    print("Available columns:", list(raw.columns))
    raise SystemExit

d = raw[need].sort_values(["country", "year"]).copy()
scale_r = 0.01 if d.eq_tr.abs().median() > 1 else 1.0
scale_b = 0.01 if d.bill_rate.abs().median() > 1 else 1.0
d["stocks"] = d.eq_tr * scale_r
d["bonds"] = d.bond_tr * scale_r
d["cash"] = d.bill_rate * scale_b
d["infl"] = d.groupby("country").cpi.pct_change() * 100
d["infl_lag"] = d.groupby("country").infl.shift(1)
print(f"Loaded {len(d)} country-years, {d.country.nunique()} countries, {int(d.year.min())} to {int(d.year.max())}")
print(f"Return scale factor {scale_r}, bill-rate scale factor {scale_b} (1.0 means values were already fractions)")

rng = np.random.default_rng(0)

def analyze(y0, y1, label):
    s = d[(d.year >= y0) & (d.year <= y1)].dropna(subset=["stocks", "bonds", "infl_lag", "infl"]).copy()
    s["s"] = s.stocks - s.groupby("country").stocks.transform("mean")
    s["b"] = s.bonds - s.groupby("country").bonds.transform("mean")
    for c in ["s", "b"]:
        lo, hi = s[c].quantile([0.01, 0.99])
        s[c] = s[c].clip(lo, hi)
    s = s.reset_index(drop=True)
    n = len(s)
    print("\n" + "=" * 70)
    print(f"{label}: {y0}-{y1}, {n} country-years, {s.country.nunique()} countries")
    x, yb, il, ic = s.s.values, s.b.values, s.infl_lag.values, s.infl.values

    years = np.array(sorted(s.year.unique()))
    by_year = {y: np.where(s.year.values == y)[0] for y in years}
    blk = 5
    boots = []
    for _ in range(500):
        ix = []
        for _k in range(int(np.ceil(len(years) / blk))):
            st = int(rng.integers(0, max(1, len(years) - blk + 1)))
            for y in years[st:st + blk]:
                ix.append(by_year[y])
        boots.append(np.concatenate(ix))
    allix = np.arange(n)

    def gc(ix, infl, lo, hi):
        m = (infl[ix] >= lo) & (infl[ix] < hi)
        if m.sum() < 8:
            return np.nan
        return np.corrcoef(x[ix][m], yb[ix][m])[0, 1]

    print("\n  Stock-bond correlation by LAGGED inflation band (pooled, country-demeaned; year-block bootstrap ranges):")
    for lo, hi, name in [(-np.inf, 2, "below 2%"), (2, 3, "2% to 3%"), (3, 4, "3% to 4%"), (4, 6, "4% to 6%"), (6, np.inf, "6% and above")]:
        obs = gc(allix, il, lo, hi)
        cnt = int(((il >= lo) & (il < hi)).sum())
        bs = [gc(ix, il, lo, hi) for ix in boots]
        ci = np.nanpercentile(bs, [2.5, 97.5]) if np.isfinite(bs).any() else (np.nan, np.nan)
        print(f"    {name:<14} corr {obs:5.2f}   n={cnt:4d}   95% CI [{ci[0]:5.2f}, {ci[1]:5.2f}]")

    def diff(ix, infl):
        return gc(ix, infl, 3, np.inf) - gc(ix, infl, -np.inf, 3)
    for lab, arr in [("lagged inflation (known in advance)", il), ("same-year inflation", ic)]:
        obs = diff(allix, arr)
        bs = [diff(ix, arr) for ix in boots]
        ci = np.nanpercentile(bs, [2.5, 97.5])
        print(f"  High (>=3%) minus low (<3%) correlation using {lab}: {obs:5.2f}, 95% CI [{ci[0]:5.2f}, {ci[1]:5.2f}]")

    rows = []
    for c, g in s.groupby("country"):
        hi_m, lo_m = g.infl_lag >= 3, g.infl_lag < 3
        if hi_m.sum() >= 10 and lo_m.sum() >= 10:
            ch = g.s[hi_m].corr(g.b[hi_m])
            cl = g.s[lo_m].corr(g.b[lo_m])
            rows.append((c, int(hi_m.sum()), int(lo_m.sum()), ch, cl, ch - cl))
    if rows:
        t = pd.DataFrame(rows, columns=["country", "n_high", "n_low", "corr_high", "corr_low", "diff"]).round(2)
        print(f"\n  By country (needs 10+ years in each group): correlation higher in the high-inflation group in {(t['diff'] > 0).sum()} of {len(t)} countries")
        print(t.sort_values("diff", ascending=False).to_string(index=False))

    cut = s.stocks.quantile(0.10)
    w = s[s.stocks <= cut]
    print(f"\n  Worst 10% of stock years (stocks <= {cut * 100:.1f}%), {len(w)} country-years: bonds and cash by lagged inflation")
    for lab, m in [("lagged inflation >= 3%", w.infl_lag >= 3), ("lagged inflation < 3%", w.infl_lag < 3)]:
        g = w[m]
        if len(g) == 0:
            continue
        cb = ((g.cash > g.bonds).mean() * 100) if g.cash.notna().any() else np.nan
        print(f"    {lab:<24} n={len(g):3d}  avg bond return {g.bonds.mean() * 100:5.1f}%  bonds positive {((g.bonds > 0).mean() * 100):3.0f}%  avg cash {g.cash.mean() * 100:4.1f}%  cash beat bonds {cb:3.0f}%")

analyze(1950, 2020, "PRIMARY: post-war sample")
analyze(1870, 1949, "SECONDARY: pre-war and gold-standard era (wars, thin inflation data)")
print("\nData: Jorda-Schularick-Taylor Macrohistory Database, R6. Cite: Jorda, Schularick, Taylor (2017) NBER Macro Annual; returns: Jorda, Knoll, Kuvshinov, Schularick, Taylor (2019) QJE.")
