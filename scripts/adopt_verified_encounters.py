"""Adopt the VERIFIED encounter set: the plan, minus what the navmesh refused.

    python scripts/adopt_verified_encounters.py --rows _verify/.../encounter_rows.json
    python scripts/adopt_verified_encounters.py --rows ... --write

WHY THIS EXISTS INSTEAD OF A TIGHTER PROXIMITY BAR
--------------------------------------------------
The planner decides "near reachable ground" by proximity to a lattice sampled at
60 m. That is a PREFILTER and it cannot be made exact by tightening:

    tightening 60 m -> 30 m took the failures from 7 of 440 to 3 of 320
    but one survivor sits 8.1 m from a reachable lattice cell

An 8 m miss is not a resolution problem. Those are genuine small pockets --
ground adjacent to the reachable region across a gap the agent will not cross --
and no radius separates them from legitimate ground without throwing away most
of the region. **The path query is the authority; proximity never was.**

WHY A SECOND ARTEFACT AND NOT AN EDIT IN PLACE
----------------------------------------------
Rewriting the plan would break its reproducibility: `check_plan_freshness
--reproduce` re-runs the producer and compares bytes, and a pruned plan differs
from what the planner emits. So this follows non-negotiable 20's
adopted-artefact pattern instead:

    encounters/<region>_all.json        THE PLAN -- reproducible from the
                                        planner, byte-for-byte
    encounters/<region>_verified.json   THE ADOPTED SET -- the plan minus rows
                                        the BUILT NAVMESH refused, hash-proven
                                        against both its sources

A placer reads the VERIFIED file. The plan stays a plan.

WHAT IT REFUSES
---------------
* a rows file whose encounter count does not match the plan -- they would be
  describing different runs, and pruning by index across two runs would delete
  the wrong rows
* a rows file with no verdicts at all
* dropping more than `--max-drop-frac` of the plan without being told to; a
  verifier that suddenly refuses half the encounters is a finding, not an input
"""
import argparse
import hashlib
import io
import json
import os
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO_ROOT, "scripts"))

import plan_stamp                                            # noqa: E402


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--plan", default="encounters/alpine_8k_all.json")
    ap.add_argument("--rows", required=True,
                    help="the encounter_rows.json written by "
                         "city_encounter_verify_payload")
    ap.add_argument("--max-drop-frac", type=float, default=0.10)
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args()

    ppath = os.path.join(REPO_ROOT, args.plan)
    rpath = os.path.join(REPO_ROOT, args.rows) if not os.path.isabs(args.rows) \
        else args.rows
    for p in (ppath, rpath):
        if not os.path.exists(p):
            sys.exit("REFUSE: no file at %s" % p)

    plan = json.loads(io.open(ppath, encoding="utf-8").read())
    rowsdoc = json.loads(io.open(rpath, encoding="utf-8").read())
    rows = rowsdoc.get("rows") or []
    enc = plan.get("encounters") or []

    if not rows:
        sys.exit("REFUSE: the rows file carries no verdicts. That is COULD NOT "
                 "LOOK, not 'everything passed'.")
    if len(rows) != len(enc):
        sys.exit("REFUSE: the rows file has %d verdicts and the plan has %d "
                 "encounters. They describe different runs, and pruning by "
                 "index across two runs deletes the wrong rows. Re-verify the "
                 "plan you intend to adopt." % (len(rows), len(enc)))

    verdicts = [r.get("same_island_as_player") for r in rows]
    unknown = sum(1 for v in verdicts if v is None)
    bad = [i for i, v in enumerate(verdicts) if v is not True]
    keep = [e for i, e in enumerate(enc) if verdicts[i] is True]

    frac = (len(bad) / float(len(enc))) if enc else 0.0
    print("plan            %s   %d encounters" % (args.plan, len(enc)))
    print("verdicts        %s" % os.path.relpath(rpath, REPO_ROOT))
    print("  reachable     %d" % len(keep))
    print("  refused       %d  (%.2f%%)" % (len(bad), 100.0 * frac))
    print("  UNKNOWN       %d  -- counted as refused; unknown is never yes"
          % unknown)
    print()

    if frac > args.max_drop_frac:
        print("REFUSE: dropping %.1f%% of the plan exceeds --max-drop-frac "
              "%.1f%%." % (100.0 * frac, 100.0 * args.max_drop_frac))
        print("A verifier that suddenly refuses this many encounters is a "
              "FINDING, not an input to be quietly applied. Investigate the "
              "navmesh or the plan before adopting.")
        return 3

    by_arch = {}
    for e in keep:
        by_arch[e["archetype"]] = by_arch.get(e["archetype"], 0) + 1
    print("  by archetype  %s" % json.dumps(by_arch, sort_keys=True))

    out = dict(plan)
    out["_what"] = ("The VERIFIED encounter set: the plan minus every row the "
                    "BUILT NAVMESH refused. A placer reads THIS file; "
                    "encounters/<region>_all.json is the plan and stays "
                    "byte-reproducible from its planner.")
    # !! THE PRODUCER OF THIS FILE IS THIS SCRIPT, NOT THE PLANNER.
    # `dict(plan)` inherited `_produced_by: scripts/plan_encounters.py`, so
    # check_plan_freshness --reproduce ran the PLANNER against this path and
    # reported DIFFERS -- correctly, since the planner emits 320 rows and this
    # file holds the 317 the navmesh accepted. A derived artefact that names
    # its parent's producer is claiming to be reproducible by a tool that
    # cannot produce it.
    #
    # This script takes no --out, so freshness will now report CANNOT
    # REPRODUCE, which is the honest verdict: reproducing it needs BOTH the
    # plan and the in-editor verdicts, and the verdicts come from a navmesh
    # build that no offline run can recreate. The STAMP still proves both
    # inputs are unchanged.
    out["_produced_by"] = "scripts/adopt_verified_encounters.py"
    out["_plan"] = args.plan.replace("\\", "/")
    out["_adopted_by"] = "scripts/adopt_verified_encounters.py"
    out["_verified_against"] = os.path.relpath(rpath, REPO_ROOT).replace(
        "\\", "/")
    out["_refused_by_navmesh"] = len(bad)
    out["encounters"] = keep
    out["counts"] = {"encounters": len(keep), "by_archetype": by_arch}

    dst = args.plan.replace("_all.json", "_verified.json")
    dpath = os.path.join(REPO_ROOT, dst)
    if not args.write:
        print()
        print("REPORT ONLY -- nothing written. Re-run with --write to adopt "
              "into %s" % dst)
        return 0

    # stamp against BOTH sources -- the plan and the verdicts it was pruned by
    out[plan_stamp.STAMP_KEY] = plan_stamp.stamp(out, REPO_ROOT)
    out[plan_stamp.STAMP_KEY][args.plan.replace("\\", "/")] = \
        plan_stamp.sha256_file(ppath)
    out[plan_stamp.STAMP_KEY][
        os.path.relpath(rpath, REPO_ROOT).replace("\\", "/")] = \
        plan_stamp.sha256_file(rpath)

    os.makedirs(os.path.dirname(dpath), exist_ok=True)
    io.open(dpath, "w", encoding="utf-8", newline="\n").write(
        json.dumps(out, indent=1) + "\n")
    back = json.loads(io.open(dpath, encoding="utf-8").read())
    if len(back.get("encounters") or []) != len(keep):
        sys.exit("REFUSE: wrote %d rows and read back %d" %
                 (len(keep), len(back.get("encounters") or [])))
    print()
    print("adopted %d verified encounters into %s" % (len(keep), dst))
    print("stamped against the plan AND the verdicts it was pruned by.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
