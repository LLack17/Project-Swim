import os
import numpy as np
import pandas as pd
from dotenv import load_dotenv
from fredapi import Fred

load_dotenv()
fred = Fred(api_key=os.getenv("FRED_API_KEY"))

# Quarter-end 10Y yield -> approximate quarterly total return
y = fred.get_series("GS10").resample("QE").last() / 100
y_prev = y.shift(1)
dur = (1 - (1 + y_prev / 2) ** -20) / y_prev     # modified duration of a 10Y par bond
bond = (y_prev / 4 - dur * (y - y_prev)).dropna()
bond.name = "Bond10Y"

reg = pd.read_csv("data/regimes_smoothed.csv", index_col=0, parse_dates=True)["q"]

def report(df, title):
    g = df.groupby("q")["Bond10Y"]
    out = pd.DataFrame({
        "avg_ann_%": (g.mean() * 400).round(1),
        "std_err_%": (g.std() / g.count() ** 0.5 * 400).round(1),
        "hit_rate_%": (g.apply(lambda s: (s > 0).mean()) * 100).round(0),
        "quarters": g.count(),
    })
    print(f"\n{title}")
    print(out)
    print("All quarters:", round(df["Bond10Y"].mean() * 400, 1))
    vals, labs = df["Bond10Y"].values, df["q"].values
    def spread(l):
        m = pd.Series(vals).groupby(l).mean()
        return m.max() - m.min()
    real = spread(labs)
    rng = np.random.default_rng(0)
    p = np.mean([spread(rng.permutation(labs)) >= real for _ in range(5000)])
    print(f"Shuffle test: {p:.1%} of random label shuffles give a spread this big")
    return out

same = pd.concat([bond, reg], axis=1, join="inner")
nxt = pd.concat([bond, reg.shift(1).rename("q")], axis=1, join="inner").dropna()

report(same, "BONDS, SAME QUARTER (descriptive)").to_csv("data/bond_returns_same.csv")
report(nxt, "BONDS, NEXT QUARTER (predictive)").to_csv("data/bond_returns_next.csv")
