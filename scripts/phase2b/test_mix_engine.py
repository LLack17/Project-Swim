# Known-answer checks for mix_engine.py on made-up numbers (no real market data).
# Usage, from the repo root:  python scripts/phase2b/test_mix_engine.py
import ast
import os
import sys
import numpy as np
import pandas as pd

sys.path.insert(0, "scripts/phase2b")
import mix_engine as E  # noqa: E402

results = []


def check(name, cond):
    results.append((name, bool(cond)))
    print(f"{'ok  ' if cond else 'FAIL'} {name}")


def raises(f):
    try:
        f()
    except (ValueError, KeyError):
        return True
    return False


def idx(start, n):
    return pd.date_range(start, periods=n, freq="ME")


close = lambda a, b, tol=1e-10: abs(a - b) < tol  # noqa: E731

# 1. windows identical to the case-study script
src = "scripts/phase2b/case_study.py"
if os.path.exists(src):
    tree = ast.parse(open(src).read())
    w = [ast.literal_eval(n.value) for n in ast.walk(tree)
         if isinstance(n, ast.Assign) and any(getattr(t, "id", "") == "WINDOWS" for t in n.targets)]
    check("windows match case_study.py", w and w[0] == E.WINDOWS)
else:
    check("windows match case_study.py (file not found)", False)

# 2. portfolio: monthly rebalancing = weighted sum each month
i = idx("2000-01", 3)
R = pd.DataFrame({"x": [0.10, -0.20, 0.05], "y": [0.0, 0.10, 0.02]}, index=i)
p = E.port(R, {"x": 0.6, "y": 0.4})
check("monthly = weighted sum", np.allclose(p.values, [0.06, -0.08, 0.038]))

# 3. never rebalanced = buy and hold
p, tr = E.port(R, {"x": 0.6, "y": 0.4}, "never", return_trades=True)
bh = 0.6 * (1 + R.x).cumprod() + 0.4 * (1 + R.y).cumprod()
check("never = buy and hold", np.allclose((1 + p).cumprod().values, bh.values) and tr == 0)

# 4. yearly: drift through the year, reset only at December
i = pd.date_range("2000-11-30", periods=3, freq="ME")    # Nov, Dec, Jan
R = pd.DataFrame({"x": [1.0, 0.0, 0.0], "y": [0.0, 0.0, 0.0]}, index=i)
p, tr = E.port(R, {"x": 0.5, "y": 0.5}, "yearly", return_trades=True)
# Nov: +50%; weights become 2/3, 1/3; Dec: 0; reset at Dec end; Jan: 0
check("yearly: returns", np.allclose(p.values, [0.5, 0.0, 0.0]) and tr == 1)
R2 = R.copy()
R2.iloc[1] = [0.0, 1.0]          # Dec: y doubles. Without a Nov reset, weights 2/3,1/3 -> return 1/3
p = E.port(R2, {"x": 0.5, "y": 0.5}, "yearly")
check("yearly: no reset in November", close(p.iloc[1], 1 / 3))
R3 = R.copy()
R3.iloc[2] = [0.0, 1.0]          # Jan after Dec reset: weights 1/2 -> return 0.5
check("yearly: reset at December", close(E.port(R3, {"x": 0.5, "y": 0.5}, "yearly").iloc[2], 0.5))

# 5. band: reset only when the band asset is 5+ points off target
i = idx("2000-01", 3)
R = pd.DataFrame({"s": [0.05, 0.25, 0.0], "b": [0.0, 0.0, 0.0]}, index=i)
# after m1: s = .55*1.05/(.55*1.05+.45) = .5620 (1.2 pts off, no trade); after m2 well over 5 pts -> reset
p, tr = E.port(R, {"s": 0.55, "b": 0.45}, "band", band=0.05, band_asset="s", return_trades=True)
w1 = 0.55 * 1.05 / (0.55 * 1.05 + 0.45)
check("band: drift month 2 uses drifted weight", close(p.iloc[1], w1 * 0.25) and tr == 1)
R = pd.DataFrame({"s": [0.01, 0.02, 0.01], "b": [0.0, 0.0, 0.0]}, index=i)   # s weight reaches ~57%
check("band: no trade when inside band", E.port(R, {"s": 0.55, "b": 0.45}, "band", band_asset="s", return_trades=True)[1] == 0)
# exactly at the band edge: s weight 0.60 -> trade
g = (0.60 / 0.40) / (0.55 / 0.45) - 1      # return on s that moves its weight from 55% to exactly 60%
R = pd.DataFrame({"s": [g, 0.0, 0.0], "b": [0.0, 0.0, 0.0]}, index=i)
check("band: trade at exactly 5 points", E.port(R, {"s": 0.55, "b": 0.45}, "band", band_asset="s", return_trades=True)[1] == 1)
check("port: rejects missing returns", raises(lambda: E.port(R.mask(R.index == i[1]), {"s": 0.55, "b": 0.45})))
check("port: rejects weights not summing to 1", raises(lambda: E.port(R, {"s": 0.55, "b": 0.40})))

# 6. drawdowns
i = idx("2000-01", 3)
r = pd.Series([-0.10, 0.05, 0.06], index=i)
check("max_dd counts a first-month loss", close(E.max_dd(r), -0.10))
check("longest underwater = 2 months", E.longest_underwater(r) == 2)
r = pd.Series([0.10, -0.50, 1.0], index=i)
check("max_dd from later high", close(E.max_dd(r), -0.5))
check("max_dd rejects missing", raises(lambda: E.max_dd(pd.Series([0.1, np.nan], index=idx("2000-01", 2)))))

# 7. window loss needs the full window
r = pd.Series(0.0, index=idx("2021-06", 25))
r["2022-03-31"] = -0.2
check("window loss 2022", close(E.window_loss(r, "2022"), -0.2))
check("window loss rejects a short window", raises(lambda: E.window_loss(r.iloc[:-1], "2022")))

# 8. annual return
check("ann: 1% a month", close(E.ann(pd.Series(0.01, index=idx("2000-01", 12))), 1.01 ** 12 - 1))

# 9. quarters
r = pd.Series(0.01, index=pd.date_range("2000-02-29", periods=5, freq="ME"))   # Feb..Jun: Q1 partial
q = E.qret(r)
check("qret drops partial quarter", len(q) == 1 and close(q.iloc[0], 1.01 ** 3 - 1))

# 10. selloff quarters: worst tenth with inflation > 3
n = 40
i = idx("1990-01", 3 * n)
qr = np.linspace(0.05, 0.01, n)
qr[[3, 10, 20, 30]] = [-0.30, -0.25, -0.20, -0.15]     # the 4 worst quarters (= worst tenth of 40)
r = pd.Series(np.repeat((1 + qr) ** (1 / 3) - 1, 3), index=i)
qi = E.qret(r).index
inf = pd.Series(2.0, index=qi)
inf.iloc[[3, 20, 30]] = 4.0
sq = E.selloff_quarters(r, inf)
check("selloff quarters: worst tenth with inflation > 3", list(sq) == [qi[3], qi[20], qi[30]])
check("selloff quarters: exactly the worst tenth (4 of 40) when inflation is always high",
      list(E.selloff_quarters(r, pd.Series(4.0, index=qi))) == [qi[3], qi[10], qi[20], qi[30]])

# 11. Test 19 criteria on a made-up hedge asset
n = 40
i = idx("1990-01", 3 * n)
qs = np.full(n, 0.02)
bad = [2, 9, 15, 22, 31]
qs[bad] = -0.20
toq = lambda q: np.repeat((1 + np.asarray(q)) ** (1 / 3) - 1, 3)  # noqa: E731
s = pd.Series(toq(qs), index=i)
qa = np.full(n, -0.01)           # small drag in normal quarters
qa[bad] = 0.10
a = pd.Series(toq(qa), index=i)
bnd = pd.Series(0.002, index=i)
c = pd.Series(0.001, index=i)
qi = E.qret(s).index
SQ = qi[bad]                      # the selloff quarters, picked outside test19 as in the script
H2 = [("1990", "1994"), ("1995", "1999")]
t = E.test19(a, s, bnd, c, SQ, halves=H2, cost=0.5)
check("test19 (a) passes for a hedge", t["a"] and t["n_q"] == 5)
check("test19 (b) passes when cost allowed", t["b"])
check("test19 (c) both halves improve", t["c"] and len(t["halves"]) == 2)
# isolate the cost rule: a limit just below the measured cost must fail (b)
cst = t["cost"]
t1 = E.test19(a, s, bnd, c, SQ, halves=H2, cost=cst + 1e-6)
t2 = E.test19(a, s, bnd, c, SQ, halves=H2, cost=cst - 1e-6)
check("test19 (b) cost limit is binding at the boundary", t1["b"] and not t2["b"])
t = E.test19(a, s, bnd, c, SQ[2:], cost=0.5, halves=H2)
check("test19 (a) needs 5 quarters", not t["a"] and t["n_q"] == 3)
t = E.test19(c, s, bnd, c, SQ, cost=0.5, halves=H2)
check("test19 (b) cash itself does not pass", not t["b"] and not t["a"])
# (c): hedge works only in the first half
qa2 = qa.copy()
qa2[[22, 31]] = -0.10
t = E.test19(pd.Series(toq(qa2), index=i), s, bnd, c, SQ, cost=0.5, halves=H2)
check("test19 (c) fails when the second half does not improve", not t["c"] and t["halves"][1][2] <= 0)
# (a) "positive in more than half": exactly half positive must fail, 4 of 6 must pass
bad6 = [2, 9, 15, 22, 31, 36]
qs6 = np.full(n, 0.02)
qs6[bad6] = -0.20
s6 = pd.Series(toq(qs6), index=i)
for npos, want in [(3, False), (4, True)]:
    q6 = np.full(n, 0.0)
    q6[bad6] = -0.005
    q6[bad6[:npos]] = 0.20
    t = E.test19(pd.Series(toq(q6), index=i), s6, bnd, c, qi[bad6], cost=0.5, halves=H2)
    check(f"test19 (a) with {npos} of 6 positive -> {want}", t["a"] == want and t["n_q"] == 6)
# candidate starting later: baseline and quarters use only the candidate's months
t = E.test19(a["1992":], s, bnd, c, SQ, cost=0.5, halves=H2)
check("test19 uses only the candidate's months", t["n_q"] == 4 and t["start"] == pd.Timestamp("1992-01-31"))
check("test19 rejects a gap in the sample", raises(lambda: E.test19(a.drop(a.index[50]), s, bnd, c, SQ, halves=H2)))

# 12. 2B-I criteria
i = idx("1970-01", 12 * 57)          # 1970-2026
base = pd.Series(0.004, index=i)
for k, (a_, b_) in E.WINDOWS.items():
    base[pd.Timestamp(a_) + pd.offsets.MonthEnd(3)] = -0.20
sel = pd.DatetimeIndex([pd.Timestamp("1974-06-30"), pd.Timestamp("1980-03-31"), pd.Timestamp("2022-06-30")])
cand = base.copy()
cand["1974-05-31"] += 0.01
cand["1980-02-29"] += 0.01
cand["2022-05-31"] += 0.01
for k in E.INFLATION_CRASHES:
    cand[pd.Timestamp(E.WINDOWS[k][0]) + pd.offsets.MonthEnd(3)] = -0.15
r = E.crit_commod(cand, base, sel)
check("2B-I (a) passes", r["a"])
check("2B-I (b) passes (growth unchanged)", r["b"])
check("2B-I (c) passes (cand earns more)", r["c"])
check("2B-I (d) passes", r["d"])
c2 = cand.copy()
c2[pd.Timestamp(E.WINDOWS["2022"][0]) + pd.offsets.MonthEnd(3)] = -0.21
check("2B-I (a) fails if one inflation crash is worse", not E.crit_commod(c2, base, sel)["a"])
check("2B-I (d) fails when the second half fails", not E.crit_commod(c2, base, sel)["d"])
c3 = cand.copy()
c3[pd.Timestamp(E.WINDOWS["2007-09"][0]) + pd.offsets.MonthEnd(3)] = -0.23   # exactly 3 pts worse
check("2B-I (b) passes at exactly 3 pts worse", E.crit_commod(c3, base, sel)["b"])
c3[pd.Timestamp(E.WINDOWS["2007-09"][0]) + pd.offsets.MonthEnd(3)] = -0.2301
check("2B-I (b) fails beyond 3 pts", not E.crit_commod(c3, base, sel)["b"])
c4 = cand - 0.001            # costs about 1 pt a year net
check("2B-I (c) fails on cost", not E.crit_commod(c4, base, sel)["c"])
c5 = cand.copy()
c5["2022-05-31"] -= 0.05     # the one second-half selloff quarter now worse -> half majority fails
r5 = E.crit_commod(c5, base, sel)
check("2B-I (d) fails on second-half quarters; (a) still majority", r5["a"] and not r5["d"])
check("2B-I rejects missing selloff quarters", raises(lambda: E.crit_commod(cand, base, pd.DatetimeIndex([pd.Timestamp("1960-03-31")]))))

# 13. long check
L = idx("1927-01", 24)
bL = pd.Series(0.0, index=L)
cL = bL.copy()
cL["1927-02-28"] = 0.02
sq = pd.DatetimeIndex([pd.Timestamp("1927-03-31")])
check("2B-I (e) passes", E.crit_long(cL, bL, sq)["e"])
check("2B-I (e) fails on negative edge", not E.crit_long(-cL, bL, sq)["e"])

# 14. weight choice
mk = lambda x: {"loss": {"1973-74": (x, 0), "2022": (-0.10, 0)}}  # noqa: E731
check("pick 5 when 10 is only 2.9 pts better", E.pick_weight(mk(-0.30), mk(-0.271), True, True) == 5)
check("pick 10 when 3 pts better", E.pick_weight(mk(-0.30), mk(-0.27), True, True) == 10)
check("pick the only passer", E.pick_weight(mk(-0.3), mk(-0.2), False, True) == 10)
check("pick none", E.pick_weight(mk(-0.3), mk(-0.2), False, False) is None)

# 15. trend filter: uses only past months
i = idx("2000-01", 14)
asset = pd.Series(0.02, index=i)
asset.iloc[12] = -0.50                      # month 13 crash: month 13 still held (signal from months 1-12)
cash = pd.Series(0.001, index=i)
tf, held = E.trend_filter(asset, cash, fee_m=0.0)
check("trend filter: first valid month is 13", tf.index[0] == i[12])
check("trend filter: holds into the crash month", bool(held.iloc[0]) and close(tf.iloc[0], -0.50))
check("trend filter: exits after the crash", not bool(held.iloc[1]) and close(tf.iloc[1], 0.001))
tf2, _ = E.trend_filter(asset, cash, fee_m=0.01)
check("trend filter: fee only when held", close(tf2.iloc[0], -0.51) and close(tf2.iloc[1], 0.001))

# 16. trend proxy: no look-ahead, sign and size
rng = np.random.default_rng(0)
i = idx("1950-01", 120)
X = pd.DataFrame(rng.normal(0.005, 0.03, (120, 3)), index=i, columns=list("abc"))
p1 = E.trend_proxy(X)
X2 = X.copy()
X2.iloc[-1] = 0.5
p2 = E.trend_proxy(X2)
check("trend proxy: changing the last month changes only the last month",
      np.allclose(p1.iloc[:-1].values, p2.iloc[:-1].values) and not close(p1.iloc[-1], p2.iloc[-1]))
t0 = p1.index[0]
k = X.index.get_loc(t0)
mom = (1 + X.iloc[k - 12:k]).prod() - 1
vol = X.iloc[k - 36:k].std() * np.sqrt(12)
check("trend proxy: hand calculation", close(p1.iloc[0], float((np.sign(mom) * 0.10 / vol * X.iloc[k]).mean())))
check("trend proxy: starts after 36 months", k == 36)

# 17. real returns
i = idx("2000-01", 2)
check("real: (1.05/1.02)-1", close(E.real(pd.Series([0.05, 0.0], index=i), pd.Series([0.02, 0.0], index=i)).iloc[0], 1.05 / 1.02 - 1))
check("real: missing inflation raises", raises(lambda: E.real(pd.Series([0.05, 0.0], index=i), pd.Series([0.02], index=i[:1]))))

# 18. more 2B-I edge cases
cm = cand.copy()
sel4 = pd.DatetimeIndex([pd.Timestamp(x) for x in ["1974-06-30", "1980-03-31", "1981-03-31", "2022-06-30"]])
cm["1981-02-28"] -= 0.01          # 1981 quarter: worse than base
cm["1980-02-29"] -= 0.02          # 1980 quarter: +0.01 - 0.02 -> worse; so better in exactly 2 of 4 (1974, 2022)
check("2B-I (a) exactly half the quarters better -> fails", not E.crit_commod(cm, base, sel4)["a"])
check("2B-I rejects candidate and base on different months",
      raises(lambda: E.crit_commod(cand.iloc[:-1], base, sel)))
check("2B-I rejects a sample with a gap", raises(lambda: E.crit_commod(cand.drop(cand.index[100]), base.drop(base.index[100]), sel)))
mk2 = lambda a, b: {"loss": {"1973-74": (a, 0), "2022": (b, 0)}}  # noqa: E731
check("pick_weight uses the WORSE inflation crash (2022 here)", E.pick_weight(mk2(-0.10, -0.30), mk2(-0.20, -0.27), True, True) == 10)
L2 = idx("1927-01", 240)
bL2 = pd.Series(0.005, index=L2)
cLc = bL2 - 0.001                 # about 1.2 pts a year cost ...
cLc["1927-02-28"] = 0.05          # ... but better in the one selloff quarter
r_ = E.crit_long(cLc, bL2, sq)
check("2B-I (e) fails on cost even with a positive edge", r_["q_diff"] > 0 and r_["cost"] > 0.005 and not r_["e"])

# 19. trend filter with misaligned inputs
i = idx("2000-01", 30)
asset = pd.Series(0.01, index=i)
cash = pd.Series(0.001, index=i[6:-3])            # T-bills start 6 months later, end 3 months earlier
tf, held = E.trend_filter(asset, cash)
check("trend filter: only months where both exist", tf.index[0] == i[6 + 12] and tf.index[-1] == i[-4] and not tf.isna().any())

# 20. splice, quarter_end, contiguous
mi = pd.date_range("1985-01", "1995-12", freq="ME")
y20 = pd.Series(7.0, index=mi)
y30 = pd.Series(8.0, index=mi)
y20[(mi >= "1987-01-01") & (mi <= "1993-09-30")] = np.nan
y20["1993-10-31":] = 6.0
y30["1990-06-30"] = 8.5                                     # a move only the 30-year series has
sys.path.insert(0, "scripts/phase2b")
try:
    from common2b import bond_ret
except Exception:                                            # stand-alone copy of the same formula
    def bond_ret(yield_pct, years):
        yy = yield_pct / 100
        yp = yy.shift(1)
        ypc = yp.where(yp.abs() > 1e-4, 1e-4)
        return (yp / 12 - (1 - (1 + ypc / 2) ** (-2 * years)) / ypc * (yy - yp)).dropna()
r20 = E.splice(bond_ret(y20, 20), bond_ret(y30, 20), "1987-01", "1993-12")
r30 = bond_ret(y30, 20)
check("splice: gap months 1987-01..1993-10 come from the 30-year only",
      np.allclose(r20["1987-01":"1993-10"].values, r30["1987-01":"1993-10"].values))
check("splice: 1993-11 comes from the 20-year", close(r20["1993-11-30"], bond_ret(y20, 20)["1993-11-30"]))
check("splice: no missing months", E.contiguous(r20, "r20") is r20 and not r20.isna().any())
y1 = pd.Series(4.0, index=pd.date_range("1975-01", "1977-12", freq="ME"))
y3 = y1 + 1.0
y2 = pd.Series(4.4, index=pd.date_range("1976-06", "1977-12", freq="ME"))
r2 = E.splice(bond_ret(y2, 2), bond_ret((y1 + y3) / 2, 2), "1962", "1976-06")
check("splice: 1976-06 from the 1y/3y average, 1976-07 from the 2y",
      close(r2["1976-06-30"], bond_ret((y1 + y3) / 2, 2)["1976-06-30"]) and close(r2["1976-07-31"], bond_ret(y2, 2)["1976-07-31"]))
qm = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0], index=pd.date_range("2000-01", periods=5, freq="ME"))
check("quarter_end keeps Mar and drops a quarter without its last month", list(E.quarter_end(qm).index) == [pd.Timestamp("2000-03-31")])
check("contiguous raises on a gap", raises(lambda: E.contiguous(qm.drop(qm.index[2]))))

# 21. 2B-F, trend adoption, index-type rules at their boundaries
i = idx("1970-01", 12 * 57)
bb = pd.Series(0.004, index=i)
for k in E.WINDOWS:
    bb[pd.Timestamp(E.WINDOWS[k][0]) + pd.offsets.MonthEnd(3)] = -0.20
def alt(g, f, drag=0.0):
    x = bb.copy() - drag
    for k in E.GROWTH_CRASHES:
        x[pd.Timestamp(E.WINDOWS[k][0]) + pd.offsets.MonthEnd(3)] = -0.20 + g
    for k in E.INFLATION_CRASHES:
        x[pd.Timestamp(E.WINDOWS[k][0]) + pd.offsets.MonthEnd(3)] = -0.20 + f
    return x
check("2B-F passes at exactly 1 pt in both", E.bond_rule(bb, alt(0.01, 0.01, 0.00001))["pass"])
check("2B-F fails if only growth improves", not E.bond_rule(bb, alt(0.05, 0.0099))["pass"])
check("2B-F fails if only inflation improves", not E.bond_rule(bb, alt(0.0099, 0.05))["pass"])
check("2B-F fails on cost", not E.bond_rule(bb, alt(0.05, 0.05, 0.001))["pass"])
rs = {"loss": {"2000-02": (-0.20, 0), "2007-09": (-0.25, 0)}}
check("trend adopted at exactly 2 pts and passing", E.trend_adopt(rs, {"pass": True, "loss": {"2000-02": (-0.20, 0), "2007-09": (-0.23, 0)}})[0])
check("trend not adopted at 1.9 pts", not E.trend_adopt(rs, {"pass": True, "loss": {"2000-02": (-0.20, 0), "2007-09": (-0.231, 0)}})[0])
check("trend not adopted if it fails (a)-(e)", not E.trend_adopt(rs, {"pass": False, "loss": {"2000-02": (-0.1, 0), "2007-09": (-0.1, 0)}})[0])
pb = bb.copy()
pg = bb.copy()
pg[pd.Timestamp(E.WINDOWS["2022"][0]) + pd.offsets.MonthEnd(3)] = -0.15
check("GSCI used at exactly 5 pts better and no cost", E.gsci_rule(pb, pg)[0])
check("GSCI not used at 4.9 pts", not E.gsci_rule(pb, pg.where(pg != -0.15, -0.151))[0])
pgc = pg - 0.001                  # about 1.2 pts a year cost ...
pgc[pd.Timestamp(E.WINDOWS["2022"][0]) + pd.offsets.MonthEnd(3)] = -0.12     # ... while still 5+ pts better in 2022
check("GSCI not used when it costs over 1 pt",
      E.window_loss(pgc, "2022") - E.window_loss(pb, "2022") >= 0.05 and not E.gsci_rule(pb, pgc)[0])
check("GSCI rule needs the same months", raises(lambda: E.gsci_rule(pb, pg.iloc[1:])))

# 22. filling unpublished index months
lv = pd.Series([100.0, np.nan, 121.0, 125.0], index=idx("2025-09", 4))
f_, months = E.fill_index(lv.drop(lv.index[1]))
check("fill_index: log-linear middle month and reports it",
      close(f_.iloc[1], 110.0, 1e-9) and months == [pd.Timestamp("2025-10-31")] and len(f_) == 4)
f_, months = E.fill_index(pd.Series([1.0, 2.0], index=idx("2000-01", 2)))
check("fill_index: nothing to fill", months == [] and len(f_) == 2)

# 23. Ken French CSV parser
txt = """This file was created by CMPT_ME_BEME_RETS using the 202608 CRSP database.
  Value Weight Returns -- Monthly

,<= 0,Lo 30,Hi 20
196307,  1.00,  2.00, -99.99
196308, -1.00,  0.50,  3.00

  Equal Weight Returns -- Monthly
,<= 0,Lo 30,Hi 20
196307, 9.00,  9.00,  9.00
"""
d = E.parse_french_csv(txt)
check("french parser: names, first block only, decimals",
      list(d.columns) == ["<= 0", "Lo 30", "Hi 20"] and len(d) == 2 and close(d.loc["1963-08-31", "Hi 20"], 0.03))
check("french parser: -99.99 becomes missing", pd.isna(d.loc["1963-07-31", "Hi 20"]))
check("french parser: month-end dates", d.index[0] == pd.Timestamp("1963-07-31"))
check("french parser: rejects a short row", raises(lambda: E.parse_french_csv(txt.replace("196308, -1.00,  0.50,  3.00", "196308, -1.00,  0.50"))))

# 24. style rule
i = idx("1963-07", 12 * 64)
mk = pd.Series(0.006, index=i)
for k in E.WINDOWS:
    mk[pd.Timestamp(E.WINDOWS[k][0]) + pd.offsets.MonthEnd(3)] = -0.30
def sty(better, drag=0.0):
    x = mk.copy() - drag
    for k in better:
        x[pd.Timestamp(E.WINDOWS[k][0]) + pd.offsets.MonthEnd(3)] = -0.25
    return x
r_ = E.style_rule(sty(["1973-74", "2000-02", "2007-09"]), mk)
check("style: 3 of 4 wins passes", r_["pass"] and r_["wins"] == 3)
check("style: 2 of 4 fails", not E.style_rule(sty(["1973-74", "2022"]), mk)["pass"])
r_ = E.style_rule(sty(list(E.WINDOWS), 0.0012), mk)
check("style: lags over 1 pt/yr fails even with 4 wins", r_["wins"] == 4 and r_["lag"] > 0.01 and not r_["pass"])
x_ = sty(list(E.WINDOWS))
gap0 = E.ann(mk) - E.ann(x_)
check("style: lag limit binding at the boundary", E.style_rule(x_, mk, lag=gap0 + 1e-9)["pass"] and not E.style_rule(x_, mk, lag=gap0 - 1e-9)["pass"])
check("style: equal loss is not a win", E.style_rule(mk.copy(), mk)["wins"] == 0)
check("style: needs the same months", raises(lambda: E.style_rule(mk.iloc[1:], mk)))

# 25. final-mix bar, tie-break, gold signal, switching portfolio
i = idx("1970-01", 120)
b0 = pd.Series(0.005, index=i)
b0[i[10]] = -0.20                                     # base: -20% then slow recovery
def cand_(dd, rec_drag=0.0):
    x = b0.copy()
    x[i[10]] = dd
    return x - rec_drag
rb_ = E.mix_bar(b0.copy(), b0)
check("mix_bar: identical -> no cut, fails", rb_["dd_cut"] == 0 and rb_["uw_cut"] == 0 and not rb_["pass"])
x_ = cand_(-0.17)
r_ = E.mix_bar(x_, b0)
check("mix_bar: 3 pts smaller loss measured", close(r_["dd_cut"], 0.03))
uwb, uwc = E.longest_underwater(b0), E.longest_underwater(x_)
check("mix_bar: underwater measured in months", r_["uw_cut"] == uwb - uwc and uwb > uwc)
check("mix_bar: passes only if underwater cut >= need", E.mix_bar(x_, b0, need_uw=uwb - uwc)["pass"] and not E.mix_bar(x_, b0, need_uw=uwb - uwc + 1)["pass"])
check("mix_bar: fails on 2.9 pts", not E.mix_bar(cand_(-0.171), b0, need_uw=0)["pass"])
check("mix_bar: fails on cost", E.mix_bar(cand_(-0.10, 0.002), b0, need_uw=-999)["cost"] > 0.003 and not E.mix_bar(cand_(-0.10, 0.002), b0, need_uw=-999)["pass"])
check("mix_bar: annual uses ppy=1", close(E.ann(pd.Series([0.1, 0.1], index=idx("2000-01", 2)), ppy=1), 0.1))
check("mix_bar: needs same periods", raises(lambda: E.mix_bar(x_.iloc[1:], b0)))
res = {"a": {"pass": True, "dd_cut": 0.05, "cost": 0.0005}, "b": {"pass": True, "dd_cut": 0.08, "cost": 0.003},
       "c": {"pass": False, "dd_cut": 0.20, "cost": 0.0}, "d": {"pass": True, "dd_cut": 0.08, "cost": 0.001}}
check("pick_best: biggest loss cut, then lower cost, ignores failures", E.pick_best(res) == "d")
check("pick_best: none passes", E.pick_best({"a": {"pass": False, "dd_cut": 1, "cost": 0}}) is None)
gi = idx("1975-01", 80)
lvl = pd.Series(range(80), index=gi, dtype=float)    # rising price: always at its high
sig = E.gold_signal(lvl)
check("gold signal: held for the first 60 months, judged from month 61", sig.iloc[:60].all() and not sig.iloc[60])
check("gold signal: off at an all-time high", not sig.iloc[60:].any())
lvl2 = lvl.copy()
lvl2.iloc[70:] = 10.0                                  # price falls back into the low part of its history
sig2 = E.gold_signal(lvl2)
check("gold signal: uses the prior month (switches on one month after the fall)", not sig2.iloc[70] and sig2.iloc[71])
lvl3 = lvl.copy()
lvl3.iloc[-1] = -100.0
check("gold signal: no look-ahead", E.gold_signal(lvl3).iloc[:-1].equals(sig.iloc[:-1]))
l85 = pd.Series(list(range(60)) + [51.0, 51.0], index=idx("1975-01", 62), dtype=float)
check("gold signal: off at the 84th percentile (top fifth)", not E.gold_signal(l85).iloc[61])
pre = pd.Series(1.0, index=idx("1970-01", 60))
sg_ = E.gold_signal(pd.concat([pre * 1000, lvl])).loc["1975-01-31":]
check("gold signal: history starts 1975 (earlier high prices ignored)", sg_.iloc[:60].all() and not sg_.iloc[60])
Rs = pd.DataFrame({"s": [0.1, 0.1], "b": [0.0, 0.0], "g": [0.2, 0.2]}, index=idx("2000-01", 2))
ps = E.port_switch(Rs, {"s": 0.5, "b": 0.4, "g": 0.1}, {"s": 0.5, "b": 0.5}, pd.Series([True, False], index=Rs.index))
check("port_switch: on/off weights by month", close(ps.iloc[0], 0.07) and close(ps.iloc[1], 0.05))

bad_ = [n for n, ok in results if not ok]
print(f"\n{len(results) - len(bad_)} of {len(results)} checks passed" + (f"; FAILED: {bad_}" if bad_ else ""))
sys.exit(1 if bad_ else 0)
