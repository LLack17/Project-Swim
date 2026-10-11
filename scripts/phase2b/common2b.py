# Shared loaders for Phase 2B case studies. Run scripts from the repo root.
# Hand-downloaded files (git-ignored) live in data/phase2b/manual/; run scripts/phase2b/data_access.py first.
import datetime
import sys
import numpy as np
import pandas as pd

sys.path.insert(0, "scripts/phase2_macro")
from common import french, fred, load_v2, wb_gold  # noqa: E402,F401

MANUAL = "data/phase2b/manual"
OUT = "data/phase2b"


def me(s):
    s = s.copy()
    s.index = pd.DatetimeIndex(s.index) + pd.offsets.MonthEnd(0)
    return s


def fred_m(sid, how="last"):
    s = fred().get_series(sid)
    s.index = pd.DatetimeIndex(s.index)
    return me(getattr(s.resample("ME"), how)())


def bond_ret(yield_pct, years):
    """Monthly return of a par bond with constant maturity, from month-end yields (percent)."""
    y = yield_pct / 100
    yp = y.shift(1)
    ypc = yp.where(yp.abs() > 1e-4, 1e-4)        # avoid dividing by zero (rows with a missing yield are dropped below)
    dur = (1 - (1 + ypc / 2) ** (-2 * years)) / ypc
    return (yp / 12 - dur * (y - yp)).dropna()     # months with a missing yield on either side are dropped


def shiller_cape():
    d = pd.read_excel(f"{MANUAL}/ie_data.xls", sheet_name="Data", header=None)
    hdr = d.index[d.iloc[:, 0].astype(str).str.strip() == "Date"][0]
    d = pd.read_excel(f"{MANUAL}/ie_data.xls", sheet_name="Data", header=hdr)
    d = d[pd.to_numeric(d["Date"], errors="coerce").notna()]
    yr = d["Date"].astype(float)
    idx = pd.to_datetime(dict(year=yr.astype(int), month=((yr - yr.astype(int)) * 100).round().astype(int).clip(1, 12),
                              day=1)) + pd.offsets.MonthEnd(0)
    col = [c for c in d.columns if str(c).strip().upper() == "CAPE"][0]
    return pd.Series(pd.to_numeric(d[col], errors="coerce").values, index=idx).dropna()


def q_lag(s, quarters=1):
    """Quarterly series known `quarters` quarters after the quarter ends, filled forward to month-ends."""
    s = me(s.resample("QE").last())
    s.index = s.index + pd.offsets.MonthEnd(3 * quarters)
    return s.resample("ME").last().ffill()


def tbill_bey(discount_pct):
    """T-bill discount rate (TB3MS) to bond-equivalent yield, so it compares with Treasury note yields."""
    d = discount_pct / 100
    return 100 * 365 * d / (360 - 91 * d)


def _date_table(path, sheet):
    raw = pd.read_excel(path, sheet_name=sheet, header=None)
    is_date = raw.iloc[:, 0].apply(lambda v: isinstance(v, datetime.datetime) or
                                   (isinstance(v, str) and pd.notna(pd.to_datetime(v, errors="coerce", format="%m/%d/%Y"))))
    first = is_date.idxmax()
    t = raw.loc[is_date].copy()
    t.columns = ["Date"] + [str(c) for c in raw.iloc[first - 1, 1:]]
    t.index = pd.to_datetime(t["Date"].astype(str), errors="coerce") + pd.offsets.MonthEnd(0)
    if t.index.isna().any() or t.index.duplicated().any():
        raise ValueError(f"{path}: unreadable or duplicate dates")
    return t.drop(columns="Date").apply(pd.to_numeric, errors="coerce")


def aqr_century():
    """AQR Century of Factor Premia: monthly excess returns (decimal), 1926 on."""
    path = f"{MANUAL}/Century-of-Factor-Premia-Monthly.xlsx"
    return _date_table(path, pd.ExcelFile(path).sheet_names[0])


def aqr_tsmom():
    return _date_table(f"{MANUAL}/Time-Series-Momentum-Factors-Monthly.xlsx", "TSMOM Factors")


def nareit():
    """FTSE Nareit All Equity REITs total return (column 22), from 1972. Excludes mortgage REITs, which are
    lenders rather than property owners."""
    raw = pd.read_excel(f"{MANUAL}/MonthlyHistoricalReturns.xls", sheet_name="Index Data", header=None)
    assert "Equity" in str(raw.iloc[5, 22]), "Nareit file layout changed: check the All Equity REITs column"
    s = pd.Series(pd.to_numeric(raw[22], errors="coerce").values / 100, index=pd.to_datetime(raw[0], errors="coerce"))
    s = me(s[s.index.notna()].dropna())
    assert s.abs().max() < 0.5, "Nareit column does not look like monthly returns"
    return s


def drawdown(w):
    return w / w.cummax() - 1
