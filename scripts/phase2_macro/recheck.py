# Test 32: recheck the close calls on the rebuilt (v2) data from Test 31.
# Run from the repo root (after data_check.py):  python scripts/phase2_macro/recheck.py > data/phase2_macro/recheck_results.txt
#
# Pre-committed flip rule (set 2026-10-07, before running): every earlier decision stands unless the v2 data flips the
# result of a pre-committed rule; then the rule's new result is followed.
#   32a Split (Test 24 rule, Trigger 2 off): the most stocks whose median max drawdown with a 6-industry stock sleeve
#       is no deeper than the plain index 60/40 (no triggers, no gold). Was 55/40/5.
#   32b Gold vs 10% more Treasuries (Test 22 reading guide; gold's decision was a judgment call, so informational).
#   32c Trigger 1 in the US (static vs revised vs real-time inflation; informational, the decision is Test 28).
import os
import sys
import numpy as np
import pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import load_v2, french, t1_states, final_port, max_dd, ann, stats, real

rng = np.random.default_rng(32)
M = load_v2()
D = M.dropna(subset=["gold"]).copy()          # 1975 on
idx = D.index
t1 = t1_states(M.infl.shift(2))
t1 = pd.Series(t1, index=M.index).reindex(idx).values
print(f"v2 data (bonds: estimate then IEF; gold: averages then GLD): {idx[0].date()} to {idx[-1].date()}, {len(D)} months\n")

# ---------------- 32a ----------------
ind = french("49_Industry_Portfolios") / 100
ind = ind.reindex(idx)
ind = ind.loc[:, (ind > -0.99).all() & ind.notna().all()]
IND = ind.values
ref = 0.6 * D.stocks.values + 0.4 * D.bonds.values
ref_dd = max_dd(ref) * 100
splits = [(0.60, 0.35), (0.57, 0.38), (0.55, 0.40), (0.50, 0.45)]
name = lambda s, b: f"{int(round(s * 100))}/{int(round(b * 100))}/5"
print(f"TEST 32a: split on v2 data. Reference plain 60/40 max drawdown {ref_dd:.1f}% (was -28.6% on v1)")
draws = [rng.choice(IND.shape[1], 6, replace=False) for _ in range(1000)]
eqs = [IND[:, d].mean(axis=1) for d in draws]
pick = "50/45/5"
res = {}
for s, b in splits:
    mk = final_port(D, t1, s=s, b=b)
    dds = [max_dd(s * e + b * (1 - 0.5 * t1) * D.bonds.values + b * 0.5 * t1 * D.cash.values + 0.05 * D.gold.values) * 100 for e in eqs]
    res[name(s, b)] = np.median(dds)
    print(f"  {name(s, b):<8} whole market {stats(mk)['max_dd_%']:6.1f}%, six industries median {np.median(dds):6.1f}% [bad draw {np.percentile(dds, 10):6.1f}%]")
for s, b in splits:
    if res[name(s, b)] >= ref_dd:
        pick = name(s, b)
        break
print(f"  DECISION (Test 24 rule): base split {pick}  ->  {'unchanged' if pick == '55/40/5' else 'FLIPPED from 55/40/5'}")

# ---------------- 32d (added 2026-10-07 after Tests 27-28 removed gold and made Trigger 1 watch-only) ----------------
# Same Test 24 rule, applied to the portfolio as it now stands: stocks / Treasuries only, static, no triggers, no gold.
print("\nTEST 32d: split for the current portfolio (static, no gold, no triggers), same Test 24 rule")
pick2 = "50/50"
res2 = {}
for s_, b_ in [(0.60, 0.40), (0.57, 0.43), (0.55, 0.45), (0.50, 0.50)]:
    lab = f"{int(round(s_ * 100))}/{int(round(b_ * 100))}"
    dds = [max_dd(s_ * e + b_ * D.bonds.values) * 100 for e in eqs]
    res2[lab] = np.median(dds)
    print(f"  {lab:<6} whole market {max_dd(s_ * D.stocks.values + b_ * D.bonds.values) * 100:6.1f}%, six industries median {np.median(dds):6.1f}% [bad draw {np.percentile(dds, 10):6.1f}%]")
for lab, v in res2.items():
    if v >= ref_dd:
        pick2 = lab
        break
print(f"  DECISION (Test 24 rule): {pick2} stocks/Treasuries")

# ---------------- 32b ----------------
core = 0.6 * D.stocks.values + 0.4 * (1 - 0.5 * t1) * D.bonds.values + 0.4 * 0.5 * t1 * D.cash.values
runs = {"Core (60/40 + Trigger 1)": core, "+10% Treasuries": 0.9 * core + 0.1 * D.bonds.values,
        "+10% cash": 0.9 * core + 0.1 * D.cash.values, "+10% gold": 0.9 * core + 0.1 * D.gold.values}
print("\nTEST 32b: gold vs more Treasuries on v2 data (Test 22 setup, Trigger 2 off)")
print(pd.DataFrame({k: stats(v) for k, v in runs.items()}).T.to_string())
halves = [idx.year <= 2000, idx.year >= 2001]
gm, tm = runs["+10% gold"], runs["+10% Treasuries"]
dd_gain = (max_dd(gm) - max_dd(tm)) * 100
cost = (ann(tm) - ann(gm)) * 100
both = all(max_dd(gm[h]) > max_dd(tm[h]) for h in halves)
print(f"  Reading guide: drawdown {dd_gain:+.1f} pts (needs >= +1), return cost {cost:+.2f} (needs <= 0.5), both halves {both} -> "
      f"{'FAVORS GOLD' if (dd_gain >= 1 and cost <= 0.5 and both) else 'FAVORS TREASURIES (or neither)'}  (was 'neither' on v1)")
print(f"  Monthly correlation: gold-stocks {np.corrcoef(D.gold, D.stocks)[0, 1]:.2f}, gold-bonds {np.corrcoef(D.gold, D.bonds)[0, 1]:.2f} (v1: -0.03, 0.05)")

# ---------------- 32c ----------------
print("\nTEST 32c: Trigger 1 in the US on v2 data, 55/40/5")
krt = M.infl_rt.shift(1)
known_mix = krt.where(krt.notna(), M.infl.shift(2))           # real-time where vintages exist, revised before
t1_rt = pd.Series(t1_states(known_mix), index=M.index).reindex(idx).values
rows = {}
for lab, stt in [("Static 55/40/5", np.zeros(len(idx))), ("Trigger 1, revised data", t1), ("Trigger 1, real-time where available", t1_rt)]:
    r = final_port(D, stt)
    rr = real(r, D.cpi_m.values)
    rows[lab] = {**stats(r), "real_max_dd_%": round(max_dd(rr) * 100, 1),
                 "2022_%": round(((1 + pd.Series(r, index=idx)["2022"]).prod() - 1) * 100, 1)}
print(pd.DataFrame(rows).T.to_string())
act = max_dd(final_port(D, t1)) - max_dd(final_port(D, np.zeros(len(idx))))
sims = [max_dd(final_port(D, np.roll(t1, int(rng.integers(24, len(t1) - 24))))) - max_dd(final_port(D, np.zeros(len(idx)))) for _ in range(500)]
print(f"  Drawdown gain from Trigger 1 (revised): {act * 100:+.1f} pts; random timing matched it {(np.array(sims) >= act).mean() * 100:.0f}% of the time")
print("\n  Next: python scripts/phase2_macro/final_tests.py (Tests 27-30, on v2 data)")
