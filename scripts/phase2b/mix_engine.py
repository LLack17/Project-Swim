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


def ann(r, ppy=12):
    """Annualized return; ppy = periods per year (12 monthly, 1 annual)."""
    _check(r)
    return float((1 + r).prod() ** (ppy / len(r)) - 1)


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


def mix_bar(cand, base, need_dd=0.03, need_uw=12, cost=0.003, ppy=12):
    """2B-H bar: the candidate cuts the worst after-inflation loss by `need_dd`+ AND the longest time underwater
    by `need_uw`+ periods (12 months, or 1 year for annual data), and costs at most `cost` a year.
    Both series are after-inflation returns on the same dates."""
    if not cand.index.equals(base.index):
        raise ValueError("candidate and base must cover the same periods")
    out = {"dd": max_dd(cand), "dd_base": max_dd(base), "uw": longest_underwater(cand),
           "uw_base": longest_underwater(base), "cost": ann(base, ppy) - ann(cand, ppy)}
    out["dd_cut"] = out["dd"] - out["dd_base"]
    out["uw_cut"] = out["uw_base"] - out["uw"]
    out["pass"] = bool(out["dd_cut"] >= need_dd - EPS and out["uw_cut"] >= need_uw and out["cost"] <= cost + EPS)
    return out


def pick_best(results):
    """Among passing candidates {name: result with 'pass', 'dd_cut', 'cost'}: the biggest cut in worst loss,
    then the lower cost. None if nothing passes."""
    ok = [(-r["dd_cut"], r["cost"], k) for k, r in results.items() if r["pass"]]
    return min(ok)[2] if ok else None


def gold_signal(real_level, hist_start="1975-01", min_months=60, top=0.80):
    """Valuation view: hold gold in month t only if its after-inflation price at the prior month-end is below
    the `top` percentile of its history from `hist_start` to that month-end. Held until `min_months` of history
    exist. Returns a boolean Series on real_level's index (True = hold)."""
    lv = real_level.dropna()
    held = pd.Series(True, index=lv.index)
    h0 = pd.Timestamp(hist_start) + pd.offsets.MonthEnd(0)
    for k in range(1, len(lv)):
        prev_t = lv.index[k - 1]
        hist = lv[h0:prev_t]
        if len(hist) >= min_months:
            held.iloc[k] = bool((hist < hist.iloc[-1]).mean() < top)
    return held


def port_switch(R, w_on, w_off, on):
    """Monthly-rebalanced portfolio whose target weights are w_on in months where `on` is True, else w_off."""
    a, b = port(R, w_on), port(R, w_off)
    on = on.reindex(R.index)
    if on.isna().any():
        raise ValueError("switch signal missing for some months")
    return a.where(on.astype(bool), b)


# ---------------- 2B-B warning signs ----------------
def expanding_flag(x, side="top", frac=0.20, min_hist=20):
    """Signal 'on' in year t if x_t is above the (1-frac) quantile (side='top') or below the frac quantile
    (side='bottom') of the SAME series' earlier values (years before t, at least `min_hist` of them).
    Returns a float Series: 1.0 on, 0.0 off, NaN when x_t is missing or history is too short."""
    x = x.sort_index()
    out = pd.Series(np.nan, index=x.index)
    vals = x.values
    for k in range(len(x)):
        if np.isnan(vals[k]):
            continue
        hist = vals[:k][~np.isnan(vals[:k])]
        if len(hist) < min_hist:
            continue
        if side == "top":
            out.iloc[k] = float(vals[k] > np.quantile(hist, 1 - frac))
        elif side == "bottom":
            out.iloc[k] = float(vals[k] < np.quantile(hist, frac))
        else:
            raise ValueError("side must be 'top' or 'bottom'")
    return out


def crash_ahead(real_ret, fall=0.30, horizon=3):
    """Year t is followed by a crash if the real total-return index falls `fall` or more below its year-t level
    at some year-end in t+1..t+horizon. real_ret: annual real returns indexed by integer year (return OF that
    year). NaN if any of those years is missing."""
    r = real_ret.sort_index()
    years = r.index
    out = pd.Series(np.nan, index=years)
    for t in years:
        nxt = [t + h for h in range(1, horizon + 1)]
        if not all(y in r.index for y in nxt) or r.loc[nxt].isna().any():
            continue
        path = np.cumprod(1 + r.loc[nxt].values)
        out.loc[t] = float(path.min() <= 1 - fall + EPS)
    return out


def odds(on, crash):
    """Pooled crash rates when a signal is on vs off. on, crash: aligned Series of 0/1 (NaN rows dropped)."""
    d = pd.concat({"on": on, "crash": crash}, axis=1, sort=True).dropna()
    n_on, n_off = int((d.on == 1).sum()), int((d.on == 0).sum())
    hits = int(((d.on == 1) & (d.crash == 1)).sum())
    r_on = hits / n_on if n_on else np.nan
    r_off = ((d.on == 0) & (d.crash == 1)).sum() / n_off if n_off else np.nan
    ratio = np.inf if (r_off == 0 and r_on > 0) else (r_on / r_off if r_off else np.nan)
    return {"n_on": n_on, "n_off": n_off, "hits": hits, "rate_on": r_on, "rate_off": r_off, "ratio": ratio}


def shuffle_blocks(seq, rng, block=5):
    """Cut seq into consecutive `block`-long pieces (the last may be shorter) and return them in random order."""
    blocks = [seq[i:i + block] for i in range(0, len(seq), block)]
    order = rng.permutation(len(blocks))
    return np.concatenate([blocks[k] for k in order])


def block_shuffle_p(panel, n=1000, block=5, seed=0):
    """Luck check. panel: DataFrame with columns country, on, crash (0/1 or NaN), one row per year of the
    checked window for every country (full grid, missing values kept in place), in year order. Each country's
    'on' sequence is cut into consecutive `block`-year blocks from the window's first year; the blocks are
    shuffled and the pooled ratio recomputed (rows with a missing value are left out of the odds only).
    Returns the share of shuffles whose ratio >= the real ratio."""
    rng = np.random.default_rng(seed)
    real_ratio = odds(panel.on, panel.crash)["ratio"]
    if np.isnan(real_ratio):
        return np.nan
    groups = [(g.on.values, g.crash.values) for _, g in panel.groupby("country", sort=True)]
    count = 0
    for _ in range(n):
        ons, crs = [], []
        for on_, cr_ in groups:
            ons.append(shuffle_blocks(on_, rng, block))
            crs.append(cr_)
        ratio = odds(pd.Series(np.concatenate(ons)), pd.Series(np.concatenate(crs)))["ratio"]
        count += bool(ratio >= real_ratio) if not np.isnan(ratio) else 0
    return count / n


def signal_rule(o, p, need_ratio=2.0, need_hits=5, need_p=0.10):
    """2B-B pass: crash rate when on >= need_ratio x rate when off, at least need_hits on-years followed by a
    crash, and luck-check p below need_p."""
    return bool(o["ratio"] >= need_ratio - EPS and o["hits"] >= need_hits and p < need_p)


# ---------------- 2B-D non-US stocks ----------------
def home_vs_abroad(eq, fx, infl, home_w=2 / 3):
    """eq: local-currency stock returns (years x countries); fx: local currency per USD (same shape);
    infl: inflation (same shape). For each home country: home-only real returns and the mix of `home_w` home
    stocks plus the rest split equally across the other countries, converted to home currency unhedged,
    rebalanced yearly. Returns {country: (home_real, mix_real)} from the SECOND row on (the first row only
    supplies the starting exchange rate). Inputs must have no missing values after the first row."""
    if not (eq.index.equals(fx.index) and eq.index.equals(infl.index)):
        raise ValueError("eq, fx and infl must share the same years")
    for nm, d in [("eq", eq.iloc[1:]), ("fx", fx), ("infl", infl.iloc[1:])]:
        if d.isna().any().any():
            raise ValueError(f"{nm} has missing values")
    fxg = fx / fx.shift(1)                                  # growth in local units per USD
    out = {}
    for h in eq.columns:
        others = [c for c in eq.columns if c != h]
        conv = (1 + eq[others]).mul(fxg[h], axis=0).div(fxg[others]) - 1   # foreign return in home currency
        mix_n = home_w * eq[h] + (1 - home_w) * conv.mean(axis=1)
        home_r = ((1 + eq[h]) / (1 + infl[h]) - 1).iloc[1:]
        mix_r = ((1 + mix_n) / (1 + infl[h]) - 1).iloc[1:]
        out[h] = (home_r, mix_r)
    return out


# ---------------- managed-futures live-fund check ----------------
def fund_rule(fund_r, index_r, need_corr=0.7, max_lag=0.01, min_months=60):
    """Live fund vs the index: eligible with at least `min_months` months; passes if monthly returns correlate
    `need_corr` or more AND the fund's annual return is at most `max_lag` below the index's (same months)."""
    d = pd.concat({"f": fund_r, "i": index_r}, axis=1, sort=True).dropna()
    if len(d):
        contiguous(d, "fund sample")
    out = {"n": len(d), "start": d.index[0] if len(d) else None, "end": d.index[-1] if len(d) else None}
    out["eligible"] = len(d) >= min_months
    if not out["eligible"]:
        out.update(corr=np.nan, lag=np.nan, pass_=False)
        return out
    out["corr"] = float(d.f.corr(d.i))
    out["lag"] = ann(d.i) - ann(d.f)
    out["pass_"] = bool(out["corr"] >= need_corr - EPS and out["lag"] <= max_lag + EPS)
    return out


def fund_choice(results):
    """{fund: fund_rule result} -> (weight, fund): 10% with the passing fund of highest correlation; otherwise 5%
    with the eligible fund of highest correlation (None if no fund is eligible)."""
    passing = {k: r for k, r in results.items() if r["pass_"]}
    if passing:
        return 0.10, max(passing, key=lambda k: passing[k]["corr"])
    elig = {k: r for k, r in results.items() if r["eligible"]}
    return 0.05, (max(elig, key=lambda k: elig[k]["corr"]) if elig else None)
