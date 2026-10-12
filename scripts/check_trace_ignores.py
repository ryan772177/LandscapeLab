"""check_trace_ignores.py -- every editor payload that loads world regions AND ground-traces must ignore HLOD + towns.

    python scripts/check_trace_ignores.py
    python scripts/check_trace_ignores.py --selftest

WHY (2026-10-08, the same mistake twice). The 2026-09-19b lattice fix taught that with regions loaded the
WorldPartitionHLOD proxies are resident and collidable, so a "ground" trace lands on HLOD canopy and the navmesh
projection below it misses (2802 vs 9810 reachable cells). The lesson lived in ONE payload. On 2026-10-08 the town
region payload, which never got it, reported 225 of 385 houses unreachable (truth: 385). A lesson that lives in
one file does not fire in the next; this check does.

RULE CHECKED: a payload (scripts/*.txt, scripts/payloads/*.py) that calls load_all_world_partition_regions or
load_world_partition_region_box AND line_trace_* must mention "WorldPartitionHLOD" and "LandscapeLab.TownKit".
Files listed in LEGACY are known-unguarded diagnostics (BACKLOG 2026-10-08), reported but not failed; anything
new or not listed FAILS. Exit 0 = clean, 3 = a non-legacy payload is unguarded, 6 = nothing scanned.
Scanned: scripts/*.txt, scripts/payloads/*.py and scripts/*.py (inline payloads in drivers). LIMIT: this is a
TEXT check -- a comment naming the class satisfies it; it proves the guard was considered, not that it works.
"""
import argparse
import glob
import io
import os
import re
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOADS = re.compile(r"load_all_world_partition_regions|load_world_partition_region_box")
TRACE = re.compile(r"line_trace_(single|multi)")
NEEDS = ("WorldPartitionHLOD", "LandscapeLab.TownKit")
# known-unguarded legacy diagnostics, 2026-10-08 -- each needs the guard before it is trusted again
LEGACY = {"_t6_nav_conn_payload.txt", "_t6_nav_diag_payload.txt", "city_barrier_probe_payload.txt",
          "city_disputed_rows_payload.txt", "city_nav_grid_payload.txt", "city_path_chain_payload.txt",
          "city_recheck_unreachable_payload.txt", "city_relay_sweep_payload.txt", "city_rim_sweep_payload.txt",
          "spawn_cone_payload.txt", "street_edge_grounding_payload.txt", "street_seat_convention_payload.txt",
          "street_seat_engine_test_payload.txt",
          # a DRIVER with an inline payload: loads every region and traces with an EMPTY ignore list at the
          # town centre -- re-running it would seat the PlayerStart on a kit roof or HLOD canopy (BACKLOG)
          "place_player_start.py"}


def scan(files):
    bad, legacy, scanned = [], [], 0
    for f in files:
        src = io.open(f, encoding="utf-8", errors="replace").read()
        if not (LOADS.search(src) and TRACE.search(src)):
            continue
        scanned += 1
        # the town guard may be the literal tag OR a TOWN_TAGS list passed in at runtime (refused on 0 matches)
        missing = [n for n in NEEDS if n not in src and not (n == "LandscapeLab.TownKit" and "TOWN_TAGS" in src)]
        if missing:
            (legacy if os.path.basename(f) in LEGACY else bad).append((os.path.basename(f), missing))
    return bad, legacy, scanned


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args(argv)
    if a.selftest:
        import tempfile
        # scratch under the repo's _verify/, removed on exit (standing rule 1; re-audit 2026-10-10 B1 class)
        with tempfile.TemporaryDirectory(dir=os.path.join(REPO, "_verify")) as d:
            p_bad = os.path.join(d, "new_bad_payload.txt")
            p_ok = os.path.join(d, "new_ok_payload.txt")
            with io.open(p_bad, "w") as fh:
                fh.write("load_all_world_partition_regions()\nline_trace_single(...)\n")
            with io.open(p_ok, "w") as fh:
                fh.write("load_all_world_partition_regions()\nline_trace_single(...)\n"
                         "WorldPartitionHLOD LandscapeLab.TownKit\n")
            bad, _l, n = scan([p_bad, p_ok])
        ok = n == 2 and [b[0] for b in bad] == ["new_bad_payload.txt"]
        print("SELFTEST %s (scanned %d, flagged %s)" % ("PASSED" if ok else "FAILED", n, bad))
        return 0 if ok else 3
    # inline payloads live inside driver .py files too (audit 2026-10-08 F7); the checker itself is excluded
    files = (glob.glob(os.path.join(REPO, "scripts", "*.txt")) + glob.glob(os.path.join(REPO, "scripts", "payloads", "*.py"))
             + [f for f in glob.glob(os.path.join(REPO, "scripts", "*.py"))
                if os.path.basename(f) != "check_trace_ignores.py"])
    bad, legacy, n = scan(files)
    print("region-loading + tracing payloads scanned: %d" % n)
    for name, miss in legacy:
        print("  legacy (BACKLOG) %-40s missing %s" % (name, miss))
    for name, miss in bad:
        print("  FAIL            %-40s missing %s" % (name, miss))
    if n == 0:
        print("REFUSE: nothing scanned -- not a pass")
        return 6
    return 3 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
