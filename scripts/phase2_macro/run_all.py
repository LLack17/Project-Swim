# Reproduce Phase 2. Run from the repo root in the project-swim environment (FRED key in .env).
#   python scripts/phase2_macro/run_all.py          Tests 27-32 and the charts (v2 data; a few minutes)
#   python scripts/phase2_macro/run_all.py --all    also Tests 1-26 (v1 data; slower)
import subprocess
import sys

D = "scripts/phase2_macro"
R = "data/phase2_macro"
V1 = [  # (script, args, output file or None)
    ("regimes.py", [], None), ("regimes2.py", [], None), ("quadrant_returns.py", [], None), ("bonds.py", [], None),
    ("robustness.py", [], "robustness_results.txt"), ("cross_country.py", [], "cross_country_results.txt"),
    ("cross_country_rule.py", [], "cross_country_rule_results.txt"), ("inflation_leg.py", [], "inflation_leg_results.txt"),
    ("trigger_interaction.py", [], "trigger_interaction_results.txt"), ("trigger2_hold.py", [], "trigger2_hold_results.txt"),
    ("gold_tests.py", [], "gold_tests_results.txt"), ("split_test.py", [], "split_test_results.txt"),
    ("split_test.py", ["--no-t2"], "split_test_no_t2_results.txt"), ("cross_country_oos.py", [], "cross_country_oos_results.txt"),
]
V2 = [
    ("data_check.py", [], "data_check_results.txt"), ("recheck.py", [], "recheck_results.txt"),
    ("final_tests.py", [], "final_tests_results.txt"), ("charts.py", [], None),
]
jobs = (V1 if "--all" in sys.argv else []) + V2
for script, args, out in jobs:
    print(f"running {script} {' '.join(args)}".strip(), flush=True)
    cmd = [sys.executable, f"{D}/{script}"] + args
    if out:
        with open(f"{R}/{out}", "w") as fh:
            rc = subprocess.run(cmd, stdout=fh).returncode
    else:
        rc = subprocess.run(cmd).returncode
    if rc != 0:
        sys.exit(f"{script} failed (exit {rc}); stopping.")
print("done")
