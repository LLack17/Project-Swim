import os
from dotenv import load_dotenv
from fredapi import Fred

load_dotenv()
fred = Fred(api_key=os.getenv("FRED_API_KEY"))

core = fred.get_series("PCEPILFE")          # Core PCE price index (monthly)
yoy = core.pct_change(12) * 100             # year-over-year % inflation
chg_3m = yoy - yoy.shift(3)                 # change in that rate vs 3 months ago

print(yoy.tail(8).round(2))
print(chg_3m.tail(8).round(2))
print("2022 look-back:")
print(yoy["2021-01":"2022-12"].round(2))