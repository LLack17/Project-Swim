# Phase 3 shortlist clean-up and robustness check (rules: docs/phase3_screen_rules.md, amendments of 2026-10-28).
# Usage, from the repo root, after screen.py:  python scripts/phase3/shortlist_check.py
# Uses the statements already downloaded by screen.py (cache), plus SEC filing lists (free).
#
# Step 1 (clean-up): partnerships out; for the top candidates, SEC 8-K filings with Item 2.01 (completed acquisition
#   or disposition) after the company's latest fiscal year-end are listed. Every flagged company needs a decision
#   in data/phase3/corporate_actions.csv (columns: symbol, decision = replace or keep, reason, source). If any flag
#   has no decision, the script stops and lists them. Replaced companies give their place to the next-best company.
# Step 2 (robustness, labels only): Magic Formula, Piotroski F-score and gross profitability, each a percentile rank
#   among the companies that passed the filters; robust = top 30% on 2+ of 3, fragile = on none, mixed otherwise.
# Output: data/phase3/shortlist_check_results.txt and data/phase3/shortlist_final.csv.
import os
import sys
import pandas as pd

sys.path.insert(0, "scripts/phase3")
import screen_engine as S  # noqa: E402
import sources as D  # noqa: E402

OUT = "data/phase3"
N_CHECK, CHECK_PER_SECTOR = 60, 6   # candidates checked for corporate actions: room for 2 replacements per sector
lines = []


def log(s=""):
    print(s)
    lines.append(s)


def finish():
    with open(f"{OUT}/shortlist_check_results.txt", "w") as f:
        f.write("\n".join(lines) + "\n")
    print(f"\nSaved {OUT}/shortlist_check_results.txt")


def _on_error(exc_type, exc, tb):
    if exc_type is not SystemExit:
        log(f"\nERROR, stopped: {exc_type.__name__}: {exc}")
        finish()
    sys.__excepthook__(exc_type, exc, tb)


sys.excepthook = _on_error


def statements(sym):
    key = lambda x: x.get("date", "")  # noqa: E731
    return [sorted(D.fmp(e, symbol=sym, period="annual", limit=3) or [], key=key, reverse=True)
            for e in ["income-statement", "balance-sheet-statement", "cash-flow-statement"]]


SC = pd.read_csv(f"{OUT}/screen_scores.csv")
original = S.shortlist(SC)
log("PHASE 3 SHORTLIST CHECK: clean-up and robustness")
log("=" * 100)

# ---------------- alternative measures for every scored company ----------------
alt = []
for _, r in SC.iterrows():
    inc, bal, cf = statements(r.symbol)
    ey, roc = S.magic_formula_inputs(inc[0] if inc else None, bal[0] if bal else None, r.marketCap)
    alt.append({"symbol": r.symbol, "ey": ey, "roc": roc, "fscore": S.piotroski(inc, bal, cf),
                "gp": S.gross_profitability(inc[0] if inc else None, bal[0] if bal else None),
                "fye": inc[0].get("date") if inc else None})
A = SC.merge(pd.DataFrame(alt), on="symbol")
A["magic"] = (S.pct_rank(A.ey) + S.pct_rank(A.roc)) / 2
A["piotroski"] = S.pct_rank(A.fscore)
A["gross_prof"] = S.pct_rank(A.gp)
log(f"Companies scored: {len(A)}; rankable on Magic Formula {A.magic.notna().sum()}, Piotroski {A.piotroski.notna().sum()}, "
    f"gross profitability {A.gross_prof.notna().sum()}")
for c_, lab_ in [("magic", "Magic Formula"), ("piotroski", "Piotroski"), ("gross_prof", "gross profitability")]:
    if A[c_].notna().mean() < 0.5:
        raise ValueError(f"{lab_} could be computed for under half the companies: an FMP field name is probably different")

# ---------------- step 1: clean-up ----------------
log("\nSTEP 1: CLEAN-UP")
lp = A[A.companyName.map(S.is_partnership)]
log(f"  Partnerships removed: {', '.join(f'{x.symbol} ({x.companyName})' for x in lp.itertuples()) or 'none'}")
B = A[~A.symbol.isin(lp.symbol)]
cands = S.shortlist(B, n=N_CHECK, per_sector=CHECK_PER_SECTOR)
ciks = D.sec_ciks()
flags = {}
for r in cands.itertuples():
    cik = ciks.get(r.symbol)
    if cik is None or not r.fye:
        log(f"  {r.symbol}: no SEC filing list or fiscal year-end; check by hand")
        flags[r.symbol] = [("?", "", "no filing list", "")]
        continue
    hits = S.item_201_after(D.sec(f"https://data.sec.gov/submissions/CIK{cik:010d}.json"), r.fye)
    if hits:
        flags[r.symbol] = hits
dec_path = f"{OUT}/corporate_actions.csv"
dec = pd.read_csv(dec_path) if os.path.exists(dec_path) else pd.DataFrame(columns=["symbol", "decision", "reason", "source"])
log(f"  Top {len(cands)} candidates (up to {CHECK_PER_SECTOR} per sector) checked for completed acquisitions/dispositions (8-K Item 2.01) after their latest fiscal year-end:")
for s, hits in flags.items():
    d = dec[dec.symbol == s]
    when = "; ".join(f"{h[0]} {h[1]}" for h in hits)
    log(f"    {s:6s} {when} -> " + (f"{d.decision.iloc[0].upper()}: {d.reason.iloc[0]} ({d.source.iloc[0]})" if len(d) else "NO DECISION YET"))
extra = dec[~dec.symbol.isin(list(flags))]
for d in extra.itertuples():
    log(f"    {d.symbol:6s} (decided without an 8-K flag) -> {d.decision.upper()}: {d.reason} ({d.source})")
missing = [s for s in flags if s not in set(dec.symbol)]
if missing:
    log(f"\nSTOPPED: decide {missing} in {dec_path} (symbol, decision = replace or keep, reason, source), then rerun.")
    finish()
    raise SystemExit(1)
bad = set(dec.decision.str.lower()) - {"replace", "keep"}
if bad:
    raise ValueError(f"decisions must be 'replace' or 'keep'; found {bad}")
out = set(dec[dec.decision.str.lower() == "replace"].symbol)
C = B[~B.symbol.isin(out)]
final = S.shortlist(C)
if len(final) < 30:
    raise ValueError(f"only {len(final)} names after clean-up")
gone = [s for s in original.symbol if s not in set(final.symbol)]
new = [s for s in final.symbol if s not in set(original.symbol)]
log(f"\n  Removed from the original top 30: {', '.join(gone) or 'none'}")
log(f"  Added (next-best eligible): {', '.join(new) or 'none'}")
unchecked = [s for s in final.symbol if s not in set(cands.symbol)]
if unchecked:
    raise ValueError(f"{unchecked} entered the list but were not among the {N_CHECK} checked; raise N_CHECK")

# ---------------- step 2: robustness ----------------
final["label"] = [S.robustness_label([a, b, c]) for a, b, c in zip(final.magic, final.piotroski, final.gross_prof)]
log("\nSTEP 2: ROBUSTNESS (labels only; the main score decides the list)")
log(f"  {'#':>3s} {'symbol':7s} {'company':30s} {'sector':22s} {'score':>6s} {'magic':>6s} {'F(0-9)':>7s} {'F rank':>7s} {'grossP':>7s}  label")
fmt = lambda v: "   n/a" if pd.isna(v) else f"{v:6.1f}"  # noqa: E731
for k, r in final.iterrows():
    log(f"  {k + 1:3d} {r.symbol:7s} {str(r.companyName)[:30]:30s} {str(r.sector)[:22]:22s} {r.combined:6.1f} {fmt(r.magic)} "
        f"{'   n/a' if pd.isna(r.fscore) else f'{int(r.fscore):6d}'} {fmt(r.piotroski):>7s} {fmt(r.gross_prof):>7s}  {r.label}")
counts = final.label.value_counts()
log(f"\n  Robust {counts.get('robust', 0)}, mixed {counts.get('mixed', 0)}, fragile {counts.get('fragile', 0)}")
for col, lab in [("magic", "Magic Formula"), ("piotroski", "Piotroski F-score"), ("gross_prof", "Gross profitability")]:
    top = C.sort_values(col, ascending=False).head(30)
    log(f"  Overlap of {lab}'s own top 30 with the shortlist: {len(set(top.symbol) & set(final.symbol))} of 30")
final[["symbol", "companyName", "sector", "marketCap", "value", "quality", "low_vol", "combined", "magic", "fscore",
       "piotroski", "gross_prof", "label"]].to_csv(f"{OUT}/shortlist_final.csv", index=False)
log(f"\nSaved {OUT}/shortlist_final.csv. Notes: Piotroski ties are common (scores 0-9), so its ranks bunch together;")
log("labels flag how much a name depends on our own score, they do not remove anyone.")
finish()
