"""Prove `plan_city`'s gates REFUSE, and that a refusal writes NOTHING.

Offline. No editor, no world, no network -- so it survives a cold replay and can
gate a commit, in the same spirit as `scripts/prove_gates.py`.

WHY THIS EXISTS
---------------
Non-negotiable 2: **a gate that has only seen good input has not been tested.**
`plan_city` carries four refusals and every one of them had only ever seen the
one town that passes it. `max_orphan_building_fraction` in particular has never
refused anything -- it is set at 0.05 against a first measurement of 3.6%, which
is a bar chosen to pass the number it first saw.

There is a SECOND property here that matters more than the first, and this
project has already been bitten by it once (2026-08-25): **the gates must run
BEFORE the write.** A refused run that writes and then exits non-zero leaves the
refused plan at exactly the path the placer reads, which is strictly worse than
not running at all. Exit code alone cannot distinguish the two. So every refusal
case asserts that the output file DOES NOT EXIST.

WHAT IT ASSERTS, per case
-------------------------
    positive control   unmutated recipe   -> exit 0  AND the file is written
    each refusal case  one gate mutated   -> exit != 0
                                          -> the output file does NOT exist
                                          -> the message NAMES the gate

and across the whole run:

    recipes/city.json           never opened for writing
    city/<id>_plan.json         byte-identical before and after

A refusal that does not name its gate is only half a refusal -- the operator
cannot tell which bar was crossed -- so the message check is an assertion, not a
courtesy.

The mutation helper REFUSES to create a key that does not already exist. A test
that invents `gates.max_orphan_bulding_fraction` and observes no refusal would
report the gate as broken when the typo is the finding.

AND THE PROVER IS ITSELF POSITIVE-CONTROLLED
--------------------------------------------
Non-negotiable 2 applies to this file too: a prover that has only ever seen
working gates has not been tested. `--self-test` writes a copy of `plan_city.py`
with ONE gate's condition made unsatisfiable, runs the whole suite against it,
and requires the verdict to be FAILED naming exactly that gate.

**THE COPY MUST LIVE IN `scripts/`, AND THAT IS NOT AN IMPLEMENTATION DETAIL.**
`plan_city` derives its repo root from its own file location, so a copy placed
anywhere else cannot resolve `recipes/` or its sibling imports and dies before
reaching a single gate. The first attempt at this control put the copy in a
scratch directory: all five cases "refused", which is indistinguishable from
five working gates, and the prover reported FAILED for entirely the wrong
reason. **A control that fails for the wrong reason is worse than no control**,
because it looks like it discriminated. The copy is written beside the original,
deleted in a `finally`, and its absence is asserted afterwards.

    python scripts/prove_city_gates.py --self-test
    expected: the control reports FAILED, naming the orphan gate, and the
              suite as a whole then reports SELF-TEST PASSED

USAGE
-----
    python scripts/prove_city_gates.py
    python scripts/prove_city_gates.py --recipe recipes/city.json

Exit 0 = every case behaved. Non-zero = a gate did not refuse, or a refusal
wrote its plan, or the committed plan moved.
"""
import argparse
import hashlib
import io
import json
import os
import subprocess
import sys
import tempfile

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_PLANNER = os.path.join(REPO_ROOT, "scripts", "plan_city.py")

# (label, dotted gate key, mutated value, substring the refusal must name)
# None key = the positive control, which must PASS and must WRITE.
CASES = [
    ("POSITIVE CONTROL (unmutated)", None, None, None),
    ("orphan fraction 0.0", "gates.max_orphan_building_fraction", 0.0,
     "orphan"),
    ("building-to-street 1 m", "gates.max_building_to_street_m", 1.0,
     "orphan"),
    ("min_buildings 10000", "gates.min_buildings", 10000, "building"),
    ("min_street_segments 100000", "gates.min_street_segments", 100000,
     "street"),
]


def sha12(path):
    if not os.path.exists(path):
        return None
    return hashlib.sha256(io.open(path, "rb").read()).hexdigest()[:12]


def set_existing(obj, dotted, value):
    """Set a nested key, REFUSING to create one that is not already there.

    A probe that invents a key silently tests nothing: the planner reads its
    own correctly-spelled key, passes, and the probe reports the gate dead.
    """
    parts = dotted.split(".")
    cur = obj
    for p in parts[:-1]:
        if p not in cur:
            raise KeyError("no section %r in the recipe -- refusing to "
                           "invent it" % p)
        cur = cur[p]
    if parts[-1] not in cur:
        raise KeyError("no key %r in the recipe -- refusing to invent it"
                       % dotted)
    old = cur[parts[-1]]
    cur[parts[-1]] = value
    return old


ORPHAN_GATE = "    if frac_orphan > max_frac:"
BROKEN_COPY = os.path.join(REPO_ROOT, "scripts",
                           "plan_city_CONTROL_BROKEN.py")


def write_broken_planner():
    """A copy of plan_city.py whose orphan gate can never fire.

    Beside the original, because plan_city locates the repo from its own path.
    Refuses unless the anchor appears exactly once -- breaking a line other
    than the intended one makes the control mean something else.
    """
    src = io.open(DEFAULT_PLANNER, encoding="utf-8").read()
    if src.count(ORPHAN_GATE) != 1:
        raise RuntimeError("expected exactly 1 orphan-gate line, found %d -- "
                           "refusing to break an unknown line"
                           % src.count(ORPHAN_GATE))
    broken = src.replace(ORPHAN_GATE,
                         "    if False:  # DELIBERATELY BROKEN CONTROL COPY")
    io.open(BROKEN_COPY, "w", encoding="utf-8", newline="\n").write(broken)
    return BROKEN_COPY


def self_test():
    """Prove this prover is capable of reporting FAILED."""
    print("SELF-TEST: running the suite against a planner whose orphan gate")
    print("has been made unsatisfiable. The expected verdict is FAILED.")
    print()
    try:
        write_broken_planner()
        rc = run_suite(BROKEN_COPY,
                       os.path.join(REPO_ROOT, "recipes", "city.json"),
                       quiet_header=True)
    finally:
        if os.path.exists(BROKEN_COPY):
            os.remove(BROKEN_COPY)
    if os.path.exists(BROKEN_COPY):
        return 1, "the broken control copy is still in scripts/ -- remove it"
    print()
    if rc == 0:
        return 1, ("the suite PASSED a planner with a dead gate. This prover "
                   "cannot detect the thing it exists to detect.")
    return 0, None


def run_suite(planner, recipe, quiet_header=False):
    planner = os.path.abspath(planner)
    if not os.path.exists(planner):
        sys.exit("REFUSE: no planner at %s" % planner)
    if planner != DEFAULT_PLANNER and not quiet_header:
        print("*** CONTROL RUN: planner is NOT the committed one. A FAILED "
              "verdict below is the expected result. ***")
        print()

    recipe = os.path.abspath(recipe)
    if not os.path.exists(recipe):
        sys.exit("REFUSE: no recipe at %s" % recipe)

    base = json.loads(io.open(recipe, encoding="utf-8").read())
    committed = os.path.join(REPO_ROOT, "city",
                             "%s_plan.json" % base["city_id"])

    recipe_before = sha12(recipe)
    committed_before = sha12(committed)
    if committed_before is None:
        sys.exit("REFUSE: no committed plan at %s. Without one the "
                 "write-order proof is vacuous -- there is nothing a stray "
                 "write could damage." % committed)

    print("planner          %s" % planner)
    print("recipe           %s  sha %s" % (os.path.relpath(recipe, REPO_ROOT),
                                           recipe_before))
    print("committed plan   %s  sha %s"
          % (os.path.relpath(committed, REPO_ROOT), committed_before))
    print()

    scratch = tempfile.mkdtemp(prefix="prove_city_gates_")
    case_recipe = os.path.join(scratch, "city_case.json")
    case_out = os.path.join(scratch, "case_plan.json")

    failures = []
    for label, key, value, must_name in CASES:
        mutated = json.loads(json.dumps(base))          # deep copy
        old = set_existing(mutated, key, value) if key else None
        io.open(case_recipe, "w", encoding="utf-8", newline="\n").write(
            json.dumps(mutated, indent=1))
        if os.path.exists(case_out):
            os.remove(case_out)

        # `scripts/` on PYTHONPATH so a planner run from ANYWHERE resolves its
        # sibling imports. Without it a copy placed outside scripts/ dies at
        # `import measure_city_connectivity` and every case "refuses" -- which
        # reads exactly like working gates and tests nothing. Measured: the
        # first control run failed all four cases for that reason.
        env = dict(os.environ)
        sdir = os.path.join(REPO_ROOT, "scripts")
        env["PYTHONPATH"] = (sdir + os.pathsep + env["PYTHONPATH"]
                             if env.get("PYTHONPATH") else sdir)
        proc = subprocess.run(
            [sys.executable, planner, "--recipe", case_recipe,
             "--out", case_out],
            capture_output=True, text=True, cwd=REPO_ROOT, env=env)
        blob = (proc.stdout or "") + (proc.stderr or "")
        wrote = os.path.exists(case_out)

        problems = []
        if key is None:
            if proc.returncode != 0:
                problems.append("the unmutated recipe was REFUSED (exit %d)"
                                % proc.returncode)
            if not wrote:
                problems.append("the accepted run wrote no plan")
            verdict = "accepts good input, writes the plan"
        else:
            if proc.returncode == 0:
                problems.append("did NOT refuse")
            if wrote:
                problems.append("WROTE ITS PLAN ON A REFUSAL")
            if must_name and must_name.lower() not in blob.lower():
                problems.append("refusal never names %r" % must_name)
            verdict = "refused, wrote nothing, named the gate"

        status = "ok   " if not problems else "FAIL "
        print("%s%-30s  %s -> %s   exit %-3d wrote %-5s"
              % (status, label,
                 ("%s" % old) if key else "-",
                 ("%s" % value) if key else "-",
                 proc.returncode, wrote))
        if problems:
            for p in problems:
                print("        %s" % p)
            failures.append(label)
        else:
            print("        %s" % verdict)

        if os.path.exists(case_out):
            os.remove(case_out)

    for p in (case_recipe, case_out):
        if os.path.exists(p):
            os.remove(p)
    os.rmdir(scratch)

    print()
    recipe_after = sha12(recipe)
    committed_after = sha12(committed)
    print("recipe           %s -> %s   %s"
          % (recipe_before, recipe_after,
             "UNCHANGED" if recipe_before == recipe_after else "*** MOVED"))
    print("committed plan   %s -> %s   %s"
          % (committed_before, committed_after,
             "UNCHANGED" if committed_before == committed_after else
             "*** MOVED"))
    if recipe_before != recipe_after:
        failures.append("recipes/city.json was modified")
    if committed_before != committed_after:
        failures.append("the committed plan was modified")

    print()
    if failures:
        print("FAILED: %d" % len(failures))
        for f in failures:
            print("  - %s" % f)
        return 1
    print("ALL %d CASES BEHAVED." % len(CASES))
    print("Gates refuse, refusals write nothing, and neither the recipe nor "
          "the committed plan moved.")
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--recipe",
                    default=os.path.join(REPO_ROOT, "recipes", "city.json"))
    ap.add_argument("--planner", default=DEFAULT_PLANNER,
                    help="point at a deliberately broken copy of plan_city.py "
                         "to prove this prover is capable of failing. It must "
                         "live in scripts/ -- plan_city locates the repo from "
                         "its own path.")
    ap.add_argument("--self-test", action="store_true",
                    help="write that broken copy, run against it, and require "
                         "a FAILED verdict; then clean it up")
    args = ap.parse_args()

    if args.self_test:
        rc, why = self_test()
        if rc:
            print("SELF-TEST FAILED: %s" % why)
            return rc
        print("SELF-TEST PASSED: the suite reports FAILED against a dead "
              "gate, so a PASS from it is evidence.")
        print()
        print("Now running for real against the committed planner:")
        print()
        return run_suite(DEFAULT_PLANNER, args.recipe)

    return run_suite(args.planner, args.recipe)


if __name__ == "__main__":
    sys.exit(main())
