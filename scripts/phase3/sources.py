# Network helpers for Phase 3: FMP (paid Starter plan during the screen month), SEC EDGAR (free) and Yahoo prices.
# Keys and contact details come from .env (git-ignored): FMP_API_KEY, SEC_USER_AGENT ("Project Swim <your email>").
# Every FMP and SEC response is cached under data/phase3/raw/ (git-ignored), so a rerun does not pull again and the
# exact data behind the results is kept.
import hashlib
import json
import os
import time
import requests
from dotenv import load_dotenv

load_dotenv()
RAW = "data/phase3/raw"
_last = [0.0]


def _cache_path(kind, key):
    h = hashlib.sha1(key.encode()).hexdigest()[:16]
    return os.path.join(RAW, kind, f"{h}.json")


def _get(url, params=None, headers=None, kind="misc", min_gap=0.25, tries=5, expect_list=False, cache_tag=""):
    key = cache_tag + url + "?" + "&".join(f"{k}={v}" for k, v in sorted((params or {}).items()) if k != "apikey")
    path = _cache_path(kind, key)
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    for k in range(tries):
        wait = min_gap - (time.time() - _last[0])
        if wait > 0:
            time.sleep(wait)
        _last[0] = time.time()
        try:
            r = requests.get(url, params=params, headers=headers, timeout=60)
        except requests.RequestException as e:
            if k == tries - 1:
                raise RuntimeError(f"{kind}: network error ({type(e).__name__})") from None
            time.sleep(2 ** k)
            continue
        if r.status_code in (429, 500, 502, 503, 504):
            time.sleep(2 ** k)
            continue
        if r.status_code != 200:
            raise RuntimeError(f"{kind}: HTTP {r.status_code} for {url.split('?')[0]}")
        data = r.json()
        if isinstance(data, dict) and ("Error Message" in data or "error" in data):
            raise RuntimeError(f"{kind}: refused: {str(data.get('Error Message') or data.get('error'))[:200]}")
        if expect_list and not isinstance(data, list):
            raise RuntimeError(f"{kind}: expected a list, got {type(data).__name__}; not cached")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            json.dump(data, f)
        return data
    raise RuntimeError(f"{kind}: gave up after {tries} tries ({url.split('?')[0]})")


def fmp(endpoint, cache_tag="", **params):
    """FMP stable API; every endpoint used here returns a list. Errors are raised and never cached."""
    key = os.getenv("FMP_API_KEY")
    if not key:
        raise SystemExit("FMP_API_KEY missing from .env")
    return _get(f"https://financialmodelingprep.com/stable/{endpoint}", {**params, "apikey": key}, kind=f"fmp_{endpoint}",
                expect_list=True, cache_tag=cache_tag)


def sec(url):
    ua = os.getenv("SEC_USER_AGENT")
    if not ua or "@" not in ua:
        raise SystemExit('SEC_USER_AGENT missing from .env: add a line like SEC_USER_AGENT="Project Swim you@example.com"')
    return _get(url, headers={"User-Agent": ua, "Accept-Encoding": "gzip, deflate"}, kind="sec", min_gap=0.15)


def sec_ciks():
    d = sec("https://www.sec.gov/files/company_tickers.json")
    return {v["ticker"].upper(): int(v["cik_str"]) for v in d.values()}


def sec_facts(cik):
    return sec(f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json")


def _yahoo_batch(batch, period):
    import pandas as pd
    import yfinance as yf
    px = yf.download(batch, period=period, interval="1d", auto_adjust=True, progress=False, group_by="ticker",
                     threads=True)
    out = {}
    for s in batch:
        try:
            d = px[s] if isinstance(px.columns, pd.MultiIndex) else px
            d = d[["Close", "Volume"]].rename(columns={"Close": "close", "Volume": "volume"}).dropna(subset=["close"])
            if len(d):
                out[s] = d
        except KeyError:
            continue
    return out


def yahoo_prices(symbols, run_date, period="15mo"):
    """Daily adjusted close and volume: {symbol: DataFrame(close, volume)}. Cached per run date in
    data/phase3/raw/yahoo/<run_date>/ so a rerun uses the same prices; symbols that fail are retried once."""
    import pandas as pd
    folder = os.path.join(RAW, "yahoo", str(run_date))
    os.makedirs(folder, exist_ok=True)
    out, todo = {}, []
    for s in symbols:
        f = os.path.join(folder, f"{s}.csv")
        if os.path.exists(f):
            out[s] = pd.read_csv(f, index_col=0, parse_dates=True)
        else:
            todo.append(s)
    for attempt in range(2):
        got = {}
        for i in range(0, len(todo), 100):
            got.update(_yahoo_batch(todo[i:i + 100], period))
        for s, d in got.items():
            d.to_csv(os.path.join(folder, f"{s}.csv"))
        out.update(got)
        todo = [s for s in todo if s not in got]
        if not todo:
            break
        time.sleep(5)
    return out
