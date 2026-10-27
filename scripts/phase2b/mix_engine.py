# Shared engine for the Phase 2B portfolio-mix tests: inflation protection (2B-A), commodities (2B-I),
# bond length (2B-F) and, later, final mix (2B-H). Pure functions only (no data downloads), so every
# piece can be checked on made-up numbers in test_mix_engine.py. Rules: docs/phase2b_research_plan.md.
import numpy as np
import pandas as pd

# Crash windows: identical to scripts/phase2b/case_study.py (a test checks they stay identical).
WINDOWS = {"1973-74": ("1972-06", "1975-12"), "2000-02": ("1999-06", "2003-06"),
           "2007-09": ("2007-01", "2009-12"), "2022": ("2021-06", "2023-06")}
INFLATION_CRASHES = ["1973-74", "2022"]
GROWTH_CRASHES = ["2000-02", "2007-09"]
HALVES = [("1970", "1997"), ("1998", "2026")]
EPS = 1e-12


def chg(s, n=1):
    """n-period change, written out because pandas pct_change() can fill gaps forward."""
    return s / s.shift(n) - 1


def real(r, infl):
    """After-inflation return from a nominal return and the month's inflation (both decimals, same dates)."""
    infl = infl.reindex(r.index)
    if infl.isna().any():
        raise ValueError("inflation missing for some return months")
    return (1 + r) / (1 + infl) - 1


def contiguous(x, name="series"):
    """Raise unless x covers every month between its first and last date (no silent gaps)."""
    if len(x) == 0 or not x.index.equals(pd.date_range(x.index[0], x.index[-1], freq="ME")):
        raise ValueError(f"{name}: missing months inside the sample")
    return x


def fill_index(level):
    """Fill months missing INSIDE a monthly index-level series (e.g. an unpublished CPI month) log-linearly
    between the neighbouring published values. Returns the filled series and the list of filled months.
    Months before the first or after the last published value are not invented."""
    level = level.dropna()
    full = pd.date_range(level.index[0], level.index[-1], freq="ME")
    x = level.reindex(full)
    filled = list(x.index[x.isna()])
    x = np.exp(np.log(x).interpolate(method="linear", limit_area="inside"))
    return x, filled


def quarter_end(s):
    """Values at quarter-end months only (Mar, Jun, Sep, Dec); a quarter whose last month is missing has none."""
    return s[s.index.month % 3 == 0].dropna()


def splice(main_r, standin_r, start, end):
    """Monthly returns from main_r, with months start..end that main_r lacks taken from standin_r. Each series
    is computed from one yield series, so no month mixes two yields."""
    return main_r.combine_first(standin_r[start:end])


def _check(r):
    if len(r) == 0:
        raise ValueError("empty return series")
    if r.isna().any():
        raise ValueError(f"missing returns between {r.index[0]:%Y-%m} and {r.index[-1]:%Y-%m}")


def port(R, w, rebalance="monthly", band=0.05, band_asset=None, return_trades=False):
    """Portfolio monthly returns. R: DataFrame of monthly returns (columns = holdings); w: target weights.
    rebalance: 'monthly' (back to target every month-end), 'yearly' (at each December month-end),
    'band' (at a month-end, only if band_asset's weight is `band` or more away from target), 'never'.
    Every rule starts at the target weights. Trades = number of month-ends where weights were reset."""
    cols = list(w)
    X = R[cols]
    if X.isna().any().any():
        raise ValueError("missing returns in portfolio holdings")
    tw = np.array([w[c] for c in cols], dtype=float)
    if abs(tw.sum() - 1) > 1e-9 or (tw < 0).any():
        raise ValueError("weights must be non-negative and sum to 1")
    out, cur, trades = [], tw.copy(), 0
    for t, row in zip(X.index, X.values):
        r = float(cur @ row)
        out.append(r)
        cur = cur * (1 + row) / (1 + r)                     # weights drift with returns
        if rebalance == "monthly":
            reset = True
        elif rebalance == "yearly":
            reset = t.month == 12
        elif rebalance == "band":
            i = cols.index(band_asset)
            reset = abs(cur[i] - tw[i]) >= band - EPS
        elif rebalance == "never":
            reset = False
        else:
            raise ValueError(f"unknown rebalance rule {rebalance}")
        if reset:
            cur, trades = tw.copy(), trades + (not np.allclose(cur, tw))
    s = pd.Series(out, index=X.index)
    return (s, trades) if return_trades else s


def wealth(r):
    _check(r)
    return (1 + r).cumprod()


def max_dd(r):
    """Worst fall from a high point, counting the starting value (1.0) as the first high point."""
    w = np.concatenate([[1.0], wealth(r).values])
    return float((w / np.maximum.accumulate(w) - 1).min())


def longest_underwater(r):
    """Longest run of consecutive month-ends below the previous high (start value counts as a high)."""
    w = np.concatenate([[1.0], wealth(r).values])
    under = w < np.maximum.accumulate(w) - EPS
    best = run = 0
    for u in under:
        run = run + 1 if u else 0
        best = max(best, run)
    return best


def window_loss(r, name):
    a, b = WINDOWS[name]
    x = r[a:b]
    n_expected = (pd.Period(b, "M") - pd.Period(a, "M")).n + 1
    if len(x) != n_expected:
        raise ValueError(f"window {name}: {len(x)} months of data, needs {n_expected}")
    return max_dd(x)


def ann(r):
    _check(r)
    return float((1 + r).prod() ** (12 / len(r)) - 1)


def qret(r):
    """Quarterly returns from monthly ones; quarters with fewer than 3 months are dropped."""
    q = (1 + r).resample("QE").prod() - 1
    return q[r.resample("QE").count() == 3]


def selloff_quarters(stock_r, infl_q, frac=0.10, hi=3.0):
    """Test 19 definition: the worst tenth of stock quarters in the sample, keeping those where inflation
    (percent, value at quarter-end) was above `hi`."""
    q = qret(contiguous(stock_r.dropna(), "selloff stock sample"))
    worst = q[q <= q.quantile(frac)]
    i = infl_q.reindex(worst.index)
    if i.isna().any():
        raise ValueError("inflation missing for a selloff quarter")
    return worst.index[i > hi]


def test19(a, s, b, c, sel_q, base_w=(0.55, 0.45), halves=HALVES, cost=0.005, slice_w=0.10):
    """Phase 2 Test 19 criteria for one candidate asset `a` (stocks s, bonds b, cash c; all monthly, same
    measure: all before inflation or all after). sel_q = the high-inflation selloff quarters, picked once
    from 1970-on nominal stock returns (selloff_quarters), so both measures and every candidate judge the
    same quarters; only those inside the candidate's months are used. The slice is funded proportionally.
    (a) in high-inflation selloff quarters: n >= 5, average beats cash, positive in more than half;
    (b) the slice's worst drawdown is shallower than both the baseline and the same slice in cash, and
        the baseline's annual return is at most `cost` higher;
    (c) the drawdown improvement vs baseline shows up in each half."""
    D = contiguous(pd.concat({"a": a, "s": s, "b": b, "c": c}, axis=1, sort=True).dropna(), "test19 sample")
    base = base_w[0] * D.s + base_w[1] * D.b
    Q = pd.DataFrame({k: qret(D[k]) for k in ["a", "s", "b", "c"]})
    g = Q.loc[Q.index.intersection(sel_q)]
    sa = (1 - slice_w) * base + slice_w * D.a
    sc = (1 - slice_w) * base + slice_w * D.c
    out = {"start": D.index[0], "end": D.index[-1], "n_q": len(g),
           "q_asset": g.a.mean() if len(g) else np.nan, "q_cash": g.c.mean() if len(g) else np.nan,
           "q_pos": (g.a > 0).mean() if len(g) else np.nan,
           "dd_base": max_dd(base), "dd_slice": max_dd(sa), "dd_cash": max_dd(sc),
           "cost": ann(base) - ann(sa), "halves": []}
    out["a"] = bool(len(g) >= 5 and g.a.mean() > g.c.mean() and (g.a > 0).mean() > 0.5)
    out["b"] = bool(out["dd_slice"] > out["dd_base"] and out["dd_slice"] > out["dd_cash"]
                    and out["cost"] <= cost + EPS)
    ok_c = True
    for h0, h1 in halves:
        if len(base[h0:h1]) == 0:
            raise ValueError(f"no data in half {h0}-{h1}")
        imp = max_dd(sa[h0:h1]) - max_dd(base[h0:h1])
        out["halves"].append((max(h0, f"{D.index[0]:%Y}"), h1, imp))
        ok_c = ok_c and imp > 0
    out["c"] = bool(ok_c)
    out["pass"] = out["a"] and out["b"] and out["c"]
    return out


def crit_commod(cand, base, sel_q, cost=0.005, grow_tol=0.03, halves=HALVES):
    """2B-I criteria (a)-(d) for a candidate vs 55/45; both monthly returns AFTER inflation, same dates.
    Loss = worst drawdown inside a case-study window (negative number; higher = smaller loss)."""
    if not cand.index.equals(base.index):
        raise ValueError("candidate and 55/45 must cover the same months")
    contiguous(cand, "2B-I sample")
    L = {k: (window_loss(cand, k), window_loss(base, k)) for k in WINDOWS}
    qc, qb = qret(cand).reindex(sel_q), qret(base).reindex(sel_q)
    if qc.isna().any() or qb.isna().any() or len(sel_q) == 0:
        raise ValueError("selloff quarters missing from the sample")
    better = qc > qb

    def a_ok(sl=None):
        crashes = [k for k in INFLATION_CRASHES if sl is None or sl[0] <= WINDOWS[k][0][:4] <= sl[1]]
        idx = better.index if sl is None else better[sl[0]:sl[1]].index
        return (all(L[k][0] > L[k][1] for k in crashes) and len(crashes) > 0
                and len(idx) > 0 and better[idx].mean() > 0.5)

    def c_ok(sl=None):
        x, y = (cand, base) if sl is None else (cand[sl[0]:sl[1]], base[sl[0]:sl[1]])
        return ann(y) - ann(x) <= cost + EPS

    out = {"loss": L, "q_better": better.mean(), "q_n": len(better),
           "cost": ann(base) - ann(cand),
           "half_detail": [(h, better[h[0]:h[1]].mean(), len(better[h[0]:h[1]]),
                            ann(base[h[0]:h[1]]) - ann(cand[h[0]:h[1]])) for h in halves]}
    out["a"] = bool(a_ok())
    out["b"] = bool(all(L[k][0] >= L[k][1] - grow_tol - EPS for k in GROWTH_CRASHES))
    out["c"] = bool(c_ok())
    out["d"] = bool(all(a_ok(h) and c_ok(h) for h in halves))
    return out


def crit_long(cand, base, sel_q, cost=0.005):
    """2B-I (e): on 1927-on data (after inflation), the candidate beats 55/45 on average in high-inflation
    selloff quarters and costs at most `cost` a year."""
    if not cand.index.equals(base.index):
        raise ValueError("candidate and 55/45 must cover the same months")
    contiguous(cand, "long sample")
    qc, qb = qret(cand).reindex(sel_q), qret(base).reindex(sel_q)
    if qc.isna().any() or qb.isna().any() or len(sel_q) == 0:
        raise ValueError("selloff quarters missing from the long sample")
    out = {"q_diff": float((qc - qb).mean()), "q_n": len(sel_q), "cost": ann(base) - ann(cand)}
    out["e"] = bool(out["q_diff"] > 0 and out["cost"] <= cost + EPS)
    return out


def pick_weight(res5, res10, pass5, pass10, extra=0.03):
    """5% unless 10% cuts the worse of the two inflation-crash losses by `extra` or more."""
    if pass5 and pass10:
        w5 = min(res5["loss"][k][0] for k in INFLATION_CRASHES)
        w10 = min(res10["loss"][k][0] for k in INFLATION_CRASHES)
        return 10 if w10 - w5 >= extra - EPS else 5
    return 5 if pass5 else (10 if pass10 else None)


def trend_filter(asset_total, cash, fee_m=0.0):
    """Hold the asset only when its past 12-month return over T-bills (to the prior month-end) is positive;
    otherwise hold T-bills. The fee is charged only in months the asset is held."""
    ex = contiguous(((1 + asset_total) / (1 + cash) - 1).dropna(), "trend filter inputs")
    asset_total, cash = asset_total.reindex(ex.index), cash.reindex(ex.index)
    sig = ((1 + ex).rolling(12).apply(np.prod, raw=True) - 1).shift(1) > 0
    valid = ex.rolling(12).count().shift(1) == 12
    held = sig & valid
    r = np.where(held, asset_total - fee_m, cash)
    r = pd.Series(r, index=asset_total.index)
    return r[valid], held[valid]


def trend_proxy(X, vol_window=36, target=0.10):
    """Simple trend-following proxy on excess returns X (columns = asset classes): each month, long an asset
    if its past 12-month excess return is positive, short if negative, sized to `target` annual volatility
    using the past `vol_window` months; equal weight across assets. Uses data to the prior month-end only."""
    mom = ((1 + X).rolling(12).apply(np.prod, raw=True) - 1).shift(1)
    vol = X.rolling(vol_window).std().shift(1) * np.sqrt(12)
    pos = np.sign(mom) * target / vol
    r = (pos * X).mean(axis=1, skipna=False)
    return r.dropna()


def worst(r, names):
    return min(window_loss(r, k) for k in names)


def bond_rule(base_r, alt_r, need=0.01, cost=0.003):
    """2B-F: the alternative cuts the worse growth-crash loss AND the worse inflation-crash loss by `need`
    or more each, and costs at most `cost` a year (both after inflation)."""
    out = {"growth": worst(alt_r, GROWTH_CRASHES) - worst(base_r, GROWTH_CRASHES),
           "infl": worst(alt_r, INFLATION_CRASHES) - worst(base_r, INFLATION_CRASHES),
           "cost": ann(base_r) - ann(alt_r)}
    out["pass"] = bool(out["growth"] >= need - EPS and out["infl"] >= need - EPS and out["cost"] <= cost + EPS)
    return out


def trend_adopt(res_static, res_tf, need=0.02):
    """2B-I second stage: trend filter adopted only if it passes (a)-(e) AND its worse growth-crash loss is
    `need` or more smaller than the static winner's."""
    gs = min(res_static["loss"][k][0] for k in GROWTH_CRASHES)
    gt = min(res_tf["loss"][k][0] for k in GROWTH_CRASHES)
    return bool(res_tf["pass"] and gt - gs >= need - EPS), gs, gt


def gsci_rule(port_broad, port_gsci, need=0.05, cost=0.01):
    """2B-I index type: broad basket unless the GSCI version's 2022 loss is `need`+ smaller and it costs at
    most `cost` a year (same months, after inflation)."""
    if not port_broad.index.equals(port_gsci.index):
        raise ValueError("broad and GSCI portfolios must cover the same months")
    l_b, l_g = window_loss(port_broad, "2022"), window_loss(port_gsci, "2022")
    c = ann(port_broad) - ann(port_gsci)
    return bool(l_g - l_b >= need - EPS and c <= cost + EPS), l_b, l_g, c


def parse_french_csv(text):
    """First block of a Ken French CSV (value-weighted returns), with its column names, as decimals.
    Missing values (-99.99 or -999) become NaN."""
    lines = text.splitlines()
    rows, header = [], None
    for k, line in enumerate(lines):
        parts = [p.strip() for p in line.split(",")]
        if len(parts[0]) == 6 and parts[0].isdigit():
            if header is None:
                j = k - 1
                while j >= 0 and not lines[j].strip():
                    j -= 1
                header = [p.strip() for p in lines[j].split(",")][1:]
            rows.append(parts)
        elif header is not None:
            break
    if not rows:
        raise ValueError("no monthly data rows found")
    if any(len(r) - 1 != len(header) for r in rows):
        raise ValueError("header and data rows have different numbers of columns")
    d = pd.DataFrame([r[1:] for r in rows], columns=header).astype(float)
    d.index = pd.to_datetime([r[0] for r in rows], format="%Y%m") + pd.offsets.MonthEnd(0)
    return d.mask(d <= -99.99) / 100


def style_rule(style_r, mkt_r, need=3, lag=0.01):
    """2B-G: a style passes if its after-inflation loss is smaller than the market's in at least `need` of the
    four case-study crashes AND its full-period annual return is at most `lag` below the market's."""
    if not style_r.index.equals(mkt_r.index):
        raise ValueError("style and market must cover the same months")
    contiguous(style_r, "style sample")
    loss = {k: (window_loss(style_r, k), window_loss(mkt_r, k)) for k in WINDOWS}
    wins = sum(a > b for a, b in loss.values())
    gap = ann(mkt_r) - ann(style_r)
    return {"loss": loss, "wins": wins, "lag": gap, "pass": bool(wins >= need and gap <= lag + EPS)}
