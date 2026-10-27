# Phase 2B decision test 2B-H: the final mix (managed-futures weight, stock/Treasury/gold split, rebalancing rule).
# Usage, from the repo root:  python scripts/phase2b/final_mix.py
# Output: data/phase2b/final_mix_results.txt
#
# Rules: docs/phase2b_research_plan.md, amendments 2026-10-16 (2B-H), 2026-10-26 (rebalancing comparison),
# 2026-10-27 (managed futures in 2B-H; 2B-H details fixed before coding). In short:
#   Step 1, managed-futures weight: 5% unless 10% (both taken proportionally from 55/45) beats the 5% mix on the
#     2B-H bar (worst after-inflation loss cut 3+ pts AND longest time underwater cut 12+ months, cost <= 0.3
#     pts/yr) and cuts the worst loss in each half (1970-97, 1998-2026).
#   Step 2, mix: each candidate stock/Treasury/gold split is applied to the part not in managed futures and judged
#     against 55/45 with the same managed-futures slice. Pass = the 2B-H bar in the US AND
#       stock/bond splits: the bar (yearly data, 1+ year underwater) in more than half of the JST countries with
#         complete data 1950-2020 (no managed futures: JST has none);
#       gold mixes: the bar in each half (1970-97, 1998-2026) and from 1975 on.
#     Gold plus managed futures must be <= 15% of the whole portfolio (otherwise dropped and reported).
#     Several pass -> the biggest cut in worst loss (then lower cost). None -> 55/45 stays.
#     Gold mixes are also shown with the valuation view (report only).
#   Step 3, rebalancing on the winning mix: yearly (December) and a 5-point drift band on the stock weight, each
#     judged against monthly on the bar in the full sample and in each half. Same tie-break. Otherwise monthly.
#   Managed futures = the trend proxy from mix_tests.py (same construction, same 1.0 pt/yr fee). The proxy is
#     rebuilt here and its correlation with AQR's official factor is printed; it must match the stage-1 value.
import os
import sys
import pandas as pd

sys.path.insert(0, "scripts/phase2b")
from common2b import OUT, aqr_century, aqr_tsmom, french, load_v2, wb_gold  # noqa: E402
from common import JST_PATH  # noqa: E402
import mix_engine as E  # noqa: E402

MF_FEE = 0.010
STAGE1_CORR, STAGE1_SCALE = 0.72, 1.79          # printed by mix_tests.py (data/phase2b/mix_tests_results.txt)
STAGE1_7374 = -0.396                             # 55/45 1973-74 loss in stage 1 and the case study
RESULTS = f"{OUT}/final_mix_results.txt"
SPLITS = {"45/55": (0.45, 0.55, 0.0), "50/50": (0.50, 0.50, 0.0), "60/40": (0.60, 0.40, 0.0), "65/35": (0.65, 0.35, 0.0)}
GOLDS = {"55/40/5 gold": (0.55, 0.40, 0.05), "50/40/10 gold": (0.50, 0.40, 0.10), "55/35/10 gold": (0.55, 0.35, 0.10)}
BASE = (0.55, 0.45, 0.0)
lines = []


def log(s=""):
    print(s)
    lines.append(s)


def pct(x, d=1):
    return "n/a" if x is None or pd.isna(x) else f"{x * 100:+.{d}f}%"


def pts(x):
    return "n/a" if x is None or pd.isna(x) else f"{x * 100:+.2f} pts"


def finish():
    os.makedirs(OUT, exist_ok=True)
    with open(RESULTS, "w") as f:
        f.write("\n".join(lines) + "\n")
    print(f"\nSaved {RESULTS}")


def _on_error(exc_type, exc, tb):
    if exc_type is not SystemExit:
        log(f"\nERROR, script stopped: {exc_type.__name__}: {exc}")
        finish()
    sys.__excepthook__(exc_type, exc, tb)


sys.excepthook = _on_error


def bar_line(label, r):
    return (f"  {label:26s} worst loss {pct(r['dd'])} (cut {pts(r['dd_cut'])}), longest underwater {r['uw']} "
            f"(cut {r['uw_cut']:+d}), cost {pts(r['cost'])}/yr -> {'PASS' if r['pass'] else 'fail'}")


# ======================= DATA =======================
v2 = load_v2()
E.contiguous(v2, "v2")
fac = french("F-F_Research_Data_Factors")
rf_all = fac[4] / 100
aqr = aqr_century()
tsmom = aqr_tsmom()["TSMOM"]
proxy_raw = E.trend_proxy(aqr[["Equity indices Market", "Fixed income Market", "Commodities Market"]])
pc = pd.concat([proxy_raw, tsmom], axis=1, sort=True).dropna()
proxy_corr = pc.corr().iloc[0, 1]
scale = pc.iloc[:, 1].std() / pc.iloc[:, 0].std()
mf = (scale * proxy_raw + rf_all - MF_FEE / 12).dropna()
gold = v2.gold.fillna(E.chg(wb_gold()).reindex(v2.index))

P = E.contiguous(pd.DataFrame({"s": v2.stocks, "b": v2.bonds, "g": gold, "m": mf.reindex(v2.index),
                               "i": v2.cpi_m})["1970-01":"2026-02"].dropna(), "US sample")
if P.index[0] != pd.Timestamp("1970-01-31") or P.index[-1] != pd.Timestamp("2026-02-28"):
    raise ValueError(f"US sample must be 1970-01 to 2026-02 (rule); got {P.index[0]:%Y-%m} to {P.index[-1]:%Y-%m}")
real = lambda r: E.real(r, P.i)  # noqa: E731
cpi_lvl = (1 + P.i).cumprod()
gold_real_lvl = (wb_gold().reindex(P.index) / cpi_lvl).dropna()

log("PHASE 2B DECISION TEST 2B-H: FINAL MIX (after inflation)")
log("=" * 100)
log("DATA CHECKS")
log(f"  US sample {P.index[0]:%Y-%m} to {P.index[-1]:%Y-%m} ({len(P)} months, no gaps)")
log(f"  Trend proxy vs AQR official factor: correlation {proxy_corr:.2f} (stage 1: {STAGE1_CORR}), size scale {scale:.2f} "
    f"(stage 1: {STAGE1_SCALE})")
if abs(proxy_corr - STAGE1_CORR) > 0.015 or abs(scale - STAGE1_SCALE) > 0.03:
    raise ValueError("managed-futures proxy differs from stage 1: data changed since stage 1 ran")
base_real = real(E.port(P, {"s": 0.55, "b": 0.45}))
l7374 = E.window_loss(base_real, "1973-74")
log(f"  55/45 1973-74 loss {pct(l7374)} (stage 1: {pct(STAGE1_7374)})")
if abs(l7374 - STAGE1_7374) > 0.001:
    raise ValueError("55/45 data differs from stage 1: v2 data changed since stage 1 ran")


def mix(split, m, rebalance="monthly"):
    s, b, g = split
    w = {"s": s * (1 - m), "b": b * (1 - m), "g": g * (1 - m), "m": m}
    w = {k: v for k, v in w.items() if v > 0}
    return real(E.port(P, w, rebalance=rebalance, band_asset="s"))


# ======================= STEP 1: MANAGED-FUTURES WEIGHT =======================
log("\n" + "=" * 100)
log("STEP 1: MANAGED-FUTURES WEIGHT (10% must beat 5% on the bar and cut the worst loss in each half)")
m5, m10 = mix(BASE, 0.05), mix(BASE, 0.10)
r = E.mix_bar(m10, m5)
halves_ok = all(E.max_dd(m10[a:z]) > E.max_dd(m5[a:z]) for a, z in E.HALVES)
log(bar_line("10% vs 5% (1970-2026)", r))
for a, z in E.HALVES:
    log(f"    {a}-{z}: worst loss 10% {pct(E.max_dd(m10[a:z]))} vs 5% {pct(E.max_dd(m5[a:z]))}")
MW = 0.10 if (r["pass"] and halves_ok) else 0.05
log(f"  For reference, 55/45 with no managed futures: worst loss {pct(E.max_dd(base_real))}, "
    f"longest underwater {E.longest_underwater(base_real)} months")
log(f"  RESULT: managed futures {int(MW * 100)}%")

# ======================= STEP 2: THE MIX =======================
log("\n" + "=" * 100)
log(f"STEP 2: THE MIX (each split applied to the {int((1 - MW) * 100)}% outside managed futures; vs 55/45 with the same slice)")
base_m = mix(BASE, MW)
log(f"  Baseline 55/45 + {int(MW * 100)}% managed futures: worst loss {pct(E.max_dd(base_m))}, longest underwater "
    f"{E.longest_underwater(base_m)} months, return {pct(E.ann(base_m))}/yr")

# JST countries
jr = pd.read_excel(JST_PATH)[["country", "year", "cpi", "eq_tr", "bond_tr"]].sort_values(["country", "year"])
sr = 0.01 if jr.eq_tr.abs().median() > 1 else 1.0
jr["s"], jr["b"] = jr.eq_tr * sr, jr.bond_tr * sr
jr["i"] = jr.groupby("country").cpi.transform(lambda x: x / x.shift(1) - 1)
J = jr[(jr.year >= 1950) & (jr.year <= 2020)]
countries = [c for c, x in J.groupby("country") if len(x) == 71 and x[["s", "b", "i"]].notna().all().all()]
log(f"  JST countries with complete data 1950-2020: {len(countries)} ({', '.join(countries)})")


def jst_pass(split):
    wins = 0
    for c in countries:
        x = J[J.country == c].set_index(pd.to_datetime(J[J.country == c].year.astype(int).astype(str) + "-12-31"))
        rr = lambda w: (1 + (w[0] * x.s + w[1] * x.b)) / (1 + x.i) - 1  # noqa: E731
        wins += E.mix_bar(rr(split), rr(BASE), need_uw=1, ppy=1)["pass"]
    return wins


results, notes = {}, {}
for name, split in {**SPLITS, **GOLDS}.items():
    if split[2] * (1 - MW) + MW > 0.15 + E.EPS:
        log(f"\n  {name}: DROPPED (gold {split[2] * (1 - MW) * 100:.1f}% + managed futures {MW * 100:.0f}% > 15%)")
        continue
    c = mix(split, MW)
    r = E.mix_bar(c, base_m)
    log(f"\n  {name}")
    log("  " + bar_line("US 1970-2026", r))
    log("      crash losses: " + "; ".join(f"{k} {pct(E.window_loss(c, k))} vs {pct(E.window_loss(base_m, k))}" for k in E.WINDOWS))
    ok = r["pass"]
    if split[2] == 0:
        n = jst_pass(split)
        ok_j = n > len(countries) / 2
        log(f"      countries: passes the bar in {n} of {len(countries)} -> {'majority' if ok_j else 'no majority'}")
        ok = ok and ok_j
    else:
        for a, z in E.HALVES + [("1975", "2026")]:
            rh = E.mix_bar(c[a:z], base_m[a:z])
            log("  " + bar_line(f"US {a}-{z}", rh))
            ok = ok and rh["pass"]
        gs = E.gold_signal(gold_real_lvl).reindex(P.index)
        if gs["1980":].isna().any():
            raise ValueError("gold valuation signal missing for months from 1980 on (World Bank data too short?)")
        gs = gs.fillna(True)                      # 1970-79: held by rule (fewer than 60 months of 1975-on history)
        w_on = {"s": split[0] * (1 - MW), "b": split[1] * (1 - MW), "g": split[2] * (1 - MW), "m": MW}
        w_off = {"s": split[0] * (1 - MW), "b": (split[1] + split[2]) * (1 - MW), "m": MW}
        cv = real(E.port_switch(P, w_on, w_off, gs))
        rv = E.mix_bar(cv, base_m)
        log(f"      valuation view (report only; gold held in {gs['1980':].mean() * 100:.0f}% of months from 1980): worst loss {pct(rv['dd'])}, "
            f"underwater {rv['uw']} months, cost {pts(rv['cost'])}/yr")
    results[name] = {**r, "pass": bool(ok)}
    log(f"      VERDICT: {'PASSES' if ok else 'fails'}")

win = E.pick_best(results)
WIN = {**SPLITS, **GOLDS}[win] if win else BASE
log(f"\n  RESULT: {'55/45 stays' if win is None else win + ' replaces 55/45'} (with {int(MW * 100)}% managed futures)")
if win and WIN[2] > 0:
    log(f"  Gold weight for the re-entry rule becomes {WIN[2] * 100:.0f}% of the stock/Treasury/gold part "
        f"({WIN[2] * (1 - MW) * 100:.2f}% of the whole portfolio); whether gold is")
    log("  held today still follows the Phase 2 valuation rule (rule freeze).")

# ======================= STEP 3: REBALANCING =======================
log("\n" + "=" * 100)
log("STEP 3: REBALANCING RULE on the winning mix (vs monthly; bar in the full sample and in each half; halves are")
log("sub-periods of one continuous run)")
wfin = {"s": WIN[0] * (1 - MW), "b": WIN[1] * (1 - MW), "g": WIN[2] * (1 - MW), "m": MW}
wfin = {k: v for k, v in wfin.items() if v > 0}
runs = {}
for rule in ["monthly", "yearly", "band"]:
    nom, trades = E.port(P, wfin, rebalance=rule, band=0.05, band_asset="s", return_trades=True)
    runs[rule] = (real(nom), trades)
rb = {}
for rule in ["yearly", "band"]:
    c, mo = runs[rule][0], runs["monthly"][0]
    r = E.mix_bar(c, mo)
    ok = r["pass"] and all(E.mix_bar(c[a:z], mo[a:z])["pass"] for a, z in E.HALVES)
    rb[rule] = {**r, "pass": bool(ok)}
for rule in ["monthly", "yearly", "band"]:
    c, trades = runs[rule]
    line = (f"  {rule:8s} trades {trades:4d}; worst loss {pct(E.max_dd(c))}; underwater {E.longest_underwater(c)} months; "
            f"return {pct(E.ann(c))}/yr; crashes " + ", ".join(f"{k} {pct(E.window_loss(c, k))}" for k in E.WINDOWS))
    if rule != "monthly":
        line += f" -> {'PASS' if rb[rule]['pass'] else 'fail'}"
    log(line)
best = E.pick_best(rb)
log(f"\n  RESULT: rebalancing rule = {best or 'monthly (unchanged)'}")

log("\n" + "=" * 100)
fw = {k: round(v * 100, 2) for k, v in wfin.items()}
log(f"FINAL MIX: stocks {fw.get('s', 0)}%, Treasuries 7-10y {fw.get('b', 0)}%, gold {fw.get('g', 0)}%"
    f"{' (held only when the valuation rule allows; otherwise in Treasuries)' if fw.get('g', 0) else ''}, "
    f"managed futures {fw.get('m', 0)}%; rebalancing {best or 'monthly'}")
log("\nNotes: managed futures are a hypothetical trend index (proxy, 1.0 pt/yr fee); live funds can lag it. Few independent")
log("crashes exist, so every result rests on a handful of episodes. CPI before 1983 overstates 1970s inflation somewhat.")
log("Gold before the GLD fund (2004) uses World Bank monthly AVERAGE prices, which smooth month-to-month moves and may")
log("make gold look steadier in crashes than month-end prices would.")
finish()
