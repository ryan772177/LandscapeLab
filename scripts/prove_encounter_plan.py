"""Prove `plan_encounters` can SUCCEED, and re-verify the plan it produces.

Offline. No editor, no world, no writes to any tracked file.

WHY THIS EXISTS
---------------
**`plan_encounters`' success path is unexecuted under the corrected method.**
The committed `encounters/alpine_8k_all.json` was written before the
availability denominator was fixed; since the fix the planner has only ever
REFUSED, correctly, because the starting basin cannot hold an encounter. So the
gates are well tested and the half that writes a plan has never run.

This project has been bitten by unexecuted success paths before -- the first
call of `create_landscape_from_heightmap` and of `build_landscape_nanite` were
both into code that compiled, was reflected, and had never once produced its
output. A planner whose only observed behaviour is refusal is in that class.

THIS IS A SYNTHETIC WORLD AND SAYS SO
-------------------------------------
It widens the area box to 3 km and relaxes the reachable-proximity prior, IN A
COPY of the recipe. **That does NOT mean the real basin can hold encounters --
it cannot, and the refusal there is the correct answer.** What this proves is
that the planner's placement, separation, archetype selection, gate arithmetic
and write path all work when a world permits them.

AND IT RE-CHECKS THE PLAN FROM ITS OUTPUT + THE RECIPE
------------------------------------------------------
The planner asserts its own invariants internally and then reports success.
This re-drives the checks from the produced plan against the RECIPE. Read
honestly (non-negotiable 8 / rule 0), they fall in THREE classes and the
independence is only partial:

  INDEPENDENT recipe cross-checks (compared against `rec`, not a planner
  field): eligibility (elevation >= archetype min_elevation_m), party size
  (within the archetype's inclusive range), count (formula re-derived here
  and compared to the binding bar).

  SHARED-INSTRUMENT geometry -- `city_shapes`/`inside_any`/
  `required_separation_cm` are IMPORTED from plan_encounters, so per rule 0
  this is ONE instrument, not two; only the distance/containment arithmetic
  is re-driven from the OUTPUT rows: separation (every pair, against
  aggro+leash of the LARGER) and settlement (no row inside the town's
  oriented rectangles + margin), plus spawn safety.

  READ-BACK of planner-recorded fields -- slope (`r["slope_deg"]` vs the
  plan's own walkable bar) and elevation (`r["elevation_m"]`) are NOT
  re-derived from the terrain; these catch an internally INCONSISTENT plan,
  not a mis-derived slope/elevation.

The value is catching a plan that disagrees with the recipe or with itself,
not re-deriving the terrain from scratch.

DETERMINISM AND A NEGATIVE CONTROL
----------------------------------
Pipeline rule 3: re-running a recipe rebuilds deterministically. Two runs of the
same synthetic recipe must be byte-identical.

And the suite carries its own refusal case -- separation raised until no plan
can satisfy it -- asserting the planner REFUSES and, as everywhere else in this
repo, that the refusal WROTE NOTHING.

USAGE
-----
    python scripts/prove_encounter_plan.py
    python scripts/prove_encounter_plan.py --half-cm 150000 --prox-m 3000

Exit 0 = the success path works and every re-checked invariant holds.
Exit 1 = a gate failed, determinism broke, or a re-checked invariant did
         not hold (the problems are printed).
"""
import argparse
import hashlib
import io
import json
import math
import os
import subprocess
import sys
import tempfile

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO_ROOT, "scripts"))

PLANNER = os.path.join(REPO_ROOT, "scripts", "plan_encounters.py")
RECIPE = os.path.join(REPO_ROOT, "recipes", "encounters.json")

# The town centre, so the synthetic box is centred where the terrain is known.
TOWN_CM = (-210800.0, 278800.0)


def sha12(path):
    return hashlib.sha256(io.open(path, "rb").read()).hexdigest()[:12]


def run_planner(recipe_path, out_path):
    env = dict(os.environ)
    sdir = os.path.join(REPO_ROOT, "scripts")
    env["PYTHONPATH"] = (sdir + os.pathsep + env["PYTHONPATH"]
                         if env.get("PYTHONPATH") else sdir)
    p = subprocess.run([sys.executable, PLANNER, "--recipe", recipe_path,
                        "--out", out_path],
                       capture_output=True, text=True, cwd=REPO_ROOT, env=env)
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def synth_recipe(base, half_cm, prox_m, sep_scale=1.0):
    r = json.loads(json.dumps(base))
    cx, cy = TOWN_CM
    r["area"]["min_cm"] = [cx - half_cm, cy - half_cm]
    r["area"]["max_cm"] = [cx + half_cm, cy + half_cm]
    r["exclusions"]["max_distance_from_reachable_m"] = prox_m
    if sep_scale != 1.0:
        for a in r["archetypes"]:
            a["aggro_radius_m"] = a["aggro_radius_m"] * sep_scale
            a["leash_radius_m"] = a["leash_radius_m"] * sep_scale
    return r


def reverify(plan, rec):
    """Re-check the plan's invariants from the OUTPUT, not from the planner."""
    from plan_encounters import (city_shapes, inside_any,
                                 required_separation_cm)

    problems = []
    rows = plan.get("encounters", [])
    if not rows:
        return ["the plan carries no encounters at all"]

    arche = {a["name"]: a for a in rec["archetypes"]}

    # 1. separation, per pair, against the LARGER of the two
    worst = None
    for i in range(len(rows)):
        for j in range(i + 1, len(rows)):
            a, b = rows[i], rows[j]
            need = required_separation_cm(arche[a["archetype"]],
                                          arche[b["archetype"]])
            d = math.hypot(a["loc_cm"][0] - b["loc_cm"][0],
                           a["loc_cm"][1] - b["loc_cm"][1])
            if worst is None or (d - need) < worst[0]:
                worst = (d - need, a["archetype"], b["archetype"], d, need)
            if d < need:
                problems.append("pair %d/%d %.0f cm apart, needs %.0f"
                                % (i, j, d, need))
    if worst is None:
        # A single-row plan has no pair to check; worst stays None and
        # indexing it below would crash. Report the empty sample (NN13)
        # rather than either passing silently or dying on a TypeError.
        print("      separation   only %d row(s); no pair to check"
              % len(rows))
    else:
        print("      separation   tightest pair %.0f cm against a required %.0f "
              "(%s vs %s), margin %+.0f cm"
              % (worst[3], worst[4], worst[1], worst[2], worst[0]))

    # 2. settlement -- rebuilt from the committed city plan, one declaration
    ex = rec["exclusions"]["settlement"]
    plan_path = os.path.join(REPO_ROOT, ex["from_city_plan"])
    city = json.loads(io.open(plan_path, encoding="utf-8").read())
    shapes = city_shapes(city, ex["building_margin_m"] * 100.0,
                         ex["street_margin_m"] * 100.0)
    inside = [i for i, r in enumerate(rows)
              if inside_any(shapes, r["loc_cm"][0], r["loc_cm"][1])]
    if inside:
        problems.append("%d encounters inside the settlement" % len(inside))
    print("      settlement   %d of %d rows inside the town's %d shapes"
          % (len(inside), len(rows), len(shapes)))

    # 3. the spawn-safe radius
    ps = plan.get("player_start_cm")
    if ps:
        safe = float(rec["exclusions"]["player_start_safe_radius_m"]) * 100.0
        near = [r for r in rows
                if math.hypot(r["loc_cm"][0] - ps[0],
                              r["loc_cm"][1] - ps[1]) < safe]
        if near:
            problems.append("%d encounters inside the spawn-safe radius"
                            % len(near))
        closest = min(math.hypot(r["loc_cm"][0] - ps[0],
                                 r["loc_cm"][1] - ps[1]) for r in rows)
        print("      spawn        nearest row %.0f m out, bar %.0f m"
              % (closest / 100.0, safe / 100.0))
    else:
        problems.append("the plan declares no player_start_cm to check "
                        "against -- COULD NOT LOOK")

    # 4. archetype eligibility by elevation, 5. slope, 6. party size
    bar = float(plan.get("walkable_slope_deg", 90.0))
    _elig_before = len(problems)
    for i, r in enumerate(rows):
        a = arche.get(r["archetype"])
        if a is None:
            problems.append("row %d has unknown archetype %r"
                            % (i, r["archetype"]))
            continue
        if r["elevation_m"] < a.get("min_elevation_m", -1e9):
            problems.append("row %d %s at %.1f m, below its min_elevation_m "
                            "%.1f" % (i, a["name"], r["elevation_m"],
                                      a["min_elevation_m"]))
        if r.get("slope_deg", 0.0) > bar + 1e-6:
            problems.append("row %d slope %.2f exceeds the bar %.2f"
                            % (i, r["slope_deg"], bar))
        lo, hi = a["party_size"]
        if not (lo <= r["party_size"] <= hi):
            problems.append("row %d party %d outside [%d, %d]"
                            % (i, r["party_size"], lo, hi))
    if len(problems) == _elig_before:
        print("      eligibility  every row at or above its archetype's minimum "
              "elevation, under the %.2f deg bar, party in range" % bar)
    else:
        print("      eligibility  %d row(s) FAILED elevation / slope (%.2f deg "
              "bar) / party range -- see problems above"
              % (len(problems) - _elig_before, bar))

    # 7. the count bar
    g = rec["gates"]
    target = int(plan.get("target_count", 0))
    need = max(int(g.get("min_encounters_floor", 0)),
               int(math.ceil(float(g.get("min_fraction_of_target", 0.0))
                             * target)))
    if len(rows) < need:
        problems.append("%d rows against a binding bar of %d"
                        % (len(rows), need))
    print("      count        %d rows, target %d, binding bar %d"
          % (len(rows), target, need))
    return problems


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--half-cm", type=float, default=150000.0,
                    help="half-width of the synthetic area box")
    ap.add_argument("--prox-m", type=float, default=3000.0,
                    help="relaxed max_distance_from_reachable_m")
    args = ap.parse_args()

    base = json.loads(io.open(RECIPE, encoding="utf-8").read())
    recipe_sha = sha12(RECIPE)
    committed = os.path.join(REPO_ROOT, "encounters",
                             "%s_all.json" % base["region"])
    committed_sha = sha12(committed) if os.path.exists(committed) else None

    print("SYNTHETIC WORLD. The real basin CANNOT hold encounters and its")
    print("refusal is the correct answer. This proves the planner's success")
    print("path, not that the basin is dangerous.")
    print()
    print("recipe (read only)   recipes/encounters.json  sha %s" % recipe_sha)
    print("box                  %.1f km square centred on the town"
          % (2 * args.half_cm / 100000.0))
    print("proximity prior      %.0f m (relaxed from %s)"
          % (args.prox_m,
             base["exclusions"].get("max_distance_from_reachable_m")))
    print()

    scratch = tempfile.mkdtemp(prefix="prove_encounter_")
    rp = os.path.join(scratch, "synth.json")
    o1 = os.path.join(scratch, "out1.json")
    o2 = os.path.join(scratch, "out2.json")
    problems = []
    try:
        # --- the success path -------------------------------------------
        io.open(rp, "w", encoding="utf-8", newline="\n").write(
            json.dumps(synth_recipe(base, args.half_cm, args.prox_m), indent=1))
        rc, blob = run_planner(rp, o1)
        wrote = os.path.exists(o1)
        print("SUCCESS PATH   exit %d, wrote %s" % (rc, wrote))
        if rc != 0 or not wrote:
            tail = [l for l in blob.splitlines() if l.strip()]
            print("      %s" % (tail[-1][:170] if tail else "no output"))
            problems.append("the planner could not produce a plan in a world "
                            "built to permit one")
        else:
            plan = json.loads(io.open(o1, encoding="utf-8").read())
            print("      placed %d, target %d, by archetype %s"
                  % (len(plan["encounters"]), plan.get("target_count"),
                     plan.get("counts", {}).get("by_archetype")))
            problems += reverify(plan, base)

            # --- determinism -------------------------------------------
            rc2, _ = run_planner(rp, o2)
            same = (rc2 == 0 and os.path.exists(o2)
                    and sha12(o1) == sha12(o2))
            print("DETERMINISM    %s   %s vs %s"
                  % ("byte-identical" if same else "*** DIFFERS",
                     sha12(o1), sha12(o2) if os.path.exists(o2) else "-"))
            if not same:
                problems.append("two runs of the same recipe differ "
                                "(pipeline rule 3)")

        # --- the negative control ----------------------------------------
        for f in (o1, o2):
            if os.path.exists(f):
                os.remove(f)
        io.open(rp, "w", encoding="utf-8", newline="\n").write(
            json.dumps(synth_recipe(base, args.half_cm, args.prox_m,
                                    sep_scale=60.0), indent=1))
        rc3, blob3 = run_planner(rp, o1)
        wrote3 = os.path.exists(o1)
        print("NEGATIVE CTRL  separation x60 -> exit %d, wrote %s"
              % (rc3, wrote3))
        if rc3 == 0:
            problems.append("a separation no plan can satisfy was ACCEPTED")
        if wrote3:
            problems.append("the refusal WROTE ITS PLAN")
        if rc3 != 0 and not wrote3:
            tail = [l for l in blob3.splitlines() if l.strip()]
            print("      %s" % (tail[-1][:150] if tail else ""))
    finally:
        for f in (rp, o1, o2):
            if os.path.exists(f):
                os.remove(f)
        if os.path.isdir(scratch):
            os.rmdir(scratch)

    print()
    print("recipes/encounters.json   %s -> %s   %s"
          % (recipe_sha, sha12(RECIPE),
             "UNCHANGED" if recipe_sha == sha12(RECIPE) else "*** MOVED"))
    if committed_sha:
        now = sha12(committed) if os.path.exists(committed) else None
        print("encounters/%-14s %s -> %s   %s"
              % (os.path.basename(committed), committed_sha, now,
                 "UNCHANGED" if committed_sha == now else "*** MOVED"))
        if committed_sha != now:
            problems.append("the committed encounter plan was modified")
    if recipe_sha != sha12(RECIPE):
        problems.append("recipes/encounters.json was modified")

    print()
    if problems:
        print("FAILED: %d" % len(problems))
        for p in problems[:20]:
            print("  - %s" % p)
        if len(problems) > 20:
            print("  ... and %d more" % (len(problems) - 20))
        return 1
    print("THE SUCCESS PATH WORKS, and every invariant re-checked from the "
          "OUTPUT holds.")
    print("The planner refuses the real basin because the basin cannot hold "
          "an encounter,")
    print("not because it cannot place one.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
