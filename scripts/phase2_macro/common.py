# Shared data loaders and helpers for Tests 27-32 (Phase 2, version 2 data).
# Run every script from the repo root. data_check.py (Test 31) must run first: it builds data/phase2_macro/v2_monthly.csv.
import io
import os
import zipfile
import urllib.request
import warnings
import numpy as np
import pandas as pd

warnings.simplefilter("ignore")
DATA = "data/phase2_macro"
KF = "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/"
WB_URL = "https://thedocs.worldbank.org/en/doc/74e8be41ceb20fa0da750cda2f6b9e4e-0050012026/related/CMO-Historical-Data-Monthly.xlsx"
WB_PATH = f"{DATA}/CMO-Historical-Data-Monthly.xlsx"
JST_PATH = f"{DATA}/JSTdatasetR6.xlsx"
V2_PATH = f"{DATA}/v2_monthly.csv"


def get_url(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    return urllib.request.urlopen(req, timeout=60).read()


def french(name, daily=False):
    """Ken French Data Library CSV: first block (value-weighted returns), in percent."""
    z = zipfile.ZipFile(io.BytesIO(get_url(KF + name + "_CSV.zip")))
    lines = z.read(z.namelist()[0]).decode("latin-1").splitlines()
    n = 8 if daily else 6
    rows, started = [], False
    for line in lines:
        parts = [p.strip() for p in line.split(",")]
        if len(parts[0]) == n and parts[0].isdigit():
            started = True
            rows.append(parts)
        elif started:
            break
    d = pd.DataFrame(rows)
    idx = pd.to_datetime(d[0], format="%Y%m%d" if daily else "%Y%m")
    d.index = idx if daily else idx + pd.offsets.MonthEnd(0)
    return d.drop(columns=0).astype(float)


def month_end(s):
    s = s.copy()
    s.index = pd.DatetimeIndex(s.index) + pd.offsets.MonthEnd(0)
    return s


_fred = None
def fred():
    global _fred
    if _fred is None:
        from dotenv import load_dotenv
        from fredapi import Fred
        load_dotenv()
        _fred = Fred(api_key=os.getenv("FRED_API_KEY"))
    return _fred


def yf_close(tickers, start, interval="1mo"):
    """Adjusted closes (dividends reinvested). Monthly bars are labeled by month; we move them to month-end."""
    import yfinance as yf
    px = yf.download(tickers, start=start, interval=interval, auto_adjust=True, progress=False)["Close"]
    if isinstance(px, pd.Series):
        px = px.to_frame(tickers if isinstance(tickers, str) else tickers[0])
    px.index = pd.to_datetime(px.index).tz_localize(None)
    if interval == "1mo":
        px.index = px.index + pd.offsets.MonthEnd(0)
    return px


def par_duration(y):
    y = y.where(y.abs() > 1e-4, 1e-4)
    return (1 - (1 + y / 2) ** -20) / y


def wb_gold():
    """World Bank Pink Sheet gold, monthly AVERAGE price in USD, indexed at month-end."""
    if not os.path.exists(WB_PATH):
        with open(WB_PATH, "wb") as f:
            f.write(get_url(WB_URL))
    xl = pd.ExcelFile(WB_PATH)
    sheet = [s for s in xl.sheet_names if "monthly" in s.lower() and "price" in s.lower()][0]
    raw = pd.read_excel(WB_PATH, sheet_name=sheet, header=None).fillna("")
    col0 = raw.iloc[:, 0].astype(str).str.strip()
    mask = col0.str.match(r"^\d{4}M\d{2}$")
    first = mask[mask].index[0]
    hdr = [r for r in range(first - 1, max(-1, first - 12), -1)
           if raw.iloc[r].astype(str).str.strip().str.lower().str.startswith("gold").any()][0]
    gcol = [i for i, v in enumerate(raw.iloc[hdr].astype(str).str.strip()) if v.lower().startswith("gold")][0]
    vals = pd.to_numeric(raw.loc[mask, raw.columns[gcol]].replace("", np.nan), errors="coerce")
    idx = pd.to_datetime(col0[mask].str.replace("M", "-") + "-01") + pd.offsets.MonthEnd(0)
    return pd.Series(vals.values, index=pd.DatetimeIndex(idx.values)).dropna()


RT_DETAILS = []   # one row per first release, for checking the real-time series (Test 31c diagnostics)


def realtime_core_pce():
    """Core PCE year-over-year inflation as it was first published (ALFRED), indexed by the month it was released
    (the decision month). For each release date, FRED is asked for that single vintage with units=pc1, so the
    year-over-year change is computed inside one vintage and a rebasing of the price index (e.g. December 2003) cannot
    mix old-base and new-base numbers. About 330 small requests, paced under FRED's limit of 120 a minute."""
    import json
    import time
    from dotenv import load_dotenv
    load_dotenv()
    key = os.getenv("FRED_API_KEY")
    base = "https://api.stlouisfed.org/fred"
    def call(path):
        try:
            return json.loads(get_url(f"{base}/{path}&file_type=json&api_key={key}"))
        except Exception as e:
            body = ""
            if hasattr(e, "read"):
                try:
                    body = e.read().decode("utf-8", "replace")[:300]
                except Exception:
                    pass
            print(f"  ALFRED request failed: {type(e).__name__}: {e} {body}".replace(key or "<no key>", "<key>"))
            return None
    vd = call("series/vintagedates?series_id=PCEPILFE&realtime_start=1995-01-01")
    if not vd:
        return None
    vintages = [v for v in vd.get("vintage_dates", []) if v >= "1999-01-01"]
    print(f"  ALFRED: {len(vintages)} release dates; downloading each (about {len(vintages) * 0.55 / 60:.0f} minutes)")
    out = {}
    for n, v in enumerate(vintages):
        r = call(f"series/observations?series_id=PCEPILFE&units=pc1&realtime_start={v}&realtime_end={v}&sort_order=desc&limit=1")
        time.sleep(0.55)
        if not r or not r.get("observations"):
            continue
        o = r["observations"][0]
        d, rel = pd.Timestamp(o["date"]), pd.Timestamp(v)
        try:
            val = float(o["value"])
        except ValueError:
            continue
        if d not in out and 0 < (rel - d).days <= 120:      # first vintage that contains month d
            out[d] = (rel, val)
            RT_DETAILS.append({"obs": d, "released": rel, "yoy": val})
        if (n + 1) % 100 == 0:
            print(f"    {n + 1} of {len(vintages)}")
    if not out:
        return None
    s = pd.Series({rel: val for rel, val in out.values()}).sort_index()
    s.index = pd.DatetimeIndex(s.index) + pd.offsets.MonthEnd(0)
    return s.groupby(level=0).last()


def t1_states(known, up=3.25, down=3.0, hold=3):
    """Trigger 1: on after `hold` months above `up`, off after `hold` months below `down`. `known` = what was known."""
    vals = np.asarray(known, dtype=float)
    on, out = False, []
    for i in range(len(vals)):
        w = vals[max(0, i - hold + 1): i + 1]
        if len(w) == hold and not np.isnan(w).any():
            if not on and (w > up).all():
                on = True
            elif on and (w < down).all():
                on = False
        out.append(on)
    return np.array(out, dtype=float)


def load_v2():
    if not os.path.exists(V2_PATH):
        raise SystemExit(f"{V2_PATH} not found: run scripts/phase2_macro/data_check.py first.")
    return pd.read_csv(V2_PATH, index_col=0, parse_dates=True)


def final_port(d, f1, s=0.55, b=0.40, g=0.05, gold_col="gold", bond_col="bonds"):
    """Final portfolio: stocks / Treasuries / gold; Trigger 1 trims half the bonds into cash."""
    f1 = np.asarray(f1, dtype=float)
    return (s * d.stocks.values + b * (1 - 0.5 * f1) * d[bond_col].values + b * 0.5 * f1 * d.cash.values
            + g * d[gold_col].values)


def max_dd(r):
    w = np.cumprod(1 + np.asarray(r, dtype=float))
    return (w / np.maximum.accumulate(w) - 1).min()


def ann(r, per=12):
    r = np.asarray(r, dtype=float)
    return np.prod(1 + r) ** (per / len(r)) - 1


def worst12(r):
    return (pd.Series(np.asarray(r, dtype=float)).add(1).rolling(12).apply(np.prod, raw=True) - 1).min()


def real(r, infl):
    return (1 + np.asarray(r, dtype=float)) / (1 + np.asarray(infl, dtype=float)) - 1


def stats(r, per=12):
    r = np.asarray(r, dtype=float)
    return {"ann_ret_%": round(ann(r, per) * 100, 2), "vol_%": round(r.std() * np.sqrt(per) * 100, 1),
            "max_dd_%": round(max_dd(r) * 100, 1)}


def boot_mean(x, rng, n=3000):
    x = np.asarray(x, dtype=float)
    return np.percentile([rng.choice(x, len(x)).mean() for _ in range(n)], [2.5, 97.5])
