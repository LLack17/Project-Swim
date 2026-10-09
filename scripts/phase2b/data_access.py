# Phase 2B setup: check that every data source the research plan needs can be reached, and how far back it goes.
# Run from the repo root:  python scripts/phase2b/data_access.py
# Files that block scripted downloads (Shiller, AQR, Nareit) can be saved by hand into data/phase2b/manual/;
# that folder is git-ignored because we have not confirmed the right to republish those files.
import os
import sys
import io
import datetime
import requests
import pandas as pd

sys.path.insert(0, "scripts/phase2_macro")
from common import french, fred, yf_close, get_url, JST_PATH  # noqa: E402

OUT = "data/phase2b/data_access_results.txt"
MANUAL = "data/phase2b/manual"
lines = []


def log(s=""):
    print(s)
    lines.append(s)


def span(obj):
    s = obj.dropna(how="all") if isinstance(obj, pd.DataFrame) else obj.dropna()
    return f"{s.index.min():%Y-%m} to {s.index.max():%Y-%m}, {len(s)} rows"


def check(name, fn):
    try:
        log(f"OK    {name}: {fn()}")
    except Exception as e:
        msg = str(e).replace(os.getenv("FRED_API_KEY") or "#", "***").replace(os.getenv("FMP_API_KEY") or "#", "***")
        log(f"FAIL  {name}: {type(e).__name__}: {msg[:160]}")


def from_web_or_manual(urls, fname):
    """Try each URL; if all fail, fall back to a file saved by hand. Returns (bytes, where)."""
    for u in urls:
        try:
            b = get_url(u)
            if len(b) > 10000 and not b[:200].lower().lstrip().startswith(b"<"):
                with open(f"{MANUAL}/{fname}", "wb") as f:
                    f.write(b)
                return b, "downloaded"
        except Exception:
            pass
    p = f"{MANUAL}/{fname}"
    if os.path.exists(p):
        return open(p, "rb").read(), "manual file"
    raise FileNotFoundError(f"download blocked; save the file by hand as {p}")


def excel_sheets(b):
    x = pd.ExcelFile(io.BytesIO(b))
    return x, x.sheet_names


def table_with_date_header(x, sheet):
    """Find the first row whose first cell is a date; the row above it holds the column names."""
    raw = pd.read_excel(x, sheet_name=sheet, header=None)
    is_date = raw.iloc[:, 0].apply(lambda v: isinstance(v, datetime.datetime) or
                                   (isinstance(v, str) and pd.notna(pd.to_datetime(v, errors="coerce", format="%m/%d/%Y"))))
    first = is_date.idxmax()
    if not is_date.any():
        raise ValueError("no date column")
    t = raw.loc[is_date].copy()
    t.columns = ["Date"] + [str(c) for c in raw.iloc[first - 1, 1:]]
    t.index = pd.to_datetime(t["Date"].astype(str), errors="coerce")
    return t.drop(columns="Date")


# --- Shiller (CAPE, long US stock and earnings history) ---
def shiller():
    b, where = from_web_or_manual(
        ["https://img1.wsimg.com/blobby/go/e5e77e0b-59d1-44d9-ab25-4763ac982e53/downloads/ie_data.xls",
         "http://www.econ.yale.edu/~shiller/data/ie_data.xls"], "ie_data.xls")
    x, _ = excel_sheets(b)
    raw = pd.read_excel(x, sheet_name="Data", header=None)
    hdr = raw.index[raw.iloc[:, 0].astype(str).str.strip() == "Date"][0]
    d = pd.read_excel(x, sheet_name="Data", header=hdr)
    d = d[pd.to_numeric(d["Date"], errors="coerce").notna()]
    yr = d["Date"].astype(float)
    idx = pd.to_datetime(dict(year=yr.astype(int), month=((yr - yr.astype(int)) * 100).round().astype(int).clip(1, 12), day=1))
    cape_col = [c for c in d.columns if str(c).strip().upper() == "CAPE"][0]
    cape = pd.Series(pd.to_numeric(d[cape_col], errors="coerce").values, index=idx)
    return f"{where}; CAPE {span(cape)}; latest {cape.dropna().iloc[-1]:.1f}"


# --- AQR trend following (managed-futures proxy) ---
def aqr(fname, url):
    def run():
        b, where = from_web_or_manual([url], fname)
        x, sheets = excel_sheets(b)
        out = [where]
        for sh in sheets[:3]:
            try:
                t = table_with_date_header(x, sh)
                out.append(f"sheet '{sh}': columns {list(t.columns)[:8]}; {span(t)}")
            except Exception:
                out.append(f"sheet '{sh}': no Date table")
        return " | ".join(out)
    return run


# --- Nareit REIT index ---
def nareit():
    b, where = from_web_or_manual(["https://www.reit.com/sites/default/files/returns/MonthlyHistoricalReturns.xls"],
                                  "MonthlyHistoricalReturns.xls")
    x, sheets = excel_sheets(b)
    raw = pd.read_excel(x, sheet_name=sheets[0], header=None)
    dates = pd.to_datetime(raw.iloc[:, 0], errors="coerce").dropna()
    return f"{where}; sheets {sheets[:4]}; dates in first column {dates.min():%Y-%m} to {dates.max():%Y-%m}"


log("Phase 2B data access check")
log("=" * 60)

log("\nWarning signs, policy and macro (FRED)")
FRED_SERIES = {
    "BAA10Y": "corporate credit spread (Baa minus 10Y)",
    "GS10": "10-year Treasury yield",
    "TB3MS": "3-month T-bill",
    "FEDFUNDS": "fed funds rate",
    "CPIAUCSL": "CPI",
    "PCEPILFE": "core PCE",
    "UNRATE": "unemployment",
    "CP": "corporate profits",
    "GDP": "nominal GDP",
    "QUSPAMUSDA": "credit to private non-financial sector (BIS, % of GDP)",
    "USSTHPI": "house prices (FHFA)",
    "CSUSHPINSA": "house prices (Case-Shiller)",
    "BOGZ1FL663067003Q": "margin credit at brokers (margin-debt proxy)",
    "BAA": "Baa corporate yield (spread vs GS10 before 1986)",
    "PPIACO": "producer prices, all commodities",
    "WALCL": "Fed balance sheet",
    "FYFSGDA188S": "federal surplus/deficit, % of GDP",
}
for sid, desc in FRED_SERIES.items():
    check(f"{sid} ({desc})", lambda sid=sid: span(fred().get_series(sid)))

log("\nStock returns, styles and regions (Ken French)")
for name, desc in [("F-F_Research_Data_Factors", "US market and factors"),
                   ("Portfolios_Formed_on_BE-ME", "value vs growth"),
                   ("Portfolios_Formed_on_OP", "profitability (quality)"),
                   ("Portfolios_Formed_on_VAR", "low vs high volatility"),
                   ("49_Industry_Portfolios", "49 industries"),
                   ("Developed_ex_US_3_Factors", "developed markets ex-US"),
                   ("Developed_3_Factors", "developed markets incl. US")]:
    check(f"{name} ({desc})", lambda name=name: span(french(name)))

log("\nFunds and indexes (yfinance)")
for t, desc in [("SHY", "1-3y Treasuries"), ("IEF", "7-10y Treasuries"), ("TLT", "20+y Treasuries"),
                ("VTI", "US total market"), ("EFA", "developed ex-US stocks"), ("VNQ", "REITs"),
                ("DBC", "commodities fund"), ("^SPGSCI", "S&P GSCI commodity index"), ("^N225", "Nikkei 225"),
                ("DBMF", "managed futures ETF"), ("AQMIX", "AQR managed futures fund")]:
    check(f"{t} ({desc})", lambda t=t: span(yf_close(t, "1960-01-01")))

log("\nHand-download candidates")
check("Shiller ie_data.xls (CAPE)", shiller)
check("AQR Time Series Momentum factors", aqr(
    "Time-Series-Momentum-Factors-Monthly.xlsx",
    "https://www.aqr.com/-/media/AQR/Documents/Insights/Data-Sets/Time-Series-Momentum-Factors-Monthly.xlsx"))
check("AQR Century of Factor Premia", aqr(
    "Century-of-Factor-Premia-Monthly.xlsx",
    "https://www.aqr.com/-/media/AQR/Documents/Insights/Data-Sets/Century-of-Factor-Premia-Monthly.xlsx"))
check("FTSE Nareit monthly returns", nareit)

log("\nCross-country and company data")
check("JST Macrohistory (local)", lambda: f"{pd.read_excel(JST_PATH, sheet_name=0).shape[0]} rows, "
      f"{pd.read_excel(JST_PATH, sheet_name=0)['country'].nunique()} countries")


def fmp():
    from dotenv import load_dotenv
    load_dotenv()
    r = requests.get("https://financialmodelingprep.com/stable/income-statement",
                     params={"symbol": "JPM", "limit": 5, "apikey": os.getenv("FMP_API_KEY")}, timeout=30)
    r.raise_for_status()
    j = r.json()
    if not isinstance(j, list) or not j:
        raise ValueError(str(j)[:120])
    return f"JPM income statements: {len(j)} years, earliest {j[-1].get('date')}"


check("FMP fundamentals (free tier)", fmp)

log("\nFRED search: net equity issuance (to pick the right series id)")
check("search", lambda: "; ".join(f"{i}: {t[:70]}" for i, t in
      fred().search("corporate equities net issuance nonfinancial")["title"].head(6).items()))

os.makedirs("data/phase2b", exist_ok=True)
with open(OUT, "w") as f:
    f.write("\n".join(lines) + "\n")
print(f"\nSaved to {OUT}")
