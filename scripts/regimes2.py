import os
import pandas as pd
from dotenv import load_dotenv
from fredapi import Fred

load_dotenv()
fred = Fred(api_key=os.getenv("FRED_API_KEY"))

gdp = fred.get_series("A191RL1Q225SBEA").resample("QE").mean()
core = fred.get_series("PCEPILFE")
infl = (core.pct_change(12) * 100).resample("QE").mean()
base = pd.DataFrame({"growth": gdp, "inflation": infl}).dropna()

def label(gu, iu):
    return pd.Series(
        [(1 if not i else 2) if g else (3 if i else 4) for g, i in zip(gu, iu)],
        index=gu.index)

# Raw: vs last quarter
raw = base.copy()
raw["q"] = label(raw.growth > raw.growth.shift(1), raw.inflation > raw.inflation.shift(1))

# Smoothed: 4-quarter average growth vs a year ago, inflation vs a year ago
sm = base.copy()
sm["g4"] = sm.growth.rolling(4).mean()
sm["q"] = label(sm.g4 > sm.g4.shift(4), sm.inflation > sm.inflation.shift(4))

for name, d in [("RAW", raw), ("SMOOTHED", sm)]:
    d = d.dropna()["1970":]
    flips = (d.q != d.q.shift()).sum() - 1
    print(f"{name}: {len(d)} quarters, {flips} label changes, avg run length {len(d)/flips:.1f} quarters")
    print(d.q.value_counts().sort_index().to_dict())

sm = sm.dropna()
sm.to_csv("data/regimes_smoothed.csv")
print("\nSmoothed, last 8 quarters:")
print(sm[["growth", "inflation", "q"]].tail(8).round(2))
print("\nSmoothed, 2021-22:")
print(sm.loc["2021Q1":"2022Q4", ["growth", "inflation", "q"]].round(2))