# Tests for scripts/launch/order_sheet.py. Run from the repo root:  python scripts/launch/test_order_sheet.py
import sys

sys.path.insert(0, "scripts/launch")
import order_sheet as O  # noqa: E402

NOV11 = {"IEF": 90.94, "KMLM": 29.26, "GNTX": 19.58, "EOG": 153.77, "ITW": 288.72, "INGR": 92.83, "MA": 660.73,
         "VTI": 374.25}


def test_nov11_plan_passes():
    rows, checks, held, cash, spent = O.build(NOV11)
    assert all(c[3] == "PASS" for c in checks), checks
    sh = {r["ticker"]: r["shares"] for r in rows}
    assert sh == {"IEF": 4700, "KMLM": 1708, "GNTX": 2055, "EOG": 261, "ITW": 139, "INGR": 433, "MA": 45, "VTI": 887}
    assert 0 <= cash < NOV11["VTI"]                      # VTI absorbs everything but less than one share
    assert "CPRT" not in sh                                # Copart waits for Nov 19
    assert round(sum(held.values())) == 331_500


def test_never_overspends_with_odd_prices():
    for bump in (0.5, 0.97, 1.03, 2.0):
        px = {t: p * bump for t, p in NOV11.items()}
        rows, checks, held, cash, spent = O.build(px)
        assert cash >= 0 and spent <= O.CAPITAL


def test_detects_sector_breach():
    saved = O.PLAN["CPRT"]
    O.PLAN["CPRT"] = (saved[0], saved[1], "Energy", 0.13, 0.0, saved[5])   # fake: Copart 13% in Energy
    try:
        _, checks, *_ = O.build(NOV11)
        res = {c[0]: c[3] for c in checks}
        assert res["Largest stock at full size"] == "FAIL"
    finally:
        O.PLAN["CPRT"] = saved


def test_max_limit_above_reference():
    rows, *_ = O.build(NOV11)
    assert all(r["max_limit"] >= r["ref_price"] for r in rows)


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("PASS", name)
