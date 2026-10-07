import os
import pandas as pd
from dotenv import load_dotenv
from fredapi import Fred

load_dotenv()
fred = Fred(api_key=os.getenv("FRED_API_KEY"))

# Growth: real GDP growth (quarterly, annualized). Inflation: core PCE YoY.
gdp = fred.get_series("A191RL1Q225SBEA").resample("QE").mean()
core = fred.get_series("PCEPILFE")
infl = (core.pct_change(12) * 100).resample("QE").mean()

df = pd.DataFrame({"growth": gdp, "inflation": infl}).dropna()
df = df["1970":]

# Direction = this quarter vs last quarter (Verdad's original rule)
df["growth_up"] = df["growth"] > df["growth"].shift(1)
df["infl_up"] = df["inflation"] > df["inflation"].shift(1)
df = df.dropna()

def quadrant(r):
    if r.growth_up and not r.infl_up: return 1   # growth up, inflation down
    if r.growth_up and r.infl_up:     return 2   # growth up, inflation up
    if not r.growth_up and r.infl_up: return 3   # growth down, inflation up
    return 4                                      # growth down, inflation down

df["quadrant"] = df.apply(quadrant, axis=1)

os.makedirs("data", exist_ok=True)
df.to_csv("data/phase2_macro/regimes.csv")

print("Quarters per quadrant:")
print(df["quadrant"].value_counts().sort_index())
print("\nLast 8 quarters:")
print(df.tail(8).round(2))
for name, a, b in [("2008-09", "2008Q1", "2009Q4"), ("2020", "2020Q1", "2020Q4"), ("2021-22", "2021Q1", "2022Q4")]:
    print(f"\n{name}:")
    print(df.loc[a:b, ["growth", "inflation", "quadrant"]].round(2))