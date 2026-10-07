import os
import numpy as np
import pandas as pd
from math import comb

PATH = "data/phase2_macro/JSTdatasetR6.xlsx"
raw = pd.read_excel(PATH)
need = ["country", "year", "cpi", "eq_tr", "bond_tr", "bill_rate"]
d = raw[need].sort_values(["country", "year"]).copy()
sr = 0.01 if d.eq_tr.abs().median() > 1 else 1.0
sb = 0.01 if d.bill_rate.abs().median() > 1 else 1.0
d["stocks"], d["bonds"], d["cash"] = d.eq_tr * sr, d.bond_tr * sr, d.bill_rate * sb
d["infl"] = d.groupby("country").cpi.pct_change() * 100
d["infl_lag"] = d.groupby("country").infl.shift(1)
d = d[(d.year >= 1950) & (d.year <= 2020)].dropna(subset=["stocks", "bonds", "cash", "infl_lag"])

UP, DOWN, BIG = 3.25, 3.0, 4.0   # fixed in advance; no parameter fitted to these countries

def states(infl_lag):
    on, out = False, []
    for v in infl_lag:
        if v > UP:
            on = True
        elif v < DOWN:
            on = False
        out.append(on)
    return np.array(out)

def trim_fracs(infl_lag, on):
    one = np.where(on, 0.5, 0.0)
    two = np.where(on, 1 / 3, 0.0)
    two = np.where(on & (infl_lag > BIG), 0.5, two)
    return one, two

def port(s, b, c, f):
    return 0.6 * s + 0.4 * (1 - f) * b + 0.4 * f * c

def max_dd(r):
    w = np.cumprod(1 + r)
    return (w / np.maximum.accumulate(w) - 1).min()

def ann_ret(r):
    return (np.prod(1 + r) ** (1 / len(r)) - 1)

res, data = [], {}
for c, g in d.groupby("country"):
    if len(g) < 50:
        continue
    s, b, ca, il = g.stocks.values, g.bonds.values, g.cash.values, g.infl_lag.values
    on = states(il)
    one, two = trim_fracs(il, on)
    r0, r1, r2 = port(s, b, ca, 0), port(s, b, ca, one), port(s, b, ca, two)
    data[c] = (s, b, ca, il, on)
    res.append({
        "country": c, "years": len(g), "pct_trimmed": on.mean() * 100,
        "ret_base": ann_ret(r0) * 100, "ret_one": ann_ret(r1) * 100, "ret_two": ann_ret(r2) * 100,
        "dd_base": max_dd(r0) * 100, "dd_one": max_dd(r1) * 100, "dd_two": max_dd(r2) * 100,
    })
t = pd.DataFrame(res).set_index("country")
t["dd_gain_one"] = t.dd_one - t.dd_base      # positive = shallower drawdown
t["dd_gain_two"] = t.dd_two - t.dd_base
t["ret_chg_one"] = t.ret_one - t.ret_base
t["ret_chg_two"] = t.ret_two - t.ret_base
t["dd_two_vs_one"] = t.dd_two - t.dd_one
t["ret_two_vs_one"] = t.ret_two - t.ret_one

print(f"CROSS-COUNTRY BACKTEST of Trigger 1, 1950-2020, {len(t)} countries, annual data, 60/40 base")
print("Rule: act when LAGGED inflation > 3.25%, restore when < 3.0%. One-step trims 1/2 of bonds into cash; two-step trims 1/3, and 1/2 when lagged inflation > 4%.")
print("Drawdowns are measured on annual returns, so they understate intra-year drops. Positive 'dd gain' = shallower drawdown.\n")
show = t[["pct_trimmed", "ret_base", "ret_chg_one", "ret_chg_two", "dd_base", "dd_gain_one", "dd_gain_two"]].round(1)
print(show.to_string())

def binom_p(k, n):
    return sum(comb(n, i) for i in range(k, n + 1)) / 2 ** n

rng = np.random.default_rng(0)
def boot_mean(x, n=3000):
    x = np.asarray(x)
    m = [rng.choice(x, len(x)).mean() for _ in range(n)]
    return np.percentile(m, [2.5, 97.5])

print("\nSUMMARY ACROSS COUNTRIES (mean difference vs plain 60/40; 95% range from resampling countries)")
for lab, dd, rr in [("One-step rule", "dd_gain_one", "ret_chg_one"), ("Two-step rule", "dd_gain_two", "ret_chg_two"), ("Two-step minus one-step", "dd_two_vs_one", "ret_two_vs_one")]:
    ci = boot_mean(t[dd])
    k = int((t[dd] > 0).sum())
    print(f"  {lab:<24} drawdown {t[dd].mean():5.1f} pts [{ci[0]:5.1f}, {ci[1]:5.1f}], shallower in {k} of {len(t)} countries (sign-test p={binom_p(k, len(t)):.2f}); return {t[rr].mean():5.2f} pts/yr [{boot_mean(t[rr])[0]:5.2f}, {boot_mean(t[rr])[1]:5.2f}]")

print("\nPLACEBO (each country's on/off pattern shifted at random; same time spent trimmed): average drawdown gain across countries")
for lab, which in [("One-step", 0), ("Two-step", 1)]:
    actual = t["dd_gain_one" if which == 0 else "dd_gain_two"].mean()
    sims = []
    for _ in range(500):
        gains = []
        for c, (s, b, ca, il, on) in data.items():
            k = int(rng.integers(5, len(on) - 5))
            on2 = np.roll(on, k)
            one, two = trim_fracs(np.roll(il, k), on2)
            f = one if which == 0 else two
            gains.append(max_dd(port(s, b, ca, f)) - max_dd(port(s, b, ca, 0)))
        sims.append(np.mean(gains) * 100)
    print(f"  {lab}: actual {actual:5.1f} pts; share of placebos at least as good: {(np.array(sims) >= actual).mean() * 100:.0f}%")
