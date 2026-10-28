# Pull everything useful from the FMP Starter plan for the research list, while the subscription is active.
# Usage, from the repo root (needs FMP_API_KEY in .env):
#   python scripts/phase3/fmp_research_pull.py                 (the 13 picks of 2026-10-28)
#   python scripts/phase3/fmp_research_pull.py AAPL MSFT ...   (any other list)
# Each endpoint is tried once per company; ones not in the plan are reported, not fatal. Nothing is guessed:
# data/phase3/fmp_endpoint_check.txt lists which endpoints worked (no data in it, safe to commit).
# Data goes to private/fmp_research/ (git-ignored; FMP's terms limit redistribution): one CSV per company and
# endpoint, a peer comparison table, market series (Treasury rates; VTI, IEF, SPY, AQMIX prices) for the
# portfolio and options work. Raw responses are also cached in data/phase3/raw/ (git-ignored), dated by run.
import datetime
import os
import sys
import pandas as pd

sys.path.insert(0, "scripts/phase3")
import sources as D  # noqa: E402

PICKS = ["EHC", "GILD", "INGR", "CL", "BYD", "GNTX", "ITW", "AOS", "VNT", "EEFT", "CARG", "EOG", "SHW"]
RUN = datetime.date.today()
START = str(RUN.replace(year=RUN.year - 5))
OUT = "private/fmp_research"
BASE = "https://financialmodelingprep.com/stable/"

COMPANY = [  # (name for the file, endpoint, params; "{s}" = the symbol)
    ("profile", "profile", {"symbol": "{s}"}),
    ("income_annual", "income-statement", {"symbol": "{s}", "period": "annual", "limit": 10}),
    ("balance_annual", "balance-sheet-statement", {"symbol": "{s}", "period": "annual", "limit": 10}),
    ("cashflow_annual", "cash-flow-statement", {"symbol": "{s}", "period": "annual", "limit": 10}),
    ("income_quarter", "income-statement", {"symbol": "{s}", "period": "quarter", "limit": 20}),
    ("balance_quarter", "balance-sheet-statement", {"symbol": "{s}", "period": "quarter", "limit": 20}),
    ("cashflow_quarter", "cash-flow-statement", {"symbol": "{s}", "period": "quarter", "limit": 20}),
    ("key_metrics", "key-metrics", {"symbol": "{s}", "period": "annual", "limit": 10}),
    ("ratios", "ratios", {"symbol": "{s}", "period": "annual", "limit": 10}),
    ("key_metrics_ttm", "key-metrics-ttm", {"symbol": "{s}"}),
    ("ratios_ttm", "ratios-ttm", {"symbol": "{s}"}),
    ("growth", "financial-growth", {"symbol": "{s}", "period": "annual", "limit": 10}),
    ("enterprise_values", "enterprise-values", {"symbol": "{s}", "period": "annual", "limit": 10}),
    ("segments_product", "revenue-product-segmentation", {"symbol": "{s}", "period": "annual"}),
    ("segments_geographic", "revenue-geographic-segmentation", {"symbol": "{s}", "period": "annual"}),
    ("analyst_estimates", "analyst-estimates", {"symbol": "{s}", "period": "annual", "limit": 10}),
    ("price_target_consensus", "price-target-consensus", {"symbol": "{s}"}),
    ("price_target_summary", "price-target-summary", {"symbol": "{s}"}),
    ("grades_consensus", "grades-consensus", {"symbol": "{s}"}),
    ("earnings", "earnings", {"symbol": "{s}", "limit": 20}),
    ("dividends", "dividends", {"symbol": "{s}"}),
    ("insider_stats", "insider-trading/statistics", {"symbol": "{s}"}),
    ("peers", "stock-peers", {"symbol": "{s}"}),
    ("shares_float", "shares-float", {"symbol": "{s}"}),
    ("employees", "employee-count", {"symbol": "{s}"}),
    ("dcf", "discounted-cash-flow", {"symbol": "{s}"}),
    ("prices", "historical-price-eod/full", {"symbol": "{s}", "from": START}),
    ("news", "news/stock", {"symbols": "{s}", "limit": 50}),
]
PEER = ["profile", "key_metrics_ttm", "ratios_ttm"]
MARKET = [("treasury_rates", "treasury-rates", {"from": START, "to": str(RUN)})] + \
         [(f"prices_{x}", "historical-price-eod/full", {"symbol": x, "from": START}) for x in ["VTI", "IEF", "SPY", "AQMIX"]]


def as_rows(data):
    """FMP answers are a list of records, a single record, or (prices) a dict holding a list."""
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for k in ("historical", "data"):
            if isinstance(data.get(k), list):
                return data[k]
        return [data]
    return []


def fetch(endpoint, params):
    key = os.getenv("FMP_API_KEY")
    if not key:
        raise SystemExit("FMP_API_KEY missing from .env")
    return D._get(BASE + endpoint, {**params, "apikey": key}, kind="fmp_" + endpoint.replace("/", "_"),
                  cache_tag=f"research{RUN}")


def pull(sym, specs, get, folder):
    """Try each (name, endpoint, params) for one symbol; save non-empty answers as CSV. Returns {name: status}."""
    os.makedirs(folder, exist_ok=True)
    status = {}
    for name, ep, params in specs:
        p = {k: (v.format(s=sym) if isinstance(v, str) else v) for k, v in params.items()}
        try:
            rows = as_rows(get(ep, p))
        except (RuntimeError, ValueError) as e:
            status[name] = "not available: " + str(e).split(": ", 1)[-1][:80]
            continue
        if not rows:
            status[name] = "empty"
            continue
        pd.json_normalize(rows).to_csv(os.path.join(folder, f"{name}.csv"), index=False)
        status[name] = f"ok ({len(rows)} rows)"
    return status


def self_test():
    """Made-up answers: list, single record, dict with a list, refusal, empty."""
    import tempfile
    answers = {"a": [{"x": 1}, {"x": 2}], "b": {"x": 3}, "c": {"symbol": "Q", "historical": [{"close": 1.0}]}, "e": []}

    def fake(ep, p):
        if ep == "d":
            raise RuntimeError("fmp_d: HTTP 402 for https://x")
        return answers[ep]
    with tempfile.TemporaryDirectory() as t:
        st = pull("Q", [(k, k, {"symbol": "{s}"}) for k in "abcde"], fake, t)
        assert st["a"] == "ok (2 rows)" and st["b"] == "ok (1 rows)" and st["c"] == "ok (1 rows)", st
        assert st["d"].startswith("not available") and st["e"] == "empty", st
        assert pd.read_csv(os.path.join(t, "c.csv")).close.iloc[0] == 1.0
    print("self-test passed")


if __name__ == "__main__":
    if sys.argv[1:] == ["--self-test"]:
        self_test()
        raise SystemExit(0)
    picks = [t.upper() for t in sys.argv[1:]] or PICKS
    report = {}
    for s in picks:
        print(f"{s} ...", flush=True)
        report[s] = pull(s, COMPANY, fetch, f"{OUT}/{s}")
    peers = set()
    for s in picks:
        f = f"{OUT}/{s}/peers.csv"
        if os.path.exists(f):
            peers |= set(pd.read_csv(f).get("symbol", pd.Series(dtype=str)).dropna().astype(str))
    peers -= set(picks)
    print(f"peers: {len(peers)} ...", flush=True)
    for s in sorted(peers):
        report[s] = pull(s, [c for c in COMPANY if c[0] in PEER], fetch, f"{OUT}/peers/{s}")
    report["MARKET"] = pull("", MARKET, fetch, f"{OUT}/market")
    # peer comparison table: TTM metrics of each pick next to its peers
    rows = []
    for s in picks:
        f = f"{OUT}/{s}/peers.csv"
        group = [s] + (list(pd.read_csv(f).symbol.dropna().astype(str)) if os.path.exists(f) and "symbol" in pd.read_csv(f) else [])
        for g in group:
            d = f"{OUT}/{s}" if g == s else f"{OUT}/peers/{g}"
            rec = {"pick": s, "symbol": g}
            for n in ["key_metrics_ttm", "ratios_ttm"]:
                if os.path.exists(f"{d}/{n}.csv"):
                    rec.update(pd.read_csv(f"{d}/{n}.csv").iloc[0].to_dict())
            rows.append(rec)
    if rows:
        pd.DataFrame(rows).to_csv(f"{OUT}/peer_comparison.csv", index=False)
    # endpoint check (no data): which endpoints the plan allowed
    lines = [f"FMP endpoint check, run {RUN} (Starter plan): status per endpoint for the research list", ""]
    names = [c[0] for c in COMPANY]
    for n in names:
        ok = sum(report[s].get(n, "").startswith("ok") for s in picks)
        why = {report[s][n] for s in picks if n in report[s] and not report[s][n].startswith("ok")}
        lines.append(f"  {n:24s} ok for {ok:2d} of {len(picks)}" + (f"   ({'; '.join(sorted(why))[:120]})" if why else ""))
    lines.append("")
    lines += [f"  market {k:17s} {v}" for k, v in report["MARKET"].items()]
    lines.append(f"\nPeers pulled: {len(peers)}. Data saved in {OUT}/ (git-ignored).")
    os.makedirs("data/phase3", exist_ok=True)
    with open("data/phase3/fmp_endpoint_check.txt", "w") as fh:
        fh.write("\n".join(lines) + "\n")
    print("\n".join(lines))
