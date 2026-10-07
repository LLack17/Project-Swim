import io
import zipfile
import urllib.request
import pandas as pd

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
            break  # first block = monthly returns only
    df = pd.DataFrame(rows)
    df.index = pd.to_datetime(df[0], format="%Y%m") + pd.offsets.MonthEnd(0)
    return df.drop(columns=0).astype(float)

fac = french("F-F_Research_Data_Factors")   # cols: Mkt-RF, SMB, HML, RF
six = french("6_Portfolios_2x3")            # 3rd col = small value

monthly = pd.DataFrame({
    "Market": (fac[1] + fac[4]) / 100,
    "SmallValue": six[3] / 100,
    "Cash": fac[4] / 100,
})

# Compound monthly into quarterly, drop incomplete quarters
quarterly = (1 + monthly).resample("QE").prod() - 1
full = monthly["Market"].resample("QE").count() == 3
quarterly = quarterly[full]

reg = pd.read_csv("data/phase2_macro/regimes_smoothed.csv", index_col=0, parse_dates=True)["q"]

def table(df, title):
    g = df.groupby("q")[["Market", "SmallValue", "Cash"]]
    out = (g.mean() * 4 * 100).round(1)          # avg annualized % return
    out["quarters"] = g.size()
    print(f"\n{title}")
    print(out)
    print("All quarters:", (df[["Market", "SmallValue", "Cash"]].mean() * 400).round(1).to_dict())
    return out

# Same quarter: what assets did DURING each regime (descriptive)
same = quarterly.join(reg, how="inner")
t1 = table(same, "SAME QUARTER (descriptive: what happened during the regime)")

# Next quarter: label known at end of quarter, applied to the FOLLOWING quarter (tradeable)
nxt = quarterly.join(reg.shift(1).rename("q"), how="inner").dropna()
t2 = table(nxt, "NEXT QUARTER (predictive: trade on the label after it is known)")

t1.to_csv("data/phase2_macro/quadrant_returns_same.csv")
t2.to_csv("data/phase2_macro/quadrant_returns_next.csv")
import numpy as np

print("\n" + "=" * 60)
print("EXTRA STATS: next-quarter Market return by label")
g = nxt.groupby("q")["Market"]
stats = pd.DataFrame({
    "avg_ann_%": (g.mean() * 400).round(1),
    "std_err_ann_%": (g.std() / g.count() ** 0.5 * 400).round(1),
    "hit_rate_%": (g.apply(lambda s: (s > 0).mean()) * 100).round(0),
    "worst_qtr_%": (g.min() * 100).round(1),
    "quarters": g.count(),
})
print(stats)

rng = np.random.default_rng(0)
vals = nxt["Market"].values
labs = nxt["q"].values

def spread(l):
    m = pd.Series(vals).groupby(l).mean()
    return m.max() - m.min()

real = spread(labs)
sims = [spread(rng.permutation(labs)) for _ in range(5000)]
p = np.mean([s >= real for s in sims])
print(f"\nBest-minus-worst quadrant spread (quarterly): {real * 100:.2f}%")
print(f"Share of 5000 label shuffles with a spread this big: {p:.1%}")
