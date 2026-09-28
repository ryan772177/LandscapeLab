#!/usr/bin/env python3
"""check_recipe_lods.py -- recipe == asset for tree LOD screen sizes (Brief 5).

Compares recipes/alpine_8k.json foliage.species[].lod_screen_sizes against a
COLD asset probe: research/brief5/input/tree_lod_probe_cold.json, read by
get_lod_screen_sizes in a FRESH editor process DISTINCT from the one that wrote
the meshes (Brief 5 R1). Exit 0 if every species the cold probe covers matches
(per-LOD, tol 1e-3), non-zero + a named diff otherwise.

WHY THE PROBE MUST BE COLD (Brief 5 R5). The old probe (tree_lod_probe_t3.json)
was a SAME-SESSION in-memory readback that was never persisted -- T3's save was a
false-success no-op (C1), so the recipe matched a probe of values that never
reached disk, and this check passed GREEN over an asset that on disk still
carried the pre-hold sizes. A same-process readback proves memory, not disk.
This check now REFUSES any probe that is not stamped cold_readback=True AND
distinct_from_apply=True, so it can only pass on a value that survived an editor
restart in a different process.

Recipe tree species that carry lod_screen_sizes but are ABSENT from the cold
probe (i.e. were not part of the hold) are reported as not-cold-verified and do
NOT gate the run -- stated plainly (rule 10), not silently dropped.

`--self-test`: proves the checker fails on a seeded mismatch and refuses a
non-cold probe (three directions + provenance).
"""
import json
import os
import sys

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
RECIPE = os.path.join(REPO, "recipes", "alpine_8k.json")
PROBE = os.path.join(REPO, "research", "brief5", "input", "tree_lod_probe_cold.json")
TOL = 1e-3


def _eq(a, b):
    if a is None or b is None or len(a) != len(b):
        return False
    return all(abs(float(x) - float(y)) < TOL for x, y in zip(a, b))


def cold_ok(probe):
    """A probe is usable only if it was read cold in a distinct process."""
    return (probe.get("cold_readback") is True
            and probe.get("distinct_from_apply") is True)


def compare(recipe, probe):
    asset = {m["species"]: [float(x) for x in (m.get("screen_sizes") or [])]
             for m in probe["meshes"]}
    diffs = []
    n = 0
    not_verified = []
    for s in recipe["foliage"]["species"]:
        name = s.get("name")
        rec = s.get("lod_screen_sizes")
        if rec is None:
            continue
        if name not in asset:
            not_verified.append(name)   # has a recipe claim, not in the cold probe
            continue
        n += 1
        if not _eq(rec, asset[name]):
            diffs.append("%s: recipe %s != asset %s" % (name, rec, asset[name]))
    return n, diffs, not_verified


def main():
    recipe = json.load(open(RECIPE, encoding="utf-8-sig"))
    if not os.path.exists(PROBE):
        print("check_recipe_lods: REFUSE -- no cold probe at %s "
              "(run research/brief5/scripts/r_apply.py)" % PROBE)
        return 2
    probe = json.load(open(PROBE, encoding="utf-8"))
    if not cold_ok(probe):
        print("check_recipe_lods: REFUSE -- probe is not a cold readback "
              "(cold_readback=%r, distinct_from_apply=%r). A same-process probe "
              "proves memory, not disk (Brief 5 C1)."
              % (probe.get("cold_readback"), probe.get("distinct_from_apply")))
        return 2
    n, diffs, not_verified = compare(recipe, probe)
    if not_verified:
        print("check_recipe_lods: NOTE -- recipe tree species with lod_screen_sizes "
              "NOT in the cold probe (not part of the hold, not verified this "
              "session): %s" % ", ".join(not_verified))
    if n == 0:
        print("check_recipe_lods: REFUSE -- 0 tree species compared against the "
              "cold probe")
        return 2
    if diffs:
        print("check_recipe_lods: FAIL (%d cold-compared)" % n)
        for d in diffs:
            print("  " + d)
        return 1
    print("check_recipe_lods: OK -- recipe == COLD asset for %d tree species "
          "(probe PID %s, distinct from apply PID %s)"
          % (n, probe.get("cold_editor_pid"), probe.get("apply_pid")))
    return 0


def selftest():
    recipe = json.load(open(RECIPE, encoding="utf-8-sig"))
    probe = json.load(open(PROBE, encoding="utf-8"))
    assert cold_ok(probe), "live probe must be a cold readback"
    n, diffs, _nv = compare(recipe, probe)
    assert n >= 2 and not diffs, "live recipe/cold-probe must match, got %s" % diffs
    # direction 2: a changed value must fail
    import copy
    bad = copy.deepcopy(recipe)
    for s in bad["foliage"]["species"]:
        if s.get("name") == "ConiferPine":
            s["lod_screen_sizes"][-1] += 0.5
    _n, d2, _ = compare(bad, probe)
    assert d2, "a changed screen size must be caught"
    # direction 3: a length change must fail
    bad2 = copy.deepcopy(recipe)
    for s in bad2["foliage"]["species"]:
        if s.get("name") == "SpruceSub":
            s["lod_screen_sizes"] = s["lod_screen_sizes"][:-1]
    _n2, d3, _ = compare(bad2, probe)
    assert d3, "a length change must be caught"
    # direction 4 (provenance): a non-cold probe must be refused
    warm = copy.deepcopy(probe)
    warm["cold_readback"] = False
    assert not cold_ok(warm), "a non-cold probe must be refused"
    warm2 = copy.deepcopy(probe)
    warm2.pop("distinct_from_apply", None)
    assert not cold_ok(warm2), "a probe with no distinct-process stamp must be refused"
    print("check_recipe_lods selftest OK: cold match passes; value+length mismatch "
          "fail; non-cold / non-distinct probe refused")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--self-test":
        selftest()
        sys.exit(0)
    sys.exit(main())
